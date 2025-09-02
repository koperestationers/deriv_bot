"""
Logging utilities for trade tracking and performance monitoring
"""

import os
from datetime import datetime
from typing import Dict, Any
import logging


class TradeLogger:
    """Handles console logging of trades and performance metrics (no file output for production)"""
    
    def __init__(self, trades_file: str = None, performance_file: str = None):
        # Disable file logging for production deployment
        self.trades_file = None
        self.performance_file = None
        self.logger = logging.getLogger(__name__)
        
        # Log configuration
        self.logger.info("TradeLogger initialized - Console output only (production mode)")
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """Log a single trade to console only"""
        try:
            # Console logging only for production
            self.logger.info(f"TRADE: {trade_data.get('mode', 'unknown').upper()} | "
                           f"Side: {trade_data.get('side', 'unknown')} | "
                           f"Stake: ${trade_data.get('stake', 0):.2f} | "
                           f"Result: {trade_data.get('result', 'unknown')} | "
                           f"P&L: ${trade_data.get('profit_loss', 0):.2f} | "
                           f"Balance: ${trade_data.get('balance_after', 0):.2f}")
        except Exception as e:
            self.logger.error(f"Failed to log trade: {e}")
    
    def log_performance(self, performance_data: Dict[str, Any]):
        """Log performance metrics to console only"""
        try:
            # Console logging only for production
            self.logger.info(f"PERFORMANCE: Balance: ${performance_data.get('balance', 0):.2f} | "
                           f"Daily P&L: ${performance_data.get('daily_pnl', 0):.2f} | "
                           f"Win Rate: {performance_data.get('win_rate', 0):.1%} | "
                           f"EV: {performance_data.get('expected_value', 0):.4f} | "
                           f"Loss Streak: {performance_data.get('loss_streak', 0)}")
        except Exception as e:
            self.logger.error(f"Failed to log performance: {e}")


class DashboardPrinter:
    """Handles console dashboard display"""
    
    @staticmethod
    def print_status(risk_status: Dict, strategy_stats: Dict, mode: str, 
                    session_stats: Dict, validation_results: Dict = None):
        """Print comprehensive status dashboard"""
        
        print("="*70)
        print(f"DERIV ODD/EVEN BOT - {mode.upper()} MODE")
        print(f"Last Updated: {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        # Balance and P&L
        print(f"Balance: ${risk_status['current_balance']:.2f} | " +
              f"Daily P&L: ${risk_status['daily_pnl']:.2f}")
        
        # Trade statistics
        win_rate = session_stats.get('wins', 0) / max(session_stats.get('total_trades', 1), 1)
        print(f"Trades: {session_stats.get('total_trades', 0)} | " +
              f"Win Rate: {win_rate:.1%} | " +
              f"Loss Streak: {risk_status['consecutive_losses']}")
        
        # Risk status
        print(f"Daily Loss Remaining: ${risk_status['daily_loss_remaining']:.2f} | " +
              f"Drawdown Remaining: ${risk_status['drawdown_remaining']:.2f}")
        
        # Cooldown status
        if risk_status['cooldown_remaining'] > 0:
            print(f"Cooldown: {risk_status['cooldown_remaining']}s remaining")
        else:
            print("Ready to trade")
        
        # Strategy statistics
        print(f"Ticks Processed: {strategy_stats.get('total_ticks', 0)} | " +
              f"Odd/Even Freq: {strategy_stats.get('odd_frequency', 0.5):.3f}/" +
              f"{strategy_stats.get('even_frequency', 0.5):.3f}")
        
        # Validation results if available
        if validation_results:
            print(f"Expected Value: {validation_results.get('expected_value', 0):.4f} | " +
                  f"Edge Detected: {'YES' if validation_results.get('validated', False) else 'NO'}")
        
        print("="*70)
    
    @staticmethod
    def print_trade_execution(side: str, stake: float, confidence: float, reason: str, mode: str):
        """Print trade execution details"""
        emoji = "PAPER" if mode == "paper" else "LIVE"
        print(f"{emoji} {mode.upper()} TRADE: {side} ${stake:.2f} | " +
              f"Confidence: {confidence:.1%} | {reason}")
    
    @staticmethod
    def print_validation_summary(validation_results: Dict):
        """Print strategy validation summary"""
        print("\n" + "="*50)
        print("STRATEGY VALIDATION RESULTS")
        print("="*50)
        
        # Validation results (if provided)
        if validation_results:
            print(f"\nStrategy Validation:")
            print(f"Win Rate: {validation_results.get('win_rate', 0):.1%}")
            
            ci = validation_results.get('confidence_interval', (0, 0))
            print(f"95% Confidence Interval: [{ci[0]:.1%}, {ci[1]:.1%}]")
            
            print(f"Expected Value: {validation_results.get('expected_value', 0):.4f}")
            print(f"Statistical Edge: {'DETECTED' if validation_results.get('validated', False) else 'NOT DETECTED'}")
        print(f"Recommendation: {validation_results.get('recommendation', 'PAPER_ONLY')}")
        
        print("="*50)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup console-only logging configuration for production"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Console only for production
        ]
    )
    
    return logging.getLogger('trading_bot')
