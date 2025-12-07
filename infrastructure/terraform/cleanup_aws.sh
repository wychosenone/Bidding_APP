#!/bin/bash
set -e
REGION="us-west-2"
PROJECT="bidding-system"

echo "=== Starting AWS Resource Cleanup ==="

# 1. Delete ECS Services
echo "Step 1: Deleting ECS services..."
CLUSTER="${PROJECT}-cluster"
for service in $(aws ecs list-services --cluster $CLUSTER --region $REGION --query 'serviceArns[]' --output text 2>/dev/null || echo ""); do
    if [ -n "$service" ]; then
        echo "  Stopping service: $service"
        aws ecs update-service --cluster $CLUSTER --service $service --desired-count 0 --region $REGION --no-cli-pager 2>/dev/null || true
        aws ecs delete-service --cluster $CLUSTER --service $service --force --region $REGION --no-cli-pager 2>/dev/null || true
    fi
done

# 2. Delete ECS Cluster
echo "Step 2: Deleting ECS cluster..."
aws ecs delete-cluster --cluster $CLUSTER --region $REGION --no-cli-pager 2>/dev/null || echo "  Cluster not found or already deleted"

# 3. Delete Load Balancers
echo "Step 3: Deleting load balancers..."
for lb in $(aws elbv2 describe-load-balancers --region $REGION --query "LoadBalancers[?contains(LoadBalancerName, '${PROJECT}')].LoadBalancerArn" --output text 2>/dev/null || echo ""); do
    if [ -n "$lb" ]; then
        echo "  Deleting LB: $lb"
        # First delete listeners
        for listener in $(aws elbv2 describe-listeners --load-balancer-arn $lb --region $REGION --query 'Listeners[].ListenerArn' --output text 2>/dev/null || echo ""); do
            aws elbv2 delete-listener --listener-arn $listener --region $REGION --no-cli-pager 2>/dev/null || true
        done
        aws elbv2 delete-load-balancer --load-balancer-arn $lb --region $REGION --no-cli-pager 2>/dev/null || true
    fi
done

# 4. Delete Target Groups
echo "Step 4: Deleting target groups..."
for tg in $(aws elbv2 describe-target-groups --region $REGION --query "TargetGroups[?contains(TargetGroupName, '${PROJECT}')].TargetGroupArn" --output text 2>/dev/null || echo ""); do
    if [ -n "$tg" ]; then
        echo "  Deleting TG: $tg"
        aws elbv2 delete-target-group --target-group-arn $tg --region $REGION --no-cli-pager 2>/dev/null || true
    fi
done

# 5. Delete RDS
echo "Step 5: Deleting RDS instance..."
aws rds delete-db-instance --db-instance-identifier ${PROJECT}-postgres --skip-final-snapshot --delete-automated-backups --region $REGION --no-cli-pager 2>/dev/null || echo "  RDS not found or already deleted"

# 6. Delete ElastiCache
echo "Step 6: Deleting ElastiCache cluster..."
aws elasticache delete-cache-cluster --cache-cluster-id ${PROJECT}-redis --region $REGION --no-cli-pager 2>/dev/null || echo "  ElastiCache not found or already deleted"

# 7. Delete DB Subnet Group
echo "Step 7: Deleting DB subnet group..."
aws rds delete-db-subnet-group --db-subnet-group-name ${PROJECT}-db-subnet-group --region $REGION --no-cli-pager 2>/dev/null || echo "  DB subnet group not found"

# 8. Delete ElastiCache Subnet Group
echo "Step 8: Deleting ElastiCache subnet group..."
aws elasticache delete-cache-subnet-group --cache-subnet-group-name ${PROJECT}-redis-subnet --region $REGION --no-cli-pager 2>/dev/null || echo "  ElastiCache subnet group not found"

echo "=== Waiting for resources to be deleted (60 seconds)... ==="
sleep 60

# 9. Delete Security Groups (except default)
echo "Step 9: Deleting security groups..."
for vpc in $(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*bidding*" --region $REGION --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo ""); do
    if [ -n "$vpc" ]; then
        for sg in $(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc" --region $REGION --query "SecurityGroups[?GroupName!='default'].GroupId" --output text 2>/dev/null || echo ""); do
            echo "  Deleting SG: $sg"
            aws ec2 delete-security-group --group-id $sg --region $REGION --no-cli-pager 2>/dev/null || true
        done
    fi
done

# 10. Delete NAT Gateways
echo "Step 10: Deleting NAT gateways..."
for nat in $(aws ec2 describe-nat-gateways --filter "Name=tag:Name,Values=*bidding*" --region $REGION --query 'NatGateways[?State!=`deleted`].NatGatewayId' --output text 2>/dev/null || echo ""); do
    if [ -n "$nat" ]; then
        echo "  Deleting NAT: $nat"
        aws ec2 delete-nat-gateway --nat-gateway-id $nat --region $REGION --no-cli-pager 2>/dev/null || true
    fi
done

echo "=== Waiting for NAT gateways to be deleted (60 seconds)... ==="
sleep 60

# 11. Release Elastic IPs
echo "Step 11: Releasing Elastic IPs..."
for eip in $(aws ec2 describe-addresses --region $REGION --query "Addresses[?Tags[?Key=='Name' && contains(Value, 'bidding')]].AllocationId" --output text 2>/dev/null || echo ""); do
    if [ -n "$eip" ]; then
        echo "  Releasing EIP: $eip"
        aws ec2 release-address --allocation-id $eip --region $REGION --no-cli-pager 2>/dev/null || true
    fi
done

# 12. Delete Internet Gateways
echo "Step 12: Deleting internet gateways..."
for vpc in $(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*bidding*" --region $REGION --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo ""); do
    if [ -n "$vpc" ]; then
        for igw in $(aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$vpc" --region $REGION --query 'InternetGateways[].InternetGatewayId' --output text 2>/dev/null || echo ""); do
            echo "  Detaching and deleting IGW: $igw from VPC: $vpc"
            aws ec2 detach-internet-gateway --internet-gateway-id $igw --vpc-id $vpc --region $REGION --no-cli-pager 2>/dev/null || true
            aws ec2 delete-internet-gateway --internet-gateway-id $igw --region $REGION --no-cli-pager 2>/dev/null || true
        done
    fi
done

# 13. Delete Subnets
echo "Step 13: Deleting subnets..."
for vpc in $(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*bidding*" --region $REGION --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo ""); do
    if [ -n "$vpc" ]; then
        for subnet in $(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" --region $REGION --query 'Subnets[].SubnetId' --output text 2>/dev/null || echo ""); do
            echo "  Deleting subnet: $subnet"
            aws ec2 delete-subnet --subnet-id $subnet --region $REGION --no-cli-pager 2>/dev/null || true
        done
    fi
done

# 14. Delete Route Tables (except main)
echo "Step 14: Deleting route tables..."
for vpc in $(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*bidding*" --region $REGION --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo ""); do
    if [ -n "$vpc" ]; then
        for rt in $(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc" --region $REGION --query "RouteTables[?Associations[0].Main!=\`true\`].RouteTableId" --output text 2>/dev/null || echo ""); do
            echo "  Deleting route table: $rt"
            aws ec2 delete-route-table --route-table-id $rt --region $REGION --no-cli-pager 2>/dev/null || true
        done
    fi
done

# 15. Delete VPCs
echo "Step 15: Deleting VPCs..."
for vpc in $(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*bidding*" --region $REGION --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo ""); do
    if [ -n "$vpc" ]; then
        echo "  Deleting VPC: $vpc"
        aws ec2 delete-vpc --vpc-id $vpc --region $REGION --no-cli-pager 2>/dev/null || true
    fi
done

# 16. Delete CloudWatch Log Groups
echo "Step 16: Deleting CloudWatch log groups..."
for lg in $(aws logs describe-log-groups --log-group-name-prefix "/ecs/${PROJECT}" --region $REGION --query 'logGroups[].logGroupName' --output text 2>/dev/null || echo ""); do
    if [ -n "$lg" ]; then
        echo "  Deleting log group: $lg"
        aws logs delete-log-group --log-group-name "$lg" --region $REGION --no-cli-pager 2>/dev/null || true
    fi
done

# 17. Delete ECR Repositories
echo "Step 17: Deleting ECR repositories..."
for repo in api-gateway broadcast-service archival-worker; do
    echo "  Deleting ECR repo: ${PROJECT}-${repo}"
    aws ecr delete-repository --repository-name "${PROJECT}-${repo}" --force --region $REGION --no-cli-pager 2>/dev/null || true
done

echo ""
echo "=== Cleanup Complete ==="
echo "Note: Some resources may take additional time to fully delete."
echo "Run 'terraform init' and 'terraform apply' to redeploy."
