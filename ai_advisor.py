import google.generativeai as genai
from config import config
from logger import logger

class AIAdvisor:
    def __init__(self):
        if config.gemini_api_key:
            genai.configure(api_key=config.gemini_api_key)
            # Use gemini-2.5-flash as it is extremely fast and capable
            self.model = genai.GenerativeModel('gemini-2.5-flash')
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

        prompt = f"""
You are an expert cryptocurrency trading assistant.
We are using the Volatility Breakout (VBD) strategy on a 15-minute timeframe (Aggressive Scalping) on Coinone. 

Context:
- Ticker: {symbol}
- Rank by 24h Volume on Coinone: Top {volume_rank}
- Current Price: {current_price:,} KRW
- 15m VBD Target Breakout Price: {target_price:,} KRW (K={k_value})
- Current 60m RSI: {rsi:.2f}

The price has just crossed the 15-minute breakout target. This implies a sudden upward momentum block.
Given that this coin is in the upper bounds of volume and momentum is building, do you authorize this BUY?

Instructions:
1. Briefly analyze the provided metrics.
2. In the very last line of your response, output exactly "DECISION: BUY" or "DECISION: WAIT". 
3. IMPORTANT: This is an AGGRESSIVE SCALPING bot. Do NOT veto a trade just because RSI is high (e.g. >80). High RSI means strong momentum. Unless you detect a clear anomaly, almost always output DECISION: BUY.
        """
        
        try:
            logger.info(f"Asking Gemini AI for approval on {symbol}...")
            response = self.model.generate_content(prompt)
            text = response.text.strip().upper()
            
            # Simple parsing
            if "DECISION: BUY" in text:
                return True, response.text
            else:
                return False, response.text
                
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            # Failsafe: If AI API fails, skip the trade to be safe
            return False, f"Error: {e}"
