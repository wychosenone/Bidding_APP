# Experiment 3: Resilience & Availability Under Component Failures - Slide Key Points

## 🎯 Main Purpose

**Validate write path availability during secondary component failures**

- **Research Question**: Does the bidding system maintain write path availability when secondary components fail?
- **Hypothesis**: Critical path (API Gateway → Redis) is fully decoupled from secondary paths
- **Three Failure Scenarios**:
  - **3a**: Broadcast Service failure (WebSocket/real-time path)
  - **3b**: Archival Worker failure (persistence path)
  - **3c**: NATS failure (message queue path)

---

## 🔑 Key Findings

### 1. **100% Write Path Availability** ✅

| Experiment | Component Failed | HTTP Error Rate | Latency Impact | Redis Writes |
|------------|------------------|-----------------|----------------|--------------|
| **3a** | Broadcast Service | **0%** | None | ✅ Continued |
| **3b** | Archival Worker | **0%** | None | ✅ Continued |
| **3c** | NATS | **0%** | +16ms P99 | ✅ Continued |

**Critical Achievement**: Zero HTTP errors during all failure scenarios

### 2. **Consistent Latency Performance**

| Metric | Baseline | During Failure | Change |
|--------|----------|----------------|--------|
| **P50 Latency** | 19ms | 19ms | **0ms** |
| **P99 Latency** | 27-50ms | 28-66ms | **+0-16ms** |
| **RPS** | 13.2-13.5/s | 13.2-13.5/s | **Stable** |

**Key Insight**: Write latency remains stable—only NATS failure caused minor P99 increase (+16ms)

### 3. **Uninterrupted Redis Writes**

**Cumulative Bid Price Increase Across All Experiments:**

```
Start:     $500/item
After 3a:  $1,800/item  (+$1,300 average)
After 3b:  $3,100/item  (+$1,300 average)
After 3c:  $4,400/item  (+$1,300 average)
```

**Finding**: Consistent ~$1,250-1,300 increase per experiment proves **sustained write throughput** throughout all failures

---

## 💡 Justifications & Why

### Why Zero HTTP Errors?

**Fire-and-Forget Architecture:**

```go
// Critical path: Redis write happens FIRST
redis.Eval(luaScript) → Bid committed ✅

// Secondary paths: Async, non-blocking
go func() {
    nats.Publish(...)  // Best effort, doesn't block
    // If fails: Only logs warning, NO error to client
}()
```

**Architectural Separation:**

```
┌─────────────────────────────────────────┐
│  CRITICAL PATH (validated)              │
│  Client → API Gateway → Redis → 200 OK │
│                                         │
│  ✅ 0% error rate                       │
│  ✅ 19ms P50 latency                    │
│  ✅ 13 bids/second                      │
└─────────────────────────────────────────┘
              │
              │ (async, fire-and-forget)
              ▼
┌─────────────────────────────────────────┐
│  SECONDARY PATHS (can fail gracefully) │
│  • Broadcast Service → WebSocket       │
│  • Archival Worker → PostgreSQL       │
│  • NATS → Message Queue                │
└─────────────────────────────────────────┘
```

**Key Design Principle**: Bid is committed to Redis **before** async operations. HTTP response returns immediately after Redis confirms write.

### Why Minimal Latency Impact?

**3a & 3b (Broadcast/Archival Failure):**
- Zero latency impact
- These services are **consumers only** (don't affect write path)
- API Gateway doesn't wait for them

**3c (NATS Failure):**
- Minor P99 increase (+16ms)
- Reason: Async goroutine timeout handling
- Impact: Negligible (66ms vs 50ms baseline)

### Why Consistent Write Throughput?

**Redis State Verification:**
- Before/after each experiment: Verified `current_bid` values
- Consistent ~$1,300 increase per 60-second failure window
- Proves: Bids were **actually written**, not just acknowledged

---

## 🎓 Why This Matters

### Architectural Validation

**Hypothesis Confirmed**: The decoupled design successfully isolates critical write path from secondary services.

**Production Implications:**
- ✅ **High Availability**: Write path remains available even if real-time features fail
- ✅ **Graceful Degradation**: Users can still bid during partial outages
- ✅ **Simplified Operations**: No need to coordinate shutdowns across services

### Tradeoffs Accepted

| Tradeoff | Evidence | Conclusion |
|----------|----------|------------|
| **Availability vs. Durability** | Events during NATS outage lost (not persisted) | ✅ Acceptable—critical data (final bid) in Redis |
| **Latency vs. Consistency** | P99 +16ms during NATS failure | ✅ Minor impact—async timeout overhead |
| **Simplicity vs. Reliability** | Fire-and-forget (no retry logic) | ✅ Simpler code, but events can be silently dropped |

---

## 📊 Visual Summary

### Performance During Failures

```
HTTP Error Rate:  0% ──────────────────────────────── ✅
P50 Latency:      19ms ────────────────────────────── ✅
P99 Latency:      27-66ms ──────────────────────────── ✅
RPS:              13.2-13.5/s ──────────────────────── ✅
Redis Writes:     Continued ────────────────────────── ✅
```

### Cumulative Bid Price Growth

```
$5,000 ┤
       │
$4,000 ┤                          ████████ (After 3c)
       │          ████████████████ (After 3b)
$3,000 ┤  ████████ (After 3a)
       │
$2,000 ┤
       │
$1,000 ┤
       │
  $500 ┼── (Start)
       └──────────────────────────────────────────────
            Start    After 3a    After 3b    After 3c
```

---

## ✅ Conclusion

### Key Takeaways

1. **Write path isolation is complete**: 0% HTTP error rate during all component failures
2. **Latency remains stable**: P50 constant at 19ms, minimal P99 impact (+16ms max)
3. **Redis writes unaffected**: Consistent throughput (~$1,300/item per experiment)
4. **Architecture validated**: Decoupled design enables graceful degradation

### Production Recommendation

**Deploy with confidence**: The system demonstrates excellent fault isolation. The write path maintains **100% availability** during failures of any secondary component.

**Future Enhancements:**
- Implement dead-letter queue for NATS events
- Add circuit breaker to reduce P99 latency impact
- Monitor secondary paths (alert on failures)

---

## 📋 Test Configuration Summary

| Component | Configuration |
|-----------|---------------|
| **Test Duration** | 180 seconds (30s baseline + 60s failure + 90s recovery) |
| **Load** | 100 concurrent users, 13-14 bids/second |
| **Failure Method** | ECS service scaled to 0 instances |
| **Metrics** | HTTP error rate, latency (P50/P99), Redis state verification |

---

*Test Date: December 6, 2025*  
*Infrastructure: AWS ECS Fargate (us-west-2)*  
*Test Script: `load-tests/run_experiment3.py`*







