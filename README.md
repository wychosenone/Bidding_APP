# Real-Time Bidding Service - Scalable Distributed System

## Architecture Overview

This is a **horizontally scalable, highly available** auction platform designed to handle:
- High write contention (thousands of concurrent bids on the same item)
- Massive read fan-out (broadcasting to tens of thousands of viewers)
- Component failures without affecting core bidding functionality

## System Components

### 1. API Gateway (Go)
**Purpose:** Stateless HTTP server that handles bid requests and item queries.

**Key Concepts:**
- **Stateless design:** No session data stored locally, enabling horizontal scaling
- **Request validation:** Validates bid amounts, user authentication before touching Redis
- **Fast path:** Writes to Redis atomically, publishes to message queue asynchronously

### 2. Redis (Cache + Message Bus)
**Purpose:** Single source of truth for real-time auction state.

**Why Redis?**
- **In-memory speed:** Sub-millisecond read/write latency
- **Atomic operations:** Lua scripts ensure thread-safe bid updates
- **Pub/Sub built-in:** Instant message broadcasting without polling

**Pattern:** Hot-path optimization - all real-time operations hit Redis, not PostgreSQL

### 3. Broadcast Service (Go + WebSockets)
**Purpose:** Maintains persistent connections to viewers and fans out updates.

**Key Concepts:**
- **Stateful service:** Holds active WebSocket connections (different from API Gateway)
- **Redis Pub/Sub subscriber:** Listens to bid events and broadcasts to connected clients
- **Efficient fan-out:** One Redis message → N WebSocket clients

### 4. Message Queue (NATS/Kafka)
**Purpose:** Decouples fast write path from slow archival path.

**Why asynchronous?**
- Bidding API doesn't wait for database writes (low latency)
- Database downtime doesn't affect accepting bids (high availability)
- Natural backpressure handling during traffic spikes

### 5. Archival Worker (Go)
**Purpose:** Consumes queue messages and persists to PostgreSQL.

**Pattern:** Event-driven consumer - processes at its own pace

### 6. PostgreSQL
**Purpose:** Long-term storage for bid history and analytics.

**Why separate from Redis?**
- Redis: Millisecond access for "current bid"
- PostgreSQL: Full history, complex queries, durability

## Data Flow

### Write Path (Bidding)
```
Client → API Gateway → Redis (atomic compare-and-set)
                    ↓
                    ├→ Redis Pub/Sub (real-time broadcast)
                    └→ NATS Queue (archival)
                                ↓
                            Archival Worker → PostgreSQL
```

**Key insight:** Write path only depends on Redis. Database/queue failures don't block bids.

### Read Path (Real-time updates)
```
Client ←→ Broadcast Service (WebSocket)
              ↑
              └─ Redis Pub/Sub (receives new bid events)
```

## Distributed Systems Concepts Demonstrated

1. **CAP Theorem Trade-offs:**
   - Redis: CP system (consistency + partition tolerance)
   - Our system: Prioritizes availability over immediate consistency in archival

2. **Event-Driven Architecture:**
   - Services communicate via events (Redis Pub/Sub, NATS)
   - Loose coupling enables independent scaling and deployment

3. **CQRS Pattern (Command Query Responsibility Segregation):**
   - Write model: Optimized for atomic updates (Redis + Lua)
   - Read model: Optimized for fan-out (WebSocket connections)

4. **Circuit Breaker Pattern:**
   - Queue failures don't cascade to API Gateway
   - Services fail independently

5. **Horizontal Scalability:**
   - Stateless API Gateway: Add more instances behind load balancer
   - Stateful Broadcast Service: Use sticky sessions or Redis for connection state

## Technology Choices

- **Go:** Fast, concurrent (goroutines), low memory footprint
- **Redis:** Speed + atomicity + pub/sub in one tool
- **NATS:** Lightweight, high-throughput message queue
- **PostgreSQL:** Reliable relational database for archival
- **WebSockets:** Full-duplex communication for real-time updates

## Project Structure

```
.
├── api-gateway/          # HTTP API service
│   ├── cmd/              # Main application entry point
│   └── internal/         # Private application code
│       ├── handlers/     # HTTP request handlers
│       ├── service/      # Business logic
│       └── redis/        # Redis client wrapper
├── broadcast-service/    # WebSocket service
│   ├── cmd/
│   └── internal/
│       ├── websocket/    # WebSocket connection management
│       └── redis/        # Redis Pub/Sub subscriber
├── archival-worker/      # Database persistence worker
│   ├── cmd/
│   └── internal/
│       ├── consumer/     # NATS consumer
│       └── database/     # PostgreSQL client
├── shared/               # Shared libraries
│   ├── models/           # Data models (Item, Bid)
│   └── config/           # Configuration utilities
├── infrastructure/       # Deployment configs
│   ├── docker/           # Docker Compose
│   └── k8s/              # Kubernetes manifests
└── load-tests/           # Locust load testing
```

## Getting Started

See each service's README for specific setup instructions.

## Experiments

1. **Write Contention Test:** Measure maximum bids/sec on single item
2. **WebSocket Fan-Out Test:** Measure broadcast latency to N clients
3. **Resilience Test:** Verify write-path availability during component failures
