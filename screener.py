# In screener.py

import pandas as pd
import pandas_ta as ta
import yfinance as yf # Keep for get_sp500_tickers only
from tqdm import tqdm
import requests
from io import StringIO
import time 

# --- NEW: Import Alpaca client ---
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from config import settings # Import settings for API keys
from datetime import datetime, timedelta # Import datetime utils

# --- CONFIGURATION ---
MIN_VOLUME = 1_000_000
MIN_PRICE = 20
OUTPUT_FILES = {
    "trend": "trend_screener_results.txt",
    "reversion": "reversion_screener_results.txt",
    "volatility": "volatility_screener_results.txt"
}

# --- NEW: Initialize Alpaca Client ---
data_client = StockHistoricalDataClient(settings.API_KEY, settings.API_SECRET)

def get_sp500_tickers():
    """Fetches the list of S&P 500 tickers from Wikipedia."""
    try:
        # A User-Agent header is crucial to avoid being blocked by web servers.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        # Wrap the HTML text in a StringIO object to ensure compatibility with pandas
        table = pd.read_html(StringIO(response.text))
        # Symbol corrections for yfinance compatibility
        tickers = table[0]['Symbol'].tolist()
        cleaned_tickers = [
            ticker.replace('.', '/').replace('/', '').replace('-','') 
            for ticker in tickers
        ]
        print(f"Fetched {len(cleaned_tickers)} tickers, first 5: {cleaned_tickers[:5]}")
        return cleaned_tickers


    except Exception as e:
        print(f"Could not fetch S&P 500 tickers: {e}")
        return []

def run_screener():
    """
    Runs technical screens on S&P 500 stocks using Alpaca and pandas-ta.
    """
    print("--- Starting Screener (Alpaca version) ---")
    tickers = get_sp500_tickers() # Uses the cleaned tickers now
    if not tickers:
        print("Could not get ticker list. Exiting.")
        return {"trend": [], "reversion": [], "volatility": []} 

    results = {"trend": [], "reversion": [], "volatility": []}
    
    print(f"Downloading data for {len(tickers)} S&P 500 stocks via Alpaca...")
    
    all_data_dict = {} 
    try:
        request_params = StockBarsRequest(
            symbol_or_symbols=tickers, # Use cleaned list
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=365) 
        )
        barset_df = data_client.get_stock_bars(request_params).df 
        
        # --- FIX: Handle potential partial failures ---
        # If some symbols fail, Alpaca might return data only for the successful ones.
        successful_symbols = barset_df.index.levels[0]
        all_data_dict = {ticker: barset_df.loc[ticker].copy() for ticker in successful_symbols}
        
        print(f"Successfully downloaded data for {len(all_data_dict)} tickers from Alpaca.")
        failed_symbols = set(tickers) - set(successful_symbols)
        if failed_symbols:
            print(f"Warning: Failed to download data for {len(failed_symbols)} symbols (e.g., {list(failed_symbols)[:5]}...).")

    except Exception as e:
        # Catch errors from the Alpaca API call itself
        print(f"!!! Major error during Alpaca download: {e}. Screener may have incomplete data. !!!")
        # Proceed with empty dict if necessary
        all_data_dict = {}

    print("\nAnalyzing stocks...")
    successful_analysis = 0
    for ticker in tqdm(all_data_dict.keys()): # Iterate through successfully downloaded tickers
        try:
            df = all_data_dict[ticker] # Get the dataframe for the ticker
            
            # Use 'close' and 'volume' (lowercase) for Alpaca data
            if df.empty or 'volume' not in df.columns or df['volume'].mean() < MIN_VOLUME or df['close'].iloc[-1] < MIN_PRICE:
                continue
            
            successful_analysis += 1 

            df.ta.sma(length=50, append=True)
            df.ta.sma(length=200, append=True)
            df.ta.rsi(length=14, append=True)
            df.ta.bbands(length=20, append=True)
            
            last = df.iloc[-1]
            prev = df.iloc[-2]

            # Trend Screen
            if 'SMA_50' in last and 'SMA_200' in last and not pd.isna(last['SMA_50']) and not pd.isna(last['SMA_200']) and \
               'SMA_50' in prev and 'SMA_200' in prev and not pd.isna(prev['SMA_50']) and not pd.isna(prev['SMA_200']):
                if last['SMA_50'] > last['SMA_200'] and prev['SMA_50'] <= prev['SMA_200']:
                    results["trend"].append(ticker)

            # Mean Reversion Screen
            if 'RSI_14' in last and not pd.isna(last['RSI_14']) and 'RSI_14' in prev and not pd.isna(prev['RSI_14']):
                 if last['RSI_14'] < 35 and prev['RSI_14'] >= 35:
                    results["reversion"].append(ticker)

            # Volatility Screen - column name might be BBU_20_2.0 or bbu_20_2.0
            bb_upper_col = next((col for col in df.columns if col.upper().startswith('BBU_')), None)
            if bb_upper_col and bb_upper_col in last and not pd.isna(last[bb_upper_col]) and 'close' in last:
                if last['close'] > last[bb_upper_col]:
                    results["volatility"].append(ticker)

        except Exception as e:
            # print(f"Warning: Could not process data for {ticker}. Error: {e}")
            continue
                
    print(f"Successfully analyzed data for {successful_analysis} tickers.")
    
    # Write results to files
    for key, filename in OUTPUT_FILES.items():
        with open(filename, 'w') as f:
            for ticker in results[key]:
                f.write(f"{ticker}\n")
        print(f"Found {len(results[key])} tickers for {key} screen. Saved to {filename}.")
            
    print("\n--- Screener Complete ---")
    return results

if __name__ == "__main__":
    run_screener()
