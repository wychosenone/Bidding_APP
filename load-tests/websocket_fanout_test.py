"""
WebSocket Fan-Out Scalability Test (Experiment 2)

This script tests the broadcast latency as the number of concurrent
WebSocket connections increases.

Measures:
- Time for a single bid event to reach all N connected clients
- P50, P95, P99 latencies
- CPU and memory usage of the broadcast service
Usage:
    python websocket_fanout_test.py --connections 1000 --bids 10 --interval 5
"""

import asyncio
import functools
import websockets
import json
import time
import statistics
import argparse
from datetime import datetime, timezone
import requests


class WebSocketFanOutTest:
    def __init__(self, ws_url, api_url, item_id, num_connections, use_client_time=False, listen_only=False, duration=60):
        self.ws_url = ws_url
        self.api_url = api_url
        self.item_id = item_id
        self.num_connections = num_connections
        # When True, compute latency purely from client-side times (receive_time - send_time),
        # ignoring server timestamps. This avoids issues with clock drift between servers
        # and distributed test clients.
        self.use_client_time = use_client_time
        # When True, only listen for messages without sending bids.
        # Use this for distributed testing where only one instance sends bids.
        self.listen_only = listen_only
        # Duration in seconds for listen-only mode
        self.duration = duration
        self.connections = []
        self.latencies = []
        self.message_count = 0

    async def connect_client(self, client_id):
        """Connect a single WebSocket client"""
        try:
            # Handle both cases: ws_url with or without /ws
            # Remove trailing /ws if present, then add /ws/items/{id}
            base_url = self.ws_url.rstrip('/')
            if base_url.endswith('/ws'):
                base_url = base_url[:-3]  # Remove /ws
            uri = f"{base_url}/ws/items/{self.item_id}"
            ws = await websockets.connect(uri)
            return ws
        except Exception as e:
            print(f"Failed to connect client {client_id}: {e}")
            return None

    def parse_server_timestamp(self, timestamp_str):
        """Parse server timestamp (ISO 8601 format) to Unix epoch"""
        if not timestamp_str:
            return None
        try:
            # Handle various ISO 8601 formats
            # e.g., "2025-12-05T10:30:00.123456Z" or "2025-12-05T10:30:00Z"
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            dt = datetime.fromisoformat(timestamp_str)
            return dt.timestamp()
        except Exception:
            return None

    async def listen_client(self, ws, client_id, event_id_queue):
        """Listen for messages on a WebSocket connection"""
        try:
            async for message in ws:
                data = json.loads(message)

                # Check if this is a bid event (not the welcome message)
                if data.get("type") != "connected" and "event_id" in data:
                    event_id = data["event_id"]
                    receive_time = time.time()

                    # Extract server timestamp for accurate latency calculation
                    server_timestamp = self.parse_server_timestamp(data.get("timestamp"))

                    # Record when this client received the event
                    await event_id_queue.put({
                        "client_id": client_id,
                        "event_id": event_id,
                        "receive_time": receive_time,
                        "server_timestamp": server_timestamp
                    })

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"Client {client_id} error: {e}")

    async def establish_connections(self):
        """Establish N WebSocket connections"""
        print(f"Establishing {self.num_connections} WebSocket connections...")

        tasks = []
        for i in range(self.num_connections):
            task = self.connect_client(i)
            tasks.append(task)

        self.connections = await asyncio.gather(*tasks)
        self.connections = [conn for conn in self.connections if conn is not None]

        print(f"Successfully connected {len(self.connections)} clients")
        return len(self.connections)

    async def get_current_bid(self):
        """Get the current bid for the item"""
        url = f"{self.api_url}/api/v1/items/{self.item_id}"
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                functools.partial(requests.get, url)
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("current_bid", 0.0)
        except Exception as e:
            print(f"Failed to get current bid: {e}")
        return 0.0

    async def send_bid(self, bid_amount):
        """Send a bid via HTTP API and record the timestamp"""
        send_time = time.time()

        payload = {
            "user_id": "load_test_user",
            "amount": bid_amount
        }

        url = f"{self.api_url}/api/v1/items/{self.item_id}/bid"

        # Use thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            functools.partial(requests.post, url, json=payload)
        )

        if response.status_code in [200, 201]:
            return send_time, response.json()
        else:
            print(f"Failed to send bid: {response.status_code} - {response.text}")
            return None, None

    async def run_fanout_test(self, num_bids=10, interval=5):
        """Run the fan-out test"""
        # Create a queue to collect received events
        event_queue = asyncio.Queue()

        # Start listening on all connections
        listen_tasks = []
        for i, ws in enumerate(self.connections):
            task = asyncio.create_task(self.listen_client(ws, i, event_queue))
            listen_tasks.append(task)

        print(f"\nStarting fan-out test with {num_bids} bids, {interval}s interval...")
        print(f"Watching {len(self.connections)} connections\n")

        # Get current bid and start from a higher amount
        current_bid = await self.get_current_bid()
        # If item is new (current_bid = 0), start from $100, otherwise start from current + 1
        if current_bid == 0:
            start_amount = 100.0
            print(f"New item detected, starting from: ${start_amount:.2f}\n")
        else:
            start_amount = max(100.0, current_bid + 1.0)
            print(f"Current bid: ${current_bid:.2f}, starting from: ${start_amount:.2f}\n")

        results = []

        for bid_num in range(num_bids):
            bid_amount = start_amount + bid_num

            # Send bid
            send_time, response = await self.send_bid(bid_amount)

            if send_time is None:
                continue

            # Get the event_id from response to filter messages
            current_event_id = response.get("event_id") if response else None

            print(f"Bid {bid_num + 1}/{num_bids}: ${bid_amount:.2f} sent at {datetime.fromtimestamp(send_time).strftime('%H:%M:%S.%f')[:-3]}")
            if current_event_id:
                print(f"  Event ID: {current_event_id[:8]}...")

            # Collect responses for this bid
            received_times = []
            stale_events = []  # Events from previous bids
            timeout = time.time() + 10  # 10 second timeout

            while len(received_times) < len(self.connections):
                if time.time() > timeout:
                    print(f"  Timeout: Only {len(received_times)}/{len(self.connections)} clients received the event")
                    break

                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)

                    # Filter by event_id if available
                    if current_event_id and event.get("event_id") != current_event_id:
                        stale_events.append(event)
                        continue

                    # Calculate latency.
                    # Option 1 (default): use server timestamp for "true" end-to-end latency
                    #   latency = client_receive_time - server_bid_accept_time
                    # Option 2 (--use-client-time): use client-side timing only
                    #   latency = client_receive_time - client_send_time
                    if self.use_client_time:
                        # Pure client-observed latency, robust to cross-machine clock drift.
                        latency_ms = (event["receive_time"] - send_time) * 1000
                    elif event.get("server_timestamp"):
                        # Use server timestamp for accurate latency (avoids client clock skew).
                        latency_ms = (event["receive_time"] - event["server_timestamp"]) * 1000
                    else:
                        # Fallback to local send_time if no server timestamp is available.
                        latency_ms = (event["receive_time"] - send_time) * 1000

                    # Skip negative latencies (indicates clock sync issues)
                    if latency_ms < 0:
                        print(f"  Warning: Negative latency {latency_ms:.2f}ms (clock sync issue)")
                        continue

                    received_times.append(latency_ms)
                except asyncio.TimeoutError:
                    continue

            if stale_events:
                print(f"  Filtered out {len(stale_events)} stale events from previous bids")

            if received_times:
                results.append(received_times)
                self.print_latency_stats(received_times, len(self.connections))

            # Wait before next bid
            if bid_num < num_bids - 1:
                await asyncio.sleep(interval)

        # Close all connections
        for ws in self.connections:
            await ws.close()

        # Cancel listen tasks
        for task in listen_tasks:
            task.cancel()

        return results

    def print_latency_stats(self, latencies, expected_count):
        """Print latency statistics for a single bid event"""
        if not latencies:
            print("  No latencies recorded")
            return

        latencies.sort()
        count = len(latencies)

        print(f"  Received by: {count}/{expected_count} clients")
        print(f"  Latency - Min: {min(latencies):.2f}ms, Median: {statistics.median(latencies):.2f}ms, Max: {max(latencies):.2f}ms")

        if count >= 20:
            p95 = latencies[int(count * 0.95)]
            p99 = latencies[int(count * 0.99)]
            print(f"  P95: {p95:.2f}ms, P99: {p99:.2f}ms")

    def print_summary(self, all_results):
        """Print overall test summary"""
        all_latencies = [lat for result in all_results for lat in result]

        if not all_latencies:
            print("\nNo data collected")
            return

        all_latencies.sort()

        print("\n" + "="*60)
        print("EXPERIMENT 2: WebSocket Fan-Out Test Results")
        print("="*60)
        print(f"Configuration:")
        print(f"  Connections: {len(self.connections)}")
        print(f"  Total bids sent: {len(all_results)}")
        print(f"  Total messages received: {len(all_latencies)}")
        print(f"\nOverall Latency Statistics:")
        print(f"  Min: {min(all_latencies):.2f}ms")
        print(f"  Median: {statistics.median(all_latencies):.2f}ms")
        print(f"  Mean: {statistics.mean(all_latencies):.2f}ms")
        print(f"  Max: {max(all_latencies):.2f}ms")

        count = len(all_latencies)
        p50 = all_latencies[int(count * 0.50)]
        p95 = all_latencies[int(count * 0.95)]
        p99 = all_latencies[int(count * 0.99)]

        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")
        print("="*60 + "\n")

    async def run_listen_only(self):
        """Run in listen-only mode - collect messages and compute latencies with clock offset correction"""
        event_queue = asyncio.Queue()

        # Start listening on all connections
        listen_tasks = []
        for i, ws in enumerate(self.connections):
            task = asyncio.create_task(self.listen_client(ws, i, event_queue))
            listen_tasks.append(task)

        print(f"\n[LISTEN-ONLY MODE] Listening for {self.duration} seconds...")
        print(f"Watching {len(self.connections)} connections\n")

        # Collect ALL latencies including negative ones for clock offset correction
        raw_latencies = []
        start_time = time.time()
        messages_received = 0
        negative_count = 0

        while time.time() - start_time < self.duration:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                messages_received += 1

                # Use server_timestamp for latency calculation
                if event.get("server_timestamp"):
                    latency_ms = (event["receive_time"] - event["server_timestamp"]) * 1000
                    raw_latencies.append(latency_ms)
                    if latency_ms < 0:
                        negative_count += 1

                # Print progress every 1000 messages
                if messages_received % 1000 == 0:
                    print(f"  Received {messages_received} messages...")

            except asyncio.TimeoutError:
                continue

        # Close connections
        for ws in self.connections:
            await ws.close()
        for task in listen_tasks:
            task.cancel()

        # Calculate clock offset if there are negative latencies
        clock_offset = 0.0
        if negative_count > 0 and raw_latencies:
            # Use the minimum latency as the clock offset (most negative value indicates clock drift)
            min_latency = min(raw_latencies)
            if min_latency < 0:
                clock_offset = abs(min_latency) + 10  # Add 10ms buffer for network latency
                print(f"\n  Clock offset detected: {clock_offset:.2f}ms (correcting {negative_count} negative samples)")

        # Apply clock offset correction
        corrected_latencies = [lat + clock_offset for lat in raw_latencies]
        # Filter out any remaining negative values (should be none after correction)
        corrected_latencies = [lat for lat in corrected_latencies if lat >= 0]

        # Print results
        print("\n" + "="*60)
        print("EXPERIMENT 2: Listen-Only Results")
        print("="*60)
        print(f"Configuration:")
        print(f"  Connections: {len(self.connections)}")
        print(f"  Duration: {self.duration}s")
        print(f"  Total messages received: {messages_received}")
        print(f"  Raw latency samples: {len(raw_latencies)}")
        print(f"  Negative samples (clock drift): {negative_count}")
        print(f"  Clock offset applied: {clock_offset:.2f}ms")
        print(f"  Valid latency samples after correction: {len(corrected_latencies)}")

        if corrected_latencies:
            corrected_latencies.sort()
            count = len(corrected_latencies)
            print(f"\nLatency Statistics (after clock offset correction):")
            print(f"  Min: {min(corrected_latencies):.2f}ms")
            print(f"  Median: {statistics.median(corrected_latencies):.2f}ms")
            print(f"  Mean: {statistics.mean(corrected_latencies):.2f}ms")
            print(f"  Max: {max(corrected_latencies):.2f}ms")
            print(f"  P50: {corrected_latencies[int(count * 0.50)]:.2f}ms")
            print(f"  P95: {corrected_latencies[int(count * 0.95)]:.2f}ms")
            print(f"  P99: {corrected_latencies[int(count * 0.99)]:.2f}ms")
        print("="*60 + "\n")

        return corrected_latencies


async def main():
    parser = argparse.ArgumentParser(description="WebSocket Fan-Out Load Test")
    parser.add_argument("--connections", type=int, default=100, help="Number of WebSocket connections (default: 100)")
    parser.add_argument("--bids", type=int, default=10, help="Number of bids to send (default: 10)")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between bids (default: 5)")
    parser.add_argument("--ws-url", type=str, default="ws://localhost:8081", help="WebSocket server URL")
    parser.add_argument("--api-url", type=str, default="http://localhost:8080", help="API server URL")
    parser.add_argument("--item-id", type=str, default=None, help="Item ID to test (default: auto-generate unique ID)")
    parser.add_argument(
        "--use-client-time",
        action="store_true",
        help=(
            "Compute latency using client-side timing only "
            "(receive_time - send_time) to avoid cross-machine clock drift. "
            "Recommended when running distributed tests from multiple EC2 instances."
        ),
    )
    parser.add_argument(
        "--listen-only",
        action="store_true",
        help=(
            "Only listen for messages without sending bids. "
            "Use this for distributed testing where only one instance sends bids."
        ),
    )
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds for listen-only mode (default: 60)")

    args = parser.parse_args()

    # Generate unique item ID if not provided (ensures fresh start for each test)
    if args.item_id is None:
        import uuid
        args.item_id = f"test_item_{uuid.uuid4().hex[:8]}"
        print(f"Using auto-generated item ID: {args.item_id}")
        print(f"  (Each test run will start with a fresh item at $0.00)")

    test = WebSocketFanOutTest(
        ws_url=args.ws_url,
        api_url=args.api_url,
        item_id=args.item_id,
        num_connections=args.connections,
        use_client_time=args.use_client_time,
        listen_only=args.listen_only,
        duration=args.duration,
    )

    # Establish connections
    connected = await test.establish_connections()

    if connected == 0:
        print("Failed to establish any connections. Exiting.")
        return

    # Run test based on mode
    if args.listen_only:
        await test.run_listen_only()
    else:
        results = await test.run_fanout_test(num_bids=args.bids, interval=args.interval)
        test.print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
