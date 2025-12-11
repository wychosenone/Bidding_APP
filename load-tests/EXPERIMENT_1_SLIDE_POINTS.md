# Experiment 1: Write Contention Test - Slide Key Points

## 🎯 Main Purpose

**Evaluate Redis concurrency control strategies under extreme write contention**

- **Scenario**: Thousands of users simultaneously bidding on a single popular item
- **Question**: Which strategy provides better throughput and latency?
- **Strategies Compared**: 
  - Lua Script (server-side atomic execution)
  - Optimistic Locking (WATCH/MULTI/EXEC with client-side retries)

---

## 🔑 Key Findings

### 1. **Lua Script Outperforms Optimistic Locking by 36-66%**

| Load Level | Lua RPS | Optimistic RPS | Advantage |
|------------|---------|----------------|-----------|
| 100 users | 3,899 | 3,624 | **+8%** |
| 500 users | 12,180 | 8,961 | **+36%** |
| 1,000 users | 14,466 | 8,733 | **+66%** |
| 10,000 users | 13,995 | 8,662 | **+62%** |

### 2. **P99 Latency: Lua is 5-9× Better**

| Load Level | Lua P99 | Optimistic P99 | Ratio |
|------------|---------|---------------|-------|
| 100 users | 22ms | 110ms | **5× better** |
| 1,000 users | 70ms | 430ms | **6× better** |
| 2,000 users | 120ms | 1,100ms | **9× better** |

### 3. **100% Data Integrity** (Both Strategies)
- Zero lost updates across 2.3M+ requests
- No race conditions detected
- Both strategies maintain correctness

---

## 💡 Justifications & Why

### Why Lua Script Wins: Single Round-Trip Architecture

```
Lua Script:
Client → Redis: EVALSHA (1 round-trip)
Redis: GET → Compare → SET (atomic, ~0.01ms)
Redis → Client: Result
Total: 1 network round-trip
```

**Benefits:**
- ✅ Single network round-trip per request
- ✅ All logic executes atomically on Redis server
- ✅ No retries needed (guaranteed success)
- ✅ Predictable, consistent latency

### Why Optimistic Locking Struggles: Multi-Round-Trip + Retries

```
Optimistic Locking:
Client → Redis: WATCH + GET (round-trip 1)
Client: Compare locally
Client → Redis: MULTI + SET + EXEC (round-trip 2)
  - If WATCH key changed: FAIL → Retry (back to step 1)
  - If unchanged: Success
Total: 2+ round-trips (often 4-6 attempts under contention)
```

**Drawbacks:**
- ❌ Minimum 2 round-trips per successful request
- ❌ Under high contention: 99.99% of transactions fail on first attempt
- ❌ Average 3-6 retry attempts per success at 10K users
- ❌ Each retry adds ~20ms latency

### Quantified Impact

**At 10,000 concurrent users:**
- **Lua**: 1 Redis operation per successful bid
- **Optimistic**: ~8-12 Redis operations per successful bid (4-6 retries × 2 ops each)

**Result**: Optimistic achieves only ~62% of Lua's throughput (8,662 vs 13,995 RPS)

---

## 📊 Performance Gap Widens with Load

| Metric | Low Load (100) | High Load (1,000+) |
|--------|----------------|-------------------|
| Throughput Advantage | +8% | **+60-66%** |
| P99 Latency Advantage | 5× better | **6-9× better** |

**Key Insight**: The performance gap increases dramatically as contention grows.

---

## ✅ Conclusions

1. **Lua Script is superior for high-contention scenarios**
   - 36-66% higher throughput
   - 5-9× better tail latency
   - Predictable single-retry behavior

2. **Optimistic Locking's retry mechanism becomes a liability**
   - Retries consume Redis resources and network bandwidth
   - Creates negative feedback loop under high load

3. **Both strategies maintain correctness**
   - Zero data integrity issues
   - Redis atomicity guarantees hold under extreme load

4. **Production Recommendation**: Use Lua Script for bidding system
   - Superior performance characteristics
   - Simpler code (no retry logic needed)
   - Better user experience (lower latency)

---

## 🏗️ Test Infrastructure

- **Platform**: AWS ECS Fargate (us-west-2)
- **API Gateway**: 4× tasks (512 CPU, 1024MB RAM)
- **Redis**: ElastiCache cache.t3.micro
- **Load**: 100 to 10,000 concurrent users
- **Total Requests**: 2.3M+ across all tests

---

## 📈 Visual Summary

```
Performance Comparison (1,000 users):
┌─────────────────────────────────────────┐
│ Lua Script:     14,466 RPS, P99: 70ms  │ ✅ Winner
│ Optimistic:      8,733 RPS, P99: 430ms │
│ Advantage:      +66% throughput        │
│                 -84% P99 latency        │
└─────────────────────────────────────────┘
```







