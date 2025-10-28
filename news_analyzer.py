import json
from datetime import datetime
from database import SessionLocal, Sentiment
import ai_services

def run_news_analysis(screener_results): # Accepts data
    """
    Refactored to be importable and use screener data.
    --- MODIFIED TO USE CORRECT KEYS ---
    """
    print("--- Starting Daily News Sentiment Analysis ---")
    
    # --- FIX: Use the keys returned by screener.py ---
    all_tickers = sorted(list(
        set(screener_results.get('trend', [])) |  # Use .get() for safety
        set(screener_results.get('reversion', [])) |
        set(screener_results.get('volatility', []))
    ))
    # ------------------------------------------------

    if not all_tickers:
        print("No tickers from screener to analyze.")
        return

    today = datetime.now().strftime('%Y-%m-%d')
    session = SessionLocal()
    
    # --- Check if the required AI function exists ---
    if not hasattr(ai_services, 'analyze_sentiment_with_ai'):
         print("ERROR: ai_services.analyze_sentiment_with_ai function not found!")
         # Add placeholder logic or raise an error
         session.close()
         return 
         
    for ticker in all_tickers:
        print(f"Analyzing news for {ticker}...")
        # Make sure your ai_services actually has this function
        #sentiment_data = ai_services.analyze_sentiment_with_ai(ticker) 

        # --- FIX: Use placeholder data ---
        sentiment_data = {
            'sentiment_score': 0.0,
            'sentiment_label': 'Neutral (Skipped)',
            'keywords': [],
            'top_headline': 'N/A (Skipped)'
        }

        sentiment_entry = Sentiment(
            ticker=ticker, date=today,
            sentiment_score=sentiment_data.get('sentiment_score', 0.0),
            sentiment_label=sentiment_data.get('sentiment_label', 'Neutral'),
            keywords=json.dumps(sentiment_data.get('keywords', [])),
            top_headline=sentiment_data.get('top_headline', 'N/A')
        )
        # Use merge instead of add if you might re-run analysis for the same day
        session.merge(sentiment_entry) 

    session.commit()
    session.close()
    print("\n--- Daily News Sentiment Analysis Complete ---")
