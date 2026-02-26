import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        self.access_key = os.getenv("UPBIT_ACCESS_KEY", "")
        self.secret_key = os.getenv("UPBIT_SECRET_KEY", "")
        
        # New: Gemini API
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        
        try:
            # We no longer trade 1 symbol. We distribute budget.
            # E.g. 100000 total -> per coin 20000 limit
            self.total_budget = float(os.getenv("TOTAL_BUDGET", "100000"))
            self.coin_count = int(os.getenv("COIN_COUNT", "5"))
            self.trade_amount = self.total_budget / self.coin_count
        except ValueError:
            logging.error("Invalid BUDGET settings in .env. Defaulting to 100,000 / 5 coins")
            self.total_budget = 100000
            self.coin_count = 5
            self.trade_amount = 20000
            
        # VBD specific settings
        # K value for VBD: typically 0.5 for crypto
        self.vbd_k = 0.5
        # Trailing stop: 3% off high
        self.trailing_stop_pct = 0.03
            
        self.dry_run = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "t")

    def validate(self):
        """Check if essential API keys are provided when not in dry run."""
        if not self.dry_run and (not self.access_key or not self.secret_key):
            raise ValueError("UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY must be set in .env when DRY_RUN is False.")
        if not self.gemini_api_key:
             logging.warning("GEMINI_API_KEY is not set. AI Advisor will default to 'Confirm' fallback.")

config = Config()
