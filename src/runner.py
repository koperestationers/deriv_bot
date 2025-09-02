"""
Main Trading Bot Runner
Orchestrates paper/live demo trading with safety controls
"""

import asyncio
import logging
import os
import signal
import sys
import time
import json
from datetime import datetime
from typing import Dict, Optional
import yaml
from dotenv import load_dotenv

from deriv_client import create_deriv_client
from strategy_even_odd import create_strategy
from risk import RiskManager, PositionSizer
from backtest import create_backtest_engine
from logging_utils import setup_logging, TradeLogger, DashboardPrinter


class TradingBot:
    """Main trading bot orchestrator with safety controls"""
    
    def __init__(self, config_path: str = "config.yaml"):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Setup logging
        setup_logging(self.config["logging"]["level"])
        self.logger = logging.getLogger(__name__)
        
        # Initialize components (console-only logging for production)
        self.trade_logger = TradeLogger()
        self.dashboard = DashboardPrinter()
        self.strategy = None
        self.risk_manager = RiskManager(self.config)
        self.position_sizer = PositionSizer(self.risk_manager)
        self.backtest_engine = create_backtest_engine(self.config)
        
        # State management
        self.mode = "paper"  # "paper" or "live_demo"
        self.running = False
        self.shutdown_requested = False
        
        # Performance tracking
        self.session_stats = {
            "start_time": time.time(),
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0
        }
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Trading bot initialized")
    
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum} - initiating graceful shutdown")
        self.shutdown_requested = True
    
    async def initialize(self):
        """Initialize all components and validate environment"""
        self.logger.info("Initializing trading bot components")
        
        # Load environment variables
        load_dotenv()
        
        # Validate environment variables
        required_vars = ["DERIV_APP_ID", "DERIV_API_TOKEN", "DERIV_ENV"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {missing_vars}")
        
        # Validate account type setting
        account_type = os.getenv("ACCOUNT_TYPE", "demo").lower()
        if account_type not in ["demo", "real"]:
            raise RuntimeError("ACCOUNT_TYPE must be either 'demo' or 'real'")
        
        self.logger.info(f"Configured for {account_type.upper()} account trading")
        
        # Initialize Deriv client
        self.deriv_client = await create_deriv_client()
        await self.deriv_client.connect()
        await self.deriv_client.authenticate()
        
        # Get initial balance and initialize risk manager
        balance = await self.deriv_client.get_balance()
        self.risk_manager.initialize_session(balance)
        
        # Initialize strategy
        self.strategy = create_strategy(self.config["strategy"], paper_mode=True)
        
        # Subscribe to tick stream
        await self.deriv_client.subscribe_ticks(callback=self._on_tick_received)
        
        self.logger.info(f"Initialization complete - Balance: ${balance:.2f}")
    
    async def run_validation_phase(self) -> bool:
        """
        Run paper trading validation to determine if live demo is safe
        
        Returns:
            True if validation passes and live demo is allowed
        """
        self.logger.info("🔍 Starting validation phase - Paper trading for edge detection")
        
        # Run backtest first
        has_edge, validation_results = self.backtest_engine.validate_strategy_edge(self.strategy)
        
        self.logger.info("📊 Backtest Results:")
        self.logger.info(f"   Total Trades: {validation_results['total_trades']}")
        self.logger.info(f"   Win Rate: {validation_results['win_rate']:.3f}")
        self.logger.info(f"   Expected Value: {validation_results['expected_value']:.4f}")
        ci = validation_results['confidence_interval']
        self.logger.info(f"   Confidence Interval: [{ci[0]:.1%}, {ci[1]:.1%}]")
        self.logger.info(f"   Recommendation: {validation_results['recommendation']}")
        
        if not has_edge:
            self.logger.warning("❌ VALIDATION FAILED: No statistical edge detected")
            self.logger.warning("   Remaining in paper mode for safety")
            return False
        
        self.logger.info("✅ VALIDATION PASSED: Statistical edge detected")
        self.logger.info("   Live demo trading authorized")
        return True
    
    async def run_trading_loop(self):
        """Main trading loop with safety controls"""
        self.running = True
        self.logger.info(f"🚀 Starting trading loop in {self.mode.upper()} mode")
        
        # CSV logging handled by TradeLogger
        
        last_status_update = 0
        tick_count = 0
        
        try:
            while self.running and not self.shutdown_requested:
                # Health checks (every 30 seconds to avoid spam)
                if time.time() - getattr(self, '_last_health_check', 0) > 30:
                    self._last_health_check = time.time()
                    if not await self.deriv_client.health_check():
                        self.logger.error("Health check failed - attempting reconnection")
                        await self._handle_connection_loss()
                        continue
                
                # Check emergency stop conditions
                emergency_stop, stop_reason = self.risk_manager.is_emergency_stop_triggered()
                if emergency_stop:
                    self.logger.error(f"🛑 EMERGENCY STOP: {stop_reason}")
                    break
                
                # Update balance
                current_balance = await self.deriv_client.get_balance()
                self.risk_manager.update_balance(current_balance)
                
                # Check if trading is allowed
                trade_allowed, risk_reason = self.risk_manager.check_trade_allowed()
                
                if trade_allowed:
                    # Get payout information
                    payout_info = await self.deriv_client.get_payout_info()
                    
                    if payout_info:
                        # Get strategy signal
                        signal = self.strategy.analyze_signal(current_balance, payout_info["payout_ratio"])
                        
                        if signal.side != "SKIP":
                            await self._execute_trade_decision(signal, payout_info)
                
                # Status update every minute
                if time.time() - last_status_update > 60:
                    self.dashboard.print_status(
                        self.risk_manager.get_risk_status(),
                        self.strategy.get_statistics(),
                        self.mode,
                        self.session_stats
                    )
                    last_status_update = time.time()
                
                # Brief pause to prevent excessive API calls
                await asyncio.sleep(5)
                tick_count += 1
                
        except Exception as e:
            self.logger.error(f"Trading loop error: {e}")
        finally:
            await self._shutdown()
    
    async def _execute_trade_decision(self, signal, payout_info: Dict):
        """Execute trade decision based on current mode"""
        stake = self.risk_manager.calculate_position_size(signal.stake_fraction)
        
        if self.mode == "paper":
            # Paper trading simulation
            result = await self.strategy.simulate_trade(signal, payout_info["payout_ratio"])
            if result["executed"]:
                self.trade_logger.log_trade(result)
                self.risk_manager.record_trade_result(result)
                self.session_stats["total_trades"] += 1
                if result["win"]:
                    self.session_stats["wins"] += 1
                else:
                    self.session_stats["losses"] += 1
                
        elif self.mode == "live_demo":
            # Real demo trading
            result = await self.deriv_client.place_odd_even_trade(signal.side, stake)
            
            if result["success"]:
                self.logger.info(f"🎯 LIVE TRADE: {signal.side} ${stake:.2f} - {signal.reason}")
                
                # Wait for contract completion (simplified)
                await asyncio.sleep(2)  # Wait for tick
                
                # Get contract result
                contract_result = await self.deriv_client.get_contract_result(result["contract_id"])
                
                if contract_result:
                    trade_data = {
                        **result,
                        **contract_result,
                        "new_balance": await self.deriv_client.get_balance()
                    }
                    
                    self.trade_logger.log_trade(trade_data)
                    self.risk_manager.record_trade_result(trade_data)
                    self.strategy.update_trade_result(signal.side, stake, contract_result.get("profit", 0))
                    
                    self.session_stats["total_trades"] += 1
                    if contract_result.get("profit", 0) > 0:
                        self.session_stats["wins"] += 1
                    else:
                        self.session_stats["losses"] += 1
    
    async def _on_tick_received(self, tick: Dict):
        """Handle incoming tick data"""
        self.strategy.add_tick(tick)
    
    
    async def _handle_connection_loss(self):
        """Handle WebSocket connection loss with exponential backoff"""
        self.logger.warning("Handling connection loss")
        
        for attempt in range(5):
            try:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                await self.deriv_client.connect()
                await self.deriv_client.authenticate()
                await self.deriv_client.subscribe_ticks(callback=self._on_tick_received)
                self.logger.info("Connection restored")
                return
                
            except Exception as e:
                self.logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
        
        self.logger.error("Failed to restore connection - stopping bot")
        self.running = False
    
    async def _shutdown(self):
        """Graceful shutdown procedure"""
        self.logger.info("🛑 Initiating graceful shutdown")
        self.running = False
        
        if self.deriv_client:
            await self.deriv_client.disconnect()
        
        # Print final statistics
        self._print_final_summary()
        self.logger.info("Shutdown complete")
    
    def _print_final_summary(self):
        """Print final session summary"""
        risk_status = self.risk_manager.get_risk_status()
        
        print("\n" + "="*60)
        print("📋 FINAL SESSION SUMMARY")
        print("="*60)
        print(f"Mode: {self.mode.upper()}")
        print(f"Starting Balance: ${risk_status['starting_balance']:.2f}")
        print(f"Final Balance: ${risk_status['current_balance']:.2f}")
        print(f"Total P&L: ${risk_status['current_balance'] - risk_status['starting_balance']:.2f}")
        print(f"Total Trades: {self.session_stats['total_trades']}")
        print(f"Session Peak: ${risk_status['session_peak']:.2f}")
        
        if self.session_stats['total_trades'] > 0:
            win_rate = self.session_stats['wins'] / self.session_stats['total_trades']
            print(f"Win Rate: {win_rate:.1%}")
        
        print("="*60)


async def main():
    """Main entry point"""
    # Load environment variables
    load_dotenv()
    
    try:
        # Create and initialize bot
        bot = TradingBot()
        await bot.initialize()
        
        # Run validation phase first
        validation_passed = await bot.run_validation_phase()
        
        if validation_passed:
            # Ask user if they want to proceed to live demo
            print("\n🎯 Validation passed! Strategy shows statistical edge.")
            print("   You can now run live demo trading.")
            print("   The bot will start in paper mode and switch to live demo after validation.")
            
            # For automated operation, switch to live demo if validation passes
            bot.mode = "live_demo"
            bot.logger.info("Switching to LIVE_DEMO mode")
        else:
            print("\n⚠️  Validation failed - No statistical edge detected.")
            print("   Remaining in paper mode for safety.")
            bot.mode = "paper"
        
        # Run main trading loop
        await bot.run_trading_loop()
        
    except KeyboardInterrupt:
        print("\n👋 Shutdown requested by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
