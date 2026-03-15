import requests
import feedparser
import time
from logger import logger

class MarketFilter:
    def __init__(self, ai_advisor, exchange_api):
        self.ai = ai_advisor
        self.exchange = exchange_api
        
        # State Flags
        self.fear_greed_score = 50 # Default Neutral
        self.news_panic_flag = False
        self.last_news_check = 0

    def update_fear_and_greed(self):
        """Tier 1 (Daily): Fetch Fear & Greed Index from CoinMarketCap (Fallback: Alternative.me)"""
        import re
        logger.info("Fetching daily Fear & Greed Index...")
        
        # 1. Primary: CoinMarketCap Scrape
        try:
            url = "https://coinmarketcap.com/charts/fear-and-greed-index/"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                match = re.search(r'"score":(\d+)', res.text)
                if match:
                    self.fear_greed_score = int(match.group(1))
                    logger.info(f"[Macro Filter] Fear & Greed Index updated via CMC: {self.fear_greed_score}")
                    return
        except Exception as e:
            logger.warning(f"Failed to scrape CMC Fear & Greed: {e}. Falling back to Alternative.me...")

        # 2. Fallback: Alternative.me
        try:
            response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                self.fear_greed_score = int(data['data'][0]['value'])
                classification = data['data'][0]['value_classification']
                logger.info(f"[Macro Filter] Fear & Greed Index updated via Alt.me: {self.fear_greed_score} ({classification})")
            else:
                logger.warning("Failed to parse Fear & Greed data from Alternative.me.")
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")

    def analyze_global_news(self):
        """Tier 2 (Every 4H): Fetch CoinDesk RSS and ask Gemini if it's a critical bear market."""
        # Prevent spamming if called multiple times rapidly
        if time.time() - self.last_news_check < 3600:
            return
            
        try:
            logger.info("Fetching global crypto news RSS for AI sentiment analysis...")
            # CoinDesk general news RSS
            feed = feedparser.parse("https://www.coindesk.com/arc/outboundfeeds/rss/")
            
            headlines = []
            for entry in feed.entries[:7]: # Top 7 latest headlines
                headlines.append(f"- {entry.title}")
                
            news_text = "\n".join(headlines)
            logger.info(f"Top Headlines Extracted:\n{news_text}")
            
            if not self.ai.client:
                logger.warning("Gemini API not configured. Skipping news analysis.")
                return

            prompt = f"""
You are an expert cryptocurrency risk manager. Read the following latest global news headlines:

{news_text}

Task: Determine if the overall market sentiment is currently in a state of CRITICAL PANIC or SEVERE BEAR MARKET due to systemic risks (e.g., massive exchange hacks, SEC blanket bans, major wars breaking out, extreme interest rate hikes).
Note: Routine volatility or minor bad news does not count as critical panic.

If there is a critical systemic risk detected, reply ONLY with the exact word: CRITICAL_BEAR
If the market is normal or just experiencing routine news, reply ONLY with the exact word: NORMAL
"""
            logger.info("Sending headlines to Gemini for panic detection...")
            response = self.ai.client.models.generate_content(
                model=self.ai.model_name,
                contents=prompt
            )
            result = response.text.strip().upper()
            
            if "CRITICAL_BEAR" in result:
                self.news_panic_flag = True
                logger.critical("🚨 [Macro Filter] AI DETECTED CRITICAL MARKET PANIC FROM NEWS. BUY LOCK ACTIVATED! 🚨")
            else:
                self.news_panic_flag = False
                logger.info("[Macro Filter] AI judged current news sentiment as NORMAL.")
                
            self.last_news_check = time.time()
            
        except Exception as e:
            logger.error(f"Error analyzing global news: {e}")
            self.news_panic_flag = False # Fail open (allow trading) if error occurs

    def check_btc_trend(self):
        """Tier 3 (Every 15m): Check if BTC is dumping significantly on 4H chart."""
        try:
            # Fetch 4H candles for BTC/KRW, limit 5 to check recent trend
            df = self.exchange.fetch_ohlcv('BTC/KRW', timeframe='4h', limit=5)
            if df is None or len(df) < 2:
                return "NORMAL"
                
            # Compare current close to previous close
            current_close = df['close'].iloc[-1]
            prev_close = df['close'].iloc[-2]
            
            drop_pct = ((current_close - prev_close) / prev_close) * 100
            
            if drop_pct <= -3.0:
                logger.warning(f"🚨 [Macro Filter] BTC 4H Dumping Detected ({drop_pct:.2f}%). Altcoin purchases paused.")
                return "DUMPING"
            
            return "NORMAL"
        except Exception as e:
            logger.error(f"Error checking BTC trend: {e}")
            return "NORMAL"

