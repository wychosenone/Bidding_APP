# Variables for AWS Bidding System Infrastructure

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "bidding-system"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 2
}

# ElastiCache (Redis) Configuration
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"  # For testing; use cache.r6g.large for production
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

# RDS (PostgreSQL) Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"  # For testing; use db.r6g.large for production
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "bidding"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "bidding"
}

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
  default     = "ChangeMe123!"  # CHANGE IN PRODUCTION
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS in GB"
  type        = number
  default     = 20
}

# ECS Configuration
variable "api_gateway_cpu" {
  description = "CPU units for API Gateway task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "api_gateway_memory" {
  description = "Memory for API Gateway task in MB"
  type        = number
  default     = 1024
}

variable "api_gateway_desired_count" {
  description = "Desired number of API Gateway tasks"
  type        = number
  default     = 2
}

variable "broadcast_service_cpu" {
  description = "CPU units for Broadcast Service task"
  type        = number
  default     = 512
}

variable "broadcast_service_memory" {
  description = "Memory for Broadcast Service task in MB"
  type        = number
  default     = 1024
}

variable "broadcast_service_desired_count" {
  description = "Desired number of Broadcast Service tasks"
  type        = number
  default     = 2
}

variable "archival_worker_cpu" {
  description = "CPU units for Archival Worker task"
  type        = number
  default     = 256
}

variable "archival_worker_memory" {
  description = "Memory for Archival Worker task in MB"
  type        = number
  default     = 512
}

variable "archival_worker_desired_count" {
  description = "Desired number of Archival Worker tasks"
  type        = number
  default     = 1
}

variable "nats_cpu" {
  description = "CPU units for NATS task"
  type        = number
  default     = 256
}

variable "nats_memory" {
  description = "Memory for NATS task in MB"
  type        = number
  default     = 512
}

# Container Image Configuration
variable "api_gateway_image" {
  description = "Docker image for API Gateway"
  type        = string
  default     = ""  # Will be set after pushing to ECR
}

variable "broadcast_service_image" {
  description = "Docker image for Broadcast Service"
  type        = string
  default     = ""  # Will be set after pushing to ECR
}

variable "archival_worker_image" {
  description = "Docker image for Archival Worker"
  type        = string
  default     = ""  # Will be set after pushing to ECR
}

variable "nats_image" {
  description = "Docker image for NATS"
  type        = string
  default     = "nats:2-alpine"
}
