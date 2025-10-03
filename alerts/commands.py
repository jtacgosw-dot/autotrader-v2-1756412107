import discord
from discord import app_commands
import os
import requests
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_BASE_URL", "https://lunaraxolotl.com")

class AlertCommands:
    """Discord slash commands for alert management and bot control"""
    
    def __init__(self, bot_client: discord.Client, alert_manager):
        self.client = bot_client
        self.alert_manager = alert_manager
        self.tree = app_commands.CommandTree(bot_client)
        
        self.register_commands()
    
    def register_commands(self):
        """Register all slash commands"""
        
        @self.tree.command(name="alerts_status", description="View open incidents and recent alert activity")
        async def alerts_status(interaction: discord.Interaction):
            await interaction.response.defer()
            
            try:
                incidents = self.alert_manager.get_open_incidents()
                
                embed = discord.Embed(
                    title="🔔 Alert System Status",
                    description=f"Currently **{len(incidents)}** open incident(s)",
                    color=discord.Color.orange() if incidents else discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                
                if incidents:
                    for incident in incidents[:10]:
                        severity = incident.get("severity", "unknown")
                        title = incident.get("title", "Unknown")
                        count = incident.get("count", 1)
                        opened_at = incident.get("opened_at", "Unknown")
                        
                        emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(severity.lower(), "📌")
                        
                        embed.add_field(
                            name=f"{emoji} {title}",
                            value=f"Severity: `{severity.upper()}` • Count: `{count}` • Opened: `{opened_at[:19]}`",
                            inline=False
                        )
                else:
                    embed.description = "✅ No open incidents - all systems operational"
                
                embed.set_footer(text="AutoTrader v2 Alert System")
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in alerts_status command: {e}")
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to fetch alert status: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed)
        
        @self.tree.command(name="alerts_mute", description="Mute alerts for a specified duration")
        async def alerts_mute(
            interaction: discord.Interaction,
            severity: str,
            duration_minutes: int = 30
        ):
            await interaction.response.defer(ephemeral=True)
            
            try:
                if severity.lower() not in ["info", "warning", "critical"]:
                    error_embed = discord.Embed(
                        title="❌ Error",
                        description="Severity must be one of: info, warning, critical",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                    return
                
                success = self.alert_manager.mute(severity, duration_minutes)
                
                if success:
                    embed = discord.Embed(
                        title="🔇 Alerts Muted",
                        description=f"**{severity.upper()}** alerts muted for **{duration_minutes} minutes**",
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )
                    
                    if severity.lower() != "critical":
                        embed.add_field(
                            name="Note",
                            value="CRITICAL alerts will still be sent regardless of mute status",
                            inline=False
                        )
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    error_embed = discord.Embed(
                        title="❌ Error",
                        description="Failed to mute alerts",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                
            except Exception as e:
                logger.error(f"Error in alerts_mute command: {e}")
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to mute alerts: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
        
        @self.tree.command(name="alerts_unmute", description="Unmute alerts at specified severity")
        async def alerts_unmute(interaction: discord.Interaction, severity: str):
            await interaction.response.defer(ephemeral=True)
            
            try:
                success = self.alert_manager.unmute(severity)
                
                if success:
                    embed = discord.Embed(
                        title="🔔 Alerts Unmuted",
                        description=f"**{severity.upper()}** alerts are now unmuted",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    error_embed = discord.Embed(
                        title="❌ Error",
                        description="Failed to unmute alerts",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                
            except Exception as e:
                logger.error(f"Error in alerts_unmute command: {e}")
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to unmute alerts: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
        
        @self.tree.command(name="alerts_test", description="Send a test alert")
        async def alerts_test(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            
            try:
                await self.alert_manager.send(
                    type="test",
                    severity="info",
                    key="manual_test",
                    title="Test Alert",
                    body="This is a test alert triggered via Discord command",
                    tags={"triggered_by": interaction.user.name}
                )
                
                embed = discord.Embed(
                    title="✅ Test Alert Sent",
                    description="A test alert has been posted to the alerts channel",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as e:
                logger.error(f"Error in alerts_test command: {e}")
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to send test alert: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
        
        @self.tree.command(name="bot_pause", description="Pause trading (controller only)")
        async def bot_pause(interaction: discord.Interaction):
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
                logger.error(f"Error in bot_pause command: {e}")
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to pause trading: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
        
        @self.tree.command(name="bot_resume", description="Resume trading (controller only)")
        async def bot_resume(interaction: discord.Interaction):
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
                logger.error(f"Error in bot_resume command: {e}")
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to resume trading: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    async def sync_commands(self):
        """Sync command tree with Discord"""
        try:
            await self.tree.sync()
            logger.info("Discord command tree synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync command tree: {e}")
