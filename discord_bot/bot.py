import discord
from discord import app_commands
import os
import sys
import requests
import json
from datetime import datetime
import asyncio
import redis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alerts.manager import AlertManager
from alerts.commands import AlertCommands

API_BASE_URL = os.getenv("API_BASE_URL", "https://lunaraxolotl.com")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

class AutoTraderBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        
        try:
            self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            self.redis_client.ping()
            print("✅ Connected to Redis")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            self.redis_client = None
        
        if self.redis_client and DISCORD_WEBHOOK_URL:
            self.alert_manager = AlertManager(self.redis_client, DISCORD_WEBHOOK_URL)
            self.commands = AlertCommands(self, self.alert_manager)
        else:
            print("⚠️ AlertManager not initialized - missing Redis or webhook URL")
            self.alert_manager = None
            self.commands = None
        
    async def setup_hook(self):
        if self.commands:
            await self.commands.sync_commands()
        print("Command tree synced!")

client = AutoTraderBot()

@client.event
async def on_ready():
    print(f'✅ {client.user} is now running!')
    print(f'Connected to {len(client.guilds)} guild(s)')

@client.tree.command(name="status", description="Get current system status and health")
async def status(interaction: discord.Interaction):
    """Get current AutoTrader system status"""
    await interaction.response.defer()
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/status", timeout=10)
        data = response.json()
        
        health_response = requests.get(f"{API_BASE_URL}/api/healthz", timeout=10)
        health_data = health_response.json()
        
        embed = discord.Embed(
            title="📊 AutoTrader System Status",
            description="Current operational status of the trading system",
            color=discord.Color.green() if health_data.get('overall_status') == 'healthy' else discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Trading Mode", value=f"`{data.get('mode', 'Unknown')}`", inline=True)
        embed.add_field(name="System Health", value=f"`{health_data.get('overall_status', 'Unknown')}`", inline=True)
        embed.add_field(name="Uptime", value=f"`{data.get('uptime', 'N/A')}`", inline=True)
        
        embed.add_field(name="Discord Webhook", value="✅" if health_data.get('discord_webhook_ok') else "❌", inline=True)
        embed.add_field(name="SSM Connectivity", value="✅" if health_data.get('ssm_ok') else "❌", inline=True)
        embed.add_field(name="Redis Cache", value="✅" if health_data.get('cache_source') == 'redis' else "❌", inline=True)
        
        embed.set_footer(text="AutoTrader v2 Monitoring")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch status: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

@client.tree.command(name="trades", description="View recent trades")
async def trades(interaction: discord.Interaction, limit: int = 10):
    """View recent trades from the system"""
    await interaction.response.defer()
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/trades?limit={limit}", timeout=10)
        data = response.json()
        trades = data.get('trades', [])
        
        embed = discord.Embed(
            title=f"📈 Recent Trades (Last {len(trades)})",
            description="Most recent trading activity",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if trades:
            for trade in trades[:5]:
                symbol = trade.get('symbol', 'Unknown')
                side = trade.get('side', 'Unknown')
                qty = trade.get('qty', 0)
                price = trade.get('price', 0)
                
                embed.add_field(
                    name=f"{symbol} - {side}",
                    value=f"Qty: `{qty:.4f}` | Price: `${price:.2f}`",
                    inline=False
                )
        else:
            embed.description = "No recent trades found"
        
        embed.set_footer(text="AutoTrader v2 Trading History")
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch trades: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

@client.tree.command(name="alerts", description="View active alerts")
async def alerts(interaction: discord.Interaction):
    """View current system alerts"""
    await interaction.response.defer()
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/alerts", timeout=10)
        data = response.json()
        alerts = data.get('alerts', [])
        
        embed = discord.Embed(
            title="🔔 Active Alerts",
            description=f"Currently {len(alerts)} active alert(s)",
            color=discord.Color.orange() if alerts else discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        if alerts:
            for alert in alerts[:10]:
                severity = alert.get('severity', 'unknown')
                message = alert.get('message', 'No message')
                
                emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(severity, "📌")
                embed.add_field(
                    name=f"{emoji} {severity.upper()}",
                    value=message,
                    inline=False
                )
        else:
            embed.description = "✅ No active alerts - system operating normally"
        
        embed.set_footer(text="AutoTrader v2 Alert System")
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch alerts: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

@client.tree.command(name="risk", description="View current risk settings")
async def risk(interaction: discord.Interaction):
    """View risk management settings"""
    await interaction.response.defer()
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/risk", timeout=10)
        data = response.json()
        
        embed = discord.Embed(
            title="⚖️ Risk Management Settings",
            description="Current risk parameters and limits",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Max Position Size", value=f"`${data.get('max_position', 'N/A')}`", inline=True)
        embed.add_field(name="Max Daily Loss", value=f"`${data.get('max_daily_loss', 'N/A')}`", inline=True)
        embed.add_field(name="Max Leverage", value=f"`{data.get('max_leverage', 'N/A')}x`", inline=True)
        
        embed.set_footer(text="AutoTrader v2 Risk Controls")
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch risk settings: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

@client.tree.command(name="pause", description="Pause trading (controller only)")
async def pause(interaction: discord.Interaction):
    """Pause all trading activity"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        response = requests.post(f"{API_BASE_URL}/api/pause", timeout=10)
        data = response.json()
        
        embed = discord.Embed(
            title="⏸️ Trading Paused",
            description="All trading activity has been paused",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to pause trading: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)

@client.tree.command(name="resume", description="Resume trading (controller only)")
async def resume(interaction: discord.Interaction):
    """Resume trading activity"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        response = requests.post(f"{API_BASE_URL}/api/resume", timeout=10)
        data = response.json()
        
        embed = discord.Embed(
            title="▶️ Trading Resumed",
            description="Trading activity has been resumed",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to resume trading: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)

@client.tree.command(name="health", description="Detailed health check of all systems")
async def health(interaction: discord.Interaction):
    """Get detailed health information"""
    await interaction.response.defer()
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/healthz", timeout=10)
        health_data = response.json()
        
        status = health_data.get('overall_status', 'unknown')
        color = discord.Color.green() if status == 'healthy' else discord.Color.red()
        
        embed = discord.Embed(
            title="🏥 System Health Check",
            description=f"Overall Status: **{status.upper()}**",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        components = [
            ("Discord Webhook", health_data.get('discord_webhook_ok', False)),
            ("SSM Connectivity", health_data.get('ssm_ok', False)),
            ("Redis Cache", health_data.get('cache_source') == 'redis'),
            ("API Server", health_data.get('api_ok', False))
        ]
        
        for name, healthy in components:
            status_emoji = "✅" if healthy else "❌"
            embed.add_field(name=name, value=status_emoji, inline=True)
        
        embed.add_field(
            name="Last Updated",
            value=f"`{health_data.get('last_updated', 'Unknown')}`",
            inline=False
        )
        
        embed.set_footer(text="AutoTrader v2 Health Monitor")
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch health data: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=error_embed)

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN environment variable not set")
        exit(1)
    
    print("🚀 Starting AutoTrader Discord Bot...")
    client.run(DISCORD_BOT_TOKEN)
