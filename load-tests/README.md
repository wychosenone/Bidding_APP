# Load Testing Guide

This directory contains load tests for the three experiments described in the project proposal.

## Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Ensure all services are running:

```bash
cd ..
make run
```

## Experiment 1: Write Contention Test

**Goal:** Determine maximum bids per second for a single highly contested item.

**Test Strategy:** Multiple users simultaneously bid on the SAME item to test Redis atomic operations.

**Run the test:**

```bash
# Basic test with 100 concurrent users
locust -f locustfile.py --headless -u 100 -r 10 -t 60s ContendedItemBidder --host=http://localhost:8080

# Aggressive test with 1000 concurrent users
locust -f locustfile.py --headless -u 1000 -r 100 -t 120s ContendedItemBidder --host=http://localhost:8080

# Interactive mode with web UI
locust -f locustfile.py ContendedItemBidder --host=http://localhost:8080
# Then open http://localhost:8089 in your browser
```

**Parameters:**
- `-u` or `--users`: Number of concurrent users
- `-r` or `--spawn-rate`: Users spawned per second
- `-t` or `--run-time`: Test duration (e.g., 60s, 5m)
- `--headless`: Run without web UI
- `--host`: API server URL

**Key Metrics to Observe:**
- Total requests per second (RPS)
- P95 and P99 latency for POST requests
- Ratio of accepted vs rejected bids
- Error rate (should be 0% for valid rejections)

**Expected Results:**
- Redis Lua script should handle high concurrency without data corruption
- Latency should remain stable even under extreme load
- System should gracefully reject bids that are too low

## Experiment 2: WebSocket Fan-Out Scalability Test

**Goal:** Measure broadcast latency as the number of concurrent viewers increases.

**Test Strategy:** Establish N WebSocket connections, send a single bid, measure time for all clients to receive it.

**Run the test:**

```bash
# Test with 100 connections
python websocket_fanout_test.py --connections 100 --bids 10 --interval 5

# Test with 1000 connections
python websocket_fanout_test.py --connections 1000 --bids 10 --interval 5

# Test with 10,000 connections
python websocket_fanout_test.py --connections 10000 --bids 5 --interval 10

# Custom configuration
python websocket_fanout_test.py \
    --connections 5000 \
    --bids 20 \
    --interval 3 \
    --ws-url ws://localhost:8081 \
    --api-url http://localhost:8080 \
    --item-id my_test_item
```

**Parameters:**
- `--connections`: Number of WebSocket connections to establish
- `--bids`: Number of bids to send during the test
- `--interval`: Seconds to wait between bids
- `--ws-url`: WebSocket server URL
- `--api-url`: HTTP API server URL
- `--item-id`: Item ID to test

**Key Metrics to Observe:**
- P50, P95, P99 broadcast latency
- Percentage of clients that successfully received each event
- Memory usage of broadcast-service container: `docker stats bidding-broadcast`
- CPU usage trends

**Expected Results:**
- Latency should scale sub-linearly with connection count
- P99 latency should remain under 100ms for 1000 connections
- System should handle 10,000+ connections with reasonable resource usage

**Monitor Resources During Test:**

```bash
# Watch Docker container stats
watch -n 1 'docker stats --no-stream bidding-broadcast'

# Check WebSocket connection count
curl http://localhost:8081/stats/items/fanout_test_item
```

## Experiment 3: Resilience & Availability Test

**Goal:** Verify the write path remains available during backend component failures.

**Test Strategy:** Run mixed workload while injecting failures into different components.

**Run the baseline test:**

```bash
# Mixed workload - bidders and viewers
locust -f locustfile.py --headless -u 200 -r 20 -t 300s MixedWorkloadUser --host=http://localhost:8080
```

**Test 3a: Broadcast Service Failure**

While the test is running, kill the broadcast service:

```bash
# In another terminal
docker kill bidding-broadcast

# Observe: WebSocket clients disconnect, but bidding continues
# Monitor API latency - should remain unchanged

# Restart after 30 seconds
docker start bidding-broadcast

# Observe: Clients can reconnect
```

**Expected:** API write path is completely unaffected. Bids continue being accepted.

**Test 3b: PostgreSQL Failure**

While the test is running, stop PostgreSQL:

```bash
# In another terminal
docker stop bidding-postgres

# Observe: Bidding continues normally
# Check NATS queue is buffering messages: curl http://localhost:8222

# Restart after 60 seconds
docker start bidding-postgres

# Observe: Archival worker resumes processing
```

**Expected:** Zero impact on bid acceptance. Database writes are queued in NATS.

**Test 3c: NATS Failure**

While the test is running, stop NATS:

```bash
# In another terminal
docker stop bidding-nats

# Observe: Bidding continues normally
# Only archival path is affected

# Restart after 60 seconds
docker start bidding-nats
```

**Expected:** Zero impact on bid acceptance. Messages lost during outage (demonstrating eventual consistency trade-off).

**Key Metrics for Resilience:**
- API latency before, during, and after failure
- Total requests per second (should remain constant)
- Error rate (should be 0% for bid API during backend failures)
- Recovery time after component restart

**Monitoring During Tests:**

```bash
# Monitor all containers
docker-compose logs -f

# Check Redis state
docker exec bidding-redis redis-cli GET item:contested_item_1:current_bid

# Check NATS statistics
curl http://localhost:8222/varz

# Check PostgreSQL
docker exec bidding-postgres psql -U bidding -d bidding -c "SELECT COUNT(*) FROM bids;"
```

## Additional Tests

### General Load Test (Mixed Traffic)

Realistic simulation with multiple items and various user behaviors:

```bash
locust -f locustfile.py --headless -u 500 -r 50 -t 300s --host=http://localhost:8080
```

### Stress Test (Find Breaking Point)

Gradually increase load until the system breaks:

```bash
locust -f locustfile.py --headless -u 5000 -r 100 --host=http://localhost:8080
# Stop when error rate exceeds 1% or latency becomes unacceptable
```

## Interpreting Results

### Good Performance Indicators:
- P99 latency under 100ms for bid API
- 0% error rate for valid requests
- Linear scaling with additional instances
- Graceful degradation under extreme load

### Red Flags:
- High error rates
- Latency spikes or timeout errors
- Memory leaks (increasing RAM over time)
- Database connection pool exhaustion

## Troubleshooting

**Issue:** Locust can't connect to services

```bash
# Check services are running
docker-compose ps

# Check ports are accessible
curl http://localhost:8080/health
curl http://localhost:8081/health
```

**Issue:** WebSocket test fails to establish connections

```bash
# Check broadcast service logs
docker logs bidding-broadcast

# Reduce connection count
python websocket_fanout_test.py --connections 10
```

**Issue:** Database errors during archival

```bash
# Check PostgreSQL is running
docker exec bidding-postgres pg_isready

# Check archival worker logs
docker logs bidding-archival-worker

# Manually verify schema
docker exec bidding-postgres psql -U bidding -d bidding -c "\dt"
```

## Performance Tuning

If tests reveal bottlenecks, consider:

1. **Redis:** Increase connection pool size, enable pipelining
2. **PostgreSQL:** Tune connection pool, add indexes, batch inserts
3. **NATS:** Enable JetStream for persistence, increase buffer sizes
4. **Go Services:** Increase GOMAXPROCS, profile with pprof
5. **Docker:** Increase resource limits in docker-compose.yml
