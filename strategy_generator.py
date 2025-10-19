import os
from dotenv import load_dotenv
import google.generativeai as genai
import re
from datetime import datetime

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OUTPUT_DIR = 'generated_strategies'

def generate_strategy_code(strategy_concept, indicators):
    """
    Uses Gemini to generate Python code for a new trading strategy.

    Args:
        strategy_concept (str): A high-level description of the strategy (e.g., "Mean-Reversion").
        indicators (list): A list of technical indicators to use (e.g., ["Bollinger Bands", "RSI"]).

    Returns:
        str: The generated Python code, or None if an error occurs.
    """
    print(f"Generating new '{strategy_concept}' strategy using {', '.join(indicators)}...")
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not found.")
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro-latest')

        prompt = f"""
        You are an expert quantitative trading strategy developer. Your task is to write a complete, syntactically correct Python class for a trading strategy that can be used with the 'backtesting.py' library.

        **Strategy Requirements:**
        - Strategy Name: AiGenerated{strategy_concept.replace('-', '')}Strategy
        - Strategy Concept: A {strategy_concept} strategy.
        - Required Indicators: {', '.join(indicators)}.

        **Output Format Rules (VERY IMPORTANT):**
        1.  The code must be a single Python class that inherits from `backtesting.Strategy`.
        2.  The class MUST define an `init(self)` method to set up the indicators. Use the `self.I()` function to define indicators.
        3.  The class MUST define a `next(self)` method that contains the trading logic (buy and sell conditions).
        4.  The logic should be sound and representative of the requested strategy concept. For example, a mean-reversion strategy should buy on dips and sell on rallies.
        5.  Include comments explaining the logic in the `next()` method.
        6.  The entire output must be ONLY the Python code, enclosed in a single markdown code block (```python ... ```). Do not include any other text, explanation, or preamble.

        **Example of a valid `init()` method:**
        def init(self):
            self.rsi = self.I(backtesting.lib.RSI, self.data.Close, 14)

        **Example of a valid `next()` method:**
        def next(self):
            # If RSI is below 30, close any short and go long.
            if crossover(self.rsi, 30):
                self.position.close()
                self.buy()
        """

        response = model.generate_content(prompt)
        
        # Extract Python code from the markdown block
        code_match = re.search(r'```python\n(.*?)```', response.text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        else:
            print("Error: AI did not return a valid Python code block.")
            return None

    except Exception as e:
        print(f"An error occurred during AI code generation: {e}")
        return None

if __name__ == '__main__':
    # --- Example Usage ---
    # Define the type of strategy you want the AI to create.
    concept = "MeanReversion"
    # Define the tools (indicators) the AI should use.
    inds = ["Bollinger Bands", "RSI"]

    generated_code = generate_strategy_code(concept, inds)

    if generated_code:
        # Create the output directory if it doesn't exist
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        
        # Create a unique filename for the new strategy
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_DIR}/ai_{concept.lower()}_{timestamp}.py"
        
        # Save the generated code to a new Python file
        with open(filename, 'w') as f:
            # Add necessary imports at the top of the file
            f.write("from backtesting import Strategy\n")
            f.write("from backtesting.lib import crossover\n")
            f.write("import talib # Assuming common indicators might use TA-Lib\n\n")
            f.write(generated_code)
        
        print(f"\nSuccess! New strategy code saved to: {filename}")
        print("Next Step: Review the code and then use your optimization_manager.py to backtest this new file.")
