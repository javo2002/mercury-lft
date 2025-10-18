import talib
import pandas as pd

def get_rsi_signal(ticker_data: pd.DataFrame, params: dict):
    """
    Analyzes historical data for a ticker and returns an RSI signal if one exists.
    
    Args:
        ticker_data: A pandas DataFrame with the ticker's historical OHLCV data.
        params: A dictionary with RSI parameters.

    Returns:
        A tuple of (signal, close_price, atr_value). Signal is 'BUY', 'SELL', or None.
    """
    try:
        close = ticker_data['close']
        rsi = talib.RSI(close, timeperiod=params['rsi_period'])
        
        if rsi.dropna().shape[0] < 2:
            return None, None, None

        prev_rsi, last_rsi = rsi.iloc[-2], rsi.iloc[-1]
        oversold = params['oversold_threshold']
        overbought = params['overbought_threshold']

        # --- OPTIMIZED / STRATEGIC FIX: Conventional RSI Logic ---
        # Buy when RSI crosses back OUT of oversold territory
        if prev_rsi < oversold and last_rsi > oversold:
            signal = 'BUY'
        # Sell when RSI crosses back OUT of overbought territory
        elif prev_rsi > overbought and last_rsi < overbought:
            signal = 'SELL' # Note: This is a short-selling signal.
        else:
            signal = None
            
        if signal:
            atr = talib.ATR(ticker_data['high'], ticker_data['low'], close, timeperiod=14).iloc[-1]
            return signal, close.iloc[-1], atr

        return None, None, None

    except Exception as e:
        print(f"Error calculating RSI signal: {e}")
        return None, None, None
