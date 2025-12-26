"""
Kill Switch - Independent Emergency Circuit Breaker

THIS IS THE MOST IMPORTANT SAFETY SYSTEM.

The kill switch operates INDEPENDENTLY of the main trading system.
It monitors for catastrophic conditions and can:
1. Cancel all orders
2. Flatten all positions
3. Halt the trading system
4. Send emergency alerts

DESIGN PRINCIPLES:
1. INDEPENDENCE: Separate process/thread from main system
2. SIMPLICITY: Minimal code, minimal dependencies
3. MULTIPLE TRIGGERS: Various failure modes covered
4. IRREVERSIBILITY: Once triggered, requires manual reset
5. ALERTING: Multiple notification channels

NEVER disable the kill switch. EVER.
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
import json


class KillSwitchTrigger(Enum):
    """Reasons for kill switch activation."""
    MANUAL = "manual"                      # Manually triggered
    DRAWDOWN = "drawdown"                  # Exceeded max drawdown
    DAILY_LOSS = "daily_loss"              # Exceeded daily loss limit
    POSITION_LOSS = "position_loss"        # Single position loss limit
    RAPID_LOSS = "rapid_loss"              # Too much loss too fast
    EXPOSURE_BREACH = "exposure_breach"    # Exposure limits exceeded
    VOLATILITY_SPIKE = "volatility_spike"  # Market volatility too high
    DATA_FAILURE = "data_failure"          # Market data feed failure
    EXECUTION_FAILURE = "execution_failure" # Execution system failure
    LATENCY_SPIKE = "latency_spike"        # Execution latency too high
    CONNECTIVITY_LOSS = "connectivity"     # Lost connection to venue
    RECONCILIATION = "reconciliation"      # Position mismatch detected
    EXTERNAL = "external"                  # External kill signal


class KillSwitchState(Enum):
    """Kill switch states."""
    ARMED = "armed"          # Active and monitoring
    TRIGGERED = "triggered"  # Kill switch activated
    DISARMED = "disarmed"    # Disabled (DANGEROUS)


@dataclass
class KillSwitchConfig:
    """
    Kill switch configuration.

    IMPORTANT: These are LAST RESORT limits.
    They should be wider than normal trading limits.
    If these trigger, something has gone VERY wrong.
    """
    # Loss limits
    max_drawdown: float = 0.15              # 15% drawdown triggers kill
    max_daily_loss_pct: float = 0.05        # 5% daily loss triggers kill
    max_rapid_loss_pct: float = 0.03        # 3% loss in 5 minutes
    rapid_loss_window_sec: float = 300.0    # 5 minute window

    # Exposure limits
    max_gross_exposure: float = 3.0         # 300% gross exposure
    max_net_exposure: float = 1.5           # 150% net exposure

    # Market limits
    max_vix_level: float = 50.0             # VIX > 50 triggers kill
    max_spread_multiple: float = 10.0       # 10x normal spread

    # Technical limits
    max_latency_ms: float = 1000.0          # 1 second max latency
    max_data_age_sec: float = 30.0          # 30 seconds stale data
    max_order_rejects: int = 10             # 10 consecutive rejects

    # Monitoring
    check_interval_sec: float = 1.0         # How often to check
    heartbeat_timeout_sec: float = 10.0     # Heartbeat timeout

    # Actions
    cancel_all_on_trigger: bool = True      # Cancel all orders
    flatten_on_trigger: bool = True         # Close all positions
    alert_channels: List[str] = field(default_factory=lambda: ["log", "email"])


@dataclass
class KillSwitchEvent:
    """Record of kill switch event."""
    timestamp: datetime
    trigger: KillSwitchTrigger
    reason: str
    metrics: Dict[str, Any]
    actions_taken: List[str]


class KillSwitch:
    """
    Independent emergency circuit breaker.

    This system runs independently and monitors for catastrophic conditions.
    When triggered, it immediately halts all trading activity.
    """

    def __init__(self, config: KillSwitchConfig = None):
        self.config = config or KillSwitchConfig()
        self.state = KillSwitchState.ARMED

        # Monitoring state
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._last_heartbeat: datetime = datetime.now()

        # Metrics to monitor
        self._metrics: Dict[str, Any] = {}
        self._metrics_lock = threading.Lock()

        # Event history
        self.events: List[KillSwitchEvent] = []

        # Loss tracking for rapid loss detection
        self._portfolio_values: List[tuple] = []  # [(timestamp, value), ...]

        # Order reject tracking
        self._recent_rejects: int = 0

        # Callbacks (set by main system)
        self.on_trigger: Optional[Callable[[KillSwitchTrigger, str], None]] = None
        self.cancel_all_orders: Optional[Callable[[], None]] = None
        self.flatten_positions: Optional[Callable[[], None]] = None
        self.send_alert: Optional[Callable[[str, str], None]] = None

    def start(self):
        """Start kill switch monitoring."""
        if self.state == KillSwitchState.DISARMED:
            raise RuntimeError("Cannot start disarmed kill switch")

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="KillSwitch",
            daemon=False  # NOT daemon - must complete
        )
        self._monitor_thread.start()

    def stop(self):
        """Stop monitoring (does NOT disarm)."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10.0)

    def arm(self):
        """Arm the kill switch."""
        self.state = KillSwitchState.ARMED
        self._log("Kill switch ARMED")

    def disarm(self, confirmation: str):
        """
        Disarm the kill switch. DANGEROUS.

        Requires explicit confirmation string.
        """
        if confirmation != "I_UNDERSTAND_THE_RISKS":
            raise ValueError("Invalid confirmation. Kill switch NOT disarmed.")

        self.state = KillSwitchState.DISARMED
        self._log("WARNING: Kill switch DISARMED")

    def trigger(self, reason: KillSwitchTrigger, message: str):
        """
        Trigger the kill switch.

        This is the nuclear option. All trading stops.
        """
        if self.state == KillSwitchState.DISARMED:
            self._log(f"Kill switch DISARMED, ignoring trigger: {reason.value}")
            return

        if self.state == KillSwitchState.TRIGGERED:
            self._log(f"Kill switch already triggered, new reason: {reason.value}")
            return

        self.state = KillSwitchState.TRIGGERED
        actions_taken = []

        self._log(f"KILL SWITCH TRIGGERED: {reason.value} - {message}")

        # Cancel all orders
        if self.config.cancel_all_on_trigger:
            if self.cancel_all_orders:
                try:
                    self.cancel_all_orders()
                    actions_taken.append("cancelled_all_orders")
                except Exception as e:
                    self._log(f"ERROR cancelling orders: {e}")

        # Flatten positions
        if self.config.flatten_on_trigger:
            if self.flatten_positions:
                try:
                    self.flatten_positions()
                    actions_taken.append("flattened_positions")
                except Exception as e:
                    self._log(f"ERROR flattening positions: {e}")

        # Send alerts
        for channel in self.config.alert_channels:
            if self.send_alert:
                try:
                    self.send_alert(
                        channel,
                        f"KILL SWITCH TRIGGERED: {reason.value}\n{message}"
                    )
                    actions_taken.append(f"alert_sent_{channel}")
                except Exception as e:
                    self._log(f"ERROR sending alert to {channel}: {e}")

        # Record event
        with self._metrics_lock:
            event = KillSwitchEvent(
                timestamp=datetime.now(),
                trigger=reason,
                reason=message,
                metrics=self._metrics.copy(),
                actions_taken=actions_taken
            )
            self.events.append(event)

        # Call trigger callback
        if self.on_trigger:
            self.on_trigger(reason, message)

    def manual_trigger(self, reason: str = "Manual activation"):
        """Manually trigger the kill switch."""
        self.trigger(KillSwitchTrigger.MANUAL, reason)

    def reset(self, confirmation: str):
        """
        Reset kill switch after trigger.

        Requires confirmation and manual review.
        """
        if confirmation != "REVIEWED_AND_UNDERSTOOD":
            raise ValueError("Invalid confirmation. Review the cause before resetting.")

        if self.state != KillSwitchState.TRIGGERED:
            raise ValueError("Kill switch is not triggered")

        self._log("Kill switch RESET - monitoring resumed")
        self.state = KillSwitchState.ARMED

    def update_metrics(self, metrics: Dict[str, Any]):
        """
        Update metrics for monitoring.

        Called by main system to provide current state.
        """
        with self._metrics_lock:
            self._metrics.update(metrics)
            self._metrics["last_update"] = datetime.now()

        # Update heartbeat
        self._last_heartbeat = datetime.now()

        # Track portfolio value for rapid loss detection
        if "portfolio_value" in metrics:
            self._portfolio_values.append(
                (datetime.now(), metrics["portfolio_value"])
            )
            # Keep only recent values
            cutoff = datetime.now() - timedelta(seconds=self.config.rapid_loss_window_sec * 2)
            self._portfolio_values = [
                (t, v) for t, v in self._portfolio_values if t > cutoff
            ]

    def report_order_reject(self):
        """Report an order rejection."""
        self._recent_rejects += 1
        if self._recent_rejects >= self.config.max_order_rejects:
            self.trigger(
                KillSwitchTrigger.EXECUTION_FAILURE,
                f"{self._recent_rejects} consecutive order rejects"
            )

    def report_order_success(self):
        """Report successful order (resets reject counter)."""
        self._recent_rejects = 0

    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._running and self.state == KillSwitchState.ARMED:
            try:
                self._check_all_conditions()
                time.sleep(self.config.check_interval_sec)
            except Exception as e:
                self._log(f"Monitoring error: {e}")
                # Don't crash - keep monitoring

    def _check_all_conditions(self):
        """Check all kill switch conditions."""
        with self._metrics_lock:
            metrics = self._metrics.copy()

        if not metrics:
            return

        # Check heartbeat
        self._check_heartbeat()

        # Check drawdown
        self._check_drawdown(metrics)

        # Check daily loss
        self._check_daily_loss(metrics)

        # Check rapid loss
        self._check_rapid_loss()

        # Check exposure
        self._check_exposure(metrics)

        # Check data freshness
        self._check_data_freshness(metrics)

        # Check latency
        self._check_latency(metrics)

    def _check_heartbeat(self):
        """Check if main system is responding."""
        age = (datetime.now() - self._last_heartbeat).total_seconds()
        if age > self.config.heartbeat_timeout_sec:
            self.trigger(
                KillSwitchTrigger.CONNECTIVITY_LOSS,
                f"No heartbeat for {age:.1f} seconds"
            )

    def _check_drawdown(self, metrics: Dict):
        """Check for excessive drawdown."""
        drawdown = metrics.get("current_drawdown", 0)
        if drawdown > self.config.max_drawdown:
            self.trigger(
                KillSwitchTrigger.DRAWDOWN,
                f"Drawdown {drawdown:.1%} exceeds {self.config.max_drawdown:.1%}"
            )

    def _check_daily_loss(self, metrics: Dict):
        """Check for excessive daily loss."""
        daily_pnl_pct = metrics.get("daily_pnl_pct", 0)
        if daily_pnl_pct < -self.config.max_daily_loss_pct:
            self.trigger(
                KillSwitchTrigger.DAILY_LOSS,
                f"Daily loss {-daily_pnl_pct:.1%} exceeds {self.config.max_daily_loss_pct:.1%}"
            )

    def _check_rapid_loss(self):
        """Check for rapid loss."""
        if len(self._portfolio_values) < 2:
            return

        now = datetime.now()
        window_start = now - timedelta(seconds=self.config.rapid_loss_window_sec)

        # Get value at window start
        start_value = None
        for t, v in self._portfolio_values:
            if t >= window_start:
                if start_value is None:
                    start_value = v
                break
            start_value = v

        if start_value is None or start_value == 0:
            return

        current_value = self._portfolio_values[-1][1]
        loss_pct = (start_value - current_value) / start_value

        if loss_pct > self.config.max_rapid_loss_pct:
            self.trigger(
                KillSwitchTrigger.RAPID_LOSS,
                f"Lost {loss_pct:.1%} in {self.config.rapid_loss_window_sec/60:.0f} minutes"
            )

    def _check_exposure(self, metrics: Dict):
        """Check for excessive exposure."""
        gross = metrics.get("gross_exposure", 0)
        net = abs(metrics.get("net_exposure", 0))

        if gross > self.config.max_gross_exposure:
            self.trigger(
                KillSwitchTrigger.EXPOSURE_BREACH,
                f"Gross exposure {gross:.1%} exceeds {self.config.max_gross_exposure:.1%}"
            )

        if net > self.config.max_net_exposure:
            self.trigger(
                KillSwitchTrigger.EXPOSURE_BREACH,
                f"Net exposure {net:.1%} exceeds {self.config.max_net_exposure:.1%}"
            )

    def _check_data_freshness(self, metrics: Dict):
        """Check if market data is stale."""
        data_age = metrics.get("data_age_sec", 0)
        if data_age > self.config.max_data_age_sec:
            self.trigger(
                KillSwitchTrigger.DATA_FAILURE,
                f"Market data {data_age:.1f}s old, max {self.config.max_data_age_sec:.1f}s"
            )

    def _check_latency(self, metrics: Dict):
        """Check execution latency."""
        latency = metrics.get("execution_latency_ms", 0)
        if latency > self.config.max_latency_ms:
            self.trigger(
                KillSwitchTrigger.LATENCY_SPIKE,
                f"Execution latency {latency:.0f}ms exceeds {self.config.max_latency_ms:.0f}ms"
            )

    def _log(self, message: str):
        """Log a message."""
        timestamp = datetime.now().isoformat()
        print(f"[KILLSWITCH {timestamp}] {message}")

    def get_status(self) -> Dict:
        """Get current kill switch status."""
        with self._metrics_lock:
            return {
                "state": self.state.value,
                "armed": self.state == KillSwitchState.ARMED,
                "triggered": self.state == KillSwitchState.TRIGGERED,
                "last_heartbeat": self._last_heartbeat.isoformat(),
                "recent_rejects": self._recent_rejects,
                "events_count": len(self.events),
                "last_event": self.events[-1].trigger.value if self.events else None,
                "current_metrics": self._metrics
            }


# =============================================================================
# KILL SWITCH BEST PRACTICES
# =============================================================================

"""
KILL SWITCH IMPLEMENTATION CHECKLIST:

1. INDEPENDENCE
   - Run in separate process/thread
   - Don't share memory with main system
   - Have independent data feeds if possible
   - Separate network path if possible

2. SIMPLICITY
   - Minimal dependencies
   - No complex logic
   - Clear, auditable conditions
   - No machine learning or adaptation

3. REDUNDANCY
   - Multiple trigger conditions
   - Multiple alert channels
   - Backup kill mechanisms
   - Manual override always available

4. TESTING
   - Test kill switch regularly (weekly)
   - Simulate each trigger condition
   - Verify cancellation works
   - Verify flattening works
   - Test alert delivery

5. DOCUMENTATION
   - Document all trigger conditions
   - Document reset procedures
   - Document who can reset
   - Post-mortem for every trigger

6. MONITORING
   - Monitor kill switch health
   - Alert if kill switch itself fails
   - Audit log all interactions
   - Heartbeat verification

NEVER:
- Disable the kill switch in production
- Tune limits too tight (false positives)
- Ignore kill switch events
- Auto-reset without review
"""
