# Experiment 2: WebSocket Fan-Out Scalability

## 1. Purpose

This experiment evaluates the **broadcast latency scalability** of our WebSocket fan-out architecture as concurrent connections increase from 100 to 10,000+.

### Research Questions

1. **How does broadcast latency scale with connection count?** — Is the relationship linear, logarithmic, or exponential?
2. **What is the effectiveness of horizontal scaling?** — Does doubling broadcast service instances halve the latency?
3. **What is the maximum concurrent connection capacity?** — At what point does the system fail to deliver messages reliably?

### Tradeoffs Explored

| Tradeoff | Options | Our Hypothesis |
|----------|---------|----------------|
| **Vertical vs Horizontal Scaling** | 2x (1 vCPU, 2GB) vs 4x (0.5 vCPU, 1GB) | More instances with smaller resources will provide better fan-out performance |
| **Latency vs Connection Count** | Accept higher latency for more connections | P99 < 500ms is acceptable for real-time bidding at 10K connections |
| **Message Delivery vs Performance** | Prioritize reliability over speed | 100% delivery is non-negotiable; latency is secondary |

### Limitations

- **Test client constraints**: EC2 t3.medium instances limited to ~3,500 TCP connections due to ephemeral port exhaustion
- **Clock synchronization**: Distributed testing introduced clock drift between EC2 and ECS Fargate, affecting latency measurements
- **Single region**: All tests conducted in us-west-2; cross-region latency not evaluated
- **Single item**: All connections subscribed to the same item; multi-item fan-out not tested

---

## 2. Experimental Setup

### 2.1 System Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
│ Test Client │────▶│ API Gateway │────▶│   Redis (Lua)       │
│   (EC2)     │     │   (ECS)     │     │   ElastiCache       │
└─────────────┘     └──────┬──────┘     └─────────────────────┘
                           │
                    ┌──────▼──────┐
                    │    NATS     │
                    │  (Pub/Sub)  │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼─────┐     ┌─────▼─────┐
    │Broadcast│      │ Broadcast │     │ Broadcast │
    │Service 1│      │ Service 2 │     │ Service N │
    └────┬────┘      └─────┬─────┘     └─────┬─────┘
         │                 │                 │
         └────────┬────────┴────────┬────────┘
                  │   WebSocket     │
         ┌────────▼────────┐ ┌──────▼────────┐
         │ Client 1...N/2  │ │Client N/2...N │
         └─────────────────┘ └───────────────┘
```

### 2.2 Infrastructure Configuration

| Component | Rounds 1-3 | Round 4 |
|-----------|------------|---------|
| Broadcast Service | 2x ECS Fargate (1 vCPU, 2GB) | 4x ECS Fargate (0.5 vCPU, 1GB) |
| API Gateway | 1x ECS Fargate (1 vCPU, 2GB) | 4x ECS Fargate (0.5 vCPU, 1GB) |
| Redis | ElastiCache cache.t3.micro | ElastiCache cache.t3.micro |
| NATS | 1x ECS Fargate (0.25 vCPU, 512MB) | 1x ECS Fargate (0.25 vCPU, 512MB) |
| Region | us-west-2 | us-west-2 |

### 2.3 Test Methodology

1. Establish N concurrent WebSocket connections to broadcast service via ALB
2. Send 10 bid requests via HTTP API at 5-second intervals
3. Measure end-to-end latency: `T_receive - T_server_timestamp`
4. Calculate P50, P95, P99 latencies across all N connections per bid
5. Verify 100% message delivery (all N clients receive each bid event)

**Test Script**: `load-tests/websocket_fanout_test.py`

---

## 3. Results

### 3.1 Latency vs Connection Count

| Connections | Round 1 P99 | Round 2 P99 | Round 4 P99 | Delivery Rate |
|-------------|-------------|-------------|-------------|---------------|
| 100 | 20.98 ms | 22.53 ms | 16.63 ms | 100% |
| 1,000 | 105.31 ms | 163.83 ms | 171.87 ms | 100% |
| ~3,500 | — | — | 318.94 ms | 100% |
| ~4,500 | 971.49 ms | — | — | 89% |
| ~10,000 | Failed | 512.33 ms | 445.62 ms | 90-100% |

**Figure 1: P99 Latency Scaling** (conceptual representation)

```
P99 Latency (ms)
    │
1000├─────────────────────────────────────●─── Round 1 (fails)
    │                                   ╱
 800├                                 ╱
    │                               ╱
 600├─────────────────────────────●───────── Round 3
    │                           ╱
 500├─────────────────────────●───────────── Round 2
    │                       ╱
 450├───────────────────────●─────────────── Round 4 (4x BS)
    │                     ╱
 300├───────────────────●───────────────────
    │                 ╱
 200├───────────────●───────────────────────
    │             ╱
 100├─────────●─╱───────────────────────────
    │       ╱
  20├─────●─────────────────────────────────
    │   ╱
    └───┴─────┴─────┴─────┴─────┴─────┴────▶ Connections
       100   1K    3K    5K    7K   10K
```

### 3.2 Horizontal Scaling Effectiveness

Comparing 2x vs 4x Broadcast Service instances at ~10,000 connections:

| Metric | 2x BS (Round 2) | 4x BS (Round 4) | Improvement |
|--------|-----------------|-----------------|-------------|
| P50 | 174.22 ms | 145.88 ms | 16.3% |
| P95 | 451.13 ms | 398.25 ms | 11.7% |
| P99 | 512.33 ms | 445.62 ms | **13.0%** |
| Delivery Rate | 90% | 100% | **+10%** |

### 3.3 Connection Capacity Limits

| Test Configuration | Max Stable Connections | Limiting Factor |
|--------------------|------------------------|-----------------|
| 1x EC2 t3.medium | ~4,500 | Ephemeral port exhaustion |
| 3x EC2 t3.medium | ~10,500 | Test client capacity |
| 2x Broadcast Service | ~9,500 | 90% delivery threshold |
| 4x Broadcast Service | ~10,500+ | Not reached |

---

## 4. Analysis

### 4.1 Scaling Behavior

**Finding 1: Latency scales sub-linearly with connection count.**

The data shows approximately O(N^0.7) scaling rather than linear O(N):
- 10x connections (100→1000): ~8x latency increase
- 10x connections (1000→10000): ~4x latency increase

This sub-linear scaling is attributable to:
1. **Parallel broadcast workers**: The broadcast service uses 10 worker goroutines for >500 connections
2. **Buffered channels**: 10,000-message buffer prevents blocking under load
3. **NATS efficiency**: Pub/sub model distributes load across broadcast instances

**Finding 2: Horizontal scaling provides diminishing returns.**

Doubling broadcast instances (2x→4x) yielded only 13% P99 improvement. This suggests:
- The bottleneck is not purely CPU-bound
- Network I/O and WebSocket write operations dominate latency
- Further scaling requires architectural changes (e.g., connection sharding by item)

### 4.2 Reliability vs Performance

**Finding 3: 4x configuration achieved 100% delivery at 10K connections.**

The critical improvement from Round 2 to Round 4 was not latency but **reliability**:
- Round 2: 90% delivery rate (message loss under load)
- Round 4: 100% delivery rate (no message loss)

This validates our hypothesis that more instances with smaller resources provide better fan-out reliability.

### 4.3 Clock Drift Challenge

**Finding 4: Multiple EC2 test clients introduce measurement bias.**

Clock drift occurs between **EC2 test clients** (not Broadcast Service instances) and the ECS Fargate API Gateway where `server_timestamp` is generated:

```
EC2 Instance 1 (clock +50ms drift)  ─┐
EC2 Instance 2 (clock -30ms drift)  ─┼─▶ Each measures: receive_time - server_timestamp
EC2 Instance 3 (clock +100ms drift) ─┘
                                          ↑
API Gateway (ECS) ──▶ Generates server_timestamp (single clock source)
```

The Broadcast Service instances do **not** affect clock measurements—they only forward the original `BidEvent.Timestamp` without modification.

| Round | EC2 Instances | BS Instances | Clock Issue | Impact |
|-------|---------------|--------------|-------------|--------|
| 1 | 1x | 2x | Minimal | Reliable data |
| 2 | 3x | 2x | Moderate | Some negative latencies |
| 3 | 6x | 2x | Significant | Anomalously low readings |
| 4 | 3x + correction | 4x | Corrected | Reliable after offset |

**Mitigation applied**: Clock offset correction algorithm that detects minimum negative latency and applies uniform offset:

```python
if min(latencies) < 0:
    offset = abs(min(latencies)) + 10  # 10ms buffer
    latencies = [lat + offset for lat in latencies]
```

### 4.4 Limitations of Analysis

1. **Clock correction introduces bias**: The offset algorithm shifts all values uniformly, which may overestimate absolute latencies while preserving relative comparisons
2. **Round 3 data unreliable**: 6x EC2 configuration showed physically impossible latency reductions; data should be treated as indicative only
3. **Single-item testing**: Real-world scenarios involve multiple items with different subscriber counts; cross-item performance not evaluated
4. **Warm-start only**: Tests began after connections were established; connection establishment latency not measured

---

## 5. Conclusions

### Key Findings

| Question | Answer | Evidence |
|----------|--------|----------|
| Latency scaling | Sub-linear O(N^0.7) | 10x connections → 4-8x latency |
| Horizontal scaling effectiveness | Moderate (13% improvement) | 2x→4x BS: P99 512→446ms |
| Maximum capacity | 10,500+ connections | 100% delivery maintained |

### Recommendations

1. **Deploy 4+ broadcast instances** for production workloads expecting >5K concurrent connections
2. **Implement connection sharding** by item ID to distribute load more evenly
3. **Use client-side timing** for latency measurement in distributed test environments
4. **Configure auto-scaling** based on active connection count with target <3,000 connections per instance

### Future Work

- Evaluate WebSocket compression for bandwidth-constrained environments
- Test multi-item scenarios with varying subscriber distributions
- Implement connection migration for zero-downtime scaling
- Measure cross-region fan-out latency with global deployments

---

*Test Date: December 5-6, 2025*
*Test Code: `load-tests/websocket_fanout_test.py`*
*Infrastructure: `infrastructure/terraform/ecs-simple.tf`*
