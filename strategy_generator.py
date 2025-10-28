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
    Uses Gemini to generate Python code for a new trading strategy
    --- COMPATIBLE WITH OUR VECTORIZED BACKTESTER ---
    """
    print(f"Generating new '{strategy_concept}' strategy using {', '.join(indicators)}...")
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not found.")
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro-latest')

        # --- FIX: Updated prompt ---
        prompt = f"""
        You are an expert quantitative trading strategy developer. Your task is to write a complete, syntactically correct Python class for a trading strategy that can be used with our custom vectorized backtester.

        **Strategy Requirements:**
        - Strategy Name: AiGenerated{strategy_concept.replace('-', '')}Strategy
        - Strategy Concept: A {strategy_concept} strategy.
        - Required Indicators: {', '.join(indicators)}.
        - Must use the 'pandas_ta' library (e.g., self.data.ta.sma(length=50, append=True)) to generate indicators.

        **Output Format Rules (VERY IMPORTANT):**
        1.  The code must be a single Python class that inherits from `BaseStrategy`.
        2.  The class MUST define a `generate_signals(self)` method.
        3.  The class MUST define a `@classmethod` named `get_default_params(cls)` that returns a dictionary of the default parameters for optimization.
        4.  The entire output must be ONLY the Python code, enclosed in a single markdown code block (```python ... ```). Do not include any other text, explanation, or preamble.

        **Example of a valid strategy file:**
        ```python
        import pandas as pd
        import numpy as np
        import pandas_ta as ta
        from research.backtester import BaseStrategy

        class AiGeneratedMeanReversionStrategy(BaseStrategy):
        
            @classmethod
            def get_default_params(cls):
                return {{
                    "bb_period": 20,
                    "bb_std_dev": 2.0,
                    "rsi_period": 14
                }}

            def generate_signals(self):
                # Get parameters from self.params
                bb_period = self.params.get('bb_period', 20)
                bb_std = self.params.get('bb_std_dev', 2.0)
                rsi_period = self.params.get('rsi_period', 14)
                
                # Calculate indicators
                self.data.ta.bbands(length=bb_period, std=bb_std, append=True)
                self.data.ta.rsi(length=rsi_period, append=True)
                
                # Create signal DataFrame
                signals = pd.DataFrame(index=self.data.index)
                signals['signal'] = 0.0
                
                # Generate signals
                bb_lower_col = f'BBL_{{bb_period}}_{{bb_std}}'
                rsi_col = f'RSI_{{rsi_period}}'
                
                signals['signal'] = np.where(
                    (self.data['close'] < self.data[bb_lower_col]) & (self.data[rsi_col] < 30), 
                    1.0, 
                    0.0
                )
                
                return signals
        ```
        """

        response = model.generate_content(prompt)
        
        # Extract Python code from the markdown block
        code_match = re.search(r'```python\n(.*?)```', response.text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        else:
            print("Error: AI did not return a valid Python code block.")
            print(f"RAW RESPONSE: {response.text}")
            return None

    except Exception as e:
        print(f"An error occurred during AI code generation: {e}")
        return None

if __name__ == '__main__':
    # ... (no change to this part) ...
    # --- Example Usage ---
    concept = "MeanReversion"
    inds = ["Bollinger Bands", "RSI"]

    generated_code = generate_strategy_code(concept, inds)

    if generated_code:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_DIR}/ai_{concept.lower()}_{timestamp}.py"
        
        with open(filename, 'w') as f:
            f.write("import pandas as pd\n")
            f.write("import numpy as np\n")
            f.write("import pandas_ta as ta\n")
            f.write("from research.backtester import BaseStrategy\n\n")
            f.write(generated_code)
        
        print(f"\nSuccess! New strategy code saved to: {filename}")
