"""
THE MEMBRANE - Risk Management System
=====================================
Protects the organism from catastrophic losses.

Features:
- Kelly Criterion position sizing
- Maximum drawdown protection
- Portfolio heat monitoring
- Circuit breakers
- Correlation-adjusted risk
- Volatility scaling
"""

import math
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Current risk exposure level"""
    MINIMAL = "minimal"      # < 25% of max risk
    MODERATE = "moderate"    # 25-50% of max risk
    ELEVATED = "elevated"    # 50-75% of max risk
    HIGH = "high"           # 75-90% of max risk
    CRITICAL = "critical"   # > 90% of max risk
    CIRCUIT_BREAKER = "circuit_breaker"  # Trading halted


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Capital
    initial_capital: float = 10000.0

    # Position Sizing
    max_position_pct: float = 0.25        # Max 25% per position
    max_portfolio_heat: float = 0.50      # Max 50% total exposure
    kelly_fraction: float = 0.25          # Quarter-Kelly for safety

    # Drawdown Protection
    max_drawdown_pct: float = 0.15        # 15% max drawdown
    daily_loss_limit_pct: float = 0.05    # 5% daily loss limit

    # Circuit Breakers
    consecutive_loss_limit: int = 5       # Pause after 5 losses
    volatility_multiplier_limit: float = 3.0  # Pause if vol > 3x normal

    # Risk Scaling
    scale_with_volatility: bool = True
    scale_with_drawdown: bool = True

    # Correlation
    correlation_adjustment: bool = True
    max_correlated_positions: int = 3


@dataclass
class Position:
    """Active position tracking"""
    asset: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    current_price: float
    size: float  # In base currency units
    entry_time: float
    stop_loss: float
    take_profit: float

    # Risk metrics
    risk_amount: float = 0.0  # $ at risk
    unrealized_pnl: float = 0.0

    def update(self, current_price: float):
        """Update position with new price"""
        self.current_price = current_price
        if self.side == "LONG":
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.size


@dataclass
class RiskState:
    """Current risk state of the portfolio"""
    # Capital
    current_capital: float
    peak_capital: float

    # Drawdown
    current_drawdown: float
    current_drawdown_pct: float
    max_drawdown_seen: float

    # Exposure
    total_exposure: float
    exposure_pct: float
    position_count: int

    # Daily
    daily_pnl: float
    daily_pnl_pct: float

    # Status
    risk_level: RiskLevel
    circuit_breaker_active: bool
    consecutive_losses: int

    # Metrics
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float


class PositionSizer:
    """
    Calculates optimal position sizes using Kelly Criterion
    with safety adjustments for volatility and correlation.
    """

    def __init__(self, config: RiskConfig):
        self.config = config

    def kelly_size(
        self,
        win_probability: float,
        avg_win: float,
        avg_loss: float,
        capital: float
    ) -> float:
        """
        Calculate Kelly Criterion position size.

        Kelly % = W - [(1-W) / R]
        Where:
            W = Win probability
            R = Win/Loss ratio
        """
        if avg_loss == 0 or win_probability <= 0:
            return 0.0

        win_loss_ratio = avg_win / abs(avg_loss)

        # Kelly formula
        kelly_pct = win_probability - ((1 - win_probability) / win_loss_ratio)

        # Apply fractional Kelly for safety
        kelly_pct *= self.config.kelly_fraction

        # Clamp to max position size
        kelly_pct = max(0, min(kelly_pct, self.config.max_position_pct))

        return capital * kelly_pct

    def volatility_adjusted_size(
        self,
        base_size: float,
        current_volatility: float,
        baseline_volatility: float
    ) -> float:
        """Reduce position size when volatility is elevated"""
        if not self.config.scale_with_volatility or baseline_volatility == 0:
            return base_size

        vol_ratio = current_volatility / baseline_volatility

        # Inverse scaling: higher vol = smaller position
        if vol_ratio > 1:
            adjustment = 1 / vol_ratio
            return base_size * adjustment

        return base_size

    def drawdown_adjusted_size(
        self,
        base_size: float,
        current_drawdown_pct: float
    ) -> float:
        """Reduce position size during drawdown"""
        if not self.config.scale_with_drawdown:
            return base_size

        # Linear reduction: at 10% DD, reduce by 50%
        # At 15% DD, reduce by 75%
        reduction_factor = 1 - (current_drawdown_pct / self.config.max_drawdown_pct)
        reduction_factor = max(0.25, min(1.0, reduction_factor))  # Min 25% of normal

        return base_size * reduction_factor

    def calculate_position_size(
        self,
        signal_confidence: float,
        capital: float,
        win_rate: float = 0.55,
        avg_win: float = 100,
        avg_loss: float = 50,
        current_volatility: float = 0.02,
        baseline_volatility: float = 0.02,
        current_drawdown_pct: float = 0.0,
        current_exposure_pct: float = 0.0
    ) -> Tuple[float, str]:
        """
        Calculate final position size with all adjustments.
        Returns (size, reasoning).
        """
        reasons = []

        # Start with Kelly sizing
        kelly = self.kelly_size(win_rate, avg_win, avg_loss, capital)
        reasons.append(f"Kelly base: ${kelly:.2f}")

        # Scale by confidence
        size = kelly * signal_confidence
        reasons.append(f"Confidence adjusted: ${size:.2f}")

        # Volatility adjustment
        if self.config.scale_with_volatility:
            size = self.volatility_adjusted_size(size, current_volatility, baseline_volatility)
            reasons.append(f"Vol adjusted: ${size:.2f}")

        # Drawdown adjustment
        if current_drawdown_pct > 0:
            size = self.drawdown_adjusted_size(size, current_drawdown_pct)
            reasons.append(f"DD adjusted: ${size:.2f}")

        # Check portfolio heat
        remaining_capacity = (self.config.max_portfolio_heat - current_exposure_pct) * capital
        if size > remaining_capacity:
            size = max(0, remaining_capacity)
            reasons.append(f"Heat capped: ${size:.2f}")

        # Final cap
        max_size = capital * self.config.max_position_pct
        size = min(size, max_size)

        return size, " → ".join(reasons)


class RiskManager:
    """
    THE MEMBRANE
    ============
    Central risk management system that protects capital.

    Responsibilities:
    - Track all positions and exposure
    - Calculate position sizes
    - Monitor drawdown and daily losses
    - Trigger circuit breakers
    - Adjust risk based on conditions
    """

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self.sizer = PositionSizer(self.config)

        # State
        self.positions: Dict[str, Position] = {}
        self.current_capital = self.config.initial_capital
        self.peak_capital = self.config.initial_capital
        self.day_start_capital = self.config.initial_capital

        # History
        self.trade_results: deque = deque(maxlen=100)  # Last 100 trades
        self.equity_curve: deque = deque(maxlen=1000)
        self.daily_pnl_history: deque = deque(maxlen=30)

        # Circuit breaker state
        self.circuit_breaker_active = False
        self.circuit_breaker_until: float = 0
        self.consecutive_losses = 0

        # Metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0

        logger.info("🛡️ Risk Manager (Membrane) initialized")

    def get_risk_state(self) -> RiskState:
        """Get current risk state"""
        # Calculate drawdown
        drawdown = self.peak_capital - self.current_capital
        drawdown_pct = drawdown / self.peak_capital if self.peak_capital > 0 else 0

        # Calculate exposure
        total_exposure = sum(p.size * p.current_price for p in self.positions.values())
        exposure_pct = total_exposure / self.current_capital if self.current_capital > 0 else 0

        # Daily P&L
        daily_pnl = self.current_capital - self.day_start_capital
        daily_pnl_pct = daily_pnl / self.day_start_capital if self.day_start_capital > 0 else 0

        # Win rate and averages
        wins = [r for r in self.trade_results if r > 0]
        losses = [r for r in self.trade_results if r < 0]

        win_rate = len(wins) / len(self.trade_results) if self.trade_results else 0.5
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0

        # Determine risk level
        risk_level = self._calculate_risk_level(exposure_pct, drawdown_pct, daily_pnl_pct)

        return RiskState(
            current_capital=self.current_capital,
            peak_capital=self.peak_capital,
            current_drawdown=drawdown,
            current_drawdown_pct=drawdown_pct,
            max_drawdown_seen=max(drawdown_pct, 0),
            total_exposure=total_exposure,
            exposure_pct=exposure_pct,
            position_count=len(self.positions),
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            risk_level=risk_level,
            circuit_breaker_active=self.circuit_breaker_active,
            consecutive_losses=self.consecutive_losses,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor
        )

    def _calculate_risk_level(
        self,
        exposure_pct: float,
        drawdown_pct: float,
        daily_pnl_pct: float
    ) -> RiskLevel:
        """Determine current risk level"""
        if self.circuit_breaker_active:
            return RiskLevel.CIRCUIT_BREAKER

        # Check multiple factors
        risk_score = 0

        # Exposure contribution (0-30 points)
        risk_score += (exposure_pct / self.config.max_portfolio_heat) * 30

        # Drawdown contribution (0-40 points)
        risk_score += (drawdown_pct / self.config.max_drawdown_pct) * 40

        # Daily loss contribution (0-30 points)
        if daily_pnl_pct < 0:
            risk_score += (abs(daily_pnl_pct) / self.config.daily_loss_limit_pct) * 30

        # Map score to level
        if risk_score >= 90:
            return RiskLevel.CRITICAL
        elif risk_score >= 75:
            return RiskLevel.HIGH
        elif risk_score >= 50:
            return RiskLevel.ELEVATED
        elif risk_score >= 25:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.MINIMAL

    def can_trade(self) -> Tuple[bool, str]:
        """Check if new trades are allowed"""
        state = self.get_risk_state()

        # Circuit breaker check
        if self.circuit_breaker_active:
            if time.time() < self.circuit_breaker_until:
                remaining = int(self.circuit_breaker_until - time.time())
                return False, f"Circuit breaker active ({remaining}s remaining)"
            else:
                self.circuit_breaker_active = False
                logger.info("🛡️ Circuit breaker deactivated")

        # Max drawdown check
        if state.current_drawdown_pct >= self.config.max_drawdown_pct:
            self._trigger_circuit_breaker("Max drawdown exceeded")
            return False, "Max drawdown limit reached"

        # Daily loss limit
        if state.daily_pnl_pct <= -self.config.daily_loss_limit_pct:
            self._trigger_circuit_breaker("Daily loss limit exceeded")
            return False, "Daily loss limit reached"

        # Consecutive losses
        if self.consecutive_losses >= self.config.consecutive_loss_limit:
            self._trigger_circuit_breaker("Consecutive loss limit")
            return False, f"Consecutive losses limit ({self.consecutive_losses})"

        # Portfolio heat
        if state.exposure_pct >= self.config.max_portfolio_heat:
            return False, "Portfolio heat limit reached"

        return True, "Trading allowed"

    def _trigger_circuit_breaker(self, reason: str, duration: int = 300):
        """Activate circuit breaker"""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = time.time() + duration
        logger.warning(f"🛡️ CIRCUIT BREAKER: {reason} (paused for {duration}s)")

    def calculate_position_size(
        self,
        signal_confidence: float,
        current_volatility: float = 0.02,
        baseline_volatility: float = 0.02
    ) -> Tuple[float, str]:
        """Calculate recommended position size"""
        state = self.get_risk_state()

        return self.sizer.calculate_position_size(
            signal_confidence=signal_confidence,
            capital=self.current_capital,
            win_rate=state.win_rate,
            avg_win=state.avg_win if state.avg_win > 0 else 100,
            avg_loss=abs(state.avg_loss) if state.avg_loss != 0 else 50,
            current_volatility=current_volatility,
            baseline_volatility=baseline_volatility,
            current_drawdown_pct=state.current_drawdown_pct,
            current_exposure_pct=state.exposure_pct
        )

    def open_position(
        self,
        asset: str,
        side: str,
        entry_price: float,
        size: float,
        stop_loss: float,
        take_profit: float
    ) -> Optional[Position]:
        """Register a new position"""
        can_trade, reason = self.can_trade()
        if not can_trade:
            logger.warning(f"🛡️ Position blocked: {reason}")
            return None

        risk_amount = abs(entry_price - stop_loss) * size

        position = Position(
            asset=asset,
            side=side,
            entry_price=entry_price,
            current_price=entry_price,
            size=size,
            entry_time=time.time(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount
        )

        self.positions[asset] = position
        logger.info(f"🛡️ Position opened: {asset} {side} {size} @ ${entry_price:.2f}")

        return position

    def close_position(self, asset: str, exit_price: float) -> Optional[float]:
        """Close a position and record the result"""
        if asset not in self.positions:
            return None

        position = self.positions[asset]
        position.update(exit_price)
        pnl = position.unrealized_pnl

        # Update capital
        self.current_capital += pnl
        self.total_pnl += pnl
        self.total_trades += 1

        # Track result
        self.trade_results.append(pnl)

        # Update win/loss tracking
        if pnl > 0:
            self.winning_trades += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

        # Update peak capital
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

        # Record equity
        self.equity_curve.append({
            'time': time.time(),
            'equity': self.current_capital,
            'pnl': pnl
        })

        # Remove position
        del self.positions[asset]

        logger.info(f"🛡️ Position closed: {asset} P&L=${pnl:.2f}")

        return pnl

    def update_positions(self, prices: Dict[str, float]):
        """Update all positions with current prices"""
        for asset, position in self.positions.items():
            if asset in prices:
                position.update(prices[asset])

    def new_day(self):
        """Reset daily tracking"""
        self.day_start_capital = self.current_capital
        self.daily_pnl_history.append({
            'date': time.strftime('%Y-%m-%d'),
            'pnl': 0
        })
        logger.info("🛡️ New trading day started")

    def get_stats(self) -> Dict:
        """Get risk management statistics"""
        state = self.get_risk_state()

        return {
            'capital': {
                'current': self.current_capital,
                'peak': self.peak_capital,
                'initial': self.config.initial_capital,
                'total_pnl': self.total_pnl,
                'total_pnl_pct': (self.current_capital - self.config.initial_capital) / self.config.initial_capital
            },
            'risk': {
                'level': state.risk_level.value,
                'exposure_pct': state.exposure_pct,
                'drawdown_pct': state.current_drawdown_pct,
                'daily_pnl_pct': state.daily_pnl_pct,
                'circuit_breaker': self.circuit_breaker_active
            },
            'performance': {
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'win_rate': state.win_rate,
                'profit_factor': state.profit_factor,
                'consecutive_losses': self.consecutive_losses
            },
            'positions': {
                'count': len(self.positions),
                'assets': list(self.positions.keys())
            }
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test risk manager
    rm = RiskManager()

    # Test position sizing
    size, reason = rm.calculate_position_size(0.8, 0.02, 0.02)
    print(f"Position size: ${size:.2f}")
    print(f"Reasoning: {reason}")

    # Test opening position
    pos = rm.open_position("BTC/USDT", "LONG", 100.0, 10, 95.0, 110.0)
    print(f"Position: {pos}")

    # Test risk state
    state = rm.get_risk_state()
    print(f"Risk level: {state.risk_level.value}")

    # Test closing
    pnl = rm.close_position("BTC/USDT", 105.0)
    print(f"P&L: ${pnl:.2f}")

    print(f"\nStats: {rm.get_stats()}")
