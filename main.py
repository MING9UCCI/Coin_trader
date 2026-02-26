import time
import schedule
import pyupbit
from config import config
from logger import logger
from exchange_api import ExchangeAPI
from ai_advisor import AIAdvisor
from strategy_vbd import StrategyVBD

# Dictionary to hold the state of positions
# positions = { 'KRW-BTC': {'buy_price': 50000, 'highest_price': 55000, 'amount': 0.01} }
positions = {}

def get_current_real_balance(exchange_api, ticker="KRW"):
    if config.dry_run:
        return config.total_budget
    return exchange_api.fetch_balance(ticker)

def scan_and_trade(exchange_api, ai_advisor, strategy):
    logger.info("--- Starting VBD + AI Scan Cycle ---")
    
    # 1. Update Top Volume Coins
    top_coins = strategy.get_top_volume_coins(limit=config.coin_count)
    
    # Check current prices for Trailing Stop logic and VBD breakout
    for symbol in top_coins:
        try:
            current_price = exchange_api.fetch_current_price(symbol)
            if not current_price:
                continue

            # a) Trailing Stop Check (If holding symbol)
            if symbol in positions:
                pos = positions[symbol]
                buy_price = pos['buy_price']
                highest_price = max(pos['highest_price'], current_price)
                positions[symbol]['highest_price'] = highest_price
                
                # Trailing stop condition: Drop by trailing_stop_pct (e.g. 3%) from peak
                drop_threshold = highest_price * (1.0 - config.trailing_stop_pct)
                
                if current_price <= drop_threshold:
                    profit_pct = ((current_price - buy_price) / buy_price) * 100
                    logger.info(f"[{symbol}] Trailing Stop Triggered! Selling at {current_price:,} KRW (Buy: {buy_price:,}). PNL: {profit_pct:.2f}%")
                    
                    # Execute Sell
                    coin_ticker = symbol.split('-')[1]
                    amount_to_sell = exchange_api.fetch_balance(coin_ticker) if not config.dry_run else pos.get('amount', 0)
                    exchange_api.place_market_sell_order(symbol, amount_to_sell)
                    
                    # Remove from tracked positions
                    del positions[symbol]
                
                continue # Skip buying logic since we already hold it

            # b) Breakout Check (If NOT holding symbol)
            # Find the breakout target price
            # Get daily OHLCV from yesterday
            df_day = exchange_api.fetch_ohlcv(symbol, timeframe='day', limit=2)
            if df_day is None or len(df_day) < 2:
                continue

            target_price = strategy.get_breakout_target(df_day)
            
            if target_price and current_price >= target_price:
                logger.info(f"[{symbol}] Breakout Detected! Price {current_price:,} >= Target {target_price:,}")
                
                # Filter via AI
                rsi = strategy.get_rsi(symbol)
                rank_index = top_coins.index(symbol) + 1
                
                approved, context = ai_advisor.analyze_breakout(symbol, current_price, target_price, config.vbd_k, rank_index, rsi)
                
                if approved:
                    logger.info(f"[{symbol}] AI Appoved: {context[-50:]}")
                    
                    # Check Balance and Execute
                    krw_avail = get_current_real_balance(exchange_api, "KRW")
                    allocate_amount = config.trade_amount
                    
                    if krw_avail >= allocate_amount and len(positions) < config.coin_count:
                        order = exchange_api.place_market_buy_order(symbol, allocate_amount)
                        
                        # Simulate amount bought for dry run tracking
                        bought_amount = (allocate_amount * 0.9995) / current_price if config.dry_run else allocate_amount / current_price 
                        
                        positions[symbol] = {
                            'buy_price': current_price,
                            'highest_price': current_price,
                            'amount': bought_amount
                        }
                        logger.info(f"[{symbol}] Position Opened.")
                else:
                    logger.info(f"[{symbol}] AI VETOED Trade: {context[-50:]}")

        except Exception as e:
            logger.error(f"Error processing symbol {symbol}: {e}")

    logger.info("--- Scan Cycle Complete ---")

def main():
    logger.info(f"Starting AI Fusion Trading Bot (Dry Run: {config.dry_run})")
    
    try:
        exchange_api = ExchangeAPI()
        ai_advisor = AIAdvisor()
        strategy = StrategyVBD(k_value=config.vbd_k)
        config.validate()

        scan_and_trade(exchange_api, ai_advisor, strategy)
        
        # In a highly volatile breakout + trailing stop, we should check frequently.
        # Check every 1 minute.
        schedule.every(1).minutes.do(scan_and_trade, exchange_api, ai_advisor, strategy)
        
        logger.info("Entering multi-coin tracking loop (every 1m). Press Ctrl+C to abort.")
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Bot manually stopped.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
