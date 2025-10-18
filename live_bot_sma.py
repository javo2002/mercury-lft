import talib
import pandas as pd

def get_sma_signal(ticker_data: pd.DataFrame, params: dict):
    """
    Analyzes historical data for a ticker and returns an SMA signal if one exists.
    
    Args:
        ticker_data: A pandas DataFrame with the ticker's historical OHLCV data.
        params: A dictionary containing the parameters 'n1' and 'n2'.

    Returns:
        A tuple of (signal, close_price, atr_value). Signal is 'BUY', 'SELL', or None.
    """
    try:
        close = ticker_data['close']
        sma1 = talib.SMA(close, timeperiod=params['n1'])
        sma2 = talib.SMA(close, timeperiod=params['n2'])
        
        if sma1.dropna().shape[0] < 2 or sma2.dropna().shape[0] < 2:
            return None, None, None

        prev_sma1, last_sma1 = sma1.iloc[-2], sma1.iloc[-1]
        prev_sma2, last_sma2 = sma2.iloc[-2], sma2.iloc[-1]

        if prev_sma1 < prev_sma2 and last_sma1 > last_sma2:
            signal = 'BUY'
        elif prev_sma1 > prev_sma2 and last_sma1 < last_sma2:
            signal = 'SELL'
        else:
            signal = None
            
        if signal:
            atr = talib.ATR(ticker_data['high'], ticker_data['low'], close, timeperiod=14).iloc[-1]
            return signal, close.iloc[-1], atr

        return None, None, None

    except Exception as e:
        print(f"Error calculating SMA signal: {e}")
        return None, None, None
