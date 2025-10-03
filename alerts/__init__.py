"""
AutoTrader Alert Management System

Comprehensive alert management with Redis-backed deduplication,
incident lifecycle tracking, and Discord integration.
"""

from .manager import AlertManager
from .commands import AlertCommands

__all__ = ['AlertManager', 'AlertCommands']
__version__ = '1.0.0'
