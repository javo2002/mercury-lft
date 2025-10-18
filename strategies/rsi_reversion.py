from backtesting import Strategy
from backtesting.lib import crossover
import talib

class RsiReversion(Strategy):
    """
    A mean-reversion strategy that buys on oversold RSI and sells on overbought RSI,
    with a dynamic, volatility-based (ATR) stop-loss.
    """
    # --- Strategy Parameters to be Optimized ---
    rsi_period = 14
    oversold_threshold = 30
    overbought_threshold = 70
    atr_multiplier = 2.0

    # This will be controlled by our main script
    position_size = 1.0

    def init(self):
        """
        Initialize indicators.
        """
        close = self.data.Close
        self.rsi = self.I(talib.RSI, close, timeperiod=self.rsi_period)
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=14)

    def next(self):
        """
        Execute trading logic on each bar.
        """
        # Calculate the stop-loss price based on the current ATR value.
        current_atr = self.atr[-1]
        long_stop_price = self.data.Close[-1] - (current_atr * self.atr_multiplier)
        short_stop_price = self.data.Close[-1] + (current_atr * self.atr_multiplier)
        
        # --- Trading Logic ---
        
        # Exit condition: If in a position and RSI crosses the midline (50)
        if self.position:
            if (self.position.is_long and crossover(self.rsi, 50)) or \
               (self.position.is_short and crossover(50, self.rsi)):
                self.position.close()

        # Entry condition: Only enter if we don't already have a position
        if not self.position:
            # Buy signal: RSI crosses below the oversold threshold
            if crossover(self.oversold_threshold, self.rsi):
                self.buy(size=self.position_size, sl=long_stop_price)

            # Sell signal: RSI crosses above the overbought threshold
            elif crossover(self.rsi, self.overbought_threshold):
                self.sell(size=self.position_size, sl=short_stop_price)
