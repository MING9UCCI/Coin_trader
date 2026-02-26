import logging
import os
from logging.handlers import RotatingFileHandler
from rich.logging import RichHandler

def setup_logger(name="trading_bot", log_file="trading.log", level=logging.INFO):
    """Sets up a logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times if logger is already configured
    if not logger.handlers:
        # File Handler (Rotating)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console Handler (Rich UI)
        console_handler = RichHandler(rich_tracebacks=True, show_time=True, show_path=False)
        logger.addHandler(console_handler)

    return logger

logger = setup_logger()
