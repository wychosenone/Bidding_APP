# RDS PostgreSQL Configuration
# Simplified for AWS Academy (no IAM roles, no encryption)

# Subnet group for RDS
resource "aws_db_subnet_group" "postgres" {
  name       = "${var.project_name}-postgres-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "${var.project_name}-postgres-subnet-group"
  }
}

# RDS Parameter Group for PostgreSQL optimization
resource "aws_db_parameter_group" "postgres" {
  name   = "${var.project_name}-postgres-params"
  family = "postgres15"

  # Optimize for write-heavy archival workload (only dynamic parameters)
  parameter {
    name  = "checkpoint_completion_target"
    value = "0.9"
  }

  parameter {
    name  = "random_page_cost"
    value = "1.1"  # Lower for SSD storage
  }

  parameter {
    name  = "work_mem"
    value = "4096"  # 4MB
  }

  parameter {
    name  = "maintenance_work_mem"
    value = "524288"  # 512MB
  }

  parameter {
    name  = "rds.force_ssl"
    value = "0"  # Allow non-SSL connections for dev/testing
  }

  tags = {
    Name = "${var.project_name}-postgres-params"
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-postgres"
  engine         = "postgres"
  engine_version = "15.10"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 2  # Enable storage autoscaling
  storage_type          = "gp3"
  storage_encrypted     = false  # AWS Academy limitation

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  parameter_group_name   = aws_db_parameter_group.postgres.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # High availability
  multi_az               = false  # AWS Academy limitation
  publicly_accessible    = false
  deletion_protection    = false  # Set to true for production
  skip_final_snapshot    = true   # Set to false for production

  # Backups (minimal for dev/testing)
  backup_retention_period = 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  # Monitoring (disabled - requires IAM role)
  # enabled_cloudwatch_logs_exports = ["postgresql"]
  # monitoring_interval             = 0
  # performance_insights_enabled    = false

  tags = {
    Name = "${var.project_name}-postgres"
  }
}

# Outputs
output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "RDS address (without port)"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "RDS port"
  value       = aws_db_instance.postgres.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.postgres.db_name
}
