# AutoTrader Web Hub Runbook

## Overview
This runbook provides operational procedures, troubleshooting guides, and emergency response steps for the AutoTrader Web Hub production environment.

**Last Updated:** October 2025  
**Environment:** Production (https://app.lunaraxolotl.com)  
**On-Call Contact:** [Your Team Contact Info]

---

## Quick Reference

### Critical URLs
- **Frontend:** https://app.lunaraxolotl.com
- **Backend API:** https://lunaraxolotl.com/api
- **Grafana:** http://localhost:3000 (or exposed port)
- **AWS Console:** https://console.aws.amazon.com
- **GitHub Repo:** https://github.com/jtacgosw-dot/autotrader-v2-1756412107

### Emergency Contacts
- **Primary On-Call:** [Contact Info]
- **Secondary On-Call:** [Contact Info]
- **Discord Alerts Channel:** [Discord Channel Link]

---

## Incident Response Quick-Start

### 1. Immediate Assessment (First 5 Minutes)
```bash
# Check overall system health
curl -s https://lunaraxolotl.com/api/health | jq '.'
curl -s https://lunaraxolotl.com/api/system/health | jq '.'

# Check CloudWatch alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix autotrader \
  --query 'MetricAlarms[?StateValue==`ALARM`].[AlarmName,StateReason]' \
  --output table

# Check recent API errors
aws logs tail /aws/ec2/autotrader-api --since 10m --format short | grep ERROR
```

### 2. Quick Triage Decision Tree
- **5xx errors spiking?** → Check ALB target health, API container logs
- **Login failures?** → Check SSM secrets, cookie domain settings
- **Discord alerts stopped?** → Check webhook URL, rate limits
- **SSE disconnects?** → Check ALB idle timeout, nginx config
- **High AWS costs?** → Check autoscaling, CloudTrail, unnecessary resources

### 3. Emergency Actions
```bash
# Pause all trading immediately
curl -X POST https://lunaraxolotl.com/api/pause \
  -H 'Cookie: session=<controller-session>' \
  --data '{}'

# Enable maintenance mode
curl -X POST https://lunaraxolotl.com/api/maintenance \
  -H 'Cookie: session=<controller-session>' \
  --data '{"enabled": true, "message": "Emergency maintenance"}'

# Silence non-critical alerts for 30 minutes
curl -X POST https://lunaraxolotl.com/api/alerts/mute \
  -H 'Cookie: session=<controller-session>' \
  -H 'Content-Type: application/json' \
  --data '{"severity": "WARN", "duration_minutes": 30}'
```

---

## Smoke Trade Test Procedure

### Purpose
Verify the full trading pipeline with a minimal $5 trade to ensure all systems are working correctly before enabling larger positions.

### Prerequisites
- System health checks passing
- Kill switch NOT active
- Maintenance mode OFF
- Controller role credentials available

### Procedure
```bash
# 1. Check current system state
curl -s https://lunaraxolotl.com/api/health | jq '.'
curl -s https://lunaraxolotl.com/api/risk | jq '.currentDrawdown, .dailyKillPct'

# 2. Execute smoke trade
curl -X POST https://lunaraxolotl.com/api/test/smoke_trade \
  -H 'Cookie: session=<controller-session>' \
  -H 'Content-Type: application/json' \
  --data '{
    "symbol": "BTC/USDT",
    "side": "buy",
    "notionalUsd": 5.0
  }'

# 3. Verify results
# - Check Discord for alert (should appear within 60s)
# - Check S3 audit logs
aws s3 ls s3://autotrader-audit-logs-v2/ --recursive | tail -5

# - Check Grafana for trade metrics
# - Verify no duplicate alerts (deduplication working)
```

### Expected Results
- ✅ Trade executes successfully
- ✅ Single Discord alert appears (no duplicates)
- ✅ Audit log written to S3 with timestamp partition
- ✅ Request ID present in alert footer
- ✅ Grafana shows trade in metrics

### Troubleshooting
- **Trade fails:** Check exchange API keys in SSM, venue connectivity
- **No Discord alert:** Check webhook URL, rate limits, AlertManager logs
- **Duplicate alerts:** Check Redis deduplication keys, cooldown settings
- **No audit log:** Check S3 permissions, logging configuration

---

## Cost Monitoring & Estimates

### Monthly Cost Breakdown (Estimated)
```
EC2 (t3.medium × 1-2):        $30-60
ALB:                          $16
CloudFront:                   $5-10
S3 (audit logs + artifacts):  $2-5
CloudTrail:                   $2-3
GuardDuty:                    $4-5
CloudWatch (logs + alarms):   $3-5
WAF:                          $5-7
Synthetics canary:            $2
Redis/Grafana (on EC2):       included
-------------------------
Total:                        $69-117/month
```

### Budget Alert Configuration
- **Threshold:** $80 (80% of $100 budget)
- **Alert via:** SNS → Discord
- **Action:** Review resources, check for anomalies

### Cost Optimization Checks
```bash
# Check S3 storage usage
aws s3 ls s3://autotrader-audit-logs-v2 --recursive --summarize

# Check CloudWatch log retention
aws logs describe-log-groups \
  --query 'logGroups[?starts_with(logGroupName, `/aws/`)].{Name:logGroupName,Retention:retentionInDays}' \
  --output table

# Check running EC2 instances
aws ec2 describe-instances \
  --filters "Name=tag:Stack,Values=autotrader-v2" \
  --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name]' \
  --output table
```

---

## Credential Rotation Procedures

### Discord Webhook
```bash
# 1. Generate new webhook in Discord server settings
# 2. Update SSM parameter
aws secretsmanager update-secret \
  --secret-id autotrader/discord-webhook \
  --secret-string '{"url":"https://discord.com/api/webhooks/NEW_WEBHOOK_URL"}'

# 3. Restart API container
ssh -i ~/.ssh/autotrader.pem ubuntu@<ec2-ip>
cd /opt/autotrader
docker-compose restart api discord_bot
```

### Grafana Admin Password
```bash
# Run the rotation script
cd /home/ubuntu/repos/autotrader-v2-1756412107/scripts
./rotate-grafana-admin.sh

# Update docker-compose.yml with new password
# Restart Grafana container
```

### User Credentials (viewer/controller)
```bash
# Update SSM secrets
aws secretsmanager update-secret \
  --secret-id autotrader/controller-credentials \
  --secret-string '{"username":"controller","password":"NEW_PASSWORD"}'

# Restart API to pick up new credentials
docker-compose restart api
```

---

## Exchange API Key Management

### Adding New Exchange Keys
```bash
# 1. Generate API keys on exchange (with IP whitelist if possible)
# 2. Store in SSM Parameter Store
aws ssm put-parameter \
  --name "/autotrader/exchanges/binance/api-key" \
  --value "YOUR_API_KEY" \
  --type "SecureString" \
  --overwrite

aws ssm put-parameter \
  --name "/autotrader/exchanges/binance/api-secret" \
  --value "YOUR_API_SECRET" \
  --type "SecureString" \
  --overwrite

# 3. Update IAM policy to allow access
# (Run scripts/update_iam_policy.py)

# 4. Restart API to load new keys
docker-compose restart api
```

### Key Security Best Practices
- ✅ Use IP whitelist on exchange side
- ✅ Enable withdrawal whitelist (no withdrawals via API)
- ✅ Set trading permissions only (no transfer/withdrawal)
- ✅ Use subaccounts if supported by exchange
- ✅ Rotate keys quarterly or after any security incident
- ✅ Monitor for unusual API usage patterns

---

## Kill Switch Drill

### Purpose
Verify the kill switch mechanism works correctly and can halt trading in emergency situations.

### Test Procedure
```bash
# 1. Record current state
CURRENT_DRAWDOWN=$(curl -s https://lunaraxolotl.com/api/risk | jq '.currentDrawdown')
CURRENT_THRESHOLD=$(curl -s https://lunaraxolotl.com/api/risk | jq '.dailyKillPct')

echo "Current Drawdown: $CURRENT_DRAWDOWN%"
echo "Kill Switch Threshold: $CURRENT_THRESHOLD%"

# 2. Temporarily lower kill switch threshold to trigger it
curl -X POST https://lunaraxolotl.com/api/risk \
  -H 'Cookie: session=<controller-session>' \
  -H 'Content-Type: application/json' \
  --data "{
    \"dailyKillPct\": 0.1,
    \"maxPosPct\": 5.0,
    \"maxSlippageBps\": 10
  }"

# 3. Verify kill switch active
# - Check Risk & Controls page UI (red alert should appear)
# - Check API logs for kill switch activation
# - Attempt a trade (should be blocked)

# 4. Restore original threshold
curl -X POST https://lunaraxolotl.com/api/risk \
  -H 'Cookie: session=<controller-session>' \
  -H 'Content-Type: application/json' \
  --data "{
    \"dailyKillPct\": $CURRENT_THRESHOLD,
    \"maxPosPct\": 5.0,
    \"maxSlippageBps\": 10
  }"

# 5. Verify kill switch deactivated
```

### Expected Behavior
- ✅ Kill switch activates when drawdown > threshold
- ✅ All new trades blocked
- ✅ Red alert appears in UI
- ✅ Discord notification sent
- ✅ Existing positions remain (no forced liquidation)
- ✅ System returns to normal when threshold raised

---

## Common Issues & Troubleshooting

### Issue: Website shows "ERR_CONNECTION_TIMED_OUT"
**Cause:** DNS not pointing to ALB, or ALB health checks failing  
**Resolution:**
```bash
# Check DNS
nslookup app.lunaraxolotl.com
# Should resolve to *.elb.amazonaws.com

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --names autotrader-tg \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)

# Check EC2 instance status
aws ec2 describe-instances \
  --instance-ids i-06051733a989e0abf \
  --query 'Reservations[0].Instances[0].State.Name'
```

### Issue: Users logged out after 10 seconds
**Cause:** Cookie domain or SameSite misconfiguration  
**Resolution:**
```bash
# Check cookie settings in API
grep -A5 "set_cookie" /opt/autotrader/api/main.py
# Should show: domain=".lunaraxolotl.com", secure=True, samesite="none"

# Test cookie in browser console
document.cookie
```

### Issue: Live Feed page is grey/dark
**Cause:** JavaScript error, likely null reference in trade data  
**Resolution:**
```bash
# Check browser console for errors
# Look for: "Cannot read property 'price' of null"

# Check SSE stream
curl -N https://lunaraxolotl.com/api/stream/health

# Verify trade data format
```

### Issue: Discord alerts spamming
**Cause:** AlertManager deduplication not working, Redis connection issue  
**Resolution:**
```bash
# Check Redis connectivity
redis-cli -h localhost ping

# Check AlertManager logs
docker logs autotrader-api | grep AlertManager

# Check deduplication keys
redis-cli keys "alert:prod:*:open"

# Temporarily silence alerts
curl -X POST https://lunaraxolotl.com/api/alerts/mute \
  -H 'Cookie: session=<controller-session>' \
  --data '{"severity": "INFO", "duration_minutes": 60}'
```

### Issue: Synthetics canary failing
**Cause:** Canary script error, authentication issue, endpoint down  
**Resolution:**
```bash
# Check canary status
aws synthetics describe-canaries --names autotrader-web-hub

# View canary logs
aws logs tail /aws/lambda/cwsyn-autotrader-web-hub --since 1h

# Test endpoints manually
curl -s https://lunaraxolotl.com/api/health
curl -s https://app.lunaraxolotl.com
```

---

## Deployment Procedures

### Frontend Deployment
```bash
cd /home/ubuntu/repos/autotrader-v2-1756412107/web

# Build
npm run build

# Deploy to S3
aws s3 sync dist/ s3://app.lunaraxolotl.com/ \
  --delete \
  --cache-control "public, max-age=31536000, immutable"

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id E2Q821S151MNYL \
  --paths "/*"
```

### Backend Deployment
```bash
cd /home/ubuntu/repos/autotrader-v2-1756412107

# Create deployment archive
tar czf autotrader-deploy.tar.gz api/ nginx/ docker-compose.yml alerts/

# Deploy via SSM
aws ssm send-command \
  --instance-ids "i-06051733a989e0abf" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "cd /opt/autotrader",
    "docker-compose down",
    "cp -r api api.backup.$(date +%s)",
    "tar xzf /tmp/autotrader-deploy.tar.gz",
    "docker-compose up -d"
  ]'
```

### Infrastructure Changes
```bash
cd /home/ubuntu/repos/autotrader-v2-1756412107/infrastructure

# Validate
terraform validate

# Plan
terraform plan -out=tfplan

# Apply (after review)
terraform apply tfplan
```

---

## Monitoring & Observability

### Grafana Dashboards
- **AutoTrader Overview:** API metrics, error rates, latency
- **AutoTrader Sleeves:** Trading strategy performance (when enabled)

### CloudWatch Alarms (Current Thresholds)
- `autotrader-alb-5xx-errors`: ≥5% for 5 minutes
- `autotrader-tg-unhealthy`: <1 healthy target for 2 checks
- `autotrader-api-error-rate`: ≥50 errors in 5 minutes (10/min)
- `autotrader-login-failure-rate`: ≥50 failures in 5 minutes (10/min)
- `autotrader-budget-breach`: ≥$80 monthly charges
- `autotrader-sse-disconnect-rate`: ≥10 disconnects in 5 minutes
- `autotrader-discord-failure-rate`: ≥3 failures in 10 minutes

### Key Metrics to Watch
```bash
# API error rate
aws cloudwatch get-metric-statistics \
  --namespace AutoTrader \
  --metric-name ApiErrorCount \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# ALB target health
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HealthyHostCount \
  --dimensions Name=TargetGroup,Value=<tg-arn-suffix> \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average
```

---

## Backup & Restore

### AMI Snapshots
```bash
# List available snapshots
aws ec2 describe-images --owners self \
  --filters "Name=tag:Stack,Values=autotrader-v2" \
  --query 'Images[*].[Name,ImageId,CreationDate]' \
  --output table

# Create new snapshot
aws ec2 create-image \
  --instance-id i-06051733a989e0abf \
  --name "autotrader-backup-$(date +%Y-%m-%d-%H%M)" \
  --description "Manual backup before major change"
```

### Restore from AMI
```bash
# 1. Update launch template with AMI
aws ec2 create-launch-template-version \
  --launch-template-id <template-id> \
  --source-version $Latest \
  --launch-template-data '{"ImageId":"<ami-id>"}'

# 2. Update autoscaling group
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name autotrader-asg \
  --launch-template LaunchTemplateId=<template-id>,Version=$Latest

# 3. Terminate old instance (ASG will launch new one)
aws ec2 terminate-instances --instance-ids <old-instance-id>
```

### S3 Audit Log Backup
```bash
# Audit logs automatically lifecycle to Glacier after 90 days
# To restore from Glacier:
aws s3api restore-object \
  --bucket autotrader-audit-logs-v2 \
  --key year=2025/month=10/day=06/audit-20251006.jsonl.gz \
  --restore-request Days=7,GlacierJobParameters={Tier=Standard}
```

---

## Security Checklist

### Regular Security Reviews (Quarterly)
- [ ] Rotate all API keys and credentials
- [ ] Review IAM policies for least privilege
- [ ] Check CloudTrail for unauthorized API calls
- [ ] Review GuardDuty findings
- [ ] Update WAF rules based on traffic patterns
- [ ] Scan dependencies for vulnerabilities
- [ ] Review security group rules
- [ ] Verify MFA enabled for AWS accounts
- [ ] Check S3 bucket policies and public access
- [ ] Review Discord webhook access logs

### Post-Incident Security Actions
- [ ] Rotate potentially compromised credentials
- [ ] Review access logs for unauthorized activity
- [ ] Update security groups if breach via network
- [ ] Document incident and update runbook
- [ ] Share lessons learned with team

---

## Escalation Matrix

### Level 1: Self-Service (0-15 minutes)
- Check this runbook
- Review CloudWatch alarms
- Check Discord alerts history
- Review recent deployments

### Level 2: Team Lead (15-30 minutes)
- Contact: [Team Lead Contact]
- Provide: Incident description, steps taken, current state
- Access: Can approve emergency changes, credential rotations

### Level 3: Infrastructure Team (30+ minutes)
- Contact: [Infrastructure Team]
- Provide: Full incident timeline, logs, metrics
- Access: Can modify IAM, VPC, core infrastructure

### Level 4: AWS Support (60+ minutes)
- Business Support: Create case via AWS Console
- Provide: Account ID, resources affected, business impact
- For production outages: Use "Production system down" severity

---

## Change Management

### Standard Change Window
- **Day:** Tuesday/Thursday
- **Time:** 10:00-12:00 UTC (off-peak hours)
- **Approval:** Requires team lead sign-off
- **Rollback plan:** Must be documented before change

### Emergency Change
- **Criteria:** Production down, security incident, critical bug
- **Approval:** On-call engineer can approve
- **Communication:** Notify team via Discord immediately
- **Post-mortem:** Required within 24 hours

---

## Contact Information

### Team
- **Engineering Lead:** [Name] - [Email] - [Phone]
- **DevOps:** [Name] - [Email] - [Phone]
- **On-Call Rotation:** See PagerDuty schedule

### External Services
- **AWS Support:** https://console.aws.amazon.com/support/
- **Discord Support:** https://support.discord.com/
- **GitHub Support:** https://support.github.com/

---

## Document History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2025-10-06 | 1.0 | Devin AI | Initial runbook creation |

---

**Note:** This runbook should be reviewed and updated quarterly or after any major incident or infrastructure change.
