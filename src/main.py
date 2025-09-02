"""
Main entry point for the Deriv Odd/Even Trading Bot
Handles command line arguments and bot initialization
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import TradingBot


async def run_paper_test():
    """Run paper trading validation only"""
    print("Paper Trading Test Mode")
    print("Testing strategy without live trades")
    print("-" * 40)
    
    bot = TradingBot()
    bot.mode = "paper"
    
    await bot.initialize()
    validation_passed = await bot.run_validation_phase()
    
    if validation_passed:
        print("\nVALIDATION PASSED")
        print("Strategy shows statistical edge - Live demo authorized")
    else:
        print("\nVALIDATION FAILED")
        print("No statistical edge detected - Paper mode only")
    
    return validation_passed


async def run_full_bot():
    """Run full bot with validation and potential live demo"""
    print("Full Bot Mode")
    print("Will validate strategy then run live demo if edge detected")
    print("-" * 60)
    
    bot = TradingBot()
    await bot.initialize()
    
    # Run validation first
    validation_passed = await bot.run_validation_phase()
    
    if validation_passed:
        print("\nValidation passed! Switching to live demo mode...")
        bot.mode = "live_demo"
    else:
        print("\nNo edge detected - Running live demo anyway (user preference)")
        bot.mode = "live_demo"
    
    # Run main trading loop
    await bot.run_trading_loop()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Deriv Odd/Even Trading Bot")
    parser.add_argument(
        "--mode", 
        choices=["paper", "full"], 
        default="full",
        help="Run mode: 'paper' for validation only, 'full' for complete bot"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Configuration file path"
    )
    
    args = parser.parse_args()
    
    # Verify environment
    if not os.path.exists(".env"):
        print("Error: .env file not found")
        print("Please copy .env.example to .env and configure your API credentials")
        sys.exit(1)
    
    if not os.path.exists(args.config):
        print(f"Error: Config file {args.config} not found")
        sys.exit(1)
    
    # Run appropriate mode
    try:
        if args.mode == "paper":
            asyncio.run(run_paper_test())
        else:
            asyncio.run(run_full_bot())
            
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
