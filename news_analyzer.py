import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
import sqlite3

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_FILE = 'trading_data.db'
TICKER_LIST_FILES = [
    'trend_screener_results.txt',
    'reversion_screener_results.txt',
    'volatility_screener_results.txt'
]

def get_all_tickers():
    """Reads all unique tickers from the screener result files."""
    all_tickers = set()
    for file_path in TICKER_LIST_FILES:
        try:
            with open(file_path, 'r') as f:
                tickers = [line.strip() for line in f if line.strip()]
                all_tickers.update(tickers)
        except FileNotFoundError:
            print(f"Warning: Ticker file not found: {file_path}")
    return sorted(list(all_tickers))

def analyze_sentiment_with_ai(ticker):
    """
    Uses the Gemini AI to find the latest news and analyze its sentiment.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')

        prompt = f"""
        Analyze the most recent, significant financial news for the stock ticker "{ticker}" from the last 24 hours.
        Provide a JSON response with the following fields:
        - "sentiment_score": A float between -1.0 (very negative) and 1.0 (very positive).
        - "sentiment_label": A string ("Positive", "Negative", or "Neutral").
        - "keywords": A list of 3-5 important keywords from the news.
        - "top_headline": The single most important news headline.

        If there is no significant news, return a neutral sentiment.
        """
        
        response = model.generate_content(prompt)
        # Clean up the response to be valid JSON
        cleaned_response = response.text.replace('```json', '').replace('```', '').strip()
        
        return json.loads(cleaned_response)

    except Exception as e:
        print(f"Error during AI sentiment analysis for {ticker}: {e}")
        return {
            "sentiment_score": 0.0,
            "sentiment_label": "Neutral",
            "keywords": [],
            "top_headline": "AI analysis failed or no news found."
        }

def run_news_analysis():
    """
    Main function to analyze news for all tickers and save results to the database.
    """
    print("--- Starting Daily News Sentiment Analysis ---")
    tickers = get_all_tickers()
    today = datetime.now().strftime('%Y-%m-%d')

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not found in .env file. Cannot run analysis.")
        return
        
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    for ticker in tickers:
        print(f"Analyzing news for {ticker}...")
        sentiment_data = analyze_sentiment_with_ai(ticker)

        # Insert or update data in the database
        cursor.execute('''
            INSERT OR REPLACE INTO sentiment (ticker, date, sentiment_score, sentiment_label, keywords, top_headline)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            ticker,
            today,
            sentiment_data.get('sentiment_score', 0.0),
            sentiment_data.get('sentiment_label', 'Neutral'),
            json.dumps(sentiment_data.get('keywords', [])), # Store list as JSON string
            sentiment_data.get('top_headline', 'N/A')
        ))

    conn.commit()
    conn.close()
    
    print("\n--- Daily News Sentiment Analysis Complete ---")
    print(f"All sentiment data for {today} has been saved to the database.")

if __name__ == "__main__":
    run_news_analysis()
