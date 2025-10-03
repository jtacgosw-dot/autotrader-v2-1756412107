"""
Basic sanity tests for AlertManager
Run with: python -m pytest alerts/test_basic.py -v
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import redis
from datetime import datetime

from alerts.manager import AlertManager


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    r = Mock(spec=redis.Redis)
    r.get = Mock(return_value=None)
    r.setex = Mock()
    r.exists = Mock(return_value=0)
    r.delete = Mock()
    r.keys = Mock(return_value=[])
    r.lrange = Mock(return_value=[])
    r.rpush = Mock()
    r.expire = Mock()
    return r


@pytest.fixture
def alert_manager(mock_redis):
    """Create AlertManager instance"""
    return AlertManager(mock_redis, "https://discord.com/webhook/test")


@pytest.mark.asyncio
async def test_severity_color(alert_manager):
    """Test severity color mapping"""
    assert alert_manager._severity_color("info") == 0x808080
    assert alert_manager._severity_color("warning") == 0xFFA500
    assert alert_manager._severity_color("critical") == 0xFF0000


@pytest.mark.asyncio
async def test_severity_emoji(alert_manager):
    """Test severity emoji mapping"""
    assert alert_manager._severity_emoji("info") == "ℹ️"
    assert alert_manager._severity_emoji("warning") == "⚠️"
    assert alert_manager._severity_emoji("critical") == "🚨"


@pytest.mark.asyncio
async def test_mute_unmute(alert_manager, mock_redis):
    """Test mute/unmute functionality"""
    alert_manager.mute("warning", 30)
    mock_redis.setex.assert_called_once()
    
    alert_manager.unmute("warning")
    mock_redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_get_open_incidents_empty(alert_manager, mock_redis):
    """Test getting open incidents when none exist"""
    mock_redis.keys.return_value = []
    incidents = alert_manager.get_open_incidents()
    assert incidents == []


@pytest.mark.asyncio
async def test_redis_keys_generation(alert_manager):
    """Test Redis key generation"""
    keys = alert_manager._get_redis_keys("health", "test-key")
    assert "alert:prod:health:test-key:open" in keys["open"]
    assert "alert:prod:health:test-key:cooldown" in keys["cooldown"]
    assert "alert:prod:health:test-key:agg" in keys["agg"]


def test_format_duration(alert_manager):
    """Test duration formatting"""
    iso_time = datetime.utcnow().isoformat()
    duration = alert_manager._format_duration(iso_time)
    assert "`" in duration


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
