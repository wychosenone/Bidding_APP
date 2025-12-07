# Experiment 1: Write Contention - Lua vs Optimistic Locking

## Test Configuration
- **Infrastructure**: AWS us-west-2, ECS Fargate
- **Load**: 100 concurrent users, 30 second test duration
- **Target**: Single contested item (all users bidding on same item)
- **Ramp-up**: 20 users/second
- **Test Date**: 2025-11-09 (After Redis pool + broadcast fixes)

## Results Summary

### Lua Atomic Strategy
- **Total Bids**: 52,128
- **Throughput**: 1,746.03 bids/sec
- **Success Rate**: 100% (0 failures)
- **Retry Count**: **1 retry for ALL bids** (atomic execution)
- **Latency**:
  - Median: 22ms
  - Average: 22ms
  - 95th percentile: 29ms
  - 99th percentile: 40ms
  - Maximum: 148ms

### Optimistic Locking Strategy
- **Total Bids**: 48,664
- **Throughput**: 1,630.86 bids/sec
- **Success Rate**: 100% (0 failures)
- **Retry Count**: **1 retry for ALL bids** (no contention observed)
- **Latency**:
  - Median: 24ms
  - Average: 26ms
  - 95th percentile: 41ms
  - 99th percentile: 100ms
  - Maximum: 282ms

## Performance Comparison

| Metric | Lua Strategy | Optimistic Strategy | Lua Advantage |
|--------|--------------|---------------------|---------------|
| Throughput | 1,746 req/s | 1,631 req/s | **+7.1%** |
| Median Latency | 22ms | 24ms | **-8.3%** |
| Average Latency | 22ms | 26ms | **-15.4%** |
| P95 Latency | 29ms | 41ms | **-29.3%** |
| P99 Latency | 40ms | 100ms | **-60.0%** |
| Max Latency | 148ms | 282ms | **-47.5%** |
| Retry Count | 1 | 1 | Equal |

## Key Findings

### 1. Lua Strategy Consistently Outperforms Optimistic Locking
- **7% higher throughput** (1,746 vs 1,631 bids/sec)
- **Lower and more consistent latency** across all percentiles
- **P99 latency 2.5x better** (40ms vs 100ms)
- Both strategies achieved 100% success rate

### 2. No Retry Contention Observed
Both strategies showed **retry_count=1** for all successful bids, meaning:
- **Lua**: Atomic execution guarantees no retries needed (expected behavior)
- **Optimistic**: No WATCH/MULTI/EXEC transaction failures occurred

**Explanation for lack of optimistic retries:**
- With increased Redis pool size (PoolSize=100), connections are available immediately
- Network latency between ECS tasks and ElastiCache provides natural spacing
- Redis atomic operations complete faster than concurrent request intervals
- 100 concurrent users may not create sufficient contention on a single item

### 3. Latency Characteristics
- **Lua** shows consistently low latency (P50=22ms, P95=29ms, P99=40ms)
- **Optimistic** shows higher tail latency (P99=100ms, max=282ms)
- Lua's server-side execution eliminates multiple network round-trips
- Optimistic locking requires WATCH → GET → MULTI → SET → EXEC sequence

### 4. System Improvements Since Previous Test
Compared to earlier deployment (before fixes):
- **3.2x higher throughput** (1,746 vs 546 bids/sec for Lua)
- **Similar latency profile** maintained
- Redis connection pool optimization (PoolSize=100) prevents bottlenecks
- Broadcast channel buffer fix (10K) doesn't affect write path

## Architectural Implications

### Why Lua Wins
1. **Single Network Round-Trip**: Script executes atomically on Redis server
2. **No Lock Contention**: No WATCH retries needed
3. **Server-Side Execution**: Eliminates client-server latency for conditional logic
4. **Predictable Performance**: Consistent latency distribution

### When Optimistic Might Be Preferred
- Non-Redis datastores (WATCH is Redis-specific)
- Complex multi-key transactions (Lua has limitations)
- Need for client-side validation before commit
- Lower read contention scenarios

## Recommendation
**Use Lua atomic scripts for production bidding system** due to:
- Superior throughput (+7%)
- Significantly better P95/P99 latency (-29% to -60%)
- Predictable single-retry behavior
- No contention-based failures
- Simpler code (no retry logic needed)

## Test Infrastructure Details
- **AWS Region**: us-west-2
- **ECS Cluster**: bidding-system-cluster
- **API Gateway**: 2x Fargate tasks (512 CPU, 1024 MB)
- **Redis**: ElastiCache cache.t3.micro (PoolSize=100, MinIdleConns=10)
- **Load Generator**: Locust 2.15.1 (100 concurrent users)
- **ALB**: bidding-system-alb-137918056.us-west-2.elb.amazonaws.com
- **Test Duration**: 30 seconds per strategy
