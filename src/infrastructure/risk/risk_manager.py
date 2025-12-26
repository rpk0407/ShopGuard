"""
Risk Manager

Central risk control system that:
- Validates orders against limits
- Monitors portfolio risk in real-time
- Enforces position limits
- Tracks P&L and drawdowns
- Triggers alerts and kill switches

DESIGN PRINCIPLE: Defense in Depth
Multiple independent layers of risk control:
1. Pre-trade checks (order validation)
2. Real-time monitoring (position, P&L)
3. Post-trade reconciliation
4. Kill switch (independent circuit breaker)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from enum import Enum
import threading
import numpy as np


class RiskLevel(Enum):
    """Risk severity levels."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskLimits:
    """
    Risk limits configuration.

    These are hard limits that should NEVER be exceeded.
    """
    # Position limits
    max_position_value: float = 100000       # Max value per position
    max_position_pct: float = 0.10           # Max % of portfolio per position
    max_gross_exposure: float = 2.0          # Max gross exposure (long + short)
    max_net_exposure: float = 1.0            # Max net exposure (long - short)

    # Order limits
    max_order_value: float = 50000           # Max single order value
    max_orders_per_minute: int = 60          # Rate limit
    max_orders_per_symbol_minute: int = 10   # Rate limit per symbol

    # Loss limits
    max_daily_loss: float = 10000            # Stop trading after this loss
    max_daily_loss_pct: float = 0.02         # 2% of portfolio
    max_drawdown: float = 0.10               # 10% max drawdown before halt
    max_position_loss: float = 5000          # Max loss per position

    # Concentration limits
    max_sector_exposure: float = 0.30        # Max 30% in one sector
    max_correlated_exposure: float = 0.50    # Max 50% in correlated positions

    # Volatility limits
    max_portfolio_volatility: float = 0.20   # 20% annualized
    volatility_scaling: bool = True          # Scale positions by vol


@dataclass
class RiskConfig:
    """Configuration for risk manager."""
    limits: RiskLimits = field(default_factory=RiskLimits)

    # Monitoring
    check_interval_sec: float = 1.0
    alert_cooldown_sec: float = 60.0

    # Callbacks
    enable_alerts: bool = True
    enable_auto_hedge: bool = False
    enable_auto_reduce: bool = False


@dataclass
class Position:
    """Current position state."""
    symbol: str
    quantity: float
    average_cost: float
    current_price: float
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.average_cost) * self.quantity

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl


@dataclass
class RiskMetrics:
    """Current risk metrics."""
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    portfolio_volatility: float = 0.0
    var_95: float = 0.0
    sharpe_ratio: float = 0.0
    risk_level: RiskLevel = RiskLevel.NORMAL
    violations: List[str] = field(default_factory=list)


class RiskManager:
    """
    Central risk management system.

    Provides:
    - Pre-trade risk checks
    - Real-time risk monitoring
    - Limit enforcement
    - Risk metrics calculation
    """

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self.limits = self.config.limits

        # State
        self.positions: Dict[str, Position] = {}
        self.portfolio_value: float = 0.0
        self.cash: float = 0.0
        self.daily_starting_value: float = 0.0
        self.peak_value: float = 0.0

        # Order tracking for rate limits
        self.recent_orders: List[datetime] = []
        self.orders_by_symbol: Dict[str, List[datetime]] = {}

        # P&L history
        self.pnl_history: List[float] = []
        self.value_history: List[float] = []

        # Monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Callbacks
        self.on_violation: Optional[Callable[[str, str], None]] = None
        self.on_risk_level_change: Optional[Callable[[RiskLevel], None]] = None

        # Current metrics
        self._current_metrics = RiskMetrics()

    def start_monitoring(self):
        """Start real-time risk monitoring."""
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)

    def check_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> Tuple[bool, str]:
        """
        Pre-trade risk check for an order.

        Returns (allowed, reason).
        """
        order_value = quantity * price

        # Check order value limit
        if order_value > self.limits.max_order_value:
            return False, f"Order value ${order_value:.2f} exceeds limit ${self.limits.max_order_value:.2f}"

        # Check rate limits
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # Clean old orders
        self.recent_orders = [t for t in self.recent_orders if t > minute_ago]

        if len(self.recent_orders) >= self.limits.max_orders_per_minute:
            return False, f"Order rate limit exceeded ({self.limits.max_orders_per_minute}/min)"

        # Per-symbol rate limit
        if symbol not in self.orders_by_symbol:
            self.orders_by_symbol[symbol] = []
        self.orders_by_symbol[symbol] = [
            t for t in self.orders_by_symbol[symbol] if t > minute_ago
        ]

        if len(self.orders_by_symbol[symbol]) >= self.limits.max_orders_per_symbol_minute:
            return False, f"Per-symbol order rate limit exceeded for {symbol}"

        # Check position limits
        current_position = self.positions.get(symbol)
        if current_position:
            new_quantity = current_position.quantity + (quantity if side == "buy" else -quantity)
            new_value = abs(new_quantity * price)
        else:
            new_value = abs(quantity * price)

        if new_value > self.limits.max_position_value:
            return False, f"Position value ${new_value:.2f} would exceed limit ${self.limits.max_position_value:.2f}"

        if self.portfolio_value > 0:
            position_pct = new_value / self.portfolio_value
            if position_pct > self.limits.max_position_pct:
                return False, f"Position would be {position_pct:.1%} of portfolio, exceeds {self.limits.max_position_pct:.1%} limit"

        # Check exposure limits
        metrics = self.calculate_metrics()

        # Gross exposure check
        exposure_delta = order_value / self.portfolio_value if self.portfolio_value > 0 else 0
        if metrics.gross_exposure + exposure_delta > self.limits.max_gross_exposure:
            return False, f"Gross exposure would exceed {self.limits.max_gross_exposure:.1%} limit"

        # Daily loss check
        if self.limits.max_daily_loss > 0 and metrics.daily_pnl < -self.limits.max_daily_loss:
            return False, f"Daily loss limit ${self.limits.max_daily_loss:.2f} exceeded"

        # Drawdown check
        if metrics.current_drawdown > self.limits.max_drawdown:
            return False, f"Drawdown {metrics.current_drawdown:.1%} exceeds {self.limits.max_drawdown:.1%} limit"

        # Record order
        self.recent_orders.append(now)
        self.orders_by_symbol[symbol].append(now)

        return True, "Order approved"

    def update_position(
        self,
        symbol: str,
        quantity_change: float,
        price: float,
        realized_pnl: float = 0.0
    ):
        """Update position after a fill."""
        with self._lock:
            if symbol in self.positions:
                pos = self.positions[symbol]
                old_value = pos.quantity * pos.average_cost

                if quantity_change > 0:  # Adding to position
                    new_value = old_value + quantity_change * price
                    pos.quantity += quantity_change
                    pos.average_cost = new_value / pos.quantity if pos.quantity != 0 else 0
                else:  # Reducing position
                    pos.quantity += quantity_change
                    pos.realized_pnl += realized_pnl

                pos.current_price = price

                # Remove closed positions
                if abs(pos.quantity) < 1e-8:
                    del self.positions[symbol]
            else:
                # New position
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity_change,
                    average_cost=price,
                    current_price=price
                )

    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions."""
        with self._lock:
            for symbol, price in prices.items():
                if symbol in self.positions:
                    self.positions[symbol].current_price = price

            # Update portfolio value
            self._update_portfolio_value()

    def calculate_metrics(self) -> RiskMetrics:
        """Calculate current risk metrics."""
        with self._lock:
            metrics = RiskMetrics()

            if self.portfolio_value <= 0:
                return metrics

            # Calculate exposures
            long_value = sum(
                p.market_value for p in self.positions.values()
                if p.quantity > 0
            )
            short_value = sum(
                abs(p.market_value) for p in self.positions.values()
                if p.quantity < 0
            )

            metrics.gross_exposure = (long_value + short_value) / self.portfolio_value
            metrics.net_exposure = (long_value - short_value) / self.portfolio_value

            # Calculate P&L
            metrics.total_pnl = sum(p.total_pnl for p in self.positions.values())
            metrics.daily_pnl = self.portfolio_value - self.daily_starting_value

            # Calculate drawdown
            if self.portfolio_value > self.peak_value:
                self.peak_value = self.portfolio_value
            metrics.current_drawdown = (self.peak_value - self.portfolio_value) / self.peak_value
            metrics.max_drawdown = max(metrics.current_drawdown, self._current_metrics.max_drawdown)

            # Calculate volatility (if enough history)
            if len(self.value_history) > 20:
                returns = np.diff(self.value_history[-21:]) / self.value_history[-21:-1]
                metrics.portfolio_volatility = np.std(returns) * np.sqrt(252)

                # VaR (simple parametric)
                metrics.var_95 = self.portfolio_value * metrics.portfolio_volatility * 1.645 / np.sqrt(252)

                # Sharpe (simple)
                if metrics.portfolio_volatility > 0:
                    mean_return = np.mean(returns) * 252
                    metrics.sharpe_ratio = mean_return / metrics.portfolio_volatility

            # Check for violations
            metrics.violations = self._check_violations(metrics)

            # Determine risk level
            metrics.risk_level = self._determine_risk_level(metrics)

            self._current_metrics = metrics
            return metrics

    def _update_portfolio_value(self):
        """Update total portfolio value."""
        position_value = sum(p.market_value for p in self.positions.values())
        self.portfolio_value = self.cash + position_value

    def _check_violations(self, metrics: RiskMetrics) -> List[str]:
        """Check for limit violations."""
        violations = []

        if metrics.gross_exposure > self.limits.max_gross_exposure:
            violations.append(f"Gross exposure {metrics.gross_exposure:.1%} > {self.limits.max_gross_exposure:.1%}")

        if abs(metrics.net_exposure) > self.limits.max_net_exposure:
            violations.append(f"Net exposure {metrics.net_exposure:.1%} > {self.limits.max_net_exposure:.1%}")

        if self.limits.max_daily_loss > 0 and metrics.daily_pnl < -self.limits.max_daily_loss:
            violations.append(f"Daily loss ${-metrics.daily_pnl:.2f} > ${self.limits.max_daily_loss:.2f}")

        if metrics.current_drawdown > self.limits.max_drawdown:
            violations.append(f"Drawdown {metrics.current_drawdown:.1%} > {self.limits.max_drawdown:.1%}")

        if metrics.portfolio_volatility > self.limits.max_portfolio_volatility:
            violations.append(f"Volatility {metrics.portfolio_volatility:.1%} > {self.limits.max_portfolio_volatility:.1%}")

        return violations

    def _determine_risk_level(self, metrics: RiskMetrics) -> RiskLevel:
        """Determine overall risk level."""
        if len(metrics.violations) >= 3:
            return RiskLevel.CRITICAL
        elif len(metrics.violations) >= 2:
            return RiskLevel.HIGH
        elif len(metrics.violations) >= 1:
            return RiskLevel.ELEVATED

        # Also check if approaching limits
        if metrics.current_drawdown > self.limits.max_drawdown * 0.8:
            return RiskLevel.ELEVATED
        if metrics.gross_exposure > self.limits.max_gross_exposure * 0.9:
            return RiskLevel.ELEVATED

        return RiskLevel.NORMAL

    def _monitoring_loop(self):
        """Continuous risk monitoring loop."""
        last_risk_level = RiskLevel.NORMAL

        while self._running:
            try:
                metrics = self.calculate_metrics()

                # Check for risk level change
                if metrics.risk_level != last_risk_level:
                    if self.on_risk_level_change:
                        self.on_risk_level_change(metrics.risk_level)
                    last_risk_level = metrics.risk_level

                # Report violations
                for violation in metrics.violations:
                    if self.on_violation:
                        self.on_violation("LIMIT_VIOLATION", violation)

                # Store history
                self.value_history.append(self.portfolio_value)
                if len(self.value_history) > 1000:
                    self.value_history.pop(0)

                time.sleep(self.config.check_interval_sec)

            except Exception as e:
                if self.on_violation:
                    self.on_violation("MONITORING_ERROR", str(e))
                time.sleep(1.0)

    def get_risk_report(self) -> Dict:
        """Generate comprehensive risk report."""
        metrics = self.calculate_metrics()

        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio_value": self.portfolio_value,
            "cash": self.cash,
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "pct_of_portfolio": pos.market_value / self.portfolio_value if self.portfolio_value > 0 else 0
                }
                for symbol, pos in self.positions.items()
            },
            "metrics": {
                "gross_exposure": metrics.gross_exposure,
                "net_exposure": metrics.net_exposure,
                "daily_pnl": metrics.daily_pnl,
                "total_pnl": metrics.total_pnl,
                "current_drawdown": metrics.current_drawdown,
                "max_drawdown": metrics.max_drawdown,
                "portfolio_volatility": metrics.portfolio_volatility,
                "var_95": metrics.var_95,
                "sharpe_ratio": metrics.sharpe_ratio
            },
            "risk_level": metrics.risk_level.value,
            "violations": metrics.violations,
            "limits": {
                "max_gross_exposure": self.limits.max_gross_exposure,
                "max_net_exposure": self.limits.max_net_exposure,
                "max_daily_loss": self.limits.max_daily_loss,
                "max_drawdown": self.limits.max_drawdown
            }
        }
