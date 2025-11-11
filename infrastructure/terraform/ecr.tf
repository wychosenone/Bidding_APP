# ECR Repositories for Container Images

# API Gateway ECR Repository
resource "aws_ecr_repository" "api_gateway" {
  name                 = "${var.project_name}/api-gateway"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-api-gateway-repo"
  }
}

# Broadcast Service ECR Repository
resource "aws_ecr_repository" "broadcast_service" {
  name                 = "${var.project_name}/broadcast-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-broadcast-service-repo"
  }
}

# Archival Worker ECR Repository
resource "aws_ecr_repository" "archival_worker" {
  name                 = "${var.project_name}/archival-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-archival-worker-repo"
  }
}

# Lifecycle policy to clean up old images
resource "aws_ecr_lifecycle_policy" "cleanup" {
  for_each = {
    api_gateway       = aws_ecr_repository.api_gateway.name
    broadcast_service = aws_ecr_repository.broadcast_service.name
    archival_worker   = aws_ecr_repository.archival_worker.name
  }

  repository = each.value

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
