import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from config import settings
from database import SessionLocal, Signal

def run_signal_generation(screener_results): # Accepts data
    """
    Refactored to be importable and use screener data.
    """
    print("--- Generating Daily Signals ---")
    
    all_unique_tickers = sorted(list(
        screener_results['trend_screener_results'] |
        screener_results['reversion_screener_results'] |
        screener_results['volatility_screener_results']
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
            continue
            
        data = barset_df.loc[ticker].copy()
        data.ta.strategy(ta.Strategy(
            name="mercury_signals",
            ta=[
                {"kind": "sma", "length": 50}, {"kind": "sma", "length": 200},
                {"kind": "rsi", "length": 14}, {"kind": "bbands", "length": 20},
            ]
        ))

        last_row = data.iloc[-1]
        prev_row = data.iloc[-2]

        sma_signal = "HOLD"
        if last_row['SMA_50'] > last_row['SMA_200'] and prev_row['SMA_50'] <= prev_row['SMA_200']: sma_signal = "BUY"
        elif last_row['SMA_50'] < last_row['SMA_200'] and prev_row['SMA_50'] >= prev_row['SMA_200']: sma_signal = "SELL"

        rsi_signal = "HOLD"
        if last_row['RSI_14'] < 30 and prev_row['RSI_14'] >= 30: rsi_signal = "BUY"
        elif last_row['RSI_14'] > 70 and prev_row['RSI_14'] <= 70: rsi_signal = "SELL"
            
        volatility_signal = "HOLD"
        if last_row['close'] > last_row['BBU_20_2.0']: volatility_signal = "BUY"

        live_signal = "NONE"
        if sma_signal != "HOLD": live_signal = f"SMA_{sma_signal}"
        elif rsi_signal != "HOLD": live_signal = f"RSI_{rsi_signal}"
        elif volatility_signal == "BUY": live_signal = "VOL_BUY"
        
        signal_entry = Signal(
            ticker=ticker, asset_class='stock', date=today, sma_signal=sma_signal,
            rsi_signal=rsi_signal, volatility_signal=volatility_signal, pattern_signal='NA',
            live_signal=live_signal, last_close=last_row['close']
        )
        session.merge(signal_entry)
        
    session.commit()
    session.close()
    print("\n--- Daily Signal Generation Complete ---")
