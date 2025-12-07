# Bidding System - AWS Infrastructure with Terraform

This directory contains Terraform configuration for deploying the Real-Time Bidding System to AWS.

## Architecture Overview

The infrastructure consists of:

- **VPC** with public and private subnets across 2 availability zones
- **ElastiCache (Redis)** - In-memory data store for real-time bidding
- **RDS (PostgreSQL)** - Persistent database for archival storage
- **ECS Fargate** - Container orchestration for services
- **Application Load Balancer** - HTTP/WebSocket traffic routing
- **ECR** - Container image registry
- **Service Discovery** - Internal service-to-service communication

## Services Deployed

1. **API Gateway** - HTTP API for bid placement (port 8080)
2. **Broadcast Service** - WebSocket server for real-time updates (port 8081)
3. **Archival Worker** - Background worker for database persistence
4. **NATS** - Message queue for event streaming

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials
3. **Terraform** >= 1.0 installed
4. **Docker** for building images

## Deployment Steps

### Step 1: Initialize Terraform

```bash
cd infrastructure/terraform

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your settings
# IMPORTANT: Change db_password!
nano terraform.tfvars

# Initialize Terraform
terraform init
```

### Step 2: Plan Infrastructure

```bash
# Review what will be created
terraform plan

# Expected resources: ~50 resources
```

### Step 3: Deploy Infrastructure

```bash
# Deploy to AWS (takes ~15-20 minutes)
terraform apply

# Type 'yes' when prompted
```

### Step 4: Build and Push Docker Images

After infrastructure is created, Terraform will output ECR repository URLs.

```bash
# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-east-1"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push images (from project root)
cd ../..

# API Gateway
docker build -t bidding-system/api-gateway:latest \
  -f infrastructure/docker/Dockerfile.api-gateway .
docker tag bidding-system/api-gateway:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/bidding-system/api-gateway:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/bidding-system/api-gateway:latest

# Broadcast Service
docker build -t bidding-system/broadcast-service:latest \
  -f infrastructure/docker/Dockerfile.broadcast-service .
docker tag bidding-system/broadcast-service:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/bidding-system/broadcast-service:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/bidding-system/broadcast-service:latest

# Archival Worker
docker build -t bidding-system/archival-worker:latest \
  -f infrastructure/docker/Dockerfile.archival-worker .
docker tag bidding-system/archival-worker:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/bidding-system/archival-worker:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/bidding-system/archival-worker:latest
```

### Step 5: Update ECS Services

```bash
# Force new deployment with pushed images
aws ecs update-service \
  --cluster bidding-system-cluster \
  --service bidding-system-api-gateway \
  --force-new-deployment \
  --region $AWS_REGION

aws ecs update-service \
  --cluster bidding-system-cluster \
  --service bidding-system-broadcast-service \
  --force-new-deployment \
  --region $AWS_REGION

aws ecs update-service \
  --cluster bidding-system-cluster \
  --service bidding-system-archival-worker \
  --force-new-deployment \
  --region $AWS_REGION
```

### Step 6: Initialize Database Schema

The archival worker will automatically create database tables on first run.
To verify:

```bash
# Get RDS endpoint from Terraform output
terraform output rds_endpoint

# Connect using psql (if installed)
psql -h <RDS_ENDPOINT> -U bidding -d bidding
# Password: (from terraform.tfvars)

# Verify tables
\dt
```

### Step 7: Test the Deployment

```bash
# Get ALB URL
ALB_URL=$(terraform output -raw alb_url)

# Health check
curl $ALB_URL/health

# Place a test bid
curl -X POST "$ALB_URL/api/v1/items/test_item/bid" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "amount": 100.00}'

# Get item status
curl "$ALB_URL/api/v1/items/test_item"
```

## Running Load Tests

### From Local Machine

```bash
cd load-tests

# Test with Lua strategy
BID_STRATEGY=lua locust -f locustfile.py \
  --headless \
  -u 1000 \
  -r 100 \
  -t 60s \
  ContendedItemBidder \
  --host=$ALB_URL

# Test with Optimistic strategy
BID_STRATEGY=optimistic locust -f locustfile.py \
  --headless \
  -u 1000 \
  -r 100 \
  -t 60s \
  ContendedItemBidder \
  --host=$ALB_URL
```

### Distributed Load Testing (for higher scale)

For 5000-10000 concurrent users, deploy Locust in distributed mode on EC2:

1. Launch EC2 instances (t3.large recommended)
2. Install Locust on all instances
3. Run master on one instance
4. Run workers on other instances pointing to master

## Monitoring

### CloudWatch Logs

```bash
# View logs for each service
aws logs tail /ecs/bidding-system/api-gateway --follow
aws logs tail /ecs/bidding-system/broadcast-service --follow
aws logs tail /ecs/bidding-system/archival-worker --follow
```

### ECS Service Status

```bash
# Check service health
aws ecs describe-services \
  --cluster bidding-system-cluster \
  --services bidding-system-api-gateway bidding-system-broadcast-service \
  --region $AWS_REGION
```

### Performance Metrics

Access CloudWatch dashboards in AWS Console:
- ECS Container Insights
- RDS Performance Insights
- ElastiCache metrics

## Cost Estimation

For development/testing configuration:
- ElastiCache (t3.micro): ~$12/month
- RDS (t3.micro): ~$15/month
- ECS Fargate (5 tasks): ~$35/month
- ALB: ~$20/month
- Data transfer: ~$10/month
- **Total: ~$92/month**

For production configuration (recommended):
- ElastiCache (r6g.large with replication): ~$200/month
- RDS (r6g.large Multi-AZ): ~$300/month
- ECS Fargate (10+ tasks): ~$150/month
- ALB: ~$20/month
- Data transfer: ~$50/month
- **Total: ~$720/month**

## Cleanup

To destroy all infrastructure:

```bash
# Careful! This will delete everything
terraform destroy

# Type 'yes' when prompted
```

## Troubleshooting

### ECS Tasks Not Starting

1. Check CloudWatch logs for error messages
2. Verify ECR images were pushed successfully
3. Check security group rules allow traffic
4. Verify ENI availability in subnets

### Cannot Connect to RDS

1. Check security group allows traffic from ECS tasks
2. Verify RDS is in private subnet
3. Check POSTGRES_URL environment variable format

### Redis Connection Errors

1. Verify ElastiCache endpoint in environment variables
2. Check security group rules
3. Confirm ElastiCache is in private subnet

## File Structure

```
terraform/
├── main.tf               # Provider and base configuration
├── variables.tf          # Input variables
├── outputs.tf            # Output values
├── vpc.tf                # VPC and networking
├── security_groups.tf    # Security group rules
├── elasticache.tf        # Redis cluster
├── rds.tf                # PostgreSQL database
├── ecr.tf                # Container registries
├── ecs.tf                # ECS cluster and services
├── alb.tf                # Load balancer
├── terraform.tfvars      # Your configuration (gitignored)
└── README.md             # This file
```

## Security Best Practices

1. **Change default passwords** in terraform.tfvars
2. **Enable deletion protection** for production RDS
3. **Enable Multi-AZ** for production RDS
4. **Use HTTPS** with ACM certificate for ALB
5. **Enable VPC Flow Logs** for network monitoring
6. **Rotate credentials** regularly
7. **Use AWS Secrets Manager** for sensitive values

## Next Steps

After successful deployment:

1. Run Experiment 1 (Write Contention Test)
2. Run Experiment 2 (WebSocket Fan-Out Test)
3. Run Experiment 3 (Resilience Test)
4. Collect metrics and analyze performance
5. Write final project report
