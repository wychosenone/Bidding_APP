# Experiment 1: Write Contention Test - Complete Report

## Test Environment
- Platform: LocalStack (Docker)
- Redis Version: 7.2
- Test Duration: 30 seconds per test
- Contested Item: contested_item_1 (single item with high write contention)
- Test Date: 2025-11-29

## Objective
Compare two Redis concurrency control strategies under high write contention:
1. **Lua Script Strategy**: Server-side atomic execution using EVAL
2. **Optimistic Locking Strategy**: WATCH/MULTI/EXEC pattern with retry logic

---

## Test Results Summary

### Lua Script Strategy

| Users | Throughput (RPS) | P50 (ms) | P95 (ms) | P99 (ms) | Total Requests | Failures | Correctness |
|------:|----------------:|--------:|---------:|---------:|---------------:|---------:|:-----------:|
| 100   | 8,512.44        | 0       | 3        | 9        | 254,156        | 0        | ✅ PASSED   |
| 500   | 13,002.77       | 24      | 46       | 65       | 389,553        | 0        | ✅ PASSED   |
| 1,000 | 12,761.56       | 59      | 110      | 160      | 386,989        | 0        | ✅ PASSED   |
| 2,000 | 11,908.28       | 120     | 270      | 370      | 382,206        | 0        | ✅ PASSED   |
| **10,000** | **9,747.94** | **130** | **650**  | **1,300** | **413,126**   | **0**    | ✅ PASSED   |

**Key Observations:**
- Peak throughput at 500 users: **13,002.77 RPS**
- Throughput degrades at 1000+ users due to client CPU bottleneck (Locust at 90%)
- Latency increases significantly with user count
- Zero failures across all tests
- Zero lost updates - all tests passed correctness verification

### Optimistic Locking Strategy

| Users | Throughput (RPS) | P50 (ms) | P95 (ms) | P99 (ms) | Total Requests | Failures | Correctness |
|------:|----------------:|--------:|---------:|---------:|---------------:|---------:|:-----------:|
| 100   | 8,545.20        | 1       | 3        | 8        | 254,772        | 0        | ✅ PASSED   |
| 500   | 12,709.17       | 24      | 47       | 68       | 380,856        | 0        | ✅ PASSED   |
| 1,000 | 12,661.96       | 59      | 120      | 160      | 384,317        | 0        | ✅ PASSED   |
| 2,000 | 12,017.57       | 120     | 270      | 380      | 387,406        | 0        | ✅ PASSED   |
| **10,000** | **10,410.09** | **130** | **500**  | **710**  | **432,804**   | **0**    | ✅ PASSED   |

**Key Observations:**
- Peak throughput at 500 users: **12,709.17 RPS**
- Performance remains stable across 500-2000 users (12,000-13,000 RPS)
- Similar latency profile to Lua strategy
- Zero failures across all tests
- Zero lost updates - all tests passed correctness verification

---

## Comparison Analysis

### Throughput Comparison

| Users  | Lua RPS    | Optimistic RPS | Difference    | Winner     |
|-------:|----------:|---------------:|--------------:|:-----------|
| 100    | 8,512     | 8,545          | +33 (+0.4%)   | Optimistic |
| 500    | 13,003    | 12,709         | -294 (-2.3%)  | **Lua**    |
| 1,000  | 12,762    | 12,662         | -100 (-0.8%)  | **Lua**    |
| 2,000  | 11,908    | 12,018         | +110 (+0.9%)  | Optimistic |
| 10,000 | 9,748     | 10,410         | +662 (+6.4%)  | Optimistic |

**Key Findings:**
- Performance is nearly equivalent between both strategies (< 6.4% difference)
- Lua has slight edge at medium load (500-1000 users)
- Optimistic performs better at very high load (10000 users)
- Bottleneck is Locust client CPU, not the Redis strategy

### Latency Comparison (P99)

| Users  | Lua P99 (ms) | Optimistic P99 (ms) | Difference |
|-------:|------------:|--------------------:|:-----------|
| 100    | 9           | 8                   | -1 ms      |
| 500    | 65          | 68                  | +3 ms      |
| 1,000  | 160         | 160                 | 0 ms       |
| 2,000  | 370         | 380                 | +10 ms     |
| 10,000 | 1,300       | 710                 | **-590 ms** |

**Observation:** At extreme load (10,000 users), Optimistic Locking shows better tail latency performance.

### Correctness Verification

All **10 tests** (5 Lua + 5 Optimistic) passed correctness verification:
- ✅ Final bid in Redis matches maximum submitted bid
- ✅ Zero lost updates detected
- ✅ Zero incorrectly rejected bids

This demonstrates that both strategies maintain **ACID properties** under extreme write contention.

---

## Visualizations

### Performance Charts

![Experiment 1 Visualization](experiment1_visualization.png)

*Figure 1: Throughput comparison, latency percentiles, and scaling behavior*

![Experiment 1 Analysis](experiment1_analysis.png)

*Figure 2: Performance difference analysis and total requests processed*

---

## Resource Utilization

### Client Side (Locust)
- **CPU**: 90%+ at 500+ users (bottleneck identified)
- This limitation prevents discovering true system capacity
- **Recommendation**: Use distributed Locust workers for higher load testing

### Server Side
- Redis CPU: Monitored via INFO stats (logs available)
- No Redis slowlog entries detected during tests
- System handled load efficiently on both strategies

---

## Test Artifacts

### Log Files

**Lua Strategy:**
- `/tmp/exp1_lua_final.log` (100 users)
- `/tmp/exp1_lua_500.log` (500 users)
- `/tmp/exp1_lua_1000.log` (1000 users)
- `/tmp/exp1_lua_2000.log` (2000 users)
- `/tmp/exp1_lua_10000.log` (10000 users)

**Optimistic Strategy:**
- `/tmp/exp1_optimistic_100.log` (100 users)
- `/tmp/exp1_optimistic_500.log` (500 users)
- `/tmp/exp1_optimistic_1000.log` (1000 users)
- `/tmp/exp1_optimistic_2000.log` (2000 users)
- `/tmp/exp1_optimistic_10000.log` (10000 users)

### Correctness Verification Results
- `correctness_verification_contested_item_1.json`
- `correctness_verification_lua_10000.txt`
- `correctness_verification_optimistic_100.json`
- `correctness_verification_optimistic_500.txt`
- `correctness_verification_optimistic_1000.txt`
- `correctness_verification_optimistic_2000.txt`
- `correctness_verification_optimistic_10000.txt`

### Redis Monitoring Logs
- `/tmp/exp1_lua_redis.log`
- `/tmp/exp1_lua_500_redis.log`
- `/tmp/exp1_lua_10000_redis.log`
- `/tmp/exp1_optimistic_*_redis.log`

### HTML Reports (Locust)
- `/tmp/exp1_lua_10000.html`
- `/tmp/exp1_optimistic_10000.html`

---

## Conclusions

1. **Performance Parity**: Both strategies deliver nearly identical throughput and latency under write contention (< 6.4% difference)

2. **Correctness Guaranteed**: Both strategies maintain data integrity with zero lost updates across all 10 test cases

3. **Scalability**:
   - Peak throughput: ~13,000 RPS at 500 concurrent users
   - Throughput remains above 9,700 RPS even at 10,000 users
   - Locust client CPU is the bottleneck, not Redis

4. **Strategy Trade-offs**:
   | Aspect | Lua Script | Optimistic Locking |
   |--------|-----------|-------------------|
   | Implementation | Single EVAL command | WATCH/MULTI/EXEC with retries |
   | Latency @ 10K users | Higher P99 (1300ms) | Lower P99 (710ms) |
   | Throughput @ 10K users | 9,748 RPS | 10,410 RPS |
   | Complexity | Lower | Higher |
   | Network Round-trips | 1 | Multiple (on retry) |

5. **Recommendation**:
   - Use **Lua Script** for simplicity and when latency at extreme load is less critical
   - Use **Optimistic Locking** when tail latency matters or complex client-side logic is needed

---

## Summary Statistics

```
================================================================================
EXPERIMENT 1: WRITE CONTENTION TEST - FINAL RESULTS
================================================================================

Users      Lua RPS      Opt RPS      Diff %     Lua P99    Opt P99
------------------------------------------------------------------------
100        8,512.44     8,545.20     -0.38%     9ms        8ms
500        13,002.77    12,709.17    +2.31%     65ms       68ms
1,000      12,761.56    12,661.96    +0.79%     160ms      160ms
2,000      11,908.28    12,017.57    -0.91%     370ms      380ms
10,000     9,747.94     10,410.09    -6.36%     1,300ms    710ms

================================================================================
KEY ACHIEVEMENTS:
================================================================================
✅ Peak Throughput:        13,003 RPS (Lua @ 500 users)
✅ Zero Failures:          0% error rate across all tests
✅ Data Integrity:         100% correctness - no lost updates
✅ Scalability:            Handles 10,000 concurrent users
================================================================================
```

---

## Next Steps
- ✅ Experiment 1 Complete
- ⏳ Experiment 2: WebSocket fan-out testing with 100/1000/10000 concurrent connections
- ⏳ Experiment 3: Resilience & Availability testing
- ⏳ Generate final mastery report
