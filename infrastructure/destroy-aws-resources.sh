#!/bin/bash

# Destroy AWS Resources Script
# This will delete all running resources to avoid charges
# But preserve configurations (VPC, Security Groups, ECR images, Task Definitions)
# for easy redeployment later

set -e

REGION="us-west-2"
CLUSTER="bidding-system-cluster"

echo "========================================="
echo "AWS Resource Destruction Script"
echo "========================================="
echo ""
echo "This will delete:"
echo "  - 4 ECS Services"
echo "  - 2 Load Balancers (ALB + NLB)"
echo "  - ElastiCache Redis"
echo "  - RDS PostgreSQL"
echo "  - 2 NAT Gateways"
echo ""
echo "This will PRESERVE (for redeployment):"
echo "  - VPC and Subnets"
echo "  - Security Groups"
echo "  - ECR Docker Images"
echo "  - ECS Task Definitions"
echo "  - ECS Cluster"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Starting resource deletion..."
echo ""

# ============================================
# Step 1: Scale down ECS services to 0
# ============================================
echo "[1/8] Scaling down ECS services to 0..."

services=(
    "bidding-system-api-gateway"
    "bidding-system-broadcast-service"
    "bidding-system-archival-worker"
    "bidding-system-nats"
)

for service in "${services[@]}"; do
    echo "  Scaling down $service..."
    aws ecs update-service \
        --cluster $CLUSTER \
        --service $service \
        --desired-count 0 \
        --region $REGION \
        --no-cli-pager > /dev/null 2>&1 || echo "  (Service may not exist, continuing...)"
done

echo "  Waiting 30 seconds for tasks to stop..."
sleep 30

# ============================================
# Step 2: Delete ECS services
# ============================================
echo ""
echo "[2/8] Deleting ECS services..."

for service in "${services[@]}"; do
    echo "  Deleting $service..."
    aws ecs delete-service \
        --cluster $CLUSTER \
        --service $service \
        --force \
        --region $REGION \
        --no-cli-pager > /dev/null 2>&1 || echo "  (Service may not exist, continuing...)"
done

echo "  Waiting 30 seconds for services to delete..."
sleep 30

# ============================================
# Step 3: Delete Application Load Balancer
# ============================================
echo ""
echo "[3/8] Deleting Application Load Balancer..."

ALB_ARN=$(aws elbv2 describe-load-balancers \
    --region $REGION \
    --query 'LoadBalancers[?LoadBalancerName==`bidding-system-alb`].LoadBalancerArn' \
    --output text)

if [ -n "$ALB_ARN" ]; then
    echo "  Deleting ALB: bidding-system-alb..."
    aws elbv2 delete-load-balancer \
        --load-balancer-arn $ALB_ARN \
        --region $REGION \
        --no-cli-pager
    echo "  ALB deleted."
else
    echo "  ALB not found, skipping..."
fi

# ============================================
# Step 4: Delete Network Load Balancer
# ============================================
echo ""
echo "[4/8] Deleting Network Load Balancer..."

NLB_ARN=$(aws elbv2 describe-load-balancers \
    --region $REGION \
    --query 'LoadBalancers[?LoadBalancerName==`bidding-system-nats-nlb`].LoadBalancerArn' \
    --output text)

if [ -n "$NLB_ARN" ]; then
    echo "  Deleting NLB: bidding-system-nats-nlb..."
    aws elbv2 delete-load-balancer \
        --load-balancer-arn $NLB_ARN \
        --region $REGION \
        --no-cli-pager
    echo "  NLB deleted."
else
    echo "  NLB not found, skipping..."
fi

echo "  Waiting 60 seconds for load balancers to delete..."
sleep 60

# ============================================
# Step 5: Delete Target Groups
# ============================================
echo ""
echo "[5/8] Deleting Target Groups..."

TG_ARNS=$(aws elbv2 describe-target-groups \
    --region $REGION \
    --query 'TargetGroups[?contains(TargetGroupName, `bidding`)].TargetGroupArn' \
    --output text)

if [ -n "$TG_ARNS" ]; then
    for tg_arn in $TG_ARNS; do
        echo "  Deleting target group: $tg_arn..."
        aws elbv2 delete-target-group \
            --target-group-arn $tg_arn \
            --region $REGION \
            --no-cli-pager || echo "  (May already be deleted)"
    done
else
    echo "  No target groups found, skipping..."
fi

# ============================================
# Step 6: Delete ElastiCache Redis
# ============================================
echo ""
echo "[6/8] Deleting ElastiCache Redis..."

echo "  Deleting bidding-system-redis..."
aws elasticache delete-cache-cluster \
    --cache-cluster-id bidding-system-redis \
    --region $REGION \
    --no-cli-pager || echo "  (Redis cluster may not exist, continuing...)"

echo "  Redis deletion initiated (will take 5-10 minutes in background)..."

# ============================================
# Step 7: Delete RDS PostgreSQL
# ============================================
echo ""
echo "[7/8] Deleting RDS PostgreSQL..."

echo "  Deleting bidding-system-postgres (skipping final snapshot)..."
aws rds delete-db-instance \
    --db-instance-identifier bidding-system-postgres \
    --skip-final-snapshot \
    --region $REGION \
    --no-cli-pager || echo "  (RDS instance may not exist, continuing...)"

echo "  RDS deletion initiated (will take 5-10 minutes in background)..."

# ============================================
# Step 8: Delete NAT Gateways (EXPENSIVE!)
# ============================================
echo ""
echo "[8/8] Deleting NAT Gateways..."

NAT_IDS=$(aws ec2 describe-nat-gateways \
    --region $REGION \
    --filter "Name=state,Values=available" "Name=vpc-id,Values=vpc-0a7410acc5126e9dd" \
    --query 'NatGateways[].NatGatewayId' \
    --output text)

if [ -n "$NAT_IDS" ]; then
    for nat_id in $NAT_IDS; do
        echo "  Deleting NAT Gateway: $nat_id..."
        aws ec2 delete-nat-gateway \
            --nat-gateway-id $nat_id \
            --region $REGION \
            --no-cli-pager
    done
    echo "  NAT Gateway deletion initiated (will take a few minutes)..."
else
    echo "  No NAT Gateways found, skipping..."
fi

# ============================================
# Summary
# ============================================
echo ""
echo "========================================="
echo "Resource Deletion Complete!"
echo "========================================="
echo ""
echo "✅ Deleted:"
echo "  - ECS Services (stopped and removed)"
echo "  - Application Load Balancer"
echo "  - Network Load Balancer"
echo "  - Target Groups"
echo "  - ElastiCache Redis (deleting...)"
echo "  - RDS PostgreSQL (deleting...)"
echo "  - NAT Gateways (deleting...)"
echo ""
echo "✅ Preserved (for redeployment):"
echo "  - VPC and Subnets"
echo "  - Security Groups"
echo "  - ECR Docker Images"
echo "  - ECS Task Definitions"
echo "  - ECS Cluster"
echo "  - Internet Gateway"
echo "  - Route Tables"
echo ""
echo "⚠️  Note: ElastiCache, RDS, and NAT Gateways will take"
echo "   5-10 minutes to fully delete in the background."
echo ""
echo "💰 Cost Savings: ~$228/month"
echo ""
echo "📝 To redeploy later, see: infrastructure/redeploy-guide.md"
echo ""
