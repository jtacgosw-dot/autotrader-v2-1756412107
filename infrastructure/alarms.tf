
resource "aws_cloudwatch_metric_alarm" "alb_5xx_errors" {
  alarm_name          = "autotrader-alb-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "5"
  alarm_description   = "Alert when ALB 5xx error rate exceeds 5% for 5 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "m1 / m2 * 100"
    label       = "5xx Error Rate"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "HTTPCode_Target_5XX_Count"
      namespace   = "AWS/ApplicationELB"
      period      = 300
      stat        = "Sum"
      dimensions = {
        LoadBalancer = aws_lb.autotrader.arn_suffix
      }
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "RequestCount"
      namespace   = "AWS/ApplicationELB"
      period      = 300
      stat        = "Sum"
      dimensions = {
        LoadBalancer = aws_lb.autotrader.arn_suffix
      }
    }
  }

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_cloudwatch_metric_alarm" "target_group_unhealthy" {
  alarm_name          = "autotrader-tg-unhealthy"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = "60"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "Alert when target group has no healthy targets for 2 consecutive checks"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "breaching"

  dimensions = {
    TargetGroup  = aws_lb_target_group.autotrader.arn_suffix
    LoadBalancer = aws_lb.autotrader.arn_suffix
  }

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/ec2/autotrader-api"
  retention_in_days = 30

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_cloudwatch_log_metric_filter" "api_errors" {
  name           = "autotrader-api-errors"
  log_group_name = aws_cloudwatch_log_group.api.name
  pattern        = "[time, level=ERROR*, ...]"

  metric_transformation {
    name      = "ApiErrorCount"
    namespace = "AutoTrader"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_error_rate" {
  alarm_name          = "autotrader-api-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApiErrorCount"
  namespace           = "AutoTrader"
  period              = "300"
  statistic           = "Sum"
  threshold           = "50"
  alarm_description   = "Alert when API error log rate exceeds 10 errors/min (50 in 5 min)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_cloudwatch_log_metric_filter" "login_failures" {
  name           = "autotrader-login-failures"
  log_group_name = aws_cloudwatch_log_group.api.name
  pattern        = "[time, level, msg=\"*Login failed*\"]"

  metric_transformation {
    name      = "LoginFailureCount"
    namespace = "AutoTrader"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "login_failure_rate" {
  alarm_name          = "autotrader-login-failure-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "LoginFailureCount"
  namespace           = "AutoTrader"
  period              = "300"
  statistic           = "Sum"
  threshold           = "50"
  alarm_description   = "Alert when login failures exceed 10/min (50 in 5 min)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}

resource "aws_cloudwatch_metric_alarm" "budget_breach" {
  alarm_name          = "autotrader-budget-breach"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "21600"
  statistic           = "Maximum"
  threshold           = "80"
  alarm_description   = "Alert when estimated charges exceed $80 (80% of budget)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    Currency = "USD"
  }

  tags = {
    Stack = "autotrader-v2"
    Env   = "prod"
  }
}
