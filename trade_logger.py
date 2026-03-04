import csv
import os
from datetime import datetime, timezone, timedelta
from logger import logger

# KST timezone (UTC+9)
KST = timezone(timedelta(hours=9))
TRADE_DIR = "trades"

def get_today_csv_path():
    """Generates the file path for today's trade log."""
    if not os.path.exists(TRADE_DIR):
        os.makedirs(TRADE_DIR)
    
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    return os.path.join(TRADE_DIR, f"{today_str}.csv")

def init_trade_logger(file_path):
    if not os.path.exists(file_path):
        with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(["Time", "Symbol", "Buy Price", "Sell Price", "Amount", "Invested KRW", "Estimated Fee KRW", "Net PNL KRW", "Net PNL %"])

def log_trade(symbol, buy_price, sell_price, amount):
    try:
        csv_path = get_today_csv_path()
        init_trade_logger(csv_path)
        
        # 코인원 왕복 수수료 기준 (매수 0.2%, 매도 0.2%)를 최악방어로 계산
        buy_value = buy_price * amount
        sell_value = sell_price * amount
        
        estimated_fee = (buy_value * 0.002) + (sell_value * 0.002)
        gross_pnl = sell_value - buy_value
        net_pnl = gross_pnl - estimated_fee
        
        net_pnl_pct = (net_pnl / buy_value) * 100 if buy_value > 0 else 0
        
        time_str = datetime.now(KST).strftime("%H:%M:%S")
        
        with open(csv_path, mode='a', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow([
                time_str, 
                symbol, 
                f"{buy_price:.4f}", 
                f"{sell_price:.4f}", 
                f"{amount:.6f}", 
                f"{buy_value:.0f}",
                f"{estimated_fee:.0f}", 
                f"{net_pnl:.0f}", 
                f"{net_pnl_pct:.2f}%"
            ])
            logger.info(f"📝 Trade logged: {symbol} | Net PNL: {net_pnl:.0f} KRW ({net_pnl_pct:.2f}%) saved to {csv_path}")
    except Exception as e:
        logger.error(f"Failed to log trade to CSV: {e}")

