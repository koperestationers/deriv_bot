#!/usr/bin/env python3
"""
Start demo trading bot
Convenience script for launching the bot
"""

import sys
import os
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from runner import main

if __name__ == "__main__":
    print("🚀 Starting Deriv Odd/Even Demo Trading Bot")
    print("   DEMO MODE ONLY - No real money at risk")
    print("   Press Ctrl+C to stop gracefully")
    print("-" * 50)
    
    asyncio.run(main())
