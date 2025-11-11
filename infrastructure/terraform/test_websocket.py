#!/usr/bin/env python3
"""Simple WebSocket client to test real-time bid updates"""

import asyncio
import websockets
import json
import sys

async def test_websocket(item_id):
    ws_url = f"ws://bidding-system-alb-137918056.us-west-2.elb.amazonaws.com/ws/items/{item_id}"

    print(f"Connecting to WebSocket: {ws_url}")

    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"✅ Connected! Listening for updates on item '{item_id}'...")
            print("Waiting for bid events (will timeout after 30 seconds)...")

            # Listen for messages with timeout
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                print(f"\n🎉 Received update: {message}")

                # Try to parse as JSON
                try:
                    data = json.loads(message)
                    print(f"\nParsed data:")
                    print(f"  Item ID: {data.get('item_id', 'N/A')}")
                    print(f"  User ID: {data.get('user_id', 'N/A')}")
                    print(f"  Amount: ${data.get('amount', 'N/A')}")
                    print(f"  Timestamp: {data.get('timestamp', 'N/A')}")
                except json.JSONDecodeError:
                    print(f"  Raw message: {message}")

                return True
            except asyncio.TimeoutError:
                print("\n⏱️  No messages received within 30 seconds")
                return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    item_id = sys.argv[1] if len(sys.argv) > 1 else "test_item_ws_001"

    print("=" * 60)
    print("Real-time WebSocket Test")
    print("=" * 60)

    success = asyncio.run(test_websocket(item_id))

    if success:
        print("\n✅ Real-time path verified: API → Redis Pub/Sub → Broadcast → WebSocket")
    else:
        print("\n⚠️  No updates received - WebSocket connection works but no bids detected")

    sys.exit(0 if success else 1)
