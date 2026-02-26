import os
from config import config
from ai_advisor import AIAdvisor
from logger import logger

def test_gemini():
    print("====================================")
    print("🚀 Gemini AI Advisor Connection Test")
    print("====================================")
    
    # Check key visibility
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        print("❌ Error: GEMINI_API_KEY is not loaded from .env")
        return
    else:
        # Show first 5 chars for safety
        print(f"✅ GEMINI_API_KEY Loaded: {gemini_key[:5]}...")
    
    ai_advisor = AIAdvisor()
    
    if not ai_advisor.active:
        print("❌ AI Advisor is inactive. Check config.")
        return
        
    print("\n⏳ Sending a fake breakout scenario to Gemini. Please wait...")
    
    # Fake VBD scenario: BTC is breaking out, rank 1, high RSI (might trigger a WAIT)
    fake_symbol = "BTC/KRW"
    fake_current_price = 100000000
    fake_target_price = 99000000
    fake_k = 0.5
    fake_rank = 1
    fake_rsi = 85.5 # deliberately high to test logic

    success, response_text = ai_advisor.analyze_breakout(
        symbol=fake_symbol,
        current_price=fake_current_price,
        target_price=fake_target_price,
        k_value=fake_k,
        volume_rank=fake_rank,
        rsi=fake_rsi
    )
    
    print("\n------------------------------------")
    print("🤖 Gemini Response:")
    print("------------------------------------")
    print(response_text)
    print("------------------------------------")
    
    if success:
        print("\n✅ Final AI Decision: BUY (Approved)")
    else:
        print("\n⏸️ Final AI Decision: WAIT (Vetoed)")
        
    print("\n✅ AI Connection Test Completed Successfully!")

if __name__ == "__main__":
    test_gemini()
