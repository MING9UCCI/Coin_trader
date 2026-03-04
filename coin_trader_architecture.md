# 🤖 Coin Trader V2: Core Architecture & Logic Study Guide

본 가이드는 컴퓨터공학 관점에서 **'AI 융합 변동성 돌파 스캘핑 봇'**의 핵심 로직과 설계 철학을 이해하기 위해 작성되었습니다.

---

## 🏗 System Architecture (시스템 구조)
이 봇은 거대한 모놀리식(Monolithic) 스크립트가 아니라, 역할(Role)이 명확히 분리된 **모듈화된 마이크로서비스 형태**로 구현되어 있습니다.

1. **`main.py` (Orchestrator)**
   - **역할**: 중앙 통제 센터 (Main Loop). 전체 사이클 스케줄링 및 포지션 상태(State) 관리.
2. **`exchange_api.py` (Adapter Layer)**
   - **역할**: CCXT와 Coinone REST API를 래핑(Wrapping)하는 어댑터 클래스. 통신 에러 처리, API Rate Limit 우회, **지정가 주문을 통한 시장가 체결 스푸핑(Spoofing)** 로직 등을 캡슐화.
3. **`strategy_vbd.py` (Business Logic)**
   - **역할**: 변동성 돌파(Volatility Breakout) 계산, RSI 지표 연산 등 순수 퀀트 알고리즘 로직.
4. **`ai_advisor.py` (Decision Engine)**
   - **역할**: Gemini API 통신을 담당하는 LLM 프록시. 조건이 성립된 매수 타점에 대한 최종 승인 필터.
5. **`auto_optimizer.py` (Self-Tuning Module)**
   - **역할**: 매일 지정된 시간에 과거 매매 손익 기록(CSV)을 읽고, 전략 변수(Hyperparameter)를 동적으로 교정하여 `.env`에 물리적으로 기록하고 라이브 리로드(Live Reload)시키는 보조 두뇌.

---

## 🧠 Core Module 1: `main.py` 상세 해부

이 파일에서 가장 중요한 핵심 함수는 `scan_and_trade` 입니다. 이는 1분마다 호출되며 아래의 파이프라인(Pipeline)을 거칩니다.

### Phase 1: Trailing Stop (매도 방어 로직)
보유 중인 코인(`positions` 딕셔너리에 존재하는 경우)에 대해 방어 로직을 우선 수행합니다.
```python
highest_price = max(pos['highest_price'], current_price)
drop_threshold = highest_price * (1.0 - config.trailing_stop_pct)

if current_price <= drop_threshold:
    # 시장가 매도 함수 호출!
```
- **CS 관점**: 매번 최댓값을 인메모리(RAM)의 Hash Map(`positions`)에 O(1) 복잡도로 업데이트하며 추적하는 `Max Tracking` 패턴입니다. 고정된 목표가가 아니라 변동하는 동적 하한선(Dynamic Floor)을 제공합니다.

### Phase 2: Volatility Breakout (매수 진입 로직)
미보유 코인의 타점을 분석합니다.
```python
target_price = strategy.get_breakout_target(df_15m)
if target_price and current_price >= target_price:
    # 1. 시드 분배 및 최소 한도 검사 로직
    # 2. AI_Advisor 호출 로직 
    # 3. 매수 집행 로직
```
- **CS 관점**: 조건부 동적 할당(Conditional Dynamic Allocation)이 들어갑니다. 최대 N(5)개 슬롯 중 비어있는 개수(`remaining_slots`), 현재 가용 원화 잔고(`krw_avail`), 최대 배팅 캡(`MAX_ALLOCATION_PER_COIN`)을 함수 내에서 실시간으로 연산하여 **예외 사항(Insufficient Funds 등)**이 API 단으로 넘어가기 전에 로컬에서 검증(Validation/Sanitization)하여 차단합니다.

### Phase 3: Time-Stop (좀비 킬러 로직)
```python
elif (time.time() - pos.get('buy_time', time.time())) > 43200: 
    # 12시간 경과 코인 강제 청산
```
- **CS 관점**: `Garbage Collection` 철학과 유사합니다. 생명주기(TTL - Time To Live)를 매수 시점의 Unix Timestamp를 기준으로 확인하여, 스탑로스에 닿지도 오르지도 않고 자원을 점유(Resource Hogging)하는 엔티티를 강제로 반환하여 기회비용을 최적화합니다.

---

## ⚙️ Core Module 2: `auto_optimizer.py` (자가 강화 모듈)

머신러닝(딥러닝) 모델을 무겁게 컨테이너에 올리기보다는, 컴퓨터공학의 고전적인 최적화 기법 중 하나인 **'언덕 오르기 (Hill-Climbing) 알고리즘'** 응용 버전으로 설계되었습니다.

### State Evaluation (상태 평가)
```python
win_rate = winning_trades / total_trades
```
- 최근 3일 치 CSV 파일(과거 로그 파일 파싱)을 읽어 수익 총합과 승률이라는 **목적 함수(Objective Function)** 값을 계산합니다.

### Parameter Adjustment (변수 교정 및 섭동)
```python
if win_rate < 0.40 or total_net_pnl < 0:
    # 하락장(성능 저조): 더 까다로운 K값(+0.05), 빠른 손절(-0.5%)
    new_k = current_k + 0.05
    new_stop = current_stop - 0.005 
```
- **CS 관점**: 강화학습의 Reward/Penalty와 유사합니다. 보상(수익률)이 낮으면 변수를 페널티 방향(보수적)으로 이동(Gradient Step)시키고, 보상이 좋으면 그리디(Greedy)하게 공격 방향으로 이동시킵니다.
- **Constraints (Hard Caps)**: 
  ```python
  new_k = round(max(0.4, min(0.8, new_k)), 2)
  ```
  수식의 발산(Divergence)을 막기 위해 상한/하한값(Bounding Box)을 강제해, 봇이 한 번의 이상 거래(Outlier)로 인해 미쳐 날뛰는 돌발 행동(Catastrophe)을 방지합니다.

### Hot Reload (무중단 배포)
```python
config.reload()
```
- 파이썬 파일이 시스템 입출력(Disk I/O)을 통해 물리적으로 루트 폴더의 설정 파일(`.env`)을 치환한 뒤, 현재 프로세스를 죽이지 않고 `load_dotenv(override=True)`를 호출하여 인메모리의 환경변수(Envs) 레지스트리만 새로 덮어씌웁니다. **무중단 업데이트(Zero-downtime Update)의 전형입니다.**

---

이 설계를 통해 이 프로그램은 단순 반복 매크로가 아닌, **상태를 가지며(Stateful), 스스로 과거 데이터를 피드백 구조(Feedback Loop)에 밀어 넣고 진화(Adapt)하는 고성능 자율형 에이전트(Autonomous Agent)**로 동작하게 됩니다.
