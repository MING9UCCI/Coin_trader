import pandas_ta as ta
import ccxt
import pyupbit
import pandas as pd
from logger import logger
from config import config

class StrategyVBD:
    def __init__(self, exchange=None, k_value=0.5):
        self.k_value = k_value
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
        """Get current 1-hour RSI to pass to AI context"""
        try:
            if config.active_exchange == "UPBIT":
                # Convert format if needed
                fmt_sym = symbol if '-' in symbol else f"KRW-{symbol.split('/')[0]}"
                df = pyupbit.get_ohlcv(fmt_sym, interval="minute60", count=20)
                if df is not None and not df.empty and len(df) >= 14:
                    rsi = ta.rsi(df['close'], length=14)
                    return rsi.iloc[-1]
                return 50.0
            else:
                if '/' not in symbol: return 50.0
                base, quote = symbol.split('/')
                
                import requests
                url = f"https://api.coinone.co.kr/public/v2/chart/{quote}/{base}?interval={timeframe}"
                response = requests.get(url)
                data = response.json()
                
                if data.get('result') == 'success':
                    chart_data = data['chart'][-20:]
                    df = pd.DataFrame(chart_data)
                    df['close'] = df['close'].astype(float)
                    
                    if not df.empty and len(df) >= 14:
                        rsi = ta.rsi(df['close'], length=14)
                        return rsi.iloc[-1]
                return 50.0 # fallback

        except Exception as e:
            logger.error(f"Error calculating RSI for {symbol}: {e}")
            return 50.0

    def get_top_volume_coins(self, limit=5):
        """Returns the top coins by 24h KRW volume."""
        try:
            import requests
            volume_list = []
            
            if config.active_exchange == "UPBIT":
                tickers = pyupbit.get_tickers(fiat="KRW")
                stablecoins = ["KRW-USDT", "KRW-USDC"]
                
                # Upbit allows max 100 tickers per request, partition it just in case
                valid_tickers = [t for t in tickers if t not in stablecoins and t not in config.blacklist]
                
                url = "https://api.upbit.com/v1/ticker"
                headers = {"accept": "application/json"}
                
                # Fetching in chunks to avoid URL length limits
                chunk_size = 50
                for i in range(0, len(valid_tickers), chunk_size):
                    chunk = valid_tickers[i:i + chunk_size]
                    querystring = {"markets": ",".join(chunk)}
                    res = requests.get(url, headers=headers, params=querystring)
                    data = res.json()
                    
                    if isinstance(data, list):
                        for item in data:
                            sym = item['market']
                            vol = item.get('acc_trade_price_24h', 0)
                            volume_list.append((sym, vol))
            else:
                # Coinone tickers usually look like 'BTC/KRW'
                tickers = self.exchange.fetch_tickers()
                stablecoins = ["USDT/KRW", "USDC/KRW", "FDUSD/KRW"]
                
                for symbol, data in tickers.items():
                    if '/KRW' in symbol and symbol not in stablecoins and symbol not in config.blacklist:
                        vol = data.get('quoteVolume', 0)
                        if vol is not None:
                            volume_list.append((symbol, vol))
            
            # Sort descending by volume
            volume_list.sort(key=lambda x: x[1], reverse=True)
            
            top_coins = [x[0] for x in volume_list[:limit]]
            logger.info(f"Scanned top {limit} volume coins on {config.active_exchange}: {top_coins}")
            return top_coins
            
        except Exception as e:
            logger.error(f"Error finding top volume coins on {config.active_exchange}: {e}")
            return ["KRW-BTC"] if config.active_exchange == "UPBIT" else ["BTC/KRW"]

