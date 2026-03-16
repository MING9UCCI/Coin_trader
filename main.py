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

# Top coins cache (refreshed every TOP_COINS_REFRESH_MIN minutes)
_cached_top_coins = []
_top_coins_last_update = 0

def get_current_real_balance(exchange_api, ticker="KRW"):
    return exchange_api.fetch_balance(ticker)

def sync_positions_with_exchange(exchange_api):
    """V5: Syncs positions dict with ACTUAL exchange balances every cycle.
    Detects ALL KRW-market coins on the exchange, not just top_coins.
    Removes positions that no longer exist on the exchange."""
    global positions
    
    try:
        balances = exchange_api.exchange.fetch_balance()
        free_balances = balances.get('free', {})
        total_balances = balances.get('total', {})
        
        # A. 저장된 포지션 중 실제 잔고 없는 코인 제거
        for sym in list(positions.keys()):
            base_ticker = sym.split('/')[0] if '/' in sym else sym.split('-')[1]
            actual_amount = float(free_balances.get(base_ticker, 0.0))
            if actual_amount <= 0:
                actual_amount = float(total_balances.get(base_ticker, 0.0))
            
            current_price = exchange_api.fetch_current_price(sym)
            if not current_price or (actual_amount * current_price) < 5000:
                logger.info(f"  [Sync] Removed [{sym}] (sold or dust).")
                del positions[sym]
            else:
                positions[sym]['amount'] = actual_amount
        
        # B. 거래소에 있지만 추적 안 되는 코인 감지 (전체 스캔)
        skip_currencies = {'KRW', 'USDT', 'USDC', 'FDUSD'}
        for currency, amount in total_balances.items():
            if currency in skip_currencies:
                continue
            amount = float(amount)
            if amount <= 0:
                continue
            
            symbol = f"{currency}/KRW"
            if symbol in positions:
                continue
            
            current_price = exchange_api.fetch_current_price(symbol)
            if current_price and (amount * current_price) > 5000:
                positions[symbol] = {
                    'buy_price': current_price,
                    'highest_price': current_price,
                    'amount': amount,
                    'buy_time': time.time()
                }
                logger.warning(f"  [Sync] Detected untracked coin: [{symbol}] ({amount} 개, ~{amount*current_price:,.0f} 원).")
        
        save_open_positions(positions)
    except Exception as e:
        logger.error(f"Failed to sync positions with exchange: {e}")

def get_cached_top_coins(strategy):
    """Returns top volume coins with caching (default: refresh every 10 min)."""
    global _cached_top_coins, _top_coins_last_update
    
    refresh_interval = int(getattr(config, 'top_coins_refresh_min', 10)) * 60
    
    if not _cached_top_coins or (time.time() - _top_coins_last_update) >= refresh_interval:
        _cached_top_coins = strategy.get_top_volume_coins(limit=config.coin_count)
        _top_coins_last_update = time.time()
        logger.info(f"Top coins list refreshed ({len(_cached_top_coins)} coins). Next refresh in {refresh_interval//60} min.")
    
    return _cached_top_coins

def scan_and_trade(exchange_api, ai_advisor, strategy, market_filter):
    logger.info("--- Starting VBD + AI Scan Cycle ---")
    
    # 0. 매 사이클마다 거래소 실잔고와 동기화
    sync_positions_with_exchange(exchange_api)
    
    # 1. Top Volume Coins (캐싱, 기본 10분마다 갱신)
    top_coins = get_cached_top_coins(strategy)
    fg_score = market_filter.fear_greed_score
    
    # ===================================================================
    # PHASE A: 기존 포지션 관리 (손절/익절/타임스탑)
    # V4.1: 적응형 트레일링 스탑 — 하락장에서는 더 빡빡하게, 수익 중이면 이익 잠금
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
            
            profit_pct_now = ((current_price - buy_price) / buy_price) * 100
            
            # === 적응형 트레일링 스탑 ===
            # 기본: 고점 대비 config.trailing_stop_pct (3%) 하락 시 매도
            trailing_pct = config.trailing_stop_pct
            
            # [이익 잠금] +3% 이상 수익 중이면 트레일링을 1.5%로 타이트하게 조여서 이익을 지킴
            if profit_pct_now >= 3.0:
                trailing_pct = 0.015  # 1.5%
            # [초과 수익 보호] +6% 이상이면 더 강하게 1%로 조임
            if profit_pct_now >= 6.0:
                trailing_pct = 0.01   # 1%
            
            drop_threshold = highest_price * (1.0 - trailing_pct)
            
            # [Tier 2 Macro Filter]: If Panic mode, sell immediately
            if market_filter.news_panic_flag:
                logger.critical(f"🚨 [{symbol}] PANIC SELL TRIGGERED BY GLOBAL NEWS! Liquidating position.")
                drop_threshold = current_price + 99999999

            # === 적응형 하드 스탑 ===
            # 기본: 진입가 대비 -3%
            # 하락장(F&G ≤ 40): -2%로 더 빡빡하게
            hard_stop_pct = 0.02 if fg_score <= 40 else 0.03
            hard_stop = buy_price * (1.0 - hard_stop_pct)
            
            if current_price <= drop_threshold or current_price <= hard_stop:
                profit_pct = ((current_price - buy_price) / buy_price) * 100
                stop_type = "TRAILING" if current_price <= drop_threshold else "HARD"
                logger.info(f"[{symbol}] {stop_type} STOP Triggered! Selling at {current_price:,} KRW (Buy: {buy_price:,}). PNL: {profit_pct:.2f}%")
                
                base_ticker = symbol.split('/')[0] if '/' in symbol else symbol.split('-')[1]
                amount_to_sell = exchange_api.fetch_balance(base_ticker) if not config.dry_run else pos.get('amount', 0)
                order_result = exchange_api.place_market_sell_order(symbol, amount_to_sell)
                
                if order_result:
                    record_trade(symbol, buy_price, current_price, amount_to_sell)
                    del positions[symbol]
                    cooldowns[symbol] = time.time()
                    logger.info(f"[{symbol}] Position cleared & Added to 3-hour cooldown.")
                    save_open_positions(positions)
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
    # PHASE B: 4-Tier F&G 기반 자산 배분 시스템
    # CASH (0~5): 매수 완전 차단
    # DANGER (6~20): 25% 투자, 1슬롯 고정
    # DEFENSIVE (21~40): 50% 투자, MAX_POSITIONS/2 슬롯
    # NORMAL (41~100): 100% 투자, MAX_POSITIONS 슬롯
    # ===================================================================
    if fg_score <= 5:
        fg_mode_name = "🔴 CASH MODE"
        fg_color = "red"
        cash_usage_ratio = 0.0
        effective_max_positions = 0
    elif fg_score <= 20:
        fg_mode_name = "🟠 DANGER"
        fg_color = "bright_red"
        cash_usage_ratio = 0.25
        effective_max_positions = 1
    elif fg_score <= 40:
        fg_mode_name = "🟡 DEFENSIVE"
        fg_color = "yellow"
        cash_usage_ratio = 0.5
        effective_max_positions = max(1, config.max_positions // 2)
    else:
        fg_mode_name = "🟢 NORMAL"
        fg_color = "green"
        cash_usage_ratio = 1.0
        effective_max_positions = config.max_positions
    
    if cash_usage_ratio == 0.0:
        logger.info(f"🔴 [Cash Mode] Fear & Greed = {fg_score}. ALL new buys BLOCKED.")
        krw_now = get_current_real_balance(exchange_api, "KRW") or 0
        status_text = f"[bold cyan]Fear & Greed:[/bold cyan] [red]{fg_score} ({fg_mode_name})[/red]\n"
        status_text += f"[bold cyan]Slots:[/bold cyan] [white]{len(positions)}[/white] / [white]0 (blocked)[/white]\n"
        status_text += f"[bold cyan]KRW Balance:[/bold cyan] [green]{krw_now:,.0f}[/green] 원\n"
        status_text += "[red bold]⛔ All new buys are BLOCKED until F&G recovers above 5.[/red bold]"
        console.print(Panel(status_text, title="[bold magenta]📊 Scan Cycle Complete[/bold magenta]", expand=False))
        return

    # === [포트폴리오 기반 퍼센티지 할당 계산] ===
    krw_avail = get_current_real_balance(exchange_api, "KRW") or 0
    total_coin_value = 0
    if positions:
        for sym, pos in positions.items():
            cur_p = exchange_api.fetch_current_price(sym) or pos['buy_price']
            total_coin_value += cur_p * pos.get('amount', 0)
            
    total_portfolio = krw_avail + total_coin_value
    
    # 투자 가능 총액 = 총 자산 × 투자 비율
    target_investment_limit = total_portfolio * cash_usage_ratio
    # 코인 1종당 균등 배분 = 투자 가능 총액 / 슬롯 수
    max_alloc_cap = int(target_investment_limit / effective_max_positions) if effective_max_positions > 0 else 0
    reserve_pct = int((1 - cash_usage_ratio) * 100)

    logger.info(f"{fg_mode_name} F&G={fg_score} → {effective_max_positions} slots, cap {max_alloc_cap:,} KRW, invest {int(cash_usage_ratio*100)}% (reserve {reserve_pct}%)")

    # ===================================================================
    # PHASE C: 돌파 후보 수집 (매수 즉시 실행 X, 리스트에 모으기)
    # ===================================================================
    breakout_candidates = []
    
    for idx, symbol in enumerate(top_coins):
        try:
            if symbol in positions:
                continue
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
                if market_filter.check_btc_trend() == "DUMPING":
                    logger.warning(f"[{symbol}] Buy cancelled due to BTC 4H Dumping Trend.")
                    continue
                
                # RSI 과열 필터: RSI ≥ 75면 이미 과매수 → 고점 추격 방지
                rsi = strategy.get_rsi(symbol)
                if rsi >= 75:
                    logger.info(f"[{symbol}] Skipped: RSI={rsi:.1f} (Overbought). Avoiding top-chasing.")
                    continue
                
                breakout_candidates.append((idx, symbol, current_price, target_price, rsi))
                logger.info(f"[{symbol}] Breakout Candidate! Price {current_price:,} >= Target {target_price:,} (Rank #{idx+1}, RSI={rsi:.1f})")
        
        except Exception as e:
            logger.error(f"Error scanning symbol {symbol}: {e}")
    
    # ===================================================================
    # PHASE D: 우선순위 매수 실행 (거래량 상위 코인부터 균등 배분)
    # ===================================================================
    if not breakout_candidates:
        # No candidates도 대시보드 표시
        from rich.table import Table
        krw_now = get_current_real_balance(exchange_api, "KRW") or 0
        reserve_pct = int((1 - cash_usage_ratio) * 100)
        status_text = f"[bold cyan]Fear & Greed:[/bold cyan] [{fg_color}]{fg_score} ({fg_mode_name})[/{fg_color}]\n"
        status_text += f"[bold cyan]Slots:[/bold cyan] [white]{len(positions)}[/white] / [white]{effective_max_positions}[/white]  |  [bold cyan]Cap/Coin:[/bold cyan] [white]{max_alloc_cap:,}[/white] KRW\n"
        status_text += f"[bold cyan]KRW Balance:[/bold cyan] [green]{krw_now:,.0f}[/green] 원  |  [bold cyan]Reserve:[/bold cyan] [yellow]{reserve_pct}%[/yellow]\n"
        status_text += "[dim]No breakout candidates this cycle.[/dim]"
        console.print(Panel(status_text, title="[bold magenta]📊 Scan Cycle Complete[/bold magenta]", expand=False))
        return
    
    breakout_candidates.sort(key=lambda x: x[0])
    logger.info(f"📊 {len(breakout_candidates)} candidates found. Processing buys...")
    
    for rank_index, symbol, current_price, target_price, rsi in breakout_candidates:
        try:
            remaining_slots = effective_max_positions - len(positions)
            if remaining_slots <= 0:
                break
            
            # 매수 전 가용 현금 재확인
            krw_avail = get_current_real_balance(exchange_api, "KRW")
            if krw_avail is None or krw_avail < 5500:
                logger.info(f"[{symbol}] Skipped: Insufficient KRW ({krw_avail:,.0f}). Cannot proceed.")
                break
            
            # 포트폴리오 기반으로 사전 계산된 고정 할당량 사용
            allocate_amount = min(max_alloc_cap, int(krw_avail * 0.99))
            
            # 최소 주문 금액 보정
            if allocate_amount < 5500:
                # 할당량이 거래소 최소 기준치(5500원) 미만이면 무리하게 남은 잔고를 끌어쓰지 않고 스킵 (예방적 예비비 초과 방지)
                logger.info(f"[{symbol}] Skipped: Ideal allocation ({allocate_amount:,.0f}) is below exchange minimum (5500 KRW). Reserved.")
                continue
            
            # AI 필터링
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
                    save_open_positions(positions)
            else:
                logger.info(f"[{symbol}] AI VETOED Trade (Rank #{rank_index+1}): {context[-50:]}")

        except Exception as e:
            logger.error(f"Error processing buy for {symbol}: {e}")

    # ===================================================================
    # STATUS DASHBOARD: 매 스캔 사이클 종료 시 현재 상태 요약 출력
    # ===================================================================
    from rich.table import Table
    
    krw_now = get_current_real_balance(exchange_api, "KRW") or 0
    used_slots = len(positions)
    
    # 포지션 테이블 생성
    status_lines = []
    status_lines.append(f"[bold cyan]Fear & Greed:[/bold cyan] [{fg_color}]{fg_score} ({fg_mode_name})[/{fg_color}]")
    status_lines.append(f"[bold cyan]Slots:[/bold cyan] [white]{used_slots}[/white] / [white]{effective_max_positions}[/white]  |  [bold cyan]Cap/Coin:[/bold cyan] [white]{max_alloc_cap:,}[/white] KRW")
    status_lines.append(f"[bold cyan]KRW Balance:[/bold cyan] [green]{krw_now:,.0f}[/green] 원  |  [bold cyan]Reserve:[/bold cyan] [yellow]{reserve_pct}%[/yellow]")
    
    if positions:
        pos_table = Table(show_header=True, header_style="bold magenta", expand=False, padding=(0, 1))
        pos_table.add_column("Coin", style="cyan", width=12)
        pos_table.add_column("Buy Price", justify="right", style="white", width=14)
        pos_table.add_column("Current", justify="right", style="white", width=14)
        pos_table.add_column("PNL", justify="right", width=10)
        pos_table.add_column("Held", justify="right", style="dim", width=8)
        
        for sym, pos in positions.items():
            cur = exchange_api.fetch_current_price(sym) or pos['buy_price']
            raw_pnl = ((cur - pos['buy_price']) / pos['buy_price']) * 100
            net_pnl = raw_pnl - 0.04  # Coinone Open API round-trip fee deduction (0.02% * 2)
            pnl_color = "green" if net_pnl >= 0 else "red"
            held_hrs = (time.time() - pos.get('buy_time', time.time())) / 3600
            pos_table.add_row(
                sym.split('/')[0],
                f"{pos['buy_price']:,.0f}",
                f"{cur:,.0f}",
                f"[{pnl_color}]{net_pnl:+.2f}%[/{pnl_color}]",
                f"{held_hrs:.1f}h"
            )
        
        status_text = "\n".join(status_lines)
        console.print(Panel(status_text, title="[bold magenta]📊 Scan Cycle Complete[/bold magenta]", expand=False))
        console.print(pos_table)
    else:
        status_lines.append("[dim]No open positions.[/dim]")
        status_text = "\n".join(status_lines)
        console.print(Panel(status_text, title="[bold magenta]📊 Scan Cycle Complete[/bold magenta]", expand=False))

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

        sync_positions_with_exchange(exchange_api)

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
