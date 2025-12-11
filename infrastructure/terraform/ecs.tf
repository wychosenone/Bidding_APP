# ECS Cluster and Services Configuration

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/ecs/${var.project_name}/api-gateway"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-api-gateway-logs"
  }
}

resource "aws_cloudwatch_log_group" "broadcast_service" {
  name              = "/ecs/${var.project_name}/broadcast-service"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-broadcast-service-logs"
  }
}

resource "aws_cloudwatch_log_group" "archival_worker" {
  name              = "/ecs/${var.project_name}/archival-worker"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-archival-worker-logs"
  }
}

resource "aws_cloudwatch_log_group" "nats" {
  name              = "/ecs/${var.project_name}/nats"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-nats-logs"
  }
}

# Use existing LabRole for AWS Academy (no IAM creation permissions)
data "aws_caller_identity" "current" {}

locals {
  # Use LabRole that already exists in AWS Academy accounts
  lab_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"
}

# NATS Task Definition
resource "aws_ecs_task_definition" "nats" {
  family                   = "${var.project_name}-nats"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.nats_cpu
  memory                   = var.nats_memory
  execution_role_arn       = local.lab_role_arn
  task_role_arn            = local.lab_role_arn

  container_definitions = jsonencode([
    {
      name  = "nats"
      image = var.nats_image

      essential = true

      command = ["-js", "-m", "8222"]

      portMappings = [
        {
          containerPort = 4222
          protocol      = "tcp"
        },
        {
          containerPort = 8222
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nats.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "nats"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "wget --spider -q http://localhost:8222/healthz || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-nats-task"
  }
}

# NATS Service
resource "aws_ecs_service" "nats" {
  name            = "${var.project_name}-nats"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.nats.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.nats.arn
    container_name   = "nats"
    container_port   = 4222
  }

  tags = {
    Name = "${var.project_name}-nats-service"
  }
}

# API Gateway Task Definition
resource "aws_ecs_task_definition" "api_gateway" {
  family                   = "${var.project_name}-api-gateway"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_gateway_cpu
  memory                   = var.api_gateway_memory
  execution_role_arn       = local.lab_role_arn
  task_role_arn            = local.lab_role_arn

  container_definitions = jsonencode([
    {
      name  = "api-gateway"
      image = var.api_gateway_image != "" ? var.api_gateway_image : "${aws_ecr_repository.api_gateway.repository_url}:latest"

      essential = true

      environment = [
        {
          name  = "SERVER_ADDR"
          value = ":8080"
        },
        {
          name  = "REDIS_ADDR"
          value = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
        },
        {
          name  = "REDIS_PASSWORD"
          value = ""
        },
        {
          name  = "REDIS_DB"
          value = "0"
        },
        {
          name  = "NATS_URL"
          value = "nats://${aws_lb.nats.dns_name}:4222"
        }
      ]

      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api_gateway.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api-gateway"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "wget --spider -q http://localhost:8080/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-api-gateway-task"
  }
}

# API Gateway Service
resource "aws_ecs_service" "api_gateway" {
  name            = "${var.project_name}-api-gateway"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api_gateway.arn
  desired_count   = var.api_gateway_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api_gateway.arn
    container_name   = "api-gateway"
    container_port   = 8080
  }

  depends_on = [
    aws_lb_listener.http,
    aws_ecs_service.nats
  ]

  tags = {
    Name = "${var.project_name}-api-gateway-service"
  }
}

# Broadcast Service Task Definition
resource "aws_ecs_task_definition" "broadcast_service" {
  family                   = "${var.project_name}-broadcast-service"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.broadcast_service_cpu
  memory                   = var.broadcast_service_memory
  execution_role_arn       = local.lab_role_arn
  task_role_arn            = local.lab_role_arn

  container_definitions = jsonencode([
    {
      name  = "broadcast-service"
      image = var.broadcast_service_image != "" ? var.broadcast_service_image : "${aws_ecr_repository.broadcast_service.repository_url}:latest"

      essential = true

      environment = [
        {
          name  = "SERVER_ADDR"
          value = ":8081"
        },
        {
          name  = "REDIS_ADDR"
          value = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
        },
        {
          name  = "REDIS_PASSWORD"
          value = ""
        },
        {
          name  = "REDIS_DB"
          value = "0"
        },
        {
          name  = "NATS_URL"
          value = "nats://${aws_lb.nats.dns_name}:4222"
        }
      ]

      portMappings = [
        {
          containerPort = 8081
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.broadcast_service.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "broadcast-service"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "wget --spider -q http://localhost:8081/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-broadcast-service-task"
  }
}

# Broadcast Service
resource "aws_ecs_service" "broadcast_service" {
  name            = "${var.project_name}-broadcast-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.broadcast_service.arn
  desired_count   = var.broadcast_service_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.broadcast_service.arn
    container_name   = "broadcast-service"
    container_port   = 8081
  }

  depends_on = [aws_lb_listener.http]

  tags = {
    Name = "${var.project_name}-broadcast-service-service"
  }
}

# Archival Worker Task Definition
resource "aws_ecs_task_definition" "archival_worker" {
  family                   = "${var.project_name}-archival-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.archival_worker_cpu
  memory                   = var.archival_worker_memory
  execution_role_arn       = local.lab_role_arn
  task_role_arn            = local.lab_role_arn

  container_definitions = jsonencode([
    {
      name  = "archival-worker"
      image = var.archival_worker_image != "" ? var.archival_worker_image : "${aws_ecr_repository.archival_worker.repository_url}:latest"

      essential = true

      environment = [
        {
          name  = "POSTGRES_URL"
          value = "postgres://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${var.db_name}?sslmode=require"
        },
        {
          name  = "NATS_URL"
          value = "nats://${aws_lb.nats.dns_name}:4222"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.archival_worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "archival-worker"
        }
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-archival-worker-task"
  }
}

# Archival Worker Service
resource "aws_ecs_service" "archival_worker" {
  name            = "${var.project_name}-archival-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.archival_worker.arn
  desired_count   = var.archival_worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  depends_on = [
    aws_ecs_service.nats,
    aws_db_instance.postgres
  ]

  tags = {
    Name = "${var.project_name}-archival-worker-service"
  }
}
