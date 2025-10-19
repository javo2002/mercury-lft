import pandas as pd
from backtesting import Backtest
# REMOVED: The old, incorrect import that was causing the error.
# from strategies.sma_cross import SmaCross 

def get_sma(data, period):
    """Calculates the Simple Moving Average."""
    return data['Close'].rolling(window=period).mean()

def get_rsi(data, period=14):
    """Calculates the Relative Strength Index."""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_sma_cross_signal(data, fast_period, slow_period):
    """
    Generates a trading signal based on SMA crossover.
    Returns 'BUY', 'SELL', or 'HOLD'.
    """
    # This is a simplified version for signal generation, not backtesting.
    sma_fast = get_sma(data, fast_period)
    sma_slow = get_sma(data, slow_period)
    
    # Check the last two periods to identify a crossover event
    if sma_fast.iloc[-1] > sma_slow.iloc[-1] and sma_fast.iloc[-2] < sma_slow.iloc[-2]:
        return "BUY"
    elif sma_fast.iloc[-1] < sma_slow.iloc[-1] and sma_fast.iloc[-2] > sma_slow.iloc[-2]:
        return "SELL"
    else:
        return "HOLD"
