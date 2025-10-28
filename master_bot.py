import os
from dotenv import load_dotenv
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

# Use the modern Alpaca SDK
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# --- Import SQLAlchemy session and models ---
from database import SessionLocal, Trade, Signal, PostTradeAnalysis
from sqlalchemy import text, desc

# Import project-specific modules
from risk_manager import get_market_condition, is_correlation_safe
import ai_services # AI services are still used for learning loop, not conviction
from config import settings # Use central settings

# --- CONFIGURATION ---
TRADE_RISK_PERCENT = 0.01
MAX_OPEN_POSITIONS = 7
VIX_EXIT_THRESHOLD = 35.0
MAX_HOLDING_DAYS = 15
PYRAMID_PROFIT_TARGET = 1.05

# --- CLIENT INITIALIZATION ---
trading_client = TradingClient(settings.API_KEY, settings.API_SECRET, paper=True) # For trading, quotes, positions
data_client = StockHistoricalDataClient(settings.API_KEY, settings.API_SECRET) # For historical data

# --- HELPER FUNCTIONS ---
def log_trade_to_db(session, ticker, asset_class, action, qty, price, reason, stop_price=None):
    """Logs trade details to the database using SQLAlchemy."""
    timestamp = datetime.now().isoformat()
    trade = Trade(
        client_order_id=f"auto_{ticker}_{timestamp}", # Generate a unique ID
        timestamp=timestamp,
        ticker=ticker,
        asset_class=asset_class,
        action=action.upper(),
        quantity=qty,
        price=price,
        reason=reason,
        trade_type='AUTOMATED',
        stop_price=stop_price
    )
    session.add(trade)
    session.commit()
    print(f"   -> Logged {action.upper()} of {qty} {ticker} to DB.")

def get_vix_level():
    """Fetches the current VIX level using Alpaca."""
    try:
        request_params = StockBarsRequest(
            symbol_or_symbols=["VIX"], # Assuming Alpaca uses 'VIX'
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=5)
            )
        vix_bars = data_client.get_stock_bars(request_params).df
        # Handle potential multi-index for single symbol request if API behavior varies
        if isinstance(vix_bars.index, pd.MultiIndex):
             if 'VIX' in vix_bars.index.levels[0]:
                  vix_bars = vix_bars.loc['VIX']
             else:
                  print("Warning: VIX data not found in multi-index response.")
                  return 20.0 # Default if VIX specifically missing

        return vix_bars['close'].iloc[-1] if not vix_bars.empty else 20.0
    except Exception as e:
        print(f"Error getting VIX level: {e}. Defaulting to 20.")
        return 20.0

# --- MAIN TRADING LOGIC ---
def run_master_bot():
    print(f"\n--- [ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ] ---")
    print("--- Running AI-Powered Master Bot (v4 - No Realtime AI Conviction) ---")

    account = trading_client.get_account()
    if account.trading_blocked:
        print("Account is restricted from trading. Exiting.")
        return
    print(f"Account Status: ACTIVE | Equity: ${account.equity}")

    current_vix = get_vix_level()
    print(f"Current VIX Level: {current_vix:.2f}")
    if current_vix > VIX_EXIT_THRESHOLD:
        print(f"!!! VIX is above {VIX_EXIT_THRESHOLD}. Liquidating all positions. !!!")
        try:
            trading_client.close_all_positions(cancel_orders=True)
            print("   -> All positions liquidated due to high VIX.")
        except Exception as e:
            print(f"   -> ERROR liquidating positions: {e}")
        return # Stop further processing if VIX is too high

    session = SessionLocal()
    try:
        positions = trading_client.get_all_positions()

        # --- Manage Existing Positions ---
        for p in positions:
            print(f"Managing position in {p.symbol} ({p.side})...")
            last_trade = session.query(Trade.timestamp).filter(Trade.ticker == p.symbol).order_by(Trade.timestamp.desc()).first()

            # Time Stop Check
            if last_trade and (datetime.now() - datetime.fromisoformat(last_trade[0])).days > MAX_HOLDING_DAYS:
                print(f"  -> TIME STOP for {p.symbol} (Held > {MAX_HOLDING_DAYS} days). Closing position.")
                try:
                    trading_client.close_position(p.symbol)
                except Exception as e:
                    print(f"  -> ERROR closing position for {p.symbol}: {e}")
                continue # Move to next position

            # Pyramid Check (only if position is profitable)
            current_price_str = p.current_price
            if current_price_str and float(p.unrealized_plpc) > 0: # Check only profitable trades
                try:
                    current_price_float = float(current_price_str)
                    profit_target_threshold = PYRAMID_PROFIT_TARGET - 1 # e.g., 0.05 for 1.05 target
                    if float(p.unrealized_plpc) > profit_target_threshold:
                         print(f"  -> PYRAMID SIGNAL for winning trade {p.symbol} (+{(float(p.unrealized_plpc)*100):.2f}% profit).")
                         qty_to_add = float(p.qty) * 0.25 # Add 25%
                         market_order_data = MarketOrderRequest(symbol=p.symbol, qty=qty_to_add, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
                         trading_client.submit_order(order_data=market_order_data)
                         log_trade_to_db(session, p.symbol, 'stock', 'buy', qty_to_add, current_price_float, "Pyramid on winning trade")
                except ValueError:
                    print(f"  -> Warning: Could not parse current_price '{current_price_str}' for {p.symbol} during pyramid check.")
                except Exception as e:
                     print(f"  -> ERROR submitting pyramid order for {p.symbol}: {e}")
            elif not current_price_str:
                 print(f"  -> Warning: Missing current_price for {p.symbol}, cannot check pyramid condition.")

        # --- Evaluate New Trades ---
        market_condition_tuple = get_market_condition() # e.g., ('BULLISH', 'LOW')
        market_condition = market_condition_tuple[0]

        if market_condition == 'NEUTRAL':
            print("Market is NEUTRAL. No new signal-based trades.")
            session.close() # Close session before returning
            return

        # Fetch fresh positions list after potential closures/pyramiding
        positions = trading_client.get_all_positions()
        open_positions_count = len(positions)
        if open_positions_count >= MAX_OPEN_POSITIONS:
            print(f"Portfolio at max capacity ({open_positions_count}/{MAX_OPEN_POSITIONS}). No new entries.")
            session.close() # Close session before returning
            return

        today = datetime.now().strftime('%Y-%m-%d')
        signals = session.query(Signal).filter(Signal.date == today, Signal.live_signal != 'NONE').all()
        print(f"Found {len(signals)} actionable signals in the database for today.")
        open_positions_tickers = [p.symbol for p in positions]

        for signal in signals:
            ticker, asset_class = signal.ticker, signal.asset_class
            if ticker in open_positions_tickers:
                continue # Skip if already holding

            trade_side = None
            if market_condition == 'BULLISH' and 'BUY' in signal.live_signal: trade_side = 'buy'
            elif market_condition == 'BEARISH' and 'SELL' in signal.live_signal: trade_side = 'sell'

            if trade_side:
                print(f"Processing {trade_side.upper()} signal for {ticker} ({signal.live_signal})...")

                # --- Skip AI Conviction Check ---
                print(f"  -> Skipping AI Conviction Check (Free Tier). Proceeding based on signal/market alignment.")
                reason = f"Signal={signal.live_signal}, Market={market_condition_tuple[0]}" # Basic reason for log
                # ----------------------------------

                if not is_correlation_safe(ticker, open_positions_tickers):
                    print(f"  -> SKIPPING {ticker}: High correlation with portfolio.")
                    continue

                try:
                    equity = float(account.equity)
                    trade_size_dollars = equity * TRADE_RISK_PERCENT

                    # --- Robust ATR calculation ---
                    atr_start_date = datetime.now() - timedelta(days=60)
                    bars_request = StockBarsRequest(
                        symbol_or_symbols=[ticker],
                        timeframe=TimeFrame.Day,
                        start=atr_start_date
                    )
                    bars = data_client.get_stock_bars(bars_request).df

                    if isinstance(bars.index, pd.MultiIndex):
                         if ticker in bars.index.levels[0]:
                              bars = bars.loc[ticker]
                         else:
                              raise ValueError(f"No bar data returned specifically for {ticker}")

                    if bars.empty or len(bars) < 15:
                        raise ValueError(f"Insufficient bar data for ATR calculation ({len(bars)} bars)")
                    if 'close' not in bars.columns or 'high' not in bars.columns or 'low' not in bars.columns:
                         raise ValueError("Bar data missing required columns (close, high, low)")

                    # Calculate ATR using pandas_ta
                    bars.ta.atr(length=14, append=True)
                    atr_col = next((col for col in bars.columns if col.upper().startswith('ATRr_')), None)

                    if not atr_col or atr_col not in bars.columns or pd.isna(bars[atr_col].iloc[-1]):
                        # Fallback calculation if pandas_ta fails or returns NaN
                        print(f"  -> Warning: pandas_ta ATR failed for {ticker}. Using fallback.")
                        high_low = bars['high'] - bars['low']
                        high_close = abs(bars['high'] - bars['close'].shift())
                        low_close = abs(bars['low'] - bars['close'].shift())
                        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                        # Simple Moving Average of True Range as fallback (EWMA can be sensitive to starting NaNs)
                        atr = tr.rolling(window=14).mean().iloc[-1] 
                        if pd.isna(atr) or atr <= 0:
                             raise ValueError(f"Fallback ATR calculation also resulted in invalid value: {atr}")
                    else:
                        atr = bars[atr_col].iloc[-1] # Use pandas_ta result if valid

                    if atr <= 0: # Final check
                         raise ValueError(f"Final ATR value is invalid: {atr}")

                    print(f"  -> Calculated ATR for {ticker}: {atr:.4f}")
                    # --- End of ATR ---

                    if trade_side == 'buy':
                        quote = trading_client.get_latest_stock_quote(symbol_or_symbols=[ticker])
                        if ticker not in quote or not quote[ticker].ask_price:
                             raise ValueError("Could not get latest ask price")
                        last_price = quote[ticker].ask_price
                        qty = trade_size_dollars / last_price
                        stop_loss_price = last_price - (atr * 2) # Example stop logic
                        market_order_data = MarketOrderRequest(symbol=ticker, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
                        trading_client.submit_order(order_data=market_order_data)
                        log_trade_to_db(session, ticker, asset_class, 'buy', qty, last_price, f"Signal Based: {reason}", stop_loss_price)
                    
                    else: # Sell
                        quote = trading_client.get_latest_stock_quote(symbol_or_symbols=[ticker])
                        if ticker not in quote or not quote[ticker].bid_price:
                             raise ValueError("Could not get latest bid price")
                        last_price = quote[ticker].bid_price
                        qty = trade_size_dollars / last_price
                        stop_loss_price = last_price + (atr * 2) # Example stop logic
                        market_order_data = MarketOrderRequest(symbol=ticker, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
                        trading_client.submit_order(order_data=market_order_data)
                        log_trade_to_db(session, ticker, asset_class, 'sell', qty, last_price, f"Signal Based: {reason}", stop_loss_price)

                    print(f"  -> Submitted {trade_side.upper()} order for {ticker}.")
                    open_positions_tickers.append(ticker) # Add to list to prevent duplicate orders in same run

                except Exception as e:
                    print(f"  -> ERROR preparing/submitting order for {ticker}: {e}") # Log specific error

                # Check if max positions reached after attempting trade
                if len(open_positions_tickers) >= MAX_OPEN_POSITIONS:
                    print("Portfolio at max capacity after trade attempt. Halting new entries for this run.")
                    break # Exit signal loop for this run
                    
    except Exception as e:
        print(f"ERROR in master bot loop: {e}")
        session.rollback() # Rollback potentially failed DB operations
    finally:
        session.close() # Ensure session is always closed
        print("\n--- Master Bot Run Complete ---")

if __name__ == '__main__':
    run_master_bot()
