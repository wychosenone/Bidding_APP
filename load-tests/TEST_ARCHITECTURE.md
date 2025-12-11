# Test Architecture: EC2 vs Local Machine

This document explains the full workflow for running tests from two different locations.

## Architecture Overview

**Key Point**: The bidding application services run on **ECS Fargate** (serverless containers), NOT on EC2 instances. EC2 is only used as a **test client** to run load tests.

### Components:
- **ECS Fargate**: Runs API Gateway, Broadcast Service, Archival Worker, NATS (serverless containers)
- **ALB**: Application Load Balancer (public-facing, in public subnets)
- **ElastiCache Redis**: In private subnets
- **RDS PostgreSQL**: In private subnets
- **Test Client**: Can run from EC2 (same VPC) or local machine (internet)

---

## Scenario 1: Tests Run from EC2 Instance (Same VPC) - FAST ⚡

### Architecture Diagram:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AWS VPC (us-west-2)                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Public Subnets                              │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │  Application Load Balancer (ALB)                  │   │  │
│  │  │  - Public DNS: bidding-system-alb-xxx.elb...     │   │  │
│  │  │  - Internal routing to ECS tasks                  │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Private Subnets                             │  │
│  │                                                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │ ECS Fargate  │  │ ECS Fargate  │  │ ECS Fargate  │  │  │
│  │  │ API Gateway  │  │ Broadcast    │  │ Archival     │  │  │
│  │  │ (2 tasks)    │  │ Service      │  │ Worker       │  │  │
│  │  │              │  │ (2 tasks)    │  │ (1 task)     │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │  │
│  │                                                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │ ElastiCache  │  │ RDS          │  │ NATS         │  │  │
│  │  │ Redis        │  │ PostgreSQL   │  │ (ECS Fargate)│  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │  │
│  │                                                           │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │  EC2 Instance (Test Client)                       │   │  │
│  │  │  - Runs: websocket_fanout_test.py                 │   │  │
│  │  │  - Connects to ALB via internal DNS               │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Full Workflow (EC2 Test Client):

#### Step 1: Test Client Setup
```
EC2 Instance (Private Subnet)
├─ Python 3 installed
├─ websocket_fanout_test.py script
└─ Connects to: ALB internal DNS name
```

#### Step 2: WebSocket Connection Establishment
```
1. EC2 Test Client
   ↓ HTTP Upgrade Request
   ↓ (Internal AWS network, ~1-2ms)
2. ALB (Public Subnet)
   ↓ Routes to Broadcast Service (priority 50 rule: /ws/*)
   ↓ (Internal AWS network, ~1-2ms)
3. ECS Fargate - Broadcast Service (Private Subnet)
   ↓ Accepts WebSocket upgrade
   ↓ (Internal AWS network, ~1ms)
4. Connection established
   Total: ~3-5ms latency
```

#### Step 3: Bid Placement & Broadcast Flow
```
1. EC2 Test Client
   ↓ POST /api/v1/items/{id}/bid
   ↓ (Internal AWS network, ~1-2ms)
2. ALB (Public Subnet)
   ↓ Routes to API Gateway (priority 200 rule: /api/*)
   ↓ (Internal AWS network, ~1-2ms)
3. ECS Fargate - API Gateway (Private Subnet)
   ├─ Validates bid
   ├─ Updates Redis (ElastiCache, same VPC, ~1ms)
   └─ Publishes to NATS (NLB, same VPC, ~1ms)
4. ECS Fargate - NATS (Private Subnet)
   ↓ Publishes event to subject: bid_events.{item_id}
   ↓ (Internal AWS network, ~1ms)
5. ECS Fargate - Broadcast Service (Private Subnet)
   ├─ Subscribes to NATS: bid_events.*
   ├─ Receives event (~1ms)
   └─ Broadcasts to all WebSocket clients
6. EC2 Test Client
   ↓ Receives WebSocket message
   Total Latency: ~5-10ms (internal AWS network only)
```

### Network Path Breakdown:
```
EC2 → ALB:         ~1-2ms (same VPC, private subnet to public subnet)
ALB → ECS Tasks:   ~1-2ms (same VPC, public subnet to private subnet)
ECS → Redis:       ~1ms   (same VPC, ElastiCache)
ECS → NATS:        ~1ms   (same VPC, NLB)
ECS → ECS:         ~1ms   (same VPC, service-to-service)
Total:             ~5-10ms (all internal AWS network)
```

---

## Scenario 2: Tests Run from Local MacBook (Internet) - SLOWER 🐌

### Architecture Diagram:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Your Local MacBook                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  websocket_fanout_test.py                                │  │
│  │  - Python script                                          │  │
│  │  - Connects via Internet                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────┴─────────┐
                    │   Internet         │
                    │   (~30-50ms)       │
                    └─────────┬─────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    AWS VPC (us-west-2)                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Public Subnets                              │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │  Application Load Balancer (ALB)                  │   │  │
│  │  │  - Public DNS: bidding-system-alb-xxx.elb...     │   │  │
│  │  │  - Internet-facing                                │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Private Subnets                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │ ECS Fargate  │  │ ECS Fargate  │  │ ECS Fargate  │  │  │
│  │  │ API Gateway  │  │ Broadcast    │  │ Archival     │  │  │
│  │  │ (2 tasks)    │  │ Service      │  │ Worker       │  │  │
│  │  │              │  │ (2 tasks)    │  │ (1 task)     │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │  │
│  │                                                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │ ElastiCache  │  │ RDS          │  │ NATS         │  │  │
│  │  │ Redis        │  │ PostgreSQL   │  │ (ECS Fargate)│  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Full Workflow (Local MacBook Test Client):

#### Step 1: Test Client Setup
```
Local MacBook
├─ Python 3 installed
├─ websocket_fanout_test.py script
└─ Connects to: ALB public DNS name (over Internet)
```

#### Step 2: WebSocket Connection Establishment
```
1. Local MacBook
   ↓ HTTP Upgrade Request
   ↓ (Internet routing, ~30-50ms)
   ↓ Geographic distance (your location → us-west-2)
   ↓ ISP routing, AWS edge locations
2. ALB (Public Subnet, Internet-facing)
   ↓ Routes to Broadcast Service (priority 50 rule: /ws/*)
   ↓ (Internal AWS network, ~1-2ms)
3. ECS Fargate - Broadcast Service (Private Subnet)
   ↓ Accepts WebSocket upgrade
   ↓ (Internal AWS network, ~1ms)
4. Connection established
   Total: ~35-55ms latency (Internet + AWS internal)
```

#### Step 3: Bid Placement & Broadcast Flow
```
1. Local MacBook
   ↓ POST /api/v1/items/{id}/bid
   ↓ (Internet routing, ~30-50ms)
2. ALB (Public Subnet)
   ↓ Routes to API Gateway (priority 200 rule: /api/*)
   ↓ (Internal AWS network, ~1-2ms)
3. ECS Fargate - API Gateway (Private Subnet)
   ├─ Validates bid
   ├─ Updates Redis (ElastiCache, same VPC, ~1ms)
   └─ Publishes to NATS (NLB, same VPC, ~1ms)
4. ECS Fargate - NATS (Private Subnet)
   ↓ Publishes event to subject: bid_events.{item_id}
   ↓ (Internal AWS network, ~1ms)
5. ECS Fargate - Broadcast Service (Private Subnet)
   ├─ Subscribes to NATS: bid_events.*
   ├─ Receives event (~1ms)
   └─ Broadcasts to all WebSocket clients
6. Local MacBook
   ↓ Receives WebSocket message
   ↓ (Internet routing, ~30-50ms)
   Total Latency: ~65-110ms (Internet × 2 + AWS internal)
```

### Network Path Breakdown:
```
MacBook → Internet:     ~30-50ms (ISP routing, geographic distance)
Internet → ALB:          ~5-10ms  (AWS edge locations, DNS resolution)
ALB → ECS Tasks:         ~1-2ms   (same VPC, public to private subnet)
ECS → Redis:             ~1ms     (same VPC, ElastiCache)
ECS → NATS:              ~1ms     (same VPC, NLB)
ECS → ECS:               ~1ms     (same VPC, service-to-service)
ECS → ALB:               ~1-2ms   (same VPC, private to public subnet)
ALB → Internet:          ~5-10ms  (AWS edge locations)
Internet → MacBook:      ~30-50ms (ISP routing, geographic distance)
Total:                   ~75-120ms (Internet overhead dominates)
```

---

## Key Differences

| Aspect | EC2 (Same VPC) | Local MacBook (Internet) |
|--------|----------------|--------------------------|
| **Network Type** | Internal AWS network | Internet (public) |
| **Latency (100 conn)** | ~5-10ms | ~35-55ms |
| **Latency (1000 conn)** | ~15-20ms | ~65-110ms |
| **Geographic Distance** | Same region (us-west-2) | Your location → us-west-2 |
| **Routing Hops** | 2-3 (VPC internal) | 10-15+ (Internet routing) |
| **ISP Overhead** | None | Yes (your ISP → AWS) |
| **DNS Resolution** | Internal DNS (~1ms) | Public DNS (~5-10ms) |
| **ALB Processing** | Same | Same |
| **ECS Processing** | Same | Same |

---

## Why Services Run on ECS Fargate (Not EC2)

**ECS Fargate** is AWS's serverless container platform:
- ✅ **No EC2 management**: AWS manages the underlying infrastructure
- ✅ **Auto-scaling**: Automatically scales based on demand
- ✅ **Cost-effective**: Pay only for running containers (no idle EC2 costs)
- ✅ **Security**: Containers run in private subnets, isolated from internet
- ✅ **Simplified deployment**: Just push Docker images, ECS handles the rest

**EC2 instances** are only used for:
- 🧪 **Test clients** (running load tests)
- 🔧 **Bastion hosts** (for SSH access)
- 📊 **Monitoring/logging** (optional)

---

## Summary

**Your Current Setup:**
- ✅ Services: ECS Fargate (serverless containers)
- ✅ ALB: Public-facing (accepts traffic from internet)
- ✅ Test Client: Local MacBook (via internet) → **Higher latency**

**To Match Original Results:**
- ✅ Services: ECS Fargate (no change needed)
- ✅ ALB: Public-facing (no change needed)
- 🔄 Test Client: EC2 instance (same VPC) → **Lower latency**

The **application architecture doesn't change** - only the **test client location** affects latency measurements.







