# 🤖 AI Fusion Crypto Trading Bot (Dual-Core V3)

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini-orange.svg)
![Exchange](https://img.shields.io/badge/Exchange-Upbit%20%7C%20Coinone-green.svg)

**구글의 최신 경량화 LLM(Gemini 2.5 Flash Lite)과 전통적인 퀀트 지표를 결합한 완전 자동화 24시간 가상자산 트레이딩 봇**입니다. **Upbit**와 **Coinone** 코어 모두 완벽 지원하며, 15분 봉 기준의 공격적인 단타(Scalping) 포지션에서 변동성 돌파(VBD)를 감지하고 AI의 최종 승인과 3중 거시경제 필터를 거쳐 즉각적인 시장가 매매를 수행합니다.

---

## 🚀 핵심 기능 (Key Features)

*   **듀얼 거래소 스위치 탑재:** `ACTIVE_EXCHANGE=UPBIT` 환경 변수 한 줄로 한국 1위 업비트(수수료/유동성 깡패)와 코인원 체제를 봇 재부팅 없이 완벽 호환 전환할 수 있습니다. 업비트 전환 시 오차 없는 네이티브 시장가 매매를 지원합니다.
*   **퀀트 기반 스캐닝 (VBD 전략):** 변동성 돌파 전략(Volatility Breakout)과 상대강도지수(RSI)를 15분 봉 캔들에 적용, 거래대금 상위 15개 주도주 코인 안에서 최대 N개의 슬롯만 유지하여 복리 폭발력을 극대화합니다.
*   **AI 실시간 필터 및 승인 시스템 (Gemini 2.5):** 타점이 감지되면 구글 제미나이에게 현재 상황(티커, 현재가, 목표가, RSI 수치 등)을 텍스트로 치환하여 프롬프트로 전송합니다. AI가 모멘텀의 유효성을 분석하여 `BUY(매수)` 또는 `WAIT(관망)`을 결정합니다.
*   **🛡️ 3-Tier Macro Market Filters (3중 현금 방어):** 폭락장과 둠스데이 대비를 위한 거시경제 필터망.
    - **Tier 1 (Daily F&G Index):** 일일 공포/탐욕 지수가 30 이하(극단적 공포)일 경우 투자 리미트를 1/6으로 억제.
    - **Tier 2 (AI Global News Panic):** 매 4시간마다 코인데스크 RSS 뉴스를 긁어 AI가 전세계 치명적 악재(거래소 해킹, 전쟁 발발 등) 판별 시 전량 시장가 패대기 및 매수 셧다운(BUY_LOCK).
    - **Tier 3 (BTC 4H Trend):** 매수 직전 대장주(BTC) 4시간 봉 단기 폭락(-3% 이상) 시 알트코인 매수 기각.
*   **오토 밸런싱 (Auto-Balance Detection):** `.env`에 원금을 하드코딩할 필요가 없습니다. 매분마다 거래소에서 '실제 가용 현금 + 코인 가치'를 읽어와 총 자산(Total Portfolio)을 실시간으로 계산하고 비중 풀배팅을 진행합니다.
*   **다이내믹 배팅 로직:** 특정 빈 슬롯에 몰빵되는 현상을 막기 위해, 언제나 `(현재 평가자산 총합) / N(최대 보유 코인수)` 공식을 사용하여 가장 안전하고 확실한 1/N 배팅 분산투자를 지킵니다.
*   **오토-옵티마이저 (Auto-Optimizer):** 매일 하루 두 번(09:00, 21:00) 자체 매매 이력(CSV)을 읽어들여 봇 스스로 손익비율과 승률을 수학적으로 계산한 후 다음 매매의 `VBD_K` 값과 `Trailing Stop` 퍼센티지를 조율(파라미터 자가학습)합니다.

---

## 🛠️ 기술 스택 (Architecture & Tech Stack)

*   **Language:** Python 3.10+
*   **Exchange API Engine:** `pyupbit` (업비트 기본 지원), `ccxt` (코인원 레거시 우회 지원)
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
*   **이슈:** 업비트와 달리 코인원은 API를 통한 '시장가 주문(Market Order)'을 원천 차단하고 오직 '지정가(Limit)'만 허용합니다. 기존에는 현재가로 지정가를 걸어두는 방식을 사용했으나, 변동성이 큰 돌파 매매 특성 상 0.1초 만에 가격이 도망가 주문이 붕 뜨는(Hanging) 현상이 빈번했습니다.
*   **해결:** 코인원의 거래 엔진(Matching Engine) 특성을 역이용하여 **'호가창 스위핑(Orderbook Sweeping)'** 전략을 도입했습니다. 봇이 내부적으로 실제 가격보다 `±1.5%` 불리한 가격(매수 시 더 비싸게, 매도 시 더 싸게)으로 목표가를 조작하여 지정가를 던집니다. 이는 실제로 1.5% 비싸게 사는 것이 아니라 거래소 측에 "이 가격대 안에서 가장 싼 매물부터 싹 다 긁어줘" 라고 1.5%의 상한선(Slippage Limit) 허가증을 내준 것과 같습니다. 따라서 실제 평단가는 시장가와 동일(최적가 순차 체결)하게 맞춰지며, 사실상 오차율 0%의 '완벽한 시장가 매매'를 코인원에서도 구현해냈습니다.

### 3. Coinone V2.1 "Error 107 (Parameter error)" 암호화 페이로드 분석 및 파훼
*   **이슈:** 코인원이 V2.1 API로 업데이트되면서 JSON 페이로드(Payload) 검사가 극도로 까다로워졌습니다(UUID 강제 요구, Float 타입 거부 등). 파이썬 표준인 CCXT 라이브러리가 만들어주는 정상적인 규격조차 "Error 107"을 뱉으며 모든 거래를 거부했습니다.
*   **해결:** HMAC-SHA512 서명 암호화를 네이티브 파이썬(`requests`)으로 짜서 돌려보는 등 디버깅을 거친 결과, CCXT 내부 매핑 파일이 코인원의 죽은 엔드포인트(`limit_buy`)를 향하고 있음을 발견했습니다. 최종적으로 봇 엔진 내부에서 CCXT를 억지로 V2.1로 올리지 않고 가장 안정적인 **V2 레거시 엔드포인트(`v2PrivatePostOrderLimitBuy`)로 강제 다운그레이드 패치**하여 완벽하게 데이터 무결성을 유지하며 거래에 성공했습니다.

### 4. 듀얼 거래소 (Dual-Exchange) 아키텍처와 Factory Pattern 도입
*   **이슈:** 초기에는 코인원(Coinone) 단일 엔진으로 가동되었으나, 이후 압도적인 유동성과 네이티브 시장가 주문을 지원하는 업비트(Upbit)로의 확장 필요성이 제기되었습니다. 하지만 기존에 고생해서 만든 코인원 우회 로직을 폐기하는 것은 유연성 및 백업 차원에서 좋은 선택이 아니었습니다.
*   **해결:** `.env` 환경 변수(`ACTIVE_EXCHANGE`)를 통한 팩토리 패턴(Factory Pattern)을 적용하여 두 거래소의 API 모듈(`pyupbit` vs `ccxt`)을 완전히 분리하면서도 하나의 공통 인터페이스(`exchange_api.py`)로 통일했습니다. 기존 코인원 버전의 코드를 100% 보존하면서, 단 한 줄의 세팅 변경만으로 두 거래소를 언제든 자유롭게 스위칭 가능한 하이브리드 시스템을 완성했습니다.

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
    ACTIVE_EXCHANGE=UPBIT     # UPBIT 또는 COINONE

    UPBIT_ACCESS_KEY=발급받은_업비트_액세스키
    UPBIT_SECRET_KEY=발급받은_업비트_시크릿키
    COINONE_ACCESS_KEY=발급받은_코인원_액세스키
    COINONE_SECRET_KEY=발급받은_코인원_시크릿키
    GEMINI_API_KEY=발급받은_구글_제미나이_API키

    COIN_COUNT=15             # 스캔할 거래량 상위 코인 갯수
    MAX_POSITIONS=5           # 동시 최대 보유 종목 제한 수
    BLACKLIST_COINS=MYX/KRW   # 진입 금지 코인 (쉼표 구분)
    DRY_RUN=False             # True로 변경 시 실제 매매 없이 모의투자 로깅만 됨.
    ```

    ```bash
    python main.py
    ```

---

## ☁️ 오라클 클라우드(Oracle Cloud VPS) 24시간 무인 구동 가이드

로컬 PC를 끄더라도 봇이 24시간 365일 안전하게 돌아가게 하려면 `tmux` (가상 터미널) 환경에서 실행하는 것을 권장합니다. 폰(Termius 등)으로 수시로 터미널 화면을 들여다볼 수 있습니다.

**1. 서버 최초 세팅 (Ubuntu 24.04)**
```bash
# 필수 시스템 패키지 설치
sudo apt update && sudo apt install python3-pip python3.12-venv git tmux -y
# 리포지토리 클론 및 이동
git clone https://github.com/MING9UCCI/Coin_trader.git
cd Coin_trader
# 가상환경 구축 및 의존성 설치
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
# API 키 파일 생성 (내부 텍스트 복붙)
nano .env
```

**2. 봇 백그라운드 무한 실행 (`tmux`)**
```bash
# 1. 'bot' 이라는 이름의 가상 터미널 생성 및 진입
tmux new -s bot

# 2. 실행
cd Coin_trader && source venv/bin/activate
python3 main.py

# 3. 봇이 돌아가는지 로그를 확인한 후, 화면 백그라운드로 숨기기(Detached)
# 키보드 `Ctrl + B` 를 누른 후 손을 떼고 `D` 입력
# [detached (from session bot)] 메시지가 나오면 창 끄기!
```

**3. 언제든 폰이나 PC로 서버에 봇 화면 띄워보기 (Attach)**
```bash
tmux attach -t bot
```
다 보고 백그라운드로 다시 숨길 때는 동일하게 `Ctrl + B` -> `D` 로 빠져나오면 됩니다.

**4. 깃허브 최신 코드 파이프라인(업데이트) & 재시작 가이드**
현재 `tmux` 가상 화면에 접속(`tmux attach -t bot`)하여 구경 중인 상태에서 코드를 업데이트하려면 아래 루틴을 거칩니다.
```bash
# 1. (가상 화면 내에서) 기존 돌아가고 있는 봇 멈춤
# Ctrl + C 

# 2. 깃허브에서 최신 코드 강제 다운로드
git pull origin main

# 3. 새로운 코드로 다시 봇 실행!
python3 main.py

# 4. (중요) 확인 후 백그라운드로 빠져나오기
# Ctrl + B -> D
```

---
*Created by [MING9UCCI](https://github.com/MING9UCCI)*
