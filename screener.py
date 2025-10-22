import pandas as pd
import pandas_ta as ta
import yfinance as yf
from tqdm import tqdm
import requests
from io import StringIO

# --- CONFIGURATION ---
MIN_VOLUME = 1_000_000
MIN_PRICE = 20
OUTPUT_FILES = {
    "trend": "trend_screener_results.txt",
    "reversion": "reversion_screener_results.txt",
    "volatility": "volatility_screener_results.txt"
}

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
        return [ticker.replace('.', '-') for ticker in tickers]
    except Exception as e:
        print(f"Could not fetch S&P 500 tickers: {e}")
        return []

def run_screener():
    """
    Runs technical screens on S&P 500 stocks using yfinance and pandas-ta.
    """
    print("--- Starting Screener (pandas-ta version) ---")
    tickers = get_sp500_tickers()
    if not tickers:
        print("Could not get ticker list. Exiting.")
        return {} # Return an empty dictionary on failure

    results = {"trend": [], "reversion": [], "volatility": []}
    
    # Download all data in a single, efficient batch
    print(f"Downloading data for {len(tickers)} S&P 500 stocks...")
    all_data = yf.download(tickers, period="1y", group_by='ticker', progress=True)

    print("\nAnalyzing stocks...")
    for ticker in tqdm(tickers):
        try:
            df = all_data[ticker].copy()
            if df.empty or df['Volume'].mean() < MIN_VOLUME or df['Close'].iloc[-1] < MIN_PRICE:
                continue

            # Calculate all necessary indicators at once
            df.ta.sma(length=50, append=True)
            df.ta.sma(length=200, append=True)
            df.ta.rsi(length=14, append=True)
            df.ta.bbands(length=20, append=True)
            
            last = df.iloc[-1]
            prev = df.iloc[-2]

            # Trend Screen (Golden Cross)
            if last['SMA_50'] > last['SMA_200'] and prev['SMA_50'] <= prev['SMA_200']:
                results["trend"].append(ticker)

            # Mean Reversion Screen (Oversold)
            if last['RSI_14'] < 35 and prev['RSI_14'] >= 35:
                results["reversion"].append(ticker)

            # Volatility Screen (Breakout above upper Bollinger Band)
            if last['Close'] > last['BBU_20_2.0']:
                results["volatility"].append(ticker)

        except (KeyError, IndexError):
            # This handles cases where a ticker download fails within the batch
            # print(f"Warning: Could not process data for {ticker}. It may be delisted or has incomplete data.")
            continue
            
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

