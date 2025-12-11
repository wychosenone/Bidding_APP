# Running Tests from EC2 Instance (Same VPC)

This guide explains how to run Experiment 2 tests from an EC2 instance in the same AWS VPC to get accurate latency measurements (matching original results).

## Why Run from EC2?

- **Lower Latency**: Tests run from within AWS VPC have ~1-5ms network latency vs 30-50ms+ from internet
- **Accurate Results**: Matches production-like conditions (internal AWS network)
- **Consistent**: Eliminates internet routing variability

## Step 1: Launch EC2 Instance

### Using AWS Console:

1. Go to EC2 → Launch Instance
2. **Name**: `bidding-test-client`
3. **AMI**: Amazon Linux 2023 (or Ubuntu 22.04)
4. **Instance Type**: `t3.micro` or `t3.small` (sufficient for load testing)
5. **Key Pair**: Create or select an existing key pair
6. **Network Settings**:
   - **VPC**: Select the same VPC as your ECS cluster
     - VPC ID: Check Terraform outputs: `terraform output vpc_id`
   - **Subnet**: Select a **private subnet** (same as ECS tasks)
   - **Auto-assign Public IP**: **No** (we'll use NAT Gateway or bastion)
   - **Security Group**: Create new or use existing
     - **Inbound Rules**: 
       - SSH (port 22) from your IP
       - Or use Session Manager (no SSH needed)

### Using AWS CLI:

```bash
# Get VPC and subnet IDs from Terraform
cd infrastructure/terraform
VPC_ID=$(terraform output -raw vpc_id)
SUBNET_ID=$(terraform output -raw private_subnet_ids | jq -r '.[0]')

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name bidding-test-client-sg \
  --description "Security group for load test client" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text \
  --region us-west-2)

# Add SSH rule (replace YOUR_IP with your public IP)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 22 \
  --cidr YOUR_IP/32 \
  --region us-west-2

# Launch instance
aws ec2 run-instances \
  --image-id ami-0c65adc9a5c7b22b9 \
  --instance-type t3.micro \
  --key-name YOUR_KEY_NAME \
  --subnet-id $SUBNET_ID \
  --security-group-ids $SG_ID \
  --associate-public-ip-address \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=bidding-test-client}]' \
  --region us-west-2
```

## Step 2: Connect to EC2 Instance

### Option A: SSH (if public IP or bastion)

```bash
# Get instance public IP
INSTANCE_IP=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=bidding-test-client" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region us-west-2)

# SSH into instance
ssh -i ~/.ssh/your-key.pem ec2-user@$INSTANCE_IP
# For Ubuntu: ssh -i ~/.ssh/your-key.pem ubuntu@$INSTANCE_IP
```

### Option B: AWS Systems Manager Session Manager (Recommended)

No SSH key needed! Works even for instances without public IP.

```bash
# Install Session Manager plugin (one-time, on your local machine)
# macOS:
brew install --cask session-manager-plugin

# Then connect:
aws ssm start-session --target i-INSTANCE_ID --region us-west-2
```

## Step 3: Install Dependencies on EC2

Once connected to EC2 instance:

```bash
# Update system
sudo yum update -y  # Amazon Linux
# OR
sudo apt update && sudo apt upgrade -y  # Ubuntu

# Install Python 3 and pip
sudo yum install -y python3 python3-pip git  # Amazon Linux
# OR
sudo apt install -y python3 python3-pip git  # Ubuntu

# Clone your repository (or upload files)
# Option 1: If repo is on GitHub
git clone https://github.com/yourusername/Bidding_APP.git
cd Bidding_APP

# Option 2: Upload files using SCP
# From your local machine:
# scp -i ~/.ssh/your-key.pem -r load-tests/ ec2-user@$INSTANCE_IP:~/

# Install Python dependencies
cd load-tests
pip3 install --user -r requirements.txt
```

## Step 4: Get Internal ALB DNS Name

The EC2 instance should use the **internal** ALB DNS name (not public), or you can use the private IP.

```bash
# From EC2 instance, get ALB internal DNS
# Option 1: Use Terraform output (from your local machine)
cd infrastructure/terraform
terraform output alb_dns_name

# Option 2: Query AWS from EC2 instance
aws elbv2 describe-load-balancers \
  --names bidding-system-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text \
  --region us-west-2
```

## Step 5: Run Tests from EC2

```bash
# On EC2 instance
cd ~/Bidding_APP/load-tests

# Test with 100 connections (will auto-generate unique item ID)
python3 websocket_fanout_test.py \
  --connections 100 \
  --bids 10 \
  --interval 5 \
  --ws-url "ws://bidding-system-alb-INTERNAL-DNS.us-west-2.elb.amazonaws.com" \
  --api-url "http://bidding-system-alb-INTERNAL-DNS.us-west-2.elb.amazonaws.com" \
  --use-client-time

# Test with 1000 connections
python3 websocket_fanout_test.py \
  --connections 1000 \
  --bids 5 \
  --interval 5 \
  --ws-url "ws://bidding-system-alb-INTERNAL-DNS.us-west-2.elb.amazonaws.com" \
  --api-url "http://bidding-system-alb-INTERNAL-DNS.us-west-2.elb.amazonaws.com" \
  --use-client-time
```

## Step 6: Transfer Results Back (Optional)

```bash
# From your local machine, download results
scp -i ~/.ssh/your-key.pem \
  ec2-user@$INSTANCE_IP:~/Bidding_APP/load-tests/*.csv \
  ./results/
```

## Expected Latency Improvements

Running from EC2 (same VPC) should give you:
- **100 connections**: P99 ~15-20ms (vs 396ms from internet)
- **1,000 connections**: P99 ~50-60ms (vs 188ms from internet)
- **10,000 connections**: P99 ~1000-1100ms (vs 4405ms from internet)

## Troubleshooting

### Can't connect to ALB from EC2

```bash
# Check security group allows traffic
# ALB security group should allow inbound from EC2 security group
# EC2 security group should allow outbound to ALB

# Test connectivity
curl http://bidding-system-alb-INTERNAL-DNS.us-west-2.elb.amazonaws.com/health
```

### No internet access (can't install packages)

If EC2 is in private subnet without NAT Gateway:
- Use Session Manager to connect
- Or temporarily assign public IP
- Or use VPC endpoints for AWS services

### IAM Permissions

EC2 instance needs IAM role with permissions to:
- Describe load balancers (optional, for DNS lookup)
- Access S3 if uploading results (optional)

## Cleanup

```bash
# Terminate EC2 instance when done
aws ec2 terminate-instances \
  --instance-ids i-INSTANCE_ID \
  --region us-west-2
```







