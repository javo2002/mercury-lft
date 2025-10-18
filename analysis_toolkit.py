import pandas as pd
from backtesting import Backtest
from strategies.sma_cross import SmaCross
from strategies.rsi_reversion import RsiReversion

# --- Configuration ---
OUT_OF_SAMPLE_START_DATE = '2021-01-01'
FIXED_POSITION_SIZE = 0.2

def load_data(ticker):
    """
    Loads a data file, cleans it of invalid dates and duplicates, 
    sorts it, and prepares it for backtesting.
    """
    file_path = f'data/{ticker}.csv'
    
    try:
        # 1. Load the CSV without setting the index immediately.
        data = pd.read_csv(file_path)
        
        # --- Data Cleaning ---
        # 2. Convert 'Date' column and handle junk rows.
        data['Date'] = pd.to_datetime(data['Date'], errors='coerce')
        data.dropna(subset=['Date'], inplace=True)
        
        # 3. Set the clean 'Date' column as the index.
        data.set_index('Date', inplace=True)
        
        # 4. Remove any duplicate index entries (dates).
        data = data[~data.index.duplicated(keep='first')]
        
        # 5. Sort the now-unique and clean index.
        data.sort_index(inplace=True)

        # 6. Convert all OHLCV columns to numeric types.
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')

    except FileNotFoundError:
        print(f"Data file not found for {ticker}. Please ensure it has been downloaded.")
        return None
    except Exception as e:
        print(f"Error loading data for {ticker}: {e}")
        return None

    # Ensure columns are in the correct order for backtesting and drop any remaining NaNs
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    data.dropna(inplace=True)
    return data

def optimize_sma_for_ticker(ticker):
    """Runs the full optimization for the SmaCross strategy on a given ticker."""
    print(f"--- Running SMA optimization for {ticker} ---")
    data = load_data(ticker)
    if data is None or data.empty:
        print(f"No valid data available for {ticker} after cleaning. Skipping.")
        return None
        
    in_sample_data = data[:OUT_OF_SAMPLE_START_DATE]

    if in_sample_data.empty:
        print(f"No valid in-sample data for {ticker}. Skipping.")
        return None

    bt = Backtest(in_sample_data, SmaCross, cash=10000, commission=.002, finalize_trades=True)
    
    # --- THE FIX: Add error handling for the optimization process ---
    try:
        stats, heatmap = bt.optimize(
            n1=range(20, 81, 10),
            n2=range(100, 251, 20),
            atr_multiplier=range(2, 11, 2),
            position_size=[FIXED_POSITION_SIZE],
            maximize='Equity Final [$]',
            return_heatmap=True
        )
        
        best_params_tuple = heatmap.idxmax()
        return {
            'n1': int(best_params_tuple[0]),
            'n2': int(best_params_tuple[1]),
            'atr_multiplier': float(best_params_tuple[2]),
        }
    except AssertionError as e:
        print(f"Optimization for {ticker} failed, likely due to extreme volatility or low price. Skipping. Error: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during optimization for {ticker}. Skipping. Error: {e}")
        return None


def optimize_rsi_for_ticker(ticker):
    """Runs the full optimization for the RsiReversion strategy on a given ticker."""
    print(f"--- Running RSI optimization for {ticker} ---")
    data = load_data(ticker)
    if data is None or data.empty:
        print(f"No valid data available for {ticker} after cleaning. Skipping.")
        return None
        
    in_sample_data = data[:OUT_OF_SAMPLE_START_DATE]

    if in_sample_data.empty:
        print(f"No valid in-sample data for {ticker}. Skipping.")
        return None

    bt = Backtest(in_sample_data, RsiReversion, cash=10000, commission=.002, finalize_trades=True)
    
    # --- THE FIX: Add error handling for the optimization process ---
    try:
        stats, heatmap = bt.optimize(
            rsi_period=range(10, 31, 5),
            oversold_threshold=range(15, 36, 5),
            overbought_threshold=range(65, 86, 5),
            atr_multiplier=range(1, 6, 1),
            position_size=[FIXED_POSITION_SIZE],
            maximize='Sharpe Ratio',
            return_heatmap=True
        )
        
        best_params_tuple = heatmap.idxmax()
        return {
            'rsi_period': int(best_params_tuple[0]),
            'oversold_threshold': int(best_params_tuple[1]),
            'overbought_threshold': int(best_params_tuple[2]),
            'atr_multiplier': float(best_params_tuple[3]),
        }
    except AssertionError as e:
        print(f"Optimization for {ticker} failed, likely due to extreme volatility or low price. Skipping. Error: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during optimization for {ticker}. Skipping. Error: {e}")
        return None

