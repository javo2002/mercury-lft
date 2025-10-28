import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import pandas as pd
import redis
from config import settings
from datetime import timedelta

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# --- NEW: Setup Redis Cache Connection ---
# We use db=1 to keep it separate from Celery's db=0
try:
    redis_cache = redis.StrictRedis(host='redis', port=6379, db=1, decode_responses=True)
    redis_cache.ping()
    print("Connected to Redis cache for AI services.")
except Exception as e:
    print(f"Warning: Could not connect to Redis cache. Caching will be disabled. Error: {e}")
    redis_cache = None


# --- CORE AI FUNCTIONS ---

def generate_daily_trade_plan(market_condition, signals, events):
    """
    Uses AI to generate a comprehensive daily trade plan.
    (#17, #22, #30)
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = f"""
    You are a hedge fund's lead trading analyst. It is pre-market.
    Create a concise, actionable "Daily Trade Plan" based on the following data.

    1.  **Overall Market Condition:** {market_condition}
        - If BULLISH, prioritize long trades. If BEARISH, prioritize short trades. If NEUTRAL, advise caution.

    2.  **Upcoming Economic Events (next 24h):**
        - {", ".join(events) if events else "None"}

    3.  **Top Trading Signals for Today:**
        - {" ".join([f"{s['ticker']}({s['live_signal']})" for s in signals]) if signals else "None"}

    **Task:**
    Synthesize this information into a plan with three sections:
    - **Market Thesis:** A one-sentence summary of your view for the day.
    - **Top Opportunities:** Bullet points on the 2-3 most promising signals and why.
    - **Key Risks:** Bullet points on the economic events or market conditions to watch out for.
    """
    response = model.generate_content(prompt)
    return response.text

# --- FIX: Removed yfinance dependency ---
# This function now only uses the AI's internal knowledge and real-time search.
def get_deep_analysis(ticker):
    """
    Performs a multi-faceted deep analysis of a single ticker using AI.
    (#19, #20, #21, #25, #26)
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = f"""
    You are a world-class equity research analyst. Conduct a "Deep Dive" analysis for the stock ticker "{ticker}".
    Leverage your internal knowledge and real-time search capabilities to gather the information.
    Generate a report with the following sections using markdown formatting.

    ### 1. Multi-Source News Summary
    - Find the top 3-5 significant news headlines from the past 48 hours from major financial news outlets.
    - Summarize the key narrative points into a single paragraph.

    ### 2. Social Media Sentiment
    - Analyze recent sentiment for ${ticker} on platforms like X (formerly Twitter) and StockTwits.
    - Classify the sentiment as Positive, Negative, or Mixed, and mention any trending topics.

    ### 3. Insider Activity
    - Report any significant insider buy or sell transactions in the last month.

    ### 4. Competitor Check
    - Identify the top 2 competitors for {ticker}.
    - Briefly summarize their recent stock performance (e.g., "outperforming", "underperforming").

    ### 5. Predictive Insight
    - Based on all the above, provide a single, forward-looking sentence on what might be the next catalyst for the stock.
    """
    response = model.generate_content(prompt)
    return response.text

def interpret_correlation_matrix(matrix_df):
    """
    Uses AI to interpret a correlation matrix and identify risks.
    (#27)
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = f"""
    You are a portfolio risk manager. The following is a correlation matrix for the assets in a trading portfolio.
    
    **Correlation Matrix (CSV):**
    ```
    {matrix_df.to_csv()}
    ```

    **Task:**
    - Identify the top 2 most highly correlated pairs (closest to 1.0).
    - Identify if there are any pairs with significant negative correlation (diversifiers).
    - Provide a one-paragraph summary of the portfolio's overall diversification risk.
    """
    response = model.generate_content(prompt)
    return response.text

def get_economic_events():
    """
    Uses AI to get a list of major upcoming economic events.
    --- NOW CACHED FOR 12 HOURS ---
    """
    cache_key = "economic_events"
    if redis_cache:
        try:
            cached_data = redis_cache.get(cache_key)
            if cached_data:
                print("Returning cached economic events.")
                return json.loads(cached_data)
        except Exception as e:
            print(f"Redis cache read error: {e}")

    # If not cached or Redis failed, call the API
    print("Fetching live economic events from AI.")
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = "List the most significant US economic events scheduled for the next 24 hours (e.g., CPI, FOMC minutes, Jobs Report). If there are none, say 'None'."
    response = model.generate_content(prompt)
    events_list = response.text.strip().split('\n')
    
    # Save to cache
    if redis_cache:
        try:
            redis_cache.setex(cache_key, timedelta(hours=12), json.dumps(events_list))
        except Exception as e:
            print(f"Redis cache write error: {e}")
            
    return events_list

# --- FIX: Replace the existing get_trade_conviction with this final version ---
def get_trade_conviction(ticker, signal_type, market_condition_tuple, past_lessons=None):
    """
    Uses AI to get a real-time conviction score for a specific trade,
    factoring in past lessons learned.
    Returns a JSON object: {"conviction": "HIGH/MEDIUM/LOW", "reason": "..."}
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    
    # Format past lessons for the prompt
    lessons_prompt = "No past lessons found for this ticker."
    if past_lessons:
        lessons_list = "\n".join([f"- {lesson}" for lesson in past_lessons])
        lessons_prompt = f"""**CRITICAL: Review your own critiques of your last {len(past_lessons)} trades in {ticker}:**
{lessons_list}"""

    prompt = f"""
    You are a senior risk analyst. A junior trader wants to execute a trade.
    You must provide a final conviction rating (HIGH, MEDIUM, or LOW) and a one-sentence justification.

    **Trade Details:**
    - **Ticker:** {ticker}
    - **Signal:** {signal_type} (e.g., "SMA_BUY", "RSI_SELL")
    - **Overall Market Condition:** {market_condition_tuple[0]} (e.g., "BULLISH", "BEARISH")
    - **Volatility Regime:** {market_condition_tuple[1]} (e.g., "HIGH", "LOW")

    {lessons_prompt}

    **Your Task (in order):**
    1.  **Analyze Past Lessons:** Do the past critiques reveal a recurring mistake (e.g., ignoring news, bad volatility reads)?
    2.  **Check for Conflicts:** A "BUY" signal in a "BEARISH" market is a major conflict.
    3.  **Check News:** Use your internal knowledge to find the single most important breaking news headline for {ticker} in the last 3 hours.
    4.  **Synthesize and Decide:**
        -   **HIGH:** All factors align AND no past lessons are being violated.
        -   **MEDIUM:** Factors are mixed OR a past lesson suggests caution (e.g., "Last time we ignored high volatility and were stopped out. This trade is valid, but be careful.")
        -   **LOW:** There is a major conflict (e.g., BULLISH market, SELL signal) OR a past lesson is being directly violated (e.g., "The past 3 critiques all mention being faked out by this exact signal. Do not trade.") OR there is major negative news.

    **Respond ONLY with a valid JSON object in this format:**
    {{
      "conviction": "YOUR_RATING",
      "reason": "Your one-sentence justification, explicitly mentioning a past lesson if it was relevant."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # Clean up markdown and load
        cleaned_response = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(cleaned_response)
        
        # Validate response
        if data.get("conviction") in ["HIGH", "MEDIUM", "LOW"]:
            return data
        else:
            print(f"AI response invalid: {cleaned_response}")
            return {"conviction": "LOW", "reason": "AI response was invalid."}
            
    except Exception as e:
        print(f"Error getting AI conviction: {e}")
        return {"conviction": "LOW", "reason": f"AI model failed: {e}"}


def get_post_trade_critique(ticker, action, reason, pnl):
    """
    Uses AI to analyze a completed trade and provide a learning-focused critique.
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    
    trade_outcome = "profit" if pnl > 0 else "loss"
    
    prompt = f"""
    You are a senior hedge fund mentor reviewing a junior trader's log.
    Your goal is to provide a concise, one-paragraph "key lesson" for them to learn.
    Do not be overly harsh; focus on a constructive, educational takeaway.

    **Trade Details:**
    - **Ticker:** {ticker}
    - **Action:** {action.upper()}
    - **Initial Reasoning:** "{reason}"
    - **Outcome:** A {trade_outcome} of ${pnl:.2f}

    **Task:**
    Analyze the reasoning in the context of the outcome.
    - If it was a good reason and a good outcome, what reinforced this?
    - If it was a good reason but a bad outcome, what external factor (e.g., news, volatility) might have been missed?
    - If it was a bad reason but a good outcome, why was this a lucky trade and what's the real lesson?
    - If it was a bad reason and a bad outcome, what was the primary flaw in the logic?

    Respond with ONLY the one-paragraph critique.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error getting AI critique: {e}")
        return f"AI analysis failed: {e}"
