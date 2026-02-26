import pyupbit
import pandas_ta as ta

def get_top_volume_coins(limit=10):
    """최근 24시간 거래대금 기준 상위 코인 목록 반환 (KRW 마켓)"""
    tickers = pyupbit.get_tickers(fiat="KRW")
    
    # 거래대금을 딕셔너리로 저장하여 정렬
    volume_dict = {}
    
    # API 요청이 너무 많으면 에러가 날 수 있으나, 빠른 테스트를 위해 최근 가격/거래량 정보 동시 조회
    current_prices = pyupbit.get_current_price(tickers)
    
    # pyupbit.get_ohlcv 로 오늘 하루치 가져와서 거래대금 계산 (간단하게)
    print("거래대금 상위 코인 탐색 중...")
    for t in tickers[:30]: # 전체 다 하면 너무 오래 걸리니 상위 30개 정도만 임의로 추출 후 테스트
        df = pyupbit.get_ohlcv(t, interval="day", count=1)
        if df is not None and not df.empty:
            volume_dict[t] = df['value'].iloc[0] # value: 거래대금
            
    # 거래대금 편의상 내림차순 정렬 후 top N개 추출
    sorted_tickers = sorted(volume_dict.items(), key=lambda item: item[1], reverse=True)
    top_tickers = [item[0] for item in sorted_tickers[:limit]]
    
    return top_tickers

def backtest_multi():
    symbols = get_top_volume_coins(limit=3) # 빠른 속도를 위해 상위 3개만 먼저 테스트 (비트 뺴고)
    print(f"대상 코인: {symbols}")
    
    total_krw_balance = 10000 # 총 초기 자본 1만원
    krw_balance = total_krw_balance
    fee_rate = 0.0005 # 0.05%
    
    print(f"--- 다중 코인 백테스트 시작 (최근 약 7일, 60분봉) ---")
    print("-" * 50)
    
    total_profit = 0

    for symbol in symbols:
        df = pyupbit.get_ohlcv(symbol, interval="minute60", count=200)
        
        if df is None or df.empty:
            continue

        # 전략 원상복구: 보수적인 1시간봉 스윙 (14기간)
        df['RSI'] = ta.rsi(df['close'], length=14)
        df = df.dropna()

        # 각 코인별로 자본금을 쪼갤 수 없으니 (최소주문 5000원), 자산이 있을 때만 매수
        # 가상으로 코인 1개당 10000원씩 들어갔다고 가정
        virtual_krw = 10000 
        btc_balance = 0.0
        
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            rsi_current = current['RSI']
            rsi_previous = previous['RSI']
            price = current['close']
            
            if rsi_previous < 30 and rsi_current >= 30:
                if virtual_krw >= 5000:
                    invest_amount = virtual_krw
                    buy_fee = invest_amount * fee_rate
                    bought_btc = (invest_amount - buy_fee) / price
                    
                    btc_balance += bought_btc
                    virtual_krw -= invest_amount
            
            elif rsi_current >= 70:
                if btc_balance > 0:
                    sell_amount_krw = btc_balance * price
                    sell_fee = sell_amount_krw * fee_rate
                    virtual_krw += (sell_amount_krw - sell_fee)
                    btc_balance = 0.0

        last_price = df.iloc[-1]['close']
        final_krw_value = virtual_krw + (btc_balance * last_price)
        coin_profit = final_krw_value - 10000
        total_profit += coin_profit
        
        print(f"[{symbol}] 수익: {coin_profit:,.0f}원")

    print("-" * 50)
    print(f"총 합산 수익: {total_profit:,.0f} 원")

if __name__ == "__main__":
    backtest_multi()
