import ccxt
import pandas as pd
from config import config
from logger import logger

class ExchangeAPI:
    def __init__(self):
        self.exchange_id = config.exchange_id
        
        try:
            exchange_class = getattr(ccxt, self.exchange_id)
            self.exchange = exchange_class({
                'apiKey': config.api_key,
                'secret': config.secret_key,
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}  # Use spot trading by default
            })
            logger.info(f"Initialized {self.exchange_id} exchange connection.")
        except AttributeError:
            logger.error(f"Exchange {self.exchange_id} is not supported by CCXT.")
            raise

    def fetch_ohlcv(self, symbol, timeframe='1h', limit=100):
        """Fetches historical candlestick data and converts it to a pandas DataFrame."""
        try:
            logger.info(f"Fetching OHLCV data for {symbol} ({timeframe})")
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error fetching OHLCV data: {e}")
            return None

    def fetch_balance(self, asset='USDT'):
        """Fetches the available balance for a specific asset."""
        try:
            balance = self.exchange.fetch_balance()
            free_balance = balance.get(asset, {}).get('free', 0.0)
            logger.info(f"Available balance for {asset}: {free_balance}")
            return free_balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0.0

    def place_market_buy_order(self, symbol, amount):
        """Places a market buy order."""
        if config.dry_run:
            logger.info(f"[DRY RUN] Would place MARKET BUY order for {amount} of {symbol}")
            return {'status': 'simulated_buy'}
        try:
            logger.info(f"Placing MARKET BUY order for {amount} of {symbol}")
            order = self.exchange.create_market_buy_order(symbol, amount)
            logger.info(f"BUY Order placed successfully: {order}")
            return order
        except Exception as e:
            logger.error(f"Error placing buy order: {e}")
            return None

    def place_market_sell_order(self, symbol, amount):
        """Places a market sell order."""
        if config.dry_run:
            logger.info(f"[DRY RUN] Would place MARKET SELL order for {amount} of {symbol}")
            return {'status': 'simulated_sell'}
        try:
            logger.info(f"Placing MARKET SELL order for {amount} of {symbol}")
            order = self.exchange.create_market_sell_order(symbol, amount)
            logger.info(f"SELL Order placed successfully: {order}")
            return order
        except Exception as e:
            logger.error(f"Error placing sell order: {e}")
            return None
