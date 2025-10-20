from backtesting import Strategy
from backtesting.lib import crossover
import talib # Assuming common indicators might use TA-Lib

import backtesting as bt
from backtesting import Strategy
from backtesting.lib import crossover

# To make this strategy self-contained and runnable, we will define the indicator
# functions here. In a real-world scenario, you would likely use a library like
# TA-Lib, which backtesting.py integrates with.
def rsi(array, n=14):
    """Relative strength index"""
    # Approximate; good enough for testing.
    import pandas as pd
    gain = pd.Series(array).diff()
    loss = gain.copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0
    rs = gain.ewm(n).mean() / -loss.ewm(n).mean()
    return 100 - 100 / (1 + rs)

def bbands(array, n=20, nd=2.0):
    """Bollinger Bands"""
    import pandas as pd
    s = pd.Series(array)
    mean = s.rolling(n).mean()
    std = s.rolling(n).std()
    upper = mean + nd * std
    lower = mean - nd * std
    # backtesting.py expects a tuple of (upper, mid, lower)
    return upper, mean, lower


class AiGeneratedMeanReversionStrategy(Strategy):
    """
    A mean-reversion trading strategy that uses Bollinger Bands and RSI.

    Entry Conditions:
    - Long: When the price closes below the lower Bollinger Band and the RSI is below the oversold threshold.
    - Short: When the price closes above the upper Bollinger Band and the RSI is above the overbought threshold.

    Exit Conditions:
    - The position is closed when the price crosses the middle Bollinger Band (the moving average),
      signaling a reversion to the mean.
    """
    # Strategy parameters (can be optimized)
    bb_period = 20
    bb_std_dev = 2.0
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought = 70

    def init(self):
        """
        Initialize the strategy's indicators.
        """
        # Price data
        self.price = self.data.Close

        # Define Bollinger Bands indicator
        # self.I() is a helper function to apply an indicator on data.
        # It handles alignment and returns a numpy array-like object.
        self.bbands = self.I(bbands, self.price, self.bb_period, self.bb_std_dev)

        # Define Relative Strength Index (RSI) indicator
        self.rsi = self.I(rsi, self.price, self.rsi_period)

    def next(self):
        """
        Define the trading logic for the next data point (bar).
        """
        # --- Entry Conditions ---

        # Check if we are not in a position
        if not self.position:
            # Long entry condition: Price is below the lower band and RSI is oversold.
            if self.price[-1] < self.bbands[2][-1] and self.rsi[-1] < self.rsi_oversold:
                # Place a buy order.
                self.buy()

            # Short entry condition: Price is above the upper band and RSI is overbought.
            elif self.price[-1] > self.bbands[0][-1] and self.rsi[-1] > self.rsi_overbought:
                # Place a sell (short) order.
                self.sell()

        # --- Exit Conditions ---

        # Check if we are currently in a position
        else:
            # If in a long position, close it if the price crosses the middle band from below.
            if self.position.is_long and crossover(self.price, self.bbands[1]):
                self.position.close()

            # If in a short position, close it if the price crosses the middle band from above.
            elif self.position.is_short and crossover(self.bbands[1], self.price):
                self.position.close()