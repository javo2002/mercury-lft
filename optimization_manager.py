import os
import json
import sys
import subprocess
from analysis_toolkit import optimize_sma_for_ticker, optimize_rsi_for_ticker

# --- Configuration ---
PARAMS_FILE = 'parameters.json'
TREND_SCREENER_FILE = 'trend_screener_results.txt'
REVERSION_SCREENER_FILE = 'reversion_screener_results.txt'
PYTHON_EXECUTABLE = '/home/ubuntu/trading_bot_phase1/venv/bin/python' # Absolute path to venv python

def load_json_file(file_path):
    """Loads a JSON file, creating it if it doesn't exist."""
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r') as f:
        return json.load(f)

def save_json_file(data, file_path):
    """Saves data to a JSON file."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def get_tickers_from_file(file_path):
    """Reads a list of tickers from a text file."""
    try:
        with open(file_path, 'r') as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        print(f"Warning: Screener file '{file_path}' not found.")
        return set()

def run_optimization_manager():
    """
    Compares screener results with the parameter store and runs optimizations
    for any new, unknown tickers.
    """
    print("--- Starting Optimization Manager ---")
    
    params = load_json_file(PARAMS_FILE)
    params.setdefault('sma', {})
    params.setdefault('rsi', {})

    # --- SMA Strategy ---
    trend_tickers = get_tickers_from_file(TREND_SCREENER_FILE)
    new_trend_tickers = trend_tickers - set(params['sma'].keys())
    
    if new_trend_tickers:
        print(f"\nFound {len(new_trend_tickers)} new tickers for SMA trend optimization: {', '.join(sorted(new_trend_tickers))}")
        for ticker in sorted(new_trend_tickers):
            
            # --- AUTONOMOUS DATA FETCHING ---
            print(f"\n--- Downloading data for new ticker: {ticker} ---")
            subprocess.run([PYTHON_EXECUTABLE, 'data_downloader.py', ticker], check=True)

            print(f"--- Optimizing SMA for {ticker} ---")
            best_params = optimize_sma_for_ticker(ticker)
            if best_params:
                params['sma'][ticker] = best_params
                save_json_file(params, PARAMS_FILE)
                print(f"Saved new SMA parameters for {ticker} to {PARAMS_FILE}")
    else:
        print("\nNo new tickers found for SMA trend optimization.")

    # --- RSI Strategy ---
    reversion_tickers = get_tickers_from_file(REVERSION_SCREENER_FILE)
    new_reversion_tickers = reversion_tickers - set(params['rsi'].keys())

    if new_reversion_tickers:
        print(f"\nFound {len(new_reversion_tickers)} new tickers for RSI reversion optimization: {', '.join(sorted(new_reversion_tickers))}")
        for ticker in sorted(new_reversion_tickers):
            
            # --- AUTONOMOUS DATA FETCHING (checks if data already exists from SMA run) ---
            if not os.path.exists(f'data/{ticker}.csv'):
                print(f"\n--- Downloading data for new ticker: {ticker} ---")
                subprocess.run([PYTHON_EXECUTABLE, 'data_downloader.py', ticker], check=True)

            print(f"--- Optimizing RSI for {ticker} ---")
            best_params = optimize_rsi_for_ticker(ticker)
            if best_params:
                params['rsi'][ticker] = best_params
                save_json_file(params, PARAMS_FILE)
                print(f"Saved new RSI parameters for {ticker} to {PARAMS_FILE}")
    else:
        print("\nNo new tickers found for RSI reversion optimization.")

    print("\n--- Optimization Manager Finished ---")

if __name__ == "__main__":
    run_optimization_manager()

