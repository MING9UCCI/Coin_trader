import time
import schedule
from config import config
from logger import logger
from exchange_api import ExchangeAPI
from strategy import Strategy

# State variable to track if we currently hold a position
# In a real scenario, you should check your actual balance or open orders
in_position = False

def trading_job(exchange_api):
    global in_position
    symbol = config.symbol
    amount = config.trade_amount
    
    logger.info("--- Starting trading job cycle ---")
    
    # 1. Fetch Market Data
    # Fetching 1h candles as an example. You can use '5m', '15m', etc.
    df = exchange_api.fetch_ohlcv(symbol, timeframe='1h', limit=50)
    
    if df is not None:
        # 2. Analyze Strategy
        strategy = Strategy(df)
        signal = strategy.analyze()
        
        # 3. Execute Trades
        if signal == 'BUY' and not in_position:
            order = exchange_api.place_market_buy_order(symbol, amount)
            if order:
                in_position = True
                
        elif signal == 'SELL' and in_position:
            order = exchange_api.place_market_sell_order(symbol, amount)
            if order:
                in_position = False
    
    logger.info("--- Trading job cycle complete ---")

def main():
    logger.info(f"Starting Trading Bot (Dry Run: {config.dry_run})")
    
    try:
        # Initialize Exchange API
        exchange_api = ExchangeAPI()
        
        # Validate configuration
        config.validate()
        
        # Log initial balances
        base_asset, quote_asset = config.symbol.split('/')
        exchange_api.fetch_balance(quote_asset)
        exchange_api.fetch_balance(base_asset)

        # Run immediately once
        trading_job(exchange_api)

        # Schedule the job to run every 1 hour
        # (Change to .minutes for shorter timeframes like 5m candles)
        schedule.every().hour.at(":01").do(trading_job, exchange_api=exchange_api)
        
        logger.info("Entering main scheduling loop. Press Ctrl+C to abort.")
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")

if __name__ == "__main__":
    main()
