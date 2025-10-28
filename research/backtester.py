import pandas as pd
import numpy as np
import pyfolio as pf
from database import SessionLocal, BacktestResult
from datetime import datetime
import pandas_ta as ta
import os
# --- NEW IMPORTS for dynamic loading ---
import importlib.util
import sys
import inspect

# --- CONFIGURATION ---
COMMISSION_BPS = 0.001
SLIPPAGE_BPS = 0.0005
GENERATED_STRATEGY_DIR = 'generated_strategies'


# --- Base Strategy Class ---
class BaseStrategy:
    def __init__(self, data, **params):
        self.data = data
        self.params = params

    def generate_signals(self):
        raise NotImplementedError("Each strategy must implement generate_signals()")

    @classmethod
    def get_default_params(cls):
        """
        Returns a dictionary of default parameters for optimization.
        """
        return {}

# --- Strategy Definitions ---
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

    @classmethod
    def get_default_params(cls):
        """
        Returns default parameters for SmaCross.
        """
        return {"fast": 50, "slow": 200}

# --- DYNAMIC STRATEGY LOADING ---

def load_dynamic_strategies(directory):
    """
    Scans a directory for .py files, imports them, and finds classes
    that inherit from BaseStrategy.
    """
    dynamic_strategies = {}
    if not os.path.exists(directory):
        print(f"Warning: Strategy directory not found: {directory}")
        return {}
        
    for filename in os.listdir(directory):
        if filename.endswith('.py') and not filename.startswith('__'):
            filepath = os.path.join(directory, filename)
            module_name = f"generated_strategies.{filename[:-3]}"
            
            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Find all classes in the file that are subclasses of BaseStrategy
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                        print(f"  -> Dynamically loaded strategy: {name}")
                        dynamic_strategies[name] = obj
                        
            except Exception as e:
                print(f"Error loading strategy from {filename}: {e}")
                
    return dynamic_strategies

# --- Create Strategy Map ---
STRATEGY_MAP = {
    "SmaCross": SmaCross,
}
print("--- Loading dynamic AI strategies... ---")
STRATEGY_MAP.update(load_dynamic_strategies(GENERATED_STRATEGY_DIR))
print(f"--- Total strategies loaded: {len(STRATEGY_MAP.keys())} ---")


# --- FIX: Modified function signature to accept 'ticker' ---
def run_backtest(ticker, data, strategy_name, strategy_params):
    """
    A high-performance vectorized backtesting engine.
    """
    
    strategy_class = STRATEGY_MAP.get(strategy_name)
    if not strategy_class:
        print(f"--- ERROR: Strategy '{strategy_name}' not found. ---")
        return None
        
    print(f"--- Running Vectorized Backtest for {ticker} | {strategy_name} ---")
    
    strategy = strategy_class(data.copy(), **strategy_params)
    signals = strategy.generate_signals()
    
    positions = signals['signal'].fillna(0)
    
    returns = data['close'].pct_change()
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
        # --- FIX: Add ticker to the database entry ---
        ticker=ticker,
        strategy_name=strategy_name,
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
    # --- FIX: Add ticker to report filename for clarity ---
    fig = pf.create_full_tear_sheet(strategy_returns, as_figure=True)
    report_filename = f"static/backtest_report_{ticker}_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    fig.write_html(report_filename)
    
    result.report_url = report_filename
    session.commit()
    
    result_id = result.id
    session.close()
    
    return result_id
