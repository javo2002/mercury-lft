import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import yfinance as yf
import pandas as pd

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

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

def get_deep_analysis(ticker):
    """
    Performs a multi-faceted deep analysis of a single ticker using AI.
    (#19, #20, #21, #25, #26)
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = f"""
    You are a world-class equity research analyst. Conduct a "Deep Dive" analysis for the stock ticker "{ticker}".
    Generate a report with the following sections using markdown formatting.

    ### 1. Multi-Source News Summary
    - Find the top 3-5 significant news headlines from the past 48 hours from financial news outlets.
    - Summarize the key narrative points into a single paragraph.

    ### 2. Social Media Sentiment
    - Analyze recent sentiment for ${ticker} on platforms like Twitter and StockTwits.
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
    (#22)
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    prompt = "List the most significant US economic events scheduled for the next 24 hours (e.g., CPI, FOMC minutes, Jobs Report). If there are none, say 'None'."
    response = model.generate_content(prompt)
    return response.text.strip().split('\n')
