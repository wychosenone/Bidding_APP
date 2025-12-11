# Experiment 2 Latency Discrepancy Analysis

## Problem Statement

If both original and new Experiment 2 tests were run from local machines (not EC2 in same VPC), what explains the significant latency differences?

### Latency Comparison

| Connections | Original P99 | New P99 | Difference |
|-------------|--------------|---------|------------|
| 100 | 17.81ms | 396.48ms | **22× slower** |
| 1,000 | 55.55ms | 188.59ms | **3.4× slower** |
| 10,000 | 1073ms | 4405ms | **4× slower** |

---

## Potential Root Causes (If Both Run from Local Machines)

### 1. **Different ALB Deployments** ⚠️ **MOST LIKELY**

**Evidence:**
- Original: `bidding-system-alb-137918056.us-west-2.elb.amazonaws.com`
- New: `bidding-system-alb-1700264738.us-west-2.elb.amazonaws.com`

**Different ALB = Different Infrastructure Configuration**

| Aspect | Impact on Latency |
|--------|------------------|
| **ALB Type** | Internal vs Internet-facing (but both appear public) |
| **Target Group Health** | Unhealthy targets add latency |
| **Connection Stickiness** | Different stickiness config affects routing |
| **ALB Capacity** | Different instance types/capacity |
| **Cross-Zone Load Balancing** | Enabled vs disabled affects routing |
| **Idle Timeout** | Different WebSocket timeout settings |

**Hypothesis**: Original ALB may have been configured differently (e.g., internal ALB, different routing rules, or healthier targets)

---

### 2. **Different ECS Task Configurations**

**Original (EXPERIMENT_2_RESULTS.md):**
- Broadcast Service: 2× tasks (512 CPU, 1024 MB)
- Test Date: 2025-11-09

**New (experiment2.record.md):**
- Broadcast Service: 2× tasks (512 CPU, 1024 MB) - **Same**
- But: Different deployment = potentially different task placement

**Possible Differences:**
- **Task Placement**: Different availability zones (AZ latency)
- **Network Performance**: Different ENI (Elastic Network Interface) performance
- **Resource Contention**: Other workloads on same ECS cluster
- **Warm vs Cold Start**: Original tests may have been on "warm" tasks

---

### 3. **Different Measurement Methodology**

**Original Tests:**
- Used `server_timestamp` from API Gateway
- Latency = `client_receive_time - server_timestamp`
- Single test client (no clock drift)

**New Tests:**
- First bid shows high latency (384ms) - **connection warm-up?**
- Subsequent bids: 48-66ms (more consistent)
- May have clock synchronization issues

**Key Observation**: First bid latency (384ms) suggests:
- Connection establishment overhead
- ALB connection stickiness negotiation
- WebSocket upgrade handshake delay

---

### 4. **Geographic/Network Location Differences**

Even if both from "local machines", differences could be:

| Factor | Impact |
|--------|--------|
| **Geographic Location** | Different cities → different routing paths |
| **ISP** | Different ISPs → different peering agreements |
| **Time of Day** | Network congestion varies |
| **AWS Edge Location** | Different CloudFront/edge routing |

**Example:**
- Original: Tested from location A → AWS us-west-2 (optimal routing)
- New: Tested from location B → AWS us-west-2 (suboptimal routing)

---

### 5. **System Load & Resource Contention**

**Original Tests:**
- May have been run during low-traffic periods
- Fresh deployment (no accumulated connections)
- Clean system state

**New Tests:**
- May have been run during higher-traffic periods
- Existing connections from previous tests
- System state accumulation (Redis cache, connection pools)

**Evidence**: First bid in new test shows 384ms (warm-up), subsequent bids ~50ms

---

### 6. **ALB Target Health & Routing**

**Original ALB (`137918056`):**
- May have had healthier targets
- Better target distribution
- Optimal routing to ECS tasks

**New ALB (`1700264738`):**
- Targets may be unhealthy or slow to respond
- Suboptimal routing
- Connection stickiness issues

**How to Check:**
```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn> \
  --region us-west-2
```

---

### 7. **Code/Configuration Differences**

**Possible Code Changes:**
- Different broadcast implementation
- Different NATS configuration
- Different WebSocket buffer sizes
- Different connection handling logic

**Evidence**: Original tests mention "After Redis pool + broadcast channel buffer fixes" - suggests code changes between tests

---

### 8. **Test Client Performance**

**Original:**
- May have been run on more powerful machine
- Less CPU/memory contention
- Faster network interface

**New:**
- May have been run on less powerful machine
- CPU/memory contention (10K connections)
- Network interface limitations

**Evidence**: New test shows connection timeouts at 10K (30 failed connections)

---

## Most Likely Explanations (Ranked)

### 1. **Different ALB Configuration** (High Confidence)

**Evidence:**
- Different ALB DNS names = different deployments
- Original ALB may have been internal-facing or differently configured
- ALB routing rules may differ

**Impact**: Could explain 20-50ms difference per request

### 2. **First Bid Warm-Up Overhead** (High Confidence)

**Evidence:**
- New test: First bid = 384ms, subsequent = 48-66ms
- Original test: Consistent ~18ms (may have warmed up before measurement)

**Impact**: Could explain 300ms+ difference if original didn't measure first bid

### 3. **Geographic/Network Location** (Medium Confidence)

**Evidence:**
- Different test locations → different routing paths
- ISP differences → different peering

**Impact**: Could explain 30-50ms difference

### 4. **System State & Load** (Medium Confidence)

**Evidence:**
- Original: Fresh deployment
- New: Accumulated state, previous test connections

**Impact**: Could explain 10-20ms difference

### 5. **Measurement Methodology** (Low Confidence)

**Evidence:**
- Original may have excluded first bid (warm-up)
- Different timing measurement approaches

**Impact**: Could explain discrepancies if methodology differed

---

## How to Verify Root Cause

### 1. Check ALB Configuration

```bash
# Compare ALB configurations
aws elbv2 describe-load-balancers \
  --load-balancer-arns <original-alb-arn> <new-alb-arn> \
  --region us-west-2

# Check target group health
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn> \
  --region us-west-2
```

### 2. Check ECS Task Placement

```bash
# Check task distribution across AZs
aws ecs describe-tasks \
  --cluster bidding-system-cluster \
  --tasks <task-ids> \
  --region us-west-2 \
  --query 'tasks[*].{AZ:availabilityZone,CPU:cpu,Memory:memory}'
```

### 3. Compare Network Paths

```bash
# From original test location
traceroute bidding-system-alb-137918056.us-west-2.elb.amazonaws.com

# From new test location
traceroute bidding-system-alb-1700264738.us-west-2.elb.amazonaws.com
```

### 4. Check Test Methodology

- Did original tests exclude first bid (warm-up)?
- Were measurements taken at different points in the test?
- Was `--use-client-time` used in original tests?

---

## Conclusion

**Most Likely Root Cause**: **Different ALB deployments** + **First bid warm-up overhead**

The 22× difference at 100 connections (17.81ms vs 396.48ms) is too large to be explained by network alone. The fact that:
1. Different ALB DNS names (different deployments)
2. First bid shows 384ms (warm-up), subsequent ~50ms
3. Original shows consistent ~18ms (may have excluded warm-up)

Suggests **measurement methodology differences** combined with **infrastructure differences**.

**Recommendation**: 
- Re-run tests excluding first bid (warm-up period)
- Use same ALB deployment for comparison
- Document exact measurement methodology
- Use `--use-client-time` flag for consistent measurements







