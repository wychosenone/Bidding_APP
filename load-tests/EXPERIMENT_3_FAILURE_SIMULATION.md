# Experiment 3: How Component Failures Are Simulated

## Overview

Experiment 3 simulates component failures by **scaling ECS Fargate services to zero instances** using AWS ECS service management. This creates a controlled "failure" scenario where a service becomes completely unavailable.

---

## 🔧 Failure Simulation Mechanism

### Core Method: ECS Service Scaling

The script uses AWS ECS's `update-service` command to change the `desired-count` of a service:

```python
def update_ecs_service(service: str, desired_count: int, ...):
    cmd = ["aws", "ecs", "update-service", 
           "--service", service, 
           "--desired-count", str(desired_count)]
    subprocess.run(cmd)
```

### What Happens When `desired-count = 0`?

When you set `desired-count = 0` for an ECS service:

1. **ECS stops all running tasks** for that service
2. **No new tasks are started** (desired = 0)
3. **Service becomes completely unavailable**
4. **Load balancer health checks fail** → removes service from target group
5. **Existing connections are terminated** (graceful shutdown)

**This effectively simulates a complete service outage.**

---

## 📊 Three Failure Scenarios

### Scenario 3a: Broadcast Service Failure

**Command Executed:**
```bash
aws ecs update-service \
  --service bidding-system-broadcast-service \
  --desired-count 0 \
  --cluster bidding-system-cluster
```

**What This Simulates:**
- All Broadcast Service tasks are stopped
- WebSocket connections are terminated
- Real-time updates stop being delivered
- API Gateway continues to accept bids (write path unaffected)

**Timeline:**
```
0s ────────────────────────────────────────────────────────── 180s
│                    │                    │
│   BASELINE         │    FAILURE        │   RECOVERY
│   (30s)            │    (60s)          │   (90s)
│                    │                    │
│   Normal ops       │   Service = 0     │   Service restored
│   All services up  │   No WebSocket    │   desired-count = 4
│                    │   connections     │
```

---

### Scenario 3b: Archival Worker Failure

**Command Executed:**
```bash
aws ecs update-service \
  --service bidding-system-archival-worker \
  --desired-count 0 \
  --cluster bidding-system-cluster
```

**What This Simulates:**
- Archival Worker tasks are stopped
- Events stop being persisted to PostgreSQL
- NATS queue messages accumulate (not consumed)
- API Gateway continues to accept bids (write path unaffected)

**Timeline:**
```
0s ────────────────────────────────────────────────────────── 180s
│                    │                    │
│   BASELINE         │    FAILURE        │   RECOVERY
│   (30s)            │    (60s)          │   (90s)
│                    │                    │
│   Normal ops       │   Worker = 0      │   Worker restored
│   Events persisted │   No DB writes   │   desired-count = 1
│                    │   Queue backlog   │
```

---

### Scenario 3c: NATS Failure

**Command Executed:**
```bash
aws ecs update-service \
  --service bidding-system-nats \
  --desired-count 0 \
  --cluster bidding-system-cluster
```

**What This Simulates:**
- NATS server tasks are stopped
- Message queue becomes unavailable
- API Gateway cannot publish events (async, non-blocking)
- Broadcast Service cannot receive events
- API Gateway continues to accept bids (write path unaffected)

**Timeline:**
```
0s ────────────────────────────────────────────────────────── 180s
│                    │                    │
│   BASELINE         │    FAILURE        │   RECOVERY
│   (30s)            │    (60s)          │   (90s)
│                    │                    │
│   Normal ops       │   NATS = 0        │   NATS restored
│   Events published │   No message bus │   desired-count = 1
│                    │   Publish fails   │
```

---

## 🔄 Complete Experiment Flow

### Step-by-Step Execution

```python
# 1. Start Locust load test
locust_proc = run_locust(
    host=args.host,
    users=100,
    duration="180s",
    csv_prefix="exp3a_v2"
)

# 2. Baseline period (30 seconds)
time.sleep(30)  # Normal operations, collect baseline metrics

# 3. Inject failure
update_ecs_service(
    service="bidding-system-broadcast-service",
    desired_count=0  # ← FAILURE INJECTED HERE
)

# 4. Failure window (60 seconds)
time.sleep(60)  # Service is down, measure impact

# 5. Recover service
update_ecs_service(
    service="bidding-system-broadcast-service",
    desired_count=4  # ← SERVICE RESTORED
)

# 6. Wait for Locust to finish
locust_proc.wait()
```

### Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    EXPERIMENT TIMELINE                      │
└─────────────────────────────────────────────────────────────┘

Time:  0s        30s        90s        180s
       │         │          │          │
       ├─────────┼──────────┼──────────┤
       │         │          │          │
       ▼         ▼          ▼          ▼
    ┌─────┐  ┌──────┐  ┌──────┐  ┌──────┐
    │Start│  │Fail  │  │Recover│  │End   │
    │Locust│  │Inject│  │Service│  │Test  │
    └─────┘  └──────┘  └──────┘  └──────┘
       │         │          │          │
       │         │          │          │
       ▼         ▼          ▼          ▼
    Baseline  Failure    Recovery   Analysis
    Metrics   Metrics    Metrics    Metrics
```

---

## 🎯 What Gets Measured

### During Baseline (0-30s)
- Normal RPS, latency, error rate
- All services operational
- Establishes performance baseline

### During Failure (30-90s)
- **Critical Question**: Does write path remain available?
- **Metrics Collected**:
  - `POST /bid` RPS (should remain stable)
  - `POST /bid` latency (should not degrade)
  - `POST /bid` error rate (should stay 0%)
  - Redis state changes (bids should continue)

### During Recovery (90-180s)
- Service restoration behavior
- Performance return to baseline
- Any lingering effects

---

## 🔍 How This Differs from Real Failures

### Simulated Failure (Current Method)

| Aspect | Simulated Failure |
|--------|-------------------|
| **Method** | Clean shutdown via `desired-count=0` |
| **Process** | Graceful task termination |
| **Timing** | Controlled, predictable |
| **State** | Clean shutdown, no data corruption |
| **Recovery** | Immediate restart on command |

### Real-World Failures

| Aspect | Real Failure |
|--------|--------------|
| **Method** | Crash, network partition, hardware failure |
| **Process** | Abrupt termination, possible data loss |
| **Timing** | Unpredictable, random |
| **State** | May leave corrupted state, partial writes |
| **Recovery** | May require manual intervention |

### Limitations of Current Simulation

1. **Clean Shutdown Only**: 
   - Real failures might be abrupt (crashes, OOM kills)
   - Current method = graceful shutdown

2. **No Network Partitions**:
   - Real failures might include network splits
   - Current method = complete service removal

3. **No Cascading Failures**:
   - Real failures might trigger chain reactions
   - Current method = isolated single service

4. **Predictable Timing**:
   - Real failures are random
   - Current method = controlled injection

---

## 🛠️ Alternative Failure Simulation Methods

### Method 1: Current (ECS Scaling) ✅ **USED**

**Pros:**
- ✅ Simple, controlled
- ✅ Reproducible
- ✅ Safe (no data corruption)
- ✅ Easy to automate

**Cons:**
- ❌ Clean shutdown only
- ❌ Doesn't simulate crashes

**Command:**
```bash
aws ecs update-service --service {name} --desired-count 0
```

---

### Method 2: Task Termination (More Realistic)

**Pros:**
- ✅ Simulates abrupt failures
- ✅ More realistic crash behavior

**Cons:**
- ❌ Less controlled
- ❌ Harder to time precisely

**Command:**
```bash
# Get running task ARN
TASK_ARN=$(aws ecs list-tasks --service {name} --query 'taskArns[0]' --output text)

# Force stop task (simulates crash)
aws ecs stop-task --task $TASK_ARN --reason "Chaos testing"
```

---

### Method 3: Network Partition (Advanced)

**Pros:**
- ✅ Simulates network failures
- ✅ Tests partition tolerance

**Cons:**
- ❌ Complex setup (requires security group changes)
- ❌ May affect other services

**Method:**
```bash
# Remove security group rules
aws ec2 revoke-security-group-ingress \
  --group-id {sg-id} \
  --protocol tcp \
  --port 4222
```

---

### Method 4: Resource Exhaustion (Stress Testing)

**Pros:**
- ✅ Simulates resource constraints
- ✅ Tests graceful degradation

**Cons:**
- ❌ Requires container-level changes
- ❌ May affect other services

**Method:**
```bash
# Limit CPU/memory in task definition
# Or use stress-ng inside container
```

---

## 📝 Example: Running Experiment 3a

### Command
```bash
python3 run_experiment3.py \
  --host http://bidding-system-alb-xxx.us-west-2.elb.amazonaws.com \
  --scenario 3a \
  --ecs-cluster bidding-system-cluster \
  --users 100 \
  --spawn-rate 10 \
  --duration 180s \
  --baseline-seconds 30 \
  --failure-seconds 60 \
  --recovery-count 4 \
  --csv-prefix exp3a_v2
```

### What Happens Behind the Scenes

```
[0s]   Starting Locust with 100 users...
[0s]   Load test begins, collecting baseline metrics
[30s]  Baseline period complete
[30s]  Executing: aws ecs update-service \
                  --service bidding-system-broadcast-service \
                  --desired-count 0
[30s]  ECS begins stopping all Broadcast Service tasks
[35s]  All tasks stopped (graceful shutdown)
[35s]  ALB health checks fail → removes from target group
[35s]  WebSocket connections terminated
[35s]  Failure period begins, measuring impact...
[90s]  Failure period complete
[90s]  Executing: aws ecs update-service \
                  --service bidding-system-broadcast-service \
                  --desired-count 4
[90s]  ECS begins starting new Broadcast Service tasks
[95s]  Tasks healthy → ALB adds back to target group
[95s]  Recovery period begins...
[180s] Locust test completes
[180s] Analyzing CSV files for metrics
```

---

## 🎯 Key Insights from Failure Simulation

### What We Learn

1. **Write Path Isolation**: 
   - ✅ Confirms critical path (API Gateway → Redis) is independent
   - ✅ Secondary failures don't affect bid acceptance

2. **Graceful Degradation**:
   - ✅ System continues operating with reduced functionality
   - ✅ No cascading failures observed

3. **Recovery Behavior**:
   - ✅ Services restore cleanly
   - ✅ Performance returns to baseline

### What We Don't Learn

1. **Crash Behavior**: 
   - ❌ Doesn't test abrupt terminations
   - ❌ Doesn't test data corruption scenarios

2. **Network Partitions**:
   - ❌ Doesn't test split-brain scenarios
   - ❌ Doesn't test partial connectivity

3. **Cascading Failures**:
   - ❌ Doesn't test multiple simultaneous failures
   - ❌ Doesn't test resource exhaustion

---

## 🔧 Improving Failure Simulation

### Recommendation 1: Add Task Termination

```python
def kill_random_task(service: str, cluster: str):
    """Kill a random task to simulate crash"""
    tasks = subprocess.run(
        ["aws", "ecs", "list-tasks", 
         "--service", service, 
         "--cluster", cluster],
        capture_output=True, text=True
    ).stdout
    
    task_arn = parse_task_arn(tasks)
    subprocess.run([
        "aws", "ecs", "stop-task",
        "--task", task_arn,
        "--reason", "Chaos testing"
    ])
```

### Recommendation 2: Add Network Partition

```python
def block_service_network(service: str):
    """Block network access to simulate partition"""
    # Revoke security group ingress rules
    # This simulates network partition
    pass
```

### Recommendation 3: Add Cascading Failures

```python
def simulate_cascading_failure():
    """Test multiple failures simultaneously"""
    # Kill NATS
    update_ecs_service("nats", 0)
    time.sleep(10)
    # Kill Archival Worker
    update_ecs_service("archival-worker", 0)
    # Measure combined impact
```

---

## 📊 Summary

### Current Simulation Method

**Technique**: ECS service scaling (`desired-count = 0`)

**What It Simulates**:
- ✅ Complete service unavailability
- ✅ Graceful shutdown behavior
- ✅ Recovery after restoration

**What It Doesn't Simulate**:
- ❌ Abrupt crashes
- ❌ Network partitions
- ❌ Cascading failures
- ❌ Resource exhaustion

### Validation

The current method is **sufficient for Experiment 3's goals**:
- ✅ Validates write path isolation
- ✅ Confirms graceful degradation
- ✅ Tests recovery behavior

For more realistic failure testing, consider adding:
- Task termination (crashes)
- Network partition simulation
- Cascading failure scenarios

---

*Document Created: December 2025*  
*Related Files: `run_experiment3.py`, `EXPERIMENT_3_REPORT.md`*


