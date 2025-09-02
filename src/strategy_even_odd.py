"""
Conservative Odd/Even Strategy Module
Implements statistical analysis with strict edge validation
"""

import logging
import numpy as np
from collections import deque
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import time


@dataclass
class StrategySignal:
    """Strategy decision output"""
    side: str  # "ODD", "EVEN", or "SKIP"
    confidence: float  # 0.0 to 1.0
    stake_fraction: float  # Fraction of balance to risk
    reason: str  # Decision rationale


class OddEvenStrategy:
    """
    Conservative strategy for Odd/Even binary options
    Uses frequency analysis and volatility filtering
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Strategy parameters
        self.lookback_window = config.get("lookback_window", 20)
        self.min_confidence = config.get("min_confidence_threshold", 0.55)
        self.frequency_bias_threshold = config.get("frequency_bias_threshold", 0.15)
        self.volatility_threshold = config.get("volatility_threshold", 0.02)
        self.cooldown_seconds = config.get("cooldown_between_trades", 30)
        
        # Data storage
        self.tick_history = deque(maxlen=1000)  # Store recent ticks
        self.last_trade_time = 0
        
        # Statistics tracking
        self.odd_count = 0
        self.even_count = 0
        self.total_ticks = 0
        
    def add_tick(self, tick: Dict):
        """Add new tick to analysis window"""
        if "last_digit" not in tick:
            return
            
        self.tick_history.append(tick)
        self.total_ticks += 1
        
        if tick["last_digit"] % 2 == 1:
            self.odd_count += 1
        else:
            self.even_count += 1
    
    def analyze_signal(self, current_balance: float, payout_ratio: float) -> StrategySignal:
        """
        Analyze current market state and generate trading signal
        
        Args:
            current_balance: Current account balance
            payout_ratio: Current payout ratio for odd/even
            
        Returns:
            StrategySignal with decision
        """
        # Check cooldown period
        if time.time() - self.last_trade_time < self.cooldown_seconds:
            return StrategySignal("SKIP", 0.0, 0.0, "Cooldown period active")
        
        # Need minimum data for analysis
        if len(self.tick_history) < self.lookback_window:
            return StrategySignal("SKIP", 0.0, 0.0, f"Insufficient data: {len(self.tick_history)}/{self.lookback_window}")
        
        # Calculate expected value first - refuse if not positive
        expected_value = self._calculate_expected_value(payout_ratio)
        if expected_value <= 0:
            return StrategySignal("SKIP", 0.0, 0.0, f"No positive edge: EV={expected_value:.4f}")
        
        # Analyze recent tick patterns
        recent_ticks = list(self.tick_history)[-self.lookback_window:]
        
        # Frequency bias analysis
        frequency_signal = self._analyze_frequency_bias(recent_ticks)
        
        # Volatility filter
        volatility_signal = self._analyze_volatility(recent_ticks)
        
        # Time-based filter (optional - avoid high-frequency periods)
        time_signal = self._analyze_time_patterns()
        
        # Combine signals
        final_signal = self._combine_signals(frequency_signal, volatility_signal, time_signal)
        
        # Apply confidence threshold
        if final_signal.confidence < self.min_confidence:
            return StrategySignal("SKIP", 0.0, 0.0, f"Low confidence: {final_signal.confidence:.3f}")
        
        # Calculate position size (conservative)
        stake_fraction = self._calculate_position_size(final_signal.confidence, current_balance)
        
        return StrategySignal(
            final_signal.side,
            final_signal.confidence,
            stake_fraction,
            final_signal.reason
        )
    
    def _calculate_expected_value(self, payout_ratio: float) -> float:
        """
        Calculate expected value based on historical performance
        Conservative approach - assume 50/50 unless strong evidence
        """
        if self.total_ticks < 100:
            # Insufficient data - assume house edge
            return payout_ratio - 1.0
        
        # Calculate historical win rate (very conservative)
        recent_window = min(200, len(self.tick_history))
        if recent_window < 50:
            return payout_ratio - 1.0
            
        recent_ticks = list(self.tick_history)[-recent_window:]
        
        # Test both odd and even strategies
        odd_wins = sum(1 for tick in recent_ticks if tick["last_digit"] % 2 == 1)
        even_wins = recent_window - odd_wins
        
        odd_win_rate = odd_wins / recent_window
        even_win_rate = even_wins / recent_window
        
        # Use the better performing side, but be conservative
        best_win_rate = max(odd_win_rate, even_win_rate)
        
        # Only consider positive if significantly above 50%
        if best_win_rate > 0.52:  # Require at least 52% to overcome house edge
            expected_value = (best_win_rate * payout_ratio) - 1.0
        else:
            expected_value = payout_ratio - 1.0  # Assume house edge
            
        return expected_value
    
    def _analyze_frequency_bias(self, recent_ticks: List[Dict]) -> StrategySignal:
        """Analyze frequency bias in recent ticks"""
        if not recent_ticks:
            return StrategySignal("SKIP", 0.0, 0.0, "No recent ticks")
        
        # Count odd/even in recent window
        odd_count = sum(1 for tick in recent_ticks if tick["last_digit"] % 2 == 1)
        even_count = len(recent_ticks) - odd_count
        
        # Calculate bias from expected 50/50
        total = len(recent_ticks)
        odd_freq = odd_count / total
        even_freq = even_count / total
        
        # Determine bias direction and strength
        bias_strength = abs(odd_freq - 0.5)
        
        if bias_strength < self.frequency_bias_threshold:
            return StrategySignal("SKIP", 0.0, 0.0, f"No significant bias: {bias_strength:.3f}")
        
        # Mean reversion assumption - bet against the recent bias
        if odd_freq > 0.5:
            # Recent odd bias - bet on even
            confidence = min(0.8, 0.5 + bias_strength)
            return StrategySignal("EVEN", confidence, 0.0, f"Mean reversion: odd_freq={odd_freq:.3f}")
        else:
            # Recent even bias - bet on odd
            confidence = min(0.8, 0.5 + bias_strength)
            return StrategySignal("ODD", confidence, 0.0, f"Mean reversion: even_freq={even_freq:.3f}")
    
    def _analyze_volatility(self, recent_ticks: List[Dict]) -> Dict:
        """Analyze price volatility - skip during high volatility"""
        if len(recent_ticks) < 5:
            return {"skip": False, "reason": "Insufficient data for volatility"}
        
        prices = [tick["quote"] for tick in recent_ticks]
        
        # Calculate rolling volatility (coefficient of variation)
        if len(prices) > 1:
            volatility = np.std(prices) / np.mean(prices) if np.mean(prices) > 0 else 0
        else:
            volatility = 0
        
        if volatility > self.volatility_threshold:
            return {"skip": True, "reason": f"High volatility: {volatility:.4f}"}
        
        return {"skip": False, "reason": f"Normal volatility: {volatility:.4f}"}
    
    def _analyze_time_patterns(self) -> Dict:
        """Analyze time-based patterns (placeholder for future enhancement)"""
        # For now, just check if we're in a reasonable trading window
        # Could be enhanced with time-of-day analysis
        
        return {"skip": False, "reason": "Time filter passed"}
    
    def _combine_signals(self, freq_signal: StrategySignal, vol_signal: Dict, time_signal: Dict) -> StrategySignal:
        """Combine multiple signal sources with conservative approach"""
        
        # Skip if any filter says skip
        if vol_signal["skip"]:
            return StrategySignal("SKIP", 0.0, 0.0, vol_signal["reason"])
        
        if time_signal["skip"]:
            return StrategySignal("SKIP", 0.0, 0.0, time_signal["reason"])
        
        if freq_signal.side == "SKIP":
            return freq_signal
        
        # Reduce confidence based on uncertainty
        combined_confidence = freq_signal.confidence * 0.9  # Conservative reduction
        
        reason = f"{freq_signal.reason} | {vol_signal['reason']}"
        
        return StrategySignal(
            freq_signal.side,
            combined_confidence,
            0.0,  # Position size calculated separately
            reason
        )
    
    def _calculate_position_size(self, confidence: float, balance: float) -> float:
        """
        Calculate position size based on confidence and Kelly-like criteria
        Very conservative approach
        """
        # Base fraction from config (max 2%)
        base_fraction = 0.01  # Start with 1% base
        
        # Scale by confidence, but cap at 2%
        confidence_multiplier = min(2.0, confidence / 0.5)  # Scale from 50% confidence
        position_fraction = base_fraction * confidence_multiplier
        
        # Hard cap at 2%
        position_fraction = min(position_fraction, 0.02)
        
        return position_fraction
    
    def update_trade_result(self, side: str, stake: float, profit: float):
        """Update strategy with trade result for learning"""
        self.last_trade_time = time.time()
        
        win = profit > 0
        self.logger.info(f"Trade result: {side} ${stake:.2f} -> {'WIN' if win else 'LOSS'} ${profit:.2f}")
    
    def get_statistics(self) -> Dict:
        """Get current strategy statistics"""
        if self.total_ticks == 0:
            return {"total_ticks": 0, "odd_frequency": 0.5, "even_frequency": 0.5}
        
        return {
            "total_ticks": self.total_ticks,
            "odd_frequency": self.odd_count / self.total_ticks,
            "even_frequency": self.even_count / self.total_ticks,
            "recent_window_size": len(self.tick_history),
            "lookback_window": self.lookback_window
        }


class PaperTradingStrategy(OddEvenStrategy):
    """Paper trading version for backtesting and validation"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.paper_trades = []
        self.paper_balance = 10.0  # Starting paper balance
        
    async def simulate_trade(self, signal: StrategySignal, payout_ratio: float) -> Dict:
        """Simulate a trade without real execution"""
        if signal.side == "SKIP":
            return {"executed": False, "reason": signal.reason}
        
        stake = signal.stake_fraction * self.paper_balance
        
        # Simulate random outcome (50/50 for now)
        # In real implementation, this would use actual tick outcome
        import random
        win = random.random() < 0.5
        
        if win:
            profit = stake * (payout_ratio - 1)
        else:
            profit = -stake
        
        self.paper_balance += profit
        
        trade_result = {
            "executed": True,
            "side": signal.side,
            "stake": stake,
            "profit": profit,
            "new_balance": self.paper_balance,
            "win": win,
            "timestamp": time.time()
        }
        
        self.paper_trades.append(trade_result)
        self.update_trade_result(signal.side, stake, profit)
        
        return trade_result
    
    def get_paper_performance(self) -> Dict:
        """Calculate paper trading performance metrics"""
        if not self.paper_trades:
            return {"trades": 0, "win_rate": 0, "total_pnl": 0, "roi": 0}
        
        wins = sum(1 for trade in self.paper_trades if trade["win"])
        total_trades = len(self.paper_trades)
        win_rate = wins / total_trades
        
        total_pnl = sum(trade["profit"] for trade in self.paper_trades)
        roi = (self.paper_balance - 10.0) / 10.0  # ROI from starting $10
        
        return {
            "trades": total_trades,
            "wins": wins,
            "losses": total_trades - wins,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "roi": roi,
            "final_balance": self.paper_balance,
            "expected_value": self._estimate_expected_value()
        }
    
    def _estimate_expected_value(self) -> float:
        """Estimate expected value from paper trading results"""
        if len(self.paper_trades) < 10:
            return 0.0
        
        # Calculate average profit per trade
        profits = [trade["profit"] for trade in self.paper_trades]
        avg_profit = np.mean(profits)
        
        # Normalize by average stake
        stakes = [trade["stake"] for trade in self.paper_trades]
        avg_stake = np.mean(stakes)
        
        if avg_stake > 0:
            return avg_profit / avg_stake
        return 0.0
    
    def has_statistical_edge(self, min_trades: int = 100, confidence_level: float = 0.95) -> tuple[bool, Dict]:
        """
        Determine if strategy has statistically significant edge
        
        Returns:
            (has_edge, statistics_dict)
        """
        if len(self.paper_trades) < min_trades:
            return False, {"reason": f"Insufficient trades: {len(self.paper_trades)}/{min_trades}"}
        
        # Calculate win rate and confidence interval
        wins = sum(1 for trade in self.paper_trades if trade["win"])
        total = len(self.paper_trades)
        win_rate = wins / total
        
        # Binomial confidence interval
        z_score = 1.96 if confidence_level == 0.95 else 2.576  # 95% or 99%
        margin_error = z_score * np.sqrt((win_rate * (1 - win_rate)) / total)
        
        ci_lower = win_rate - margin_error
        ci_upper = win_rate + margin_error
        
        # Calculate expected value with confidence interval
        ev_estimate = self._estimate_expected_value()
        
        # Conservative edge detection
        has_edge = (
            ci_lower > 0.51 and  # Lower bound > 51%
            ev_estimate > 0.01   # Expected value > 1%
        )
        
        stats = {
            "total_trades": total,
            "win_rate": win_rate,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "expected_value": ev_estimate,
            "confidence_level": confidence_level,
            "has_edge": has_edge,
            "reason": "Statistical edge detected" if has_edge else "No significant edge"
        }
        
        return has_edge, stats


def create_strategy(config: Dict, paper_mode: bool = True) -> OddEvenStrategy:
    """Factory function to create strategy instance"""
    if paper_mode:
        return PaperTradingStrategy(config)
    else:
        return OddEvenStrategy(config)
