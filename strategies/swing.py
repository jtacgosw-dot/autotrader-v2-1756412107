"""
Swing Trading Strategy - Conservative Trend Following

Entry: Fast SMA(20) > Slow SMA(60) on both 15m and 1h
       RSI(14) between 50-70
       Volume > MA(20) volume
Exit:  Fast SMA(20) < Slow SMA(60) on 15m OR
       Trailing stop = 2.0 × ATR(14) from peak OR
       Hard stop = 1.0 × ATR(14) from entry
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SwingConfig:
    enabled: bool = False
    symbols: List[str] = None
    tf_fast: str = "15m"
    tf_slow: str = "1h"
    sma_fast: int = 20
    sma_slow: int = 60
    rsi_min: int = 50
    rsi_max: int = 70
    atr_stop: float = 1.0
    atr_trail: float = 2.0
    vol_ma_len: int = 20
    risk_per_trade_bps: int = 25
    pos_cap_pct: float = 1.0
    min_hold_minutes: int = 30
    reentry_cooldown_minutes: int = 60

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["BTC/USDT", "ETH/USDT"]


class SwingSleeve:
    def __init__(self, config: SwingConfig):
        self.config = config
        self.positions = {}
        self.cooldowns = {}
        
    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        return prices.rolling(window=period).mean()
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def check_entry_signal(self, data_15m: pd.DataFrame, data_1h: pd.DataFrame) -> bool:
        if len(data_15m) < self.config.sma_slow or len(data_1h) < self.config.sma_slow:
            return False
        
        sma_fast_15m = self.calculate_sma(data_15m['close'], self.config.sma_fast).iloc[-1]
        sma_slow_15m = self.calculate_sma(data_15m['close'], self.config.sma_slow).iloc[-1]
        
        sma_fast_1h = self.calculate_sma(data_1h['close'], self.config.sma_fast).iloc[-1]
        sma_slow_1h = self.calculate_sma(data_1h['close'], self.config.sma_slow).iloc[-1]
        
        rsi = self.calculate_rsi(data_15m['close']).iloc[-1]
        
        vol_ma = data_15m['volume'].rolling(window=self.config.vol_ma_len).mean().iloc[-1]
        current_vol = data_15m['volume'].iloc[-1]
        
        trend_confirm = (sma_fast_15m > sma_slow_15m) and (sma_fast_1h > sma_slow_1h)
        rsi_confirm = self.config.rsi_min <= rsi <= self.config.rsi_max
        vol_confirm = current_vol > vol_ma
        
        return trend_confirm and rsi_confirm and vol_confirm
    
    def check_exit_signal(self, data_15m: pd.DataFrame, entry_price: float, peak_price: float) -> tuple[bool, str]:
        if len(data_15m) < self.config.sma_slow:
            return False, ""
        
        sma_fast_15m = self.calculate_sma(data_15m['close'], self.config.sma_fast).iloc[-1]
        sma_slow_15m = self.calculate_sma(data_15m['close'], self.config.sma_slow).iloc[-1]
        
        if sma_fast_15m < sma_slow_15m:
            return True, "trend_reversal"
        
        atr = self.calculate_atr(data_15m['high'], data_15m['low'], data_15m['close']).iloc[-1]
        current_price = data_15m['close'].iloc[-1]
        
        hard_stop = entry_price - (self.config.atr_stop * atr)
        if current_price <= hard_stop:
            return True, "hard_stop"
        
        trailing_stop = peak_price - (self.config.atr_trail * atr)
        if current_price <= trailing_stop:
            return True, "trailing_stop"
        
        return False, ""
    
    def backtest(self, historical_data: Dict[str, Dict[str, pd.DataFrame]], start_capital: float = 10000) -> Dict:
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
