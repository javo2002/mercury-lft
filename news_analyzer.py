import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from newsapi import NewsApiClient
import google.generativeai as genai
import time

load_dotenv()
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

TREND_SCREENER_FILE = 'trend_screener_results.txt'
REVERSION_SCREENER_FILE = 'reversion_screener_results.txt'
OUTPUT_JSON_FILE = 'sentiment_report.json'

# --- NEW: Keywords to check for financial relevance ---
FINANCIAL_KEYWORDS = [
    'stock', 'earnings', 'shares', 'market', 'price', 'analyst', 'revenue', 
    'profit', 'growth', 'quarter', 'ipo', 'fed', 'economic', 'inflation'
]

def get_tickers_from_file(file_path):
    try:
        with open(file_path, 'r') as f: return {line.strip() for line in f if line.strip()}
    except FileNotFoundError: return set()

def is_financially_relevant(text):
    """Simple check to see if the text contains financial keywords."""
    return any(keyword in text.lower() for keyword in FINANCIAL_KEYWORDS)

def analyze_text_with_ai(headline, description):
    if not model: return {"sentiment_score": 0, "keywords": ["AI not configured"]}

    prompt = f"""
    Analyze the financial news article below.
    Respond ONLY with a JSON object with two keys: "sentiment_score" (a float from -1.0 to 1.0) and "keywords" (a Python list of 2-3 analytical terms).
    If the article is not financially relevant, return a sentiment_score of 0 and keywords ["non-financial news"].

    Headline: "{headline}"
    Description: "{description}"
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"  - AI analysis failed: {e}")
        return {"sentiment_score": 0, "keywords": ["analysis_failed"]}

def run_news_analyzer():
    print("--- Starting Advanced News & Sentiment Analyzer ---")
    if not NEWS_API_KEY or not GEMINI_API_KEY: return

    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
    global model
    model = genai.GenerativeModel('gemini-pro-latest')

    tickers = get_tickers_from_file(TREND_SCREENER_FILE).union(get_tickers_from_file(REVERSION_SCREENER_FILE))
    sentiment_data = {}
    print(f"Fetching and analyzing news for {len(tickers)} tickers...")

    for ticker in sorted(list(tickers)):
        print(f"Processing {ticker}...")
        try:
            articles = newsapi.get_everything(q=f'"{ticker}"', language='en', sort_by='relevancy', from_param=(datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'), page_size=1)
            
            if articles['status'] == 'ok' and articles['articles']:
                article = articles['articles'][0]
                headline = article['title']
                description = article['description'] or ""
                
                # --- NEW: Pre-filtering step ---
                if not is_financially_relevant(headline + description):
                    print(f"  - Skipping non-financial article for {ticker}.")
                    analysis_result = {"sentiment_score": 0, "keywords": ["non-financial news"]}
                else:
                    analysis_result = analyze_text_with_ai(headline, description)

                sentiment_data[ticker] = {
                    "date": article['publishedAt'], "headline": headline,
                    "source": article['source']['name'], **analysis_result
                }
                time.sleep(1)
        except Exception as e:
            if 'rateLimited' in str(e): print("NewsAPI rate limit reached."); break
            print(f"  - Could not process {ticker}: {e}")

    with open(OUTPUT_JSON_FILE, 'w') as f:
        json.dump(sentiment_data, f, indent=4)
    print(f"\nSuccessfully generated sentiment report for {len(sentiment_data)} tickers.")

if __name__ == "__main__":
    run_news_analyzer()
