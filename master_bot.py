import os
import sys
import json
import time
import csv
from datetime import datetime, timedelta
import pandas as pd
import talib
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# --- Import all strategy and utility modules ---
from live_bot_sma import get_sma_signal
from live_bot_rsi import get_rsi_signal
from live_bot_volatility import get_volatility_signal
from risk_manager import is_safe_to_trade

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
PARAMS_FILE = 'parameters.json'
TRADE_LOG_FILE = 'trade_log.csv'
POSITION_SIZE = 0.2
TREND_SCREENER_FILE = 'trend_screener_results.txt'
REVERSION_SCREENER_FILE = 'reversion_screener_results.txt'
VOLATILITY_SCREENER_FILE = 'volatility_screener_results.txt'

# --- Utility Functions ---
def load_json_file(file_path):
    if not os.path.exists(file_path): return {}
    with open(file_path, 'r') as f: return json.load(f)

def get_tickers_from_file(file_path):
    try:
        with open(file_path, 'r') as f: return {line.strip() for line in f if line.strip()}
    except FileNotFoundError: return set()

def execute_trade(trading_client, ticker, strategy_name, signal, close_price, atr_value, atr_multiplier):
    """Handles the logic for submitting buy or sell orders."""
    print(f"--- Executing trade for {ticker} with signal: {signal} ---")
    try:
        trading_client.close_position(ticker)
        print(f"Closed any existing position for {ticker} to ensure fresh entry.")
        time.sleep(1)
    except Exception:
        pass # No position to close

    equity = float(trading_client.get_account().equity)
    qty = int((equity * POSITION_SIZE) / close_price)
    
    if qty <= 0:
        print(f"Calculated quantity is zero. Skipping trade.")
        return

    side = OrderSide.BUY if signal == 'BUY' else OrderSide.SELL
    stop_price = close_price - (atr_value * atr_multiplier) if side == OrderSide.BUY else close_price + (atr_value * atr_multiplier)

    order_data = MarketOrderRequest(symbol=ticker, qty=qty, side=side, time_in_force=TimeInForce.DAY, stop_loss={'stop_price': stop_price})
    trading_client.submit_order(order_data=order_data)
    print(f"Submitted {side.value} order for {qty} shares of {ticker}.")

# --- Portfolio Management Function ---
def manage_open_positions(trading_client, data_client, params_db):
    print("\n--- Managing Open Positions ---")
    try:
        positions = trading_client.get_all_positions()
        if not positions:
            print("No open positions to manage.")
            return

        print(f"Found {len(positions)} open positions to check.")
        position_symbols = [p.symbol for p in positions]
        
        request_params = StockBarsRequest(symbol_or_symbols=position_symbols, timeframe=TimeFrame.Day, start=datetime.now() - timedelta(days=300))
        barset_df = data_client.get_stock_bars(request_params).df

        for p in positions:
            print(f"Checking exit conditions for {p.symbol}...")
            if p.symbol not in barset_df.index:
                print(f"  - Could not get data for {p.symbol}, skipping.")
                continue
            
            ticker_data = barset_df.loc[p.symbol]
            
            # Check SMA Exit (Bearish Crossover)
            sma_params = params_db.get('sma', {}).get(p.symbol)
            if sma_params:
                sma_signal, _, _ = get_sma_signal(ticker_data, sma_params)
                if sma_signal == 'SELL':
                    print(f"  - SMA SELL signal detected for {p.symbol}. Closing position.")
                    trading_client.close_position(p.symbol)
                    continue

            # Check RSI Exit (Crosses below 50)
            rsi_params = params_db.get('rsi', {}).get(p.symbol)
            if rsi_params:
                rsi = talib.RSI(ticker_data['close'], timeperiod=rsi_params['rsi_period'])
                if not rsi.empty and rsi.iloc[-1] < 50:
                     print(f"  - RSI SELL signal detected (RSI < 50) for {p.symbol}. Closing position.")
                     trading_client.close_position(p.symbol)
                     continue
            
            print(f"  - No exit signal for {p.symbol}. Holding.")
    except Exception as e:
        print(f"Error managing open positions: {e}")

# --- Main Bot Logic ---
def run_master_bot():
    print("--- Starting Master Bot Execution ---")
    
    trading_client = TradingClient(API_KEY, API_SECRET, paper=True)
    data_client = StockHistoricalDataClient(API_KEY, API_SECRET)
    
    if not is_safe_to_trade(data_client):
        print("\nRisk Manager: Halting new trades.")
        return

    params_db = load_json_file(PARAMS_FILE)

    # 1. Manage existing positions BEFORE looking for new ones
    manage_open_positions(trading_client, data_client, params_db)
    
    # 2. Look for new entry signals
    print("\n--- Searching for New Entry Signals ---")
    trend_tickers = get_tickers_from_file(TREND_SCREENER_FILE)
    reversion_tickers = get_tickers_from_file(REVERSION_SCREENER_FILE)
    volatility_tickers = get_tickers_from_file(VOLATILITY_SCREENER_FILE)

    all_unique_tickers = sorted(list(trend_tickers.union(reversion_tickers).union(volatility_tickers)))
    print(f"Found {len(all_unique_tickers)} unique tickers to analyze for new trades.")

    if not all_unique_tickers:
        print("No tickers to analyze for new signals.")
        return

    request_params = StockBarsRequest(symbol_or_symbols=all_unique_tickers, timeframe=TimeFrame.Day, start=datetime.now() - timedelta(days=730))
    barset_df = data_client.get_stock_bars(request_params).df
    
    strategies = {
        'SMA': {'tickers': trend_tickers, 'signal_func': get_sma_signal},
        'RSI': {'tickers': reversion_tickers, 'signal_func': get_rsi_signal},
        'Volatility': {'tickers': volatility_tickers, 'signal_func': get_volatility_signal}
    }

    for strat_key, config in strategies.items():
        print(f"\n--- Analyzing {len(config['tickers'])} {strat_key} candidates for entry ---")
        for ticker in sorted(list(config['tickers'])):
            if ticker not in barset_df.index: continue
            
            ticker_data = barset_df.loc[ticker]
            params = params_db.get(strat_key.lower(), {}).get(ticker, {})
            atr_multiplier = params.get('atr_multiplier', 2.0)
            
            signal, close_price, atr_value = config['signal_func'](ticker_data, params)
            
            if signal:
                execute_trade(trading_client, ticker, strat_key, signal, close_price, atr_value, atr_multiplier)
            else:
                print(f"No new {strat_key} signal for {ticker}.")

    print("\n--- Master Bot Execution Complete ---")

if __name__ == "__main__":
    if not API_KEY or not API_SECRET:
        print("Error: API Keys not set. Did you create a .env file?")
        sys.exit(1)
    run_master_bot()

