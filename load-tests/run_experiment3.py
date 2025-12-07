#!/usr/bin/env python3
"""
Automated runner for Experiment 3 (Resilience & Availability) on AWS ECS.

This script:
  - Starts the MixedWorkloadUser Locust test
  - Waits for a baseline period
  - Injects a failure into a target ECS service (3a / 3b / 3c)
  - Keeps the service down for a failure window
  - Restores the service

You can then read Locust CSVs / CloudWatch metrics and fill in EXPERIMENT_3_REPORT.md.
"""

import argparse
import subprocess
import sys
import time
from typing import Optional


def parse_duration_seconds(duration: str) -> int:
    """Parse simple duration strings like '180s' or '3m' into seconds."""
    duration = duration.strip().lower()
    if duration.endswith("s"):
        return int(duration[:-1])
    if duration.endswith("m"):
        return int(float(duration[:-1]) * 60)
    return int(duration)


def run_locust(
    host: str,
    users: int,
    spawn_rate: int,
    duration: str,
    csv_prefix: Optional[str],
) -> subprocess.Popen:
    cmd = [
        "locust",
        "-f",
        "locustfile.py",
        "--headless",
        "-u",
        str(users),
        "-r",
        str(spawn_rate),
        "-t",
        duration,
        "MixedWorkloadUser",
        "--host",
        host,
    ]

    if csv_prefix:
        cmd.extend(["--csv", csv_prefix])

    print("\nRunning Experiment 3 load (MixedWorkloadUser) with:")
    print(f"  host       = {host}")
    print(f"  users      = {users}")
    print(f"  spawn_rate = {spawn_rate}/s")
    print(f"  duration   = {duration}")
    if csv_prefix:
        print(f"  csv_prefix = {csv_prefix}")
    print(f"\nExecuting: {' '.join(cmd)}\n")

    return subprocess.Popen(cmd)


def update_ecs_service(
    service: str,
    desired_count: int,
    cluster: Optional[str],
    region: Optional[str],
) -> None:
    cmd = ["aws", "ecs", "update-service", "--service", service, "--desired-count", str(desired_count)]
    if cluster:
        cmd.extend(["--cluster", cluster])
    if region:
        cmd.extend(["--region", region])

    print(f"\n[Experiment 3] Updating ECS service: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("[WARN] aws CLI not found. Please run this command manually:")
        print(" ", " ".join(cmd))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Experiment 3 (Resilience & Availability) on AWS ECS.")
    parser.add_argument("--host", type=str, required=True, help="API Gateway host, e.g. http://<ALB-DNS>")
    parser.add_argument("--users", type=int, default=100, help="Number of concurrent users (default: 100)")
    parser.add_argument("--spawn-rate", type=int, default=10, help="User spawn rate per second (default: 10)")
    parser.add_argument("--duration", type=str, default="180s", help="Total test duration, e.g. 180s, 3m (default: 180s)")
    parser.add_argument("--csv-prefix", type=str, default=None, help="Optional Locust CSV prefix for saving metrics")

    parser.add_argument(
        "--scenario",
        type=str,
        choices=["3a", "3b", "3c"],
        required=True,
        help="Which Experiment 3 scenario to run: 3a (broadcast), 3b (archival worker), 3c (nats)",
    )
    parser.add_argument("--ecs-cluster", type=str, default=None, help="ECS cluster name (optional if defaulted in AWS)")
    parser.add_argument(
        "--broadcast-service",
        type=str,
        default="bidding-system-broadcast-service",
        help="ECS service name for broadcast-service (3a)",
    )
    parser.add_argument(
        "--archival-service",
        type=str,
        default="bidding-system-archival-worker",
        help="ECS service name for archival worker (3b)",
    )
    parser.add_argument(
        "--nats-service",
        type=str,
        default="bidding-system-nats",
        help="ECS service name for NATS / JetStream (3c)",
    )
    parser.add_argument("--region", type=str, default="us-west-2", help="AWS region (default: us-west-2)")

    parser.add_argument(
        "--baseline-seconds",
        type=int,
        default=30,
        help="Seconds to wait before injecting failure (default: 30)",
    )
    parser.add_argument(
        "--failure-seconds",
        type=int,
        default=45,
        help="Seconds to keep target service at desired-count=0 (default: 45)",
    )
    parser.add_argument(
        "--recovery-count",
        type=int,
        default=1,
        help="Desired count to restore for the target ECS service (default: 1)",
    )

    args = parser.parse_args()

    total_seconds = parse_duration_seconds(args.duration)
    if args.baseline_seconds + args.failure_seconds >= total_seconds:
        print(
            f"[WARN] baseline({args.baseline_seconds}) + failure({args.failure_seconds}) "
            f">= total duration ({total_seconds}). Consider increasing --duration."
        )

    # Decide which service to target based on scenario
    if args.scenario == "3a":
        target_service = args.broadcast_service
        scenario_desc = "3a - Broadcast Service Failure"
    elif args.scenario == "3b":
        target_service = args.archival_service
        scenario_desc = "3b - Archival Worker Failure"
    else:
        target_service = args.nats_service
        scenario_desc = "3c - NATS Failure"

    print(f"\n[Experiment 3] Starting scenario: {scenario_desc}")
    print(f"  Target ECS service: {target_service}")
    print(f"  Baseline seconds : {args.baseline_seconds}")
    print(f"  Failure seconds  : {args.failure_seconds}")
    print(f"  Recovery count   : {args.recovery_count}")

    locust_proc = run_locust(
        host=args.host,
        users=args.users,
        spawn_rate=args.spawn_rate,
        duration=args.duration,
        csv_prefix=args.csv_prefix,
    )

    # Baseline period
    print(f"\n[Experiment 3] Baseline phase: sleeping {args.baseline_seconds}s before injecting failure...")
    time.sleep(args.baseline_seconds)

    # Inject failure: desired-count=0
    print("\n[Experiment 3] Injecting failure: setting desired-count=0")
    update_ecs_service(
        service=target_service,
        desired_count=0,
        cluster=args.ecs_cluster,
        region=args.region,
    )

    # Failure window
    print(f"[Experiment 3] Failure phase: sleeping {args.failure_seconds}s with service down...")
    time.sleep(args.failure_seconds)

    # Recover: restore desired-count
    print(f"\n[Experiment 3] Recovering service: setting desired-count={args.recovery_count}")
    update_ecs_service(
        service=target_service,
        desired_count=args.recovery_count,
        cluster=args.ecs_cluster,
        region=args.region,
    )

    # Wait for Locust to finish
    print("\n[Experiment 3] Waiting for Locust run to complete...")
    return_code = locust_proc.wait()
    print(f"[Experiment 3] Locust finished with exit code {return_code}")

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())


