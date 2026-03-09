import ccxt
import pyupbit
import math
import time
import pandas as pd
from config import config
from logger import logger

class CoinoneAPI:
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
        remaining_krw = krw_budget or 0
        remaining_coin = coin_budget or 0
        start_krw = remaining_krw
        start_coin = remaining_coin
        
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
                
            # Use CCXT's native precision formatter to safely truncate the exact decimal places allowed by Coinone.
            # This dramatically prevents 'dust' (0.0000001 coins) from being left behind in the wallet.
            try:
                qty_formatted_str = self.exchange.amount_to_precision(symbol, amount)
                qty_formatted = float(qty_formatted_str)
            except Exception:
                # Failsafe if CCXT fails to load market precision
                qty_formatted = math.floor(amount * 10000) / 10000
                
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
                
        # 최대 재시도(max_retries)가 끝났거나, 잔여 물량이 너무 작아 루프를 탈출한 경우
        # 조금이라도 체결된 이력이 있다면 '실패(None)'가 아닌 '부분 체결(Partial Success)'로 보고하여 
        # 메인루프에서 포지션을 추적/청산할 수 있게 유도함.
        if side == 'BUY' and remaining_krw < start_krw:
            logger.warning(f"[{symbol}] BUY order max retries reached but partially filled. Tracking it.")
            return {"result": "partial_success"}
        if side == 'SELL' and remaining_coin < start_coin:
            logger.warning(f"[{symbol}] SELL order max retries reached but partially filled. Clearing it.")
            return {"result": "partial_success"}
            
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

        # Fetch actual real-time balance to prevent Error 103 (Lack of Balance) due to fee deduction
        base_ticker = symbol.split('/')[0]
        actual_balance = self.fetch_balance(base_ticker)
        
        safe_amount = min(amount, actual_balance)
        current_price = self.fetch_current_price(symbol)
        
        # 먼지(Dust) 방지 필터: 보유 잔고의 가치가 4,500원 미만이면 코인원 최소 주문금액(5,000원) 미달로 무조건 에러남.
        # 이 경우 '알아서 다 팔렸거나, 팔 수 없는 먼지'로 간주하고 무한 루프에 빠지지 않도록 처리함.
        if current_price and (safe_amount * current_price) < 4500:
             logger.warning(f"[{symbol}] Balance ({safe_amount} 개, 약 {safe_amount * current_price:.0f} 원) is practically dust or below minimum order size. Clearing from memory.")
             return {"result": "dust_cleared", "filled_price": current_price}

        return self._wait_and_fill_limit_order(symbol, 'SELL', coin_budget=safe_amount)

class UpbitAPI:
    def __init__(self):
        self.upbit = pyupbit.Upbit(config.upbit_access_key, config.upbit_secret_key)
        logger.info("Initialized Upbit API connection (pyupbit).")

    def format_symbol(self, symbol):
        """Converts CCXT BTC/KRW or KRW-BTC into pyupbit format KRW-BTC"""
        if '/' in symbol:
            base, quote = symbol.split('/')
            return f"{quote}-{base}"
        return symbol

    def fetch_balance(self, ticker="KRW"):
        if config.dry_run:
            return 100000.0 if ticker == "KRW" else 0.0
        try:
            # get_balances returns a list of dictionaries like {'currency': 'KRW', 'balance': '100000.0', ...}
            raw_balances = self.upbit.get_balances()
            if raw_balances:
                for b in raw_balances:
                    if b['currency'] == ticker:
                        return float(b['balance'])
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching balance for {ticker}: {e}")
            return 0.0

    def fetch_current_price(self, symbol):
        try:
            formatted_sym = self.format_symbol(symbol)
            return pyupbit.get_current_price(formatted_sym)
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def fetch_ohlcv(self, symbol, timeframe='1d', limit=2):
        try:
            formatted_sym = self.format_symbol(symbol)
            interval_map = {'day': 'day', '1d': 'day', '1h': 'minute60', '15m': 'minute15', '4h': 'minute240'}
            interval = interval_map.get(timeframe, 'day')
            df = pyupbit.get_ohlcv(formatted_sym, interval=interval, count=limit)
            if df is not None and not df.empty:
                df.reset_index(inplace=True)
                df.rename(columns={'index': 'timestamp'}, inplace=True)
                return df
            return None
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return None

    def place_market_buy_order(self, symbol, cost_krw):
        if config.dry_run:
            logger.info(f"[DRY RUN] Simulated Upbit Market Buy for {symbol} with {cost_krw} KRW")
            return {"uuid": f"dry-run-buy-{time.time()}"}
            
        try:
            # 강제로 5천원 미만이면 거부
            if cost_krw < 5000:
                logger.warning(f"[{symbol}] Buy order cost ({cost_krw}) under Upbit minimum 5000 KRW.")
                return None
                
            formatted_sym = self.format_symbol(symbol)
            # 업비트는 buy_market_order 지원
            res = self.upbit.buy_market_order(formatted_sym, cost_krw)
            if res and 'uuid' in res:
                logger.info(f"[{symbol}] Upbit Market BUY Placed. (ID: {res['uuid']})")
                return {"result": "success", "orderId": res['uuid'], "filled_price": self.fetch_current_price(symbol)}
            elif 'error' in res:
                logger.error(f"[{symbol}] Upbit Market BUY Error: {res}")
                return None
            else:
                logger.error(f"[{symbol}] Upbit Market BUY Failed: {res}")
                return None
        except Exception as e:
            logger.error(f"[{symbol}] Upbit BUY Exception: {e}")
            return None

    def place_market_sell_order(self, symbol, amount):
        if config.dry_run:
            logger.info(f"[DRY RUN] Simulated Upbit Market Sell for {symbol} of amount {amount}")
            return {"uuid": f"dry-run-sell-{time.time()}"}
            
        try:
            base_ticker = symbol.split('/')[0] if '/' in symbol else symbol.split('-')[1]
            actual_balance = self.fetch_balance(base_ticker)
            safe_amount = min(amount, actual_balance)
            current_price = self.fetch_current_price(symbol)
            
            # 5천원 미만 잔고면 먼지로 판별하고 청산. 업비트는 시장가 매도 최소 5000원 룰이 있음.
            if current_price and (safe_amount * current_price) < 4800:
                logger.warning(f"[{symbol}] Balance ({safe_amount} 개) is below Upbit minimum sell size. Clearing dust from memory.")
                return {"result": "dust_cleared", "filled_price": current_price}
                
            formatted_sym = self.format_symbol(symbol)
            res = self.upbit.sell_market_order(formatted_sym, safe_amount)
            if res and 'uuid' in res:
                logger.info(f"[{symbol}] Upbit Market SELL Placed. (ID: {res['uuid']})")
                return {"result": "success", "orderId": res['uuid'], "filled_price": current_price}
            else:
                logger.error(f"[{symbol}] Upbit Market SELL Failed: {res}")
                return None
        except Exception as e:
            logger.error(f"[{symbol}] Upbit SELL Exception: {e}")
            return None


def get_exchange_api():
    if config.active_exchange == "UPBIT":
        return UpbitAPI()
    else:
        return CoinoneAPI()
