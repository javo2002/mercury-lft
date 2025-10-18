import os
from datetime import datetime, timedelta
import talib
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# --- Load API keys from .env file ---
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

def is_safe_to_trade(data_client: StockHistoricalDataClient):
    """
    Checks if the overall market condition is safe for taking new long positions.
    Returns True if safe, False otherwise.
    """
    print("\n--- Running Risk Manager ---")
    try:
        # Re-initialize the client if one isn't passed, ensuring keys are loaded
        if not data_client:
            if not API_KEY or not API_SECRET: raise ValueError("API keys not found for Risk Manager")
            data_client = StockHistoricalDataClient(API_KEY, API_SECRET)

        spy_request = StockBarsRequest(
            symbol_or_symbols=["SPY"],
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=300),
            feed='iex'
        )
        spy_bars = data_client.get_stock_bars(spy_request).df
        
        if spy_bars.empty:
            print("Risk Manager: Could not fetch SPY data. Defaulting to NOT SAFE.")
            return False
        
        spy_close = spy_bars['close'].iloc[-1]
        spy_sma_200 = talib.SMA(spy_bars['close'], timeperiod=200).iloc[-1]
        
        if spy_close > spy_sma_200:
            print(f"Risk Manager: Market is SAFE (SPY Close ${spy_close:.2f} > 200-SMA ${spy_sma_200:.2f})")
            return True
        else:
            print(f"Risk Manager: Market is NOT SAFE (SPY Close ${spy_close:.2f} <= 200-SMA ${spy_sma_200:.2f})")
            return False
            
    except Exception as e:
        print(f"Risk Manager Error: {e}. Defaulting to NOT SAFE.")
        return False
