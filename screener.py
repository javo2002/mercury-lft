import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
import talib
from dotenv import load_dotenv # --- FIX: Import the library ---

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# --- FIX: Add this line to load API keys from your .env file ---
load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')

# --- The rest of the script is unchanged ---
MIN_SHARE_PRICE = 20.0
MIN_AVG_DAILY_VOLUME = 1_000_000
MIN_AVG_DOLLAR_VOLUME = 20_000_000
TOP_N_RESULTS = 30 
BATCH_SIZE = 100

TREND_OUTPUT_FILE = 'trend_screener_results.txt'
REVERSION_OUTPUT_FILE = 'reversion_screener_results.txt'
VOLATILITY_OUTPUT_FILE = 'volatility_screener_results.txt'

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def run_screener():
    if not API_KEY or not API_SECRET:
        print("Error: API_KEY and/or API_SECRET not found in .env file.")
        sys.exit(1)

    print("--- Starting Advanced Stock Screener & Ranker ---")
    trading_client = TradingClient(API_KEY, API_SECRET, paper=True)
    data_client = StockHistoricalDataClient(API_KEY, API_SECRET)

    search_params = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
    assets = trading_client.get_all_assets(search_params)
    
    tradable_symbols = [
        a.symbol for a in assets 
        if a.tradable and a.exchange in ['NASDAQ', 'NYSE', 'ARCA']
        and '.' not in a.symbol and '/' not in a.symbol and not a.symbol.endswith('W')
    ]
    print(f"Found {len(assets)} total assets. Analyzing {len(tradable_symbols)} relevant US equities.")

    scored_stocks = []
    symbol_chunks = list(chunks(tradable_symbols, BATCH_SIZE))
    
    for i, chunk in enumerate(symbol_chunks):
        print(f"Analyzing batch {i+1}/{len(symbol_chunks)}...")
        try:
            request_params = StockBarsRequest(
                symbol_or_symbols=chunk,
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=90),
                feed='iex'
            )
            bars = data_client.get_stock_bars(request_params).df
            
            if bars.empty: continue

            for symbol in bars.index.get_level_values('symbol').unique():
                symbol_bars = bars.loc[symbol]
                if symbol_bars.empty or len(symbol_bars) < 51: continue

                avg_volume = symbol_bars['volume'].mean()
                latest_close = symbol_bars['close'].iloc[-1]
                avg_dollar_volume = (symbol_bars['close'] * symbol_bars['volume']).mean()

                if (latest_close < MIN_SHARE_PRICE or 
                    avg_volume < MIN_AVG_DAILY_VOLUME or 
                    avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME):
                    continue

                sma_50 = talib.SMA(symbol_bars['close'], timeperiod=50).iloc[-1]
                trend_score = (latest_close - sma_50) / sma_50 if sma_50 > 0 else 0

                atr_14 = talib.ATR(symbol_bars['high'], symbol_bars['low'], symbol_bars['close'], timeperiod=14).iloc[-1]
                volatility_score = (atr_14 / latest_close) * 100 if latest_close > 0 else 0
                
                upper, middle, lower = talib.BBANDS(symbol_bars['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
                bbw_score = (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1] if middle.iloc[-1] > 0 else float('inf')

                scored_stocks.append({
                    'symbol': symbol,
                    'trend_score': trend_score,
                    'volatility_score': volatility_score,
                    'bbw_score': bbw_score
                })
        except Exception as e:
            print(f"Could not process batch {i+1}: {e}")
            continue
    
    print(f"\n--- Screener Complete ---")
    print(f"Found {len(scored_stocks)} liquid stocks to score and rank.")

    trend_shortlist = sorted(scored_stocks, key=lambda x: x['trend_score'], reverse=True)
    with open(TREND_OUTPUT_FILE, 'w') as f:
        for stock in trend_shortlist[:TOP_N_RESULTS]: f.write(f"{stock['symbol']}\n")
    print(f"Top {TOP_N_RESULTS} trend-following candidates saved to {TREND_OUTPUT_FILE}")

    reversion_shortlist = sorted(scored_stocks, key=lambda x: x['volatility_score'], reverse=True)
    with open(REVERSION_OUTPUT_FILE, 'w') as f:
        for stock in reversion_shortlist[:TOP_N_RESULTS]: f.write(f"{stock['symbol']}\n")
    print(f"Top {TOP_N_RESULTS} mean-reversion candidates saved to {REVERSION_OUTPUT_FILE}")

    volatility_shortlist = sorted(scored_stocks, key=lambda x: x['bbw_score'])
    with open(VOLATILITY_OUTPUT_FILE, 'w') as f:
        for stock in volatility_shortlist[:TOP_N_RESULTS]: f.write(f"{stock['symbol']}\n")
    print(f"Top {TOP_N_RESULTS} volatility-breakout candidates saved to {VOLATILITY_OUTPUT_FILE}")

if __name__ == "__main__":
    run_screener()
