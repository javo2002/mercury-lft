import yfinance as yf
import pandas as pd

CORR_THRESHOLD = 0.7 # Don't add a new position if its avg correlation to the portfolio is > 70%
CORR_PERIOD = "1y"

def get_market_condition(spy_period=200, vix_threshold=35.0):
    """
    Analyzes multiple factors to determine the overall market condition.
    
    Returns:
        str: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    print("--- Running Market Condition Analysis ---")
    try:
        # 1. SPY Trend Check
        spy_hist = yf.Ticker("SPY").history(period=f"{spy_period + 50}d")
        if spy_hist.empty:
            print("Warning: Could not fetch SPY data. Defaulting to NEUTRAL.")
            return 'NEUTRAL'
            
        spy_sma = spy_hist['Close'].rolling(window=spy_period).mean().iloc[-1]
        spy_current_price = spy_hist['Close'].iloc[-1]
        is_uptrend = spy_current_price > spy_sma
        print(f"SPY Trend Check: Price=${spy_current_price:.2f}, SMA=${spy_sma:.2f} -> {'UPTREND' if is_uptrend else 'DOWNTREND'}")

        # 2. VIX Fear Check
        vix_hist = yf.Ticker("^VIX").history(period="5d")
        vix_current_level = vix_hist['Close'].iloc[-1]
        is_high_fear = vix_current_level > vix_threshold
        print(f"VIX Fear Check: Level={vix_current_level:.2f}, Threshold=<{vix_threshold} -> {'HIGH FEAR' if is_high_fear else 'NORMAL'}")

        # 3. Yield Curve Check
        ten_year = yf.Ticker("^TNX").history(period="5d")['Close'].iloc[-1]
        three_month = yf.Ticker("^IRX").history(period="5d")['Close'].iloc[-1]
        is_inverted = ten_year < three_month
        print(f"Yield Curve Check: 10Y={ten_year:.2f}%, 3M={three_month:.2f}% -> {'INVERTED' if is_inverted else 'NORMAL'}")

        if is_uptrend and not is_high_fear and not is_inverted:
            print("Result: Market condition is BULLISH.")
            return 'BULLISH'
        elif not is_uptrend and not is_inverted:
            print("Result: Market condition is BEARISH.")
            return 'BEARISH'
        else:
            print("Result: Market condition is NEUTRAL/UNCERTAIN. No new trades advised.")
            return 'NEUTRAL'
            
    except Exception as e:
        print(f"Error during market condition analysis: {e}")
        return 'NEUTRAL'

def is_correlation_safe(new_ticker, open_positions_tickers):
    """
    Checks if a new ticker is highly correlated with existing positions.
    """
    if not open_positions_tickers:
        return True

    print(f"--- Running Correlation Check for {new_ticker} ---")
    all_tickers = open_positions_tickers + [new_ticker]
    try:
        data = yf.download(all_tickers, period=CORR_PERIOD, progress=False)['Adj Close']
        if data.empty or data.shape[1] != len(all_tickers):
            print("  -> Warning: Could not get complete correlation data. Assuming safe.")
            return True
            
        returns = data.pct_change().dropna()
        corr_matrix = returns.corr()
        avg_corr = corr_matrix[new_ticker][open_positions_tickers].mean()
        
        print(f"  -> Average correlation of {new_ticker} to portfolio: {avg_corr:.2f}")
        
        if avg_corr > CORR_THRESHOLD:
            print(f"  -> Result: UNSAFE. Correlation ({avg_corr:.2f}) exceeds threshold ({CORR_THRESHOLD}).")
            return False
        else:
            print(f"  -> Result: SAFE. Correlation is acceptable.")
            return True

    except Exception as e:
        print(f"  -> Warning: Correlation check failed: {e}. Assuming safe.")
        return True

