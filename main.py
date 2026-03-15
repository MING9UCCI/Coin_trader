import time
import schedule
import pyupbit
from rich.console import Console
from rich.panel import Panel
from config import config
from logger import logger
from exchange_api import get_exchange_api
from ai_advisor import AIAdvisor
from strategy_vbd import StrategyVBD
from database import record_trade, save_open_positions, load_open_positions
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
    """Syncs existing portfolio balances into bot memory.
    V4: First loads saved positions (with real entry prices). 
    Then detects any NEW coins on the exchange not in saved data."""
    global positions
    
    # 1단계: 영구 저장된 포지션 먼저 로드 (실제 매수가 보존)
    saved = load_open_positions()
    if saved:
        positions.update(saved)
        logger.info(f"Loaded {len(saved)} saved positions from open_positions.json")
        for sym, pos in saved.items():
            logger.info(f"  Restored: [{sym}] (Buy Price: {pos.get('buy_price', 'N/A'):,}, Amount: {pos.get('amount', 0):.4f})")
    
    # 2단계: 거래소에 있지만 저장 파일에 없는 '미추적' 코인 감지
    logger.info("Scanning exchange for any untracked positions...")
    try:
        balances = exchange_api.exchange.fetch_balance()
        top_coins = strategy.get_top_volume_coins(limit=config.coin_count)
        
        for symbol in top_coins:
            if symbol in positions:
                continue  # 이미 로드된 포지션은 건드리지 않음
            
            base_ticker = symbol.split('/')[0] if '/' in symbol else symbol.split('-')[1]
            free_amount = float(balances.get('free', {}).get(base_ticker, 0.0))
            if free_amount <= 0:
                free_amount = float(balances.get('total', {}).get(base_ticker, 0.0))
                
            if free_amount > 0:
                current_price = exchange_api.fetch_current_price(symbol)
                if current_price and (free_amount * current_price) > 5000:
                    positions[symbol] = {
                        'buy_price': current_price,  # 실제 매수가를 모르므로 현재가로 대체 (차선책)
                        'highest_price': current_price,
                        'amount': free_amount,
                        'buy_time': time.time()
                    }
                    logger.warning(f"Detected untracked position: [{symbol}] (Amount: {free_amount:.4f}, Using current price as buy_price: {current_price:,})")
        
        # 최종 상태를 영구 저장
        save_open_positions(positions)

    except Exception as e:
        logger.error(f"Failed to sync positions: {e}")

def scan_and_trade(exchange_api, ai_advisor, strategy, market_filter):
    logger.info("--- Starting VBD + AI Scan Cycle ---")
    
    # 1. Update Top Volume Coins (sorted by 24h volume descending)
    top_coins = strategy.get_top_volume_coins(limit=config.coin_count)
    
    # ===================================================================
    # PHASE A: 기존 포지션 관리 (손절/익절/타임스탑)
    # 모든 보유 코인을 먼저 순회하며 매도 조건을 체크합니다.
    # ===================================================================
    for symbol in list(positions.keys()):
        try:
            current_price = exchange_api.fetch_current_price(symbol)
            if not current_price:
                continue

            pos = positions[symbol]
            buy_price = pos['buy_price']
            highest_price = max(pos['highest_price'], current_price)
            positions[symbol]['highest_price'] = highest_price
            
            # Trailing stop condition
            drop_threshold = highest_price * (1.0 - config.trailing_stop_pct)
            
            # [Tier 2 Macro Filter]: If Panic mode, sell immediately
            if market_filter.news_panic_flag:
                logger.critical(f"🚨 [{symbol}] PANIC SELL TRIGGERED BY GLOBAL NEWS! Liquidating position.")
                drop_threshold = current_price + 99999999

            # Hard Stop Loss at -3% from entry
            hard_stop = buy_price * 0.97
            
            if current_price <= drop_threshold or current_price <= hard_stop:
                profit_pct = ((current_price - buy_price) / buy_price) * 100
                logger.info(f"[{symbol}] STOP Triggered! Selling at {current_price:,} KRW (Buy: {buy_price:,}). PNL: {profit_pct:.2f}%")
                
                base_ticker = symbol.split('/')[0] if '/' in symbol else symbol.split('-')[1]
                amount_to_sell = exchange_api.fetch_balance(base_ticker) if not config.dry_run else pos.get('amount', 0)
                order_result = exchange_api.place_market_sell_order(symbol, amount_to_sell)
                
                if order_result:
                    record_trade(symbol, buy_price, current_price, amount_to_sell)
                    del positions[symbol]
                    cooldowns[symbol] = time.time()
                    logger.info(f"[{symbol}] Position cleared & Added to 3-hour cooldown.")
                    save_open_positions(positions) # 영구 저장
                else:
                    logger.warning(f"[{symbol}] Sell order failed or partially filled. Keeping in memory to retry on next tick.")
            
            # Time-Stop: 12시간 보유 초과 시 청산
            elif (time.time() - pos.get('buy_time', time.time())) > 43200:
                profit_pct = ((current_price - buy_price) / buy_price) * 100
                logger.info(f"[{symbol}] ⏰ TIME-STOP Triggered! Held over 12 hours. Selling at {current_price:,} KRW. PNL: {profit_pct:.2f}%")
                
                base_ticker = symbol.split('/')[0] if '/' in symbol else symbol.split('-')[1]
                amount_to_sell = exchange_api.fetch_balance(base_ticker) if not config.dry_run else pos.get('amount', 0)
                order_result = exchange_api.place_market_sell_order(symbol, amount_to_sell)
                
                if order_result:
                    record_trade(symbol, buy_price, current_price, amount_to_sell)
                    del positions[symbol]
                    cooldowns[symbol] = time.time()
                    save_open_positions(positions)
                else:
                    logger.warning(f"[{symbol}] Time-stop sell order failed. Keeping in memory to retry on next tick.")

        except Exception as e:
            logger.error(f"Error managing position for {symbol}: {e}")

    # ===================================================================
    # PHASE B: 하락장 방어 모드 (Fear & Greed 3단계 필터)
    # 극단적 공포장에서는 신규 매수를 100% 차단하여 현금 보유.
    # ===================================================================
    fg_score = market_filter.fear_greed_score
    
    if fg_score <= 20:
        logger.info(f"🔴 [Cash Mode] Fear & Greed = {fg_score}. Extreme Fear detected. ALL new buys BLOCKED. Preserving cash.")
        logger.info("--- Scan Cycle Complete ---")
        return
    
    # 방어 모드: 슬롯 수와 예산 제한 축소
    if fg_score <= 40:
        effective_max_positions = min(config.max_positions, 3)
        max_alloc_cap = 30000
        logger.info(f"🟡 [Defensive Mode] Fear & Greed = {fg_score}. Max positions reduced to {effective_max_positions}, cap per coin: {max_alloc_cap:,} KRW.")
    else:
        effective_max_positions = config.max_positions
        max_alloc_cap = 300000

    # ===================================================================
    # PHASE C: 돌파 후보 수집 (매수 즉시 실행 X, 리스트에 모으기)
    # 모든 코인을 스캔한 후 거래량 순위가 높은 순서대로 매수.
    # ===================================================================
    breakout_candidates = []  # (rank_index, symbol, current_price, target_price) 튜플 리스트
    
    for idx, symbol in enumerate(top_coins):
        try:
            # 이미 보유 중이면 스킵
            if symbol in positions:
                continue
            
            # 뉴스 패닉이면 신규 매수 스킵
            if market_filter.news_panic_flag:
                continue
            
            # 쿨다운 체크
            if symbol in cooldowns:
                elapsed = time.time() - cooldowns[symbol]
                if elapsed < 10800:
                    continue
                else:
                    del cooldowns[symbol]
            
            current_price = exchange_api.fetch_current_price(symbol)
            if not current_price:
                continue
            
            # VBD 15m 돌파 체크
            df_15m = exchange_api.fetch_ohlcv(symbol, timeframe='15m', limit=2)
            if df_15m is None or len(df_15m) < 2:
                continue
            
            target_price = strategy.get_breakout_target(df_15m)
            
            if target_price and current_price >= target_price:
                # BTC Dumping 체크
                if market_filter.check_btc_trend() == "DUMPING":
                    logger.warning(f"[{symbol}] Buy cancelled due to BTC 4H Dumping Trend.")
                    continue
                
                # 후보 리스트에 추가 (rank = index in volume-sorted list, lower = better)
                breakout_candidates.append((idx, symbol, current_price, target_price))
                logger.info(f"[{symbol}] Breakout Candidate! Price {current_price:,} >= Target {target_price:,} (Volume Rank: #{idx+1})")
        
        except Exception as e:
            logger.error(f"Error scanning symbol {symbol}: {e}")
    
    # ===================================================================
    # PHASE D: 우선순위 매수 실행 (거래량 상위 코인부터 균등 배분)
    # ===================================================================
    if not breakout_candidates:
        logger.info("--- Scan Cycle Complete (No breakout candidates) ---")
        return
    
    # 거래량 순위가 높은(= rank_index가 낮은) 순서로 정렬
    breakout_candidates.sort(key=lambda x: x[0])
    logger.info(f"📊 {len(breakout_candidates)} breakout candidates found. Processing by volume rank priority...")
    
    for rank_index, symbol, current_price, target_price in breakout_candidates:
        try:
            # 슬롯 체크
            remaining_slots = effective_max_positions - len(positions)
            if remaining_slots <= 0:
                logger.info(f"[{symbol}] Maximum coin count ({effective_max_positions}) reached. Stopping buy loop.")
                break
            
            # 균등 배분: 현재 가용 현금 / 남은 빈 슬롯 수
            krw_avail = get_current_real_balance(exchange_api, "KRW")
            if krw_avail is None or krw_avail < 5500:
                logger.info(f"[{symbol}] Skipped: Insufficient KRW ({krw_avail:,.0f}). Cannot proceed.")
                break
            
            allocate_amount = int((krw_avail / remaining_slots) * 0.99)  # 1% 수수료 안전마진
            
            # 방어모드/정상모드 캡 적용
            if allocate_amount > max_alloc_cap:
                allocate_amount = max_alloc_cap
                logger.info(f"[{symbol}] Allocation capped at {max_alloc_cap:,} KRW (F&G: {fg_score}).")
            
            # 최소 주문 금액 보정
            if allocate_amount < 5500:
                if krw_avail >= 5500:
                    allocate_amount = max(5500, int(krw_avail * 0.99))
                    logger.info(f"[{symbol}] Budget per slot too low. Adjusted to: {allocate_amount:,.0f} KRW")
                else:
                    logger.info(f"[{symbol}] Skipped: KRW ({krw_avail:,.0f}) below 5,500 minimum.")
                    continue
            
            # AI 필터링
            rsi = strategy.get_rsi(symbol)
            approved, context = ai_advisor.analyze_breakout(symbol, current_price, target_price, config.vbd_k, rank_index + 1, rsi)
            
            if approved:
                logger.info(f"[{symbol}] AI Approved (Rank #{rank_index+1}): {context[-50:]}")
                logger.info(f"[{symbol}] Buying with Equal Allocation: {allocate_amount:,.0f} KRW")
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
                    save_open_positions(positions) # 영구 저장
            else:
                logger.info(f"[{symbol}] AI VETOED Trade (Rank #{rank_index+1}): {context[-50:]}")

        except Exception as e:
            logger.error(f"Error processing buy for {symbol}: {e}")

    logger.info("--- Scan Cycle Complete ---")

def main():
    welcome_msg = f"[bold cyan]AI Fusion Trading Bot + Auto Optimizer (KST)[/bold cyan]\n" \
                  f"Tracking: [yellow]Top {config.coin_count} Coins[/yellow] | Max Hold: [green]{config.max_positions} Coins[/green]\n" \
                  f"VBD K-Value: [magenta]{config.vbd_k}[/magenta] | Target Stop: [red]{config.trailing_stop_pct*100:.1f}%[/red]\n" \
                  f"Dry Run Mode: [red]{config.dry_run}[/red]"
    
    console.print(Panel(welcome_msg, title="[bold magenta]Initialization[/bold magenta]", expand=False))
    
    logger.info(f"Starting Engine with Active Exchange: {config.active_exchange}")
    
    try:
        exchange_api = get_exchange_api()
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
