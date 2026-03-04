import os
import csv
import glob
from datetime import datetime, timezone, timedelta
from logger import logger
from config import config

KST = timezone(timedelta(hours=9))
TRADE_DIR = "trades"
ENV_FILE = ".env"

def update_env_variable(key, new_value):
    """Updates a specific key-value pair in the .env file."""
    try:
        if not os.path.exists(ENV_FILE):
            logger.warning(f"{ENV_FILE} not found. Skipped updating {key}.")
            return False

        with open(ENV_FILE, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        key_found = False
        with open(ENV_FILE, 'w', encoding='utf-8') as file:
            for line in lines:
                if line.startswith(f"{key}="):
                    file.write(f"{key}={new_value}\n")
                    key_found = True
                else:
                    file.write(line)
            
            if not key_found:
                file.write(f"\n{key}={new_value}\n")
                
        return True
    except Exception as e:
        logger.error(f"Failed to update {ENV_FILE}: {e}")
        return False

def analyze_recent_trades():
    """Analyzes the trades from the last 3 days to determine if we should optimize."""
    csv_files = glob.glob(os.path.join(TRADE_DIR, "*.csv"))
    if not csv_files:
        logger.info("No trade history found. Skipping auto-optimization.")
        return None

    # Sort files by name (which is date), get up to 3 most recent
    csv_files.sort(reverse=True)
    recent_files = csv_files[:3]
    
    total_trades = 0
    winning_trades = 0
    total_net_pnl = 0.0

    for file_path in recent_files:
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    net_pnl_str = row.get('Net PNL KRW', '0')
                    try:
                        net_pnl = float(net_pnl_str)
                        total_trades += 1
                        total_net_pnl += net_pnl
                        if net_pnl > 0:
                            winning_trades += 1
                    except ValueError:
                        pass
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")

    if total_trades < 3:
        logger.info(f"Not enough trades ({total_trades}) in the last 3 days to optimize. Needs at least 3.")
        return None

    win_rate = winning_trades / total_trades
    logger.info(f"📊 Auto-Optimizer Stats | Trades: {total_trades} | Win Rate: {win_rate:.2%} | Net PNL: {total_net_pnl:.0f} KRW")
    
    return win_rate, total_net_pnl

def run_optimizer():
    """Runs the optimization logic and updates parameters if necessary."""
    logger.info("🤖 Starting Auto-Optimizer Analysis...")
    stats = analyze_recent_trades()
    
    if not stats:
        return
        
    win_rate, total_net_pnl = stats
    
    # Reload current config values to start with fresh baseline
    current_k = config.vbd_k
    current_stop = config.trailing_stop_pct
    
    new_k = current_k
    new_stop = current_stop
    
    # 1. Bad Market Condition (Win rate < 40% or net loss) -> DEFENSIVE
    if win_rate < 0.40 or total_net_pnl < 0:
        logger.info("📉 Market condition detected as POOR. Shifting to DEFENSIVE mode.")
        new_k = current_k + 0.05
        new_stop = current_stop - 0.005 # Sell faster
        
    # 2. Good Market Condition (Win rate >= 60% and profit) -> AGGRESSIVE
    elif win_rate >= 0.60 and total_net_pnl > 0:
        logger.info("📈 Market condition detected as GOOD. Shifting to AGGRESSIVE mode.")
        new_k = current_k - 0.05
        new_stop = current_stop + 0.005 # Hold longer
        
    else:
        logger.info("⚖️ Market condition is NEUTRAL. Maintaining current strategy parameters.")
        return

    # Apply Limits (Safeguards)
    new_k = round(max(0.4, min(0.8, new_k)), 2)
    new_stop = round(max(0.015, min(0.035, new_stop)), 3)
    
    changed = False
    if new_k != current_k:
        update_env_variable('VBD_K', str(new_k))
        logger.info(f"🔧 Adjusted VBD_K: {current_k} -> {new_k}")
        changed = True
        
    if new_stop != current_stop:
        update_env_variable('TRAILING_STOP_PCT', str(new_stop))
        logger.info(f"🔧 Adjusted TRAILING_STOP_PCT: {current_stop} -> {new_stop}")
        changed = True

    if changed:
        config.reload() # Tell config to reload from .env immediately
        logger.info("✅ Auto-Optimization Complete. New parameters loaded into bot memory.")
    else:
        logger.info("🔒 Parameters hit safety limits. No changes applied.")

if __name__ == "__main__":
    # Test run
    run_optimizer()
