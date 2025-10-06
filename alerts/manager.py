import os
import json
import time
import asyncio
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import redis
from collections import defaultdict

logger = logging.getLogger(__name__)

class AlertManager:
    """
    Comprehensive alert management system with Redis-backed deduplication,
    incident lifecycle tracking, aggregation, and Discord integration.
    """
    
    def __init__(self, redis_client, webhook_url: str):
        self.redis = redis_client
        self.webhook_url = webhook_url
        self.env = os.getenv("ALERTS_ENV", "prod")
        
        self.enable = os.getenv("ALERTS_ENABLE", "true").lower() == "true"
        self.dedupe_ttl = int(os.getenv("ALERTS_DEDUPE_TTL_SEC", "900"))
        self.cooldown = int(os.getenv("ALERTS_COOLDOWN_SEC", "300"))
        self.agg_window = int(os.getenv("ALERTS_AGG_WINDOW_SEC", "60"))
        self.max_posts_per_min = int(os.getenv("ALERTS_MAX_POSTS_PER_MIN", "20"))
        
        self.channel_info = os.getenv("ALERTS_CHANNEL_INFO", "#alerts")
        self.channel_warn = os.getenv("ALERTS_CHANNEL_WARN", "#alerts")
        self.channel_crit = os.getenv("ALERTS_CHANNEL_CRIT", "#pages")
        
        self.escalate_after = int(os.getenv("ALERTS_ESCALATE_AFTER", "600"))
        self.pagerduty_webhook = os.getenv("ALERTS_PAGERDUTY_WEBHOOK")
        
        self.rate_limiter = asyncio.Semaphore(5)
        
        self.heartbeat_interval = int(os.getenv("ALERTS_HEARTBEAT_INTERVAL_MIN", "30"))
        self.last_heartbeat = None
        
    def _get_redis_keys(self, alert_type: str, key: str) -> Dict[str, str]:
        """Generate Redis keys for incident tracking"""
        base = f"alert:{self.env}:{alert_type}:{key}"
        return {
            "open": f"{base}:open",
            "cooldown": f"{base}:cooldown",
            "agg": f"{base}:agg"
        }
    
    def _severity_color(self, severity: str) -> int:
        """Get Discord embed color for severity"""
        colors = {
            "info": 0x808080,
            "warn": 0xFFA500,
            "warning": 0xFFA500,
            "critical": 0xFF0000,
            "crit": 0xFF0000
        }
        return colors.get(severity.lower(), 0x808080)
    
    def _severity_emoji(self, severity: str) -> str:
        """Get emoji for severity"""
        emojis = {
            "info": "ℹ️",
            "warn": "⚠️",
            "warning": "⚠️",
            "critical": "🚨",
            "crit": "🚨"
        }
        return emojis.get(severity.lower(), "📌")
    
    def _is_muted(self, severity: str) -> bool:
        """Check if alerts at this severity are muted"""
        mute_key = f"alerts:mute:{severity.lower()}:{self.env}"
        return self.redis.exists(mute_key) > 0
    
    async def send(
        self,
        type: str,
        severity: str,
        key: str,
        title: str,
        body: str,
        fingerprint: Optional[str] = None,
        dedupe_ttl: Optional[int] = None,
        cooldown: Optional[int] = None,
        group: str = "ops",
        tags: Optional[Dict[str, str]] = None,
        links: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Send an alert with full incident lifecycle management.
        
        Args:
            type: Alert type (e.g., "health", "infra", "trade", "risk", "latency")
            severity: "INFO", "WARN", or "CRITICAL"
            key: Dedupe key (same key => same incident)
            title: Alert title
            body: Alert body/description
            fingerprint: Optional idempotency key
            dedupe_ttl: Override default dedupe TTL
            cooldown: Override default cooldown
            group: Channel routing group
            tags: Additional metadata tags
            links: Links to include in embed (e.g., {"Grafana": "https://...", "CloudWatch": "https://..."})
        
        Returns:
            True if alert was sent, False if suppressed
        """
        if not self.enable:
            logger.debug(f"Alerts disabled, skipping: {type}:{key}")
            return False
        
        if self._is_muted(severity) and severity.upper() != "CRITICAL":
            logger.info(f"Alert muted: {severity}:{type}:{key}")
            return False
        
        dedupe_ttl = dedupe_ttl or self.dedupe_ttl
        cooldown = cooldown or self.cooldown
        tags = tags or {}
        links = links or {}
        
        redis_keys = self._get_redis_keys(type, key)
        
        try:
            incident_data = self.redis.get(redis_keys["open"])
            if incident_data:
                incident = json.loads(incident_data)
                
                in_cooldown = self.redis.exists(redis_keys["cooldown"]) > 0
                if in_cooldown:
                    logger.debug(f"Alert in cooldown: {type}:{key}")
                    incident["count"] = incident.get("count", 1) + 1
                    incident["last_seen"] = datetime.utcnow().isoformat()
                    self.redis.setex(redis_keys["open"], dedupe_ttl, json.dumps(incident))
                    return False
                
                return await self._update_incident(
                    incident, type, severity, key, title, body, tags, links, redis_keys, cooldown
                )
            else:
                return await self._open_incident(
                    type, severity, key, title, body, tags, links, redis_keys, dedupe_ttl, cooldown
                )
                
        except Exception as e:
            logger.error(f"Error in AlertManager.send: {e}", exc_info=True)
            return False
    
    async def _open_incident(
        self, type: str, severity: str, key: str, title: str, body: str,
        tags: Dict, links: Dict, redis_keys: Dict, dedupe_ttl: int, cooldown: int
    ) -> bool:
        """Open a new incident"""
        try:
            embed = self._build_embed(severity, title, body, tags, links, count=1, is_open=True)
            
            async with self.rate_limiter:
                message_id = await self._post_to_discord(embed)
            
            if message_id:
                incident = {
                    "type": type,
                    "severity": severity,
                    "key": key,
                    "title": title,
                    "opened_at": datetime.utcnow().isoformat(),
                    "last_sent_at": datetime.utcnow().isoformat(),
                    "last_seen": datetime.utcnow().isoformat(),
                    "discord_message_id": message_id,
                    "count": 1,
                    "tags": tags
                }
                
                self.redis.setex(redis_keys["open"], dedupe_ttl, json.dumps(incident))
                self.redis.setex(redis_keys["cooldown"], cooldown, "1")
                
                logger.info(f"Incident opened: {type}:{key} (message_id={message_id})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error opening incident: {e}", exc_info=True)
            return False
    
    async def _update_incident(
        self, incident: Dict, type: str, severity: str, key: str, title: str,
        body: str, tags: Dict, links: Dict, redis_keys: Dict, cooldown: int
    ) -> bool:
        """Update an existing incident"""
        try:
            incident["count"] = incident.get("count", 1) + 1
            incident["last_sent_at"] = datetime.utcnow().isoformat()
            incident["last_seen"] = datetime.utcnow().isoformat()
            
            embed = self._build_embed(
                severity, title, body, tags, links,
                count=incident["count"],
                opened_at=incident.get("opened_at"),
                is_open=True
            )
            
            message_id = incident.get("discord_message_id")
            if message_id:
                async with self.rate_limiter:
                    success = await self._edit_discord_message(message_id, embed)
                
                if success:
                    self.redis.setex(redis_keys["open"], self.dedupe_ttl, json.dumps(incident))
                    self.redis.setex(redis_keys["cooldown"], cooldown, "1")
                    logger.info(f"Incident updated: {type}:{key} (count={incident['count']})")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating incident: {e}", exc_info=True)
            return False
    
    async def resolve(self, type: str, key: str, resolution_message: str = "Condition resolved") -> bool:
        """Resolve an open incident"""
        redis_keys = self._get_redis_keys(type, key)
        
        try:
            incident_data = self.redis.get(redis_keys["open"])
            if not incident_data:
                logger.debug(f"No open incident to resolve: {type}:{key}")
                return False
            
            incident = json.loads(incident_data)
            
            embed = {
                "title": "✅ Incident Resolved",
                "description": f"**{incident.get('title', type)}**\n\n{resolution_message}",
                "color": 0x00FF00,
                "timestamp": datetime.utcnow().isoformat(),
                "fields": [
                    {
                        "name": "Duration",
                        "value": self._format_duration(incident.get("opened_at")),
                        "inline": True
                    },
                    {
                        "name": "Total Events",
                        "value": f"`{incident.get('count', 1)}`",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": f"AutoTrader v2 • Resolved at {datetime.utcnow().strftime('%H:%M:%S')} UTC"
                }
            }
            
            async with self.rate_limiter:
                await self._post_to_discord(embed)
            
            self.redis.delete(redis_keys["open"])
            self.redis.delete(redis_keys["cooldown"])
            
            logger.info(f"Incident resolved: {type}:{key}")
            return True
            
        except Exception as e:
            logger.error(f"Error resolving incident: {e}", exc_info=True)
            return False
    
    def _build_embed(
        self, severity: str, title: str, body: str, tags: Dict,
        links: Dict, count: int = 1, opened_at: Optional[str] = None,
        is_open: bool = True
    ) -> Dict:
        """Build Discord embed"""
        emoji = self._severity_emoji(severity)
        color = self._severity_color(severity)
        
        embed = {
            "title": f"{emoji} {title}",
            "description": body,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Severity",
                    "value": f"`{severity.upper()}`",
                    "inline": True
                },
                {
                    "name": "Environment",
                    "value": f"`{self.env}`",
                    "inline": True
                }
            ]
        }
        
        if tags:
            for tag_name, tag_value in tags.items():
                embed["fields"].append({
                    "name": tag_name.title(),
                    "value": f"`{tag_value}`",
                    "inline": True
                })
        
        if links:
            links_text = "\n".join([f"[{name}]({url})" for name, url in links.items()])
            embed["fields"].append({
                "name": "Links",
                "value": links_text,
                "inline": False
            })
        
        footer_text = f"AutoTrader v2 Monitoring"
        if is_open and count > 1:
            footer_text += f" • seen {count} times"
        if opened_at:
            footer_text += f" • last at {datetime.utcnow().strftime('%H:%M:%S')}Z"
        
        embed["footer"] = {"text": footer_text}
        
        return embed
    
    async def _post_to_discord(self, embed: Dict) -> Optional[str]:
        """Post embed to Discord and return message ID"""
        try:
            response = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                params={"wait": "true"},
                timeout=10
            )
            
            if response.status_code in (200, 204):
                data = response.json() if response.status_code == 200 else {}
                message_id = data.get("id")
                return message_id
            else:
                logger.error(f"Discord webhook failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error posting to Discord: {e}")
            return None
    
    async def _edit_discord_message(self, message_id: str, embed: Dict) -> bool:
        """Edit an existing Discord message"""
        try:
            webhook_parts = self.webhook_url.split("/")
            if len(webhook_parts) < 2:
                return False
            
            webhook_id = webhook_parts[-2]
            webhook_token = webhook_parts[-1]
            
            edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
            
            response = requests.patch(
                edit_url,
                json={"embeds": [embed]},
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error editing Discord message: {e}")
            return False
    
    def _format_duration(self, start_iso: Optional[str]) -> str:
        """Format duration since incident opened"""
        if not start_iso:
            return "Unknown"
        
        try:
            start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            duration = datetime.utcnow() - start
            
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            
            if hours > 0:
                return f"`{hours}h {minutes}m`"
            else:
                return f"`{minutes}m`"
        except:
            return "Unknown"
    
    async def aggregate_and_flush(self, type: str, key: str) -> bool:
        """
        Aggregate events from the aggregation window and flush a summary.
        Used for burst/chatty alert types like latency spikes.
        """
        redis_keys = self._get_redis_keys(type, key)
        agg_key = redis_keys["agg"]
        
        try:
            agg_data = self.redis.lrange(agg_key, 0, -1)
            if not agg_data:
                return False
            
            events = [json.loads(e) for e in agg_data]
            count = len(events)
            
            first_event = events[0]
            
            summary_lines = []
            event_types = defaultdict(int)
            for event in events:
                event_types[event.get("detail", "unknown")] += 1
            
            for detail, detail_count in sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                summary_lines.append(f"{detail}: {detail_count} events")
            
            summary = "\n".join(summary_lines)
            
            body = f"{count} events in last {self.agg_window}s\n\n{summary}"
            
            await self.send(
                type=type,
                severity=first_event.get("severity", "warning"),
                key=f"{key}_aggregated",
                title=first_event.get("title", "Aggregated Events"),
                body=body,
                tags=first_event.get("tags", {})
            )
            
            self.redis.delete(agg_key)
            
            logger.info(f"Flushed aggregated events: {type}:{key} ({count} events)")
            return True
            
        except Exception as e:
            logger.error(f"Error aggregating events: {e}")
            return False
    
    def add_to_aggregation(self, type: str, key: str, event: Dict):
        """Add an event to the aggregation window"""
        redis_keys = self._get_redis_keys(type, key)
        agg_key = redis_keys["agg"]
        
        try:
            event["timestamp"] = datetime.utcnow().isoformat()
            self.redis.rpush(agg_key, json.dumps(event))
            self.redis.expire(agg_key, self.agg_window + 10)
        except Exception as e:
            logger.error(f"Error adding to aggregation: {e}")
    
    async def send_daily_digest(self):
        """Send daily digest at 09:05 UTC with stats"""
        if not self.enable or not self.webhook_url:
            return False
        
        try:
            open_incidents = await self.get_open_incidents()
            
            severity_counts = {"INFO": 0, "WARN": 0, "CRITICAL": 0}
            top_offenders = []
            
            for incident in open_incidents:
                severity = incident.get("severity", "INFO")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                if incident.get("count", 1) > 5:
                    top_offenders.append({
                        "key": incident.get("key"),
                        "count": incident.get("count"),
                        "severity": severity
                    })
            
            top_offenders.sort(key=lambda x: x["count"], reverse=True)
            
            redis_info = self.redis.info()
            
            embed = {
                "title": "📊 Daily System Digest",
                "color": 0x3498db,
                "fields": [
                    {
                        "name": "Open Incidents",
                        "value": f"Total: {len(open_incidents)}\n"
                                 f"🔴 Critical: {severity_counts['CRITICAL']}\n"
                                 f"🟡 Warning: {severity_counts['WARN']}\n"
                                 f"⚪ Info: {severity_counts['INFO']}",
                        "inline": True
                    },
                    {
                        "name": "Top Offenders (Last 24h)",
                        "value": "\n".join([
                            f"{i+1}. {o['key']}: {o['count']} events ({o['severity']})"
                            for i, o in enumerate(top_offenders[:5])
                        ]) if top_offenders else "None",
                        "inline": True
                    },
                    {
                        "name": "System Health",
                        "value": f"Redis Keys: {redis_info.get('db0', {}).get('keys', 0)}\n"
                                 f"Redis Memory: {redis_info.get('used_memory_human', 'N/A')}\n"
                                 f"Uptime: {redis_info.get('uptime_in_days', 0)} days",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"AutoTrader {self.env} | Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with self.rate_limiter:
                message_id = await self._post_to_discord(embed)
            
            if message_id:
                logger.info("Daily digest sent successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error sending daily digest: {e}", exc_info=True)
            return False

    async def send_heartbeat(self) -> bool:
        """Send heartbeat if alerts were sent in last 24h"""
        try:
            now = datetime.utcnow()
            
            if self.last_heartbeat:
                since_last = (now - self.last_heartbeat).total_seconds() / 60
                if since_last < self.heartbeat_interval:
                    return False
            
            pattern = f"alert:{self.env}:*:open"
            keys = self.redis.keys(pattern)
            
            any_recent_alerts = False
            for key in keys[:10]:
                incident_data = self.redis.get(key)
                if incident_data:
                    incident = json.loads(incident_data)
                    opened_at = datetime.fromisoformat(incident["opened_at"].replace("Z", "+00:00"))
                    age_hours = (now - opened_at).total_seconds() / 3600
                    if age_hours < 24:
                        any_recent_alerts = True
                        break
            
            if not any_recent_alerts:
                logger.debug("No recent alerts in 24h, skipping heartbeat")
                return False
            
            embed = {
                "title": "✅ System Heartbeat",
                "description": "AutoTrader monitoring system is operational",
                "color": 0x00FF00,
                "timestamp": now.isoformat(),
                "fields": [
                    {
                        "name": "Status",
                        "value": "`Healthy`",
                        "inline": True
                    },
                    {
                        "name": "Interval",
                        "value": f"`{self.heartbeat_interval}m`",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": f"AutoTrader v2 • Next heartbeat: {(now + timedelta(minutes=self.heartbeat_interval)).strftime('%H:%M')} UTC"
                }
            }
            
            async with self.rate_limiter:
                await self._post_to_discord(embed)
            
            self.last_heartbeat = now
            logger.info(f"Heartbeat sent at {now.strftime('%H:%M:%S')} UTC")
            return True
            
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return False
    
    def mute(self, severity: str, duration_minutes: int) -> bool:
        """Mute alerts at specified severity for duration"""
        try:
            mute_key = f"alerts:mute:{severity.lower()}:{self.env}"
            self.redis.setex(mute_key, duration_minutes * 60, "1")
            logger.info(f"Muted {severity} alerts for {duration_minutes}m")
            return True
        except Exception as e:
            logger.error(f"Error muting alerts: {e}")
            return False
    
    def unmute(self, severity: str) -> bool:
        """Unmute alerts at specified severity"""
        try:
            mute_key = f"alerts:mute:{severity.lower()}:{self.env}"
            self.redis.delete(mute_key)
            logger.info(f"Unmuted {severity} alerts")
            return True
        except Exception as e:
            logger.error(f"Error unmuting alerts: {e}")
            return False
    
    def get_open_incidents(self) -> List[Dict]:
        """Get all currently open incidents"""
        try:
            pattern = f"alert:{self.env}:*:open"
            keys = self.redis.keys(pattern)
            
            incidents = []
            for key in keys:
                incident_data = self.redis.get(key)
                if incident_data:
                    incident = json.loads(incident_data)
                    incidents.append(incident)
            
            incidents.sort(key=lambda x: x.get("opened_at", ""), reverse=True)
            return incidents
            
        except Exception as e:
            logger.error(f"Error getting open incidents: {e}")
            return []
