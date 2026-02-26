import pyupbit
import pandas_ta as ta
from logger import logger

class StrategyVBD:
    def __init__(self, k_value=0.5):
        self.k_value = k_value

    def get_breakout_target(self, df):
        """
        Calculate Volatility Breakout target price based on previous day's data.
        target = today_open + (prev_high - prev_low) * K
        """
        if df is None or len(df) < 2:
            return None
            
        # VBD is typically calculated using Daily candles
        # So df here must be an 'interval="day"' dataframe
        prev_candle = df.iloc[-2]
        today_candle = df.iloc[-1]
        
        prev_high = prev_candle['high']
        prev_low = prev_candle['low']
        today_open = today_candle['open']
        
        range_val = prev_high - prev_low
        target_price = today_open + (range_val * self.k_value)
        
        return target_price

    def get_rsi(self, symbol, interval="minute60"):
        """Get current RSI to pass to AI context"""
        try:
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=20)
            if df is not None and not df.empty:
               rsi = ta.rsi(df['close'], length=14)
               return rsi.iloc[-1]
            return 50.0 # fallback
        except:
            return 50.0

    def get_top_volume_coins(self, limit=5):
        """Returns the top coins by 24h KRW volume on Upbit."""
        try:
            tickers = pyupbit.get_tickers(fiat="KRW")
            # Filter stablecoins
            stablecoins = ["KRW-USDT", "KRW-USDC", "KRW-FDUSD"]
            tickers = [t for t in tickers if t not in stablecoins]
            
            # Get current data including acc_trade_price_24h
            current_data = pyupbit.get_current_price(tickers)
            
            # Since get_current_price returns a dict of ticker:price, we need a different approach
            # Using pyupbit to fetch tickers overview (which takes more work) 
            # OR simple logic: we pull market data
            import requests # Upbit REST API directly for faster bulk volume
            url = "https://api.upbit.com/v1/ticker"
            querystring = {"markets": ",".join(tickers)}
            response = requests.request("GET", url, params=querystring)
            data = response.json()
            
            # Sort by acc_trade_price_24h (24h trade volume)
            sorted_data = sorted(data, key=lambda x: x['acc_trade_price_24h'], reverse=True)
            
            top_coins = [x['market'] for x in sorted_data[:limit]]
            logger.info(f"Scanned top {limit} volume coins: {top_coins}")
            return top_coins
            
        except Exception as e:
            logger.error(f"Error finding top volume coins: {e}")
            return ["KRW-BTC"] # Fallback to BTC
