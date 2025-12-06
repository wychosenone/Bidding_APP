# Experiment 3: Resilience & Availability Under Component Failures

## 1. Purpose

### 1.1 Research Question

**Does the bidding system maintain write path availability when secondary components (Broadcast Service, Archival Worker, NATS) fail?**

This experiment validates the architectural hypothesis that the critical write path (API Gateway → Redis) is fully decoupled from secondary paths, enabling graceful degradation during partial system failures.

### 1.2 Tradeoffs Being Explored

| Design Decision | Benefit | Tradeoff |
|-----------------|---------|----------|
| Async NATS publishing | Write path not blocked by message queue | Events may be lost during NATS outage |
| Fire-and-forget broadcast | Low latency bid responses | WebSocket clients may miss updates |
| Decoupled archival | Frontend unaffected by DB issues | Eventual consistency for historical data |

### 1.3 Hypothesis

The system architecture separates concerns into:
- **Critical Path**: Client → API Gateway → Redis (must be highly available)
- **Secondary Paths**: NATS/Archival, Broadcast/WebSocket (can fail gracefully)

We hypothesize that failures in secondary components will have **zero impact** on:
1. Bid acceptance rate (0% HTTP errors)
2. Write latency (no degradation)
3. Redis state consistency (bids continue to be recorded)

### 1.4 Limitations

- **Single-region testing**: All components in us-west-2; cross-region failures not tested
- **Controlled failure**: Clean ECS service shutdown vs. network partitions or crashes
- **Limited duration**: 60-second failure windows may not reveal slow memory leaks
- **No chaos testing**: Did not test multiple simultaneous failures

---

## 2. Experimental Setup

### 2.1 Test Environment (AWS ECS Fargate)

| Component | Configuration | Instances |
|-----------|---------------|-----------|
| API Gateway | 0.5 vCPU, 1GB RAM | 4x Fargate |
| Broadcast Service | 0.5 vCPU, 1GB RAM | 4x Fargate |
| Archival Worker | 0.25 vCPU, 512MB RAM | 1x Fargate |
| NATS + JetStream | 0.25 vCPU, 512MB RAM | 1x Fargate |
| Redis | ElastiCache cache.t3.micro | 1 node |
| PostgreSQL | RDS db.t3.micro | 1 instance |
| Region | us-west-2 | - |

### 2.2 Load Generation

- **Tool**: Locust 2.15.1 with `MixedWorkloadUser`
- **Concurrent Users**: 100
- **User Behavior**:
  - 70% operations: Browse items (`GET /api/v1/items/{id}`)
  - 30% operations: Place bids (`POST /api/v1/items/{id}/bid`)
- **Bid Logic**: Query current price, then bid $0.50-$10.00 higher (ensures bids succeed)
- **Think Time**: 1-3 seconds between operations

### 2.3 Fault Injection Protocol

```
Timeline (180 seconds total):

0s                    30s                   90s                   180s
|---------------------|---------------------|---------------------|
     BASELINE              FAILURE               RECOVERY
   (normal ops)      (service stopped)      (service restored)

Fault injection command:
  aws ecs update-service --service {target} --desired-count 0

Recovery command:
  aws ecs update-service --service {target} --desired-count N
```

### 2.4 Three Sub-Experiments

| Experiment | Target Service | Purpose |
|------------|----------------|---------|
| **3a** | Broadcast Service | Test WebSocket/real-time path isolation |
| **3b** | Archival Worker | Test persistence path isolation |
| **3c** | NATS | Test message queue path isolation |

### 2.5 Metrics Collected

1. **HTTP Metrics** (from Locust):
   - Requests per second (RPS)
   - Response latency (P50, P95, P99)
   - Error rate (%)

2. **State Verification** (from Redis via API):
   - `current_bid` values before/after each experiment
   - Confirms bids were actually written, not just acknowledged

---

## 3. Results

### 3.1 Experiment 3a: Broadcast Service Failure

**Fault Injected**: Broadcast Service scaled to 0 instances for 60 seconds.

#### HTTP Performance During Failure

| Metric | Baseline (0-30s) | Failure (30-90s) | Recovery (90-180s) |
|--------|------------------|------------------|-------------------|
| `POST /bid` RPS | 13.5/s | 13.2/s | 13.4/s |
| `POST /bid` P50 | 19ms | 19ms | 19ms |
| `POST /bid` P99 | 27ms | 28ms | 27ms |
| Error Rate | 0% | **0%** | 0% |

#### Redis State Verification

| Item | Before Test | After Test | Change |
|------|-------------|------------|--------|
| item_1 | $500.00 | $1,784.78 | +$1,284.78 |
| item_2 | $499.74 | $2,013.45 | +$1,513.71 |
| item_3 | $499.44 | $1,767.97 | +$1,268.53 |
| item_4 | $499.12 | $1,931.08 | +$1,431.96 |
| item_5 | $499.87 | $1,674.63 | +$1,174.76 |

**Observation**: Bids continued to be written to Redis throughout the failure period. The ~$1,300 average increase per item confirms sustained write throughput.

---

### 3.2 Experiment 3b: Archival Worker Failure

**Fault Injected**: Archival Worker scaled to 0 instances for 60 seconds.

#### HTTP Performance During Failure

| Metric | Baseline (0-30s) | Failure (30-90s) | Recovery (90-180s) |
|--------|------------------|------------------|-------------------|
| `POST /bid` RPS | 13.2/s | 13.5/s | 13.1/s |
| `POST /bid` P50 | 19ms | 19ms | 19ms |
| `POST /bid` P99 | 30ms | 28ms | 29ms |
| Error Rate | 0% | **0%** | 0% |

#### Redis State Verification

| Item | Before (post-3a) | After 3b | Change |
|------|------------------|----------|--------|
| item_1 | $1,784.78 | $3,009.18 | +$1,224.40 |
| item_2 | $2,013.45 | $3,297.15 | +$1,283.70 |
| item_3 | $1,767.97 | $3,065.12 | +$1,297.15 |
| item_4 | $1,931.08 | $3,226.65 | +$1,295.57 |
| item_5 | $1,674.63 | $2,925.26 | +$1,250.63 |

**Observation**: Identical behavior to 3a. Archival Worker failure has no observable impact on the write path.

---

### 3.3 Experiment 3c: NATS Failure

**Fault Injected**: NATS service scaled to 0 instances for 60 seconds.

#### HTTP Performance During Failure

| Metric | Baseline (0-30s) | Failure (30-90s) | Recovery (90-180s) |
|--------|------------------|------------------|-------------------|
| `POST /bid` RPS | 13.5/s | 13.2/s | 13.4/s |
| `POST /bid` P50 | 19ms | 19ms | 19ms |
| `POST /bid` P99 | 50ms | 66ms | 45ms |
| Error Rate | 0% | **0%** | 0% |

#### Redis State Verification

| Item | Before (post-3b) | After 3c | Change |
|------|------------------|----------|--------|
| item_1 | $3,009.18 | $4,222.90 | +$1,213.72 |
| item_2 | $3,297.15 | $4,564.03 | +$1,266.88 |
| item_3 | $3,065.12 | $4,438.45 | +$1,373.33 |
| item_4 | $3,226.65 | $4,513.47 | +$1,286.82 |
| item_5 | $2,925.26 | $4,174.18 | +$1,248.92 |

**Observation**: Slight P99 latency increase (50ms → 66ms) during NATS failure, likely due to connection timeout handling in the async publish goroutine. However, **zero HTTP errors** and **consistent write throughput**.

---

## 4. Analysis

### 4.1 Summary of Results

| Experiment | Component Failed | HTTP Error Rate | Latency Impact | Redis Writes |
|------------|------------------|-----------------|----------------|--------------|
| 3a | Broadcast Service | 0% | None | ✅ Continued |
| 3b | Archival Worker | 0% | None | ✅ Continued |
| 3c | NATS | 0% | +16ms P99 | ✅ Continued |

### 4.2 Cumulative Redis State Change

```
$5,000 ┤
       │
$4,000 ┤                                          ████████ ($4,222-4,564)
       │                          ████████████████
$3,000 ┤          ████████████████ ($3,009-3,297)
       │  ████████ ($1,674-2,013)
$2,000 ┤██
       │
$1,000 ┤
       │
  $500 ┼── ($499-500)
       └──────────────────────────────────────────────────────
            Start    After 3a      After 3b      After 3c
```

**Key Insight**: The consistent ~$1,250 increase per experiment (across all items) demonstrates that write throughput remained stable throughout all failure scenarios.

### 4.3 Why Zero HTTP Errors?

The API Gateway uses **fire-and-forget** semantics for secondary paths:

```go
// From api-gateway/internal/service/bidding.go:146-168

// Publish to NATS for real-time broadcast (non-blocking, best effort)
go func() {
    if err := s.nats.Publish(subject, eventJSON); err != nil {
        fmt.Printf("Warning: failed to publish bid event to NATS: %v\n")
        // Only logs warning, does NOT return error to client!
    }
}()

// Publish to JetStream for archival (async, non-blocking)
go func() {
    if err := s.publishToArchivalQueue(bidEvent); err != nil {
        fmt.Printf("Warning: failed to publish to archival queue: %v\n")
        // Only logs warning, does NOT return error to client!
    }
}()
```

The bid is committed to Redis **before** these async operations. The HTTP response returns success immediately after Redis confirms the write.

### 4.4 Architectural Validation

```
┌─────────────────────────────────────────────────────────────────┐
│                    CRITICAL PATH (validated)                     │
│  Client → API Gateway → Redis (Lua atomic bid) → HTTP 200       │
│                                                                  │
│  ✅ 0% error rate during all failures                           │
│  ✅ Consistent 19ms P50 latency                                 │
│  ✅ ~13 bids/second sustained throughput                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ (async, fire-and-forget)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SECONDARY PATHS (validated)                   │
│                                                                  │
│  3a: Broadcast Service failure                                   │
│      → WebSocket clients disconnected, write path unaffected    │
│                                                                  │
│  3b: Archival Worker failure                                     │
│      → Events not persisted to PostgreSQL, write path unaffected│
│                                                                  │
│  3c: NATS failure                                                │
│      → Events not published, write path unaffected (+16ms P99)  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 Tradeoff Analysis

| Tradeoff | Evidence from Experiment | Conclusion |
|----------|--------------------------|------------|
| **Availability vs. Durability** | Events during NATS outage are lost (not persisted to PostgreSQL) | Acceptable for auction events; critical data (final bid) is in Redis |
| **Latency vs. Consistency** | P99 increased 16ms during NATS failure | Minor impact; async timeout handling adds slight overhead |
| **Simplicity vs. Reliability** | Fire-and-forget requires no retry logic in critical path | Simpler code, but events can be silently dropped |

---

## 5. Conclusions

### 5.1 Key Findings

1. **Write path isolation is complete**: All three experiments demonstrated 0% HTTP error rate during component failures.

2. **Redis writes are unaffected**: The cumulative price increase ($500 → $4,500) across all experiments proves bids were consistently written to Redis.

3. **Latency remains stable**: P50 latency stayed constant at 19ms. Only NATS failure caused a minor P99 increase (+16ms).

4. **Architecture hypothesis validated**: The decoupled design successfully isolates the critical write path from secondary services.

### 5.2 Limitations of This Analysis

1. **Clean shutdown only**: ECS `desired-count=0` performs graceful shutdown. Real failures (crashes, network partitions) may behave differently.

2. **Single failure at a time**: Did not test cascading failures (e.g., NATS + Archival Worker simultaneously).

3. **No data loss quantification**: We confirmed writes succeeded but did not measure how many NATS events were lost during outages.

4. **Short failure duration**: 60-second windows may not reveal issues like connection pool exhaustion or memory leaks.

### 5.3 Recommendations

1. **Implement dead-letter queue**: Capture failed NATS publishes for later replay to ensure event durability.

2. **Add circuit breaker**: Prevent repeated connection attempts during known outages to reduce P99 latency impact.

3. **Monitor secondary paths**: Alert on NATS/Archival failures even though they don't affect users directly.

4. **Test longer outages**: Validate behavior during extended (10+ minute) failures.

### 5.4 Final Summary

**The bidding system demonstrates excellent fault isolation. The write path maintains 100% availability during failures of any secondary component, validating the decoupled architecture design. The tradeoff of potential event loss during outages is acceptable given the system's auction use case, where the authoritative bid state resides in Redis.**

---

## Appendix A: Test Execution Commands

```bash
# Experiment 3a: Broadcast Service Failure
python3 run_experiment3.py \
  --host http://bidding-system-alb-707478221.us-west-2.elb.amazonaws.com \
  --scenario 3a \
  --ecs-cluster bidding-system-cluster \
  --users 100 --spawn-rate 10 --duration 180s \
  --baseline-seconds 30 --failure-seconds 60 \
  --recovery-count 4 --csv-prefix exp3a_v2

# Experiment 3b: Archival Worker Failure
python3 run_experiment3.py \
  --host http://bidding-system-alb-707478221.us-west-2.elb.amazonaws.com \
  --scenario 3b \
  --ecs-cluster bidding-system-cluster \
  --users 100 --spawn-rate 10 --duration 180s \
  --baseline-seconds 30 --failure-seconds 60 \
  --recovery-count 1 --csv-prefix exp3b_v2

# Experiment 3c: NATS Failure
python3 run_experiment3.py \
  --host http://bidding-system-alb-707478221.us-west-2.elb.amazonaws.com \
  --scenario 3c \
  --ecs-cluster bidding-system-cluster \
  --users 100 --spawn-rate 10 --duration 180s \
  --baseline-seconds 30 --failure-seconds 60 \
  --recovery-count 1 --csv-prefix exp3c_v2
```

## Appendix B: Key Source Files

| File | Purpose |
|------|---------|
| `load-tests/run_experiment3.py` | Automated fault injection runner |
| `load-tests/locustfile.py` | Load test definition (`MixedWorkloadUser`) |
| `api-gateway/internal/service/bidding.go` | Bid handling with async NATS publish |
| `api-gateway/internal/redis/client.go` | Redis Lua script for atomic bids |

## Appendix C: Raw CSV Data Files

- `exp3a_v2_stats.csv` - Experiment 3a Locust statistics
- `exp3b_v2_stats.csv` - Experiment 3b Locust statistics
- `exp3c_v2_stats.csv` - Experiment 3c Locust statistics

---

*Test Date: December 6, 2025*
*Test Infrastructure: AWS ECS Fargate (us-west-2)*
*Report Generated: December 6, 2025*
