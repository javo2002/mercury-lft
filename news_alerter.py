import os
import sys
from newsapi import NewsApiClient
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from transformers import pipeline
from datetime import datetime, timedelta

# --- CONFIGURATION ---
# API keys should be set as environment variables on your server
load_dotenv()
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_CHANNEL = '#trading-alerts'

# File where the screener saves its results
SCREENER_RESULTS_FILE = 'screener_results.txt'

# --- Keywords and Thresholds ---
HIGH_IMPACT_KEYWORDS = [
    'earnings', 'guidance', 'forecast', 'fda', 'lawsuit', 'acquisition',
    'merger', 'investigation', 'takeover', 'partnership', 'approval', 'rating change'
]
SENTIMENT_CONFIDENCE_THRESHOLD = 0.95

def get_tickers_from_screener():
    """Reads the list of tickers from the screener's output file."""
    try:
        with open(SCREENER_RESULTS_FILE, 'r') as f:
            tickers = [line.strip() for line in f if line.strip()]
        print(f"Successfully read {len(tickers)} tickers from {SCREENER_RESULTS_FILE}.")
        return tickers
    except FileNotFoundError:
        print(f"Warning: Screener results file '{SCREENER_RESULTS_FILE}' not found. No tickers to monitor.")
        return []
    except Exception as e:
        print(f"Error reading screener file: {e}")
        return []

def get_recent_news(ticker):
    # ... (This function remains unchanged) ...
    print(f"Fetching news for {ticker}...")
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    from_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    try:
        articles = newsapi.get_everything(q=ticker,
                                          from_param=from_date,
                                          language='en',
                                          sort_by='relevancy',
                                          page_size=10)
        return articles['articles']
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return []

def send_slack_alert(message):
    # ... (This function remains unchanged) ...
    try:
        client = WebClient(token=SLACK_BOT_TOKEN)
        client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
        print("Slack alert sent successfully.")
    except SlackApiError as e:
        print(f"Error sending Slack alert: {e.response['error']}")

def run_news_analysis():
    """Main function to analyze news for dynamically screened tickers."""
    
    # --- DYNAMIC TICKER LIST ---
    # Instead of a preset list, we now read from the screener's output
    tickers_to_monitor = get_tickers_from_screener()
    if not tickers_to_monitor:
        print("No tickers to analyze. Exiting.")
        return

    print("Initializing sentiment analysis pipeline (this may take a moment)...")
    sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
    print("Pipeline initialized. Starting news analysis cycle.")

    for ticker in tickers_to_monitor:
        articles = get_recent_news(ticker)
        if not articles:
            continue

        for article in articles:
            title = article['title']
            url = article['url']

            found_keyword = next((keyword for keyword in HIGH_IMPACT_KEYWORDS if keyword in title.lower()), None)
            sentiment_result = sentiment_pipeline(title)[0]
            label = sentiment_result['label']
            score = sentiment_result['score']

            alert = False
            reason = ""
            if found_keyword:
                alert = True
                reason = f"High-Impact Keyword Found: '{found_keyword}'"
            elif score > SENTIMENT_CONFIDENCE_THRESHOLD and label == 'NEGATIVE':
                alert = True
                reason = f"Strong Negative Sentiment Detected"

            if alert:
                alert_message = (
                    f"🚨 *Automated Trading Alert for ${ticker}*\n\n"
                    f"*Reason:* {reason}\n"
                    f"*Headline:* {title}\n"
                    f"*Sentiment:* {label} (Confidence: {score:.0%})\n"
                    f"*Action Recommended:* Review and consider pausing associated trading bots before the next market open.\n"
                    f"*Source:* <{url}|Read Article>"
                )
                send_slack_alert(alert_message)

    print("News analysis cycle complete.")

if __name__ == "__main__":
    if 'YOUR_NEWS_API_KEY' in NEWS_API_KEY or 'YOUR_SLACK_BOT_TOKEN' in SLACK_BOT_TOKEN:
        print("ERROR: API keys for NewsAPI and Slack are not configured.")
        print("Please edit the script and replace the placeholder keys.")
        sys.exit(1)

    run_news_analysis()

