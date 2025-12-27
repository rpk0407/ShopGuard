"""
System Health Monitoring

Monitors health of all system components:
- Connectivity to exchanges
- Database connections
- Message queue health
- Memory/CPU usage
- Process health
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Single health check."""
    name: str
    check_fn: Callable[[], bool]
    timeout_seconds: float = 5.0
    critical: bool = False  # If True, unhealthy = system unhealthy
    description: str = ""


@dataclass
class HealthResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    latency_ms: float
    timestamp: datetime
    critical: bool = False


@dataclass
class ComponentHealth:
    """Health of a system component."""
    name: str
    status: HealthStatus
    checks: List[HealthResult]
    last_check: datetime
    uptime_pct: float  # Percentage of checks that passed


class SystemHealth:
    """
    Monitors overall system health.

    Performs periodic health checks on all components
    and maintains health history.
    """

    def __init__(
        self,
        check_interval_seconds: float = 10.0,
        history_size: int = 1000
    ):
        """
        Initialize system health monitor.

        Args:
            check_interval_seconds: How often to run checks
            history_size: Number of results to keep
        """
        self.check_interval = check_interval_seconds
        self.history_size = history_size

        # Health checks by component
        self.checks: Dict[str, List[HealthCheck]] = {}

        # Results history
        self.results: Dict[str, List[HealthResult]] = {}

        # Overall status
        self._overall_status: HealthStatus = HealthStatus.UNKNOWN
        self._last_check_time: Optional[datetime] = None

        # Background monitoring
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def register_check(
        self,
        component: str,
        check: HealthCheck
    ):
        """Register a health check for a component."""
        with self._lock:
            if component not in self.checks:
                self.checks[component] = []
                self.results[component] = []
            self.checks[component].append(check)

    def run_checks(self) -> Dict[str, ComponentHealth]:
        """Run all health checks and return results."""
        component_health = {}
        now = datetime.now()

        with self._lock:
            for component, checks in self.checks.items():
                results = []

                for check in checks:
                    result = self._run_single_check(check)
                    results.append(result)

                    # Store in history
                    if component not in self.results:
                        self.results[component] = []
                    if len(self.results[component]) >= self.history_size:
                        self.results[component].pop(0)
                    self.results[component].append(result)

                # Determine component status
                if any(r.status == HealthStatus.UNHEALTHY and r.critical for r in results):
                    status = HealthStatus.UNHEALTHY
                elif any(r.status == HealthStatus.UNHEALTHY for r in results):
                    status = HealthStatus.DEGRADED
                elif any(r.status == HealthStatus.DEGRADED for r in results):
                    status = HealthStatus.DEGRADED
                elif all(r.status == HealthStatus.HEALTHY for r in results):
                    status = HealthStatus.HEALTHY
                else:
                    status = HealthStatus.UNKNOWN

                # Calculate uptime
                history = self.results.get(component, [])
                if history:
                    healthy_count = sum(1 for r in history if r.status == HealthStatus.HEALTHY)
                    uptime = healthy_count / len(history) * 100
                else:
                    uptime = 100.0

                component_health[component] = ComponentHealth(
                    name=component,
                    status=status,
                    checks=results,
                    last_check=now,
                    uptime_pct=uptime
                )

            # Update overall status
            self._last_check_time = now
            self._update_overall_status(component_health)

        return component_health

    def _run_single_check(self, check: HealthCheck) -> HealthResult:
        """Run a single health check."""
        start = time.perf_counter()

        try:
            # Run with timeout
            result = self._run_with_timeout(check.check_fn, check.timeout_seconds)
            latency = (time.perf_counter() - start) * 1000

            if result:
                status = HealthStatus.HEALTHY
                message = "OK"
            else:
                status = HealthStatus.UNHEALTHY
                message = "Check failed"

        except TimeoutError:
            latency = check.timeout_seconds * 1000
            status = HealthStatus.UNHEALTHY
            message = f"Timeout after {check.timeout_seconds}s"

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            status = HealthStatus.UNHEALTHY
            message = f"Error: {str(e)}"

        return HealthResult(
            name=check.name,
            status=status,
            message=message,
            latency_ms=latency,
            timestamp=datetime.now(),
            critical=check.critical
        )

    def _run_with_timeout(
        self,
        fn: Callable,
        timeout: float
    ) -> bool:
        """Run a function with timeout."""
        result = [None]
        exception = [None]

        def target():
            try:
                result[0] = fn()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            raise TimeoutError()

        if exception[0]:
            raise exception[0]

        return result[0]

    def _update_overall_status(self, component_health: Dict[str, ComponentHealth]):
        """Update overall system status."""
        if not component_health:
            self._overall_status = HealthStatus.UNKNOWN
            return

        statuses = [c.status for c in component_health.values()]

        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            # Check if critical component is unhealthy
            for comp in component_health.values():
                if comp.status == HealthStatus.UNHEALTHY:
                    if any(r.critical for r in comp.checks if r.status == HealthStatus.UNHEALTHY):
                        self._overall_status = HealthStatus.UNHEALTHY
                        return
            self._overall_status = HealthStatus.DEGRADED
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            self._overall_status = HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            self._overall_status = HealthStatus.HEALTHY
        else:
            self._overall_status = HealthStatus.UNKNOWN

    def start_monitoring(self):
        """Start background health monitoring."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop_monitoring(self):
        """Stop background health monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                self.run_checks()
            except Exception:
                pass

            time.sleep(self.check_interval)

    def get_status(self) -> HealthStatus:
        """Get overall system health status."""
        return self._overall_status

    def get_component_status(self, component: str) -> Optional[HealthStatus]:
        """Get health status for a specific component."""
        with self._lock:
            if component in self.results and self.results[component]:
                latest = self.results[component][-1]
                return latest.status
        return None

    def get_uptime(self, component: str = None) -> float:
        """Get uptime percentage."""
        with self._lock:
            if component:
                history = self.results.get(component, [])
            else:
                # Overall uptime
                history = []
                for comp_results in self.results.values():
                    history.extend(comp_results)

            if not history:
                return 100.0

            healthy = sum(1 for r in history if r.status == HealthStatus.HEALTHY)
            return healthy / len(history) * 100

    def get_health_report(self) -> Dict:
        """Get comprehensive health report."""
        component_health = self.run_checks()

        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': self._overall_status.value,
            'components': {
                name: {
                    'status': comp.status.value,
                    'uptime_pct': comp.uptime_pct,
                    'last_check': comp.last_check.isoformat(),
                    'checks': [
                        {
                            'name': r.name,
                            'status': r.status.value,
                            'message': r.message,
                            'latency_ms': r.latency_ms,
                            'critical': r.critical
                        }
                        for r in comp.checks
                    ]
                }
                for name, comp in component_health.items()
            }
        }

    def format_report(self) -> str:
        """Format health report for display."""
        report = self.get_health_report()

        lines = []
        lines.append("=" * 60)
        lines.append("SYSTEM HEALTH REPORT")
        lines.append(f"Time: {report['timestamp']}")
        lines.append(f"Overall Status: {report['overall_status'].upper()}")
        lines.append("=" * 60)

        for comp_name, comp in report['components'].items():
            lines.append("")
            status_icon = {
                'healthy': '✓',
                'degraded': '!',
                'unhealthy': '✗',
                'unknown': '?'
            }.get(comp['status'], '?')

            lines.append(f"{status_icon} {comp_name} - {comp['status'].upper()}")
            lines.append(f"  Uptime: {comp['uptime_pct']:.1f}%")

            for check in comp['checks']:
                check_icon = '✓' if check['status'] == 'healthy' else '✗'
                critical_marker = ' [CRITICAL]' if check['critical'] else ''
                lines.append(f"    {check_icon} {check['name']}: {check['message']} ({check['latency_ms']:.1f}ms){critical_marker}")

        return "\n".join(lines)


def create_standard_checks() -> List[HealthCheck]:
    """Create standard health checks."""
    checks = []

    # Database check (placeholder)
    checks.append(HealthCheck(
        name="database",
        check_fn=lambda: True,  # Would check DB connection
        timeout_seconds=5.0,
        critical=True,
        description="Database connectivity"
    ))

    # Exchange connectivity (placeholder)
    checks.append(HealthCheck(
        name="exchange_connection",
        check_fn=lambda: True,  # Would check exchange API
        timeout_seconds=10.0,
        critical=True,
        description="Exchange API connectivity"
    ))

    # Market data (placeholder)
    checks.append(HealthCheck(
        name="market_data",
        check_fn=lambda: True,  # Would check market data feed
        timeout_seconds=5.0,
        critical=True,
        description="Market data feed"
    ))

    # Order management (placeholder)
    checks.append(HealthCheck(
        name="order_management",
        check_fn=lambda: True,  # Would check OMS
        timeout_seconds=5.0,
        critical=True,
        description="Order management system"
    ))

    # Risk system (placeholder)
    checks.append(HealthCheck(
        name="risk_system",
        check_fn=lambda: True,  # Would check risk engine
        timeout_seconds=5.0,
        critical=True,
        description="Risk management system"
    ))

    return checks
