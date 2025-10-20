import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import talib
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
DATABASE_FILE = 'trading_data.db'
PARAMETERS_FILE = 'parameters.json'
TICKER_LIST_FILES = [
    'trend_screener_results.txt',
    'reversion_screener_results.txt',
    'volatility_screener_results.txt'
]

# --- HELPER FUNCTIONS ---
def get_all_tickers():
    """Reads all unique tickers from the screener result files."""
    all_tickers = set()
    for file_path in TICKER_LIST_FILES:
        try:
            with open(file_path, 'r') as f:
                all_tickers.update([line.strip() for line in f if line.strip()])
        except FileNotFoundError:
            print(f"Warning: Ticker file not found: {file_path}")
    return sorted(list(all_tickers))

def get_parameters():
    """Loads strategy parameters from the JSON file."""
    try:
        with open(PARAMETERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def run_signal_generation():
    """
    Fetches data from Alpaca, calculates signals using TA-Lib,
    and saves them to the SQLite database.
    """
    if not API_KEY or not API_SECRET:
        print("Error: API_KEY and/or API_SECRET not found in .env file.")
        sys.exit(1)

    print("--- Starting Daily Signal Generation (Alpaca Version) ---")
    
    tickers = get_all_tickers()
    parameters = get_parameters()
    today_str = datetime.now().strftime('%Y-%m-%d')
    data_client = StockHistoricalDataClient(API_KEY, API_SECRET)

    if not tickers:
        print("No tickers found in screener files. Exiting.")
        return

    # --- BATCH DATA FETCH ---
    print(f"Fetching data for {len(tickers)} tickers from Alpaca...")
    try:
        request_params = StockBarsRequest(
            symbol_or_symbols=tickers,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=300) # Get enough data for a 200-day SMA
        )
        barset_df = data_client.get_stock_bars(request_params).df
        print("Data fetch complete.")
    except Exception as e:
        print(f"Error fetching data from Alpaca: {e}")
        return
        
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    for ticker in tickers:
        if ticker not in barset_df.index.get_level_values('symbol'):
            print(f"Warning: No data returned for {ticker}. Skipping.")
            continue
            
        data = barset_df.loc[ticker]
        if len(data) < 200: # Ensure we have enough data for long-term indicators
            print(f"Warning: Not enough historical data for {ticker} ({len(data)} bars). Skipping.")
            continue

        print(f"Processing {ticker}...")
        try:
            close = data['close']
            last_close = close.iloc[-1]
            
            # --- SIGNAL CALCULATIONS (using TA-Lib) ---
            sma_params = parameters.get(ticker, {}).get('sma', {})
            fast_p, slow_p = sma_params.get('fast_period', 50), sma_params.get('slow_period', 200)
            sma_fast = talib.SMA(close, timeperiod=fast_p)
            sma_slow = talib.SMA(close, timeperiod=slow_p)
            sma_signal = "HOLD"
            if sma_fast.iloc[-2] <= sma_slow.iloc[-2] and sma_fast.iloc[-1] > sma_slow.iloc[-1]:
                sma_signal = "BUY"
            elif sma_fast.iloc[-2] >= sma_slow.iloc[-2] and sma_fast.iloc[-1] < sma_slow.iloc[-1]:
                sma_signal = "SELL"
                
            rsi_params = parameters.get(ticker, {}).get('rsi', {})
            rsi_p = rsi_params.get('rsi_period', 14)
            ob, os = rsi_params.get('rsi_overbought', 70), rsi_params.get('rsi_oversold', 30)
            rsi = talib.RSI(close, timeperiod=rsi_p)
            rsi_signal = "HOLD"
            if rsi.iloc[-2] >= os and rsi.iloc[-1] < os:
                rsi_signal = "BUY"
            elif rsi.iloc[-2] <= ob and rsi.iloc[-1] > ob:
                rsi_signal = "SELL"
            
            # Simplified versions for other signals
            volatility_signal = "HOLD"
            upper, _, _ = talib.BBANDS(close, timeperiod=20)
            if last_close > upper.iloc[-1]:
                volatility_signal = "BUY"

            pattern_signal = "HOLD"
            recent_high = data['high'].iloc[-21:-1].max()
            if close.iloc[-2] < recent_high and last_close > recent_high:
                pattern_signal = "BUY"
            
            # --- DETERMINE LIVE SIGNAL (with priority) ---
            live_signal = "NONE"
            if sma_signal != "HOLD": live_signal = f"SMA_{sma_signal}"
            elif rsi_signal != "HOLD": live_signal = f"RSI_{rsi_signal}"
            elif pattern_signal != "HOLD": live_signal = f"PATTERN_{pattern_signal}"
            elif volatility_signal == "BUY": live_signal = f"VOL_BUY"

            cursor.execute('''
                INSERT OR REPLACE INTO signals (ticker, asset_class, date, sma_signal, rsi_signal, volatility_signal, pattern_signal, live_signal, last_close)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticker, 'stock', today_str, sma_signal, rsi_signal, volatility_signal, pattern_signal, live_signal, last_close))

        except Exception as e:
            print(f"  -> ERROR processing {ticker}: {e}")

    conn.commit()
    conn.close()
    print("\n--- Daily Signal Generation Complete ---")

if __name__ == "__main__":
    run_signal_generation()
