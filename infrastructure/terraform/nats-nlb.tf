# Internal Network Load Balancer for NATS discovery
# This works around AWS Academy Service Discovery restrictions

# Internal NLB for NATS
resource "aws_lb" "nats" {
  name               = "${var.project_name}-nats-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = aws_subnet.private[*].id

  enable_deletion_protection = false

  tags = {
    Name = "${var.project_name}-nats-nlb"
  }
}

# Target Group for NATS
resource "aws_lb_target_group" "nats" {
  name        = "${var.project_name}-nats-tg"
  port        = 4222
  protocol    = "TCP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 10
    interval            = 30
    protocol            = "TCP"
  }

  tags = {
    Name = "${var.project_name}-nats-target-group"
  }
}

# Listener for NATS
resource "aws_lb_listener" "nats" {
  load_balancer_arn = aws_lb.nats.arn
  port              = "4222"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nats.arn
  }
}

# Output the NATS NLB DNS name
output "nats_nlb_dns" {
  description = "Internal NLB DNS name for NATS"
  value       = aws_lb.nats.dns_name
}
