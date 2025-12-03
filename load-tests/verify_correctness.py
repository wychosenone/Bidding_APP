"""
Correctness Verification Script for Experiment 1

This script verifies that the bidding system maintains correctness under high contention:
1. No lost updates - the final highest bid is indeed the maximum of all submitted bids
2. No incorrect rejections - no bid higher than the final price was incorrectly rejected
3. Consistency - Redis state matches the expected outcome

Usage:
    python verify_correctness.py --item-id contested_item_1 --api-url http://localhost:8080 --bids-file bids_submitted.json
"""

import argparse
import json
import requests
import sys
from typing import List, Dict

def verify_correctness(item_id: str, api_url: str, bids_submitted: List[Dict]) -> Dict:
    """
    Verify correctness of bidding system

    Args:
        item_id: ID of the item being bid on
        api_url: Base URL of the API
        bids_submitted: List of all bids submitted during the test
                       Each bid should have: {"user_id": str, "amount": float, "timestamp": float}

    Returns:
        Dictionary with verification results
    """
    print("\n" + "="*60)
    print("CORRECTNESS VERIFICATION")
    print("="*60)

    # Step 1: Get the final bid from Redis
    print(f"\n[1/4] Fetching final state from Redis for item: {item_id}")
    try:
        response = requests.get(f"{api_url}/api/v1/items/{item_id}", timeout=5)
        response.raise_for_status()
        final_state = response.json()
        final_bid = final_state.get("current_bid", 0)
        final_bidder = final_state.get("highest_bidder_id", "")
        print(f"      Final bid in Redis: ${final_bid:.2f}")
        print(f"      Winner: {final_bidder}")
    except Exception as e:
        print(f"      ERROR: Failed to fetch final state: {e}")
        return {"success": False, "error": str(e)}

    # Step 2: Calculate expected highest bid
    print(f"\n[2/4] Analyzing {len(bids_submitted)} submitted bids")
    if not bids_submitted:
        print("      WARNING: No bids were submitted!")
        return {"success": False, "error": "No bids submitted"}

    max_bid = max(bid["amount"] for bid in bids_submitted)
    min_bid = min(bid["amount"] for bid in bids_submitted)
    avg_bid = sum(bid["amount"] for bid in bids_submitted) / len(bids_submitted)

    print(f"      Max submitted bid: ${max_bid:.2f}")
    print(f"      Min submitted bid: ${min_bid:.2f}")
    print(f"      Avg submitted bid: ${avg_bid:.2f}")

    # Step 3: Verify no lost updates
    print(f"\n[3/4] Checking for lost updates")
    if final_bid != max_bid:
        print(f"      ❌ LOST UPDATE DETECTED!")
        print(f"         Expected: ${max_bid:.2f}")
        print(f"         Got:      ${final_bid:.2f}")
        print(f"         Difference: ${max_bid - final_bid:.2f}")
        lost_update = True
    else:
        print(f"      ✅ No lost updates - final bid matches maximum")
        lost_update = False

    # Step 4: Check for incorrectly rejected bids
    print(f"\n[4/4] Checking for incorrectly rejected bids")
    incorrectly_rejected = []

    # In our bidding system, a bid should only be rejected if it's <= current highest
    # We can't fully verify this without response logs, but we can check if any bid
    # higher than the final bid exists (which would indicate incorrect rejection)
    higher_bids = [b for b in bids_submitted if b["amount"] > final_bid]

    if higher_bids:
        print(f"      ⚠️  Found {len(higher_bids)} bids higher than final bid!")
        print(f"         This indicates potential incorrect rejections or race conditions")
        for bid in higher_bids[:5]:  # Show first 5
            print(f"         - ${bid['amount']:.2f} from {bid['user_id']}")
    else:
        print(f"      ✅ No bids higher than final bid found")

    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)

    success = not lost_update and not higher_bids

    result = {
        "success": success,
        "final_bid": final_bid,
        "expected_max_bid": max_bid,
        "lost_update": lost_update,
        "incorrectly_rejected_count": len(higher_bids),
        "total_bids_submitted": len(bids_submitted),
        "bid_range": {
            "min": min_bid,
            "max": max_bid,
            "avg": avg_bid
        }
    }

    if success:
        print("✅ PASSED - System maintained correctness under contention")
    else:
        print("❌ FAILED - Correctness violations detected")
        if lost_update:
            print("   - Lost update: Final bid != Max submitted bid")
        if higher_bids:
            print(f"   - {len(higher_bids)} bids higher than final bid")

    print("="*60 + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description="Verify bidding system correctness")
    parser.add_argument("--item-id", default="contested_item_1", help="Item ID to check")
    parser.add_argument("--api-url", default="http://localhost:8080", help="API base URL")
    parser.add_argument("--bids-file", help="JSON file containing submitted bids")
    parser.add_argument("--bids-json", help="JSON string of submitted bids")

    args = parser.parse_args()

    # Load bids
    if args.bids_file:
        with open(args.bids_file, 'r') as f:
            bids_submitted = json.load(f)
    elif args.bids_json:
        bids_submitted = json.loads(args.bids_json)
    else:
        print("ERROR: Must provide either --bids-file or --bids-json")
        sys.exit(1)

    # Run verification
    result = verify_correctness(args.item_id, args.api_url, bids_submitted)

    # Save result
    output_file = f"correctness_verification_{args.item_id}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Results saved to: {output_file}")

    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
