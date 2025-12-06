# Simplified ECS Configuration using existing LabRole
# This works around AWS Academy IAM restrictions

locals {
  lab_role_arn = "arn:aws:iam::905418455791:role/LabRole"
}

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

resource "aws_cloudwatch_log_group" "nats" {
  name              = "/ecs/${var.project_name}/nats"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-nats-logs"
  }
}

resource "aws_cloudwatch_log_group" "archival_worker" {
  name              = "/ecs/${var.project_name}/archival-worker"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-archival-worker-logs"
  }
}

# API Gateway Task Definition (using LabRole)
resource "aws_ecs_task_definition" "api_gateway_simple" {
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
      image = "${aws_ecr_repository.api_gateway.repository_url}:latest"

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
        },
        {
          name  = "REDIS_STRATEGY"
          value = var.redis_strategy
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
    }
  ])

  tags = {
    Name = "${var.project_name}-api-gateway-task-simple"
  }
}

# API Gateway Service (simplified)
resource "aws_ecs_service" "api_gateway_simple" {
  name            = "${var.project_name}-api-gateway"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api_gateway_simple.arn
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

  depends_on = [aws_lb_listener.http, aws_ecs_service.nats_simple]

  tags = {
    Name = "${var.project_name}-api-gateway-service-simple"
  }
}

# Broadcast Service Task Definition (using LabRole)
resource "aws_ecs_task_definition" "broadcast_service_simple" {
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
      image = "${aws_ecr_repository.broadcast_service.repository_url}:latest"

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
    }
  ])

  tags = {
    Name = "${var.project_name}-broadcast-service-task-simple"
  }
}

# Broadcast Service (simplified)
resource "aws_ecs_service" "broadcast_service_simple" {
  name            = "${var.project_name}-broadcast-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.broadcast_service_simple.arn
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

  depends_on = [aws_lb_listener.http, aws_ecs_service.nats_simple]

  tags = {
    Name = "${var.project_name}-broadcast-service-service-simple"
  }
}

# NATS Task Definition (using LabRole)
resource "aws_ecs_task_definition" "nats_simple" {
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
      image = "nats:2.10-alpine"

      essential = true

      command = ["-js"]

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
    }
  ])

  tags = {
    Name = "${var.project_name}-nats-task-simple"
  }
}

# NATS Service using NLB for discovery
resource "aws_ecs_service" "nats_simple" {
  name            = "${var.project_name}-nats"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.nats_simple.arn
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

  depends_on = [aws_lb_listener.nats]

  tags = {
    Name = "${var.project_name}-nats-service-simple"
  }
}

# Archival Worker Task Definition (using LabRole)
resource "aws_ecs_task_definition" "archival_worker_simple" {
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
      image = "${aws_ecr_repository.archival_worker.repository_url}:latest"

      essential = true

      environment = [
        {
          name  = "NATS_URL"
          value = "nats://${aws_lb.nats.dns_name}:4222"
        },
        {
          name  = "POSTGRES_URL"
          value = "postgres://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${aws_db_instance.postgres.db_name}?sslmode=disable"
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
    Name = "${var.project_name}-archival-worker-task-simple"
  }
}

# Archival Worker Service (no load balancer - background worker)
resource "aws_ecs_service" "archival_worker_simple" {
  name            = "${var.project_name}-archival-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.archival_worker_simple.arn
  desired_count   = var.archival_worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  depends_on = [aws_ecs_service.nats_simple, aws_db_instance.postgres]

  tags = {
    Name = "${var.project_name}-archival-worker-service-simple"
  }
}
