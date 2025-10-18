from backtesting import Strategy
from backtesting.lib import crossover
from backtesting.test import SMA
import talib

class SmaCross(Strategy):
    """
    A trend-following strategy with a dynamic, volatility-based (ATR) stop-loss
    that can be disabled for analysis.
    """
    # --- Strategy Parameters ---
    n1 = 50
    n2 = 200
    
    # --- Phase 2 Refined: ATR Stop-Loss Parameter ---
    # A value > 0 sets the stop as a multiple of ATR.
    # A value <= 0 disables the stop-loss.
    atr_multiplier = 2.0

    # This will be controlled by our Kelly Criterion calculation in main.py.
    position_size = 1.0

    def init(self):
        """
        Initialize indicators, including the Average True Range (ATR).
        """
        close = self.data.Close
        self.sma1 = self.I(SMA, close, self.n1)
        self.sma2 = self.I(SMA, close, self.n2)
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=14)

    def next(self):
        """
        Execute trading logic on each bar with a dynamic stop-loss.
        """
        long_stop_price = None
        short_stop_price = None

        # Only calculate a stop-loss if the multiplier is positive
        if self.atr_multiplier > 0:
            current_atr = self.atr[-1]
            long_stop_price = self.data.Close[-1] - (current_atr * self.atr_multiplier)
            short_stop_price = self.data.Close[-1] + (current_atr * self.atr_multiplier)

        # Buy signal: fast SMA crosses above slow SMA
        if crossover(self.sma1, self.sma2):
            self.position.close()
            # Pass the dynamically calculated 'sl' (which can be None)
            self.buy(size=self.position_size, sl=long_stop_price)

        # Sell signal: fast SMA crosses below slow SMA
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            # Pass the dynamically calculated 'sl' (which can be None)
            self.sell(size=self.position_size, sl=short_stop_price)