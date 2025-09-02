"""
Risk Management System for Deriv Odd/Even Trading Bot
Implements all safety constraints and position sizing
"""

import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class RiskLimits:
    """Risk management parameters"""
    max_stake_fraction: float = 0.02  # 2% max
    max_stake_cap: float = 0.20       # $0.20 cap when balance <= $10
    daily_loss_cap_fraction: float = 0.10  # 10% daily loss limit
    drawdown_stop_fraction: float = 0.15   # 15% drawdown stop
    loss_streak_threshold: int = 3
    cooldown_minutes: int = 10
    balance_stop_lower: float = 5.0
    balance_stop_upper: float = 10000.0


class RiskManager:
    """Comprehensive risk management with all safety constraints"""
    
    def __init__(self, config: Dict):
        self.logger = logging.getLogger(__name__)
        
        # Load risk parameters
        risk_config = config.get("risk", {})
        self.limits = RiskLimits(
            max_stake_fraction=risk_config.get("max_stake_fraction", 0.02),
            max_stake_cap=risk_config.get("max_stake_cap", 0.20),
            daily_loss_cap_fraction=risk_config.get("daily_loss_cap_fraction", 0.10),
            drawdown_stop_fraction=risk_config.get("drawdown_stop_fraction", 0.15),
            loss_streak_threshold=risk_config.get("loss_streak_threshold", 3),
            cooldown_minutes=risk_config.get("cooldown_minutes", 10),
            balance_stop_lower=risk_config.get("balance_stop_lower", 5.0),
            balance_stop_upper=risk_config.get("balance_stop_upper", 10000.0)
        )
        
        # State tracking
        self.starting_balance = 0.0
        self.daily_starting_balance = 0.0
        self.session_peak_balance = 0.0
        self.current_balance = 0.0
        
        # Loss tracking
        self.consecutive_losses = 0
        self.last_loss_time = 0
        self.cooldown_until = 0
        
        # Daily reset tracking
        self.last_reset_date = datetime.now().date()
        
        # Trade history for analysis
        self.trade_history = []
        
        self.logger.info("Risk Manager initialized with safety constraints")
    
    def initialize_session(self, starting_balance: float):
        """Initialize risk manager for new trading session"""
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.session_peak_balance = starting_balance
        
        # Check if new day - reset daily limits
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_starting_balance = starting_balance
            self.last_reset_date = today
            self.logger.info(f"New day - Daily starting balance: ${self.daily_starting_balance:.2f}")
        
        self.logger.info(f"Session initialized - Balance: ${starting_balance:.2f}")
    
    def update_balance(self, new_balance: float):
        """Update current balance and track peak"""
        self.current_balance = new_balance
        
        if new_balance > self.session_peak_balance:
            self.session_peak_balance = new_balance
            self.logger.debug(f"New session peak: ${new_balance:.2f}")
    
    def calculate_position_size(self, signal_fraction: float) -> float:
        """
        Calculate safe position size with all constraints
        
        Args:
            signal_fraction: Suggested fraction from strategy
            
        Returns:
            Safe stake amount in USD
        """
        # Start with strategy suggestion
        base_stake = signal_fraction * self.current_balance
        
        # Apply maximum fraction limit
        max_fraction_stake = self.limits.max_stake_fraction * self.current_balance
        stake = min(base_stake, max_fraction_stake)
        
        # Apply hard cap when balance is low
        if self.current_balance <= 10.0:
            stake = min(stake, max(self.limits.max_stake_cap, 0.35))  # Ensure min $0.35
        
        # Ensure minimum viable stake (Deriv requirement)
        stake = max(stake, 0.35)  # Minimum $0.35
        
        return round(stake, 2)
    
    def check_trade_allowed(self) -> tuple[bool, str]:
        """
        Check if trading is allowed based on all risk constraints
        
        Returns:
            (allowed, reason)
        """
        # Check minimum balance for trading
        if self.current_balance < 5.0:
            return False, "Balance below minimum threshold ($5.00)"
        
        # Check if balance allows minimum stake (Deriv requirement)
        min_stake = 0.35
        if self.current_balance < min_stake:
            return False, f"Balance insufficient for minimum stake (${min_stake})"
        
        # Check balance limits
        if self.current_balance <= self.limits.balance_stop_lower:
            return False, f"Balance too low: ${self.current_balance:.2f} <= ${self.limits.balance_stop_lower}"
        
        if self.current_balance >= self.limits.balance_stop_upper:
            return False, f"Balance target reached: ${self.current_balance:.2f} >= ${self.limits.balance_stop_upper}"
        
        # Check daily loss limit
        daily_loss = self.daily_starting_balance - self.current_balance
        daily_loss_limit = self.daily_starting_balance * self.limits.daily_loss_cap_fraction
        
        if daily_loss >= daily_loss_limit:
            return False, f"Daily loss limit reached: ${daily_loss:.2f} >= ${daily_loss_limit:.2f}"
        
        # Check drawdown limit
        drawdown = self.session_peak_balance - self.current_balance
        drawdown_limit = self.session_peak_balance * self.limits.drawdown_stop_fraction
        
        if drawdown >= drawdown_limit:
            return False, f"Drawdown limit reached: ${drawdown:.2f} >= ${drawdown_limit:.2f}"
        
        # Check loss streak cooldown
        if time.time() < self.cooldown_until:
            remaining = int(self.cooldown_until - time.time())
            return False, f"Loss streak cooldown: {remaining}s remaining"
        
        return True, "All risk checks passed"
    
    def record_trade_result(self, trade_data: Dict):
        """Record trade result and update risk tracking"""
        profit = trade_data.get("profit", 0)
        is_win = profit > 0
        
        # Update balance
        new_balance = trade_data.get("new_balance", self.current_balance + profit)
        self.update_balance(new_balance)
        
        # Track consecutive losses
        if is_win:
            self.consecutive_losses = 0
            self.logger.debug("Win - Loss streak reset")
        else:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            
            self.logger.warning(f"Loss #{self.consecutive_losses} - Profit: ${profit:.2f}")
            
            # Trigger cooldown if loss streak threshold reached
            if self.consecutive_losses >= self.limits.loss_streak_threshold:
                cooldown_seconds = self.limits.cooldown_minutes * 60
                self.cooldown_until = time.time() + cooldown_seconds
                
                self.logger.warning(
                    f"COOLDOWN TRIGGERED: {self.consecutive_losses} consecutive losses. "
                    f"Pausing for {self.limits.cooldown_minutes} minutes"
                )
        
        # Store trade in history
        trade_record = {
            **trade_data,
            "consecutive_losses": self.consecutive_losses,
            "session_peak": self.session_peak_balance,
            "daily_pnl": self.daily_starting_balance - new_balance,
            "timestamp": time.time()
        }
        
        self.trade_history.append(trade_record)
    
    def get_risk_status(self) -> Dict:
        """Get current risk management status"""
        daily_pnl = self.daily_starting_balance - self.current_balance
        daily_loss_limit = self.daily_starting_balance * self.limits.daily_loss_cap_fraction
        daily_loss_remaining = daily_loss_limit - daily_pnl
        
        drawdown = self.session_peak_balance - self.current_balance
        drawdown_limit = self.session_peak_balance * self.limits.drawdown_stop_fraction
        drawdown_remaining = drawdown_limit - drawdown
        
        cooldown_remaining = max(0, int(self.cooldown_until - time.time()))
        
        return {
            "current_balance": self.current_balance,
            "starting_balance": self.starting_balance,
            "daily_starting_balance": self.daily_starting_balance,
            "session_peak": self.session_peak_balance,
            "daily_pnl": daily_pnl,
            "daily_loss_remaining": daily_loss_remaining,
            "drawdown": drawdown,
            "drawdown_remaining": drawdown_remaining,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_remaining": cooldown_remaining,
            "total_trades": len(self.trade_history)
        }
    
    def is_emergency_stop_triggered(self) -> tuple[bool, str]:
        """Check if emergency stop conditions are met"""
        allowed, reason = self.check_trade_allowed()
        
        if not allowed and any(keyword in reason.lower() for keyword in 
                              ["balance too low", "balance target reached", "daily loss limit", "drawdown limit"]):
            return True, f"EMERGENCY STOP: {reason}"
        
        return False, ""
    
    def reset_daily_limits(self):
        """Reset daily limits for new trading day"""
        self.daily_starting_balance = self.current_balance
        self.last_reset_date = datetime.now().date()
        self.logger.info(f"Daily limits reset - New daily starting balance: ${self.daily_starting_balance:.2f}")


class PositionSizer:
    """Conservative position sizing with Kelly-like criteria"""
    
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(__name__)
    
    def calculate_stake(self, confidence: float, win_rate: float, payout_ratio: float) -> float:
        """
        Calculate optimal stake using modified Kelly criterion
        Very conservative approach with multiple safety layers
        """
        # Kelly fraction calculation (conservative)
        if payout_ratio <= 1.0 or win_rate <= 0.5:
            return 0.0  # No positive expectancy
        
        # Kelly formula: f = (bp - q) / b
        # where b = payout_ratio - 1, p = win_rate, q = 1 - win_rate
        b = payout_ratio - 1
        p = win_rate
        q = 1 - win_rate
        
        kelly_fraction = (b * p - q) / b
        
        # Apply heavy conservative scaling (use only 25% of Kelly)
        conservative_fraction = kelly_fraction * 0.25
        
        # Scale by confidence
        confidence_adjusted = conservative_fraction * confidence
        
        # Apply risk manager constraints
        safe_stake = self.risk_manager.calculate_position_size(confidence_adjusted)
        
        self.logger.debug(
            f"Position sizing: Kelly={kelly_fraction:.4f}, "
            f"Conservative={conservative_fraction:.4f}, "
            f"Final=${safe_stake:.2f}"
        )
        
        return safe_stake
