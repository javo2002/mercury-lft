import yfinance as yf
import os
import sys
from datetime import datetime

# --- Configuration ---
DATA_DIR = 'data'
END_DATE = datetime.now().strftime('%Y-%m-%d')
START_DATE = '2010-01-01'

def fetch_data_for_ticker(ticker):
    """
    Fetches historical stock data for a given ticker from yfinance,
    and saves it as a clean CSV file with a proper 'Date' column.
    """
    output_file = f'{DATA_DIR}/{ticker}.csv'

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    print(f"Fetching data for {ticker} from {START_DATE} to {END_DATE}...")
    data = yf.download(ticker, start=START_DATE, end=END_DATE, auto_adjust=True)

    if data.empty:
        print(f"No data found for ticker {ticker}. Skipping.")
        return False

    # Make the 'Date' index a regular column
    data.reset_index(inplace=True)
    
    # Save to CSV, ensuring the 'Date' column is written correctly.
    # index=False prevents pandas from writing an extra unnamed index column.
    data.to_csv(output_file, index=False)
    
    print(f"Clean data file created successfully for {ticker} at: {output_file}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python data_downloader.py <TICKER>")
        sys.exit(1)
    
    ticker_to_fetch = sys.argv[1].upper()
    fetch_data_for_ticker(ticker_to_fetch)

