import json
from datetime import datetime
from database import SessionLocal, Sentiment
import ai_services

def run_news_analysis(screener_results): # Accepts data
    """
    Refactored to be importable and use screener data.
    """
    print("--- Starting Daily News Sentiment Analysis ---")
    all_tickers = sorted(list(
        screener_results['trend_screener_results'] |
        screener_results['reversion_screener_results'] |
        screener_results['volatility_screener_results']
    ))
    
    if not all_tickers:
        print("No tickers from screener to analyze.")
        return

    today = datetime.now().strftime('%Y-%m-%d')
    session = SessionLocal()

    for ticker in all_tickers:
        print(f"Analyzing news for {ticker}...")
        sentiment_data = ai_services.analyze_sentiment_with_ai(ticker)

        sentiment_entry = Sentiment(
            ticker=ticker, date=today,
            sentiment_score=sentiment_data.get('sentiment_score', 0.0),
            sentiment_label=sentiment_data.get('sentiment_label', 'Neutral'),
            keywords=json.dumps(sentiment_data.get('keywords', [])),
            top_headline=sentiment_data.get('top_headline', 'N/A')
        )
        session.merge(sentiment_entry)

    session.commit()
    session.close()
    print("\n--- Daily News Sentiment Analysis Complete ---")
