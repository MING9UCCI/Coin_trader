import pandas_ta as ta
from logger import logger

class Strategy:
    def __init__(self, df):
        self.df = df

    def analyze(self):
        """
        Analyzes the data and returns a trading signal.
        Returns: 'BUY', 'SELL', or 'HOLD'
        """
        if self.df is None or self.df.empty:
            logger.warning("Empty dataframe provided to strategy.")
            return 'HOLD'

        # Calculate RSI (14 periods)
        self.df['RSI_14'] = ta.rsi(self.df['close'], length=14)
        
        # We need enough data to calculate indicators
        if len(self.df) < 15:
            return 'HOLD'

        # Get the latest closed candle and the one before it
        latest = self.df.iloc[-1]
        previous = self.df.iloc[-2]

        rsi_latest = latest['RSI_14']
        
        logger.info(f"Current RSI(14): {rsi_latest:.2f}")

        # Basic RSI Strategy:
        # Buy if RSI crosses above 30 (Oversold recovery)
        # Sell if RSI crosses above 70 (Overbought boundary)
        
        if previous['RSI_14'] < 30 and rsi_latest >= 30:
            logger.info("RSI crossed above 30. Signal: BUY")
            return 'BUY'
        elif rsi_latest >= 70:
            logger.info("RSI is 70 or above. Signal: SELL")
            return 'SELL'

        return 'HOLD'
