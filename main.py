import time
import schedule
from config import config
from logger import logger
from exchange_api import ExchangeAPI
from strategy import Strategy

# 간단한 상태 관리: 코인을 샀는지 여부
# 실제 운영 환경에서는 upbit.get_balance()로 실제 잔고를 확인하는 것이 훨씬 안전합니다.
in_position = False

def trading_job(exchange_api):
    global in_position
    symbol = config.symbol
    krw_amount = config.trade_amount
    
    logger.info("--- Starting trading job cycle ---")
    
    # 1. 시세 데이터 조회 (예: 60분봉)
    df = exchange_api.fetch_ohlcv(symbol, timeframe='minute60', limit=50)
    
    if df is not None:
        # 2. 투자 전략 분석 (RSI)
        strategy = Strategy(df)
        signal = strategy.analyze()
        
        # 3. 매매 실행
        if signal == 'BUY' and not in_position:
            # 원화(KRW) 잔고 확인
            krw_balance = exchange_api.fetch_balance("KRW") if not config.dry_run else krw_amount * 2
            
            # 수수료 고려하여 실제 가능한 매수 금액 계산이 필요할 수 있으나 여기선 단순화
            if krw_balance >= krw_amount:
                # 업비트 시장가 매수는 '액수(KRW)' 기준으로 주문합니다.
                order = exchange_api.place_market_buy_order(symbol, krw_amount)
                if order:
                    in_position = True
            else:
                logger.warning(f"Not enough KRW balance to buy. Have: {krw_balance}, Need: {krw_amount}")
                
        elif signal == 'SELL' and in_position:
            # 보유 코인 수량 확인
            # 'KRW-BTC' -> 'BTC'만 추출하여 조회
            coin_ticker = symbol.split('-')[1]
            coin_balance = exchange_api.fetch_balance(coin_ticker) if not config.dry_run else 0.001
            
            # 최소 주문 금액(업비트 기준 보통 5000원) 이상인지 확인 필요하나 여기선 전량 매도
            if coin_balance > 0:
                # 업비트 시장가 매도는 '코인 수량' 기준으로 주문합니다.
                order = exchange_api.place_market_sell_order(symbol, coin_balance)
                if order:
                    in_position = False
            else:
                 logger.warning(f"No {coin_ticker} balance to sell.")
                 in_position = False # 상태 초기화
    
    logger.info("--- Trading job cycle complete ---")

def main():
    logger.info(f"Starting Trading Bot (Dry Run: {config.dry_run})")
    
    try:
        # 거래소 API 초기화
        exchange_api = ExchangeAPI()
        
        # 설정값 검증
        config.validate()
        
        # 초기 잔고 확인 로직 (테스트)
        if not config.dry_run:
            exchange_api.fetch_balance("KRW")

        # 봇 시작 시 1회 즉시 실행
        trading_job(exchange_api)

        # 1시간마다 반복 예약
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
