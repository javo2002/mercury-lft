import yfinance as yf
import pandas as pd
import os
import sys # Import the sys module to read command-line arguments

def fetch_and_save_clean_data(ticker):
    """
    Fetches historical stock data for a given ticker, ensures it's in the correct format,
    and saves it as a clean CSV file ready for backtesting.
    """
    # --- Configuration ---
    START_DATE = '2010-01-01'
    END_DATE = '2023-12-31'
    DATA_DIR = 'data'
    OUTPUT_FILE = f'{DATA_DIR}/{ticker}.csv'

    # Create the data directory if it doesn't exist
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    print(f"Fetching data for {ticker} from {START_DATE} to {END_DATE}...")

    # Download the data using yfinance
    data = yf.download(ticker, start=START_DATE, end=END_DATE)

    if data.empty:
        print(f"No data found for ticker {ticker}. Please check the ticker symbol and date range.")
        return

    # Explicitly name the index column to 'Date'
    data.index.name = 'Date'

    # Save the DataFrame to a CSV file
    data.to_csv(OUTPUT_FILE)
    
    print(f"Clean data file created successfully for {ticker} at: {OUTPUT_FILE}")

if __name__ == "__main__":
    # Check if a ticker was provided as a command-line argument
    if len(sys.argv) < 2:
        print("Usage: python data_fetcher.py <TICKER>")
        print("Example: python data_fetcher.py AAPL")
        sys.exit(1) # Exit if no ticker is provided
    
    # The first argument is the script name, the second is the ticker
    ticker_to_fetch = sys.argv[1].upper()
    fetch_and_save_clean_data(ticker_to_fetch)