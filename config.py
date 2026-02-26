import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        self.access_key = os.getenv("COINONE_ACCESS_KEY", "")
        self.secret_key = os.getenv("COINONE_SECRET_KEY", "")
        
        # New: Gemini API
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        
        try:
            self.coin_count = int(os.getenv("COIN_COUNT", "5"))
        except ValueError:
            logging.error("Invalid COIN_COUNT settings in .env. Defaulting to 5 coins")
            self.coin_count = 5
            
        # VBD specific settings
        # K value for VBD: lowered to 0.3 for aggressive 15m scalping
        self.vbd_k = 0.3
        # Trailing stop: 3% off high
        self.trailing_stop_pct = 0.03
            
        self.dry_run = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "t")

    def validate(self):
        """Check if essential API keys are provided when not in dry run."""
        if not self.dry_run and (not self.access_key or not self.secret_key):
            raise ValueError("COINONE_ACCESS_KEY and COINONE_SECRET_KEY must be set in .env when DRY_RUN is False.")
        if not self.gemini_api_key:
             logging.warning("GEMINI_API_KEY is not set. AI Advisor will default to 'Confirm' fallback.")

config = Config()
