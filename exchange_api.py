import ccxt
import time
import pandas as pd
from config import config
from logger import logger

class ExchangeAPI:
    def __init__(self):
        """Initializes the ccxt Coinone object with credentials if available."""
        exchange_class = getattr(ccxt, 'coinone')
        self.exchange = exchange_class({
            'apiKey': config.access_key,
            'secret': config.secret_key,
            'enableRateLimit': True,
        })
        
        # Load markets
        try:
            self.exchange.load_markets()
            logger.info("Initialized Coinone API connection (CCXT).")
        except Exception as e:
            logger.error(f"Failed to connect to Coinone: {e}")

    def fetch_balance(self, ticker="KRW"):
        """Fetches the available balance for a specific ticker (e.g. 'KRW', 'BTC')."""
        if config.dry_run:
            # Fake balance for dry run
            return 100000.0 if ticker == "KRW" else 0.0
            
        try:
            balance = self.exchange.fetch_balance()
            if ticker in balance:
                return balance[ticker]['free']
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching balance for {ticker}: {e}")
            return 0.0

    def fetch_current_price(self, symbol):
        """Fetches the current ticker price. Symbol format: 'BTC/KRW'"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def fetch_ohlcv(self, symbol, timeframe='1d', limit=2):
        """
        Fetches OHLCV data. 
        CCXT uses timeframes like '1m', '1h', '1d'.
        Returns a Pandas DataFrame.
        """
        try:
            # ccxt fetch_ohlcv returns list of [timestamp, open, high, low, close, volume]
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return None

    def place_market_buy_order(self, symbol, cost_krw):
        """Places a market buy order using a specific KRW amount."""
        if config.dry_run:
            logger.info(f"[DRY RUN] Simulated Market Buy for {symbol} with {cost_krw} KRW")
            return {"uuid": f"dry-run-buy-{time.time()}"}

        try:
            # Note: Coinone might not support standard market buy by cost natively through CCXT in all cases
            # However, ccxt standardizes "createMarketBuyOrderWithCost" if the exchange supports it, 
            # OR we specify the 'cost' parameter to the standard create_market_buy_order.
            # But the most foolproof standard CCXT way if quote amount isn't supported is calculate amount:
            current_price = self.fetch_current_price(symbol)
            if not current_price: return None
            
            amount = cost_krw / current_price
            
            # Place order
            order = self.exchange.create_market_buy_order(symbol, amount)
            logger.info(f"Market BUY Order placed for {symbol}: {order}")
            return order
        except Exception as e:
            logger.error(f"Error placing buy order for {symbol}: {e}")
            return None

    def place_market_sell_order(self, symbol, amount):
        """Places a market sell order for a specific amount of coins."""
        if config.dry_run:
            logger.info(f"[DRY RUN] Simulated Market Sell for {symbol} of amount {amount}")
            return {"uuid": f"dry-run-sell-{time.time()}"}

        try:
            order = self.exchange.create_market_sell_order(symbol, amount)
            logger.info(f"Market SELL Order placed for {symbol}: {order}")
            return order
        except Exception as e:
            logger.error(f"Error placing sell order for {symbol}: {e}")
            return None
