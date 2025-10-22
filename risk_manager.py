import yfinance as yf
import pandas as pd
from database import SessionLocal
from database import Trade
from sqlalchemy import func

# --- CONFIGURATION ---
CORR_THRESHOLD = 0.7 
CORR_PERIOD = "3mo"
MAX_SECTOR_CONCENTRATION = 0.40 # No more than 40% of portfolio in one sector

# --- SECTOR CACHE ---
sector_cache = {}

def get_sector(ticker):
    """Fetches and caches the sector for a given ticker."""
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
    Analyzes market trend and volatility to determine the current regime.
    Returns a tuple: (trend_condition, volatility_regime)
    e.g., ('BULLISH', 'LOW')
    """
    print("--- Running Advanced Market Regime Analysis ---")
    try:
        spy_hist = yf.Ticker("SPY").history(period="1y")
        vix_hist = yf.Ticker("^VIX").history(period="1y")
        
        # Trend Condition
        spy_sma_200 = spy_hist['Close'].rolling(window=200).mean().iloc[-1]
        spy_current_price = spy_hist['Close'].iloc[-1]
        trend_condition = 'BULLISH' if spy_current_price > spy_sma_200 else 'BEARISH'

        # Volatility Regime
        vix_sma_50 = vix_hist['Close'].rolling(window=50).mean().iloc[-1]
        vix_current_level = vix_hist['Close'].iloc[-1]
        volatility_regime = 'HIGH' if vix_current_level > vix_sma_50 else 'LOW'

        print(f"  -> Trend: {trend_condition} | Volatility: {volatility_regime}")
        return trend_condition, volatility_regime
            
    except Exception as e:
        print(f"  -> Market condition analysis failed: {e}. Defaulting to NEUTRAL.")
        return 'NEUTRAL', 'HIGH'

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
