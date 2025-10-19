import json
import yfinance as yf
from datetime import datetime
from strategies import get_sma_signal, get_rsi_signal, get_volatility_signal, get_pattern_breakout_signal
import sqlite3

# --- CONFIGURATION ---
PARAMETERS_FILE = 'parameters.json'
DATABASE_FILE = 'trading_data.db'
TICKER_LIST_FILES = [
    'trend_screener_results.txt', 'reversion_screener_results.txt',
    'value_screener_results.txt', 'growth_screener_results.txt',
    'crypto_screener_results.txt'
]

def get_all_tickers():
    all_tickers = set()
    for file_path in TICKER_LIST_FILES:
        try:
            with open(file_path, 'r') as f:
                all_tickers.update([line.strip() for line in f if line.strip()])
        except FileNotFoundError:
            print(f"Warning: Ticker file not found: {file_path}")
    return sorted(list(all_tickers))

def get_parameters():
    try:
        with open(PARAMETERS_FILE, 'r') as f: return json.load(f)
    except FileNotFoundError: return {}

def fetch_data(ticker):
    try:
        data = yf.download(ticker, period="1y", progress=False)
        return data if not data.empty else None
    except Exception: return None

def run_signal_generation():
    print("--- Starting Daily Signal Generation (Tier 1) ---")
    tickers = get_all_tickers()
    parameters = get_parameters()
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    for ticker in tickers:
        print(f"Processing {ticker}...")
        data = fetch_data(ticker)
        if data is None: continue
        
        asset_class = 'crypto' if '-' in ticker else 'stock'
        sma_params = parameters.get(ticker, {}).get('sma', {})
        rsi_params = parameters.get(ticker, {}).get('rsi', {})
        
        sma_signal = get_sma_signal(data, sma_params.get('fast_period', 50), sma_params.get('slow_period', 200))
        rsi_signal = get_rsi_signal(data, rsi_params.get('rsi_period', 14), rsi_params.get('rsi_overbought', 70), rsi_params.get('rsi_oversold', 30))
        volatility_signal = get_volatility_signal(data)
        pattern_signal = get_pattern_breakout_signal(data)

        live_signal = "NONE"
        if sma_signal != "HOLD": live_signal = f"SMA_{sma_signal}"
        elif rsi_signal != "HOLD": live_signal = f"RSI_{rsi_signal}"
        elif pattern_signal != "HOLD": live_signal = f"PATTERN_{pattern_signal}"
        elif volatility_signal == "BUY": live_signal = f"VOL_BUY"
            
        last_close = data['Close'].iloc[-1]

        cursor.execute('''
            INSERT OR REPLACE INTO signals (ticker, asset_class, date, sma_signal, rsi_signal, volatility_signal, pattern_signal, live_signal, last_close)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, asset_class, today, sma_signal, rsi_signal, volatility_signal, pattern_signal, live_signal, last_close))

    conn.commit()
    conn.close()
    print("\n--- Daily Signal Generation Complete ---")

if __name__ == "__main__":
    run_signal_generation()

