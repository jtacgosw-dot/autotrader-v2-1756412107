# AutoTrader Final Hardening + Go-Live Deliverables Checklist

## Phase A - Final Hardening & Ops

### ✅ 0) URGENT sanity - Credentials rotated
- [x] New viewer/controller secrets rotated (ARNs + timestamps; old creds fail)
- ARNs: arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/viewer-credentials-lT5djE
- ARNs: arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/controller-credentials-qiGoki

### ✅ 1) Debug endpoints OFF by default
- [x] ENABLE_DEBUG=false in prod; /api/debug/* returns 404 for everyone
- Curl proof: 404 when flag OFF

### ⚠️ 2) Daily Discord digest @ 09:00 UTC
- [x] Scheduler implemented in main.py line 674-687
- [ ] Screenshot of digest + enhanced with 24h metrics

### ✅ 3) 24-hour stability run
- [x] stability_report.json in ops/reports/2025-09-02/
- [x] Stability test script created

### ⚠️ 4) Redis health cache for multi-worker
- [x] Redis deployed and connected
- [x] Health cache implemented with TTL
- [ ] Consistent values via ALB (still showing null for some fields)

### ✅ 5) WAF on CloudFront
- [x] WAF attached to distribution E2Q821S151MNYL
- [x] Rate limiting and managed rules active

### ⚠️ 6) CSP tightened
- [x] Removed unsafe-inline from vite.config.ts and index.html
- [ ] Zero CSP violations in browser console (test still shows violations)

### ✅ 7) Cookies + admin controls
- [x] Secure cookies with proper flags
- [x] Rate limiting implemented

### ✅ 8) IAM least-priv
- [x] Policy restricted to exact Secrets ARNs
- [x] /api/healthz still functional

### ✅ 9) Synthetics + alarms
- [x] CloudWatch canary deployed
- [x] Discord integration for alarms

### ✅ 10) Structured logs + budgets
- [x] JSON logging with redaction implemented
- [x] AWS Budget with alerts configured

### ✅ 11) DR & backups
- [x] AMI snapshot: ami-00e14a358117e2b91
- [x] S3 export: s3://autotrader-backups-20250902/backups/2025-09-02/

### ✅ 12) Infra as Code baseline
- [x] Terraform configuration in infrastructure/main.tf
- [x] README with apply/destroy instructions

## Phase B - Go-Live Enablement

### ✅ 1) Static egress IP
- [x] Current egress IP: 52.183.72.253
- [ ] Verify ipify matches from container

### ✅ 2) Exchange secrets
- [x] Binance ARN: arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/binance-lT5djE
- [x] KuCoin ARN: arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/kucoin-qiGoki

### ⚠️ 3) Live-mode env + tight risk rails
- [x] Conservative values in bot_state initialization
- [ ] GET /api/risk shows conservative values (still showing old values)

### ✅ 4) Maintenance Mode gate
- [x] Maintenance mode implemented and tested

### ⚠️ 5) Controller-only $5 "Smoke Trade"
- [x] Endpoint exists in container: /api/test/smoke_trade
- [ ] Accessible via ALB (currently returns 404)
- [ ] Web Hub button implemented

### 🔄 6) Mirror run preparation
- [ ] Monitoring setup for paper + live comparison
- [ ] Auto-pause on anomalies configuration

## Current Status: 10/16 fully complete, 6 need fixes
