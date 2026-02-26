import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        self.exchange_id = os.getenv("EXCHANGE_ID", "binance").lower()
        self.api_key = os.getenv("API_KEY", "")
        self.secret_key = os.getenv("SECRET_KEY", "")
        self.symbol = os.getenv("SYMBOL", "BTC/USDT")
        
        try:
            self.trade_amount = float(os.getenv("TRADE_AMOUNT", "0.01"))
        except ValueError:
            logging.error("Invalid TRADE_AMOUNT in .env. Defaulting to 0.01")
            self.trade_amount = 0.01
            
        self.dry_run = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "t")

    def validate(self):
        """Check if essential API keys are provided when not in dry run."""
        if not self.dry_run and (not self.api_key or not self.secret_key):
            raise ValueError("API_KEY and SECRET_KEY must be set in .env when DRY_RUN is False.")

config = Config()
