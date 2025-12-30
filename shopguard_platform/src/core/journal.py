"""
THE MEMORY - Trade Journal & Performance Analytics
===================================================
Records all trades and learns from history.

Features:
- Complete trade logging
- Performance metrics (Sharpe, Sortino, Calmar)
- Pattern recognition
- Equity curve tracking
- Drawdown analysis
- Win/loss streaks
- Trade attribution
"""

import time
import json
import math
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from enum import Enum
from collections import deque
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class TradeOutcome(Enum):
    """Trade result classification"""
    BIG_WIN = "big_win"        # > 2R profit
    WIN = "win"                # > 0 profit
    SCRATCH = "scratch"        # Break-even (-0.5R to 0.5R)
    LOSS = "loss"              # < 0 loss
    BIG_LOSS = "big_loss"      # > 2R loss
    STOPPED_OUT = "stopped"    # Hit stop loss


@dataclass
class TradeRecord:
    """Complete trade record"""
    # Identification
    trade_id: str
    asset: str
    strategy: str = "titan"

    # Entry
    entry_time: float = 0.0
    entry_price: float = 0.0
    entry_signal: str = ""
    entry_confidence: float = 0.0
    entry_regime: str = ""

    # Position
    side: str = "LONG"  # LONG or SHORT
    size: float = 0.0
    risk_amount: float = 0.0  # $ at risk

    # Exit
    exit_time: float = 0.0
    exit_price: float = 0.0
    exit_reason: str = ""

    # Results
    pnl: float = 0.0
    pnl_pct: float = 0.0
    r_multiple: float = 0.0  # P&L / Risk
    outcome: TradeOutcome = TradeOutcome.SCRATCH

    # Context
    market_phase: str = ""
    volatility_at_entry: float = 0.0
    pillars_aligned: int = 0

    # Duration
    hold_time_seconds: float = 0.0

    # Fees
    entry_fee: float = 0.0
    exit_fee: float = 0.0
    total_fees: float = 0.0

    # Slippage
    entry_slippage: float = 0.0
    exit_slippage: float = 0.0

    # Notes
    notes: str = ""

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['outcome'] = self.outcome.value
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeRecord':
        data['outcome'] = TradeOutcome(data.get('outcome', 'scratch'))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    # Returns
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Win/Loss
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # Profit
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    # Expectancy
    expectancy: float = 0.0  # Average $ per trade
    expectancy_r: float = 0.0  # Average R per trade

    # Drawdown
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # Days

    # Streaks
    max_win_streak: int = 0
    max_loss_streak: int = 0
    current_streak: int = 0
    current_streak_type: str = "none"

    # Time
    avg_hold_time: float = 0.0
    avg_winner_hold_time: float = 0.0
    avg_loser_hold_time: float = 0.0

    # Efficiency
    ulcer_index: float = 0.0
    recovery_factor: float = 0.0


class TradeJournal:
    """
    THE MEMORY
    ==========
    Complete trade logging and performance analytics.

    Learns from history:
    - Which regimes are most profitable
    - Optimal position sizing
    - Best entry/exit patterns
    - Time-of-day effects
    """

    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # Trade storage
        self.trades: List[TradeRecord] = []
        self.open_trades: Dict[str, TradeRecord] = {}

        # Equity curve
        self.equity_curve: List[Dict] = [{'time': time.time(), 'equity': initial_capital}]
        self.peak_equity = initial_capital
        self.drawdowns: List[float] = []

        # Performance cache
        self._metrics_cache: Optional[PerformanceMetrics] = None
        self._cache_valid = False

        # Streak tracking
        self.current_streak = 0
        self.current_streak_type = "none"
        self.max_win_streak = 0
        self.max_loss_streak = 0

        # Pattern tracking
        self.regime_performance: Dict[str, List[float]] = {}
        self.signal_performance: Dict[str, List[float]] = {}
        self.time_performance: Dict[int, List[float]] = {}  # Hour -> returns

        logger.info("📝 Trade Journal (Memory) initialized")

    def open_trade(
        self,
        trade_id: str,
        asset: str,
        side: str,
        entry_price: float,
        size: float,
        stop_loss: float,
        entry_signal: str = "",
        entry_confidence: float = 0.0,
        entry_regime: str = "",
        market_phase: str = "",
        volatility: float = 0.0,
        pillars_aligned: int = 0
    ) -> TradeRecord:
        """Record a new trade entry"""
        risk_amount = abs(entry_price - stop_loss) * size

        trade = TradeRecord(
            trade_id=trade_id,
            asset=asset,
            side=side,
            entry_time=time.time(),
            entry_price=entry_price,
            size=size,
            risk_amount=risk_amount,
            entry_signal=entry_signal,
            entry_confidence=entry_confidence,
            entry_regime=entry_regime,
            market_phase=market_phase,
            volatility_at_entry=volatility,
            pillars_aligned=pillars_aligned
        )

        self.open_trades[trade_id] = trade
        self._cache_valid = False

        logger.info(f"📝 Trade opened: {trade_id} {side} {size} {asset} @ ${entry_price:.2f}")

        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str = "",
        exit_fee: float = 0.0,
        exit_slippage: float = 0.0
    ) -> Optional[TradeRecord]:
        """Record trade exit and calculate results"""
        if trade_id not in self.open_trades:
            logger.warning(f"📝 Trade not found: {trade_id}")
            return None

        trade = self.open_trades[trade_id]

        # Calculate P&L
        if trade.side == "LONG":
            pnl = (exit_price - trade.entry_price) * trade.size
        else:
            pnl = (trade.entry_price - exit_price) * trade.size

        pnl_pct = pnl / (trade.entry_price * trade.size)

        # Calculate R-multiple
        r_multiple = pnl / trade.risk_amount if trade.risk_amount > 0 else 0

        # Determine outcome
        if r_multiple > 2:
            outcome = TradeOutcome.BIG_WIN
        elif r_multiple > 0.1:
            outcome = TradeOutcome.WIN
        elif r_multiple > -0.5:
            outcome = TradeOutcome.SCRATCH
        elif r_multiple > -2:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BIG_LOSS

        if exit_reason == "STOP_LOSS":
            outcome = TradeOutcome.STOPPED_OUT

        # Update trade record
        trade.exit_time = time.time()
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.pnl = pnl
        trade.pnl_pct = pnl_pct
        trade.r_multiple = r_multiple
        trade.outcome = outcome
        trade.hold_time_seconds = trade.exit_time - trade.entry_time
        trade.exit_fee = exit_fee
        trade.exit_slippage = exit_slippage
        trade.total_fees = trade.entry_fee + exit_fee

        # Update capital and equity curve
        self.current_capital += pnl
        self._update_equity_curve()

        # Update streak tracking
        self._update_streaks(pnl > 0)

        # Track performance by regime/signal
        self._track_pattern_performance(trade)

        # Move to closed trades
        self.trades.append(trade)
        del self.open_trades[trade_id]

        self._cache_valid = False

        logger.info(
            f"📝 Trade closed: {trade_id} | "
            f"P&L: ${pnl:.2f} ({pnl_pct*100:.2f}%) | "
            f"R: {r_multiple:.2f} | {outcome.value}"
        )

        return trade

    def _update_equity_curve(self):
        """Update equity curve and drawdown tracking"""
        current_equity = self.current_capital

        self.equity_curve.append({
            'time': time.time(),
            'equity': current_equity
        })

        # Update peak and drawdown
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        else:
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
            self.drawdowns.append(drawdown)

    def _update_streaks(self, is_win: bool):
        """Update win/loss streak tracking"""
        if is_win:
            if self.current_streak_type == "win":
                self.current_streak += 1
            else:
                self.current_streak = 1
                self.current_streak_type = "win"

            self.max_win_streak = max(self.max_win_streak, self.current_streak)
        else:
            if self.current_streak_type == "loss":
                self.current_streak += 1
            else:
                self.current_streak = 1
                self.current_streak_type = "loss"

            self.max_loss_streak = max(self.max_loss_streak, self.current_streak)

    def _track_pattern_performance(self, trade: TradeRecord):
        """Track performance by various patterns"""
        # By regime
        if trade.entry_regime:
            if trade.entry_regime not in self.regime_performance:
                self.regime_performance[trade.entry_regime] = []
            self.regime_performance[trade.entry_regime].append(trade.r_multiple)

        # By signal type
        if trade.entry_signal:
            if trade.entry_signal not in self.signal_performance:
                self.signal_performance[trade.entry_signal] = []
            self.signal_performance[trade.entry_signal].append(trade.r_multiple)

        # By hour
        entry_hour = datetime.fromtimestamp(trade.entry_time).hour
        if entry_hour not in self.time_performance:
            self.time_performance[entry_hour] = []
        self.time_performance[entry_hour].append(trade.r_multiple)

    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics"""
        if self._cache_valid and self._metrics_cache:
            return self._metrics_cache

        metrics = PerformanceMetrics()

        if not self.trades:
            return metrics

        # Basic counts
        metrics.total_trades = len(self.trades)
        pnls = [t.pnl for t in self.trades]
        r_multiples = [t.r_multiple for t in self.trades]

        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        metrics.winning_trades = len(winners)
        metrics.losing_trades = len(losers)
        metrics.win_rate = len(winners) / len(pnls) if pnls else 0

        # Profit metrics
        metrics.gross_profit = sum(winners)
        metrics.gross_loss = abs(sum(losers))
        metrics.total_return = sum(pnls)
        metrics.total_return_pct = metrics.total_return / self.initial_capital

        metrics.profit_factor = metrics.gross_profit / metrics.gross_loss if metrics.gross_loss > 0 else float('inf')

        metrics.avg_win = np.mean(winners) if winners else 0
        metrics.avg_loss = np.mean(losers) if losers else 0
        metrics.avg_trade = np.mean(pnls)

        metrics.largest_win = max(winners) if winners else 0
        metrics.largest_loss = min(losers) if losers else 0

        # Expectancy
        metrics.expectancy = metrics.avg_trade
        metrics.expectancy_r = np.mean(r_multiples) if r_multiples else 0

        # Drawdown
        if self.drawdowns:
            metrics.max_drawdown_pct = max(self.drawdowns)
            metrics.max_drawdown = metrics.max_drawdown_pct * self.peak_equity
            metrics.avg_drawdown = np.mean(self.drawdowns)

        # Risk-adjusted returns
        if len(pnls) > 1:
            returns = np.array(pnls) / self.initial_capital
            std_returns = np.std(returns)
            downside_returns = returns[returns < 0]
            std_downside = np.std(downside_returns) if len(downside_returns) > 0 else 0.001

            # Sharpe (assuming 0 risk-free rate)
            metrics.sharpe_ratio = (np.mean(returns) / std_returns * np.sqrt(252)) if std_returns > 0 else 0

            # Sortino
            metrics.sortino_ratio = (np.mean(returns) / std_downside * np.sqrt(252)) if std_downside > 0 else 0

            # Calmar
            metrics.calmar_ratio = (metrics.total_return_pct / metrics.max_drawdown_pct) if metrics.max_drawdown_pct > 0 else 0

        # Streaks
        metrics.max_win_streak = self.max_win_streak
        metrics.max_loss_streak = self.max_loss_streak
        metrics.current_streak = self.current_streak
        metrics.current_streak_type = self.current_streak_type

        # Hold times
        hold_times = [t.hold_time_seconds for t in self.trades]
        winner_hold_times = [t.hold_time_seconds for t in self.trades if t.pnl > 0]
        loser_hold_times = [t.hold_time_seconds for t in self.trades if t.pnl < 0]

        metrics.avg_hold_time = np.mean(hold_times) if hold_times else 0
        metrics.avg_winner_hold_time = np.mean(winner_hold_times) if winner_hold_times else 0
        metrics.avg_loser_hold_time = np.mean(loser_hold_times) if loser_hold_times else 0

        # Recovery factor
        metrics.recovery_factor = metrics.total_return / metrics.max_drawdown if metrics.max_drawdown > 0 else 0

        # Cache results
        self._metrics_cache = metrics
        self._cache_valid = True

        return metrics

    def get_best_regime(self) -> Tuple[str, float]:
        """Find the most profitable regime"""
        if not self.regime_performance:
            return "unknown", 0

        best_regime = max(self.regime_performance.keys(),
                         key=lambda k: np.mean(self.regime_performance[k]))
        return best_regime, np.mean(self.regime_performance[best_regime])

    def get_best_signal(self) -> Tuple[str, float]:
        """Find the most profitable signal type"""
        if not self.signal_performance:
            return "unknown", 0

        best_signal = max(self.signal_performance.keys(),
                         key=lambda k: np.mean(self.signal_performance[k]))
        return best_signal, np.mean(self.signal_performance[best_signal])

    def get_best_hours(self, top_n: int = 3) -> List[Tuple[int, float]]:
        """Find the most profitable trading hours"""
        if not self.time_performance:
            return []

        sorted_hours = sorted(
            self.time_performance.items(),
            key=lambda x: np.mean(x[1]),
            reverse=True
        )
        return [(h, np.mean(r)) for h, r in sorted_hours[:top_n]]

    def get_recent_trades(self, n: int = 10) -> List[TradeRecord]:
        """Get last N trades"""
        return self.trades[-n:]

    def get_trades_by_outcome(self, outcome: TradeOutcome) -> List[TradeRecord]:
        """Filter trades by outcome"""
        return [t for t in self.trades if t.outcome == outcome]

    def export_trades(self, filepath: str):
        """Export all trades to JSON"""
        data = {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'trades': [t.to_dict() for t in self.trades],
            'metrics': asdict(self.calculate_metrics())
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"📝 Exported {len(self.trades)} trades to {filepath}")

    def get_stats(self) -> Dict:
        """Get journal statistics"""
        metrics = self.calculate_metrics()

        return {
            'capital': {
                'initial': self.initial_capital,
                'current': self.current_capital,
                'peak': self.peak_equity,
                'total_return': metrics.total_return,
                'total_return_pct': metrics.total_return_pct
            },
            'performance': {
                'total_trades': metrics.total_trades,
                'win_rate': metrics.win_rate,
                'profit_factor': metrics.profit_factor,
                'expectancy': metrics.expectancy,
                'expectancy_r': metrics.expectancy_r
            },
            'risk': {
                'sharpe_ratio': metrics.sharpe_ratio,
                'sortino_ratio': metrics.sortino_ratio,
                'max_drawdown_pct': metrics.max_drawdown_pct,
                'calmar_ratio': metrics.calmar_ratio
            },
            'streaks': {
                'current': metrics.current_streak,
                'type': metrics.current_streak_type,
                'max_win': metrics.max_win_streak,
                'max_loss': metrics.max_loss_streak
            },
            'patterns': {
                'best_regime': self.get_best_regime(),
                'best_signal': self.get_best_signal(),
                'best_hours': self.get_best_hours()
            }
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test journal
    journal = TradeJournal(initial_capital=10000)

    # Simulate some trades
    import random

    for i in range(20):
        trade_id = f"trade_{i}"
        entry_price = 100 + random.uniform(-5, 5)
        stop_loss = entry_price * 0.95
        exit_price = entry_price * (1 + random.uniform(-0.03, 0.05))

        trade = journal.open_trade(
            trade_id=trade_id,
            asset="BTC/USDT",
            side="LONG",
            entry_price=entry_price,
            size=1.0,
            stop_loss=stop_loss,
            entry_signal="STRONG_BUY" if random.random() > 0.5 else "BUY",
            entry_regime="trending_up" if random.random() > 0.3 else "ranging",
            pillars_aligned=random.randint(2, 4)
        )

        journal.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            exit_reason="TAKE_PROFIT" if exit_price > entry_price else "STOP_LOSS"
        )

    # Print stats
    print("\n" + "="*60)
    print("TRADE JOURNAL SUMMARY")
    print("="*60)

    stats = journal.get_stats()
    print(f"\nCapital: ${stats['capital']['current']:.2f} ({stats['capital']['total_return_pct']*100:.2f}%)")
    print(f"Win Rate: {stats['performance']['win_rate']*100:.1f}%")
    print(f"Profit Factor: {stats['performance']['profit_factor']:.2f}")
    print(f"Sharpe Ratio: {stats['risk']['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {stats['risk']['max_drawdown_pct']*100:.2f}%")
    print(f"\nBest Regime: {stats['patterns']['best_regime']}")
    print(f"Best Signal: {stats['patterns']['best_signal']}")
