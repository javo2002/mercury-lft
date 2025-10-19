import os
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
from risk_manager import get_market_condition, is_correlation_safe
import yfinance as yf

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv('API_KEY'); API_SECRET = os.getenv('API_SECRET')
BASE_URL = 'https://paper-api.alpaca.markets'; DATABASE_FILE = 'trading_data.db'
ATR_PERIOD = 14; ATR_MULTIPLIER = 2.5
MAX_OPEN_POSITIONS = 7; MAX_SECTOR_CONCENTRATION = 0.4 
VIX_EXIT_THRESHOLD = 40.0; MAX_HOLDING_DAYS = 15
PYRAMID_PROFIT_TARGET = 1.05 # Add to position if it's up 5% from entry

# --- HELPER FUNCTIONS ---
sector_cache = {}

def get_alpaca_api():
    try:
        api = tradeapi.REST(API_KEY, API_SECRET, base_url=BASE_URL, api_version='v2')
        api.get_account()
        return api
    except Exception: return None

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_atr(ticker, period):
    try:
        data = yf.download(ticker, period=f"{period*2}d", progress=False)
        if data.empty: return None
        high_low = data['High'] - data['Low']
        high_close = abs(data['High'] - data['Close'].shift())
        low_close = abs(data['Low'] - data['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(window=period).mean().iloc[-1]
    except Exception: return None
    
def get_sector(ticker):
    if ticker in sector_cache: return sector_cache[ticker]
    try:
        info = yf.Ticker(ticker).info
        sector = info.get('sector', 'Unknown')
        sector_cache[ticker] = sector
        return sector
    except Exception: return "Unknown"

def log_trade_to_db(ticker, asset_class, action, qty, price, reason, stop_price=None):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO trades (timestamp, ticker, asset_class, action, quantity, price, reason, trade_type, stop_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (timestamp, ticker, asset_class, action.upper(), qty, price, reason, 'AUTOMATED', stop_price)
    )
    conn.commit()
    conn.close()

# --- TRADING LOGIC ---
def run_master_bot():
    print(f"\n--- [ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ] ---")
    print("--- Running Master Bot (Tier 1 Complete) ---")
    
    api = get_alpaca_api()
    if not api: return

    # --- 0. PRE-MARKET & PORTFOLIO CHECKS ---
    try:
        vix_data = yf.download('^VIX', period="5d", progress=False)
        if vix_data['Close'].iloc[-1] > VIX_EXIT_THRESHOLD:
            print("VIX SPIKE! Liquidating all positions."); api.close_all_positions(cancel_orders=True); return
    except Exception: pass

    positions = api.list_positions()
    conn = get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    signals = conn.execute("SELECT * FROM signals WHERE date = ?", (today,)).fetchall()
    signal_map = {s['ticker']: s['live_signal'] for s in signals}

    # --- 1. POSITION MANAGEMENT (STOPS, TIME EXITS, & PYRAMIDING) ---
    for p in positions:
        print(f"Managing position in {p.symbol} ({p.side})...")
        is_long = p.side == 'long'
        asset_class = 'crypto' if '/' in p.symbol else 'stock'
        db_ticker = p.symbol.replace('/', '-') if asset_class == 'crypto' else p.symbol
        last_trade_action = 'BUY' if is_long else 'SELL'
        last_trade = conn.execute(f"SELECT * FROM trades WHERE ticker = ? AND action = '{last_trade_action}' ORDER BY timestamp DESC LIMIT 1", (db_ticker,)).fetchone()
        
        if not last_trade: continue

        entry_time = datetime.strptime(last_trade['timestamp'], '%Y-%m-%d %H:%M:%S')
        if (datetime.now() - entry_time).days > MAX_HOLDING_DAYS:
            print(f"  -> TIME STOP for {p.symbol}. Closing position."); api.close_position(p.symbol); continue

        current_price = float(p.current_price); stop_price = float(last_trade['stop_price']) if last_trade['stop_price'] else 0
        if stop_price > 0 and ((is_long and current_price < stop_price) or (not is_long and current_price > stop_price)):
            print(f"  -> TRAILING STOP for {p.symbol}. Closing position."); api.close_position(p.symbol); continue

        current_signal = signal_map.get(db_ticker)
        entry_price = float(last_trade['price'])
        if is_long and current_signal and 'BUY' in current_signal and current_price > (entry_price * PYRAMID_PROFIT_TARGET):
            print(f"  -> PYRAMID SIGNAL for winning trade {p.symbol}. Adding to position.")
            try:
                qty_to_add = (1000 / current_price) / 2
                api.submit_order(symbol=p.symbol, qty=qty_to_add, side='buy', type='limit', time_in_force='day', limit_price=round(current_price * 1.001, 2))
                log_trade_to_db(db_ticker, asset_class, 'buy', qty_to_add, current_price, f"Pyramid on {current_signal}", stop_price)
            except Exception as e:
                print(f"    -> ERROR adding to position: {e}")
                
    # --- 2. NEW TRADE ENTRY LOGIC ---
    market_condition = get_market_condition()
    if market_condition == 'NEUTRAL':
        print("Market is NEUTRAL. No new signal-based trades."); conn.close(); return

    positions = api.list_positions()
    if len(positions) >= MAX_OPEN_POSITIONS:
        print(f"Portfolio at max capacity ({len(positions)}/{MAX_OPEN_POSITIONS})."); conn.close(); return
        
    open_positions_tickers = [p.symbol.replace('/','-') for p in positions]
    for signal in signals:
        ticker, asset_class = signal['ticker'], signal['asset_class']
        api_symbol = ticker.replace('-', '/') if asset_class == 'crypto' else ticker
        
        trade_side = None
        if market_condition == 'BULLISH' and 'BUY' in signal['live_signal']: trade_side = 'buy'
        elif market_condition == 'BEARISH' and 'SELL' in signal['live_signal']: trade_side = 'sell'

        if trade_side and ticker not in open_positions_tickers:
            print(f"Found new {trade_side.upper()} signal for {ticker}.")

            if not is_correlation_safe(ticker, open_positions_tickers):
                print(f"  -> SKIPPING {ticker} due to high correlation with portfolio.")
                continue

            try:
                atr = get_atr(ticker, ATR_PERIOD)
                if not atr: continue
                
                if trade_side == 'buy':
                    quote = api.get_latest_quote(api_symbol)
                    limit_price = quote.ask_price * 1.001
                    initial_stop = limit_price - (atr * ATR_MULTIPLIER)
                else: # sell
                    quote = api.get_latest_quote(api_symbol)
                    limit_price = quote.bid_price * 0.999
                    initial_stop = limit_price + (atr * ATR_MULTIPLIER)

                qty = 1000 / limit_price
                api.submit_order(symbol=api_symbol, qty=qty, side=trade_side, type='limit', time_in_force='day', limit_price=round(limit_price, 2))
                log_trade_to_db(ticker, asset_class, trade_side, qty, limit_price, f"Signal: {signal['live_signal']}", initial_stop)
                open_positions_tickers.append(ticker) # Add to list for subsequent correlation checks
            except Exception as e:
                print(f"  -> ERROR submitting order for {api_symbol}: {e}")
            
            if len(open_positions_tickers) >= MAX_OPEN_POSITIONS:
                print("Portfolio has now reached max capacity. Halting new entries for this run.")
                break

    conn.close()
    print("\n--- Master Bot Tier 1 Run Complete ---")

if __name__ == '__main__':
    run_master_bot()

