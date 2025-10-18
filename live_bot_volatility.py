import talib
import pandas as pd

def get_volatility_signal(ticker_data: pd.DataFrame, params: dict):
    """
    Analyzes data for a Bollinger Band breakout signal.
    
    Args:
        ticker_data: DataFrame with historical OHLCV data.
        params: A dictionary (currently unused but good for future expansion).

    Returns:
        A tuple of (signal, close_price, atr_value). Signal is 'BUY' or None.
    """
    try:
        close = ticker_data['close']
        
        upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        
        if upper.dropna().empty:
            return None, None, None

        last_close = close.iloc[-1]
        last_upper = upper.iloc[-1]
        
        # Simple Breakout Logic: Buy if today's close is above the upper band
        if last_close > last_upper:
            signal = 'BUY'
            atr = talib.ATR(ticker_data['high'], ticker_data['low'], close, timeperiod=14).iloc[-1]
            return signal, last_close, atr

        return None, None, None

    except Exception as e:
        print(f"Error calculating volatility signal: {e}")
        return None, None, None
