"""
Enhanced Locust test for Experiment 1 with correctness tracking

This version records all submitted bids for post-test verification
"""

import json
import random
import time
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
from threading import Lock

# Global data structures for tracking bids
submitted_bids = []
bids_lock = Lock()

class ContendedItemBidder(FastHttpUser):
    """
    Experiment 1: Write Contention Test with bid tracking
    All users hammer the SAME item with incrementing bids
    """

    wait_time = between(0.01, 0.05)
    host = "http://localhost:8080"

    def on_start(self):
        self.user_id = f"user_{random.randint(1, 1000000)}"
        self.item_id = "contested_item_1"
        self.bid_counter = 0

    @task
    def realistic_bid(self):
        """
        Realistic bidding behavior: GET current price, then POST higher bid
        This simulates real users who check the current price before bidding
        """
        # Step 1: GET current item price
        try:
            with self.client.get(
                f"/api/v1/items/{self.item_id}",
                catch_response=True,
                name="/items/[id] [price check]"
            ) as get_response:
                if get_response.status_code == 200:
                    item_data = get_response.json()
                    current_bid = item_data.get("current_bid", 0)
                    get_response.success()
                else:
                    get_response.failure(f"Failed to get item: {get_response.status_code}")
                    return
        except Exception as e:
            print(f"Error getting current price: {e}")
            return

        # Step 2: Calculate a higher bid
        # Realistic increment: $0.50 to $10.00 above current price
        increment = random.uniform(0.50, 10.00)
        bid_amount = current_bid + increment

        payload = {
            "user_id": self.user_id,
            "amount": round(bid_amount, 2)
        }

        start_time = time.time()

        # Record the bid submission
        with bids_lock:
            submitted_bids.append({
                "user_id": self.user_id,
                "amount": payload["amount"],
                "timestamp": start_time,
                "current_price_when_submitted": current_bid
            })

        # Step 3: POST the bid
        with self.client.post(
            f"/api/v1/items/{self.item_id}/bid",
            json=payload,
            catch_response=True,
            name="/items/[id]/bid [contention]"
        ) as response:
            latency = (time.time() - start_time) * 1000

            if response.status_code in [200, 201]:
                # Parse response to see if bid was accepted
                try:
                    result = response.json()
                    if result.get("success"):
                        events.request.fire(
                            request_type="POST",
                            name="bid_accepted",
                            response_time=latency,
                            response_length=len(response.content),
                            exception=None,
                            context={}
                        )
                    else:
                        events.request.fire(
                            request_type="POST",
                            name="bid_rejected",
                            response_time=latency,
                            response_length=len(response.content),
                            exception=None,
                            context={}
                        )
                except:
                    pass
                response.success()
            else:
                response.failure(f"Unexpected status {response.status_code}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global submitted_bids
    submitted_bids = []  # Reset
    print("\n" + "="*60)
    print("EXPERIMENT 1: Write Contention Test")
    print("="*60)
    print("Tracking all submitted bids for correctness verification")
    print()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "="*60)
    print("EXPERIMENT 1 COMPLETED")
    print("="*60)

    # Print summary
    stats = environment.stats
    print(f"\nPerformance Metrics:")
    print(f"  Total requests: {stats.total.num_requests}")
    print(f"  Total failures: {stats.total.num_failures}")
    print(f"  Median latency: {stats.total.median_response_time}ms")
    print(f"  P95 latency: {stats.total.get_response_time_percentile(0.95)}ms")
    print(f"  P99 latency: {stats.total.get_response_time_percentile(0.99)}ms")
    print(f"  Requests/sec: {stats.total.total_rps:.2f}")

    # Save submitted bids for verification
    output_file = "/tmp/localstack_exp1_bids_submitted.json"
    with open(output_file, 'w') as f:
        json.dump(submitted_bids, f, indent=2)

    print(f"\nCorrectness Tracking:")
    print(f"  Total bids submitted: {len(submitted_bids)}")
    print(f"  Bids saved to: {output_file}")
    print(f"  Run verify_correctness.py to check for lost updates\n")
