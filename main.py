import pandas as pd
from backtesting import Backtest
from strategies.sma_cross import SmaCross
import numpy as np
import sys

# --- Configuration ---
OUT_OF_SAMPLE_START_DATE = '2021-01-01'
FIXED_POSITION_SIZE = 0.2 # Risk 20% of portfolio equity per trade

def load_data(ticker):
    """
    Loads data for a given ticker, automatically handling both the original
    malformed GOOG.csv and the new clean yfinance CSVs.
    """
    file_path = f'data/{ticker}.csv'
    try:
        # First, try loading the clean yfinance format (header on row 0, 'Date' index)
        data = pd.read_csv(file_path, header=0, index_col='Date', parse_dates=True)
        print(f"Successfully loaded clean yfinance format for {ticker}.")
    except Exception:
        # If that fails, fall back to the original malformed format parser
        print(f"Could not load clean format. Attempting to load original malformed format for {ticker}.")
        data = pd.read_csv(file_path, skiprows=3, header=None)
        data.columns = ['Date', 'Close', 'High', 'Low', 'Open', 'Volume']
        data['Date'] = pd.to_datetime(data['Date'])
        data.set_index('Date', inplace=True)
    
    # Ensure columns are in the correct order and drop any missing values
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    data.dropna(inplace=True)
    return data

def run_analysis_for_ticker(ticker):
    """
    Performs a full quantitative analysis workflow for a given ticker.
    """
    print(f"\n{'='*60}")
    print(f"Starting Full Analysis for Ticker: {ticker}")
    print(f"{'='*60}")

    # --- Data Loading and Cleaning ---
    try:
        data = load_data(ticker)
    except Exception as e:
        print(f"Failed to load data for {ticker}. Error: {e}")
        return

    # --- Data Splitting: In-Sample and Out-of-Sample ---
    in_sample_data = data[:OUT_OF_SAMPLE_START_DATE]
    out_of_sample_data = data[OUT_OF_SAMPLE_START_DATE:]
    print(f"\nData split into In-Sample ({in_sample_data.index[0].date()} to {in_sample_data.index[-1].date()}) and Out-of-Sample ({out_of_sample_data.index[0].date()} to {out_of_sample_data.index[-1].date()}).")

    # --- Step 1: Optimize Strategy Parameters on IN-SAMPLE data ---
    print(f"\n[1/2] Optimizing strategy parameters for {ticker} on In-Sample data...")
    bt_optimize = Backtest(in_sample_data, SmaCross, cash=10000, commission=.002, finalize_trades=True)
    
    stats_optimize, heatmap = bt_optimize.optimize(
        n1=range(20, 81, 5),
        n2=range(100, 251, 10),
        atr_multiplier=range(2, 11, 1),
        position_size=[FIXED_POSITION_SIZE],
        maximize='Equity Final [$]',
        return_heatmap=True
    )
    print(f"\n--- Best In-Sample Optimization Results for {ticker} ---")
    print(stats_optimize)

    best_params = heatmap.idxmax()
    print(f"\nOptimal parameters for {ticker}: n1={best_params[0]}, n2={best_params[1]}, atr_multiplier={best_params[2]}")

    # --- Step 2: Run Final Validation on OUT-OF-SAMPLE data ---
    print(f"\n[2/2] Running final validation test for {ticker} on Out-of-Sample data...")
    bt_validation = Backtest(out_of_sample_data, SmaCross, cash=10000, commission=.002, finalize_trades=True)
    
    stats_validation = bt_validation.run(
        n1=best_params[0],
        n2=best_params[1],
        atr_multiplier=int(best_params[2]),
        position_size=FIXED_POSITION_SIZE
    )

    print(f"\n--- Final OUT-OF-SAMPLE Performance for {ticker} ---")
    print(stats_validation)
    print("---------------------------------------\n")

    print(f"Generating final Out-of-Sample plot for {ticker}...")
    output_filename = f"{ticker}_validation_plot.html"
    bt_validation.plot(resample=False, filename=output_filename, open_browser=False)
    print(f"Plot saved to {output_filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <TICKER>")
        print("Example: python main.py AAPL")
        sys.exit(1)
    
    ticker_to_run = sys.argv[1].upper()
    run_analysis_for_ticker(ticker_to_run)