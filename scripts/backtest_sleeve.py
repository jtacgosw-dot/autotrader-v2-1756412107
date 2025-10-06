"""
Backtest runner for Swing and Event trading sleeves

Usage:
    python scripts/backtest_sleeve.py --sleeve swing --days 180
    python scripts/backtest_sleeve.py --sleeve event --days 365
"""

import argparse
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.swing import SwingSleeve, SwingConfig
from strategies.event import EventSleeve, EventConfig


def fetch_historical_data(symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    """Fetch historical OHLCV data using CCXT (stub)"""
    print(f"Fetching {days} days of {timeframe} data for {symbol}...")
    return pd.DataFrame()


def run_backtest(sleeve_type: str, days: int = 180):
    print(f"Running {sleeve_type} backtest for {days} days...")
    
    if sleeve_type == "swing":
        config = SwingConfig()
        sleeve = SwingSleeve(config)
        symbols = config.symbols
        
        historical_data = {}
        for symbol in symbols:
            historical_data[symbol] = {
                '15m': fetch_historical_data(symbol, '15m', days),
                '1h': fetch_historical_data(symbol, '1h', days)
            }
        
        results = sleeve.backtest(historical_data)
        
    elif sleeve_type == "event":
        config = EventConfig()
        sleeve = EventSleeve(config)
        symbols = config.symbols
        
        historical_data = {}
        for symbol in symbols:
            historical_data[symbol] = fetch_historical_data(symbol, '5m', days)
        
        results = sleeve.backtest(historical_data)
        
    else:
        raise ValueError(f"Unknown sleeve type: {sleeve_type}")
    
    output_dir = Path(__file__).parent.parent / "ops" / "reports" / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{sleeve_type}_backtest_{timestamp}.json"
    
    report = {
        'sleeve': sleeve_type,
        'period_days': days,
        'symbols': symbols,
        'config': config.__dict__,
        'results': results,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Backtest Report - {sleeve_type.upper()} Strategy")
    print(f"{'='*60}")
    print(f"Period: {days} days")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"\nResults:")
    print(f"  Total Trades: {results.get('total_trades', 0)}")
    print(f"  Win Rate: {results.get('win_rate', 0):.2f}%")
    print(f"  Total PnL: ${results.get('total_pnl', 0):.2f}")
    print(f"  Max Drawdown: {results.get('max_drawdown', 0):.2f}%")
    print(f"  Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
    print(f"  Avg Trade Duration: {results.get('avg_trade_duration', 0):.1f} hours")
    print(f"  Exposure: {results.get('exposure', 0):.2f}%")
    print(f"\nReport saved to: {output_file}")
    print(f"{'='*60}\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Run backtest for trading sleeves')
    parser.add_argument('--sleeve', choices=['swing', 'event'], required=True,
                        help='Which sleeve to backtest')
    parser.add_argument('--days', type=int, default=180,
                        help='Number of days to backtest (default: 180)')
    
    args = parser.parse_args()
    run_backtest(args.sleeve, args.days)


if __name__ == '__main__':
    main()
