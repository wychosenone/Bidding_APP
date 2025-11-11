# Terraform Outputs

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

# Load Balancer Outputs
output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_url" {
  description = "URL of the Application Load Balancer"
  value       = "http://${aws_lb.main.dns_name}"
}

# ElastiCache Outputs
output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
}

# RDS Outputs - Disabled for AWS Academy
# output "rds_endpoint" {
#   description = "RDS PostgreSQL endpoint"
#   value       = aws_db_instance.postgres.endpoint
#   sensitive   = true
# }
#
# output "rds_database_name" {
#   description = "RDS database name"
#   value       = aws_db_instance.postgres.db_name
# }

# ECS Outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

# ECR Outputs
output "ecr_api_gateway_url" {
  description = "URL of the API Gateway ECR repository"
  value       = aws_ecr_repository.api_gateway.repository_url
}

output "ecr_broadcast_service_url" {
  description = "URL of the Broadcast Service ECR repository"
  value       = aws_ecr_repository.broadcast_service.repository_url
}

output "ecr_archival_worker_url" {
  description = "URL of the Archival Worker ECR repository"
  value       = aws_ecr_repository.archival_worker.repository_url
}

# Service Discovery Outputs - Disabled for AWS Academy
# output "service_discovery_namespace" {
#   description = "Service discovery namespace"
#   value       = aws_service_discovery_private_dns_namespace.main.name
# }
#
# output "nats_service_url" {
#   description = "NATS service URL for internal access"
#   value       = "nats://nats.${aws_service_discovery_private_dns_namespace.main.name}:4222"
# }

# Helpful Commands
output "deployment_commands" {
  description = "Commands for deploying services"
  value = <<-EOT
    # 1. Build and push Docker images to ECR
    aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.api_gateway.repository_url}

    docker build -t ${aws_ecr_repository.api_gateway.repository_url}:latest -f infrastructure/docker/Dockerfile.api-gateway .
    docker push ${aws_ecr_repository.api_gateway.repository_url}:latest

    docker build -t ${aws_ecr_repository.broadcast_service.repository_url}:latest -f infrastructure/docker/Dockerfile.broadcast-service .
    docker push ${aws_ecr_repository.broadcast_service.repository_url}:latest

    docker build -t ${aws_ecr_repository.archival_worker.repository_url}:latest -f infrastructure/docker/Dockerfile.archival-worker .
    docker push ${aws_ecr_repository.archival_worker.repository_url}:latest

    # 2. Update ECS services to use new images
    aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service ${aws_ecs_service.api_gateway_simple.name} --force-new-deployment --region ${var.aws_region}
    aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service ${aws_ecs_service.broadcast_service_simple.name} --force-new-deployment --region ${var.aws_region}

    # 3. Access the application
    API Gateway: http://${aws_lb.main.dns_name}/api/v1/items/test_item
    WebSocket: ws://${aws_lb.main.dns_name}/ws/items/test_item
  EOT
}

output "connection_info" {
  description = "Connection information for services"
  value = {
    api_gateway_url    = "http://${aws_lb.main.dns_name}/api/v1"
    websocket_url      = "ws://${aws_lb.main.dns_name}/ws"
    health_check_url   = "http://${aws_lb.main.dns_name}/health"
  }
}
