"""
Backtest Metrics

Performance metrics for strategy evaluation:
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Win Rate
- Profit Factor
- Expectancy
"""
from dataclasses import dataclass
from typing import List, Optional
import math
import statistics
import logging

from ..config.constants import MIN_BACKTEST_TRADES, MIN_SHARPE_RATIO, MIN_WIN_RATE

logger = logging.getLogger(__name__)


@dataclass
class BacktestMetrics:
    """
    Complete backtest performance metrics.

    All the numbers that matter for validating a strategy.
    """
    # Basic stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    # P&L
    total_pnl: float
    total_pnl_pct: float
    avg_trade_pnl: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float  # gross_profit / gross_loss

    # Risk metrics
    max_drawdown: float
    max_drawdown_pct: float
    avg_drawdown: float
    drawdown_duration_max: int  # candles
    ulcer_index: float  # Measures drawdown severity

    # Risk-adjusted returns
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float  # Annual return / Max drawdown

    # Expectancy
    expectancy: float  # Expected $ per trade
    expectancy_ratio: float  # Expected R per trade

    # Time metrics
    avg_trade_duration: float  # candles
    time_in_market_pct: float

    # Equity curve
    final_equity: float
    peak_equity: float
    cagr: float  # Compound annual growth rate

    def to_dict(self) -> dict:
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 4),
            'total_pnl': round(self.total_pnl, 2),
            'total_pnl_pct': round(self.total_pnl_pct, 4),
            'avg_trade_pnl': round(self.avg_trade_pnl, 2),
            'avg_win': round(self.avg_win, 2),
            'avg_loss': round(self.avg_loss, 2),
            'largest_win': round(self.largest_win, 2),
            'largest_loss': round(self.largest_loss, 2),
            'profit_factor': round(self.profit_factor, 2),
            'max_drawdown': round(self.max_drawdown, 2),
            'max_drawdown_pct': round(self.max_drawdown_pct, 4),
            'sharpe_ratio': round(self.sharpe_ratio, 2),
            'sortino_ratio': round(self.sortino_ratio, 2),
            'calmar_ratio': round(self.calmar_ratio, 2),
            'expectancy': round(self.expectancy, 2),
            'expectancy_ratio': round(self.expectancy_ratio, 3),
            'final_equity': round(self.final_equity, 2),
            'cagr': round(self.cagr, 4),
        }

    def passes_minimum(self) -> tuple[bool, List[str]]:
        """
        Check if metrics pass minimum thresholds.

        Returns:
            (passes: bool, reasons: List[str])
        """
        failures = []

        if self.total_trades < MIN_BACKTEST_TRADES:
            failures.append(f"Insufficient trades: {self.total_trades} < {MIN_BACKTEST_TRADES}")

        if self.sharpe_ratio < MIN_SHARPE_RATIO:
            failures.append(f"Sharpe too low: {self.sharpe_ratio:.2f} < {MIN_SHARPE_RATIO}")

        if self.win_rate < MIN_WIN_RATE:
            failures.append(f"Win rate too low: {self.win_rate:.1%} < {MIN_WIN_RATE:.1%}")

        if self.profit_factor < 1.0:
            failures.append(f"Profit factor < 1: {self.profit_factor:.2f}")

        if self.max_drawdown_pct > 0.25:
            failures.append(f"Max drawdown too high: {self.max_drawdown_pct:.1%}")

        return len(failures) == 0, failures

    def summary(self) -> str:
        """Generate human-readable summary."""
        passes, failures = self.passes_minimum()
        status = "PASS" if passes else "FAIL"

        lines = [
            "=" * 60,
            f"BACKTEST RESULTS: {status}",
            "=" * 60,
            "",
            "TRADES:",
            f"  Total: {self.total_trades}",
            f"  Win Rate: {self.win_rate:.1%} ({self.winning_trades}W / {self.losing_trades}L)",
            f"  Avg Win: ${self.avg_win:.2f}",
            f"  Avg Loss: ${self.avg_loss:.2f}",
            "",
            "RETURNS:",
            f"  Total P&L: ${self.total_pnl:.2f} ({self.total_pnl_pct:.1%})",
            f"  CAGR: {self.cagr:.1%}",
            f"  Profit Factor: {self.profit_factor:.2f}",
            f"  Expectancy: ${self.expectancy:.2f} per trade",
            "",
            "RISK:",
            f"  Max Drawdown: ${self.max_drawdown:.2f} ({self.max_drawdown_pct:.1%})",
            f"  Sharpe Ratio: {self.sharpe_ratio:.2f}",
            f"  Sortino Ratio: {self.sortino_ratio:.2f}",
            f"  Calmar Ratio: {self.calmar_ratio:.2f}",
            "",
            "EQUITY:",
            f"  Final: ${self.final_equity:.2f}",
            f"  Peak: ${self.peak_equity:.2f}",
            "",
        ]

        if not passes:
            lines.extend([
                "FAILURES:",
                *[f"  - {f}" for f in failures],
                ""
            ])

        lines.append("=" * 60)

        return "\n".join(lines)


@dataclass
class TradeResult:
    """Result of a single trade."""
    entry_price: float
    exit_price: float
    size: float
    direction: str  # 'long' or 'short'
    pnl: float
    pnl_pct: float
    duration: int  # candles
    entry_time: int  # timestamp
    exit_time: int


def calculate_metrics(
    trades: List[TradeResult],
    initial_capital: float,
    risk_free_rate: float = 0.02,  # 2% annual
    periods_per_year: int = 252 * 24  # Hourly candles
) -> BacktestMetrics:
    """
    Calculate all backtest metrics from trade results.

    Args:
        trades: List of completed trades
        initial_capital: Starting capital
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        BacktestMetrics with all calculations
    """
    if not trades:
        return _empty_metrics(initial_capital)

    # Basic counts
    total_trades = len(trades)
    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]
    winning_trades = len(winners)
    losing_trades = len(losers)
    win_rate = winning_trades / total_trades

    # P&L calculations
    pnls = [t.pnl for t in trades]
    total_pnl = sum(pnls)
    total_pnl_pct = total_pnl / initial_capital
    avg_trade_pnl = statistics.mean(pnls)

    avg_win = statistics.mean([t.pnl for t in winners]) if winners else 0
    avg_loss = statistics.mean([t.pnl for t in losers]) if losers else 0
    largest_win = max([t.pnl for t in winners]) if winners else 0
    largest_loss = min([t.pnl for t in losers]) if losers else 0

    # Profit factor
    gross_profit = sum(t.pnl for t in winners) if winners else 0
    gross_loss = abs(sum(t.pnl for t in losers)) if losers else 0.01
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    # Equity curve and drawdown
    equity_curve = [initial_capital]
    for trade in trades:
        equity_curve.append(equity_curve[-1] + trade.pnl)

    peak_equity = max(equity_curve)
    final_equity = equity_curve[-1]

    # Drawdown calculation
    drawdowns = []
    peak = initial_capital
    dd_start_idx = 0
    max_dd_duration = 0
    current_dd_duration = 0

    for i, equity in enumerate(equity_curve):
        if equity > peak:
            peak = equity
            dd_start_idx = i
            current_dd_duration = 0
        dd = peak - equity
        drawdowns.append(dd)
        if dd > 0:
            current_dd_duration = i - dd_start_idx
            max_dd_duration = max(max_dd_duration, current_dd_duration)

    max_drawdown = max(drawdowns)
    max_drawdown_pct = max_drawdown / peak_equity if peak_equity > 0 else 0
    avg_drawdown = statistics.mean(drawdowns) if drawdowns else 0

    # Ulcer Index (RMS of drawdowns)
    ulcer_index = (sum(dd**2 for dd in drawdowns) / len(drawdowns)) ** 0.5 if drawdowns else 0

    # Returns for Sharpe/Sortino calculation
    returns = [t.pnl_pct for t in trades]

    # Sharpe Ratio
    if len(returns) > 1:
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        period_rf = risk_free_rate / periods_per_year

        if std_return > 0:
            sharpe_ratio = (mean_return - period_rf) / std_return * math.sqrt(periods_per_year / len(trades))
        else:
            sharpe_ratio = 0
    else:
        sharpe_ratio = 0

    # Sortino Ratio (uses downside deviation)
    negative_returns = [r for r in returns if r < 0]
    if negative_returns and len(returns) > 1:
        downside_std = statistics.stdev(negative_returns) if len(negative_returns) > 1 else abs(negative_returns[0])
        if downside_std > 0:
            mean_return = statistics.mean(returns)
            sortino_ratio = mean_return / downside_std * math.sqrt(periods_per_year / len(trades))
        else:
            sortino_ratio = 0
    else:
        sortino_ratio = sharpe_ratio  # No losing trades = use Sharpe

    # Calmar Ratio
    if max_drawdown_pct > 0:
        # Approximate annual return
        annual_return = total_pnl_pct * (periods_per_year / len(trades))
        calmar_ratio = annual_return / max_drawdown_pct
    else:
        calmar_ratio = 0

    # Expectancy
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    # Expectancy ratio (in R multiples)
    # Assumes average loss is 1R
    if avg_loss != 0:
        expectancy_ratio = expectancy / abs(avg_loss)
    else:
        expectancy_ratio = 0

    # Time metrics
    durations = [t.duration for t in trades]
    avg_trade_duration = statistics.mean(durations) if durations else 0

    # Time in market (approximate)
    total_duration = sum(durations)
    total_period = trades[-1].exit_time - trades[0].entry_time if trades else 1
    time_in_market_pct = total_duration / (total_period / 60000) if total_period > 0 else 0  # Assume 1min candles

    # CAGR
    if total_trades > 0:
        # Approximate holding period in years
        holding_years = len(trades) / periods_per_year
        if holding_years > 0 and final_equity > 0:
            cagr = (final_equity / initial_capital) ** (1 / holding_years) - 1
        else:
            cagr = 0
    else:
        cagr = 0

    return BacktestMetrics(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        avg_trade_pnl=avg_trade_pnl,
        avg_win=avg_win,
        avg_loss=avg_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        avg_drawdown=avg_drawdown,
        drawdown_duration_max=max_dd_duration,
        ulcer_index=ulcer_index,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        expectancy=expectancy,
        expectancy_ratio=expectancy_ratio,
        avg_trade_duration=avg_trade_duration,
        time_in_market_pct=min(1.0, time_in_market_pct),
        final_equity=final_equity,
        peak_equity=peak_equity,
        cagr=cagr
    )


def _empty_metrics(initial_capital: float) -> BacktestMetrics:
    """Return empty metrics when no trades."""
    return BacktestMetrics(
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        win_rate=0,
        total_pnl=0,
        total_pnl_pct=0,
        avg_trade_pnl=0,
        avg_win=0,
        avg_loss=0,
        largest_win=0,
        largest_loss=0,
        profit_factor=0,
        max_drawdown=0,
        max_drawdown_pct=0,
        avg_drawdown=0,
        drawdown_duration_max=0,
        ulcer_index=0,
        sharpe_ratio=0,
        sortino_ratio=0,
        calmar_ratio=0,
        expectancy=0,
        expectancy_ratio=0,
        avg_trade_duration=0,
        time_in_market_pct=0,
        final_equity=initial_capital,
        peak_equity=initial_capital,
        cagr=0
    )
