"""
Alert Management System

Monitors conditions and triggers alerts:
- P&L thresholds
- Risk limits
- System anomalies
- Trading errors

Fast detection and notification is critical
for risk management.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import threading
import time


class AlertLevel(Enum):
    """Alert severity levels."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """Single alert."""
    id: str
    level: AlertLevel
    rule_name: str
    message: str
    timestamp: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == AlertStatus.ACTIVE

    @property
    def duration(self) -> timedelta:
        end = self.resolved_at or datetime.now()
        return end - self.timestamp


@dataclass
class AlertRule:
    """
    Rule that triggers alerts.

    A rule consists of:
    - condition: Function that returns True if alert should fire
    - level: Severity level
    - cooldown: Minimum time between alerts
    - aggregation: How to handle multiple firings
    """
    name: str
    condition: Callable[[], bool]
    level: AlertLevel
    message_template: str
    cooldown_seconds: float = 60.0
    max_alerts_per_hour: int = 10
    auto_resolve: bool = True
    metadata_fn: Optional[Callable[[], Dict]] = None

    _last_fired: Optional[datetime] = field(default=None, init=False)
    _fire_count: int = field(default=0, init=False)


class AlertManager:
    """
    Manages alert rules, firing, and notifications.
    """

    def __init__(self, max_alerts: int = 10000):
        """
        Initialize alert manager.

        Args:
            max_alerts: Maximum alerts to keep in history
        """
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: deque = deque(maxlen=max_alerts)
        self.active_alerts: Dict[str, Alert] = {}

        # Notification handlers
        self.handlers: List[Callable[[Alert], None]] = []

        # Suppression
        self.suppressed_rules: set = set()
        self.global_suppression: bool = False

        # Thread safety
        self._lock = threading.Lock()

        # Alert ID counter
        self._alert_counter: int = 0

    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        with self._lock:
            self.rules[rule.name] = rule

    def remove_rule(self, name: str):
        """Remove an alert rule."""
        with self._lock:
            if name in self.rules:
                del self.rules[name]

    def add_handler(self, handler: Callable[[Alert], None]):
        """Add notification handler."""
        self.handlers.append(handler)

    def check_rules(self) -> List[Alert]:
        """
        Check all rules and fire alerts as needed.

        Call this periodically (e.g., every second).
        """
        if self.global_suppression:
            return []

        fired_alerts = []
        now = datetime.now()

        with self._lock:
            for name, rule in self.rules.items():
                if name in self.suppressed_rules:
                    continue

                # Check cooldown
                if rule._last_fired:
                    elapsed = (now - rule._last_fired).total_seconds()
                    if elapsed < rule.cooldown_seconds:
                        continue

                # Check rate limit
                if rule._fire_count >= rule.max_alerts_per_hour:
                    # Reset counter after an hour
                    if rule._last_fired and (now - rule._last_fired).total_seconds() > 3600:
                        rule._fire_count = 0
                    else:
                        continue

                # Evaluate condition
                try:
                    should_fire = rule.condition()
                except Exception as e:
                    # Rule evaluation error - fire an error alert
                    should_fire = False

                if should_fire:
                    alert = self._create_alert(rule)
                    fired_alerts.append(alert)

                    rule._last_fired = now
                    rule._fire_count += 1

                elif rule.auto_resolve:
                    # Check if we should auto-resolve
                    if name in self.active_alerts:
                        self._resolve_alert(name, "Auto-resolved: condition cleared")

        # Notify handlers
        for alert in fired_alerts:
            self._notify(alert)

        return fired_alerts

    def _create_alert(self, rule: AlertRule) -> Alert:
        """Create an alert from a rule."""
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter}"

        # Get metadata
        metadata = {}
        if rule.metadata_fn:
            try:
                metadata = rule.metadata_fn()
            except Exception:
                pass

        alert = Alert(
            id=alert_id,
            level=rule.level,
            rule_name=rule.name,
            message=rule.message_template.format(**metadata) if metadata else rule.message_template,
            timestamp=datetime.now(),
            metadata=metadata
        )

        self.alerts.append(alert)
        self.active_alerts[rule.name] = alert

        return alert

    def _resolve_alert(self, rule_name: str, reason: str = ""):
        """Resolve an active alert."""
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            if reason:
                alert.metadata['resolution_reason'] = reason
            del self.active_alerts[rule_name]

    def _notify(self, alert: Alert):
        """Notify all handlers of an alert."""
        for handler in self.handlers:
            try:
                handler(alert)
            except Exception:
                pass

    def acknowledge(self, alert_id: str):
        """Acknowledge an alert."""
        with self._lock:
            for rule_name, alert in self.active_alerts.items():
                if alert.id == alert_id:
                    alert.status = AlertStatus.ACKNOWLEDGED
                    alert.acknowledged_at = datetime.now()
                    break

    def resolve(self, alert_id: str, reason: str = ""):
        """Manually resolve an alert."""
        with self._lock:
            for rule_name, alert in list(self.active_alerts.items()):
                if alert.id == alert_id:
                    self._resolve_alert(rule_name, reason)
                    break

    def suppress_rule(self, rule_name: str):
        """Suppress a rule from firing."""
        self.suppressed_rules.add(rule_name)

    def unsuppress_rule(self, rule_name: str):
        """Unsuppress a rule."""
        self.suppressed_rules.discard(rule_name)

    def suppress_all(self):
        """Suppress all alerts globally."""
        self.global_suppression = True

    def unsuppress_all(self):
        """Unsuppress all alerts."""
        self.global_suppression = False

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        with self._lock:
            return list(self.active_alerts.values())

    def get_alerts_by_level(
        self,
        level: AlertLevel,
        since: datetime = None
    ) -> List[Alert]:
        """Get alerts at or above a level."""
        with self._lock:
            alerts = [
                a for a in self.alerts
                if a.level.value >= level.value
            ]

            if since:
                alerts = [a for a in alerts if a.timestamp >= since]

            return alerts

    def get_alert_stats(self, duration: timedelta = None) -> Dict:
        """Get alert statistics."""
        with self._lock:
            alerts = list(self.alerts)

        if duration:
            cutoff = datetime.now() - duration
            alerts = [a for a in alerts if a.timestamp >= cutoff]

        if not alerts:
            return {
                'total': 0,
                'by_level': {},
                'by_rule': {},
                'active': 0
            }

        by_level = {}
        for level in AlertLevel:
            count = sum(1 for a in alerts if a.level == level)
            if count > 0:
                by_level[level.name] = count

        by_rule = {}
        for alert in alerts:
            by_rule[alert.rule_name] = by_rule.get(alert.rule_name, 0) + 1

        return {
            'total': len(alerts),
            'by_level': by_level,
            'by_rule': by_rule,
            'active': len(self.active_alerts)
        }


def create_standard_rules(
    pnl_getter: Callable[[], float],
    drawdown_getter: Callable[[], float],
    position_getter: Callable[[], Dict],
    latency_getter: Callable[[], float]
) -> List[AlertRule]:
    """
    Create standard trading alert rules.

    Args:
        pnl_getter: Function to get current P&L
        drawdown_getter: Function to get current drawdown
        position_getter: Function to get positions
        latency_getter: Function to get latency

    Returns:
        List of standard alert rules
    """
    rules = []

    # P&L alerts
    rules.append(AlertRule(
        name="pnl_critical_loss",
        condition=lambda: pnl_getter() < -100000,  # $100K loss
        level=AlertLevel.CRITICAL,
        message_template="Critical P&L loss: ${pnl:,.2f}",
        cooldown_seconds=300,  # 5 min cooldown
        metadata_fn=lambda: {'pnl': pnl_getter()}
    ))

    rules.append(AlertRule(
        name="pnl_warning_loss",
        condition=lambda: pnl_getter() < -50000,  # $50K loss
        level=AlertLevel.WARNING,
        message_template="P&L warning: ${pnl:,.2f}",
        cooldown_seconds=600,
        metadata_fn=lambda: {'pnl': pnl_getter()}
    ))

    # Drawdown alerts
    rules.append(AlertRule(
        name="drawdown_critical",
        condition=lambda: drawdown_getter() > 0.10,  # 10% drawdown
        level=AlertLevel.CRITICAL,
        message_template="Critical drawdown: {drawdown:.1%}",
        cooldown_seconds=300,
        metadata_fn=lambda: {'drawdown': drawdown_getter()}
    ))

    rules.append(AlertRule(
        name="drawdown_warning",
        condition=lambda: drawdown_getter() > 0.05,  # 5% drawdown
        level=AlertLevel.WARNING,
        message_template="Drawdown warning: {drawdown:.1%}",
        cooldown_seconds=600,
        metadata_fn=lambda: {'drawdown': drawdown_getter()}
    ))

    # Position alerts
    rules.append(AlertRule(
        name="high_concentration",
        condition=lambda: any(
            abs(p.get('exposure', 0)) > 500000
            for p in position_getter().values()
        ),
        level=AlertLevel.WARNING,
        message_template="High position concentration detected",
        cooldown_seconds=300
    ))

    # Latency alerts
    rules.append(AlertRule(
        name="latency_critical",
        condition=lambda: latency_getter() > 10000,  # 10ms
        level=AlertLevel.ERROR,
        message_template="Critical latency: {latency:.0f}μs",
        cooldown_seconds=60,
        metadata_fn=lambda: {'latency': latency_getter()}
    ))

    rules.append(AlertRule(
        name="latency_warning",
        condition=lambda: latency_getter() > 5000,  # 5ms
        level=AlertLevel.WARNING,
        message_template="High latency: {latency:.0f}μs",
        cooldown_seconds=120,
        metadata_fn=lambda: {'latency': latency_getter()}
    ))

    return rules


class AlertNotifier:
    """
    Sends alert notifications via various channels.
    """

    def __init__(self):
        self.channels: Dict[str, Callable[[Alert], None]] = {}

    def add_channel(self, name: str, handler: Callable[[Alert], None]):
        """Add a notification channel."""
        self.channels[name] = handler

    def notify(self, alert: Alert, channels: List[str] = None):
        """Send notification to specified channels."""
        target_channels = channels or list(self.channels.keys())

        for channel_name in target_channels:
            if channel_name in self.channels:
                try:
                    self.channels[channel_name](alert)
                except Exception:
                    pass

    def console_handler(self, alert: Alert):
        """Print alert to console."""
        level_colors = {
            AlertLevel.DEBUG: "",
            AlertLevel.INFO: "",
            AlertLevel.WARNING: "⚠️ ",
            AlertLevel.ERROR: "❌ ",
            AlertLevel.CRITICAL: "🔥 "
        }

        prefix = level_colors.get(alert.level, "")
        print(f"{prefix}[{alert.level.name}] {alert.rule_name}: {alert.message}")

    def log_handler(self, alert: Alert, log_fn: Callable = print):
        """Log alert to logging system."""
        log_fn(f"ALERT [{alert.level.name}] {alert.rule_name}: {alert.message}")
