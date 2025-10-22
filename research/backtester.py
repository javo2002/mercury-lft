import pandas as pd
import numpy as np
import pyfolio as pf
from database import SessionLocal, BacktestResult
from datetime import datetime
import pandas_ta as ta
import os

# --- CONFIGURATION ---
COMMISSION_BPS = 0.001
SLIPPAGE_BPS = 0.0005

def run_backtest(data, strategy_class, strategy_params):
    """
    A high-performance vectorized backtesting engine.
    """
    print(f"--- Running Vectorized Backtest for {strategy_class.__name__} ---")
    
    strategy = strategy_class(data.copy(), **strategy_params)
    signals = strategy.generate_signals()
    
    positions = signals['signal'].fillna(0)
    
    # --- FIX: CORRECTED RETURN CALCULATION TO AVOID LOOKAHEAD BIAS ---
    # Calculate daily returns based on the close price.
    returns = data['close'].pct_change()
    
    # Apply the position from the PREVIOUS day's signal to the CURRENT day's return.
    # This correctly simulates holding the position through the day.
    strategy_returns = returns * positions.shift(1)
    
    trades = positions.diff().abs()
    transaction_costs = trades * (COMMISSION_BPS + SLIPPAGE_BPS)
    strategy_returns -= transaction_costs
    
    strategy_returns.index = pd.to_datetime(strategy_returns.index)
    
    if strategy_returns.abs().sum() == 0:
        print("--- Backtest completed with no trades. No report generated. ---")
        return None

    perf_stats_df = pf.timeseries.perf_stats(strategy_returns, as_dict=True)
    
    session = SessionLocal()
    result = BacktestResult(
        strategy_name=strategy_class.__name__,
        parameters=str(strategy_params),
        start_date=data.index[0].date().isoformat(),
        end_date=data.index[-1].date().isoformat(),
        sharpe_ratio=perf_stats_df.get('Sharpe ratio', 0),
        cagr=perf_stats_df.get('Annual return', 0),
        max_drawdown=perf_stats_df.get('Max drawdown', 0),
        win_rate=perf_stats_df.get('Win rate', 0.5),
        timestamp=datetime.now().isoformat()
    )
    session.add(result)
    session.commit()
    
    print(f"--- Backtest Complete. Sharpe Ratio: {perf_stats_df.get('Sharpe ratio', 0):.2f} ---")
    
    os.makedirs('static', exist_ok=True)
    fig = pf.create_full_tear_sheet(strategy_returns, as_figure=True)
    report_filename = f"static/backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    fig.write_html(report_filename)
    
    result.report_url = report_filename
    session.commit()
    
    result_id = result.id
    session.close()
    
    return result_id

class BaseStrategy:
    def __init__(self, data, **params):
        self.data = data
        self.params = params

    def generate_signals(self):
        raise NotImplementedError("Each strategy must implement generate_signals()")

class SmaCross(BaseStrategy):
    def generate_signals(self):
        fast_window = self.params.get('fast', 50)
        slow_window = self.params.get('slow', 200)
        
        signals = pd.DataFrame(index=self.data.index)
        signals['signal'] = 0.0
        
        self.data.ta.sma(length=fast_window, append=True)
        self.data.ta.sma(length=slow_window, append=True)
        
        fast_sma_col = f'SMA_{fast_window}'
        slow_sma_col = f'SMA_{slow_window}'

        signals['signal'] = np.where(self.data[fast_sma_col] > self.data[slow_sma_col], 1.0, 0.0)
        
        return signals

