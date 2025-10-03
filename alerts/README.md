# AutoTrader Alert Management System

Comprehensive alert management with Redis-backed deduplication, incident lifecycle tracking, and Discord integration.

## Features

- **Incident Lifecycle**: Automatic open/update/resolve workflow
- **Deduplication**: Redis-backed cooldowns prevent alert spam
- **Aggregation**: Burst event windows for chatty alert types
- **Message Editing**: Updates existing Discord messages instead of creating new ones
- **Heartbeat**: Optional periodic health checks (only if recent alerts)
- **Mute Windows**: Temporarily suppress alerts by severity
- **Channel Routing**: Route alerts to different channels by severity
- **Slash Commands**: Discord bot integration for two-way control

## AlertManager API

```python
from alerts.manager import AlertManager

alert_manager = AlertManager(redis_client, webhook_url)

# Send an alert
await alert_manager.send(
    type="health",
    severity="CRITICAL",
    key="alb:tg-8081",
    title="ALB Target Group Unhealthy",
    body="2/2 targets failing health checks",
    tags={"env": "prod", "region": "us-east-1"},
    links={"Grafana": "https://...", "CloudWatch": "https://..."}
)

# Resolve an incident
await alert_manager.resolve("health", "alb:tg-8081", "All targets healthy")

# Get open incidents
incidents = alert_manager.get_open_incidents()

# Mute/unmute alerts
alert_manager.mute("warning", duration_minutes=30)
alert_manager.unmute("warning")
```

## Configuration

Environment variables:

```bash
# Core Config
ALERTS_ENABLE=true
ALERTS_ENV=prod

# Timing
ALERTS_DEDUPE_TTL_SEC=900          # How long to track incidents
ALERTS_COOLDOWN_SEC=300            # Min time between updates
ALERTS_AGG_WINDOW_SEC=60           # Aggregation window
ALERTS_HEARTBEAT_INTERVAL_MIN=30   # Heartbeat frequency

# Channel Routing
ALERTS_CHANNEL_INFO=#alerts
ALERTS_CHANNEL_WARN=#alerts
ALERTS_CHANNEL_CRIT=#pages

# Escalation
ALERTS_ESCALATE_AFTER=600          # Escalate after 10min
ALERTS_PAGERDUTY_WEBHOOK=...       # Optional PagerDuty integration
```

## Incident Lifecycle

1. **Open**: First occurrence creates a new incident and posts an embed
2. **Update**: Subsequent occurrences (within cooldown) update the same message
3. **Resolve**: When condition clears, posts a RESOLVED embed and closes incident

## Aggregation

For burst/chatty alerts, use aggregation windows:

```python
# Add events to aggregation bucket
alert_manager.add_to_aggregation("latency", "binance", {
    "title": "High Latency",
    "severity": "warning",
    "detail": "Binance p95 620ms"
})

# Flush aggregated events (typically called on a timer)
await alert_manager.aggregate_and_flush("latency", "binance")
```

## Discord Commands

Available slash commands:

- `/alerts_status` - View open incidents
- `/alerts_mute <severity> <duration>` - Mute alerts temporarily
- `/alerts_unmute <severity>` - Unmute alerts
- `/alerts_test` - Send a test alert
- `/bot_pause` - Pause trading
- `/bot_resume` - Resume trading

## Redis Keys

- `alert:{env}:{type}:{key}:open` - Open incident state (JSON)
- `alert:{env}:{type}:{key}:cooldown` - Cooldown TTL
- `alert:{env}:{type}:{key}:agg` - Aggregation buffer (list)
- `alerts:mute:{severity}:{env}` - Mute window TTL

## Testing

Run unit tests:

```bash
pytest alerts/test_manager.py
```

Test locally:

```bash
# Set environment variables
export DISCORD_WEBHOOK=https://...
export REDIS_HOST=localhost

# Run test script
python -c "
from alerts.manager import AlertManager
import redis
import asyncio

r = redis.Redis(host='localhost', decode_responses=True)
am = AlertManager(r, 'https://...')

async def test():
    await am.send('test', 'info', 'test-1', 'Test Alert', 'This is a test')

asyncio.run(test())
"
```

## Architecture

```
┌─────────────────┐
│   API Server    │
│   (main.py)     │
└────────┬────────┘
         │
         ├─────────> AlertManager.send()
         │              ├─> Check mute status
         │              ├─> Check/update Redis state
         │              ├─> Post/edit Discord message
         │              └─> Store message_id
         │
         └─────────> AlertManager.resolve()
                        └─> Post RESOLVED embed

┌─────────────────┐
│  Discord Bot    │
│   (bot.py)      │
└────────┬────────┘
         │
         └─────────> Slash Commands
                        ├─> /alerts status
                        ├─> /alerts mute
                        ├─> /alerts unmute
                        └─> /alerts test
```
