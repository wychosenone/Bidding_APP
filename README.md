# Real-Time Bidding Service - Scalable Distributed System

A **horizontally scalable, highly available** auction platform designed to handle:
- High write contention (thousands of concurrent bids on the same item)
- Massive read fan-out (broadcasting to tens of thousands of viewers)
- Component failures without affecting core bidding functionality

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [System Components](#system-components)
- [API Endpoints](#api-endpoints)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Load Testing](#load-testing)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Distributed Systems Concepts](#distributed-systems-concepts)

## Architecture Overview

The system is built using an **event-driven, microservices architecture** with clear separation of concerns:

### Data Flow

**Write Path (Bidding):**
```
Client → API Gateway → Redis (atomic compare-and-set)
                    ↓
                    ├→ NATS JetStream (archival queue)
                    └→ NATS Pub/Sub (real-time broadcast)
                                ↓
                    Broadcast Service → WebSocket Clients
                                ↓
                    Archival Worker → PostgreSQL
```

**Read Path (Real-time updates):**
```
Client ←→ Broadcast Service (WebSocket)
              ↑
              └─ NATS Pub/Sub (receives new bid events)
```

**Key Design Principles:**
- **Hot-path optimization:** All real-time operations hit Redis, not PostgreSQL
- **Decoupled services:** Database/queue failures don't block bids
- **Event-driven:** Services communicate via NATS events
- **Horizontal scalability:** Stateless services enable easy scaling

## System Components

### 1. API Gateway (Go)
**Purpose:** Stateless HTTP server that handles bid requests and item queries.

**Key Features:**
- **Stateless design:** No session data stored locally, enabling horizontal scaling
- **Request validation:** Validates bid amounts, user authentication before touching Redis
- **Fast path:** Writes to Redis atomically, publishes to message queue asynchronously
- **Local price cache:** Pre-filters obviously low bids to reduce Redis load
- **Dual Redis strategies:** Supports both Lua scripts and optimistic locking

**Port:** `8080`

### 2. Redis (Cache + Real-Time State Store)
**Purpose:** Single source of truth for real-time auction state.

**Why Redis?**
- **In-memory speed:** Sub-millisecond read/write latency
- **Atomic operations:** Lua scripts ensure thread-safe bid updates
- **High concurrency:** Handles thousands of simultaneous writes

**Pattern:** Hot-path optimization - all real-time operations hit Redis, not PostgreSQL

**Redis Strategies:**
- **Lua Scripts (default):** Atomic compare-and-set operations
- **Optimistic Locking:** WATCH/MULTI/EXEC pattern for high contention scenarios

### 3. Broadcast Service (Go + WebSockets)
**Purpose:** Maintains persistent connections to viewers and fans out updates.

**Key Features:**
- **Stateful service:** Holds active WebSocket connections
- **NATS subscriber:** Listens to bid events via NATS Pub/Sub
- **Efficient fan-out:** One NATS message → N WebSocket clients
- **Connection management:** Handles connection lifecycle and cleanup

**Port:** `8081`

### 4. Message Queue (NATS JetStream)
**Purpose:** Decouples fast write path from slow archival path.

**Why NATS?**
- **Lightweight:** Low overhead, high throughput
- **JetStream:** Persistent message storage for reliability
- **Pub/Sub:** Built-in real-time broadcasting
- **Decoupling:** Bidding API doesn't wait for database writes (low latency)
- **Resilience:** Database downtime doesn't affect accepting bids

### 5. Archival Worker (Go)
**Purpose:** Consumes queue messages and persists to PostgreSQL.

**Key Features:**
- **Event-driven consumer:** Processes at its own pace
- **Automatic schema creation:** Initializes database tables on startup
- **Graceful shutdown:** Handles in-flight messages during shutdown

**Pattern:** Event-driven consumer - processes at its own pace

### 6. PostgreSQL
**Purpose:** Long-term storage for bid history and analytics.

**Why separate from Redis?**
- **Redis:** Millisecond access for "current bid"
- **PostgreSQL:** Full history, complex queries, durability, analytics

## API Endpoints

### Health Check
```
GET /health
```
Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "api-gateway",
  "time": "2024-01-01T00:00:00Z"
}
```

### Get Item
```
GET /api/v1/items/{id}
```
Retrieves current bid information for an item.

**Response:**
```json
{
  "id": "item_123",
  "name": "Vintage Watch",
  "current_bid": 150.50,
  "highest_bidder_id": "user_456",
  "status": "active"
}
```

### Place Bid
```
POST /api/v1/items/{id}/bid
Content-Type: application/json

{
  "user_id": "user_123",
  "amount": 200.00
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Bid accepted",
  "current_bid": 200.00,
  "your_bid": 200.00,
  "is_highest": true,
  "event_id": "evt_abc123"
}
```

**Response (Rejected):**
```json
{
  "success": false,
  "message": "Bid amount must be higher than current bid",
  "current_bid": 250.00,
  "your_bid": 200.00,
  "is_highest": false
}
```

### WebSocket Connection
```
WS ws://localhost:8081/ws?item_id={id}
```
Establishes WebSocket connection to receive real-time bid updates for a specific item.

**Message Format:**
```json
{
  "event_id": "evt_abc123",
  "item_id": "item_123",
  "bid_id": "bid_xyz",
  "user_id": "user_456",
  "amount": 200.00,
  "previous_bid": 150.50,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Getting Started

### Prerequisites

- **Go** 1.21 or later
- **Docker** and **Docker Compose**
- **Make** (optional, for convenience commands)

### Local Development

#### Option 1: Using Docker Compose (Recommended)

```bash
# Start all services
make run

# Or manually:
cd infrastructure/docker
docker-compose up --build -d

# View logs
make logs

# Stop services
make stop
```

This will start:
- Redis on port `6379`
- NATS on ports `4222` (client) and `8222` (monitoring)
- PostgreSQL on port `5432`
- API Gateway on port `8080`
- Broadcast Service on port `8081`
- Archival Worker (background)

#### Option 2: Run Services Locally

```bash
# Terminal 1: Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: Start NATS
docker run -d -p 4222:4222 -p 8222:8222 nats:2-alpine -js

# Terminal 3: Start PostgreSQL
docker run -d -p 5432:5432 \
  -e POSTGRES_DB=bidding \
  -e POSTGRES_USER=bidding \
  -e POSTGRES_PASSWORD=password \
  postgres:15-alpine

# Terminal 4: Run API Gateway
make dev-api
# Or: cd api-gateway && go run ./cmd

# Terminal 5: Run Broadcast Service
make dev-broadcast
# Or: cd broadcast-service && go run ./cmd

# Terminal 6: Run Archival Worker
make dev-archival
# Or: cd archival-worker && go run ./cmd
```

### Environment Variables

**API Gateway:**
- `SERVER_ADDR`: Server address (default: `:8080`)
- `REDIS_ADDR`: Redis address (default: `localhost:6379`)
- `REDIS_PASSWORD`: Redis password (default: empty)
- `REDIS_DB`: Redis database number (default: `0`)
- `REDIS_STRATEGY`: Redis strategy - `lua` or `optimistic` (default: `lua`)
- `NATS_URL`: NATS connection URL (default: `nats://localhost:4222`)

**Broadcast Service:**
- `SERVER_ADDR`: Server address (default: `:8081`)
- `NATS_URL`: NATS connection URL (default: `nats://localhost:4222`)

**Archival Worker:**
- `POSTGRES_URL`: PostgreSQL connection string (default: `postgres://bidding:password@localhost:5432/bidding?sslmode=disable`)
- `NATS_URL`: NATS connection URL (default: `nats://localhost:4222`)

### Build Services

```bash
# Build all services
make build

# Build individual services
cd api-gateway && go build -o bin/api-gateway ./cmd
cd broadcast-service && go build -o bin/broadcast-service ./cmd
cd archival-worker && go build -o bin/archival-worker ./cmd
```

### Test the System

```bash
# Health check
curl http://localhost:8080/health

# Get item (will create if doesn't exist)
curl http://localhost:8080/api/v1/items/test_item

# Place a bid
curl -X POST http://localhost:8080/api/v1/items/test_item/bid \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123", "amount": 100.00}'

# Place another bid
curl -X POST http://localhost:8080/api/v1/items/test_item/bid \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_456", "amount": 150.00}'
```

## Deployment

### AWS Deployment (Terraform)

The project includes Terraform configurations for deploying to AWS with:
- **ECS Fargate** for container orchestration
- **ElastiCache (Redis)** for caching
- **RDS (PostgreSQL)** for persistent storage
- **Application Load Balancer** for HTTP/WebSocket routing
- **ECR** for container images

See [infrastructure/terraform/README.md](infrastructure/terraform/README.md) for detailed deployment instructions.

**Quick Start:**
```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
terraform init
terraform plan
terraform apply
```

**Estimated Cost:** ~$92/month (development) to ~$720/month (production)

### Docker Compose Production

For production deployments, modify `infrastructure/docker/docker-compose.yml` with:
- Resource limits
- Health checks
- Logging configuration
- Secrets management
- SSL/TLS certificates

## Load Testing

The project includes comprehensive load tests using **Locust** and custom Python scripts.

### Setup

```bash
cd load-tests
pip install -r requirements.txt
```

### Experiment 1: Write Contention Test

Measure maximum bids per second for a single highly contested item.

```bash
# Basic test (100 concurrent users)
locust -f locustfile.py --headless -u 100 -r 10 -t 60s \
  ContendedItemBidder --host=http://localhost:8080

# Aggressive test (1000 concurrent users)
locust -f locustfile.py --headless -u 1000 -r 100 -t 120s \
  ContendedItemBidder --host=http://localhost:8080

# Interactive mode with web UI
locust -f locustfile.py ContendedItemBidder --host=http://localhost:8080
# Then open http://localhost:8089
```

### Experiment 2: WebSocket Fan-Out Test

Measure broadcast latency as the number of concurrent viewers increases.

```bash
# Test with 100 connections
python websocket_fanout_test.py --connections 100 --bids 10 --interval 5

# Test with 1000 connections
python websocket_fanout_test.py --connections 1000 --bids 10 --interval 5

# Test with 10,000 connections
python websocket_fanout_test.py --connections 10000 --bids 5 --interval 10
```

### Experiment 3: Resilience Test

Verify write-path availability during component failures.

```bash
# Run baseline workload
locust -f locustfile.py --headless -u 200 -r 20 -t 300s \
  MixedWorkloadUser --host=http://localhost:8080

# In another terminal, kill components and observe:
# - Broadcast Service: docker kill bidding-broadcast
# - PostgreSQL: docker stop bidding-postgres
# - NATS: docker stop bidding-nats
```

See [load-tests/README.md](load-tests/README.md) for detailed testing instructions and results.

## Project Structure

```
.
├── api-gateway/              # HTTP API service
│   ├── cmd/                  # Main application entry point
│   │   └── main.go
│   └── internal/             # Private application code
│       ├── handlers/         # HTTP request handlers
│       │   └── handlers.go
│       ├── service/          # Business logic
│       │   └── bidding.go
│       └── redis/            # Redis client wrapper
│           └── client.go
├── broadcast-service/        # WebSocket service
│   ├── cmd/
│   │   └── main.go
│   └── internal/
│       ├── websocket/        # WebSocket connection management
│       │   ├── handler.go
│       │   └── manager.go
│       └── redis/            # Redis Pub/Sub subscriber (if used)
│           └── subscriber.go
├── archival-worker/          # Database persistence worker
│   ├── cmd/
│   │   └── main.go
│   └── internal/
│       ├── consumer/         # NATS consumer
│       │   └── nats.go
│       └── database/         # PostgreSQL client
│           └── postgres.go
├── shared/                   # Shared libraries
│   ├── models/               # Data models
│   │   ├── bid.go
│   │   └── item.go
│   └── config/               # Configuration utilities
│       └── config.go
├── infrastructure/           # Deployment configurations
│   ├── docker/               # Docker Compose setup
│   │   ├── docker-compose.yml
│   │   └── Dockerfile.*
│   └── terraform/            # AWS infrastructure as code
│       ├── main.tf
│       ├── vpc.tf
│       ├── ecs.tf
│       ├── elasticache.tf
│       └── rds.tf
├── load-tests/               # Load testing scripts
│   ├── locustfile.py         # Locust test scenarios
│   ├── websocket_fanout_test.py
│   ├── run_experiment3.py
│   └── README.md
├── Makefile                  # Convenience commands
└── README.md                 # This file
```

## Technology Stack

- **Go 1.21+:** Fast, concurrent (goroutines), low memory footprint
- **Redis 7:** In-memory data store with atomic operations and pub/sub
- **NATS 2:** Lightweight message queue with JetStream persistence
- **PostgreSQL 15:** Reliable relational database for archival
- **WebSockets:** Full-duplex communication for real-time updates
- **Docker & Docker Compose:** Containerization and local development
- **Terraform:** Infrastructure as code for AWS deployment
- **Locust:** Python-based load testing framework

## Distributed Systems Concepts

This project demonstrates several key distributed systems patterns:

### 1. CAP Theorem Trade-offs
- **Redis:** CP system (consistency + partition tolerance)
- **System:** Prioritizes availability over immediate consistency in archival path
- **Trade-off:** Eventual consistency for archival allows high availability

### 2. Event-Driven Architecture
- Services communicate via events (NATS Pub/Sub, JetStream)
- Loose coupling enables independent scaling and deployment
- Asynchronous processing decouples fast path from slow path

### 3. CQRS Pattern (Command Query Responsibility Segregation)
- **Write model:** Optimized for atomic updates (Redis + Lua scripts)
- **Read model:** Optimized for fan-out (WebSocket connections)
- Separate read and write paths for optimal performance

### 4. Circuit Breaker Pattern
- Queue failures don't cascade to API Gateway
- Services fail independently
- Graceful degradation under component failures

### 5. Horizontal Scalability
- **Stateless API Gateway:** Add more instances behind load balancer
- **Stateful Broadcast Service:** Can use sticky sessions or connection state sharing
- **Independent scaling:** Scale each service based on its own load

### 6. Hot-Path Optimization
- Critical path (bid acceptance) only depends on Redis
- Slow operations (database writes) happen asynchronously
- Pre-filtering with local cache reduces Redis load

## Key Features

- ✅ **High Concurrency:** Handles thousands of concurrent bids on single items
- ✅ **Real-time Updates:** WebSocket broadcasting to thousands of viewers
- ✅ **Fault Tolerance:** Bidding continues during database/queue failures
- ✅ **Horizontal Scaling:** Stateless services enable easy scaling
- ✅ **Atomic Operations:** Redis Lua scripts ensure data consistency
- ✅ **Event-Driven:** Decoupled services via NATS messaging
- ✅ **Comprehensive Testing:** Load tests for all three core experiments
- ✅ **Production Ready:** AWS deployment with Terraform

## Monitoring

### Health Checks
- API Gateway: `GET http://localhost:8080/health`
- Broadcast Service: `GET http://localhost:8081/health`
- NATS Monitoring: `http://localhost:8222/varz`

### Logs
```bash
# Docker Compose logs
make logs

# Individual service logs
docker logs bidding-api-gateway
docker logs bidding-broadcast
docker logs bidding-archival-worker
```

### Metrics
- **Redis:** Monitor via `redis-cli INFO`
- **NATS:** Monitor via `http://localhost:8222/varz`
- **PostgreSQL:** Monitor via `pg_stat_activity` and `pg_stat_statements`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and load tests
5. Submit a pull request

## License

This project is part of a distributed systems course demonstration.
