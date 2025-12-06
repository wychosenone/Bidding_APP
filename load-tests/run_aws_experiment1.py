#!/usr/bin/env python3
"""
Run Experiment 1 on AWS with multiple user sizes
"""
import subprocess
import time
import json
from datetime import datetime

HOST = "http://bidding-system-alb-628791499.us-west-2.elb.amazonaws.com"
USER_SIZES = [100, 500, 1000, 2000, 10000]
DURATION = "60s"
SPAWN_RATE = 50

results = []

for users in USER_SIZES:
    print(f"\n{'='*60}")
    print(f"Testing with {users} concurrent users")
    print(f"{'='*60}\n")
    
    # Reset item state
    subprocess.run([
        "curl", "-s", "-X", "POST", 
        f"{HOST}/api/v1/items/contested_item_1/bid",
        "-H", "Content-Type: application/json",
        "-d", '{"user_id":"reset","amount":0.01}'
    ], capture_output=True)
    
    time.sleep(2)
    
    # Run locust
    cmd = [
        "locust", "-f", "locustfile_experiment1.py",
        "--headless",
        "-u", str(users),
        "-r", str(SPAWN_RATE),
        "-t", DURATION,
        "--host", HOST,
        "--csv", f"aws_exp1_{users}u"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    
    # Parse results from CSV
    try:
        with open(f"aws_exp1_{users}u_stats.csv", "r") as f:
            lines = f.readlines()
            # Get aggregated row
            for line in lines:
                if "Aggregated" in line:
                    parts = line.split(",")
                    results.append({
                        "users": users,
                        "total_requests": int(parts[2]),
                        "failures": int(parts[3]),
                        "avg_latency": float(parts[5]),
                        "p50": float(parts[6]),
                        "p95": float(parts[10]),
                        "p99": float(parts[12]),
                        "rps": float(parts[16])
                    })
    except Exception as e:
        print(f"Error parsing results: {e}")
    
    print(f"\nWaiting 10 seconds before next test...")
    time.sleep(10)

# Save results
print("\n" + "="*60)
print("EXPERIMENT 1 RESULTS SUMMARY (AWS - 4 API Gateway instances)")
print("="*60)
print(f"{'Users':>8} {'Requests':>10} {'Failures':>10} {'Avg(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10} {'RPS':>10}")
print("-"*70)
for r in results:
    print(f"{r['users']:>8} {r['total_requests']:>10} {r['failures']:>10} {r['avg_latency']:>10.1f} {r['p95']:>10.1f} {r['p99']:>10.1f} {r['rps']:>10.1f}")

output_file = "aws_experiment1_optimistic_fresh_results.json"
with open(output_file, "w") as f:
    json.dump({"timestamp": datetime.now().isoformat(), "strategy": "optimistic", "results": results}, f, indent=2)

print(f"\nResults saved to {output_file}")
