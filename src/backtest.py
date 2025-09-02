"""
Backtesting Engine for Odd/Even Strategy
Statistical validation with confidence intervals
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from scipy import stats
import time
import random


class BacktestEngine:
    """Backtest odd/even strategy with statistical validation"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Backtest parameters
        backtest_config = config.get("backtest", {})
        self.min_samples = backtest_config.get("min_samples", 1000)
        self.confidence_level = backtest_config.get("confidence_level", 0.95)
        self.min_edge_threshold = backtest_config.get("min_edge_threshold", 0.01)
        
        # Results storage
        self.backtest_results = []
        self.synthetic_ticks = []
    
    def generate_synthetic_ticks(self, count: int, symbol: str = "R_50") -> List[Dict]:
        """
        Generate synthetic tick data for backtesting
        Uses realistic price movements and digit distribution
        """
        self.logger.info(f"Generating {count} synthetic ticks for backtesting")
        
        ticks = []
        base_price = 100.0
        
        for i in range(count):
            # Random walk with small steps
            price_change = random.gauss(0, 0.001)  # Small volatility
            base_price += price_change
            base_price = max(base_price, 50.0)  # Floor price
            
            # Generate realistic decimal places (5 digits after decimal)
            price = round(base_price + random.gauss(0, 0.01), 5)
            
            # Extract last digit
            price_str = f"{price:.5f}"
            last_digit = int(price_str[-1])
            
            tick = {
                "symbol": symbol,
                "quote": price,
                "epoch": int(time.time()) + i,
                "last_digit": last_digit,
                "is_odd": last_digit % 2 == 1,
                "timestamp": time.time() + i
            }
            
            ticks.append(tick)
        
        self.synthetic_ticks = ticks
        return ticks
    
    def run_backtest(self, strategy, payout_ratio: float = 1.9, starting_balance: float = 10.0) -> Dict:
        """
        Run comprehensive backtest with statistical analysis
        
        Args:
            strategy: Strategy instance to test
            payout_ratio: Payout ratio for winning trades
            starting_balance: Starting balance for simulation
            
        Returns:
            Backtest results with statistical metrics
        """
        self.logger.info("Starting backtest simulation")
        
        # Generate synthetic data if needed
        if not self.synthetic_ticks:
            self.generate_synthetic_ticks(self.min_samples)
        
        # Initialize simulation
        balance = starting_balance
        trades = []
        equity_curve = [balance]
        
        # Process each tick
        for i, tick in enumerate(self.synthetic_ticks):
            strategy.add_tick(tick)
            
            # Skip initial period for strategy warmup
            if i < strategy.lookback_window:
                continue
            
            # Get strategy signal
            signal = strategy.analyze_signal(balance, payout_ratio)
            
            if signal.side != "SKIP":
                # Calculate stake
                stake = signal.stake_fraction * balance
                stake = min(stake, balance * 0.02)  # Risk limit
                stake = max(stake, 0.01)  # Minimum stake
                
                if stake > balance:
                    continue  # Skip if insufficient balance
                
                # Simulate trade outcome using actual tick
                next_tick_idx = i + 1
                if next_tick_idx < len(self.synthetic_ticks):
                    outcome_tick = self.synthetic_ticks[next_tick_idx]
                    actual_outcome = "ODD" if outcome_tick["is_odd"] else "EVEN"
                    
                    win = (signal.side == actual_outcome)
                    
                    if win:
                        profit = stake * (payout_ratio - 1)
                    else:
                        profit = -stake
                    
                    balance += profit
                    
                    trade = {
                        "tick_index": i,
                        "side": signal.side,
                        "stake": stake,
                        "actual_outcome": actual_outcome,
                        "win": win,
                        "profit": profit,
                        "balance": balance,
                        "confidence": signal.confidence,
                        "reason": signal.reason
                    }
                    
                    trades.append(trade)
                    equity_curve.append(balance)
        
        # Calculate performance metrics
        results = self._calculate_metrics(trades, equity_curve, starting_balance, payout_ratio)
        
        self.backtest_results = results
        self.logger.info(f"Backtest completed: {len(trades)} trades, Final balance: ${balance:.2f}")
        
        return results
    
    def _calculate_metrics(self, trades: List[Dict], equity_curve: List[float], 
                          starting_balance: float, payout_ratio: float) -> Dict:
        """Calculate comprehensive performance metrics"""
        
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "expected_value": payout_ratio - 1.0,  # Assume house edge
                "has_edge": False,
                "confidence_interval": (0, 0),
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "final_balance": starting_balance,
                "roi": 0
            }
        
        # Basic metrics
        total_trades = len(trades)
        wins = sum(1 for trade in trades if trade["win"])
        win_rate = wins / total_trades
        
        # P&L metrics
        total_pnl = sum(trade["profit"] for trade in trades)
        final_balance = equity_curve[-1]
        roi = (final_balance - starting_balance) / starting_balance
        
        # Risk metrics
        returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
        sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
        
        # Maximum drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak
        max_drawdown = np.max(drawdown)
        
        # Statistical significance testing
        confidence_interval = self._calculate_confidence_interval(win_rate, total_trades)
        
        # Expected value calculation
        avg_win = np.mean([trade["profit"] for trade in trades if trade["win"]]) if wins > 0 else 0
        avg_loss = np.mean([trade["profit"] for trade in trades if not trade["win"]]) if (total_trades - wins) > 0 else 0
        expected_value = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        
        # Normalize expected value by average stake
        avg_stake = np.mean([trade["stake"] for trade in trades])
        normalized_ev = expected_value / avg_stake if avg_stake > 0 else 0
        
        # Edge detection
        has_edge = (
            confidence_interval[0] > 0.51 and  # Lower CI bound > 51%
            normalized_ev > self.min_edge_threshold  # Positive expected value
        )
        
        results = {
            "total_trades": total_trades,
            "wins": wins,
            "losses": total_trades - wins,
            "win_rate": win_rate,
            "confidence_interval": confidence_interval,
            "expected_value": normalized_ev,
            "total_pnl": total_pnl,
            "final_balance": final_balance,
            "roi": roi,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "avg_stake": avg_stake,
            "has_edge": has_edge,
            "edge_significance": confidence_interval[0] - 0.5,
            "trades_data": trades
        }
        
        return results
    
    def _calculate_confidence_interval(self, win_rate: float, sample_size: int, 
                                     confidence_level: float = None) -> tuple[float, float]:
        """Calculate binomial confidence interval for win rate"""
        if confidence_level is None:
            confidence_level = self.confidence_level
        
        if sample_size < 10:
            return (0.0, 1.0)  # Wide interval for small samples
        
        # Wilson score interval (more accurate for proportions)
        z = stats.norm.ppf((1 + confidence_level) / 2)
        n = sample_size
        p = win_rate
        
        denominator = 1 + z**2 / n
        center = (p + z**2 / (2*n)) / denominator
        margin = z * np.sqrt((p*(1-p) + z**2/(4*n)) / n) / denominator
        
        ci_lower = max(0, center - margin)
        ci_upper = min(1, center + margin)
        
        return (ci_lower, ci_upper)
    
    def validate_strategy_edge(self, strategy) -> tuple[bool, Dict]:
        """
        Validate if strategy has statistically significant edge
        
        Returns:
            (has_edge, validation_results)
        """
        self.logger.info("Validating strategy edge through backtesting")
        
        # Run backtest with current market conditions
        # In real implementation, would use recent tick data
        payout_ratio = 1.9  # Typical odd/even payout
        
        results = self.run_backtest(strategy, payout_ratio)
        
        # Strict validation criteria
        has_edge = (
            results["total_trades"] >= self.min_samples and
            results["has_edge"] and
            results["expected_value"] > self.min_edge_threshold and
            results["confidence_interval"][0] > 0.51
        )
        
        validation = {
            "validated": has_edge,
            "total_trades": results["total_trades"],
            "win_rate": results["win_rate"],
            "confidence_interval": results["confidence_interval"],
            "expected_value": results["expected_value"],
            "min_samples_met": results["total_trades"] >= self.min_samples,
            "statistical_significance": results["confidence_interval"][0] > 0.51,
            "positive_ev": results["expected_value"] > self.min_edge_threshold,
            "recommendation": "LIVE_DEMO" if has_edge else "PAPER_ONLY"
        }
        
        if has_edge:
            self.logger.info("✅ Strategy validation PASSED - Edge detected")
        else:
            self.logger.warning("❌ Strategy validation FAILED - No significant edge")
        
        return has_edge, validation
    
    def export_results(self, filepath: str):
        """Export backtest results to CSV"""
        if not self.backtest_results:
            self.logger.warning("No backtest results to export")
            return
        
        try:
            trades_df = pd.DataFrame(self.backtest_results.get("trades_data", []))
            trades_df.to_csv(filepath, index=False)
            self.logger.info(f"Backtest results exported to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Export failed: {e}")


def create_backtest_engine(config: Dict) -> BacktestEngine:
    """Factory function to create backtest engine"""
    return BacktestEngine(config)
