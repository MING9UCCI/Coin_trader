# 🤖 AI Fusion Crypto Trading Bot (Coinone V2)

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini-orange.svg)
![CCXT](https://img.shields.io/badge/Exchange-Coinone_(CCXT)-green.svg)

**구글의 최신 경량화 LLM(Gemini 2.5 Flash Lite)과 전통적인 퀀트 지표를 결합한 완전 자동화 24시간 가상자산 트레이딩 봇**입니다. 코인원(Coinone) 거래소를 타겟으로 개발되었으며, 15분 봉 기준의 공격적인 단타(Scalping) 포지션에서 변동성 돌파(VBD)를 감지하고, AI의 최종 승인을 거쳐 즉각적인 시장가 매매를 수행합니다.

---

## 🚀 핵심 기능 (Key Features)

*   **퀀트 기반 스캐닝 (VBD 전략):** 래리 윌리엄스의 변동성 돌파 전략(Volatility Breakout)과 상대강도지수(RSI)를 15분 봉 캔들에 적용하여, 거래량 상위 5개 코인 중 장중 폭발적인 상승 모멘텀이 발생하는 정확한 타점을 계산합니다.
*   **AI 실시간 검증 시스템:** 타점이 감지되면 구글의 최신 **`gemini-2.5-flash-lite`** 모델에게 즉시 현재 상황(티커, 현재가, 목표가, RSI 수치 등)을 텍스트로 치환하여 프롬프트로 전송합니다. AI가 모멘텀의 유효성을 분석하여 `BUY(매수)` 또는 `WAIT(관망)` 형식의 최종 의사결정을 내립니다.
*   **다이내믹 자산 분배 로직:** 매분마다 거래소 API를 추적하여 사용 가능한 실시간 원화(KRW) 잔고를 파악합니다. 남은 예산에 맞춰 보유 가능한 코인의 슬롯을 동적으로 계산하고, 거래소 최소 주문 금액(예: 5,500 KRW) 미만인 경우 API 호출 자체를 차단하여 시스템 안정성을 높였습니다.
*   **트레일링 스톱 (Trailing Stop) 시스템:** 수익을 극대화하면서 손실을 제한하기 위해, 매수 직후부터 해당 코인의 '최고점'을 지속적으로 기록합니다. 최고점 대비 **3% 이상 하락**하는 즉시 시장가 매도(청산) 주문을 발생시킵니다.
*   **CCXT V2.1 API 우회 기술 적용:** 코인원의 폐쇄적인 API 아키텍처(시장가 주문 미지원, 엄격한 payload 검열)를 파훼하기 위해 고도로 커스터마이징된 CCXT 래퍼 로직이 탑재되어 있습니다.

---

## 🛠️ 기술 스택 (Architecture & Tech Stack)

*   **Language:** Python 3.10+
*   **Exchange API Engine:** `ccxt` (Coinone API 규격에 맞춰 페이로드 및 엔드포인트를 V2로 다운그레이드 패치하여 사용)
*   **AI Engine:** `google-genai` SDK (Gemini 2.5 Flash Lite 탑재)
*   **Data Processing:** `pandas`, `pandas-ta` (보조 지표 및 OHLCV 데이터 연산)
*   **Automation:** `schedule` (백그라운드 스케줄러 루프 구동)

---

## 🧠 트러블 슈팅 (Engineering Highlights)

본 프로젝트를 개발 및 운영하면서 발생한 실제 크리티컬 이슈들과 그 해결 과정입니다.

### 1. 15분 단타 스캔으로 인한 Google API Rate Limit (429 에러) 돌파
*   **이슈:** 15분마다 탑 5 코인을 추적하며 돌파 시 AI에게 컨설팅을 요청하는 로직 특성상, 기존 `gemini-1.5-flash` 모델의 무료 API 한도(15회/분)를 순식간에 초과하여 IP 밴(429 에러)이 발생했습니다.
*   **해결:** AI 추론 엔진을 처리 속도가 압도적으로 빠르고 한도가 매우 넉넉한 구글의 최신 **`gemini-2.5-flash-lite`** 모델로 전면 교체했습니다. 또한 API Request 간에 비동기 지연(`time.sleep`) 로직을 삽입하여 Rate Limit을 완전히 우회하는 무한 루프 안정성을 확보했습니다.

### 2. 코인원 시장가 매수 불가 사태 (CCXT Limitation) 해결
*   **이슈:** 업비트와 달리 코인원은 API를 통한 '시장가 주문(Market Order)'을 원천 차단하고 오직 '지정가(Limit)'만 허용합니다. 이로 인해 최초 단계에서 매수/매도 엔진이 멈추는 에러가 발생했습니다.
*   **해결:** `place_market_buy_order` 메서드를 재설계하여, 주문 즉시 0.1초 단위의 현재가(Current Price)를 긁어온 뒤 해당 가격으로 지정가 주문을 강제 삽입하는 방식으로, 코인원 서버가 정상적인 스캘핑 시장가 주문으로 인식하게끔 로직을 우회했습니다.

### 3. Coinone V2.1 "Error 107 (Parameter error)" 암호화 페이로드 분석 및 파훼
*   **이슈:** 코인원이 V2.1 API로 업데이트되면서 JSON 페이로드(Payload) 검사가 극도로 까다로워졌습니다(UUID 강제 요구, Float 타입 거부 등). 파이썬 표준인 CCXT 라이브러리가 만들어주는 정상적인 규격조차 "Error 107"을 뱉으며 모든 거래를 거부했습니다.
*   **해결:** HMAC-SHA512 서명 암호화를 네이티브 파이썬(`requests`)으로 짜서 돌려보는 등 디버깅을 거친 결과, CCXT 내부 매핑 파일이 코인원의 죽은 엔드포인트(`limit_buy`)를 향하고 있음을 발견했습니다. 최종적으로 봇 엔진 내부에서 CCXT를 억지로 V2.1로 올리지 않고 가장 안정적인 **V2 레거시 엔드포인트(`v2PrivatePostOrderLimitBuy`)로 강제 다운그레이드 패치**하여 완벽하게 데이터 무결성을 유지하며 거래에 성공했습니다.

---

## ⚙️ 설치 및 실행 방법

> ⚠️ **면책 조항:** 본 리포지토리는 포트폴리오 및 기술 시연 목적으로 작성되었습니다. 봇은 실제 API 키와 원화(KRW)를 사용하여 매매를 수행하므로 사용 시 강력한 주의가 필요합니다.

1.  **리포지토리 클론:**
    ```bash
    git clone https://github.com/MING9UCCI/Coin_trader.git
    cd Coin_trader
    ```

2.  **가상 환경(Virtual Environment) 세팅:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows 환경: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **환경 변수 (.env) 설정:**
    루트 디렉토리에 `.env` 파일을 생성합니다. **이 파일은 GitHub에 절대 커밋되지 않도록 `.gitignore`에 등록되어 있습니다.**
    ```ini
    # .env
    COINONE_ACCESS_KEY=발급받은_코인원_액세스키
    COINONE_SECRET_KEY=발급받은_코인원_시크릿키
    GEMINI_API_KEY=발급받은_구글_제미나이_API키

    COIN_COUNT=5
    DRY_RUN=False # True로 변경 시 실제 매매 없이 모의 투자 로직만 돌아갑니다.
    ```

4.  **엔진 구동:**
    ```bash
    python main.py
    ```

---
*Created by [MING9UCCI](https://github.com/MING9UCCI)*
