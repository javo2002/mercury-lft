import pandas as pd
import numpy as np # --- FIX: Import numpy for NaN checking ---
from analysis_toolkit import get_sma, get_rsi

def get_sma_signal(data, fast_period=50, slow_period=200):
    """Generates a BUY signal on a golden cross and a SELL signal on a death cross."""
    sma_fast = get_sma(data, fast_period)
    sma_slow = get_sma(data, slow_period)
    
    # --- FIX: Add a check to ensure the SMA values are valid numbers before comparing ---
    # This prevents errors if yfinance returns incomplete data for a ticker.
    last_fast = sma_fast.iloc[-1]
    prev_fast = sma_fast.iloc[-2]
    last_slow = sma_slow.iloc[-1]
    prev_slow = sma_slow.iloc[-2]

    if np.isnan([last_fast, prev_fast, last_slow, prev_slow]).any():
        return "HOLD" # Not enough data to make a decision

    if last_fast > last_slow and prev_fast <= prev_slow:
        return "BUY"
    elif last_fast < last_slow and prev_fast >= prev_slow:
        return "SELL" # SELL to go short
    return "HOLD"

def get_rsi_signal(data, rsi_period=14, rsi_overbought=70, rsi_oversold=30):
    """Generates a BUY signal on oversold and a SELL signal on overbought."""
    rsi = get_rsi(data, rsi_period)

    # --- FIX: Add a NaN check for RSI as well ---
    last_rsi = rsi.iloc[-1]
    prev_rsi = rsi.iloc[-2]
    if np.isnan([last_rsi, prev_rsi]).any():
        return "HOLD"

    if last_rsi < rsi_oversold and prev_rsi >= rsi_oversold:
        return "BUY"
    elif last_rsi > rsi_overbought and prev_rsi <= rsi_overbought:
        return "SELL" # SELL to go short
    return "HOLD"

def get_volatility_signal(data, atr_period=14, lookback=20):
    """Generates a BUY signal on a high-volatility upside breakout."""
    high_low = data['High'] - data['Low']
    high_close = (data['High'] - data['Close'].shift()).abs()
    low_close = (data['Low'] - data['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=atr_period).mean()
    
    recent_high = data['High'].rolling(window=lookback).max()
    is_volatile = atr.iloc[-1] > atr.rolling(window=50).mean().iloc[-1]
    
    if data['Close'].iloc[-1] > recent_high.iloc[-2] and is_volatile:
        return "BUY"
    # Note: A shorting version of this strategy would be more complex.
    return "HOLD"

def get_pattern_breakout_signal(data, consolidation_period=20):
    """Generates a BUY signal on a breakout from a consolidation range."""
    recent_high = data['High'].iloc[-consolidation_period:-1].max()
    recent_low = data['Low'].iloc[-consolidation_period:-1].min()
    
    if data['Close'].iloc[-2] < recent_high and data['Close'].iloc[-1] > recent_high:
        return "BUY"
    elif data['Close'].iloc[-2] > recent_low and data['Close'].iloc[-1] < recent_low:
        return "SELL" # SELL to go short on a breakdown
    return "HOLD"
