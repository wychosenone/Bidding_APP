# AWS 重新部署指南

当你准备好继续开发时，使用本指南快速恢复所有AWS资源。

## 前提条件

确保你仍然有：
- ✅ VPC: `vpc-0a7410acc5126e9dd`
- ✅ 安全组（在VPC中保留）
- ✅ 子网（public + private）
- ✅ ECR镜像（在ECR仓库中保留）
- ✅ ECS任务定义
- ✅ ECS集群: `bidding-system-cluster`

---

## 重新部署步骤

### 选项A：完整部署（包括NAT Gateway）

如果你需要私有子网访问互联网（例如拉取Docker镜像）：

```bash
cd /Users/aaronwang/workspace/Bidding_APP/infrastructure/terraform

# 1. 重新创建所有资源
terraform apply

# 2. 等待资源创建（约10-15分钟）

# 3. 获取新的负载均衡器URL
aws elbv2 describe-load-balancers \
    --region us-west-2 \
    --query 'LoadBalancers[?LoadBalancerName==`bidding-system-alb`].DNSName' \
    --output text

# 4. 更新load-tests中的URL并测试
```

**费用估算：~$228/月**

---

### 选项B：低成本部署（无NAT Gateway）

如果你可以使用公有子网（节省$64/月）：

#### 步骤1：创建ElastiCache Redis

```bash
# 创建Redis集群（使用公有子网）
aws elasticache create-cache-cluster \
    --cache-cluster-id bidding-system-redis \
    --engine redis \
    --cache-node-type cache.t3.micro \
    --num-cache-nodes 1 \
    --region us-west-2 \
    --security-group-ids sg-XXXXXXXXX \
    --preferred-availability-zone us-west-2a

# 等待Redis可用（5-10分钟）
aws elasticache describe-cache-clusters \
    --cache-cluster-id bidding-system-redis \
    --region us-west-2 \
    --query 'CacheClusters[0].CacheClusterStatus'
```

#### 步骤2：创建RDS PostgreSQL

```bash
# 创建PostgreSQL数据库
aws rds create-db-instance \
    --db-instance-identifier bidding-system-postgres \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username bidding \
    --master-user-password YourSecurePassword123 \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-XXXXXXXXX \
    --db-subnet-group-name your-db-subnet-group \
    --region us-west-2

# 等待RDS可用（5-10分钟）
aws rds describe-db-instances \
    --db-instance-identifier bidding-system-postgres \
    --region us-west-2 \
    --query 'DBInstances[0].DBInstanceStatus'
```

#### 步骤3：获取新的Endpoint

```bash
# 获取Redis endpoint
REDIS_ENDPOINT=$(aws elasticache describe-cache-clusters \
    --cache-cluster-id bidding-system-redis \
    --show-cache-node-info \
    --region us-west-2 \
    --query 'CacheClusters[0].CacheNodes[0].Endpoint.Address' \
    --output text)

echo "Redis Endpoint: $REDIS_ENDPOINT:6379"

# 获取PostgreSQL endpoint
POSTGRES_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier bidding-system-postgres \
    --region us-west-2 \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)

echo "PostgreSQL Endpoint: $POSTGRES_ENDPOINT:5432"
```

#### 步骤4：更新ECS Task Definitions

更新以下文件中的endpoint：

**api-gateway-task-def.json:**
```json
{
  "name": "REDIS_ADDR",
  "value": "<REDIS_ENDPOINT>:6379"
}
```

**broadcast-service-task-def.json:**
```json
{
  "name": "REDIS_ADDR",
  "value": "<REDIS_ENDPOINT>:6379"
}
```

**archival-worker-task-def.json:**
```json
{
  "name": "POSTGRES_URL",
  "value": "postgres://bidding:YourPassword@<POSTGRES_ENDPOINT>:5432/bidding?sslmode=disable"
}
```

#### 步骤5：注册新的Task Definitions

```bash
cd /Users/aaronwang/workspace/Bidding_APP

# 注册更新后的task definitions
aws ecs register-task-definition \
    --cli-input-json file://infrastructure/ecs/api-gateway-task-def.json \
    --region us-west-2

aws ecs register-task-definition \
    --cli-input-json file://infrastructure/ecs/broadcast-service-task-def.json \
    --region us-west-2

aws ecs register-task-definition \
    --cli-input-json file://infrastructure/ecs/archival-worker-task-def.json \
    --region us-west-2

aws ecs register-task-definition \
    --cli-input-json file://infrastructure/ecs/nats-task-def.json \
    --region us-west-2
```

#### 步骤6：创建负载均衡器和目标组

参考之前的Terraform配置或使用控制台创建：
- Application Load Balancer (ALB)
- Network Load Balancer (NLB) for NATS
- Target Groups

#### 步骤7：创建ECS服务

```bash
# 创建API Gateway服务
aws ecs create-service \
    --cluster bidding-system-cluster \
    --service-name bidding-system-api-gateway \
    --task-definition bidding-system-api-gateway:LATEST_VERSION \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-XXX],securityGroups=[sg-XXX],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=api-gateway,containerPort=8080" \
    --region us-west-2

# 重复以上步骤创建其他服务...
```

**费用估算：~$164/月（省$64）**

---

## 选项C：仅本地开发（完全免费）

如果只需要本地测试：

```bash
cd /Users/aaronwang/workspace/Bidding_APP/infrastructure/docker

# 启动所有服务
docker-compose up -d

# 验证服务运行
docker-compose ps

# 运行本地测试
cd ../../load-tests
python websocket_fanout_test.py \
    --connections 100 \
    --bids 10 \
    --ws-url ws://localhost:8081 \
    --api-url http://localhost:8080
```

**费用：$0/月**

---

## 快速参考

### 检查资源状态

```bash
# 检查ECS服务
aws ecs list-services --cluster bidding-system-cluster --region us-west-2

# 检查负载均衡器
aws elbv2 describe-load-balancers --region us-west-2

# 检查Redis
aws elasticache describe-cache-clusters --cache-cluster-id bidding-system-redis --region us-west-2

# 检查RDS
aws rds describe-db-instances --db-instance-identifier bidding-system-postgres --region us-west-2

# 检查NAT Gateways（贵！）
aws ec2 describe-nat-gateways --region us-west-2 --filter "Name=state,Values=available"
```

### 月度费用对比

| 资源 | 费用 | 可选？ |
|------|------|--------|
| ECS Fargate (4 tasks, 2 vCPU, 4GB) | ~$70/月 | ❌ 必需 |
| Application Load Balancer | ~$16/月 | ❌ 必需 |
| Network Load Balancer | ~$16/月 | ❌ 必需 |
| ElastiCache Redis (cache.t3.micro) | ~$12/月 | ✅ 可用localhost |
| RDS PostgreSQL (db.t3.micro) | ~$12/月 | ✅ 可用localhost |
| NAT Gateway (x2) | ~$64/月 | ✅ **建议删除** |
| 数据传输 | ~$20/月 | ❌ 必需 |
| **总计** | **~$210/月** | |
| **无NAT Gateway** | **~$146/月** | 省$64 |

---

## 常见问题

### Q: 我的ECR镜像还在吗？
A: 是的，ECR镜像不会被删除，随时可以重新部署。

### Q: 我需要重新构建Docker镜像吗？
A: 不需要，除非你修改了代码。已有的镜像仍然在ECR中。

### Q: 如何避免NAT Gateway费用？
A: 使用公有子网（assignPublicIp=ENABLED）而不是私有子网。

### Q: 销毁后还会产生费用吗？
A: 非常少（VPC、ECR存储等），大约<$5/月。

### Q: 重新部署需要多久？
A: 选项A（完整）：15-20分钟，选项B（手动）：30-40分钟。

---

## 需要帮助？

如果遇到问题，检查：
1. AWS凭证是否有效
2. 安全组规则是否正确
3. 子网配置是否正确
4. IAM角色权限是否充足

查看日志：
```bash
# ECS任务日志
aws logs tail /ecs/bidding-system/api-gateway --follow --region us-west-2
```
