import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        self.access_key = os.getenv("UPBIT_ACCESS_KEY", "")
        self.secret_key = os.getenv("UPBIT_SECRET_KEY", "")
        self.symbol = os.getenv("SYMBOL", "KRW-BTC")
        
        try:
            self.trade_amount = float(os.getenv("TRADE_AMOUNT", "10000"))
        except ValueError:
            logging.error("Invalid TRADE_AMOUNT in .env. Defaulting to 10000")
            self.trade_amount = 10000
            
        self.dry_run = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "t")

    def validate(self):
        """Check if essential API keys are provided when not in dry run."""
        if not self.dry_run and (not self.access_key or not self.secret_key):
            raise ValueError("UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY must be set in .env when DRY_RUN is False.")

config = Config()
