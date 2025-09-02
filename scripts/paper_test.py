#!/usr/bin/env python3
"""
Paper trading test script
Run strategy validation without live trading
"""

import sys
import os
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from runner import TradingBot

async def paper_test():
    """Run paper trading test"""
    print("📝 Starting Paper Trading Test")
    print("   Testing strategy edge detection")
    print("-" * 40)
    
    try:
        bot = TradingBot()
        bot.mode = "paper"  # Force paper mode
        
        await bot.initialize()
        validation_passed = await bot.run_validation_phase()
        
        if validation_passed:
            print("✅ Strategy validation PASSED")
            print("   Statistical edge detected - Live demo authorized")
        else:
            print("❌ Strategy validation FAILED") 
            print("   No statistical edge - Remain in paper mode")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(paper_test())
