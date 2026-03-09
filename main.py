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
from database import record_trade
from auto_optimizer import run_optimizer
from market_filter import MarketFilter

console = Console()

# Dictionary to hold the state of positions
# positions = { 'KRW-BTC': {'buy_price': 50000, 'highest_price': 55000, 'amount': 0.01} }
positions = {}
cooldowns = {} # Tracks sell timestamps to prevent immediate re-entry

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
                        'amount': free_amount,
                        'buy_time': time.time() # 1. 시간 초과 체크를 위해 현재 시간 등록
                    }
                    logger.info(f"Synced existing position: [{symbol}] (Amount: {free_amount:.4f}, Checkpoint Price: {current_price:,})")

    except Exception as e:
        logger.error(f"Failed to sync positions: {e}")

def scan_and_trade(exchange_api, ai_advisor, strategy, market_filter):
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
                
                # [Tier 2 Macro Filter]: If Panic mode, sell immediately
                if market_filter.news_panic_flag:
                    logger.critical(f"🚨 [{symbol}] PANIC SELL TRIGGERED BY GLOBAL NEWS! Liquidating position.")
                    drop_threshold = current_price + 99999999 # Force trigger sell
                
                # NEW: Hard Stop Loss at -3% from entry to prevent sliding failures
                hard_stop = buy_price * 0.97
                
                if current_price <= drop_threshold or current_price <= hard_stop:
                    profit_pct = ((current_price - buy_price) / buy_price) * 100
                    logger.info(f"[{symbol}] STOP Triggered! Selling at {current_price:,} KRW (Buy: {buy_price:,}). PNL: {profit_pct:.2f}%")
                    
                    # Execute Sell
                    coin_ticker = symbol.split('/')[0]
                    amount_to_sell = exchange_api.fetch_balance(coin_ticker) if not config.dry_run else pos.get('amount', 0)
                    order_result = exchange_api.place_market_sell_order(symbol, amount_to_sell)
                    
                    # 1. 찌꺼기 방지: 매도 주문이 '성공적으로' 체결되었을 때만 메모리에서 삭제
                    if order_result:
                        record_trade(symbol, buy_price, current_price, amount_to_sell)
                        del positions[symbol]
                        cooldowns[symbol] = time.time()
                        logger.info(f"[{symbol}] Position cleared & Added to 3-hour cooldown.")
                    else:
                        logger.warning(f"[{symbol}] Sell order failed or partially filled. Keeping in memory to retry on next tick.")
                
                # 3. 좀비 포지션 정리 (Time-Stop): 12시간 보유하고도 트레일링 스탑을 못 쳤다면 청산 (기회비용 확보)
                elif (time.time() - pos.get('buy_time', time.time())) > 43200: # 12 hours = 43200 sec
                    profit_pct = ((current_price - buy_price) / buy_price) * 100
                    logger.info(f"[{symbol}] ⏰ TIME-STOP Triggered! Held over 12 hours. Selling at {current_price:,} KRW. PNL: {profit_pct:.2f}%")
                    
                    coin_ticker = symbol.split('/')[0]
                    amount_to_sell = exchange_api.fetch_balance(coin_ticker) if not config.dry_run else pos.get('amount', 0)
                    order_result = exchange_api.place_market_sell_order(symbol, amount_to_sell)
                    
                    if order_result:
                        record_trade(symbol, buy_price, current_price, amount_to_sell)
                        del positions[symbol]
                        cooldowns[symbol] = time.time()
                    else:
                        logger.warning(f"[{symbol}] Time-stop sell order failed. Keeping in memory to retry on next tick.")

                continue # Skip buying logic since we already hold it

            # --- Filter: Check News Panic before Buying ---
            if market_filter.news_panic_flag:
                # Skipping new buys
                continue

            # NEW: Check Cooldown (Block re-entry for 3 hours)
            if symbol in cooldowns:
                elapsed = time.time() - cooldowns[symbol]
                if elapsed < 10800:
                    continue
                else:
                    del cooldowns[symbol]

            # b) Breakout Check (If NOT holding symbol)
            # Find the breakout target price
            # Get 15m OHLCV from the previous 15-minute candle
            df_15m = exchange_api.fetch_ohlcv(symbol, timeframe='15m', limit=2)
            if df_15m is None or len(df_15m) < 2:
                continue

            target_price = strategy.get_breakout_target(df_15m)
            
            if target_price and current_price >= target_price:
                # [Tier 3 Macro Filter]: 비트코인 단기 폭락(Dumping) 중이면 진입 금지
                if market_filter.check_btc_trend() == "DUMPING":
                    logger.warning(f"[{symbol}] Buy cancelled due to BTC 4H Dumping Trend.")
                    continue
                    
                # 1단계: 돈이 충분한지 (최소 5,500원) 미리 검사해서 AI 호출 낭비 방지
                krw_avail = get_current_real_balance(exchange_api, "KRW")
                if krw_avail is None: krw_avail = 0
                
                remaining_slots = config.max_positions - len(positions)
                if remaining_slots <= 0:
                    logger.info(f"[{symbol}] Maximum coin count ({config.max_positions}) reached. Can't buy more.")
                    continue
                    
                allocate_amount = krw_avail / remaining_slots
                
                # 수수료/슬리피지 대비 1% 자체를 빼버려서 극단적으로 안전한 금액만 주문 (잔액 부족 에러 원천 차단)
                allocate_amount = int(allocate_amount * 0.99)
                
                # 2. 복리리스크 방지 및 공포/탐욕 캡 적용 (Tier 1 필터 적용)
                if market_filter.fear_greed_score <= 30:
                    MAX_ALLOCATION_PER_COIN = 50000
                    # Log only occasionally or simply reduce silently since it loops 15 times
                else:
                    MAX_ALLOCATION_PER_COIN = 300000
                    
                if allocate_amount > MAX_ALLOCATION_PER_COIN:
                    allocate_amount = MAX_ALLOCATION_PER_COIN
                    logger.info(f"[{symbol}] Allocation capped at {MAX_ALLOCATION_PER_COIN:,} KRW (F&G Score: {market_filter.fear_greed_score}).")
                
                # 강제로 최소 주문 금액(5,500원) 이상으로 보정 (수수료 포함 안전빵)
                if allocate_amount < 5500:
                    if krw_avail >= 5500:
                        allocate_amount = int(krw_avail * 0.99) 
                        if allocate_amount < 5500: 
                            allocate_amount = 5500 # 혹시나 5500원 딱코면 다시 복구
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
                            'amount': bought_amount,
                            'buy_time': time.time()
                        }
                        logger.info(f"[{symbol}] Position Opened successfully.")
                else:
                    logger.info(f"[{symbol}] AI VETOED Trade: {context[-50:]}")

        except Exception as e:
            logger.error(f"Error processing symbol {symbol}: {e}")

    logger.info("--- Scan Cycle Complete ---")

def main():
    welcome_msg = f"[bold cyan]AI Fusion Trading Bot + Auto Optimizer (KST)[/bold cyan]\n" \
                  f"Tracking: [yellow]Top {config.coin_count} Coins[/yellow] | Max Hold: [green]{config.max_positions} Coins[/green]\n" \
                  f"VBD K-Value: [magenta]{config.vbd_k}[/magenta] | Target Stop: [red]{config.trailing_stop_pct*100:.1f}%[/red]\n" \
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

        market_filter = MarketFilter(ai_advisor, exchange_api)
        market_filter.update_fear_and_greed() # Run once on boot
        market_filter.analyze_global_news()   # Run once on boot

        sync_positions(exchange_api, strategy)

        scan_and_trade(exchange_api, ai_advisor, strategy, market_filter)
        
        # Check every 1 minute.
        schedule.every(1).minutes.do(scan_and_trade, exchange_api, ai_advisor, strategy, market_filter)
        
        # Auto-Optimizer Schedule: Twice a day (09:00, 21:00 KST)
        schedule.every().day.at("09:00").do(run_optimizer)
        schedule.every().day.at("21:00").do(run_optimizer)
        
        # Market Filter Schedules
        schedule.every().day.at("08:50").do(market_filter.update_fear_and_greed)
        schedule.every(4).hours.do(market_filter.analyze_global_news)
        
        logger.info("Entering multi-coin tracking loop. Press Ctrl+C to abort.")
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Bot manually stopped.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
