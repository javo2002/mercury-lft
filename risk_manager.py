# In risk_manager.py

import yfinance as yf # Keep yf for get_sector for now, or replace later
import pandas as pd
from database import SessionLocal, Trade # Removed unused imports
from sqlalchemy import func # Removed unused imports

# --- NEW: Import Alpaca client ---
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from config import settings # Import settings for API keys
from datetime import datetime, timedelta # Import datetime utils

# --- CONFIGURATION ---
CORR_THRESHOLD = 0.7 
CORR_PERIOD = "3mo"
MAX_SECTOR_CONCENTRATION = 0.40 

# --- SECTOR CACHE ---
sector_cache = {}

# --- NEW: Initialize Alpaca Client ---
data_client = StockHistoricalDataClient(settings.API_KEY, settings.API_SECRET)

def get_sector(ticker):
    # This still uses yfinance, could be replaced if needed
    if ticker in sector_cache:
        return sector_cache[ticker]
    try:
        info = yf.Ticker(ticker).info
        sector = info.get('sector', 'Other')
        sector_cache[ticker] = sector
        return sector
    except Exception:
        return "Other"

def get_market_condition():
    """
    Analyzes market trend and volatility using Alpaca data.
    """
    print("--- Running Advanced Market Regime Analysis (Alpaca) ---")
    trend_condition = 'NEUTRAL' 
    volatility_regime = 'HIGH' 
    
    try:
        # --- FIX: Use Alpaca client to fetch SPY and VIX ---
        request_params = StockBarsRequest(
            symbol_or_symbols=["SPY", "VIX"], # Use Alpaca's symbol for VIX if different (^VIX might not work) - Check Alpaca docs if needed. Often just 'VIX'.
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=365) # Get 1 year for 200 day SMA
        )
        barset = data_client.get_stock_bars(request_params).df

        if "SPY" in barset.index:
            spy_hist = barset.loc['SPY']
            if not spy_hist.empty and 'close' in spy_hist.columns:
                spy_sma_200 = spy_hist['close'].rolling(window=200).mean()
                if not spy_sma_200.empty and not pd.isna(spy_sma_200.iloc[-1]):
                    spy_current_price = spy_hist['close'].iloc[-1]
                    trend_condition = 'BULLISH' if spy_current_price > spy_sma_200.iloc[-1] else 'BEARISH'

        # Check Alpaca symbol for VIX, it might be just 'VIX'
        vix_symbol = "VIX" # or "^VIX" if Alpaca uses that
        if vix_symbol in barset.index:
            vix_hist = barset.loc[vix_symbol]
            if not vix_hist.empty and 'close' in vix_hist.columns:
                vix_sma_50 = vix_hist['close'].rolling(window=50).mean()
                if not vix_sma_50.empty and not pd.isna(vix_sma_50.iloc[-1]):
                    vix_current_level = vix_hist['close'].iloc[-1]
                    volatility_regime = 'HIGH' if vix_current_level > vix_sma_50.iloc[-1] else 'LOW'

        print(f"  -> Trend: {trend_condition} | Volatility: {volatility_regime}")
            
    except Exception as e:
        print(f"  -> Market condition analysis failed: {e}. Defaulting to {trend_condition}, {volatility_regime}.")
    
    return trend_condition, volatility_regime

def check_portfolio_constraints(new_ticker_sector, open_positions):
    """
    Checks if adding a new position would violate portfolio constraints.
    - Sector Concentration
    """
    if not open_positions:
        return True # No positions, no constraints to violate

    print("--- Checking Portfolio Constraints ---")
    
    # Sector Concentration Check
    sector_exposure = {}
    total_market_value = sum(float(p.market_value) for p in open_positions)
    if total_market_value == 0: return True

    for p in open_positions:
        sector = get_sector(p.symbol)
        sector_exposure[sector] = sector_exposure.get(sector, 0) + float(p.market_value)
    
    # Calculate what the new concentration would be
    potential_new_exposure = sector_exposure.get(new_ticker_sector, 0) + (total_market_value / len(open_positions)) # Approximate value of new trade
    potential_total_value = total_market_value + (total_market_value / len(open_positions))
    
    if (potential_new_exposure / potential_total_value) > MAX_SECTOR_CONCENTRATION:
        print(f"  -> VIOLATION: Adding a trade in '{new_ticker_sector}' would exceed max sector concentration.")
        return False

    print("  -> Portfolio constraints passed.")
    return True

def is_correlation_safe(new_ticker, open_positions_tickers):
    """
    Checks if a new ticker is highly correlated with existing positions.
    (#Stub for master_bot.py)
    """
    if not open_positions_tickers:
        return True # No positions, safe to trade

    try:
        all_tickers = open_positions_tickers + [new_ticker]
        data = yf.download(all_tickers, period=CORR_PERIOD)['Close']
        corr_matrix = data.corr()
        
        # Check the new ticker's correlation against all others
        correlations = corr_matrix[new_ticker].drop(new_ticker)
        
        if correlations.max() > CORR_THRESHOLD:
            print(f"  -> RISK: {new_ticker} correlation ({correlations.max():.2f}) exceeds threshold.")
            return False
            
        return True
    except Exception as e:
        print(f"  -> WARN: Correlation check failed for {new_ticker}: {e}. Defaulting to safe.")
        return True # Default to safe if yfinance fails
