"""
Event Trading Strategy - Volatility Breakout

Entry: Price closes above Donchian upper band (20 bars)
       ATR(14) >= median ATR × 1.3 (volatility expansion)
       Volume >= MA(20) volume × 1.2
Exit:  Close back inside band OR
       Trailing stop = 1.5 × ATR(14)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EventConfig:
    enabled: bool = False
    symbols: List[str] = None
    tf: str = "5m"
    donchian_len: int = 20
    atr_mult: float = 1.3
    vol_mult: float = 1.2
    atr_trail: float = 1.5
    risk_per_trade_bps: int = 25
    pos_cap_pct: float = 1.0
    reentry_bars: int = 10

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["BTC/USDT", "ETH/USDT"]


class EventSleeve:
    def __init__(self, config: EventConfig):
        self.config = config
        self.positions = {}
        self.last_trades = {}
        
    def calculate_donchian(self, high: pd.Series, low: pd.Series, period: int) -> tuple[pd.Series, pd.Series]:
        upper = high.rolling(window=period).max()
        lower = low.rolling(window=period).min()
        return upper, lower
    
    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def check_entry_signal(self, data: pd.DataFrame) -> bool:
        if len(data) < self.config.donchian_len:
            return False
        
        upper_band, lower_band = self.calculate_donchian(
            data['high'], data['low'], self.config.donchian_len
        )
        
        atr = self.calculate_atr(data['high'], data['low'], data['close'])
        atr_median = atr.rolling(window=20).median()
        
        vol_ma = data['volume'].rolling(window=20).mean()
        
        current_price = data['close'].iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_atr = atr.iloc[-1]
        current_atr_median = atr_median.iloc[-1]
        current_vol = data['volume'].iloc[-1]
        current_vol_ma = vol_ma.iloc[-1]
        
        breakout = current_price > current_upper
        vol_expansion = current_atr >= (current_atr_median * self.config.atr_mult)
        vol_confirm = current_vol >= (current_vol_ma * self.config.vol_mult)
        
        return breakout and vol_expansion and vol_confirm
    
    def check_exit_signal(self, data: pd.DataFrame, entry_price: float, peak_price: float) -> tuple[bool, str]:
        if len(data) < self.config.donchian_len:
            return False, ""
        
        upper_band, lower_band = self.calculate_donchian(
            data['high'], data['low'], self.config.donchian_len
        )
        
        current_price = data['close'].iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_lower = lower_band.iloc[-1]
        
        if current_lower <= current_price <= current_upper:
            return True, "band_reentry"
        
        atr = self.calculate_atr(data['high'], data['low'], data['close']).iloc[-1]
        trailing_stop = peak_price - (self.config.atr_trail * atr)
        
        if current_price <= trailing_stop:
            return True, "trailing_stop"
        
        return False, ""
    
    def backtest(self, historical_data: Dict[str, pd.DataFrame], start_capital: float = 10000) -> Dict:
        results = {
            'trades': [],
            'equity_curve': [],
            'total_pnl': 0,
            'win_rate': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'total_trades': 0,
            'avg_trade_duration': 0,
            'exposure': 0
        }
        
        return results
