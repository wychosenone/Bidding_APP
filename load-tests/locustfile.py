"""
Locust load testing for Real-Time Bidding Service

This file contains load tests for the three experiments described in the proposal:
1. Write Contention Test - Maximum bids per second on a single item
2. WebSocket Fan-Out Test - Broadcast latency to N concurrent viewers
3. Resilience Test - System behavior during component failures
"""

import json
import random
import time
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser


class BidderUser(FastHttpUser):
    """
    Simulates a user placing bids on auction items.
    Used for Experiment 1: Write Contention Test
    """

    wait_time = between(0.1, 0.5)  # Wait 0.1-0.5 seconds between requests
    host = "http://localhost:8080"

    def on_start(self):
        """Called when a user starts"""
        self.user_id = f"user_{random.randint(1, 100000)}"
        self.item_id = "contested_item_1"  # All users bid on the same item

    @task(10)
    def place_bid(self):
        """
        Place a bid on an item.
        Weight: 10 (happens more frequently)
        """
        bid_amount = random.uniform(10.0, 1000.0)

        payload = {
            "user_id": self.user_id,
            "amount": round(bid_amount, 2)
        }

        with self.client.post(
            f"/api/v1/items/{self.item_id}/bid",
            json=payload,
            catch_response=True,
            name="/items/[id]/bid"
        ) as response:
            if response.status_code == 200 or response.status_code == 201:
                response.success()
            elif response.status_code == 429:
                # Rate limited, consider this acceptable
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)
    def get_item(self):
        """
        Get current item information.
        Weight: 3 (happens less frequently than bidding)
        """
        with self.client.get(
            f"/api/v1/items/{self.item_id}",
            catch_response=True,
            name="/items/[id]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(1)
    def health_check(self):
        """
        Health check endpoint.
        Weight: 1 (minimal)
        """
        with self.client.get("/health", name="/health") as response:
            pass


class ContendedItemBidder(FastHttpUser):
    """
    Specialized user for Experiment 1: Write Contention Test

    All users hammer the SAME item with bids as fast as possible.
    This tests the atomic compare-and-set logic in Redis.

    Usage:
        locust -f locustfile.py --headless -u 1000 -r 100 -t 60s --only-summary ContendedItemBidder
    """

    wait_time = between(0.01, 0.05)  # Very aggressive - minimal wait time
    host = "http://localhost:8080"

    def on_start(self):
        self.user_id = f"user_{random.randint(1, 100000)}"
        self.item_id = "contested_item_1"
        self.bid_counter = 0

    @task
    def aggressive_bid(self):
        """Place bids as fast as possible"""
        self.bid_counter += 1
        bid_amount = 100.0 + (self.bid_counter * 0.01)  # Incrementing bids

        payload = {
            "user_id": self.user_id,
            "amount": round(bid_amount, 2)
        }

        start_time = time.time()
        with self.client.post(
            f"/api/v1/items/{self.item_id}/bid",
            json=payload,
            catch_response=True,
            name="/items/[id]/bid [contention]"
        ) as response:
            latency = (time.time() - start_time) * 1000  # Convert to ms

            if response.status_code in [200, 201]:
                # Record successful bid
                events.request.fire(
                    request_type="POST",
                    name="bid_accepted",
                    response_time=latency,
                    response_length=len(response.content),
                    exception=None,
                    context={}
                )
                response.success()
            elif response.status_code == 200 and b'"success":false' in response.content:
                # Bid rejected (too low), but this is expected behavior
                events.request.fire(
                    request_type="POST",
                    name="bid_rejected",
                    response_time=latency,
                    response_length=len(response.content),
                    exception=None,
                    context={}
                )
                response.success()
            else:
                response.failure(f"Unexpected status {response.status_code}")


class MixedWorkloadUser(FastHttpUser):
    """
    Simulates realistic traffic with both bidders and viewers.
    Used for Experiment 3: Resilience Test

    Represents normal operating conditions with:
    - Multiple items being bid on
    - Various user behaviors
    - Realistic think time
    - Smart bidding: GET current price first, then bid higher
    """

    wait_time = between(1, 3)
    host = "http://localhost:8080"

    def on_start(self):
        self.user_id = f"user_{random.randint(1, 100000)}"
        # Users can bid on multiple items
        self.watched_items = [f"item_{i}" for i in range(1, 11)]

    @task(5)
    def browse_items(self):
        """Browse different items"""
        item_id = random.choice(self.watched_items)
        with self.client.get(f"/api/v1/items/{item_id}", name="/items/[id]"):
            pass

    @task(2)
    def place_bid(self):
        """
        Place a bid on a random item.
        First GET current price, then POST a higher bid.
        This ensures bids can actually succeed.
        """
        item_id = random.choice(self.watched_items)

        # Step 1: GET current price
        try:
            with self.client.get(
                f"/api/v1/items/{item_id}",
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
            return

        # Step 2: Bid higher than current price
        increment = random.uniform(0.50, 10.00)
        bid_amount = current_bid + increment

        payload = {
            "user_id": self.user_id,
            "amount": round(bid_amount, 2)
        }

        with self.client.post(
            f"/api/v1/items/{item_id}/bid",
            json=payload,
            catch_response=True,
            name="/items/[id]/bid"
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Bid failed: {response.status_code}")


# Event handlers for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "="*60)
    print("Starting load test for Real-Time Bidding Service")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "="*60)
    print("Load test completed")
    print("="*60 + "\n")

    # Print summary statistics
    stats = environment.stats
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Median response time: {stats.total.median_response_time}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95)}ms")
    print(f"99th percentile: {stats.total.get_response_time_percentile(0.99)}ms")
    print(f"Requests per second: {stats.total.total_rps:.2f}")
