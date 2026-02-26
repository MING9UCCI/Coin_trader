import pandas_ta as ta
import ccxt
import pandas as pd
from logger import logger

class StrategyVBD:
    def __init__(self, exchange=None, k_value=0.5):
        self.k_value = k_value
        # CCXT instantiated correctly in main or locally
        self.exchange = exchange if exchange else ccxt.coinone()

    def get_breakout_target(self, df):
        """
        Calculate Volatility Breakout target price based on previous day's data.
        df must contain a pandas dataframe from CCXT fetch_ohlcv with columns ['high', 'low', 'open'].
        target = today_open + (prev_high - prev_low) * K
        """
        if df is None or len(df) < 2:
            return None
            
        prev_candle = df.iloc[-2]
        today_candle = df.iloc[-1]
        
        prev_high = prev_candle['high']
        prev_low = prev_candle['low']
        today_open = today_candle['open']
        
        range_val = prev_high - prev_low
        target_price = today_open + (range_val * self.k_value)
        
        return target_price

    def get_rsi(self, symbol, timeframe='1h'):
        """Get current 1-hour RSI to pass to AI context via CCXT"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=20)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            if not df.empty:
               rsi = ta.rsi(df['close'], length=14)
               return rsi.iloc[-1]
               
            return 50.0 # fallback
        except Exception as e:
            logger.error(f"Error calculating RSI for {symbol}: {e}")
            return 50.0

    def get_top_volume_coins(self, limit=5):
        """Returns the top coins by 24h KRW volume on Coinone."""
        try:
            # Coinone tickers usually look like 'BTC/KRW'
            tickers = self.exchange.fetch_tickers()
            
            volume_list = []
            stablecoins = ["USDT/KRW", "USDC/KRW", "FDUSD/KRW"]
            
            for symbol, data in tickers.items():
                if '/KRW' in symbol and symbol not in stablecoins:
                    # 'quoteVolume' is usually the 24h volume in the quote currency (KRW)
                    vol = data.get('quoteVolume', 0)
                    if vol is not None:
                        volume_list.append((symbol, vol))
            
            # Sort descending by volume
            volume_list.sort(key=lambda x: x[1], reverse=True)
            
            top_coins = [x[0] for x in volume_list[:limit]]
            logger.info(f"Scanned top {limit} volume coins on Coinone: {top_coins}")
            return top_coins
            
        except Exception as e:
            logger.error(f"Error finding top volume coins on Coinone: {e}")
            return ["BTC/KRW"] # Fallback

