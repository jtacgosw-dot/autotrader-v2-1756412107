resource "aws_synthetics_canary" "web_hub" {
  name                 = "autotrader-web-hub"
  artifact_s3_location = "s3://${aws_s3_bucket.web_bucket.id}/canary-artifacts/"
  execution_role_arn   = aws_iam_role.canary_role.arn
  handler              = "web-hub-canary.handler"
  zip_file             = "${path.module}/../scripts/synthetics/web-hub-canary.js"
  runtime_version      = "syn-nodejs-puppeteer-6.2"

  schedule {
    expression = "rate(5 minutes)"
  }

  run_config {
    timeout_in_seconds = 60
    memory_in_mb       = 1024
  }

  success_retention_period = 2
  failure_retention_period = 14

  tags = {
    Name        = "autotrader-web-hub-canary"
    Environment = "prod"
  }
}

resource "aws_iam_role" "canary_role" {
  name = "autotrader-canary-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "canary_policy" {
  role       = aws_iam_role.canary_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchSyntheticsFullAccess"
}

resource "aws_iam_role_policy" "canary_s3_policy" {
  name = "canary-s3-policy"
  role = aws_iam_role.canary_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:PutObject", "s3:GetObject"]
      Resource = "arn:aws:s3:::autotrader-synthetics-artifacts/canary-artifacts/*"
    }]
  })
}
