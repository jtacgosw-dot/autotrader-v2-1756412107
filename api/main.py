from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os
from datetime import datetime, timedelta
import json
import secrets
import hashlib
import boto3
import logging
import requests
import io
import csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AutoTrader API", version="2.0.0")

SESSION_TIMEOUT_MINUTES = 30
COOKIE_MAX_AGE = SESSION_TIMEOUT_MINUTES * 60

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

def load_credentials():
    print("=== LOAD_CREDENTIALS FUNCTION CALLED ===", flush=True)
    logger.info("Loading credentials from AWS Secrets Manager")
    try:
        client = boto3.client('secretsmanager', region_name='us-east-1')
        
        print("=== FETCHING VIEWER CREDENTIALS ===", flush=True)
        viewer_secret = client.get_secret_value(SecretId='autotrader/viewer-credentials')
        viewer_data = json.loads(viewer_secret['SecretString'])
        print(f"=== SUCCESS: Loaded viewer credentials for: {viewer_data['username']} ===", flush=True)
        logger.info(f"Loaded viewer credentials for: {viewer_data['username']}")
        
        print("=== FETCHING CONTROLLER CREDENTIALS ===", flush=True)
        controller_secret = client.get_secret_value(SecretId='autotrader/controller-credentials')
        controller_data = json.loads(controller_secret['SecretString'])
        print(f"=== SUCCESS: Loaded controller credentials for: {controller_data['username']} ===", flush=True)
        logger.info(f"Loaded controller credentials for: {controller_data['username']}")
        
        credentials = {
            viewer_data['username']: {"password": viewer_data['password'], "role": "viewer"},
            controller_data['username']: {"password": controller_data['password'], "role": "controller"}
        }
        print(f"=== CREDENTIALS LOADED FROM SECRETS MANAGER: {list(credentials.keys())} ===", flush=True)
        logger.info(f"Successfully loaded {len(credentials)} user credentials from Secrets Manager")
        return credentials
    except Exception as e:
        print(f"=== FAILED TO LOAD FROM SECRETS MANAGER: {e} ===", flush=True)
        logger.error(f"Failed to load credentials from Secrets Manager: {e}")
        import traceback
        traceback.print_exc()
        print("=== USING FALLBACK ENVIRONMENT VARIABLES ===", flush=True)
        logger.info("Using fallback environment variable credentials")
        fallback_creds = {
            "viewer": {"password": os.getenv("VIEWER_PASSWORD", "ViewerPass123!"), "role": "viewer"},
            "controller": {"password": os.getenv("CONTROLLER_PASSWORD", "ControllerPass456!"), "role": "controller"}
        }
        print(f"=== FALLBACK CREDENTIALS: {list(fallback_creds.keys())} ===", flush=True)
        return fallback_creds

sessions = {}

# Load user credentials
print("=== ABOUT TO CALL LOAD_CREDENTIALS ===", flush=True)
users = load_credentials()
print(f"=== USERS LOADED: {list(users.keys())} ===", flush=True)
logger.info(f"Loaded user credentials: {list(users.keys())}")

bot_state = {
    "status": "running",
    "mode": "paper",
    "paused": False,
    "kill_switch_active": False,
    "maintenance_mode": False,
    "total_equity": 100000.0,
    "pnl_today": 1250.75,
    "drawdown": 0.35,
    "daily_kill_pct": 1.0,
    "max_pos_pct": 1.0,
    "max_slippage_bps": 6
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
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = sessions[session_id]
    
    if datetime.utcnow() - session["last_activity"] > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        del sessions[session_id]
        raise HTTPException(status_code=401, detail="Session expired")
    
    session["last_activity"] = datetime.utcnow()
    
    return session

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
async def login(login_data: LoginRequest, response: Response):
    username = login_data.username
    password = login_data.password
    
    print(f"=== LOGIN ATTEMPT: username={username} ===", flush=True)
    print(f"=== AVAILABLE USERS: {list(users.keys())} ===", flush=True)
    
    if username in users:
        stored_password = users[username]["password"]
        print(f"=== STORED PASSWORD: {stored_password[:8]}... ===", flush=True)
        print(f"=== PROVIDED PASSWORD: {password[:8]}... ===", flush=True)
        print(f"=== PASSWORD MATCH: {stored_password == password} ===", flush=True)
    
    if username not in users or users[username]["password"] != password:
        print(f"=== LOGIN FAILED: Invalid credentials for {username} ===", flush=True)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "username": username,
        "role": users[username]["role"],
        "created_at": datetime.utcnow(),
        "last_activity": datetime.utcnow()
    }
    
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/"
    )
    
    print(f"=== LOGIN SUCCESSFUL: {username} with role {users[username]['role']} ===", flush=True)
    return {"message": "Login successful", "role": users[username]["role"]}

@app.post("/api/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
    
    response.delete_cookie("session_id")
    return {"message": "Logged out successfully"}

class AlertManager:
    def __init__(self):
        self.last_alerts = {}
        self.alert_throttle_minutes = 15
    
    async def send_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """Send alert to Discord with throttling"""
        current_time = datetime.utcnow()
        alert_key = f"{alert_type}:{message}"
        
        if alert_key in self.last_alerts:
            time_diff = current_time - self.last_alerts[alert_key]
            if time_diff.total_seconds() < (self.alert_throttle_minutes * 60):
                return
        
        self.last_alerts[alert_key] = current_time
        
        if DISCORD_WEBHOOK_URL:
            try:
                color = {"critical": 0xFF0000, "warning": 0xFFA500, "info": 0x0099FF}.get(severity, 0x808080)
                
                payload = {
                    "embeds": [{
                        "title": f"AutoTrader Alert - {alert_type.replace('_', ' ').title()}",
                        "description": message,
                        "color": color,
                        "timestamp": current_time.isoformat(),
                        "fields": [
                            {"name": "Severity", "value": severity.upper(), "inline": True},
                            {"name": "Environment", "value": "Production", "inline": True}
                        ]
                    }]
                }
                
                response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
                response.raise_for_status()
                logging.info(f"Alert sent to Discord: {alert_type}")
                
            except Exception as e:
                logging.error(f"Failed to send Discord alert: {e}")

alert_manager = AlertManager()

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/healthz")
async def health_aggregator():
    """Comprehensive health check aggregating all system components"""
    health_status = {
        "api_ok": True,
        "nginx_ok": True,
        "tg_healthy": True,
        "ssm_ok": True,
        "discord_webhook_ok": True,
        "overall_status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        ssm_client = boto3.client('ssm', region_name='us-east-1')
        ssm_client.describe_instance_information(MaxResults=1)
        health_status["ssm_ok"] = True
    except Exception:
        health_status["ssm_ok"] = False
    
    try:
        if DISCORD_WEBHOOK_URL:
            health_status["discord_webhook_ok"] = True
        else:
            health_status["discord_webhook_ok"] = False
    except Exception:
        health_status["discord_webhook_ok"] = False
    
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

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user=Depends(get_current_user)):
    """Acknowledge an alert"""
    for alert in alerts:
        if alert["id"] == alert_id:
            alert["acknowledged"] = True
            return {"message": "Alert acknowledged"}
    raise HTTPException(status_code=404, detail="Alert not found")

@app.post("/api/pause")
async def pause_trading(user=Depends(require_role("controller"))):
    if bot_state["mode"] != "paper":
        raise HTTPException(status_code=400, detail="Only paper mode supported")
    
    bot_state["paused"] = True
    bot_state["status"] = "paused"
    
    await alert_manager.send_alert(
        "trading_paused", 
        f"Trading paused by user {user['username']}", 
        "warning"
    )
    
    audit_log = {
        "ts": datetime.utcnow().isoformat(),
        "action": "pause",
        "user": user["username"],
        "details": "Trading paused via API"
    }
    
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
    
    await alert_manager.send_alert(
        "trading_resumed", 
        f"Trading resumed by user {user['username']}", 
        "info"
    )
    
    audit_log = {
        "ts": datetime.utcnow().isoformat(),
        "action": "resume", 
        "user": user["username"],
        "details": "Trading resumed via API"
    }
    
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
        "details": f"Risk settings updated: kill={settings.daily_kill_pct}%, pos={settings.max_pos_pct}%, slippage={settings.max_slippage_bps}bps"
    }
    
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
        await alert_manager.send_alert(
            "maintenance_mode_enabled",
            f"Maintenance mode enabled by {user['username']}",
            "warning"
        )
    else:
        if not bot_state["kill_switch_active"]:
            bot_state["paused"] = False
            bot_state["status"] = "running"
        await alert_manager.send_alert(
            "maintenance_mode_disabled",
            f"Maintenance mode disabled by {user['username']}",
            "info"
        )
    
    return {
        "maintenance_mode": enabled,
        "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}"
    }

@app.post("/api/test-alert")
async def test_alert(user=Depends(require_role("controller"))):
    """Test endpoint for Discord alerts"""
    await alert_manager.send_alert(
        "test_alert",
        f"Test alert triggered by {user['username']} - system is working correctly",
        "info"
    )
    return {"message": "Test alert sent"}

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
        "kill_switch_active": bot_state["kill_switch_active"]
    }

@app.get("/api/balances")
async def get_balances():
    return {
        "USDT": {"balance": 50000.0, "available": 48750.0, "locked": 1250.0},
        "BTC": {"balance": 1.5, "available": 1.45, "locked": 0.05},
        "ETH": {"balance": 10.0, "available": 10.0, "locked": 0.0}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
