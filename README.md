# 🤖 AI Fusion Crypto Trading Bot (Oracle VPS 24/7)

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini-orange.svg)
![Exchange](https://img.shields.io/badge/Exchange-Coinone%20%7C%20Upbit-green.svg)
![Server](https://img.shields.io/badge/Server-Oracle_Cloud-red.svg)

**구글 최고속 경량화 LLM (Gemini 2.5 Flash Lite)과 퀀트 지표(VBD)를 결합한 완전 무인 24시간 가상자산 트레이딩 봇**입니다. Oracle Cloud VPS 인스턴스에서 백그라운드 스케줄러를 통해 24시간 365일 무중단 가동되며, 15분 봉 기준의 공격적인 단타 포지션에서 돌파를 감지하고 AI의 승인과 거시경제 필터를 거쳐 즉각적인 매매를 수행합니다.

`ACTIVE_EXCHANGE` 환경 변수를 통해 **코인원(기본값, Open API 수수료 0.04% 최적화)**과 **업비트** 코어를 모두 완벽하게 전환·지원합니다.

---

## 🚀 아키텍처 및 핵심 기능 (V5.0 OVERHAUL)

### 1. 퀀트 + AI 하이브리드 스캐닝 (스마트 필터)
* **VBD (변동성 돌파) 전략:** 거래대금 상위 15개 코인의 15분 캔들을 분석, 변동성 계수(K)를 넘어서는 모멘텀을 감지합니다.
* **API 부하 최적화:** 거래량 상위 코인 스캔 결과를 **10분간 캐싱**하여 API 안정성과 속도를 확보했습니다.
* **AI 펌프앤덤프(설거지) 감지:** Gemini AI가 단기 급폭등 후 폭락 징후가 보이는 종목을 판별하여 매수를 강력하게 기각합니다.
* **RSI 과매수 필터:** RSI 75 초과 시 고점 추격 방지를 위해 자동 기각합니다.

### 2. 🛡️ 4단계 하위 시장 대응 시스템 (Dynamic Asset Allocation)
시장 상황에 따라 '보유 현금 비율'과 '슬롯 수'를 동적으로 자동 조절합니다.
* **Tier 1 (🔴 CASH MODE | F&G 0~5):** 폭락장 시나리오. **매수 100% 중단 (현금 전액 보존)**.
* **Tier 2 (🟠 DANGER | F&G 6~20):** 극심한 공포장. **슬롯 1개 고정**, 예산의 25%만 투자 (현금 75% 대기).
* **Tier 3 (🟡 DEFENSIVE | F&G 21~40):** 하락장 방어. **예산의 50%만 투자**, 슬롯은 `MAX_POSITIONS / 2`개 사용.
* **Tier 4 (🟢 NORMAL | F&G 41~100):** 정상장. 가용 예산 100% 활용, 슬롯 전체 사용.

### 3. 지능형 포지션 관리 및 완벽 동기화 (Auto-Sync)
* **N분의 1 균등 배분:** 매도/매수 후에도 어떤 코인이든 `(총 자격 × 투자 비율) / 슬롯 수` 공식을 통해 칼같이 정확한 원금 균등 분할 매수를 수행합니다.
* **전수 조사 동기화:** 1분마다 거래소 실제 잔고와 봇 메모리를 대조합니다. 유저의 수동 매도나 미추적 코인 유입을 실시간으로 감지하여 대시보드에 반영합니다.
* **적응형 트레일링 스탑:** 수익권 진입 시 고점 대비 하락 폭을 조밀하게 좁혀 이익을 잠급니다. (3% 수익 시 1.5% 트레일링 적용 등)

---

## 🛠️ 기술 스택 (Tech Stack)

* **언어:** Python 3.10+
* **LLM Engine:** `google-genai` SDK (Gemini 2.5 Flash Lite)
* **Exchange API:** `ccxt` (코인원 v2 호환 / 수수료 0.04% 로직 보정), `pyupbit` (업비트 엔진 유지)
* **퀀트/데이터:** `pandas`, `pandas-ta`
* **서버/인프라:** Oracle Cloud (Ubuntu VM), `tmux`, `pip` 환경

---

## ⚙️ 실행 방법 (Quick Setup)

1. 리포지토리 클론 및 의존성 설치:
```bash
git clone https://github.com/MING9UCCI/Coin_trader.git
cd Coin_trader
pip install -r requirements.txt
```

2. 루트 폴더에 `.env` 파일을 세팅:
```ini
ACTIVE_EXCHANGE=COINONE
COINONE_ACCESS_KEY=your_key
COINONE_SECRET_KEY=your_secret
GEMINI_API_KEY=your_gemini_key

TOP_COINS_REFRESH_MIN=10    # 코인 목록 갱신 주기 (분)
MAX_POSITIONS=6            # 최대 보유 슬롯
VBD_K=0.8                 # 변동성 계수
TRAILING_STOP_PCT=0.015    # 트레일링 스탑 (1.5%)
DRY_RUN=False             # 실전 매매 여부
```

3. 봇 실행 (`tmux` 백그라운드 권장):
```bash
python3 main.py
```

---
*Created by [MING9UCCI](https://github.com/MING9UCCI) — 개인 포트폴리오 및 기술 시연 용도입니다.*
