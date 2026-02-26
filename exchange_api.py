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
        Coinone CCXT fetch_ohlcv() is not supported yet, so we use their native Public REST API.
        Returns a Pandas DataFrame.
        """
        try:
            # symbol format: 'BTC/KRW'
            if '/' not in symbol:
                return None
            base, quote = symbol.split('/')
            
            # Map ccxt timeframe to Coinone interval string
            # Coinone supports: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1M
            interval_map = {'day': '1d', '1d': '1d', '1h': '1h', 'minute60': '1h', '15m': '15m'}
            interval = interval_map.get(timeframe, '1d')
            
            import requests
            url = f"https://api.coinone.co.kr/public/v2/chart/{quote}/{base}?interval={interval}"
            response = requests.get(url)
            data = response.json()
            
            if data.get('result') != 'success':
                logger.error(f"Coinone API Error fetching OHLCV: {data.get('error_msg')}")
                return None
                
            chart_data = data['chart'][-limit:]
            
            df = pd.DataFrame(chart_data)
            # Coinone returns string numbers, so we convert them
            for col in ['open', 'high', 'low', 'close', 'target_volume']:
                df[col] = df[col].astype(float)
                
            df.rename(columns={'target_volume': 'volume'}, inplace=True)
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
            # Coinone CCXT only supports Limit Orders, so we mimic a market order 
            # by placing a limit order at the exact current price.
            current_price = self.fetch_current_price(symbol)
            if not current_price: return None
            
            amount = cost_krw / current_price
            
            # Place order
            order = self.exchange.create_limit_buy_order(symbol, amount, current_price)
            logger.info(f"Market(Limit) BUY Order placed for {symbol}: {order}")
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
            # Mimic market sell via limit order at current price
            current_price = self.fetch_current_price(symbol)
            if not current_price: return None
            
            order = self.exchange.create_limit_sell_order(symbol, amount, current_price)
            logger.info(f"Market(Limit) SELL Order placed for {symbol}: {order}")
            return order
        except Exception as e:
            logger.error(f"Error placing sell order for {symbol}: {e}")
            return None
