from google import genai
import time
from config import config
from logger import logger

class AIAdvisor:
    def __init__(self):
        if config.gemini_api_key:
            self.client = genai.Client(api_key=config.gemini_api_key)
            self.model_name = 'gemini-2.5-flash-lite'
            self.active = True
            logger.info("AI Advisor (Gemini) initialized.")
        else:
            self.active = False
            logger.warning("AI Advisor disabled (No API key). Will auto-approve.")

    def analyze_breakout(self, symbol, current_price, target_price, k_value, volume_rank, rsi):
        """
        Asks Gemini whether the breakout is valid given the context.
        """
        if not self.active:
            # If no API key, we blindly trust the mathematical breakout
            return True, "No AI configured. Auto-approved."

        from database import get_recent_performance
        recent_trades = get_recent_performance(symbol)
        history_text = "No recent trade history."
        if recent_trades:
            history_text = "\n".join([f"- Trade: {t['time_str']} | Profit: {t['profit_pct']}%" for t in recent_trades])

        prompt = f"""
You are an expert cryptocurrency trading assistant.
We are using the Volatility Breakout (VBD) strategy on a 15-minute timeframe on Coinone. 

Context:
- Ticker: {symbol}
- Rank by 24h Volume on Coinone: Top {volume_rank}
- Current Price: {current_price:,} KRW
- 15m VBD Target Breakout Price: {target_price:,} KRW (K={k_value})
- Current 60m RSI: {rsi:.2f}

[RECENT TRADE HISTORY FOR THIS BOT CONCERNING {symbol}]
{history_text}

The price has just crossed the 15-minute breakout target. 
Given that this coin is in the upper bounds of volume, momentum is building, AND looking at the bot's past successes/failures with this specific coin, do you authorize this BUY?

Instructions:
1. Briefly analyze the provided metrics.
2. If the Trade History shows repeated consecutive losses (e.g., multiple negative PNLs today), YOU MUST VETO THE TRADE to prevent bleeding money on a deceptive trending coin.
3. In the very last line of your response, output exactly "DECISION: BUY" or "DECISION: WAIT". 
        """
        
        try:
            logger.info(f"Asking Gemini AI for approval on {symbol}... (Adding 2s delay to prevent API Rate Limit)")
            time.sleep(2)  # Artificial delay to cool down API requests
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            text = response.text.strip().upper()
            
            # Simple parsing
            if "DECISION: BUY" in text:
                return True, response.text
            else:
                return False, response.text
                
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower():
                logger.error("Gemini API Quota Exceeded (429). Waiting for reset (Free Tier limitation).")
                return False, "Rate Limit Exceeded. Auto-veto to protect quota."
            else:
                short_err = err_str.splitlines()[0] if err_str else "Unknown Error"
                logger.error(f"Gemini API Error: {short_err}")
                return False, f"API Error: {short_err}"
