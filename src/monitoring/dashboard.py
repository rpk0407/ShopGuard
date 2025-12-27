"""
Trading Dashboard

Real-time monitoring of trading system performance:
- P&L tracking
- Position monitoring
- Risk metrics
- System performance
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import threading
import time


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"  # Monotonically increasing
    GAUGE = "gauge"  # Point-in-time value
    HISTOGRAM = "histogram"  # Distribution
    RATE = "rate"  # Per-second rate


@dataclass
class Metric:
    """Single metric measurement."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    name: str
    current: float
    mean: float
    min: float
    max: float
    std: float
    count: int
    rate_per_second: float


class MetricCollector:
    """
    Collects and aggregates metrics for the trading system.
    """

    def __init__(self, history_size: int = 3600):
        """
        Initialize metric collector.

        Args:
            history_size: Number of data points to keep per metric
        """
        self.history_size = history_size
        self.metrics: Dict[str, deque] = {}
        self._lock = threading.Lock()

        # Computed metrics cache
        self._summaries: Dict[str, MetricSummary] = {}
        self._last_summary_time: datetime = datetime.now()

    def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        tags: Dict[str, str] = None
    ):
        """Record a metric value."""
        metric = Metric(
            name=name,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {},
            metric_type=metric_type
        )

        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = deque(maxlen=self.history_size)
            self.metrics[name].append(metric)

    def increment(self, name: str, amount: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter metric."""
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = deque(maxlen=self.history_size)

            current = self.metrics[name][-1].value if self.metrics[name] else 0
            self.record(name, current + amount, MetricType.COUNTER, tags)

    def get_current(self, name: str) -> Optional[float]:
        """Get current value of a metric."""
        with self._lock:
            if name in self.metrics and self.metrics[name]:
                return self.metrics[name][-1].value
        return None

    def get_history(
        self,
        name: str,
        duration: timedelta = None
    ) -> List[Metric]:
        """Get history for a metric."""
        with self._lock:
            if name not in self.metrics:
                return []

            if duration is None:
                return list(self.metrics[name])

            cutoff = datetime.now() - duration
            return [m for m in self.metrics[name] if m.timestamp >= cutoff]

    def get_summary(self, name: str) -> Optional[MetricSummary]:
        """Get summary statistics for a metric."""
        with self._lock:
            if name not in self.metrics or not self.metrics[name]:
                return None

            values = [m.value for m in self.metrics[name]]
            timestamps = [m.timestamp for m in self.metrics[name]]

        if not values:
            return None

        # Calculate rate
        if len(timestamps) >= 2:
            duration = (timestamps[-1] - timestamps[0]).total_seconds()
            if duration > 0:
                rate = len(values) / duration
            else:
                rate = 0
        else:
            rate = 0

        return MetricSummary(
            name=name,
            current=values[-1],
            mean=np.mean(values),
            min=np.min(values),
            max=np.max(values),
            std=np.std(values) if len(values) > 1 else 0,
            count=len(values),
            rate_per_second=rate
        )

    def get_all_summaries(self) -> Dict[str, MetricSummary]:
        """Get summaries for all metrics."""
        with self._lock:
            names = list(self.metrics.keys())

        return {
            name: summary
            for name in names
            if (summary := self.get_summary(name)) is not None
        }


class TradingDashboard:
    """
    Real-time trading dashboard.

    Provides comprehensive view of:
    - P&L and returns
    - Positions and exposure
    - Risk metrics
    - Order flow
    - System health
    """

    def __init__(self):
        self.collector = MetricCollector()

        # Core metrics
        self._pnl_history: deque = deque(maxlen=86400)  # 1 day at 1/sec
        self._position_history: Dict[str, deque] = {}
        self._trade_history: deque = deque(maxlen=10000)

        # Computed values
        self._peak_pnl: float = 0
        self._drawdown: float = 0
        self._start_time: datetime = datetime.now()

        self._lock = threading.Lock()

    def update_pnl(self, pnl: float, realized: float, unrealized: float):
        """Update P&L metrics."""
        now = datetime.now()

        with self._lock:
            self._pnl_history.append({
                'timestamp': now,
                'total': pnl,
                'realized': realized,
                'unrealized': unrealized
            })

            # Update peak and drawdown
            if pnl > self._peak_pnl:
                self._peak_pnl = pnl
            self._drawdown = (self._peak_pnl - pnl) / self._peak_pnl if self._peak_pnl > 0 else 0

        self.collector.record('pnl.total', pnl)
        self.collector.record('pnl.realized', realized)
        self.collector.record('pnl.unrealized', unrealized)
        self.collector.record('pnl.drawdown', self._drawdown)

    def update_position(
        self,
        symbol: str,
        quantity: int,
        avg_price: float,
        market_price: float
    ):
        """Update position for a symbol."""
        pnl = (market_price - avg_price) * quantity
        exposure = abs(quantity * market_price)

        with self._lock:
            if symbol not in self._position_history:
                self._position_history[symbol] = deque(maxlen=3600)

            self._position_history[symbol].append({
                'timestamp': datetime.now(),
                'quantity': quantity,
                'avg_price': avg_price,
                'market_price': market_price,
                'pnl': pnl,
                'exposure': exposure
            })

        self.collector.record(f'position.{symbol}.quantity', quantity)
        self.collector.record(f'position.{symbol}.pnl', pnl)
        self.collector.record(f'position.{symbol}.exposure', exposure)

    def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_id: str
    ):
        """Record a trade execution."""
        trade = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'order_id': order_id,
            'value': quantity * price
        }

        with self._lock:
            self._trade_history.append(trade)

        self.collector.increment('trades.count')
        self.collector.record('trades.value', quantity * price)
        self.collector.record(f'trades.{symbol}.count', 1, MetricType.COUNTER)

    def update_risk_metrics(
        self,
        var: float,
        cvar: float,
        beta: float,
        correlation: float
    ):
        """Update risk metrics."""
        self.collector.record('risk.var', var)
        self.collector.record('risk.cvar', cvar)
        self.collector.record('risk.beta', beta)
        self.collector.record('risk.correlation', correlation)

    def update_system_metrics(
        self,
        latency_us: float,
        cpu_percent: float,
        memory_mb: float,
        order_rate: float
    ):
        """Update system performance metrics."""
        self.collector.record('system.latency_us', latency_us)
        self.collector.record('system.cpu_percent', cpu_percent)
        self.collector.record('system.memory_mb', memory_mb)
        self.collector.record('system.order_rate', order_rate)

    def get_pnl_summary(self) -> Dict:
        """Get P&L summary."""
        with self._lock:
            if not self._pnl_history:
                return {'total': 0, 'realized': 0, 'unrealized': 0}

            latest = self._pnl_history[-1]

            # Calculate returns
            if len(self._pnl_history) > 1:
                prev = self._pnl_history[-2]
                ret = (latest['total'] - prev['total']) / max(1, abs(prev['total']))
            else:
                ret = 0

            # Calculate Sharpe (annualized)
            if len(self._pnl_history) > 10:
                pnls = [p['total'] for p in self._pnl_history]
                returns = np.diff(pnls) / np.abs(np.array(pnls[:-1]) + 1)
                if len(returns) > 0 and np.std(returns) > 0:
                    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 6.5 * 60)
                else:
                    sharpe = 0
            else:
                sharpe = 0

        return {
            'total': latest['total'],
            'realized': latest['realized'],
            'unrealized': latest['unrealized'],
            'return': ret,
            'peak': self._peak_pnl,
            'drawdown': self._drawdown,
            'sharpe': sharpe
        }

    def get_position_summary(self) -> Dict:
        """Get position summary."""
        with self._lock:
            positions = {}
            for symbol, history in self._position_history.items():
                if history:
                    latest = history[-1]
                    positions[symbol] = {
                        'quantity': latest['quantity'],
                        'avg_price': latest['avg_price'],
                        'market_price': latest['market_price'],
                        'pnl': latest['pnl'],
                        'exposure': latest['exposure']
                    }

        total_exposure = sum(p['exposure'] for p in positions.values())
        total_pnl = sum(p['pnl'] for p in positions.values())

        return {
            'positions': positions,
            'total_exposure': total_exposure,
            'total_pnl': total_pnl,
            'num_positions': len(positions)
        }

    def get_trade_summary(self, duration: timedelta = None) -> Dict:
        """Get trade summary."""
        with self._lock:
            trades = list(self._trade_history)

        if duration:
            cutoff = datetime.now() - duration
            trades = [t for t in trades if t['timestamp'] >= cutoff]

        if not trades:
            return {
                'count': 0,
                'volume': 0,
                'value': 0,
                'buy_count': 0,
                'sell_count': 0
            }

        return {
            'count': len(trades),
            'volume': sum(t['quantity'] for t in trades),
            'value': sum(t['value'] for t in trades),
            'buy_count': sum(1 for t in trades if t['side'] == 'buy'),
            'sell_count': sum(1 for t in trades if t['side'] == 'sell'),
            'symbols': list(set(t['symbol'] for t in trades))
        }

    def get_dashboard_data(self) -> Dict:
        """Get complete dashboard data."""
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': (datetime.now() - self._start_time).total_seconds(),
            'pnl': self.get_pnl_summary(),
            'positions': self.get_position_summary(),
            'trades': self.get_trade_summary(timedelta(hours=1)),
            'risk': {
                'var': self.collector.get_current('risk.var'),
                'cvar': self.collector.get_current('risk.cvar'),
                'beta': self.collector.get_current('risk.beta'),
            },
            'system': {
                'latency_us': self.collector.get_current('system.latency_us'),
                'cpu_percent': self.collector.get_current('system.cpu_percent'),
                'memory_mb': self.collector.get_current('system.memory_mb'),
            },
            'metrics': self.collector.get_all_summaries()
        }

    def format_dashboard(self) -> str:
        """Format dashboard for console display."""
        data = self.get_dashboard_data()
        pnl = data['pnl']
        pos = data['positions']
        trades = data['trades']

        lines = []
        lines.append("=" * 70)
        lines.append("TRADING DASHBOARD")
        lines.append(f"Time: {data['timestamp']}  Uptime: {data['uptime_seconds']:.0f}s")
        lines.append("=" * 70)

        # P&L Section
        lines.append("")
        lines.append("P&L")
        lines.append("-" * 40)
        lines.append(f"  Total:      ${pnl.get('total', 0):>12,.2f}")
        lines.append(f"  Realized:   ${pnl.get('realized', 0):>12,.2f}")
        lines.append(f"  Unrealized: ${pnl.get('unrealized', 0):>12,.2f}")
        lines.append(f"  Drawdown:   {pnl.get('drawdown', 0)*100:>12.2f}%")
        lines.append(f"  Sharpe:     {pnl.get('sharpe', 0):>12.2f}")

        # Positions Section
        lines.append("")
        lines.append("POSITIONS")
        lines.append("-" * 40)
        lines.append(f"  Count:      {pos.get('num_positions', 0):>12}")
        lines.append(f"  Exposure:   ${pos.get('total_exposure', 0):>12,.2f}")

        for symbol, position in pos.get('positions', {}).items():
            qty = position['quantity']
            pnl_val = position['pnl']
            lines.append(f"  {symbol:12} {qty:>8} ${pnl_val:>10,.2f}")

        # Trades Section
        lines.append("")
        lines.append("TRADES (Last Hour)")
        lines.append("-" * 40)
        lines.append(f"  Count:      {trades.get('count', 0):>12}")
        lines.append(f"  Volume:     {trades.get('volume', 0):>12,}")
        lines.append(f"  Value:      ${trades.get('value', 0):>12,.2f}")

        # System Section
        system = data.get('system', {})
        lines.append("")
        lines.append("SYSTEM")
        lines.append("-" * 40)
        latency = system.get('latency_us') or 0
        cpu = system.get('cpu_percent') or 0
        memory = system.get('memory_mb') or 0
        lines.append(f"  Latency:    {latency:>12.0f} μs")
        lines.append(f"  CPU:        {cpu:>12.1f}%")
        lines.append(f"  Memory:     {memory:>12.0f} MB")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


class DashboardServer:
    """
    Serves dashboard data over HTTP.

    Simple HTTP server for dashboard visualization.
    """

    def __init__(
        self,
        dashboard: TradingDashboard,
        host: str = "localhost",
        port: int = 8080
    ):
        self.dashboard = dashboard
        self.host = host
        self.port = port
        self._running = False

    def start(self):
        """Start the dashboard server."""
        self._running = True
        # Would start HTTP server here
        # For now, just a placeholder

    def stop(self):
        """Stop the dashboard server."""
        self._running = False

    def get_json(self) -> Dict:
        """Get dashboard data as JSON."""
        return self.dashboard.get_dashboard_data()
