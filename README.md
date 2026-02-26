# 🤖 AI Fusion Crypto Trading Bot (Coinone V2)

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini-orange.svg)
![CCXT](https://img.shields.io/badge/Exchange-Coinone_(CCXT)-green.svg)

An automated, 24/7 cryptocurrency trading bot that fuses traditional quantitative strategies with Google's advanced LLM reasoning. Designed specifically for aggressive 15-minute scalping on the **Coinone** exchange, this bot scans the top volume coins, detects breakout moments, and asks an AI for final trade approval before executing live fiat (KRW) market orders.

---

## 🚀 Key Features

*   **Quantitative Screening (VBD Strategy):** Implements Larry Williams' Volatility Breakout (VBD) strategy alongside RSI (Relative Strength Index) on 15-minute candles to mathematically identify explosive momentum entries.
*   **AI-Driven Trade Validation:** Integrates with Google's latest **`gemini-2.5-flash-lite`** model. The bot formats a prompt containing the coin's ticker, current price, target breakout price, and RSI, and asks the AI to analyze the momentum context and output a definitive `BUY` or `WAIT` decision.
*   **Smart Dynamic Budgeting:** Automatically fetches the live KRW balance via API and dynamically divides the portfolio evenly across the top 5 volume coins. It mathematically prevents API spam by respecting exchange minimum order limits (e.g., 5,500 KRW threshold).
*   **Trailing Stop-Loss System:** Protects profits by continuously tracking the peak price of held assets. If a coin drops 3% from its detected peak, the bot automatically triggers a market sell order to liquidate the position constraint.
*   **CCXT V2.1 API Circumvention:** Built with a highly customized CCXT wrapper to bypass Coinone's restrictive architecture (which disables standard Market Orders) and successfully circumvents undocumented JSON Parameter Serialization Errors (Error 107) on their V2 API.

---

## 🛠️ Architecture & Tech Stack

*   **Language:** Python 3.10+
*   **Exchange API Engine:** `ccxt` (Coinone implementation, downgraded to stable V2 endpoints for payload integrity).
*   **AI Engine:** `google-genai` SDK (Gemini 2.5 Flash Lite)
*   **Data Processing:** `pandas`, `pandas-ta` (Technical Analysis library for OHLCV indicators).
*   **Automation:** `schedule` for minute-by-minute system loops.

---

## ⚙️ Installation & Usage (Local Deployment)

> ⚠️ **Disclaimer:** This repository is for educational and portfolio purposes. Cryptocurrency trading involves massive risk, and this bot operates with real API keys and fiat currency. Use at your own risk.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/MING9UCCI/Coin_trader.git
    cd Coin_trader
    ```

2.  **Create a Virtual Environment & Install Dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Environment Variables (.env):**
    Create a `.env` file in the root directory. **Never commit this file to version control.**
    ```ini
    # .env
    COINONE_ACCESS_KEY=your_coinone_access_key_here
    COINONE_SECRET_KEY=your_coinone_secret_key_here
    GEMINI_API_KEY=your_google_gemini_api_key_here

    COIN_COUNT=5
    DRY_RUN=False # Set to True to simulate trades without using real money
    ```

4.  **Run the Engine:**
    ```bash
    python main.py
    ```

---

## 🧠 Engineering Highlights (Portfolio Specific)

During the development of this bot, several critical engineering hurdles were overcome:

*   **Handling Aggressive API Rate Limits:** The 15-minute scalping frequency caused immediate `429 Too Many Requests` bans from Google's Gemini 1.5 free tier. By migrating the codebase to `gemini-2.5-flash-lite` and implementing asynchronous thread-sleeping delays, the bot achieved infinite uptime without API rejection.
*   **Coinone Market Order Restrictions:** The CCXT interface threw `createOrder() allows limit orders only` because the exchange disabled standard Market Buy packets. I re-engineered the execution logic to fetch milliseconds-accurate current prices, instantly wrapping them into targeted Limit Orders to mimic immediate market fills.
*   **JSON Payload Serialization (Error 107):** Coinone's V2.1 API brutally rejected standard Python float types with a generic `Parameter Error (107)`. After attempting native HMAC-SHA512 payload bypasses, I ultimately patched the CCXT instantiation logic to downgrade to Coinone's stable V2 (`v2PrivatePostOrderLimitBuy`) endpoint, perfectly retaining CCXT's functionality while achieving 100% order success.

---
*Created by [MING9UCCI](https://github.com/MING9UCCI)*
