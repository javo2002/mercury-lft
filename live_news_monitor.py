import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
import json

# --- FIX: Import new libraries ---
from alpaca.trading.client import TradingClient
from database import SessionLocal, Event
from config import settings

# --- CONFIGURATION ---
# --- FIX: Configure GenAI and Alpaca Client from central settings ---
genai.configure(api_key=settings.GEMINI_API_KEY)
trading_client = TradingClient(settings.API_KEY, settings.API_SECRET, paper=True)


def get_current_positions():
    """Fetches the list of current stock positions from Alpaca."""
    try:
        # --- FIX: Use new alpaca-py client ---
        positions = trading_client.get_all_positions()
        return [p.symbol for p in positions]
    except Exception as e:
        print(f"Error fetching positions: {e}")
        return []

def classify_news_event(ticker):
    """
    Uses Gemini to classify breaking news into a specific, tradable event type.
    (This function logic remains the same)
    """
    try:
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
    Main function to monitor for and log specific, tradable news events
    using SQLAlchemy.
    """
    print(f"\n--- [ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ] ---")
    print("--- Running Event Detector Monitor (SQLAlchemy version) ---")

    positions = get_current_positions()
    if not positions:
        print("No open positions to monitor for events. Exiting.")
        return

    # --- FIX: Use SQLAlchemy session ---
    session = SessionLocal()
    try:
        for ticker in positions:
            print(f"Scanning for events on {ticker}...")
            event_data = classify_news_event(ticker)

            if event_data.get("event_found"):
                event_type = event_data.get('event_type')
                print(f"  -> EVENT DETECTED for {ticker}: {event_type}!")
                
                # --- FIX: Create Event object and add to session ---
                event_entry = Event(
                    timestamp=datetime.now().isoformat(),
                    ticker=ticker,
                    event_type=event_type,
                    headline=event_data.get('headline'),
                    source_url=event_data.get('source_url')
                )
                session.add(event_entry)
                
        session.commit()
    except Exception as e:
        print(f"Error during event monitor loop: {e}")
        session.rollback()
    finally:
        session.close()
    
    print("--- Event Detector run complete ---")

if __name__ == "__main__":
    run_live_monitor()
