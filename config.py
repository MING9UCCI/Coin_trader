import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        self.active_exchange = os.getenv("ACTIVE_EXCHANGE", "UPBIT").upper()
        
        # Coinone API
        self.access_key = os.getenv("COINONE_ACCESS_KEY", "")
        self.secret_key = os.getenv("COINONE_SECRET_KEY", "")
        
        # Upbit API (Priority Default)
        self.upbit_access_key = os.getenv("UPBIT_ACCESS_KEY", "")
        self.upbit_secret_key = os.getenv("UPBIT_SECRET_KEY", "")
        
        # New: Gemini API
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        
        try:
            self.coin_count = int(os.getenv("COIN_COUNT", "15"))
        except ValueError:
            logging.error("Invalid COIN_COUNT settings in .env. Defaulting to 15 coins")
            self.coin_count = 15
            
        # Max number of positions to hold concurrently
        self.max_positions = int(os.getenv("MAX_POSITIONS", "5"))
        
        # Blacklisted coins to completely ignore (e.g. "MYX/KRW,RIVER/KRW")
        blacklist_str = os.getenv("BLACKLIST_COINS", "MYX/KRW,XRP/KRW,RIVER/KRW")
        self.blacklist = [c.strip() for c in blacklist_str.split(',') if c.strip()]
            
        # VBD specific settings
        # K value for VBD: Default to 0.5 for a balance between sensitivity and fake-out resistance
        self.vbd_k = float(os.getenv("VBD_K", "0.5"))
        # Trailing stop: Default to 2% (0.02)
        self.trailing_stop_pct = float(os.getenv("TRAILING_STOP_PCT", "0.02"))
            
        self.dry_run = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "t")

    def validate(self):
        """Check if essential API keys are provided when not in dry run."""
        if not self.dry_run:
            if self.active_exchange == "UPBIT":
                if not self.upbit_access_key or not self.upbit_secret_key:
                    raise ValueError("UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY must be set in .env when ACTIVE_EXCHANGE is UPBIT and DRY_RUN is False.")
            else:
                if not self.access_key or not self.secret_key:
                    raise ValueError("COINONE_ACCESS_KEY and COINONE_SECRET_KEY must be set in .env when ACTIVE_EXCHANGE is COINONE and DRY_RUN is False.")

        if not self.gemini_api_key:
             logging.warning("GEMINI_API_KEY is not set. AI Advisor will default to 'Confirm' fallback.")

    def reload(self):
        """Reloads dynamic strategy parameters from .env without restarting the bot."""
        load_dotenv(override=True)
        self.vbd_k = float(os.getenv("VBD_K", str(self.vbd_k)))
        self.trailing_stop_pct = float(os.getenv("TRAILING_STOP_PCT", str(self.trailing_stop_pct)))

config = Config()
