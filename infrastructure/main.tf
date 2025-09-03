terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "alb" {
  name_prefix = "autotrader-alb-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_security_group" "ec2" {
  name_prefix = "autotrader-ec2-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port       = 8081
    to_port         = 8081
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_lb" "autotrader" {
  name               = "autotrader-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets           = data.aws_subnets.default.ids

  enable_deletion_protection = false

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_lb_target_group" "autotrader" {
  name     = "autotrader-tg-8081"
  port     = 8081
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.default.id

  health_check {
    enabled             = true
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 15
    path                = "/api/health"
    matcher             = "200-399"
    port                = "traffic-port"
    protocol            = "HTTP"
  }

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_lb_listener" "autotrader" {
  load_balancer_arn = aws_lb.autotrader.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = "arn:aws:acm:us-east-1:123198875719:certificate/3bc1506b-e0e2-45bf-be20-05aed866db19"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.autotrader.arn
  }
}

resource "aws_iam_role" "autotrader_ec2" {
  name = "autotrader-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_iam_instance_profile" "autotrader_ec2" {
  name = "autotrader-ec2-profile"
  role = aws_iam_role.autotrader_ec2.name
}

resource "aws_s3_bucket" "web_hub" {
  bucket = "app.lunaraxolotl.com"

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_s3_bucket_public_access_block" "web_hub" {
  bucket = aws_s3_bucket.web_hub.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_distribution" "web_hub" {
  origin {
    domain_name              = aws_s3_bucket.web_hub.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.web_hub.bucket}"
    origin_access_control_id = aws_cloudfront_origin_access_control.web_hub.id
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  aliases = ["app.lunaraxolotl.com"]

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.web_hub.bucket}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn = "arn:aws:acm:us-east-1:123198875719:certificate/884715cd-0cf3-4d16-a653-7c87b5ad8461"
    ssl_support_method  = "sni-only"
  }

  web_acl_id = aws_wafv2_web_acl.autotrader.arn

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_cloudfront_origin_access_control" "web_hub" {
  name                              = "autotrader-web-hub-oac"
  description                       = "OAC for AutoTrader Web Hub"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_wafv2_web_acl" "autotrader" {
  name  = "AutoTraderWebACL"
  scope = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "CommonRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }

  rule {
    name     = "RateLimitRule"
    priority = 2

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit          = 300
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "RateLimitMetric"
      sampled_requests_enabled    = true
    }
  }

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                 = "AutoTraderWebACL"
    sampled_requests_enabled    = true
  }
}

resource "aws_budgets_budget" "autotrader" {
  name         = "AutoTrader-Monthly-Budget"
  budget_type  = "COST"
  limit_amount = "100"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filters = {
    Tag = ["Stack:autotrader-v2"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["alerts@lunaraxolotl.com"]
  }
}

output "alb_dns_name" {
  value = aws_lb.autotrader.dns_name
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.web_hub.domain_name
}

output "s3_bucket_name" {
  value = aws_s3_bucket.web_hub.bucket
}
