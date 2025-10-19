import os
from dotenv import load_dotenv
import google.generativeai as genai
import json

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
PARAMETERS_FILE = 'parameters.json'

def suggest_new_parameters(strategy_name, ticker, existing_params):
    """
    Uses AI to suggest new parameter ranges to test for a given strategy.
    (#16)
    """
    model = genai.GenerativeModel('gemini-pro-latest')
    
    prompt = f"""
    You are a quantitative researcher. Your goal is to optimize a trading strategy's parameters.

    - **Ticker:** {ticker}
    - **Strategy:** {strategy_name}
    - **Current Parameters:** {json.dumps(existing_params)}

    **Task:**
    Based on the strategy type, suggest a new, slightly different set of parameters to test in a backtest. For example, if the current SMA periods are (50, 200), you might suggest (40, 180). If the RSI period is 14, you might suggest 12 or 16.

    Provide your answer ONLY as a valid JSON object with the new parameters.
    
    Example for SMA: {{ "fast_period": 40, "slow_period": 180 }}
    Example for RSI: {{ "rsi_period": 12, "rsi_overbought": 75, "rsi_oversold": 25 }}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Error generating new parameters: {e}")
        return None

if __name__ == '__main__':
    print("--- AI Parameter Optimization Suggester ---")
    
    try:
        with open(PARAMETERS_FILE, 'r') as f:
            all_params = json.load(f)
    except FileNotFoundError:
        print(f"Error: {PARAMETERS_FILE} not found. Cannot run optimization.")
        exit()

    # --- Example Usage ---
    # We want to find new parameters for the 'sma' strategy on 'AAPL'
    target_ticker = 'AAPL'
    target_strategy = 'sma'

    if target_ticker in all_params and target_strategy in all_params[target_ticker]:
        current_params = all_params[target_ticker][target_strategy]
        print(f"\nRequesting new parameter suggestions for {target_ticker} ({target_strategy})...")
        print(f"Current parameters: {current_params}")
        
        new_params = suggest_new_parameters(target_strategy, target_ticker, current_params)
        
        if new_params:
            print(f"\nAI Suggestion for next backtest run: {new_params}")
            # Here, you would integrate this with your optimization_manager.py
            # to automatically run a new backtest with these parameters.
    else:
        print(f"No existing parameters found for {target_ticker} and strategy {target_strategy}.")
