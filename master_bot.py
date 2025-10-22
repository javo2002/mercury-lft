import os
from dotenv import load_dotenv
import sqlite3
import pandas as pd
import pandas_ta as ta # FIX: Import pandas_ta
from datetime import datetime, timedelta

# Use the modern Alpaca SDK
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Import project-specific modules
from risk_manager import get_market_condition, is_correlation_safe
import ai_services # To get AI conviction scores
from config import API_KEY, API_SECRET, DATABASE_FILE

# --- CONFIGURATION ---
TRADE_RISK_PERCENT = 0.01
MAX_OPEN_POSITIONS = 7
VIX_EXIT_THRESHOLD = 35.0
MAX_HOLDING_DAYS = 15
PYRAMID_PROFIT_TARGET = 1.05

# --- CLIENT INITIALIZATION ---
trading_client = TradingClient(API_KEY, API_SECRET, paper=True)
data_client = StockHistoricalDataClient(API_KEY, API_SECRET)

# --- HELPER FUNCTIONS ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def log_trade_to_db(ticker, asset_class, action, qty, price, reason, stop_price=None):
    # This function remains the same
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO trades (timestamp, ticker, asset_class, action, quantity, price, reason, trade_type, stop_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (timestamp, ticker, asset_class, action.upper(), qty, price, reason, 'AUTOMATED', stop_price)
    )
    conn.commit()
    conn.close()
    print(f"   -> Logged {action.upper()} of {qty} {ticker} to DB.")

def get_vix_level():
    # This function remains the same
    try:
        request_params = StockBarsRequest(symbol_or_symbols=["VIX"], timeframe=TimeFrame.Day, start=datetime.now() - timedelta(days=5))
        vix_bars = data_client.get_stock_bars(request_params).df
        return vix_bars['close'].iloc[-1] if not vix_bars.empty else 20.0
    except Exception:
        return 20.0

# --- MAIN TRADING LOGIC ---
def run_master_bot():
    print(f"\n--- [ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ] ---")
    print("--- Running AI-Powered Master Bot (pandas-ta version) ---")

    account = trading_client.get_account()
    if account.trading_blocked:
        print("Account is restricted from trading. Exiting.")
        return
    print(f"Account Status: ACTIVE | Equity: ${account.equity}")

    if get_vix_level() > VIX_EXIT_THRESHOLD:
        print(f"!!! VIX is above {VIX_EXIT_THRESHOLD}. Liquidating all positions. !!!")
        trading_client.close_all_positions(cancel_orders=True)
        return

    positions = trading_client.get_positions()
    conn = get_db_connection()
    for p in positions:
        print(f"Managing position in {p.symbol} ({p.side})...")
        last_trade = conn.execute("SELECT timestamp FROM trades WHERE ticker = ? ORDER BY timestamp DESC LIMIT 1", (p.symbol,)).fetchone()
        if last_trade and (datetime.now() - datetime.strptime(last_trade['timestamp'], '%Y-%m-%d %H:%M:%S')).days > MAX_HOLDING_DAYS:
            print(f"  -> TIME STOP for {p.symbol}. Closing position.")
            trading_client.close_position(p.symbol)
            continue
        if float(p.unrealized_plpc) > (PYRAMID_PROFIT_TARGET - 1):
             print(f"  -> PYRAMID SIGNAL for winning trade {p.symbol}.")
             qty_to_add = float(p.qty) * 0.25 
             market_order_data = MarketOrderRequest(symbol=p.symbol, qty=qty_to_add, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
             trading_client.submit_order(order_data=market_order_data)
             log_trade_to_db(p.symbol, 'stock', 'buy', qty_to_add, p.current_price, "Pyramid on winning trade")

    market_condition = get_market_condition()
    if market_condition == 'NEUTRAL':
        print("Market is NEUTRAL. No new signal-based trades.")
        conn.close()
        return

    open_positions_count = len(trading_client.get_positions())
    if open_positions_count >= MAX_OPEN_POSITIONS:
        print(f"Portfolio at max capacity ({open_positions_count}/{MAX_OPEN_POSITIONS}).")
        conn.close()
        return
        
    today = datetime.now().strftime('%Y-%m-%d')
    signals = conn.execute("SELECT * FROM signals WHERE date = ? AND live_signal != 'NONE'", (today,)).fetchall()
    print(f"Found {len(signals)} actionable signals in the database for today.")
    open_positions_tickers = [p.symbol for p in positions]

    for signal in signals:
        ticker, asset_class = signal['ticker'], signal['asset_class']
        if ticker in open_positions_tickers:
            continue

        trade_side = None
        if market_condition == 'BULLISH' and 'BUY' in signal['live_signal']: trade_side = 'buy'
        elif market_condition == 'BEARISH' and 'SELL' in signal['live_signal']: trade_side = 'sell'

        if trade_side:
            print(f"Processing {trade_side.upper()} signal for {ticker} ({signal['live_signal']})...")
            
            conviction = ai_services.get_trade_conviction(ticker, signal['live_signal'], market_condition)
            print(f"  -> AI Conviction Score: {conviction}")
            if conviction != "HIGH":
                print(f"  -> SKIPPING {ticker}: AI conviction is not HIGH.")
                continue

            if not is_correlation_safe(ticker, open_positions_tickers):
                print(f"  -> SKIPPING {ticker}: High correlation with portfolio.")
                continue

            try:
                equity = float(account.equity)
                trade_size_dollars = equity * TRADE_RISK_PERCENT
                
                # --- FIX: Use pandas-ta to calculate ATR for stop loss ---
                bars = data_client.get_stock_bars(StockBarsRequest(symbol_or_symbols=[ticker], timeframe=TimeFrame.Day, start=datetime.now() - timedelta(days=30))).df
                bars.ta.atr(length=14, append=True)
                atr = bars['ATRr_14'].iloc[-1]
                
                if trade_side == 'buy':
                    last_price = data_client.get_latest_stock_quote(symbol_or_symbols=[ticker])[ticker].ask_price
                    qty = trade_size_dollars / last_price
                    stop_loss_price = last_price - (atr * 2)
                    market_order_data = MarketOrderRequest(symbol=ticker, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
                    trading_client.submit_order(order_data=market_order_data)
                    log_trade_to_db(ticker, asset_class, 'buy', qty, last_price, f"AI Validated Signal: {signal['live_signal']}", stop_loss_price)
                else: # Sell
                    last_price = data_client.get_latest_stock_quote(symbol_or_symbols=[ticker])[ticker].bid_price
                    qty = trade_size_dollars / last_price
                    stop_loss_price = last_price + (atr * 2)
                    market_order_data = MarketOrderRequest(symbol=ticker, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
                    trading_client.submit_order(order_data=market_order_data)
                    log_trade_to_db(ticker, asset_class, 'sell', qty, last_price, f"AI Validated Signal: {signal['live_signal']}", stop_loss_price)

                print(f"  -> Submitted {trade_side.upper()} order for {ticker}.")
                open_positions_tickers.append(ticker)
            
            except Exception as e:
                print(f"  -> ERROR submitting order for {ticker}: {e}")

            if len(open_positions_tickers) >= MAX_OPEN_POSITIONS:
                print("Portfolio at max capacity. Halting new entries.")
                break

    conn.close()
    print("\n--- Master Bot Run Complete ---")

if __name__ == '__main__':
    run_master_bot()
