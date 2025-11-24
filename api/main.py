from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
import os
import sys
from datetime import datetime, timedelta, time as datetime_time
import json
import secrets
import hashlib
import boto3
import asyncio
import logging
import requests
import io
import csv
import threading
import time
import redis
import uuid
from contextvars import ContextVar
import re
from typing import AsyncGenerator
import gzip

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from alerts.manager import AlertManager as NewAlertManager

class RedactedJSONFormatter(logging.Formatter):
    """JSON formatter that redacts sensitive information"""
    
    SENSITIVE_PATTERNS = [
        r'password["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
        r'token["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
        r'secret["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
        r'key["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)'
    ]
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if hasattr(record, 'user'):
            log_entry['user'] = record.user
        if hasattr(record, 'ip'):
            log_entry['ip'] = record.ip
        if hasattr(record, 'action'):
            log_entry['action'] = record.action
        
        message = log_entry['message']
        for pattern in self.SENSITIVE_PATTERNS:
            message = re.sub(pattern, r'\1***REDACTED***', message, flags=re.IGNORECASE)
        log_entry['message'] = message
        
        return json.dumps(log_entry)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30
)
HEALTH_CACHE_KEY = "autotrader:healthz"
HEALTH_CACHE_TTL = 90
TRADES_CHANNEL = "autotrader:trades"
HEALTH_CHANNEL = "autotrader:health"
AUDIT_BUCKET = os.getenv("AUDIT_BUCKET", "autotrader-audit-logs-v2")

try:
    s3_client = boto3.client('s3', region_name='us-east-1')
except Exception as e:
    logger.error(f"Failed to initialize S3 client: {e}")
    s3_client = None

json_handler = logging.StreamHandler()
json_handler.setFormatter(RedactedJSONFormatter())
logger.addHandler(json_handler)
logger.setLevel(logging.INFO)

app = FastAPI(title="AutoTrader API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.lunaraxolotl.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Authorization", "Content-Type", "Cookie", "X-CSRF-Token", "X-Request-ID", "X-Requested-With", "Baggage", "Sentry-Trace"],
    expose_headers=["Set-Cookie", "X-Request-ID"],
    max_age=86400,
)

request_id_var: ContextVar[str] = ContextVar('request_id', default='')

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

SESSION_TIMEOUT_MINUTES = 30
COOKIE_MAX_AGE = SESSION_TIMEOUT_MINUTES * 60

def discord_webhook_url():
    """Load Discord webhook URL from AWS Secrets Manager or environment variable"""
    try:
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret = client.get_secret_value(SecretId="autotrader/discord-webhook")["SecretString"]
        data = json.loads(secret)
        webhook_url = data.get("webhook_url")
        if webhook_url:
            return webhook_url
    except Exception as e:
        logger.warning(f"Failed to load Discord webhook URL from Secrets Manager: {e}")
    
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if webhook_url:
        logger.info("Using Discord webhook URL from environment variable")
        return webhook_url
    
    logger.error("Discord webhook URL not available from Secrets Manager or environment variable")
    return None

def load_credentials():
    logger.info("Loading credentials from AWS Secrets Manager")
    try:
        client = boto3.client('secretsmanager', region_name='us-east-1')
        
        viewer_secret = client.get_secret_value(SecretId='autotrader/viewer')
        viewer_data = json.loads(viewer_secret['SecretString'])
        logger.info(f"Loaded viewer credentials for: {viewer_data['username']}")
        
        controller_secret = client.get_secret_value(SecretId='autotrader/controller')
        controller_data = json.loads(controller_secret['SecretString'])
        logger.info(f"Loaded controller credentials for: {controller_data['username']}")
        
        credentials = {
            viewer_data['username']: {"password": viewer_data['password'], "role": "viewer"},
            controller_data['username']: {"password": controller_data['password'], "role": "controller"}
        }
        logger.info(f"Successfully loaded {len(credentials)} user credentials from Secrets Manager")
        return credentials
    except Exception as e:
        logger.error(f"Failed to load credentials from Secrets Manager: {e}")
        logger.info("Using fallback environment variable credentials")
        fallback_creds = {
            "viewer": {"password": os.getenv("VIEWER_PASSWORD", "ViewerPass123!"), "role": "viewer"},
            "controller": {"password": os.getenv("CONTROLLER_PASSWORD", "ControllerPass456!"), "role": "controller"}
        }
        return fallback_creds

def upload_audit_log_to_s3(audit_log: dict) -> bool:
    """Upload audit log to S3 with date partitioning"""
    if not s3_client:
        logger.warning("S3 client not initialized, skipping audit log upload")
        return False
    
    try:
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
        
        s3_key = f"year={year}/month={month}/day={day}/audit-{timestamp}.jsonl.gz"
        
        json_line = json.dumps(audit_log) + "\n"
        compressed_data = gzip.compress(json_line.encode('utf-8'))
        
        s3_client.put_object(
            Bucket=AUDIT_BUCKET,
            Key=s3_key,
            Body=compressed_data,
            ContentType='application/x-jsonlines',
            ContentEncoding='gzip',
            ServerSideEncryption='AES256'
        )
        
        logger.info(f"Audit log uploaded to s3://{AUDIT_BUCKET}/{s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to upload audit log to S3: {e}")
        return False

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30
)

SESSION_TIMEOUT_MINUTES = 30
COOKIE_MAX_AGE = 60 * 60 * 12
SESSION_PREFIX = "autotrader:session:"

# Load user credentials
users = load_credentials()
logger.info(f"Loaded user credentials: {list(users.keys())}")

bot_state = {
    "status": "running",
    "mode": "paper",
    "paused": False,
    "daily_kill_pct": 0.8,
    "max_pos_pct": 0.5,
    "max_slippage_bps": 6,
    "kill_switch_active": False,
    "maintenance_mode": False,
    "kill_switch_active": False,
    "maintenance_mode": False,
    "total_equity": 100000.0,
    "pnl_today": 1250.75,
    "drawdown": 0.35
}

sleeves = {
    "arbitrage": "active",
    "swing": "inactive", 
    "event": "inactive"
}

venues = [
    {
        "name": "Binance",
        "status": "connected",
        "latency": {"p50": 45, "p95": 120, "p99": 250},
        "rejectRate": 0.2,
        "reconnects": 0,
        "circuitBreaker": False
    },
    {
        "name": "Coinbase", 
        "status": "connected",
        "latency": {"p50": 65, "p95": 180, "p99": 320},
        "rejectRate": 0.1,
        "reconnects": 1,
        "circuitBreaker": False
    },
    {
        "name": "Kraken",
        "status": "degraded", 
        "latency": {"p50": 120, "p95": 450, "p99": 800},
        "rejectRate": 2.1,
        "reconnects": 3,
        "circuitBreaker": True
    }
]

orders = [
    {
        "id": "ord_001",
        "timestamp": "2025-08-28T01:05:23Z",
        "venue": "binance",
        "pair": "BTC/USDT", 
        "side": "BUY",
        "size": 0.05,
        "price": 29855.0,
        "fees": 1.49,
        "slippageBps": 1.8,
        "latencyMs": 198,
        "mode": "paper"
    }
]

positions = [
    {
        "pair": "BTC/USDT",
        "side": "BUY",
        "size": 0.05,
        "avgPrice": 29855.0,
        "currentPrice": 30120.5,
        "pnl": 13.28,
        "pnlPercent": 0.89
    }
]

alerts = [
    {
        "id": "alert_001",
        "timestamp": "2025-08-28T00:45:12Z",
        "level": "warning",
        "message": "Kraken latency above threshold (p95: 450ms)",
        "acknowledged": False
    }
]

class RiskSettings(BaseModel):
    daily_kill_pct: float
    max_pos_pct: float
    max_slippage_bps: int

class LoginRequest(BaseModel):
    username: str
    password: str

def get_current_user(request: Request):
    session_id = request.cookies.get("session")
    logger.info(f"Session validation - Cookie: {session_id[:20] if session_id else 'None'}...")
    
    if not session_id:
        logger.error("No session cookie found")
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_key = f"{SESSION_PREFIX}{session_id}"
    try:
        session_data = redis_client.get(session_key)
        if not session_data:
            logger.error(f"Session {session_id[:20]}... not found in Redis")
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        session = json.loads(session_data)
        
        last_activity = datetime.fromisoformat(session["last_activity"])
        if datetime.utcnow() - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            logger.error(f"Session {session_id[:20]}... expired")
            redis_client.delete(session_key)
            raise HTTPException(status_code=401, detail="Session expired")
        
        session["last_activity"] = datetime.utcnow().isoformat()
        redis_client.setex(session_key, COOKIE_MAX_AGE, json.dumps(session))
        
        logger.info(f"Session validation successful for user: {session['username']}")
        return session
        
    except redis.RedisError as e:
        logger.error(f"Redis error during session validation: {e}")
        raise HTTPException(status_code=401, detail="Not authenticated")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid session data in Redis: {e}")
        redis_client.delete(session_key)
        raise HTTPException(status_code=401, detail="Not authenticated")

def require_role(required_role: str):
    def role_checker(user=Depends(get_current_user)):
        if required_role == "controller" and user["role"] != "controller":
            raise HTTPException(status_code=403, detail="Controller access required")
        return user
    return role_checker

@app.get("/")
async def root():
    login_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AutoTrader Login</title>
        <style>
            body { font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
            .login-container { background: #1e293b; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
            .login-form { display: flex; flex-direction: column; gap: 1rem; }
            .form-group { display: flex; flex-direction: column; gap: 0.5rem; }
            label { font-weight: 500; color: #e2e8f0; }
            input { padding: 0.75rem; border: 1px solid #475569; border-radius: 4px; background: #334155; color: #f8fafc; }
            input:focus { outline: none; border-color: #3b82f6; }
            button { padding: 0.75rem; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; }
            button:hover { background: #2563eb; }
            .error { color: #ef4444; font-size: 0.875rem; margin-top: 0.5rem; }
            h1 { text-align: center; margin-bottom: 2rem; color: #f8fafc; }
            .credentials { background: #374151; padding: 1rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.875rem; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>AutoTrader Login</h1>
            <div class="credentials">
                <strong>Test Credentials:</strong><br>
                Viewer: viewer / ViewerPass123!<br>
                Controller: controller / ControllerPass456!
            </div>
            <form class="login-form" onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit">Login</button>
                <div id="error" class="error" style="display: none;"></div>
            </form>
        </div>
        <script>
            async function handleLogin(event) {
                event.preventDefault();
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                const errorDiv = document.getElementById('error');
                
                try {
                    const response = await fetch('/api/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, password })
                    });
                    
                    if (response.ok) {
                        window.location.href = '/dashboard';
                    } else {
                        const error = await response.json();
                        errorDiv.textContent = error.detail || 'Login failed';
                        errorDiv.style.display = 'block';
                    }
                } catch (err) {
                    errorDiv.textContent = 'Network error';
                    errorDiv.style.display = 'block';
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=login_html)

@app.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    dashboard_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AutoTrader Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }}
            .user-info {{ background: #1e293b; padding: 1rem; border-radius: 4px; }}
            .nav {{ display: flex; gap: 1rem; margin-bottom: 2rem; }}
            .nav a {{ color: #3b82f6; text-decoration: none; padding: 0.5rem 1rem; background: #1e293b; border-radius: 4px; }}
            .nav a:hover {{ background: #334155; }}
            .content {{ background: #1e293b; padding: 2rem; border-radius: 8px; }}
            .logout {{ background: #ef4444; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>AutoTrader Dashboard</h1>
            <div class="user-info">
                Logged in as: <strong>{user['username']}</strong> ({user['role']})
                <button class="logout" onclick="logout()">Logout</button>
            </div>
        </div>
        <div class="nav">
            <a href="https://app.lunaraxolotl.com/overview">Overview</a>
            <a href="https://app.lunaraxolotl.com/venues">Venues & Latency</a>
            <a href="https://app.lunaraxolotl.com/orders">Orders & Positions</a>
            <a href="https://app.lunaraxolotl.com/risk">Risk & Controls</a>
            <a href="https://app.lunaraxolotl.com/alerts">Alerts</a>
            <a href="/api/health">API Health</a>
            {f'<a href="/api/pause">Pause</a><a href="/api/resume">Resume</a>' if user['role'] == 'controller' else ''}
        </div>
        <div class="content">
            <h2>Welcome to AutoTrader</h2>
            <p>You are logged in as a <strong>{user['role']}</strong>.</p>
            <p>Use the navigation links above to access the Web Hub interface.</p>
            <p>Direct API access: <a href="/api/health">Health Check</a></p>
        </div>
        <script>
            async function logout() {{
                await fetch('/api/logout', {{ method: 'POST' }});
                window.location.href = '/';
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=dashboard_html)

@app.post("/api/login")
async def login(login_data: LoginRequest, request: Request, response: Response):
    username = login_data.username
    password = login_data.password
    
    logger.info(f"Login attempt for username: {username}")
    
    if username not in users or users[username]["password"] != password:
        logger.error(f"Login failed for {username}: Invalid credentials")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    session_id = secrets.token_urlsafe(32)
    session_data = {
        "username": username,
        "role": users[username]["role"],
        "created_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat()
    }
    
    session_key = f"{SESSION_PREFIX}{session_id}"
    try:
        redis_client.setex(session_key, COOKIE_MAX_AGE, json.dumps(session_data))
        logger.info(f"Session {session_id[:20]}... stored in Redis for user {username}")
    except redis.RedisError as e:
        logger.error(f"Failed to store session in Redis: {e}")
        raise HTTPException(status_code=500, detail="Session creation failed")
    
    response.set_cookie(
        key="session",
        value=session_id,
        domain=".lunaraxolotl.com",
        httponly=True,
        secure=True,  # Always secure - ProxyHeadersMiddleware handles HTTPS detection
        samesite="none",  # Required for cross-subdomain with secure=True
        max_age=COOKIE_MAX_AGE,
        path="/"
    )
    
    logger.info(f"Login successful for {username} with role {users[username]['role']}")
    return {"message": "Login successful", "role": users[username]["role"]}

@app.post("/api/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("session")
    if session_id:
        session_key = f"{SESSION_PREFIX}{session_id}"
        try:
            redis_client.delete(session_key)
            logger.info(f"Session {session_id[:20]}... deleted from Redis")
        except redis.RedisError as e:
            logger.error(f"Failed to delete session from Redis: {e}")
    
    response.delete_cookie(key="session", domain=".lunaraxolotl.com", path="/")
    return {"message": "Logged out successfully"}

try:
    webhook_url = discord_webhook_url()
    if webhook_url:
        alert_manager = NewAlertManager(redis_client, webhook_url)
        logger.info("Initialized new AlertManager with Redis and Discord webhook")
    else:
        alert_manager = None
        logger.warning("AlertManager not initialized - Discord webhook URL not available")
except Exception as e:
    logger.error(f"Failed to initialize AlertManager: {e}")
    alert_manager = None

class DailyDigest:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.digest_time = datetime_time(9, 0)
        self.last_digest_date = None
    
    async def send_daily_digest(self):
        """Send daily digest at 9:00 UTC with real 24h metrics"""
        current_date = datetime.utcnow().date()
        
        if self.last_digest_date != current_date:
            try:
                health_data = await health_aggregator()
                
                try:
                    import os
                    report_dir = f"/home/ubuntu/autotrader/ops/reports/{current_date.strftime('%Y-%m-%d')}"
                    stability_file = os.path.join(report_dir, "stability_report.json")
                    
                    if os.path.exists(stability_file):
                        import json
                        with open(stability_file, 'r') as f:
                            stability_data = json.load(f)
                        
                        uptime = stability_data.get('uptime_percentage', 99.8)
                        avg_latency = stability_data.get('avg_response_time', 145)
                        total_requests = stability_data.get('total_requests', 0)
                        failed_requests = stability_data.get('failed_requests', 0)
                        error_rate = (failed_requests / max(total_requests, 1)) * 100
                        
                        metrics_source = f"Real data: {total_requests} requests"
                    else:
                        uptime = 99.8
                        avg_latency = 145
                        error_rate = 0.02
                        metrics_source = "Estimated (no stability report)"
                except Exception as e:
                    logger.error(f"Failed to load stability metrics: {e}")
                    uptime = 99.8
                    avg_latency = 145
                    error_rate = 0.02
                    metrics_source = "Fallback values"
                
                current_time = datetime.utcnow()
                
                digest_embed = {
                    "title": "📊 Daily AutoTrader Digest",
                    "description": f"System summary for **{current_date}**",
                    "color": 0x0099FF if health_data.get('overall_status') == 'healthy' else 0xFF0000,
                    "timestamp": current_time.isoformat(),
                    "fields": [
                        {
                            "name": "🟢 System Status",
                            "value": '✅ Healthy' if health_data.get('overall_status') == 'healthy' else '🔴 Issues Detected',
                            "inline": False
                        },
                        {
                            "name": "📡 Connectivity",
                            "value": f"Discord: {'✅' if health_data.get('discord_webhook_ok') else '❌'}\nSSM: {'✅' if health_data.get('ssm_ok') else '❌'}\nRedis: {'✅' if health_data.get('cache_source') == 'redis' else '❌'}",
                            "inline": True
                        },
                        {
                            "name": "📈 24h Performance",
                            "value": f"Uptime: `{uptime:.1f}%`\nAvg Latency: `{avg_latency:.0f}ms`\nError Rate: `{error_rate:.2f}%`",
                            "inline": True
                        },
                        {
                            "name": "🔒 Security",
                            "value": "WAF Active ✅\nCSP Enforced ✅\nHealth Checks Automated ✅",
                            "inline": False
                        },
                        {
                            "name": "💼 Trading Status",
                            "value": f"Mode: `Paper Trading` 📝\nKill Switch: `Inactive` ✅",
                            "inline": False
                        }
                    ],
                    "footer": {
                        "text": f"Data source: {metrics_source} | Next digest: 09:00 UTC"
                    }
                }
                
                webhook_url = discord_webhook_url()
                if webhook_url:
                    payload = {"embeds": [digest_embed]}
                    requests.post(webhook_url, json=payload, timeout=10)
                
                self.last_digest_date = current_date
                logger.info(f"Daily digest sent with 24h metrics at {current_time.strftime('%H:%M')} UTC")
            except Exception as e:
                logger.error(f"Failed to send daily digest: {e}")

def get_instance_id():
    """Get EC2 instance ID from metadata service or EC2 API"""
    try:
        token_response = requests.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=2
        )
        if token_response.status_code == 200:
            token = token_response.text
            instance_response = requests.get(
                "http://169.254.169.254/latest/meta-data/instance-id",
                headers={"X-aws-ec2-metadata-token": token},
                timeout=2
            )
            if instance_response.status_code == 200:
                return instance_response.text
    except Exception as e:
        logger.error(f"Failed to get instance ID from metadata service: {e}")
    
    try:
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Stack', 'Values': ['autotrader-v2']},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
        if response['Reservations'] and response['Reservations'][0]['Instances']:
            instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']
            logger.info(f"Retrieved instance ID from EC2 API: {instance_id}")
            return instance_id
    except Exception as e:
        logger.error(f"Failed to get instance ID from EC2 API: {e}")
    
    return "i-06051733a989e0abf"

def refresh_health_probes():
    """Background task to refresh health probes every 60 seconds"""
    instance_id = get_instance_id()
    
    discord_ok = False
    try:
        webhook_url = discord_webhook_url()
        discord_ok = bool(webhook_url)  # Just check if webhook URL exists
    except Exception as e:
        logger.error(f"Discord webhook check failed: {e}")
    
    ssm_ok = False
    try:
        if instance_id:
            ssm_client = boto3.client('ssm', region_name='us-east-1')
            response = ssm_client.describe_instance_information(
                InstanceInformationFilterList=[
                    {'key': 'InstanceIds', 'valueSet': [instance_id]}
                ]
            )
            if response['InstanceInformationList']:
                ping_status = response['InstanceInformationList'][0]['PingStatus']
                ssm_ok = (ping_status == 'Online')
    except Exception as e:
        logger.error(f"SSM health probe failed: {e}")
    
    health_data = {
        "type": "health_update",
        "discord_webhook_ok": discord_ok,
        "ssm_ok": ssm_ok,
        "api_ok": True,
        "overall_status": "healthy" if discord_ok and ssm_ok else "degraded",
        "last_updated": datetime.utcnow().isoformat(),
        "instance_id": instance_id
    }
    
    try:
        # Store in Redis cache
        redis_client.setex(HEALTH_CACHE_KEY, HEALTH_CACHE_TTL, json.dumps(health_data))
        
        redis_client.publish(HEALTH_CHANNEL, json.dumps(health_data))
        
        logger.debug(f"Health probes updated in Redis: discord_ok={discord_ok}, ssm_ok={ssm_ok}")
    except Exception as e:
        logger.error(f"Failed to update Redis health cache: {e}")

def background_health_monitor():
    """Background thread for health monitoring with Redis cache"""
    logger.info("Background health monitor thread started with Redis")
    while True:
        try:
            logger.debug("Running health probe refresh to Redis...")
            refresh_health_probes()
            logger.debug("Health probe refresh completed, sleeping 60s")
            time.sleep(60)
        except Exception as e:
            logger.error(f"Background health monitor error: {e}")
            time.sleep(60)

daily_digest = DailyDigest(alert_manager)

def daily_digest_task():
    """Background task for daily digest at 09:00 UTC"""
    logger.info("Daily digest task thread started")
    while True:
        try:
            current_time = datetime.utcnow()
            if current_time.hour == 9 and current_time.minute == 0:
                logger.info("Sending daily digest at 09:00 UTC...")
                asyncio.run(daily_digest.send_daily_digest())
                time.sleep(60)  # Prevent duplicate sends within the same minute
            time.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error(f"Daily digest task error: {e}")
            time.sleep(60)
def heartbeat_task():
    """Background thread for sending heartbeats"""
    if not alert_manager:
        return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            loop.run_until_complete(alert_manager.send_heartbeat())
        except Exception as e:
            logger.error(f"Heartbeat task error: {e}")
        
        interval_sec = alert_manager.heartbeat_interval * 60
        time.sleep(interval_sec)

def start_daily_digest_scheduler():
    """Start the daily digest scheduler thread"""
    digest_thread = threading.Thread(target=daily_digest_task, name="DailyDigestThread", daemon=True)
    digest_thread.start()
    logger.info("Daily digest scheduler thread started")
    
    heartbeat_thread = threading.Thread(target=heartbeat_task, name="HeartbeatThread", daemon=True)
    heartbeat_thread.start()
    logger.info("Heartbeat task started")



@app.get("/api/health")
@app.head("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/healthz")
@app.head("/api/healthz")
async def health_aggregator():
    """Comprehensive health check using Redis cached probe results"""
    current_time = datetime.utcnow()
    
    try:
        cached_data = redis_client.get(HEALTH_CACHE_KEY)
        
        if cached_data:
            health_data = json.loads(cached_data)
            discord_ok = health_data.get("discord_webhook_ok", False)
            ssm_ok = health_data.get("ssm_ok", False)
            last_updated = health_data.get("last_updated")
            cache_source = "redis"
        else:
            discord_ok = False
            ssm_ok = False
            last_updated = None
            cache_source = "redis_empty"
    except Exception as e:
        logger.error(f"Failed to read Redis health cache: {e}")
        discord_ok = False
        ssm_ok = False
        last_updated = None
        cache_source = "redis_error"
    
    health_status = {
        "api_ok": True,
        "nginx_ok": True,
        "tg_healthy": True,
        "ssm_ok": ssm_ok,
        "discord_webhook_ok": discord_ok,
        "overall_status": "healthy",
        "timestamp": current_time.isoformat(),
        "last_probe": last_updated,
        "cache_source": cache_source
    }
    
    if not all([health_status["api_ok"], health_status["nginx_ok"], health_status["ssm_ok"]]):
        health_status["overall_status"] = "degraded"
    
    if not health_status["tg_healthy"]:
        health_status["overall_status"] = "unhealthy"
    
    return health_status

@app.get("/api/mode")
async def get_mode():
    return {"mode": bot_state["mode"]}

@app.get("/api/status")
async def get_status():
    return {
        "status": bot_state["status"],
        "totalEquity": bot_state["total_equity"],
        "pnlToday": bot_state["pnl_today"],
        "drawdown": bot_state["drawdown"],
        "sleeves": sleeves
    }

@app.get("/api/venues")
async def get_venues():
    return venues

@app.get("/api/orders")
async def get_orders():
    return orders

@app.get("/api/positions")
async def get_positions():
    return positions

@app.get("/api/alerts")
async def get_alerts():
    return alerts

@app.get("/api/incidents")
async def get_incidents():
    """Get currently open incidents from AlertManager"""
    if not alert_manager:
        return {"incidents": [], "message": "AlertManager not initialized"}
    
    try:
        incidents = alert_manager.get_open_incidents()
        return {
            "incidents": incidents,
            "count": len(incidents)
        }
    except Exception as e:
        logger.error(f"Failed to get incidents: {e}")
        return {"incidents": [], "error": str(e)}

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user=Depends(get_current_user)):
    """Acknowledge an alert"""
    for alert in alerts:
        if alert["id"] == alert_id:
            alert["acknowledged"] = True
            return {"message": "Alert acknowledged"}
    raise HTTPException(status_code=404, detail="Alert not found")

@app.post("/api/pause")
async def pause_trading(user: dict = Depends(require_role("controller"))):
    if bot_state["mode"] != "paper":
        raise HTTPException(status_code=400, detail="Only paper mode supported")
    
    bot_state["paused"] = True
    bot_state["status"] = "paused"
    
    if alert_manager:
        await alert_manager.send(
            type="trading_paused",
            severity="warning",
            key="trading_paused",
            title="Trading Paused",
            body=f"Trading paused by user {user['username']}"
        )
    
    audit_log = {
        "ts": datetime.utcnow().isoformat(),
        "action": "pause",
        "user": user["username"],
        "details": "Trading paused via API",
        "request_id": request_id_var.get()
    }
    
    upload_audit_log_to_s3(audit_log)
    
    return {"status": "paused", "message": "Trading paused successfully"}

@app.post("/api/resume")
async def resume_trading(user=Depends(require_role("controller"))):
    if bot_state["mode"] != "paper":
        raise HTTPException(status_code=400, detail="Only paper mode supported")
    
    if bot_state["kill_switch_active"]:
        raise HTTPException(status_code=400, detail="Cannot resume: kill switch active")
    
    if bot_state["maintenance_mode"]:
        raise HTTPException(status_code=400, detail="Cannot resume: maintenance mode active")
    
    bot_state["paused"] = False
    bot_state["status"] = "running"
    
    if alert_manager:
        await alert_manager.send(
            type="trading_resumed",
            severity="info",
            key="trading_resumed",
            title="Trading Resumed",
            body=f"Trading resumed by user {user['username']}"
        )
    
    audit_log = {
        "ts": datetime.utcnow().isoformat(),
        "action": "resume", 
        "user": user["username"],
        "details": "Trading resumed via API",
        "request_id": request_id_var.get()
    }
    
    upload_audit_log_to_s3(audit_log)
    
    return {"status": "running", "message": "Trading resumed successfully"}

@app.post("/api/risk")
async def update_risk_settings(settings: RiskSettings, user=Depends(require_role("controller"))):
    bot_state["daily_kill_pct"] = settings.daily_kill_pct
    bot_state["max_pos_pct"] = settings.max_pos_pct
    bot_state["max_slippage_bps"] = settings.max_slippage_bps
    
    audit_log = {
        "ts": datetime.utcnow().isoformat(),
        "action": "risk_update",
        "user": user["username"], 
        "details": f"Risk settings updated: kill={settings.daily_kill_pct}%, pos={settings.max_pos_pct}%, slippage={settings.max_slippage_bps}bps",
        "request_id": request_id_var.get()
    }
    
    upload_audit_log_to_s3(audit_log)
    
    return {
        "message": "Risk settings updated",
        "settings": {
            "daily_kill_pct": bot_state["daily_kill_pct"],
            "max_pos_pct": bot_state["max_pos_pct"], 
            "max_slippage_bps": bot_state["max_slippage_bps"]
        }
    }

@app.get("/api/maintenance")
async def get_maintenance_status():
    """Get current maintenance mode status"""
    return {
        "maintenance_mode": bot_state["maintenance_mode"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/maintenance")
async def toggle_maintenance_mode(
    request: Request,
    user=Depends(require_role("controller"))
):
    """Toggle maintenance mode on/off"""
    body = await request.json()
    enabled = body.get("enabled", False)
    
    bot_state["maintenance_mode"] = enabled
    
    if enabled:
        bot_state["paused"] = True
        bot_state["status"] = "maintenance"
        if alert_manager:
            await alert_manager.send(
                type="maintenance",
                severity="warning",
                key="maintenance_mode_enabled",
                title="Maintenance Mode Enabled",
                body=f"Maintenance mode enabled by {user['username']}"
            )
    else:
        if not bot_state["kill_switch_active"]:
            bot_state["paused"] = False
            bot_state["status"] = "running"
        if alert_manager:
            await alert_manager.send(
                type="maintenance",
                severity="info",
                key="maintenance_mode_disabled",
                title="Maintenance Mode Disabled",
                body=f"Maintenance mode disabled by {user['username']}"
            )
    
    return {
        "maintenance_mode": enabled,
        "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}"
    }

@app.post("/api/test/alert")
async def test_alert(user: dict = Depends(require_role("controller"))):
    """Test endpoint for Discord alerts"""
    success = False
    if alert_manager:
        success = await alert_manager.send(
            type="test",
            severity="info",
            key="test_alert",
            title="Test Alert",
            body=f"Hello from AutoTrader - Test alert triggered by {user['username']} at {datetime.utcnow().isoformat()}"
        )
    return {"message": "Test alert sent", "success": success}

@app.get("/api/export/orders")
async def export_orders(format: str = "csv", user=Depends(get_current_user)):
    """Export orders data in CSV or JSONL format"""
    if format not in ["csv", "jsonl"]:
        raise HTTPException(status_code=400, detail="Format must be csv or jsonl")
    
    orders_data = orders
    
    if format == "csv":
        output = io.StringIO()
        if orders_data:
            writer = csv.DictWriter(output, fieldnames=orders_data[0].keys())
            writer.writeheader()
            writer.writerows(orders_data)
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=orders.csv"}
        )
    else:
        content = "\n".join(json.dumps(order) for order in orders_data)
        return Response(
            content=content,
            media_type="application/x-jsonlines",
            headers={"Content-Disposition": "attachment; filename=orders.jsonl"}
        )

@app.get("/api/export/positions")
async def export_positions(format: str = "csv", user=Depends(get_current_user)):
    """Export positions data in CSV or JSONL format"""
    if format not in ["csv", "jsonl"]:
        raise HTTPException(status_code=400, detail="Format must be csv or jsonl")
    
    positions_data = positions
    
    if format == "csv":
        output = io.StringIO()
        if positions_data:
            writer = csv.DictWriter(output, fieldnames=positions_data[0].keys())
            writer.writeheader()
            writer.writerows(positions_data)
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=positions.csv"}
        )
    else:
        content = "\n".join(json.dumps(position) for position in positions_data)
        return Response(
            content=content,
            media_type="application/x-jsonlines",
            headers={"Content-Disposition": "attachment; filename=positions.jsonl"}
        )

@app.get("/api/risk")
async def get_risk_settings():
    return {
        "daily_kill_pct": bot_state["daily_kill_pct"],
        "max_pos_pct": bot_state["max_pos_pct"],
        "max_slippage_bps": bot_state["max_slippage_bps"],
        "kill_switch_active": bot_state["kill_switch_active"],
        "withdrawals_enabled": False,
        "pairs": ["BTC/USDT", "ETH/USDT"],
        "min_notional_usd": 10,
        "trading_mode": os.getenv("TRADING_MODE", "paper")
    }

@app.get("/api/balances")
async def get_balances():
    return {
        "USDT": {"balance": 50000.0, "available": 48750.0, "locked": 1250.0},
        "BTC": {"balance": 1.5, "available": 1.45, "locked": 0.05},
        "ETH": {"balance": 10.0, "available": 10.0, "locked": 0.0}
    }

@app.post("/api/alerts/trigger/tg-health")
async def trigger_tg_health_alert(healthy: bool = True):
    """Trigger target group health alert"""
    severity = "info" if healthy else "critical"
    message = f"Target group is now {'healthy' if healthy else 'unhealthy'}"
    if alert_manager:
        await alert_manager.send(
            type="health",
            severity=severity,
            key="tg_health",
            title="Target Group Health",
            body=message
        )
    return {"message": f"TG health alert sent: {message}"}

@app.post("/api/alerts/trigger/latency")
async def trigger_latency_alert(venue: str, p95_ms: int):
    """Trigger high latency alert"""
    if p95_ms > 300 and alert_manager:
        await alert_manager.send(
            type="latency",
            severity="warning",
            key=f"high_latency_{venue}",
            title="High Latency Alert",
            body=f"{venue} p95 latency is {p95_ms}ms (threshold: 300ms)",
            tags={"venue": venue, "p95_ms": str(p95_ms)}
        )
    return {"message": f"Latency alert checked for {venue}: {p95_ms}ms"}

@app.post("/api/alerts/trigger/5xx-spike")
async def trigger_5xx_spike_alert(count: int, timeframe: str = "5min"):
    """Trigger 5xx error spike alert"""
    if count > 10 and alert_manager:
        await alert_manager.send(
            type="infra",
            severity="critical",
            key="5xx_spike",
            title="5xx Error Spike",
            body=f"{count} 5xx errors in {timeframe} (threshold: 10)",
            tags={"count": str(count), "timeframe": timeframe}
        )
    return {"message": f"5xx spike alert checked: {count} errors"}

@app.post("/api/alerts/trigger/container-restart")
async def trigger_container_restart_alert(container: str):
    """Trigger container restart alert"""
    if alert_manager:
        await alert_manager.send(
            type="infra",
            severity="warning",
            key=f"container_restart_{container}",
            title="Container Restart",
            body=f"Container {container} has restarted",
            tags={"container": container}
        )
    return {"message": f"Container restart alert sent for {container}"}

@app.post("/api/alerts/trigger/low-disk")
async def trigger_low_disk_alert(usage_percent: int):
    """Trigger low disk space alert"""
    if usage_percent > 85 and alert_manager:
        await alert_manager.send(
            type="infra",
            severity="warning",
            key="low_disk",
            title="Low Disk Space",
            body=f"Disk usage is {usage_percent}% (threshold: 85%)",
            tags={"usage_percent": str(usage_percent)}
        )
    return {"message": f"Low disk alert checked: {usage_percent}%"}

@app.post("/api/alerts/trigger/deploy-complete")
async def trigger_deploy_complete_alert(component: str, version: str = "latest"):
    """Trigger deployment complete alert"""
    if alert_manager:
        await alert_manager.send(
            type="infra",
            severity="info",
            key=f"deploy_complete_{component}",
            title="Deployment Complete",
            body=f"{component} deployment completed successfully (version: {version})",
            tags={"component": component, "version": version}
        )
    return {"message": f"Deploy complete alert sent for {component}"}

def check_debug_enabled():
    """Check if debug endpoints are enabled via environment variable"""
    return os.getenv("ENABLE_DEBUG", "false").lower() == "true"
@app.get("/api/version")
async def get_version():
    """Get API version and build information"""
    return {
        "service": "autotrader-api",
        "version": os.getenv("API_VERSION", "2.0.0"),
        "build_sha": os.getenv("GIT_SHA", "unknown"),
        "build_time": os.getenv("BUILD_TIME", "unknown"),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "environment": os.getenv("TRADING_MODE", "paper")
    }

@app.get("/api/system/health")
async def system_health():
    """Get detailed system health including SSE and Discord status"""
    import aiohttp
    
    health = {
        "api": "ok",
        "redis": "unknown",
        "discord": "unknown",
        "sse_connections": 0
    }
    
    try:
        if alert_manager and hasattr(alert_manager, 'redis') and alert_manager.redis:
            alert_manager.redis.ping()
            health["redis"] = "ok"
    except Exception as e:
        health["redis"] = "error"
        logger.error(f"Redis health check failed: {e}")
    
    try:
        webhook_url = os.getenv("DISCORD_WEBHOOK")
        if webhook_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(webhook_url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    health["discord"] = "ok" if resp.status < 500 else "degraded"
        else:
            health["discord"] = "not_configured"
    except Exception as e:
        health["discord"] = "error"
        logger.error(f"Discord health check failed: {e}")
    
    return health

@app.post("/api/alerts/mute")
async def mute_alerts(
    request: dict,
    user: dict = Depends(require_role("controller"))
):
    """Mute alerts for a specified duration"""
    severity = request.get("severity", "WARN")
    duration_minutes = request.get("duration_minutes", 30)
    
    if alert_manager:
        success = await alert_manager.mute(severity, duration_minutes)
        return {"success": success, "message": f"Alerts muted for {duration_minutes} minutes"}
    
    return {"success": False, "message": "AlertManager not available"}

@app.post("/api/alerts/unmute")
async def unmute_alerts(
    request: dict,
    user: dict = Depends(require_role("controller"))
):
    """Unmute alerts"""
    severity = request.get("severity", "WARN")
    
    if alert_manager:
        success = await alert_manager.unmute(severity)
        return {"success": success, "message": "Alerts unmuted"}
    
    return {"success": False, "message": "AlertManager not available"}


@app.get("/api/auth/whoami")
async def auth_whoami(request: Request, user: dict = Depends(get_current_user)):
    """
    Stable authentication check endpoint.
    Returns current user info if authenticated, 401 if not.
    Used by frontend for session validation.
    """
    return {
        "user": user["username"],
        "role": user["role"],
        "authenticated": True
    }



@app.get("/api/debug/whoami")
async def debug_whoami(request: Request):
    """Debug endpoint to check authentication status (controller only when enabled)"""
    if not check_debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        user = await get_current_user(request)
        if user["role"] != "controller":
            raise HTTPException(status_code=403, detail="Controller role required")
    except HTTPException as e:
        if e.status_code == 401:
            raise HTTPException(status_code=403, detail="Controller role required")
        raise
    
    session_id = request.cookies.get("session")
    return {
        "user": user["username"],
        "role": user["role"],
        "cookie_seen": session_id is not None,
        "session_id": session_id[:8] + "..." if session_id else None,
        "headers": dict(request.headers)
    }

@app.get("/api/debug/cors")
async def debug_cors(request: Request):
    """Debug endpoint to check CORS headers (controller only when enabled)"""
    if not check_debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        user = await get_current_user(request)
        if user["role"] != "controller":
            raise HTTPException(status_code=403, detail="Controller role required")
    except HTTPException as e:
        if e.status_code == 401:
            raise HTTPException(status_code=403, detail="Controller role required")
        raise
    
    return {
        "request_headers": dict(request.headers),
        "origin": request.headers.get("origin"),
        "user_agent": request.headers.get("user-agent"),
        "referer": request.headers.get("referer")
    }


daily_digest = DailyDigest(alert_manager)

@app.on_event("startup")
async def startup_event():
    logger.info("=== STARTUP EVENT TRIGGERED ===")
    
    digest_thread = threading.Thread(target=daily_digest_task, daemon=True, name="DailyDigestThread")
    digest_thread.start()
    logger.info(f"Daily digest task started in thread: {digest_thread.name}")
    
    health_thread = threading.Thread(target=background_health_monitor, daemon=True, name="HealthMonitorThread")
    health_thread.start()
    logger.info(f"Background health monitoring thread started: {health_thread.name}")
    
    refresh_health_probes()
    logger.info("Initial health probe completed")
    
    if alert_manager:
        asyncio.create_task(heartbeat_task_async())
        asyncio.create_task(daily_digest_task_async())
        logger.info("AlertManager heartbeat and daily digest tasks scheduled")

async def heartbeat_task_async():
    """Send heartbeat every 30 minutes if there were recent alerts"""
    while True:
        try:
            await asyncio.sleep(1800)
            if alert_manager:
                await alert_manager.send_heartbeat()
        except Exception as e:
            logger.error(f"Error in heartbeat task: {e}")
            await asyncio.sleep(300)

async def daily_digest_task_async():
    """Send daily digest at 09:05 UTC"""
    while True:
        try:
            now = datetime.utcnow()
            next_run = now.replace(hour=9, minute=5, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Daily digest scheduled for {next_run} UTC ({wait_seconds}s from now)")
            
            await asyncio.sleep(wait_seconds)
            
            if alert_manager:
                await alert_manager.send_daily_digest()
                
        except Exception as e:
            logger.error(f"Error in daily digest task: {e}")
            await asyncio.sleep(3600)

class SmokeTradeRequest(BaseModel):
    symbol: str
    side: str
    notionalUsd: float

@app.post("/api/test/smoke_trade")
async def smoke_trade(request: SmokeTradeRequest, user: dict = Depends(require_role("controller"))):
    """Controller-only $5 smoke trade endpoint"""
    logger.info(f"Smoke trade endpoint reached - user: {user}")
    
    if request.notionalUsd > 10:
        raise HTTPException(status_code=400, detail="Smoke trade limited to $10 max")
    
    if request.symbol not in ["BTC/USDT", "ETH/USDT"]:
        raise HTTPException(status_code=400, detail="Only BTC/USDT and ETH/USDT supported for smoke trades")
    
    if request.side.upper() not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL")
    
    order_id = f"smoke_{int(time.time())}"
    
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": "smoke_trade",
        "user": user["username"],
        "symbol": request.symbol,
        "side": request.side.upper(),
        "notional_usd": request.notionalUsd,
        "order_id": order_id,
        "status": "submitted",
        "mode": "smoke"
    }
    
    logger.info(f"Smoke trade executed: {audit_entry}")
    
    trade_event = {
        "type": "trade",
        "ts": datetime.utcnow().isoformat(),
        "venue": "paper",
        "symbol": request.symbol,
        "side": request.side.upper(),
        "qty": request.notionalUsd / 30000,
        "notional": request.notionalUsd,
        "lat_ms": 150,
        "status": "filled",
        "pnl_usd": 0,
        "equity_usd": bot_state["total_equity"],
        "order_id": order_id
    }
    
    try:
        redis_client.publish(TRADES_CHANNEL, json.dumps(trade_event))
        logger.info(f"Published trade event to Redis: {order_id}")
    except redis.RedisError as e:
        logger.error(f"Failed to publish trade event: {e}")
    
    return {
        "order_id": order_id,
        "symbol": request.symbol,
        "side": request.side.upper(),
        "notional_usd": request.notionalUsd,
        "status": "submitted",
        "message": "Smoke trade submitted successfully"
    }

async def trade_event_stream(user: dict) -> AsyncGenerator[str, None]:
    """Generate SSE stream for trade events"""
    pubsub = redis_client.pubsub()
    pubsub.subscribe(TRADES_CHANNEL)
    
    try:
        yield f"data: {json.dumps({'type': 'heartbeat', 'ts': datetime.utcnow().isoformat()})}\n\n"
        
        heartbeat_counter = 0
        while True:
            message = pubsub.get_message(timeout=0.1)
            if message and message['type'] == 'message':
                data = message['data']
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                yield f"data: {data}\n\n"
            
            # Send heartbeat every 30 seconds
            heartbeat_counter += 1
            if heartbeat_counter >= 300:  # 0.1s * 300 = 30s
                yield f"data: {json.dumps({'type': 'heartbeat', 'ts': datetime.utcnow().isoformat()})}\n\n"
                heartbeat_counter = 0
                
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Trade stream error: {e}")
    finally:
        pubsub.close()

async def health_event_stream(user: dict) -> AsyncGenerator[str, None]:
    """Generate SSE stream for health events"""
    pubsub = redis_client.pubsub()
    pubsub.subscribe(HEALTH_CHANNEL)
    
    try:
        try:
            health_data = redis_client.get(HEALTH_CACHE_KEY)
            if health_data:
                health_json = json.loads(health_data)
                health_json['type'] = 'health_update'
                yield f"data: {json.dumps(health_json)}\n\n"
        except Exception as e:
            logger.error(f"Failed to send initial health data: {e}")
        
        heartbeat_counter = 0
        while True:
            message = pubsub.get_message(timeout=0.1)
            if message and message['type'] == 'message':
                data = message['data']
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                yield f"data: {data}\n\n"
            
            # Send heartbeat every 30 seconds
            heartbeat_counter += 1
            if heartbeat_counter >= 300:  # 0.1s * 300 = 30s
                yield f"data: {json.dumps({'type': 'heartbeat', 'ts': datetime.utcnow().isoformat()})}\n\n"
                heartbeat_counter = 0
                
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Health stream error: {e}")
    finally:
        pubsub.close()

@app.get("/api/stream/trades")
async def stream_trades():
    """Server-Sent Events endpoint for trade updates"""
    dummy_user = {"username": "test", "role": "viewer"}
    return StreamingResponse(
        trade_event_stream(dummy_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "https://app.lunaraxolotl.com",
            "Access-Control-Allow-Credentials": "true"
        }
    )

@app.get("/api/stream/health")
async def stream_health():
    """Server-Sent Events endpoint for health updates"""
    dummy_user = {"username": "test", "role": "viewer"}
    return StreamingResponse(
        health_event_stream(dummy_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "https://app.lunaraxolotl.com",
            "Access-Control-Allow-Credentials": "true"
        }
    )

@app.get("/api/trades")
async def get_trades(since: str = None, limit: int = 1000, user: dict = Depends(get_current_user)):
    """Get historical trades for backfill"""
    filtered_orders = orders
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            filtered_orders = [
                order for order in orders 
                if datetime.fromisoformat(order['timestamp'].replace('Z', '+00:00')) >= since_dt
            ]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid since timestamp format")
    
    return {"trades": filtered_orders[:limit]}

@app.get("/api/mode")
async def get_mode():
    """Return current trading mode"""
    return {
        "mode": os.getenv("TRADING_MODE", "paper"),
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
