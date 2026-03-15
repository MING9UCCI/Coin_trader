import json
import os
from logger import logger

DB_FILE = "history.json"

def load_history():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading trade history DB: {e}")
        return []

def save_history(data):
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving trade history DB: {e}")

def record_trade(symbol, buy_price, sell_price, amount):
    """Records a completed trade into the history DB."""
    history = load_history()
    
    profit_pct = ((sell_price - buy_price) / buy_price) * 100
    
    trade_record = {
        "symbol": symbol,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "profit_pct": round(profit_pct, 2),
        "amount": amount,
        "timestamp": os.environ.get('TZ', 'KST') # Basic timestamp string
    }
    
    import datetime
    trade_record["time_str"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    history.append(trade_record)
    
    # Keep only the last 100 trades to prevent file bloat
    if len(history) > 100:
        history = history[-100:]
        
    save_history(history)
    logger.debug(f"Recorded trade for {symbol}: {profit_pct:.2f}%")

def get_recent_performance(symbol, limit=5):
    """Returns the last 'limit' trades for a specific symbol."""
    history = load_history()
    symbol_trades = [t for t in history if t.get("symbol") == symbol]
    return symbol_trades[-limit:]

# ===================================================================
# Open Position Persistence (V4)
# Saves/loads currently held positions to prevent buy_price loss on restart.
# ===================================================================
POSITIONS_FILE = "open_positions.json"

def save_open_positions(positions_dict):
    """Saves the current open positions dictionary to a JSON file."""
    try:
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(positions_dict, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving open positions: {e}")

def load_open_positions():
    """Loads previously saved open positions from a JSON file."""
    if not os.path.exists(POSITIONS_FILE):
        return {}
    try:
        with open(POSITIONS_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception as e:
        logger.error(f"Error loading open positions: {e}")
        return {}

