# Final Mastery Report: Real-time Bidding System
## Comparing Local Development (LocalStack) vs Cloud Production (AWS) Deployments

**Course:** CS6650 Building Scalable Distributed Systems
**Student:** Aaron Wang
**Date:** November 29, 2025
**Repository:** https://github.com/aaronwang/bidding-app

---

## 1. Executive Summary

This report analyzes the **same bidding system application** deployed in two different environments:

1. **LocalStack Environment** - Local Docker-based deployment simulating cloud infrastructure
2. **AWS Environment** - Production cloud deployment using managed AWS services

**Key Finding:** LocalStack provides excellent development velocity but produces **misleading performance metrics**. AWS deployment reveals realistic production characteristics essential for capacity planning and SLA definition.

---

## 2. System Architecture

### 2.1 Application Overview

A real-time bidding platform handling high-frequency concurrent bid submissions. The system uses Redis Lua scripts for atomic operations to ensure data consistency under extreme write contention.

### 2.2 Core Components

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| API Gateway | Go + Gorilla Mux | HTTP API, bid validation, Redis operations |
| Redis | Redis 7 + Lua Scripts | Atomic bid storage, concurrency control |
| NATS | NATS JetStream | Async event messaging |
| Broadcast Service | Go + WebSocket | Real-time client notifications |
| Archival Worker | Go | Persist completed bids to PostgreSQL |

### 2.3 Architecture Diagram

```
                         ┌─────────────────┐
                         │  Load Balancer  │
                         │ (Port/ALB+NLB)  │
                         └────────┬────────┘
                                  │
               ┌──────────────────┼──────────────────┐
               ▼                  ▼                  ▼
         ┌──────────┐      ┌──────────┐      ┌──────────────┐
         │   API    │      │   API    │      │  Broadcast   │
         │ Gateway  │      │ Gateway  │      │   Service    │
         └────┬─────┘      └────┬─────┘      └──────┬───────┘
              │                 │                   │
              └────────┬────────┘                   │
                       ▼                            │
                ┌─────────────┐                     │
                │    Redis    │◄────────────────────┘
                │ (Lua Scripts)│
                └──────┬──────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
        ┌──────────┐     ┌──────────┐
        │   NATS   │────▶│ Archival │
        │ JetStream│     │  Worker  │
        └──────────┘     └────┬─────┘
                              ▼
                       ┌──────────┐
                       │PostgreSQL│
                       └──────────┘
```

---

## 3. Deployment Environments

### 3.1 LocalStack Environment

LocalStack provides a local cloud development environment that emulates AWS services. Our deployment uses Docker Compose with the LocalStack configuration:

```yaml
# docker-compose.localstack.yml
services:
  localstack:     # LocalStack core (AWS API emulation)
  redis:          # Simulates ElastiCache
  nats:           # Message queue
  api-gateway:    # Application service
  broadcast-service:  # WebSocket service
```

**Configuration:**
- **Container Runtime:** Docker on local machine
- **Redis:** Docker container (`redis:7-alpine`)
- **Network:** Docker bridge network (~0ms latency)
- **Instances:** 1 API Gateway container
- **Cost:** $0/month

### 3.2 AWS Environment

Production deployment using AWS managed services via Terraform:

**Configuration:**
- **Container Runtime:** ECS Fargate (0.5 vCPU, 1GB RAM per task)
- **Redis:** ElastiCache (`cache.t3.micro`)
- **Database:** RDS PostgreSQL (`db.t3.micro`)
- **Load Balancing:** ALB (HTTP) + NLB (NATS)
- **Network:** VPC with 2 AZs, public/private subnets
- **Instances:** 2 API Gateway Fargate tasks
- **Region:** us-west-2
- **Cost:** ~$164/month

### 3.3 Infrastructure Comparison

| Aspect | LocalStack | AWS |
|--------|------------|-----|
| Redis | Docker container | ElastiCache (managed) |
| Compute | Docker container | ECS Fargate (serverless) |
| Load Balancer | Direct port (8080) | ALB + NLB |
| Network Latency | ~0ms | 15-30ms round-trip |
| High Availability | No | Yes (2 AZs) |
| Auto-scaling | No | Yes (ECS Service) |
| Monitoring | Docker stats | CloudWatch + Container Insights |

---

## 4. Experiment Design

### 4.1 Test Objective

Compare the **same application** under identical workloads in both environments to answer:
1. What performance differences exist between local and cloud deployments?
2. Which metrics are meaningful in each environment?
3. When should each deployment type be used?

### 4.2 Test Parameters

| Parameter | Value |
|-----------|-------|
| Test Tool | Locust (Python) |
| Concurrent Users | 100, 500, 1,000, 2,000, 10,000 |
| Duration | 30 seconds per test |
| Workload | All users bid on same item (maximum contention) |
| Metrics | Throughput (RPS), Latency (P50, P95, P99), Errors |

### 4.3 Correctness Verification

Each test verified that:
- Final Redis bid = Maximum submitted bid
- Zero lost updates
- Zero data corruption

---

## 5. Performance Results

### 5.1 Throughput Comparison

| Users | LocalStack RPS | AWS RPS | Difference |
|------:|---------------:|--------:|-----------:|
| 100 | 8,512 | 3,607 | -57.6% |
| 500 | 13,003 | 10,256 | -21.1% |
| 1,000 | 12,762 | 10,737 | -15.9% |
| 2,000 | 11,908 | 11,084 | -6.9% |
| 10,000 | 9,748 | 9,735 | -0.1% |

**Analysis:**
- LocalStack shows **2.4x higher throughput** at low load (100 users) due to zero network latency
- Performance gap **narrows with increased load** as compute becomes the bottleneck
- At 10,000 users, both converge (~9,735 RPS) due to client CPU saturation

### 5.2 Latency Comparison

| Users | LocalStack P50 | AWS P50 | LocalStack P99 | AWS P99 |
|------:|---------------:|--------:|---------------:|--------:|
| 100 | 0ms | 22ms | 9ms | 37ms |
| 500 | 24ms | 40ms | 65ms | 110ms |
| 1,000 | 59ms | 78ms | 160ms | 350ms |
| 2,000 | 120ms | 120ms | 370ms | 740ms |
| 10,000 | 130ms | 480ms | 1,300ms | 3,900ms |

**Analysis:**
- LocalStack P50 latency starts at **0ms** (unrealistic for production)
- AWS adds **15-25ms baseline latency** from network hops
- AWS P99 is **2-3x higher** than LocalStack (realistic tail latency)
- At high load, **queue buildup effects** are visible in both environments

### 5.3 Error Rate & Data Integrity

| Environment | Total Requests | Failures | Data Integrity |
|-------------|---------------:|----------|----------------|
| LocalStack | 1,412,904 | 0 (0.00%) | ✅ 100% |
| AWS | 1,399,464 | 0 (0.00%) | ✅ 100% |

**Both environments achieved zero lost updates**, validating that the Redis Lua script atomic operations work correctly regardless of deployment environment.

### 5.4 Resource Utilization

**LocalStack:**
- API Gateway CPU: Not bottlenecked (Docker container)
- Redis CPU: <10% utilization
- Locust Client CPU: 90%+ (bottleneck)

**AWS:**
- API Gateway CPU: **100%** of allocated 0.5 vCPU (bottleneck identified)
- ElastiCache CPU: 6.41% (not bottleneck)
- ElastiCache Cache Hit Rate: 100%

---

## 6. Key Findings

### 6.1 When to Use Each Environment

| Use Case | LocalStack | AWS | Recommendation |
|----------|:----------:|:---:|----------------|
| Daily development | ✅ | ❌ | LocalStack - fast iteration, zero cost |
| Unit/Integration tests | ✅ | ❌ | LocalStack - CI/CD friendly |
| Functional correctness | ✅ | ✅ | Both work - use LocalStack for speed |
| Performance benchmarking | ❌ | ✅ | AWS - realistic metrics |
| Capacity planning | ❌ | ✅ | AWS - accurate throughput numbers |
| SLA definition | ❌ | ✅ | AWS - realistic latencies |
| Cost estimation | ❌ | ✅ | AWS - actual infrastructure costs |
| HA/DR testing | ❌ | ✅ | AWS - multi-AZ, failure injection |

### 6.2 Which Metrics Are Meaningful

| Metric | LocalStack | AWS | Notes |
|--------|------------|-----|-------|
| **Throughput (RPS)** | Optimistic | Realistic | LocalStack inflated by ~20-50% |
| **P50 Latency** | Invalid | Valid | LocalStack shows 0ms (unrealistic) |
| **P99 Latency** | Underestimated | Valid | AWS 2-3x higher (production-like) |
| **Error Rate** | Valid | Valid | Both accurate for correctness |
| **CPU Utilization** | Limited | Valid | AWS CloudWatch shows real bottlenecks |
| **Memory Usage** | Valid | Valid | Both accurate |
| **Cache Hit Rate** | Valid | Valid | Both accurate |

### 6.3 Critical Insights

**1. Network Latency Dominates Low-Load Performance**
```
LocalStack: Client → Container → Redis → Response = ~0ms
AWS:        Client → ALB → ECS → ElastiCache → Response = 15-25ms
```

**2. Bottleneck Identification**
- LocalStack: Hard to identify real bottlenecks (no network overhead)
- AWS: Clear bottleneck visibility (API Gateway CPU at 100%, Redis at 6%)

**3. Scalability Characteristics**
- LocalStack: Single container, peaks at 500 users then degrades
- AWS: Distributed (2 tasks), maintains throughput with horizontal scaling potential

---

## 7. Conclusions

### 7.1 Summary

| Aspect | LocalStack | AWS |
|--------|------------|-----|
| **Best For** | Development & Testing | Production & Benchmarking |
| **Throughput Accuracy** | Optimistic (+20-50%) | Realistic |
| **Latency Accuracy** | Poor (underestimates) | Accurate |
| **Cost** | Free | ~$164/month |
| **Setup Time** | Minutes | Hours |
| **Production Relevance** | Low | High |

### 7.2 Recommendations

1. **Development Workflow:**
   - Use LocalStack for daily development (fast, free)
   - Run AWS tests before major releases (realistic metrics)

2. **Capacity Planning:**
   - Use AWS throughput numbers with 20% headroom
   - Never use LocalStack numbers for production sizing

3. **SLA Definition:**
   - Base P99 guarantees on AWS metrics only
   - LocalStack P99 underestimates by 2-3x

4. **Cost Optimization:**
   - Current AWS config handles 10K RPS on ~$164/month
   - Scale API Gateway horizontally if needed (Redis has 90%+ headroom)

### 7.3 Lessons Learned

1. **LocalStack is not a performance simulator** - It's a functional AWS emulator for development
2. **Network latency matters** - 15-25ms baseline latency significantly impacts perceived performance
3. **Bottlenecks differ by environment** - LocalStack hides real production bottlenecks
4. **Both environments validate correctness** - Algorithm correctness is environment-independent

---

## 8. Appendix

### 8.1 Repository Structure

```
bidding-app/
├── api-gateway/           # Go HTTP API service
├── broadcast-service/     # WebSocket service
├── archival-worker/       # Database persistence worker
├── shared/                # Shared models and utilities
├── infrastructure/
│   ├── docker/            # LocalStack deployment configs
│   │   ├── docker-compose.yml
│   │   └── docker-compose.localstack.yml
│   └── terraform/         # AWS infrastructure as code
└── load-tests/            # Locust test scripts and results
```

### 8.2 How to Run

**LocalStack Environment:**
```bash
cd infrastructure/docker
docker-compose -f docker-compose.localstack.yml up -d
# API available at http://localhost:8080
```

**AWS Environment:**
```bash
cd infrastructure/terraform
terraform init && terraform apply
# API available at ALB DNS name
```

### 8.3 Test Artifacts

- LocalStack Results: `load-tests/EXPERIMENT_1_COMPLETE_REPORT.md`
- AWS Results: `load-tests/exp1_aws_*.log`
- Comparison Charts: `load-tests/*.png`
- Visualization Scripts: `load-tests/visualize_*.py`

### 8.4 AWS Infrastructure Details

| Resource | Identifier |
|----------|------------|
| ALB | `bidding-system-alb-144071932.us-west-2.elb.amazonaws.com` |
| ElastiCache | `bidding-system-redis.qv5a2n.0001.usw2.cache.amazonaws.com` |
| RDS | `bidding-system-postgres.cafae2v9tyro.us-west-2.rds.amazonaws.com` |

---

*Report generated for CS6650 Final Mastery Assignment*
