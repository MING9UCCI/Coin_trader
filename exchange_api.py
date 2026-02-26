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

    def _wait_and_fill_limit_order(self, symbol: str, side: str, krw_budget=None, coin_budget=None, max_retries=5):
        """
        Auto-chasing limit order to spoof a market fill.
        Since Coinone prohibits true market orders, limit orders placed at `current_price`
        can easily hang if the market price spikes instantly.
        This loops up to `max_retries`, waiting 5 seconds. If unfilled, it cancels and tries again
        at the new price.
        """
        base, quote = symbol.split('/')
        remaining_krw = krw_budget
        remaining_coin = coin_budget
        
        for attempt in range(max_retries):
            current_price = self.fetch_current_price(symbol)
            if not current_price: continue

            # Determine order dimensions
            if side == 'BUY':
                if remaining_krw <= 0: break
                amount = remaining_krw / current_price
            else:
                if remaining_coin <= 0: break
                amount = remaining_coin
                
            qty_formatted = float(f"{amount:.4f}")
            if qty_formatted <= 0: break

            request_params = {
                'currency': base,
                'price': float(current_price),
                'qty': qty_formatted
            }
            
            try:
                # Place the spoofed market (limit) order
                if side == 'BUY':
                    res = self.exchange.v2PrivatePostOrderLimitBuy(request_params)
                else:
                    res = self.exchange.v2PrivatePostOrderLimitSell(request_params)
                
                if res.get('errorCode') != '0':
                    logger.error(f"[{symbol}] API Error placing order on attempt {attempt+1}: {res}")
                    return None
                    
                order_id = res.get('orderId')
                logger.info(f"[{symbol}] Attempt {attempt+1}/{max_retries} - Placed Limited {side} at {current_price:,} (ID: {order_id})")
                
                # Wait for execution
                time.sleep(5)
                
                # Check execution status
                query_params = {
                    'currency': base,
                    'order_id': order_id
                }
                status_res = self.exchange.v2PrivatePostOrderQueryOrder(query_params)
                
                if status_res.get('errorCode') == '0':
                    order_info = status_res.get('info', {})
                    # If status is "live", it hasn't completely filled.
                    if order_info.get('status') == 'live':
                        logger.warning(f"[{symbol}] Order {order_id} hanging due to slippage. Canceling and retrying...")
                        # Partially filled amount (we subtract this from our remaining budget)
                        filled_qty = float(order_info.get('qty', 0)) - float(order_info.get('remainQty', 0))
                        if side == 'BUY':
                            remaining_krw -= (filled_qty * float(current_price))
                        else:
                            remaining_coin -= filled_qty
                            
                        # Cancel the hanging remainder
                        self.exchange.v2PrivatePostOrderCancel({
                            'currency': base,
                            'order_id': order_id,
                            'price': float(current_price),
                            'qty': float(order_info.get('remainQty')),
                            'is_ask': 1 if side == 'SELL' else 0
                        })
                        time.sleep(1) # Wait for cancel to process
                    else:
                        # Fully filled ("completed" or other)
                        return {"result": "success", "orderId": order_id, "filled_price": current_price}
                
            except Exception as e:
                logger.error(f"[{symbol}] Exception in order chase loop: {e}")
                
        logger.error(f"[{symbol}] Failed to fully fill {side} order after {max_retries} attempts.")
        return None

    def place_market_buy_order(self, symbol, cost_krw):
        """Places a market buy order using a specific KRW amount by mimicking it with an auto-chasing limit order."""
        if config.dry_run:
            logger.info(f"[DRY RUN] Simulated Market Buy for {symbol} with {cost_krw} KRW")
            return {"uuid": f"dry-run-buy-{time.time()}"}

        return self._wait_and_fill_limit_order(symbol, 'BUY', krw_budget=cost_krw)

    def place_market_sell_order(self, symbol, amount):
        """Places a market sell order for a specific amount of coins by mimicking it with an auto-chasing limit order."""
        if config.dry_run:
            logger.info(f"[DRY RUN] Simulated Market Sell for {symbol} of amount {amount}")
            return {"uuid": f"dry-run-sell-{time.time()}"}

        return self._wait_and_fill_limit_order(symbol, 'SELL', coin_budget=amount)
