"""
Unit tests for risk management system
Tests all safety constraints and position sizing
"""

import pytest
import time
from unittest.mock import Mock
from src.risk import RiskManager, RiskLimits, PositionSizer


class TestRiskManager:
    """Test risk management safety constraints"""
    
    def setup_method(self):
        """Setup test environment"""
        config = {
            "risk": {
                "max_stake_fraction": 0.02,
                "max_stake_cap": 0.20,
                "daily_loss_cap_fraction": 0.10,
                "drawdown_stop_fraction": 0.15,
                "loss_streak_threshold": 3,
                "cooldown_minutes": 10,
                "balance_stop_lower": 5.0,
                "balance_stop_upper": 10000.0
            }
        }
        self.risk_manager = RiskManager(config)
        self.risk_manager.initialize_session(100.0)  # $100 starting balance
    
    def test_position_size_constraints(self):
        """Test position sizing respects all limits"""
        # Test 2% fraction limit
        stake = self.risk_manager.calculate_position_size(0.05)  # 5% suggested
        assert stake <= 2.0  # Should be capped at 2% of $100
        
        # Test hard cap when balance is low
        self.risk_manager.update_balance(10.0)
        stake = self.risk_manager.calculate_position_size(0.05)
        assert stake <= 0.20  # Hard cap when balance <= $10
    
    def test_balance_stop_limits(self):
        """Test balance-based stop conditions"""
        # Test lower limit
        self.risk_manager.update_balance(4.0)
        allowed, reason = self.risk_manager.check_trade_allowed()
        assert not allowed
        assert "balance too low" in reason.lower()
        
        # Test upper limit
        self.risk_manager.update_balance(11000.0)
        allowed, reason = self.risk_manager.check_trade_allowed()
        assert not allowed
        assert "balance target reached" in reason.lower()
    
    def test_daily_loss_limit(self):
        """Test daily loss cap enforcement"""
        # Simulate 10% daily loss
        self.risk_manager.daily_starting_balance = 100.0
        self.risk_manager.update_balance(89.0)  # 11% loss
        
        allowed, reason = self.risk_manager.check_trade_allowed()
        assert not allowed
        assert "daily loss limit" in reason.lower()
    
    def test_drawdown_stop(self):
        """Test drawdown stop mechanism"""
        # Set peak balance higher
        self.risk_manager.session_peak_balance = 120.0
        self.risk_manager.update_balance(100.0)  # 16.7% drawdown
        
        allowed, reason = self.risk_manager.check_trade_allowed()
        assert not allowed
        assert "drawdown limit" in reason.lower()
    
    def test_loss_streak_cooldown(self):
        """Test loss streak cooldown mechanism"""
        # Simulate 3 consecutive losses
        for i in range(3):
            trade_data = {
                "profit": -1.0,
                "new_balance": self.risk_manager.current_balance - 1.0
            }
            self.risk_manager.record_trade_result(trade_data)
        
        # Should trigger cooldown
        allowed, reason = self.risk_manager.check_trade_allowed()
        assert not allowed
        assert "cooldown" in reason.lower()
    
    def test_emergency_stop_conditions(self):
        """Test emergency stop triggers"""
        # Test balance too low
        self.risk_manager.update_balance(3.0)
        emergency, reason = self.risk_manager.is_emergency_stop_triggered()
        assert emergency
        assert "emergency stop" in reason.lower()


class TestPositionSizer:
    """Test position sizing calculations"""
    
    def setup_method(self):
        """Setup test environment"""
        config = {"risk": {"max_stake_fraction": 0.02}}
        self.risk_manager = RiskManager(config)
        self.risk_manager.initialize_session(100.0)
        self.position_sizer = PositionSizer(self.risk_manager)
    
    def test_kelly_calculation(self):
        """Test Kelly criterion-based position sizing"""
        # Test with positive expectancy
        stake = self.position_sizer.calculate_stake(
            confidence=0.8,
            win_rate=0.55,
            payout_ratio=1.9
        )
        assert stake > 0
        assert stake <= 2.0  # Respect 2% limit
        
        # Test with no edge
        stake = self.position_sizer.calculate_stake(
            confidence=0.6,
            win_rate=0.48,
            payout_ratio=1.9
        )
        assert stake == 0.0  # No positive expectancy
    
    def test_conservative_scaling(self):
        """Test conservative scaling of Kelly fraction"""
        # Even with high confidence and edge, should be conservative
        stake = self.position_sizer.calculate_stake(
            confidence=0.9,
            win_rate=0.60,
            payout_ratio=2.0
        )
        # Should be much less than full Kelly would suggest
        assert stake <= 2.0  # Respect maximum limits


if __name__ == "__main__":
    pytest.main([__file__])
