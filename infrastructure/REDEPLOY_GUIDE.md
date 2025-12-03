# Bidding App 重新部署指南

本指南记录了如何重新部署 Bidding App 到 AWS。

## 当前部署配置快照

### AWS 账户信息
- **Account ID:** 661658682907
- **Region:** us-west-2
- **Environment:** dev

### 部署的资源清单
| 资源类型 | 资源名称 | 配置 |
|---------|---------|------|
| ECS Cluster | bidding-system-cluster | Fargate |
| ECS Service | api-gateway | 2 tasks, 512 CPU, 1024 MB |
| ECS Service | broadcast-service | 2 tasks, 512 CPU, 1024 MB |
| ECS Service | archival-worker | 1 task, 256 CPU, 512 MB |
| ECS Service | nats | 1 task, 256 CPU, 512 MB |
| ElastiCache | Redis | cache.t3.micro, 1 node |
| RDS | PostgreSQL | db.t3.micro, 20 GB |
| ALB | API Gateway | HTTP:80 |
| NLB | NATS | TCP:4222 |
| ECR | 3 repositories | api-gateway, broadcast-service, archival-worker |
| VPC | 10.0.0.0/16 | 2 AZs, 2 NAT Gateways |

---

## 重新部署步骤

### 步骤 1: 配置 AWS 凭证

```bash
# 方法 1: AWS Learner Lab
# 从 Learner Lab 复制凭证到 ~/.aws/credentials

# 方法 2: 环境变量
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_SESSION_TOKEN="your-session-token"  # Learner Lab 需要
export AWS_DEFAULT_REGION="us-west-2"

# 验证凭证
aws sts get-caller-identity
```

### 步骤 2: 初始化 Terraform

```bash
cd infrastructure/terraform

# 初始化 Terraform (下载 providers)
terraform init

# 检查配置
terraform validate
```

### 步骤 3: 检查部署计划

```bash
# 查看将要创建的资源
terraform plan -out=tfplan

# 重要: 仔细检查输出，确保没有意外的更改
```

### 步骤 4: 部署基础设施

```bash
# 应用部署计划
terraform apply tfplan

# 或者直接部署 (会再次提示确认)
terraform apply
```

### 步骤 5: 构建并推送 Docker 镜像

```bash
# 获取 ECR 登录
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 661658682907.dkr.ecr.us-west-2.amazonaws.com

# 构建镜像
cd ../../api-gateway
docker build -t bidding-system/api-gateway .

cd ../broadcast-service
docker build -t bidding-system/broadcast-service .

cd ../archival-worker
docker build -t bidding-system/archival-worker .

# 标记镜像
docker tag bidding-system/api-gateway:latest 661658682907.dkr.ecr.us-west-2.amazonaws.com/bidding-system/api-gateway:latest
docker tag bidding-system/broadcast-service:latest 661658682907.dkr.ecr.us-west-2.amazonaws.com/bidding-system/broadcast-service:latest
docker tag bidding-system/archival-worker:latest 661658682907.dkr.ecr.us-west-2.amazonaws.com/bidding-system/archival-worker:latest

# 推送镜像
docker push 661658682907.dkr.ecr.us-west-2.amazonaws.com/bidding-system/api-gateway:latest
docker push 661658682907.dkr.ecr.us-west-2.amazonaws.com/bidding-system/broadcast-service:latest
docker push 661658682907.dkr.ecr.us-west-2.amazonaws.com/bidding-system/archival-worker:latest
```

### 步骤 6: 强制更新 ECS 服务

```bash
# 强制重新部署以拉取新镜像
aws ecs update-service --cluster bidding-system-cluster --service api-gateway --force-new-deployment
aws ecs update-service --cluster bidding-system-cluster --service broadcast-service --force-new-deployment
aws ecs update-service --cluster bidding-system-cluster --service archival-worker --force-new-deployment
```

### 步骤 7: 验证部署

```bash
# 获取 ALB DNS
terraform output alb_dns_name

# 测试 API
curl http://<ALB_DNS>/health

# 查看 ECS 服务状态
aws ecs describe-services --cluster bidding-system-cluster --services api-gateway broadcast-service archival-worker
```

---

## 销毁资源

```bash
cd infrastructure/terraform

# 查看将要销毁的资源
terraform plan -destroy

# 销毁所有资源
terraform destroy

# 确认输入 "yes"
```

---

## 重要文件清单

确保以下文件存在且正确:

| 文件 | 用途 | 状态 |
|------|------|------|
| `terraform.tfvars` | 部署变量配置 | ✅ 已保存 |
| `terraform.tfstate` | Terraform 状态 | ⚠️ 销毁后会清空 |
| `ecs-simple.tf` | ECS 服务定义 | ✅ 已保存 |
| `variables.tf` | 变量定义 | ✅ 已保存 |
| `vpc.tf` | VPC 配置 | ✅ 已保存 |
| `elasticache.tf` | Redis 配置 | ✅ 已保存 |
| `rds.tf` | PostgreSQL 配置 | ✅ 已保存 |

---

## 配置备份

### terraform.tfvars 内容
```hcl
aws_region  = "us-west-2"
environment = "dev"
project_name = "bidding-system"

vpc_cidr = "10.0.0.0/16"
availability_zones_count = 2

redis_node_type = "cache.t3.micro"
redis_num_cache_nodes = 1

db_instance_class = "db.t3.micro"
db_name = "bidding"
db_username = "bidding"
db_password = "BiddingApp2024!SecurePass"
db_allocated_storage = 20

api_gateway_cpu = 512
api_gateway_memory = 1024
api_gateway_desired_count = 2

broadcast_service_cpu = 512
broadcast_service_memory = 1024
broadcast_service_desired_count = 2

archival_worker_cpu = 256
archival_worker_memory = 512
archival_worker_desired_count = 1

nats_cpu = 256
nats_memory = 512
```

---

## 估计费用

| 资源 | 每小时费用 | 每月费用 (预估) |
|------|-----------|----------------|
| ECS Fargate (6 tasks) | ~$0.08 | ~$58 |
| NAT Gateway (2) | ~$0.09 | ~$65 |
| ALB | ~$0.02 | ~$16 |
| ElastiCache (t3.micro) | ~$0.02 | ~$12 |
| RDS (t3.micro) | ~$0.02 | ~$12 |
| **总计** | **~$0.23** | **~$165** |

**提示:** NAT Gateway 是最大的费用来源。如果不需要私有子网，可以考虑使用公共子网部署以节省费用。

---

*最后更新: 2025-11-30*
