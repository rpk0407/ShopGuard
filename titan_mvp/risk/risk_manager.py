"""
Risk Manager

Central risk management with:
1. Position sizing (ATR-based)
2. Drawdown controls
3. Daily/weekly loss limits
4. Consecutive loss tracking

This is "The Membrane" - the defense layer.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from enum import Enum
import logging

from ..config.constants import (
    MAX_DAILY_LOSS_PCT,
    MAX_WEEKLY_LOSS_PCT,
    MAX_DRAWDOWN_PCT,
    MAX_CONSECUTIVE_LOSSES,
    MAX_TRADES_PER_DAY,
    MIN_TIME_BETWEEN_TRADES,
)
from .atr_calculator import ATRCalculator
from .position_sizer import PositionSizer, PositionSize

logger = logging.getLogger(__name__)


class RiskStatus(Enum):
    """Risk manager status."""
    NORMAL = "normal"           # Trading allowed
    REDUCED = "reduced"         # Trading with reduced size
    HALTED = "halted"          # No trading
    COOLDOWN = "cooldown"      # Temporary pause


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_daily_loss_pct: float = MAX_DAILY_LOSS_PCT
    max_weekly_loss_pct: float = MAX_WEEKLY_LOSS_PCT
    max_drawdown_pct: float = MAX_DRAWDOWN_PCT
    max_consecutive_losses: int = MAX_CONSECUTIVE_LOSSES
    max_trades_per_day: int = MAX_TRADES_PER_DAY
    min_time_between_trades: int = MIN_TIME_BETWEEN_TRADES  # seconds


@dataclass
class RiskState:
    """Current risk state."""
    status: RiskStatus
    reason: str
    size_multiplier: float  # 1.0 = normal, 0.5 = reduced, 0 = halted

    # P&L tracking
    daily_pnl: float
    weekly_pnl: float
    peak_equity: float
    current_equity: float
    drawdown: float
    drawdown_pct: float

    # Trade tracking
    trades_today: int
    consecutive_losses: int
    last_trade_time: Optional[datetime]

    # Cooldown
    cooldown_until: Optional[datetime]

    def to_dict(self) -> dict:
        return {
            'status': self.status.value,
            'reason': self.reason,
            'size_multiplier': self.size_multiplier,
            'daily_pnl': round(self.daily_pnl, 2),
            'weekly_pnl': round(self.weekly_pnl, 2),
            'drawdown': round(self.drawdown, 2),
            'drawdown_pct': round(self.drawdown_pct, 4),
            'trades_today': self.trades_today,
            'consecutive_losses': self.consecutive_losses,
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
        }


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    trade_id: str
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    is_win: bool


class RiskManager:
    """
    Central risk management system.

    Responsibilities:
    1. Track P&L and drawdown
    2. Enforce loss limits
    3. Manage position sizing
    4. Handle cooldowns after losses

    Usage:
        risk = RiskManager(initial_capital=10000)

        # Before each trade:
        if risk.can_trade():
            size = risk.calculate_position(...)
            # Execute trade

        # After each trade:
        risk.record_trade(pnl=100)
    """

    def __init__(
        self,
        initial_capital: float,
        limits: Optional[RiskLimits] = None,
        atr_calculator: Optional[ATRCalculator] = None
    ):
        """
        Initialize risk manager.

        Args:
            initial_capital: Starting capital
            limits: Risk limit configuration
            atr_calculator: ATR calculator for position sizing
        """
        self.initial_capital = initial_capital
        self.limits = limits or RiskLimits()
        self.atr_calculator = atr_calculator or ATRCalculator()
        self.position_sizer = PositionSizer(account_size=initial_capital)

        # State
        self._current_equity = initial_capital
        self._peak_equity = initial_capital
        self._daily_pnl = 0.0
        self._weekly_pnl = 0.0

        # Tracking
        self._trades_today = 0
        self._consecutive_losses = 0
        self._consecutive_wins = 0
        self._last_trade_time: Optional[datetime] = None
        self._cooldown_until: Optional[datetime] = None

        # History
        self._trade_history: List[TradeRecord] = []
        self._daily_reset_date = datetime.now().date()
        self._weekly_reset_date = self._get_week_start()

        # Status
        self._status = RiskStatus.NORMAL
        self._status_reason = "System initialized"

        logger.info(
            "Risk Manager initialized: capital=$%.2f, max_dd=%.0f%%, max_daily=%.0f%%",
            initial_capital, self.limits.max_drawdown_pct * 100, self.limits.max_daily_loss_pct * 100
        )

    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed.

        Returns:
            (can_trade: bool, reason: str)
        """
        self._check_date_reset()
        self._update_status()

        if self._status == RiskStatus.HALTED:
            return False, self._status_reason

        if self._status == RiskStatus.COOLDOWN:
            if self._cooldown_until and datetime.now() < self._cooldown_until:
                remaining = (self._cooldown_until - datetime.now()).seconds
                return False, f"Cooldown: {remaining}s remaining"
            else:
                # Cooldown ended
                self._cooldown_until = None
                self._status = RiskStatus.NORMAL

        # Check trades per day limit
        if self._trades_today >= self.limits.max_trades_per_day:
            return False, f"Daily trade limit reached ({self.limits.max_trades_per_day})"

        # Check time between trades
        if self._last_trade_time:
            elapsed = (datetime.now() - self._last_trade_time).seconds
            if elapsed < self.limits.min_time_between_trades:
                remaining = self.limits.min_time_between_trades - elapsed
                return False, f"Min time between trades: {remaining}s remaining"

        return True, "Trading allowed"

    def calculate_position(
        self,
        entry_price: float,
        direction: str,
        confidence: float = 1.0
    ) -> Optional[PositionSize]:
        """
        Calculate position size with risk adjustments.

        Args:
            entry_price: Entry price
            direction: 'long' or 'short'
            confidence: Signal confidence (0-1)

        Returns:
            PositionSize or None if trading not allowed
        """
        can_trade, reason = self.can_trade()
        if not can_trade:
            logger.warning("Position calculation blocked: %s", reason)
            return None

        # Get current ATR
        atr_value = self.atr_calculator.get_atr_value()
        if atr_value is None:
            logger.warning("ATR not available - cannot calculate position")
            return None

        # Calculate base position
        size = self.position_sizer.calculate(
            entry_price=entry_price,
            atr=atr_value.atr,
            direction=direction,
            confidence_multiplier=confidence
        )

        # Apply status-based multiplier
        state = self.get_state()
        if state.size_multiplier < 1.0:
            size = PositionSize(
                size_usd=size.size_usd * state.size_multiplier,
                size_base=size.size_base * state.size_multiplier,
                risk_amount=size.risk_amount * state.size_multiplier,
                stop_distance=size.stop_distance,
                stop_price=size.stop_price,
                target_distance=size.target_distance,
                target_price=size.target_price,
                leverage_used=size.leverage_used * state.size_multiplier,
                is_constrained=True,
                constraint_reason=f"Risk status: {state.status.value}"
            )

        return size

    def record_trade(self, pnl: float, trade_id: str = "") -> None:
        """
        Record completed trade.

        Args:
            pnl: Profit/loss in USD
            trade_id: Trade identifier
        """
        now = datetime.now()

        # Update equity
        self._current_equity += pnl
        self.position_sizer.update_account_size(self._current_equity)

        # Update peak
        if self._current_equity > self._peak_equity:
            self._peak_equity = self._current_equity

        # Update P&L tracking
        self._daily_pnl += pnl
        self._weekly_pnl += pnl

        # Update trade counts
        self._trades_today += 1
        self._last_trade_time = now

        # Track wins/losses
        is_win = pnl > 0
        if is_win:
            self._consecutive_wins += 1
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1
            self._consecutive_wins = 0

            # Check for cooldown trigger
            if self._consecutive_losses >= self.limits.max_consecutive_losses:
                self._trigger_cooldown()

        # Record in history
        self._trade_history.append(TradeRecord(
            trade_id=trade_id or f"trade_{len(self._trade_history)}",
            entry_time=now - timedelta(minutes=5),  # Approximate
            exit_time=now,
            pnl=pnl,
            pnl_pct=pnl / (self._current_equity - pnl),
            is_win=is_win
        ))

        # Update status
        self._update_status()

        logger.info(
            "Trade recorded: PnL=$%.2f, Equity=$%.2f, DD=%.1f%%, Consec=%d",
            pnl, self._current_equity, self._get_drawdown_pct() * 100, self._consecutive_losses
        )

    def _update_status(self) -> None:
        """Update risk status based on current state."""
        drawdown_pct = self._get_drawdown_pct()
        daily_loss_pct = -self._daily_pnl / self.initial_capital if self._daily_pnl < 0 else 0
        weekly_loss_pct = -self._weekly_pnl / self.initial_capital if self._weekly_pnl < 0 else 0

        # Check halt conditions
        if drawdown_pct >= self.limits.max_drawdown_pct:
            self._status = RiskStatus.HALTED
            self._status_reason = f"Max drawdown exceeded: {drawdown_pct*100:.1f}%"
            return

        if daily_loss_pct >= self.limits.max_daily_loss_pct:
            self._status = RiskStatus.HALTED
            self._status_reason = f"Daily loss limit: {daily_loss_pct*100:.1f}%"
            return

        # Check reduced conditions
        if weekly_loss_pct >= self.limits.max_weekly_loss_pct * 0.8:  # 80% of limit
            self._status = RiskStatus.REDUCED
            self._status_reason = f"Approaching weekly limit: {weekly_loss_pct*100:.1f}%"
            return

        if drawdown_pct >= self.limits.max_drawdown_pct * 0.7:  # 70% of limit
            self._status = RiskStatus.REDUCED
            self._status_reason = f"Approaching drawdown limit: {drawdown_pct*100:.1f}%"
            return

        # Cooldown check (handled separately)
        if self._cooldown_until and datetime.now() < self._cooldown_until:
            self._status = RiskStatus.COOLDOWN
            self._status_reason = "Cooldown after consecutive losses"
            return

        # All clear
        self._status = RiskStatus.NORMAL
        self._status_reason = "Trading normally"

    def _trigger_cooldown(self) -> None:
        """Trigger cooldown period after consecutive losses."""
        cooldown_minutes = 60  # 1 hour cooldown
        self._cooldown_until = datetime.now() + timedelta(minutes=cooldown_minutes)
        self._status = RiskStatus.COOLDOWN
        self._status_reason = f"Cooldown: {self._consecutive_losses} consecutive losses"
        logger.warning(
            "COOLDOWN TRIGGERED: %d consecutive losses. Pausing until %s",
            self._consecutive_losses, self._cooldown_until
        )

    def _get_drawdown_pct(self) -> float:
        """Calculate current drawdown percentage."""
        if self._peak_equity == 0:
            return 0.0
        return (self._peak_equity - self._current_equity) / self._peak_equity

    def _check_date_reset(self) -> None:
        """Reset daily/weekly counters if needed."""
        today = datetime.now().date()
        week_start = self._get_week_start()

        # Daily reset
        if today != self._daily_reset_date:
            self._daily_pnl = 0.0
            self._trades_today = 0
            self._daily_reset_date = today
            logger.info("Daily counters reset")

        # Weekly reset
        if week_start != self._weekly_reset_date:
            self._weekly_pnl = 0.0
            self._weekly_reset_date = week_start
            logger.info("Weekly counters reset")

    def _get_week_start(self) -> datetime:
        """Get start of current week (Monday)."""
        today = datetime.now()
        return today - timedelta(days=today.weekday())

    def get_state(self) -> RiskState:
        """Get current risk state."""
        self._check_date_reset()
        self._update_status()

        # Calculate size multiplier
        if self._status == RiskStatus.HALTED:
            size_mult = 0.0
        elif self._status == RiskStatus.COOLDOWN:
            size_mult = 0.0
        elif self._status == RiskStatus.REDUCED:
            size_mult = 0.5
        else:
            size_mult = 1.0

        drawdown = self._peak_equity - self._current_equity

        return RiskState(
            status=self._status,
            reason=self._status_reason,
            size_multiplier=size_mult,
            daily_pnl=self._daily_pnl,
            weekly_pnl=self._weekly_pnl,
            peak_equity=self._peak_equity,
            current_equity=self._current_equity,
            drawdown=drawdown,
            drawdown_pct=self._get_drawdown_pct(),
            trades_today=self._trades_today,
            consecutive_losses=self._consecutive_losses,
            last_trade_time=self._last_trade_time,
            cooldown_until=self._cooldown_until
        )

    def get_stats(self) -> dict:
        """Get risk manager statistics."""
        if not self._trade_history:
            return {'total_trades': 0}

        wins = [t for t in self._trade_history if t.is_win]
        losses = [t for t in self._trade_history if not t.is_win]

        return {
            'total_trades': len(self._trade_history),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(self._trade_history),
            'total_pnl': sum(t.pnl for t in self._trade_history),
            'avg_win': sum(t.pnl for t in wins) / len(wins) if wins else 0,
            'avg_loss': sum(t.pnl for t in losses) / len(losses) if losses else 0,
            'largest_win': max((t.pnl for t in wins), default=0),
            'largest_loss': min((t.pnl for t in losses), default=0),
            'current_equity': self._current_equity,
            'peak_equity': self._peak_equity,
            'max_drawdown_pct': self._get_drawdown_pct(),
        }

    def reset(self) -> None:
        """Reset risk manager to initial state."""
        self._current_equity = self.initial_capital
        self._peak_equity = self.initial_capital
        self._daily_pnl = 0.0
        self._weekly_pnl = 0.0
        self._trades_today = 0
        self._consecutive_losses = 0
        self._consecutive_wins = 0
        self._last_trade_time = None
        self._cooldown_until = None
        self._trade_history.clear()
        self._status = RiskStatus.NORMAL
        self._status_reason = "System reset"
        self.position_sizer.update_account_size(self.initial_capital)
