import pandas as pd
from a_fast_screener import yahoo_screener

# --- CONFIGURATION ---
MIN_VOLUME = 1000000
MIN_PRICE = 20

# --- SCREENER DEFINITIONS ---

def screen_trend_stocks():
    """Finds stocks in a strong uptrend (above 50 and 200-day SMAs)."""
    print("--- Running Trend Screener ---")
    s = yahoo_screener.Screener()
    s.add_filter('regularMarketPrice', 'GREATER_THAN', MIN_PRICE)
    s.add_filter('regularMarketVolume', 'GREATER_THAN', MIN_VOLUME)
    s.add_golden_cross(50, 200)
    return s.run(20)

def screen_reversion_stocks():
    """Finds stocks that are technically "oversold" but in a long-term uptrend."""
    print("--- Running Mean-Reversion Screener ---")
    s = yahoo_screener.Screener()
    s.add_filter('regularMarketPrice', 'GREATER_THAN', MIN_PRICE)
    s.add_filter('regularMarketVolume', 'GREATER_THAN', MIN_VOLUME)
    s.add_RSI(14, 'LESS_THAN', 40)
    s.add_SMA(200, 'GREATER_THAN', 'regularMarketPrice') # Must be in long term uptrend
    return s.run(20)

# --- NEW: FUNDAMENTAL & FACTOR SCREENERS ---

def screen_value_stocks():
    """Finds fundamentally undervalued stocks (low P/E, P/B)."""
    print("--- Running Value Factor Screener ---")
    s = yahoo_screener.Screener()
    s.add_filter('regularMarketPrice', 'GREATER_THAN', MIN_PRICE)
    s.add_filter('regularMarketVolume', 'GREATER_THAN', MIN_VOLUME)
    s.add_filter('trailingPE', 'LESS_THAN', 20)
    s.add_filter('priceToBook', 'LESS_THAN', 3)
    s.add_filter('marketCap', 'GREATER_THAN', 2000000000) # Market cap > $2B
    return s.run(20)

def screen_growth_stocks():
    """Finds stocks with high revenue and earnings growth."""
    print("--- Running Growth Factor Screener ---")
    s = yahoo_screener.Screener()
    s.add_filter('regularMarketPrice', 'GREATER_THAN', MIN_PRICE)
    s.add_filter('regularMarketVolume', 'GREATER_THAN', MIN_VOLUME)
    s.add_filter('revenueGrowth', 'GREATER_THAN', 0.20) # 20%+ revenue growth
    s.add_filter('earningsGrowth', 'GREATER_THAN', 0.20) # 20%+ earnings growth
    s.add_filter('marketCap', 'GREATER_THAN', 5000000000) # Market cap > $5B
    return s.run(20)

def screen_crypto():
    """Provides a list of top cryptocurrencies to screen."""
    print("--- Generating Crypto Watchlist ---")
    return [
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
        "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD", "MATIC-USD"
    ]

def run_all_screeners():
    """Runs all defined screeners and saves the results to text files."""
    screeners = {
        "trend_screener_results.txt": screen_trend_stocks,
        "reversion_screener_results.txt": screen_reversion_stocks,
        "value_screener_results.txt": screen_value_stocks, # NEW
        "growth_screener_results.txt": screen_growth_stocks, # NEW
        "crypto_screener_results.txt": screen_crypto
    }
    for filename, function in screeners.items():
        try:
            results = function()
            with open(filename, 'w') as f:
                for ticker in results: f.write(ticker + '\n')
            print(f"Successfully saved {len(results)} tickers to {filename}")
        except Exception as e:
            print(f"Error running screener for {filename}: {e}")
            
if __name__ == "__main__":
    run_all_screeners()

