from backtesting import Strategy
from backtesting.lib import crossover
import talib # Assuming common indicators might use TA-Lib

import backtesting
from backtesting import Strategy
from backtesting.lib import crossover, crossunder

# It's good practice to import indicator functions directly if they are used.
# However, to strictly follow the example `backtesting.lib.RSI`, we can skip this.
# For this implementation, we will define them within the class for clarity.


class AiGeneratedMeanReversionStrategy(Strategy):
    """
    A mean-reversion trading strategy that uses Bollinger Bands and RSI.
    It enters a long position when the price drops below the lower Bollinger Band
    and RSI indicates an oversold condition. It enters a short position when the
    price breaks above the upper Bollinger Band and RSI indicates an overbought condition.
    The strategy assumes that such extreme price movements are temporary and will
    revert to their mean.
    """

    # --- Strategy Parameters ---
    # These can be optimized by the backtesting framework.
    bb_period = 20
    bb_std_dev = 2.0
    rsi_period = 14
    rsi_oversold_threshold = 30
    rsi_overbought_threshold = 70

    def init(self):
        """
        This method is called by the framework once at the beginning of the backtest.
        We use it to initialize our indicators.
        """
        # Calculate Bollinger Bands using the data's closing prices.
        # The self.I() function is a helper that wraps indicator functions.
        # It ensures that the indicator is calculated correctly on the data.
        self.bbands = self.I(
            backtesting.lib.BBANDS,
            self.data.Close,
            self.bb_period,
            self.bb_std_dev
        )

        # Calculate the Relative Strength Index (RSI).
        self.rsi = self.I(
            backtesting.lib.RSI,
            self.data.Close,
            self.rsi_period
        )

    def next(self):
        """
        This method is called by the framework for each time step (e.g., each bar).
        It contains the core logic of the strategy for making trading decisions.
        """

        # --- Long Entry Condition ---
        # We consider going long if the price has moved to an extreme low.
        # Condition 1: The closing price crosses below the lower Bollinger Band.
        # Condition 2: The RSI is below the oversold threshold, confirming weak momentum.
        is_oversold = self.rsi[-1] < self.rsi_oversold_threshold
        price_crosses_lower_band = crossunder(self.data.Close, self.bbands.LowerBand)

        if price_crosses_lower_band and is_oversold:
            # If a short position is open, close it before entering a long position.
            self.position.close()
            # Enter a long position.
            self.buy()

        # --- Short Entry Condition ---
        # We consider going short if the price has moved to an extreme high.
        # Condition 1: The closing price crosses above the upper Bollinger Band.
        # Condition 2: The RSI is above the overbought threshold, confirming strong, but potentially overextended, momentum.
        is_overbought = self.rsi[-1] > self.rsi_overbought_threshold
        price_crosses_upper_band = crossover(self.data.Close, self.bbands.UpperBand)

        if price_crosses_upper_band and is_overbought:
            # If a long position is open, close it before entering a short position.
            self.position.close()
            # Enter a short position.
            self.sell()