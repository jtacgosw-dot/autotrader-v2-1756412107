# AutoTrader Infrastructure as Code

This directory contains Terraform configuration for the AutoTrader production infrastructure.

## Resources Managed

- Application Load Balancer (ALB) with HTTPS listener
- Target Group for EC2 instances on port 8081
- Security Groups for ALB and EC2
- S3 bucket for Web Hub static assets
- CloudFront distribution with Origin Access Control
- WAF Web ACL with managed rules and rate limiting
- IAM roles and policies for EC2 instances
- Budget alerts for cost monitoring

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Terraform installed (version >= 1.0)
3. ACM certificates already issued:
   - `arn:aws:acm:us-east-1:123198875719:certificate/3bc1506b-e0e2-45bf-be20-05aed866db19` (lunaraxolotl.com)
   - `arn:aws:acm:us-east-1:123198875719:certificate/884715cd-0cf3-4d16-a653-7c87b5ad8461` (app.lunaraxolotl.com)

## Usage

### Initialize Terraform
```bash
cd infrastructure/
terraform init
```

### Plan Changes
```bash
terraform plan
```

### Apply Infrastructure
```bash
terraform apply
```

### Destroy Infrastructure
```bash
terraform destroy
```

## Important Notes

- This configuration assumes the default VPC and subnets
- ACM certificates must be pre-created and validated
- The configuration includes security best practices:
  - S3 bucket with public access blocked
  - CloudFront with Origin Access Control
  - WAF with managed rules and rate limiting
  - Security groups with minimal required access

## State Management

For production use, consider:
1. Using remote state backend (S3 + DynamoDB)
2. Implementing state locking
3. Using Terraform workspaces for multiple environments

## Monitoring

The infrastructure includes:
- CloudWatch metrics for WAF and ALB
- Budget alerts for cost monitoring
- Health checks for target groups

## Security

- All S3 buckets have public access blocked
- CloudFront uses HTTPS only
- WAF includes AWS managed rule sets
- Security groups follow least privilege principle
