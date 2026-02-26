import time
import schedule
import pyupbit
from rich.console import Console
from rich.panel import Panel
from config import config
from logger import logger
from exchange_api import ExchangeAPI
from ai_advisor import AIAdvisor
from strategy_vbd import StrategyVBD

console = Console()

# Dictionary to hold the state of positions
# positions = { 'KRW-BTC': {'buy_price': 50000, 'highest_price': 55000, 'amount': 0.01} }
positions = {}

def get_current_real_balance(exchange_api, ticker="KRW"):
    return exchange_api.fetch_balance(ticker)

def sync_positions(exchange_api, strategy):
    logger.info("Syncing existing portfolio balances into bot memory...")
    try:
        # ccxt fetch_balance returns all balances mapped
        balances = exchange_api.exchange.fetch_balance()
        top_coins = strategy.get_top_volume_coins(limit=config.coin_count)
        
        for symbol in top_coins:
            base_ticker = symbol.split('/')[0]
            # Safely get the free amount for the ticker
            free_amount = float(balances.get('free', {}).get(base_ticker, 0.0))
            if free_amount <= 0:
                # Fallback to total if free isn't specified but total is
                free_amount = float(balances.get('total', {}).get(base_ticker, 0.0))
                
            if free_amount > 0:
                current_price = exchange_api.fetch_current_price(symbol)
                if current_price and (free_amount * current_price) > 5000:
                    positions[symbol] = {
                        'buy_price': current_price,
                        'highest_price': current_price,
                        'amount': free_amount
                    }
                    logger.info(f"Synced existing position: [{symbol}] (Amount: {free_amount:.4f}, Checkpoint Price: {current_price:,})")

    except Exception as e:
        logger.error(f"Failed to sync positions: {e}")

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
                    # Coinone symbols are "COIN/KRW", so split by '/'
                    coin_ticker = symbol.split('/')[0]
                    amount_to_sell = exchange_api.fetch_balance(coin_ticker) if not config.dry_run else pos.get('amount', 0)
                    exchange_api.place_market_sell_order(symbol, amount_to_sell)
                    
                    # Remove from tracked positions
                    del positions[symbol]
                
                continue # Skip buying logic since we already hold it

            # b) Breakout Check (If NOT holding symbol)
            # Find the breakout target price
            # Get 15m OHLCV from the previous 15-minute candle
            df_15m = exchange_api.fetch_ohlcv(symbol, timeframe='15m', limit=2)
            if df_15m is None or len(df_15m) < 2:
                continue

            target_price = strategy.get_breakout_target(df_15m)
            
            if target_price and current_price >= target_price:
                # 1단계: 돈이 충분한지 (최소 5,500원) 미리 검사해서 AI 호출 낭비 방지
                krw_avail = get_current_real_balance(exchange_api, "KRW")
                if krw_avail is None: krw_avail = 0
                
                remaining_slots = config.coin_count - len(positions)
                if remaining_slots <= 0:
                    logger.info(f"[{symbol}] Maximum coin count reached. Can't buy more.")
                    continue
                    
                allocate_amount = krw_avail / remaining_slots
                
                # 강제로 최소 주문 금액(5,500원) 이상으로 보정 (수수료 포함 안전빵)
                if allocate_amount < 5500:
                    if krw_avail >= 5500:
                        allocate_amount = krw_avail  # 남은 돈 몰빵
                        logger.info(f"[{symbol}] Budget per slot too low. Adjusting allocation to available KRW: {allocate_amount:,.0f}")
                    else:
                        logger.info(f"[{symbol}] Skipped: Total KRW ({krw_avail:,.0f}) is under absolute minimum 5,500 KRW. Cannot proceed.")
                        continue
                
                logger.info(f"[{symbol}] Breakout Detected! Price {current_price:,} >= Target {target_price:,}")
                
                # 2단계: 돈이 확인되었으므로 AI 필터링 시작
                rsi = strategy.get_rsi(symbol)
                rank_index = top_coins.index(symbol) + 1
                
                approved, context = ai_advisor.analyze_breakout(symbol, current_price, target_price, config.vbd_k, rank_index, rsi)
                
                if approved:
                    logger.info(f"[{symbol}] AI Appoved: {context[-50:]}")
                    
                    logger.info(f"[{symbol}] Attemping to BUY with Dynamic Allocation: {allocate_amount:,.0f} KRW")
                    order = exchange_api.place_market_buy_order(symbol, allocate_amount)
                    
                    if order:
                        bought_amount = (allocate_amount * 0.9995) / current_price if config.dry_run else allocate_amount / current_price 
                        
                        positions[symbol] = {
                            'buy_price': current_price,
                            'highest_price': current_price,
                            'amount': bought_amount
                        }
                        logger.info(f"[{symbol}] Position Opened successfully.")
                else:
                    logger.info(f"[{symbol}] AI VETOED Trade: {context[-50:]}")

        except Exception as e:
            logger.error(f"Error processing symbol {symbol}: {e}")

    logger.info("--- Scan Cycle Complete ---")

def main():
    welcome_msg = f"[bold cyan]AI Fusion Trading Bot V2.1 (Dynamic)[/bold cyan]\n" \
                  f"Target: [yellow]Top {config.coin_count} Volume Coins[/yellow]\n" \
                  f"Dynamic Allocation: [green]Active[/green]\n" \
                  f"Dry Run Mode: [red]{config.dry_run}[/red]"
    
    console.print(Panel(welcome_msg, title="[bold magenta]Initialization[/bold magenta]", expand=False))
    
    logger.info("Starting up engine and connecting to APIs...")
    
    try:
        exchange_api = ExchangeAPI()
        ai_advisor = AIAdvisor()
        strategy = StrategyVBD(k_value=config.vbd_k)
        config.validate()
        
        # 실제 계좌 원화 잔고 출력
        krw_real = get_current_real_balance(exchange_api, "KRW")
        logger.info(f"💰 Current Coinone KRW Balance: {krw_real:,.0f} 원")

        sync_positions(exchange_api, strategy)

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
