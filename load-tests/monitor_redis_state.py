#!/usr/bin/env python3
"""
Redis State Monitor for Experiment 3

Monitors the current_bid values in Redis during fault injection tests.
This validates that the write path continues to update Redis even when
secondary services (Broadcast, NATS, Archival) are down.

Usage:
    python monitor_redis_state.py --redis-host <host> --duration 180 --interval 5
"""

import argparse
import redis
import time
import json
from datetime import datetime


def monitor_redis(redis_host: str, redis_port: int, duration: int, interval: int):
    """Monitor Redis item bids over time"""

    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    # Test connection
    try:
        r.ping()
        print(f"Connected to Redis at {redis_host}:{redis_port}")
    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        return

    start_time = time.time()
    samples = []

    print(f"\nMonitoring Redis for {duration} seconds (sampling every {interval}s)...")
    print("-" * 60)

    while time.time() - start_time < duration:
        timestamp = datetime.now().strftime("%H:%M:%S")
        elapsed = int(time.time() - start_time)

        # Get all item keys
        item_keys = r.keys("item:*")

        item_bids = {}
        for key in item_keys:
            try:
                data = r.hgetall(key)
                if data:
                    item_id = key.split(":")[1] if ":" in key else key
                    current_bid = float(data.get("current_bid", 0))
                    item_bids[item_id] = current_bid
            except Exception as e:
                pass

        # Get max bid across all items
        max_bid = max(item_bids.values()) if item_bids else 0
        total_items = len(item_bids)

        sample = {
            "timestamp": timestamp,
            "elapsed_sec": elapsed,
            "total_items": total_items,
            "max_bid": max_bid,
            "item_bids": item_bids
        }
        samples.append(sample)

        # Print summary
        print(f"[{timestamp}] t={elapsed:3d}s | Items: {total_items} | Max bid: ${max_bid:.2f}")

        time.sleep(interval)

    print("-" * 60)
    print("\nSummary:")

    if len(samples) >= 2:
        first_max = samples[0]["max_bid"]
        last_max = samples[-1]["max_bid"]
        bid_increase = last_max - first_max

        print(f"  Start max bid: ${first_max:.2f}")
        print(f"  End max bid:   ${last_max:.2f}")
        print(f"  Increase:      ${bid_increase:.2f}")

        if bid_increase > 0:
            print(f"\n  ✓ Redis state was continuously updated during the test")
        else:
            print(f"\n  ✗ WARNING: No bid increase detected - write path may be blocked!")

    # Save detailed results
    output_file = f"redis_monitor_{int(time.time())}.json"
    with open(output_file, "w") as f:
        json.dump(samples, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Monitor Redis state during Experiment 3")
    parser.add_argument("--redis-host", type=str, required=True, help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port")
    parser.add_argument("--duration", type=int, default=180, help="Duration in seconds")
    parser.add_argument("--interval", type=int, default=5, help="Sampling interval in seconds")

    args = parser.parse_args()

    monitor_redis(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        duration=args.duration,
        interval=args.interval
    )


if __name__ == "__main__":
    main()
