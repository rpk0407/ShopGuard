"""
Latency Monitoring and Optimization

In HFT, latency is everything. Microseconds matter.

Latency sources:
1. Network (wire time, switch queuing)
2. Processing (CPU, memory, algorithms)
3. Serialization (encoding/decoding messages)
4. Kernel (syscalls, context switches)
5. Application (business logic)

This module provides:
- Latency measurement and monitoring
- Jitter analysis
- Performance optimization hints
- Alerting for latency spikes
"""

import time
import threading
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from collections import deque
from datetime import datetime, timedelta
import numpy as np


@dataclass
class LatencyMeasurement:
    """Single latency measurement."""
    name: str                    # What was measured
    latency_ns: int             # Latency in nanoseconds
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)

    @property
    def latency_us(self) -> float:
        """Latency in microseconds."""
        return self.latency_ns / 1000

    @property
    def latency_ms(self) -> float:
        """Latency in milliseconds."""
        return self.latency_ns / 1_000_000


@dataclass
class LatencyStats:
    """Latency statistics over a period."""
    name: str
    count: int
    mean_ns: float
    median_ns: float
    std_ns: float
    min_ns: int
    max_ns: int
    p50_ns: float
    p95_ns: float
    p99_ns: float
    p999_ns: float


class LatencyMonitor:
    """
    Real-time latency monitoring for trading systems.

    Tracks latency at multiple points in the execution path:
    - Market data ingestion
    - Signal calculation
    - Order generation
    - Order submission
    - Exchange acknowledgment
    - Fill notification
    """

    def __init__(
        self,
        history_size: int = 10000,
        alert_threshold_us: float = 1000
    ):
        """
        Initialize latency monitor.

        Args:
            history_size: Number of measurements to keep
            alert_threshold_us: Threshold for alerts (microseconds)
        """
        self.history_size = history_size
        self.alert_threshold_us = alert_threshold_us

        # Measurements by type
        self.measurements: Dict[str, deque] = {}

        # Alerts
        self.alerts: deque = deque(maxlen=1000)

        # Callbacks
        self.on_alert: Optional[Callable[[str, float], None]] = None

        # Thread safety
        self._lock = threading.Lock()

    def start_timer(self) -> int:
        """Start a high-resolution timer. Returns start time in ns."""
        return time.perf_counter_ns()

    def record(
        self,
        name: str,
        start_time_ns: int,
        metadata: Dict = None
    ) -> LatencyMeasurement:
        """
        Record a latency measurement.

        Args:
            name: Measurement name (e.g., 'order_submission')
            start_time_ns: Start time from start_timer()
            metadata: Optional additional data

        Returns:
            LatencyMeasurement object
        """
        end_time_ns = time.perf_counter_ns()
        latency_ns = end_time_ns - start_time_ns

        measurement = LatencyMeasurement(
            name=name,
            latency_ns=latency_ns,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )

        with self._lock:
            if name not in self.measurements:
                self.measurements[name] = deque(maxlen=self.history_size)
            self.measurements[name].append(measurement)

        # Check for alert
        if measurement.latency_us > self.alert_threshold_us:
            self._trigger_alert(name, measurement.latency_us)

        return measurement

    def record_external(
        self,
        name: str,
        latency_ns: int,
        timestamp: datetime = None,
        metadata: Dict = None
    ):
        """Record an externally measured latency."""
        measurement = LatencyMeasurement(
            name=name,
            latency_ns=latency_ns,
            timestamp=timestamp or datetime.now(),
            metadata=metadata or {}
        )

        with self._lock:
            if name not in self.measurements:
                self.measurements[name] = deque(maxlen=self.history_size)
            self.measurements[name].append(measurement)

    def get_stats(self, name: str) -> Optional[LatencyStats]:
        """Get statistics for a measurement type."""
        with self._lock:
            if name not in self.measurements or len(self.measurements[name]) == 0:
                return None

            latencies = [m.latency_ns for m in self.measurements[name]]

        if not latencies:
            return None

        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        return LatencyStats(
            name=name,
            count=n,
            mean_ns=statistics.mean(latencies),
            median_ns=statistics.median(latencies),
            std_ns=statistics.stdev(latencies) if n > 1 else 0,
            min_ns=min(latencies),
            max_ns=max(latencies),
            p50_ns=latencies_sorted[int(n * 0.50)],
            p95_ns=latencies_sorted[int(n * 0.95)],
            p99_ns=latencies_sorted[int(n * 0.99)],
            p999_ns=latencies_sorted[min(int(n * 0.999), n - 1)]
        )

    def get_all_stats(self) -> Dict[str, LatencyStats]:
        """Get statistics for all measurement types."""
        with self._lock:
            names = list(self.measurements.keys())

        return {name: self.get_stats(name) for name in names}

    def _trigger_alert(self, name: str, latency_us: float):
        """Trigger a latency alert."""
        alert = {
            'timestamp': datetime.now(),
            'name': name,
            'latency_us': latency_us,
            'threshold_us': self.alert_threshold_us
        }

        with self._lock:
            self.alerts.append(alert)

        if self.on_alert:
            self.on_alert(name, latency_us)

    def get_jitter_analysis(self, name: str) -> Dict:
        """
        Analyze latency jitter (variability).

        High jitter is often more problematic than high latency.
        """
        with self._lock:
            if name not in self.measurements or len(self.measurements[name]) < 10:
                return {}

            latencies = [m.latency_ns for m in self.measurements[name]]

        mean_lat = np.mean(latencies)
        std_lat = np.std(latencies)

        # Jitter = standard deviation of latency differences
        diffs = np.diff(latencies)
        jitter = np.std(diffs)

        # Coefficient of variation
        cv = std_lat / mean_lat if mean_lat > 0 else 0

        return {
            'mean_ns': mean_lat,
            'std_ns': std_lat,
            'jitter_ns': jitter,
            'coefficient_of_variation': cv,
            'is_stable': cv < 0.3,  # CV < 30% is stable
            'outlier_count': np.sum(np.abs(latencies - mean_lat) > 3 * std_lat)
        }

    def get_latency_breakdown(self) -> Dict[str, float]:
        """
        Get latency breakdown by component.

        Shows where time is being spent.
        """
        all_stats = self.get_all_stats()

        breakdown = {}
        total = 0

        for name, stats in all_stats.items():
            if stats:
                breakdown[name] = stats.mean_ns
                total += stats.mean_ns

        # Add percentages
        result = {}
        for name, ns in breakdown.items():
            result[name] = {
                'mean_ns': ns,
                'mean_us': ns / 1000,
                'percentage': (ns / total * 100) if total > 0 else 0
            }

        return result


class LatencyOptimizer:
    """
    Suggestions for latency optimization.

    Based on measurements, provides recommendations.
    """

    def __init__(self, monitor: LatencyMonitor):
        self.monitor = monitor

    def analyze(self) -> List[Dict]:
        """
        Analyze latency data and provide optimization suggestions.

        Returns list of recommendations.
        """
        recommendations = []
        all_stats = self.monitor.get_all_stats()

        for name, stats in all_stats.items():
            if stats is None:
                continue

            # Check for high p99/p50 ratio (indicates outliers)
            if stats.p50_ns > 0 and stats.p99_ns / stats.p50_ns > 10:
                recommendations.append({
                    'component': name,
                    'issue': 'High tail latency',
                    'severity': 'HIGH',
                    'detail': f'P99 ({stats.p99_ns/1000:.1f}µs) is {stats.p99_ns/stats.p50_ns:.0f}x P50 ({stats.p50_ns/1000:.1f}µs)',
                    'suggestion': 'Investigate garbage collection, lock contention, or system calls'
                })

            # Check for high jitter
            jitter = self.monitor.get_jitter_analysis(name)
            if jitter.get('coefficient_of_variation', 0) > 0.5:
                recommendations.append({
                    'component': name,
                    'issue': 'High jitter',
                    'severity': 'MEDIUM',
                    'detail': f'Coefficient of variation: {jitter["coefficient_of_variation"]:.2f}',
                    'suggestion': 'Consider CPU pinning, disable frequency scaling, or use busy polling'
                })

            # Check for extreme outliers
            if jitter.get('outlier_count', 0) > stats.count * 0.01:
                recommendations.append({
                    'component': name,
                    'issue': 'Frequent outliers',
                    'severity': 'MEDIUM',
                    'detail': f'{jitter["outlier_count"]} outliers (> 3 sigma)',
                    'suggestion': 'Check for context switches, interrupts, or memory allocation'
                })

        # Provide general optimization tips based on total latency
        breakdown = self.monitor.get_latency_breakdown()
        if breakdown:
            # Find the biggest contributor
            biggest = max(breakdown.items(), key=lambda x: x[1]['mean_ns'])
            if biggest[1]['percentage'] > 50:
                recommendations.append({
                    'component': biggest[0],
                    'issue': 'Latency bottleneck',
                    'severity': 'HIGH',
                    'detail': f'{biggest[0]} accounts for {biggest[1]["percentage"]:.0f}% of total latency',
                    'suggestion': f'Focus optimization efforts on {biggest[0]}'
                })

        return recommendations


class TradingSystemLatency:
    """
    Full trading system latency tracking.

    Tracks the complete order lifecycle:
    1. Market data received
    2. Signal calculated
    3. Order decision made
    4. Order created
    5. Order submitted
    6. Ack received
    7. Fill received
    """

    def __init__(self):
        self.monitor = LatencyMonitor(alert_threshold_us=500)

        # Order lifecycle tracking
        self.order_timings: Dict[str, Dict[str, int]] = {}

    def on_market_data(self, order_id: str = None) -> int:
        """Mark market data arrival."""
        start = self.monitor.start_timer()
        if order_id:
            self.order_timings[order_id] = {'market_data': start}
        return start

    def on_signal_calculated(self, order_id: str, start: int):
        """Mark signal calculation complete."""
        self.monitor.record('signal_calculation', start)
        if order_id in self.order_timings:
            self.order_timings[order_id]['signal'] = time.perf_counter_ns()

    def on_order_created(self, order_id: str, start: int):
        """Mark order creation complete."""
        self.monitor.record('order_creation', start)
        self.order_timings[order_id]['created'] = time.perf_counter_ns()

    def on_order_submitted(self, order_id: str, start: int):
        """Mark order submission complete."""
        self.monitor.record('order_submission', start)
        self.order_timings[order_id]['submitted'] = time.perf_counter_ns()

    def on_order_acked(self, order_id: str, start: int):
        """Mark order acknowledgment received."""
        self.monitor.record('order_ack', start)
        if order_id in self.order_timings:
            self.order_timings[order_id]['acked'] = time.perf_counter_ns()

    def on_fill(self, order_id: str):
        """Mark fill received."""
        if order_id in self.order_timings:
            self.order_timings[order_id]['filled'] = time.perf_counter_ns()

    def get_order_latency_breakdown(self, order_id: str) -> Dict:
        """Get latency breakdown for a specific order."""
        if order_id not in self.order_timings:
            return {}

        timings = self.order_timings[order_id]
        breakdown = {}

        stages = ['market_data', 'signal', 'created', 'submitted', 'acked', 'filled']
        for i, stage in enumerate(stages[:-1]):
            if stage in timings and stages[i+1] in timings:
                breakdown[f'{stage}_to_{stages[i+1]}'] = (
                    timings[stages[i+1]] - timings[stage]
                ) / 1000  # Convert to microseconds

        if 'market_data' in timings and 'submitted' in timings:
            breakdown['total_decision_latency_us'] = (
                timings['submitted'] - timings['market_data']
            ) / 1000

        if 'submitted' in timings and 'filled' in timings:
            breakdown['round_trip_latency_us'] = (
                timings['filled'] - timings['submitted']
            ) / 1000

        return breakdown

    def get_summary(self) -> Dict:
        """Get summary of all latency metrics."""
        return {
            'stats': self.monitor.get_all_stats(),
            'breakdown': self.monitor.get_latency_breakdown(),
            'alerts': list(self.monitor.alerts)[-10:]  # Last 10 alerts
        }
