# 🤖 AI Fusion Crypto Trading Bot (Oracle VPS 24/7)

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini-orange.svg)
![Exchange](https://img.shields.io/badge/Exchange-Coinone%20%7C%20Upbit-green.svg)
![Server](https://img.shields.io/badge/Server-Oracle_Cloud-red.svg)

**구글 최고속 경량화 LLM (Gemini 2.5 Flash Lite)과 퀀트 지표(VBD)를 결합한 완전 무인 24시간 가상자산 트레이딩 봇**입니다. Oracle Cloud VPS 인스턴스에서 백그라운드 스케줄러를 통해 24시간 365일 무중단 가동되며, 15분 봉 기준의 공격적인 단타 포지션에서 돌파를 감지하고 AI의 승인과 거시경제 필터를 거쳐 즉각적인 매매를 수행합니다.

`ACTIVE_EXCHANGE` 환경 변수를 통해 **코인원(기본값, Open API 수수료 0.04% 최적화)**과 **업비트** 코어를 모두 완벽하게 전환·지원합니다.

---

## 🚀 아키텍처 및 핵심 기능 (V4.4 기준)

### 1. 퀀트 + AI 하이브리드 스캐닝
* **VBD (변동성 돌파) 전략:** 거래대금 상위 15개 코인의 15분 캔들을 분석, 변동성 계수(K)를 넘어서는 모멘텀을 감지합니다.
* **RSI 과매수 필터:** RSI 지수가 75를 초과하는 종목은 "고점 추격 방지" 규칙에 따라 AI에게 묻지도 않고 자동으로 기각합니다.
* **Gemini 2.5 실시간 판독:** 퀀트 타점이 잡히면 티커, 현재가, 목표가, RSI 수치, 과거 나의 매매 승률(DB)을 구글 AI로 전송합니다. 인간의 시야로 모멘텀 유효성을 분석하여 최종 `BUY(매수)` 또는 `WAIT(관망)`을 결정합니다.

### 2. 🛡️ 극강의 하락장 방어망 (Bear Market Cash Reserve)
시장 상황에 따라 보유 '현금 비율'을 유동적으로 통제하는 3단계 방어막.
* **Tier 1 (🔴 CASH MODE | F&G ≤ 5):** CoinMarketCap 글로벌 지수가 '극단적 공포(5 이하)' 폭락 시나리오일 때, **매수 100% 셧다운 (현금 전액 보존)**.
* **Tier 2 (🟡 DEFENSIVE | F&G 6~40):** 불안정한 시장에서는 **가용 현금의 50%만 예비비로 남기고**, 나머지 50%의 소액으로만 보수적으로 단타 접근. 
* **Tier 3 (🟢 NORMAL | F&G 41+):** 정상장에서는 가용 현금 100%를 활용해 최대 보유 슬롯(예: 5slots) 내에서 N분의 1로 칼같이 정확한 원금 균등 분할 매수.

### 3. 지능형 포지션 관리 및 이익 잠금 (Profit Locking)
* **적응형 트레일링 스탑:** 단순 고정 스탑-로스가 아닙니다. 
    * 고점 대비 -3% 하락 시 매도하지만, **최대 +3% 익절 구간 진입 시 트레일링 갭을 1.5%로 바짝 조여서 이익을 확정**시킵니다 (+6% 돌파 시 1%로 초밀착).
* **적응형 하드 스탑:** 진입가 대비 -3%면 미련 없이 손절 (공포장에서는 -2%로 하드스탑 기준 강화).
* **재진입 쿨다운 / 타임스탑:** 한 번 사고 판 코인은 당일 3시간 동안 재진입(뇌동매매) 불가. 12시간 내내 안 팔리고 횡보하는 코인은 자동 타임스탑으로 청산.
* **Auto-Sync:** 휴대폰 앱으로 사용자가 수동 매도해도, 봇이 스스로 잔고를 크로스체크해 메모리를 비우는 완전 동기화 탑재.

### 4. Oracle Cloud 무인 자동화
* 오라클 클라우드 프리 티어(Ubuntu 24.04 VM) 환경의 `tmux` 백그라운드에 안착되어 365일 PC 전원을 꺼도 스스로 돌아갑니다.

---

## 🛠️ 기술 스택 (Tech Stack)

* **언어:** Python 3.10+
* **LLM Engine:** `google-genai` SDK (Gemini 2.5 Flash Lite)
* **Exchange API:** `ccxt` (코인원 v2 호환 / 수수료 0.04% 로직 보정), `pyupbit` (업비트 엔진)
* **퀀트/데이터:** `pandas`, `pandas-ta`
* **서버/인프라:** Oracle Cloud (Ubuntu VM), `tmux`, Linux Crontab / `nohup`

---

## ⚙️ 실행 방법 (Quick Setup)

1. 리포지토리 클론 및 의존성 설치:
```bash
git clone https://github.com/MING9UCCI/Coin_trader.git
cd Coin_trader
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

2. 루트 폴더에 `.env` 파일을 생성하고 키 세팅 (Github 커밋 방지):
```ini
ACTIVE_EXCHANGE=COINONE     # 또는 UPBIT
COINONE_ACCESS_KEY=your_key
COINONE_SECRET_KEY=your_secret
GEMINI_API_KEY=your_gemini_key

COIN_COUNT=15             # 스캔할 거래량 상위 코인 수
MAX_POSITIONS=5           # 기본 최대 슬롯 제한 (F&G 지수에 따라 자동 축소됨)
TRAILING_STOP_PCT=0.03    # 기본 트레일링 3%
DRY_RUN=False             # True = 모의 투자, False = 실전 매매
```

3. 봇 실행 (`tmux` 백그라운드 권장):
```bash
python3 main.py
```

---
*Created by [MING9UCCI](https://github.com/MING9UCCI) — 개인 포트폴리오 및 기술 시연 용도입니다.*
