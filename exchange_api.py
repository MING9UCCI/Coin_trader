import pyupbit
import pandas as pd
from config import config
from logger import logger

class ExchangeAPI:
    def __init__(self):
        self.upbit = None
        if config.access_key and config.secret_key:
            self.upbit = pyupbit.Upbit(config.access_key, config.secret_key)
            logger.info("Initialized Upbit API connection.")
        else:
            logger.warning("Upbit keys not found. Operating in public-only mode or Dry-Run without actual balance tracking.")

    def fetch_ohlcv(self, symbol, timeframe='minute60', limit=100):
        """Fetches historical candlestick data from Upbit."""
        try:
            logger.info(f"Fetching OHLCV data for {symbol} ({timeframe})")
            # pyupbit returns a pandas DataFrame directly
            df = pyupbit.get_ohlcv(symbol, interval=timeframe, count=limit)
            return df
        except Exception as e:
            logger.error(f"Error fetching OHLCV data: {e}")
            return None

    def fetch_current_price(self, symbol):
        """Fetch real-time current price."""
        return pyupbit.get_current_price(symbol)

    def fetch_balance(self, ticker='KRW'):
        """Fetches the available balance for a specific asset (e.g., 'KRW' or 'KRW-BTC')."""
        if not self.upbit:
            return 0.0
            
        try:
            balance = self.upbit.get_balance(ticker)
            logger.info(f"Available balance for {ticker}: {balance}")
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0.0

    def place_market_buy_order(self, symbol, krw_amount):
        """Places a market buy order for a specific KRW amount on Upbit."""
        if config.dry_run:
            logger.info(f"[DRY RUN] Would place MARKET BUY order for {krw_amount} KRW of {symbol}")
            return {'status': 'simulated_buy'}
            
        if not self.upbit:
            logger.error("API keys missing, cannot place real order.")
            return None
            
        try:
            logger.info(f"Placing MARKET BUY order for {krw_amount} KRW of {symbol}")
            order = self.upbit.buy_market_order(symbol, krw_amount)
            logger.info(f"BUY Order placed successfully: {order}")
            return order
        except Exception as e:
            logger.error(f"Error placing buy order: {e}")
            return None

    def place_market_sell_order(self, symbol, coin_volume):
        """Places a market sell order for a certain volume of coin on Upbit."""
        if config.dry_run:
            logger.info(f"[DRY RUN] Would place MARKET SELL order for {coin_volume} of {symbol}")
            return {'status': 'simulated_sell'}
            
        if not self.upbit:
            logger.error("API keys missing, cannot place real order.")
            return None
            
        try:
            logger.info(f"Placing MARKET SELL order for {coin_volume} of {symbol}")
            order = self.upbit.sell_market_order(symbol, coin_volume)
            logger.info(f"SELL Order placed successfully: {order}")
            return order
        except Exception as e:
            logger.error(f"Error placing sell order: {e}")
            return None
