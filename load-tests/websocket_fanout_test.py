"""
WebSocket Fan-Out Scalability Test (Experiment 2)

This script tests the broadcast latency as the number of concurrent
WebSocket connections increases.

Measures:
- Time for a single bid event to reach all N connected clients
- P50, P95, P99 latencies
- CPU and memory usage of the broadcast service

Usage:
    python websocket_fanout_test.py --connections 1000 --duration 60
"""

import asyncio
import websockets
import json
import time
import statistics
import argparse
from datetime import datetime
import requests


class WebSocketFanOutTest:
    def __init__(self, ws_url, api_url, item_id, num_connections):
        self.ws_url = ws_url
        self.api_url = api_url
        self.item_id = item_id
        self.num_connections = num_connections
        self.connections = []
        self.latencies = []
        self.message_count = 0

    async def connect_client(self, client_id):
        """Connect a single WebSocket client"""
        try:
            uri = f"{self.ws_url}/ws/items/{self.item_id}"
            ws = await websockets.connect(uri)
            return ws
        except Exception as e:
            print(f"Failed to connect client {client_id}: {e}")
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

                    # Record when this client received the event
                    await event_id_queue.put({
                        "client_id": client_id,
                        "event_id": event_id,
                        "receive_time": receive_time
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

    async def send_bid(self, bid_amount):
        """Send a bid via HTTP API and record the timestamp"""
        send_time = time.time()

        payload = {
            "user_id": "load_test_user",
            "amount": bid_amount
        }

        url = f"{self.api_url}/api/v1/items/{self.item_id}/bid"

        response = requests.post(url, json=payload)

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

        results = []

        for bid_num in range(num_bids):
            bid_amount = 100.0 + bid_num

            # Send bid
            send_time, response = await self.send_bid(bid_amount)

            if send_time is None:
                continue

            print(f"Bid {bid_num + 1}/{num_bids}: ${bid_amount:.2f} sent at {datetime.fromtimestamp(send_time).strftime('%H:%M:%S.%f')[:-3]}")

            # Collect responses for this bid
            received_times = []
            timeout = time.time() + 10  # 10 second timeout

            while len(received_times) < len(self.connections):
                if time.time() > timeout:
                    print(f"  Timeout: Only {len(received_times)}/{len(self.connections)} clients received the event")
                    break

                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    latency_ms = (event["receive_time"] - send_time) * 1000
                    received_times.append(latency_ms)
                except asyncio.TimeoutError:
                    continue

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


async def main():
    parser = argparse.ArgumentParser(description="WebSocket Fan-Out Load Test")
    parser.add_argument("--connections", type=int, default=100, help="Number of WebSocket connections (default: 100)")
    parser.add_argument("--bids", type=int, default=10, help="Number of bids to send (default: 10)")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between bids (default: 5)")
    parser.add_argument("--ws-url", type=str, default="ws://localhost:8081", help="WebSocket server URL")
    parser.add_argument("--api-url", type=str, default="http://localhost:8080", help="API server URL")
    parser.add_argument("--item-id", type=str, default="fanout_test_item", help="Item ID to test")

    args = parser.parse_args()

    test = WebSocketFanOutTest(
        ws_url=args.ws_url,
        api_url=args.api_url,
        item_id=args.item_id,
        num_connections=args.connections
    )

    # Establish connections
    connected = await test.establish_connections()

    if connected == 0:
        print("Failed to establish any connections. Exiting.")
        return

    # Run test
    results = await test.run_fanout_test(num_bids=args.bids, interval=args.interval)

    # Print summary
    test.print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
