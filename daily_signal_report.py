import os
import sys
import json
from datetime import datetime, timedelta
import pandas as pd
import talib
from dotenv import load_dotenv # --- FIX: Import the library ---

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# --- FIX: Add this line to load API keys from your .env file ---
load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

# --- The rest of the script is unchanged ---
PARAMS_FILE = 'parameters.json'
TREND_SCREENER_FILE = 'trend_screener_results.txt'
REVERSION_SCREENER_FILE = 'reversion_screener_results.txt'
VOLATILITY_SCREENER_FILE = 'volatility_screener_results.txt'
OUTPUT_JSON_FILE = 'signal_report.json'

def load_json_file(file_path):
    if not os.path.exists(file_path): return None
    with open(file_path, 'r') as f: return json.load(f)

def get_tickers_from_file(file_path):
    try:
        with open(file_path, 'r') as f: return {line.strip() for line in f if line.strip()}
    except FileNotFoundError: return set()

def run_signal_report():
    if not API_KEY or not API_SECRET:
        print("Error: API_KEY and/or API_SECRET not found in .env file.")
        sys.exit(1)

    print("--- Generating Daily Signal Proximity Report Data ---")
    params_db = load_json_file(PARAMS_FILE)
    if not params_db:
        print(f"Error: Could not load parameters from {PARAMS_FILE}")
        return

    trend_tickers = get_tickers_from_file(TREND_SCREENER_FILE)
    reversion_tickers = get_tickers_from_file(REVERSION_SCREENER_FILE)
    volatility_tickers = get_tickers_from_file(VOLATILITY_SCREENER_FILE)
    
    data_client = StockHistoricalDataClient(API_KEY, API_SECRET)
    
    report_data = {'sma_signals': [], 'rsi_signals': [], 'volatility_signals': []}

    all_unique_tickers = sorted(list(trend_tickers.union(reversion_tickers).union(volatility_tickers)))
    if not all_unique_tickers:
        print("No tickers found in screener files. Creating empty report.")
        with open(OUTPUT_JSON_FILE, 'w') as f:
            json.dump(report_data, f, indent=4)
        return

    print(f"Fetching data for {len(all_unique_tickers)} unique tickers...")
    today = datetime.now()
    start_date = today - timedelta(days=730)
    request_params = StockBarsRequest(symbol_or_symbols=all_unique_tickers, timeframe=TimeFrame.Day, start=start_date, end=today, feed='iex')
    try:
        barset_df = data_client.get_stock_bars(request_params).df
        print("Data fetch complete.")
    except Exception as e:
        print(f"Failed to fetch historical data batch: {e}")
        return

    # --- SMA Analysis ---
    print("\nAnalyzing Trend Following (SMA) Watchlist...")
    for ticker in sorted(list(trend_tickers)):
        if ticker not in barset_df.index: continue
        ticker_data = barset_df.loc[ticker]
        params = params_db.get('sma', {}).get(ticker)
        if not params: continue
        try:
            close = ticker_data['close']
            sma1 = talib.SMA(close, timeperiod=params['n1'])
            sma2 = talib.SMA(close, timeperiod=params['n2'])
            if sma1.dropna().shape[0] < 2 or sma2.dropna().shape[0] < 2: continue
            last_close, last_sma1, last_sma2 = close.iloc[-1], sma1.iloc[-1], sma2.iloc[-1]
            prev_sma1, prev_sma2 = sma1.iloc[-2], sma2.iloc[-2]
            signal_state, proximity_percent = "", 0.0
            if prev_sma1 < prev_sma2 and last_sma1 > last_sma2: signal_state, proximity_percent = "Bullish Crossover", 1.0
            elif prev_sma1 > prev_sma2 and last_sma1 < last_sma2: signal_state, proximity_percent = "Bearish Crossover", 1.0
            else:
                proximity_ratio = last_sma1 / last_sma2 if last_sma2 > 0 else 0
                if proximity_ratio >= 1.0:
                    signal_state, proximity_percent = "Uptrend Active", min((proximity_ratio - 1.0) / 0.20, 1.0) 
                else:
                    signal_state, proximity_percent = "Approaching Bullish", proximity_ratio
            report_data['sma_signals'].append({'ticker': ticker, 'strategy': 'SMA', 'current_price': last_close, 'signal_line': last_sma2, 'indicator_value': last_sma1, 'proximity': proximity_percent, 'signal_state': signal_state, 'chart_data': { 'labels': ticker_data.index[-60:].strftime('%Y-%m-%d').tolist(), 'close': close[-60:].round(2).tolist(), 'sma1': sma1[-60:].round(2).where(pd.notna, None).tolist(), 'sma2': sma2[-60:].round(2).where(pd.notna, None).tolist(), 'n1': params['n1'], 'n2': params['n2'] }})
        except Exception as e: print(f"  - {ticker}: ERROR (SMA) - {e}")

    # --- RSI Analysis ---
    print("\nAnalyzing Mean Reversion (RSI) Watchlist...")
    for ticker in sorted(list(reversion_tickers)):
        if ticker not in barset_df.index: continue
        ticker_data = barset_df.loc[ticker]
        params = params_db.get('rsi', {}).get(ticker)
        if not params: continue
        try:
            close = ticker_data['close']
            rsi = talib.RSI(close, timeperiod=params['rsi_period'])
            if rsi.dropna().shape[0] < 2: continue
            last_close, last_rsi, prev_rsi = close.iloc[-1], rsi.iloc[-1], rsi.iloc[-2]
            oversold, overbought = params['oversold_threshold'], params['overbought_threshold']
            signal_state, proximity_percent = "Neutral", 0.5
            if prev_rsi < oversold and last_rsi > oversold: signal_state, proximity_percent = "Oversold Exit (Buy)", 1.0
            elif prev_rsi > overbought and last_rsi < overbought: signal_state, proximity_percent = "Overbought Exit (Sell)", 1.0
            else:
                if last_rsi < oversold: signal_state, proximity_percent = "Oversold", 1.0 - (last_rsi / oversold)
                elif last_rsi > overbought: signal_state, proximity_percent = "Overbought", (last_rsi - overbought) / (100 - overbought)
                else: signal_state, proximity_percent = "Neutral", (last_rsi - oversold) / (overbought - oversold)
            report_data['rsi_signals'].append({'ticker': ticker, 'strategy': 'RSI', 'current_price': last_close, 'signal_line': float(oversold), 'indicator_value': last_rsi, 'proximity': proximity_percent, 'signal_state': signal_state, 'chart_data': { 'labels': ticker_data.index[-60:].strftime('%Y-%m-%d').tolist(), 'rsi': rsi[-60:].round(2).where(pd.notna, None).tolist(), 'oversold': oversold, 'overbought': overbought, 'rsi_period': params['rsi_period'] }})
        except Exception as e: print(f"  - {ticker}: ERROR (RSI) - {e}")

    # --- Volatility Analysis ---
    print("\nAnalyzing Volatility Breakout Watchlist...")
    for ticker in sorted(list(volatility_tickers)):
        if ticker not in barset_df.index: continue
        ticker_data = barset_df.loc[ticker]
        try:
            close = ticker_data['close']
            upper_band, _, lower_band = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
            if upper_band.dropna().empty: continue
            last_close = close.iloc[-1]
            last_upper_band = upper_band.iloc[-1]
            last_lower_band = lower_band.iloc[-1]
            signal_state = "Consolidating"
            proximity = (last_close - last_lower_band) / (last_upper_band - last_lower_band) if (last_upper_band - last_lower_band) > 0 else 0.5
            if last_close > last_upper_band: signal_state = "Breakout Signal"
            report_data['volatility_signals'].append({'ticker': ticker, 'strategy': 'Volatility', 'current_price': last_close, 'signal_line': last_upper_band, 'indicator_value': last_close, 'proximity': proximity, 'signal_state': signal_state, 'chart_data': { 'labels': ticker_data.index[-60:].strftime('%Y-%m-%d').tolist(), 'close': close[-60:].round(2).tolist() }})
        except Exception as e: print(f"  - {ticker}: ERROR (Volatility) - {e}")
        
    with open(OUTPUT_JSON_FILE, 'w') as f:
        json.dump(report_data, f, indent=4)
    
    print(f"\nSignal report successfully generated and saved to {OUTPUT_JSON_FILE}")

if __name__ == "__main__":
    run_signal_report()
