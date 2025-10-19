import os
from dotenv import load_dotenv
import google.generativeai as genai
import alpaca_trade_api as tradeapi
from datetime import datetime
import sqlite3
import json

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
BASE_URL = 'https://paper-api.alpaca.markets'
DATABASE_FILE = 'trading_data.db'

def get_current_positions():
    """Fetches the list of current stock positions from Alpaca."""
    try:
        api = tradeapi.REST(API_KEY, API_SECRET, base_url=BASE_URL)
        return [p.symbol for p in api.list_positions()]
    except Exception as e:
        print(f"Error fetching positions: {e}")
        return []

def classify_news_event(ticker):
    """
    Uses Gemini to classify breaking news into a specific, tradable event type.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro-latest')

        prompt = f"""
        Analyze the single most significant financial news headline for the stock ticker "{ticker}" published within the last 60-90 minutes.

        First, classify the headline into one of the following specific event types:
        - "EARNINGS_BEAT": Reports earnings better than analyst expectations.
        - "EARNINGS_MISS": Reports earnings worse than analyst expectations.
        - "FDA_APPROVAL": Receives a significant drug or product approval from the FDA.
        - "MERGER_ANNOUNCEMENT": Announces it is being acquired or is acquiring another company.
        - "ANALYST_UPGRADE": A major analyst firm upgrades the stock's rating.
        - "NONE": No significant, tradable news found.

        Respond ONLY with a valid JSON object.
        If a significant event is found, provide:
        {{
          "event_found": true,
          "event_type": "The classified event type (e.g., EARNINGS_BEAT)",
          "headline": "The exact news headline.",
          "source_url": "The URL of the source article."
        }}
        
        If no event is found, respond with:
        {{
          "event_found": false
        }}
        """
        
        response = model.generate_content(prompt)
        cleaned_response = response.text.replace('```json', '').replace('```', '').strip()
        
        return json.loads(cleaned_response)

    except Exception as e:
        print(f"Error during AI news classification for {ticker}: {e}")
        return {"event_found": False}

def run_live_monitor():
    """
    Main function to monitor for and log specific, tradable news events.
    """
    print(f"\n--- [ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ] ---")
    print("--- Running Event Detector Monitor ---")

    # For event detection, we might want to scan a broader list than just current positions
    # For now, we'll stick to positions, but this could be expanded.
    positions = get_current_positions()
    if not positions:
        print("No open positions to monitor for events. Exiting.")
        return

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    for ticker in positions:
        print(f"Scanning for events on {ticker}...")
        event_data = classify_news_event(ticker)

        if event_data.get("event_found"):
            event_type = event_data.get('event_type')
            print(f"  -> EVENT DETECTED for {ticker}: {event_type}!")
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO events (timestamp, ticker, event_type, headline, source_url)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                timestamp, ticker, event_type,
                event_data.get('headline'), event_data.get('source_url')
            ))
            conn.commit()
    
    conn.close()
    print("--- Event Detector run complete ---")

if __name__ == "__main__":
    run_live_monitor()

