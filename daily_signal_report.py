import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from config import settings
from database import SessionLocal, Signal
# --- NEW: Import numpy if needed for checking, although float() handles it ---
import numpy as np 

def run_signal_generation(screener_results):
    """
    Refactored to be importable and use screener data.
    --- MODIFIED TO FIX DB TYPE ERROR ---
    """
    print("--- Generating Daily Signals ---")

    all_unique_tickers = sorted(list(
        set(screener_results.get('trend', [])) |
        set(screener_results.get('reversion', [])) |
        set(screener_results.get('volatility', []))
    ))

    if not all_unique_tickers:
        print("No tickers from screener to process.")
        return

    data_client = StockHistoricalDataClient(settings.API_KEY, settings.API_SECRET)
    request_params = StockBarsRequest(
        symbol_or_symbols=all_unique_tickers,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=365)
    )
    barset_df = data_client.get_stock_bars(request_params).df

    session = SessionLocal()
    today = datetime.now().strftime('%Y-%m-%d')

    for ticker in all_unique_tickers:
        if ticker not in barset_df.index.get_level_values('symbol'):
            print(f"Warning: Data for ticker {ticker} not found in Alpaca results.")
            continue

        data = barset_df.loc[ticker].copy()
        if data.empty or len(data) < 201: 
             print(f"Warning: Insufficient data for {ticker} ({len(data)} bars). Skipping.")
             continue

        try:
            data.ta.sma(length=50, append=True)
            data.ta.sma(length=200, append=True)
            data.ta.rsi(length=14, append=True)
            data.ta.bbands(length=20, append=True)
        except Exception as e:
            print(f"Error calculating indicators for {ticker}: {e}")
            continue

        if len(data) < 2:
             print(f"Warning: Not enough data points after indicator calculation for {ticker}. Skipping.")
             continue

        last_row = data.iloc[-1]
        prev_row = data.iloc[-2]

        # Use .get() for safer access and check for NaN
        if last_row.get('close') is None or pd.isna(last_row.get('close')) or \
           prev_row.get('close') is None or pd.isna(prev_row.get('close')):
             print(f"Warning: Close price missing or NaN for {ticker}. Skipping signal generation.")
             continue
             
        # Check other essential columns exist and are not NaN
        required_cols = ['SMA_50', 'SMA_200', 'RSI_14']
        bb_upper_col = next((col for col in data.columns if col.upper().startswith('BBU_')), None)
        if bb_upper_col:
            required_cols.append(bb_upper_col)
            
        if any(col not in last_row or pd.isna(last_row[col]) for col in required_cols) or \
           any(col not in prev_row or pd.isna(prev_row[col]) for col in ['SMA_50', 'SMA_200', 'RSI_14']):
             print(f"Warning: Indicator values missing or NaN for {ticker}. Skipping signal generation.")
             continue

        # --- Calculate Signals ---
        volatility_signal = "BUY" if bb_upper_col and last_row['close'] > last_row[bb_upper_col] else "HOLD"

        sma_signal = "HOLD"
        if last_row['SMA_50'] > last_row['SMA_200'] and prev_row['SMA_50'] <= prev_row['SMA_200']: sma_signal = "BUY"
        elif last_row['SMA_50'] < last_row['SMA_200'] and prev_row['SMA_50'] >= prev_row['SMA_200']: sma_signal = "SELL"
        
        rsi_signal = "HOLD"
        if last_row['RSI_14'] < 30 and prev_row['RSI_14'] >= 30: rsi_signal = "BUY"
        elif last_row['RSI_14'] > 70 and prev_row['RSI_14'] <= 70: rsi_signal = "SELL"
        
        live_signal = "NONE"
        if sma_signal != "HOLD": live_signal = f"SMA_{sma_signal}"
        elif rsi_signal != "HOLD": live_signal = f"RSI_{rsi_signal}"
        elif volatility_signal == "BUY": live_signal = "VOL_BUY"

        # --- FIX: Convert last_close to standard Python float ---
        try:
            last_close_float = float(last_row['close'])
        except (TypeError, ValueError):
            print(f"Warning: Could not convert last_close '{last_row['close']}' to float for {ticker}. Skipping.")
            continue
        # --------------------------------------------------------

        signal_entry = Signal(
            ticker=ticker, asset_class='stock', date=today, sma_signal=sma_signal,
            rsi_signal=rsi_signal, volatility_signal=volatility_signal, pattern_signal='NA',
            live_signal=live_signal, 
            last_close=last_close_float # Use the converted float
        )
        session.merge(signal_entry, load=True) 

    # Commit outside the loop after processing all tickers
    try:
        session.commit()
    except Exception as e:
        print(f"Database commit failed: {e}")
        session.rollback() # Rollback on error
    finally:
        session.close() # Ensure session is closed

    print("\n--- Daily Signal Generation Complete ---")
