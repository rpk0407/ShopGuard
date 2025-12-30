"""
THE NERVOUS SYSTEM - Alert & Event System
==========================================
Propagates signals and events throughout the organism.

Features:
- Multi-level alerts (info, warning, critical)
- Event bus for component communication
- Signal aggregation
- Alert history
- Notification channels
"""

import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from collections import deque
from queue import Queue
import json

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class EventType(Enum):
    """System event types"""
    # Trading events
    SIGNAL_GENERATED = "signal_generated"
    ORDER_CREATED = "order_created"
    ORDER_FILLED = "order_filled"
    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"

    # Risk events
    DRAWDOWN_WARNING = "drawdown_warning"
    CIRCUIT_BREAKER = "circuit_breaker"
    POSITION_LIMIT = "position_limit"

    # Market events
    REGIME_CHANGE = "regime_change"
    VOLATILITY_SPIKE = "volatility_spike"
    PRICE_ALERT = "price_alert"

    # Evolution events
    GENERATION_COMPLETE = "generation_complete"
    ALPHA_EVOLVED = "alpha_evolved"
    BRAIN_UPDATED = "brain_updated"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    ERROR = "error"
    HEALTH_CHECK = "health_check"


@dataclass
class Alert:
    """Single alert/notification"""
    alert_id: str
    level: AlertLevel
    event_type: EventType
    title: str
    message: str
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    data: Dict = field(default_factory=dict)
    acknowledged: bool = False

    def to_dict(self) -> Dict:
        return {
            'id': self.alert_id,
            'level': self.level.value,
            'event_type': self.event_type.value,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp,
            'source': self.source,
            'data': self.data,
            'acknowledged': self.acknowledged
        }


class AlertSystem:
    """
    THE NERVOUS SYSTEM
    ==================
    Central event bus and alert management.

    Responsibilities:
    - Route events between components
    - Generate and store alerts
    - Notify subscribers
    - Aggregate signals
    """

    def __init__(self, max_history: int = 1000):
        # Alert storage
        self.alerts: deque = deque(maxlen=max_history)
        self.unacknowledged: Dict[str, Alert] = {}

        # Event subscribers
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self.global_subscribers: List[Callable] = []

        # Event queue for async processing
        self.event_queue: Queue = Queue()

        # Stats
        self.alert_counts: Dict[AlertLevel, int] = {level: 0 for level in AlertLevel}
        self.event_counts: Dict[EventType, int] = {event: 0 for event in EventType}

        # Threading
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Alert counter
        self._alert_counter = 0

        logger.info("🔔 Alert System (Nervous System) initialized")

    def start(self):
        """Start the event processor"""
        if self._running:
            return

        self._running = True
        self._processor_thread = threading.Thread(target=self._process_events, daemon=True)
        self._processor_thread.start()

        self.emit(EventType.SYSTEM_START, "System Started", "Alert system initialized")
        logger.info("🔔 Alert system started")

    def stop(self):
        """Stop the event processor"""
        self.emit(EventType.SYSTEM_STOP, "System Stopped", "Alert system shutting down")
        self._running = False

        if self._processor_thread:
            self._processor_thread.join(timeout=2)

        logger.info("🔔 Alert system stopped")

    def subscribe(self, event_type: EventType, callback: Callable[[Alert], None]):
        """Subscribe to a specific event type"""
        with self._lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self.subscribers[event_type].append(callback)

        logger.debug(f"🔔 Subscribed to {event_type.value}")

    def subscribe_all(self, callback: Callable[[Alert], None]):
        """Subscribe to all events"""
        with self._lock:
            self.global_subscribers.append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unsubscribe from an event type"""
        with self._lock:
            if event_type in self.subscribers:
                self.subscribers[event_type] = [
                    cb for cb in self.subscribers[event_type] if cb != callback
                ]

    def emit(
        self,
        event_type: EventType,
        title: str,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        source: str = "",
        data: Dict = None
    ) -> Alert:
        """Emit an event/alert"""
        with self._lock:
            self._alert_counter += 1
            alert_id = f"alert_{self._alert_counter}_{int(time.time())}"

        alert = Alert(
            alert_id=alert_id,
            level=level,
            event_type=event_type,
            title=title,
            message=message,
            source=source,
            data=data or {}
        )

        # Store alert
        with self._lock:
            self.alerts.append(alert)
            self.alert_counts[level] += 1
            self.event_counts[event_type] += 1

            if level in [AlertLevel.WARNING, AlertLevel.CRITICAL, AlertLevel.EMERGENCY]:
                self.unacknowledged[alert_id] = alert

        # Queue for async processing
        self.event_queue.put(alert)

        # Log based on level
        log_msg = f"🔔 [{level.value.upper()}] {title}: {message}"
        if level == AlertLevel.EMERGENCY:
            logger.critical(log_msg)
        elif level == AlertLevel.CRITICAL:
            logger.error(log_msg)
        elif level == AlertLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return alert

    def _process_events(self):
        """Background event processor"""
        while self._running:
            try:
                alert = self.event_queue.get(timeout=0.5)

                # Notify subscribers
                with self._lock:
                    # Specific subscribers
                    if alert.event_type in self.subscribers:
                        for callback in self.subscribers[alert.event_type]:
                            try:
                                callback(alert)
                            except Exception as e:
                                logger.error(f"Subscriber error: {e}")

                    # Global subscribers
                    for callback in self.global_subscribers:
                        try:
                            callback(alert)
                        except Exception as e:
                            logger.error(f"Global subscriber error: {e}")

            except:
                continue  # Timeout, continue loop

    def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        with self._lock:
            if alert_id in self.unacknowledged:
                self.unacknowledged[alert_id].acknowledged = True
                del self.unacknowledged[alert_id]
                return True
            return False

    def acknowledge_all(self):
        """Acknowledge all alerts"""
        with self._lock:
            for alert in self.unacknowledged.values():
                alert.acknowledged = True
            self.unacknowledged.clear()

    # =========================================
    # CONVENIENCE METHODS FOR COMMON ALERTS
    # =========================================

    def signal_alert(
        self,
        signal_type: str,
        asset: str,
        confidence: float,
        price: float,
        source: str = "TitanBrain"
    ):
        """Emit a trading signal alert"""
        self.emit(
            EventType.SIGNAL_GENERATED,
            f"Signal: {signal_type}",
            f"{asset} @ ${price:.2f} (Confidence: {confidence*100:.0f}%)",
            level=AlertLevel.INFO,
            source=source,
            data={'signal': signal_type, 'asset': asset, 'confidence': confidence, 'price': price}
        )

    def trade_alert(
        self,
        action: str,  # "OPENED" or "CLOSED"
        asset: str,
        side: str,
        price: float,
        pnl: float = None
    ):
        """Emit a trade alert"""
        event_type = EventType.TRADE_OPENED if action == "OPENED" else EventType.TRADE_CLOSED
        message = f"{side} {asset} @ ${price:.2f}"

        if pnl is not None:
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            message += f" | P&L: {pnl_str}"

        self.emit(
            event_type,
            f"Trade {action}",
            message,
            level=AlertLevel.INFO,
            data={'asset': asset, 'side': side, 'price': price, 'pnl': pnl}
        )

    def risk_alert(
        self,
        alert_type: str,
        message: str,
        level: AlertLevel = AlertLevel.WARNING
    ):
        """Emit a risk management alert"""
        event_map = {
            'drawdown': EventType.DRAWDOWN_WARNING,
            'circuit_breaker': EventType.CIRCUIT_BREAKER,
            'position_limit': EventType.POSITION_LIMIT
        }

        event_type = event_map.get(alert_type, EventType.DRAWDOWN_WARNING)

        self.emit(
            event_type,
            f"Risk Alert: {alert_type.upper()}",
            message,
            level=level,
            source="RiskManager"
        )

    def regime_alert(
        self,
        asset: str,
        old_regime: str,
        new_regime: str
    ):
        """Emit a regime change alert"""
        self.emit(
            EventType.REGIME_CHANGE,
            "Regime Change",
            f"{asset}: {old_regime} → {new_regime}",
            level=AlertLevel.INFO,
            source="RegimeDetector",
            data={'asset': asset, 'old': old_regime, 'new': new_regime}
        )

    def evolution_alert(
        self,
        generation: int,
        best_fitness: float,
        alpha_updated: bool = False
    ):
        """Emit evolution progress alert"""
        if alpha_updated:
            self.emit(
                EventType.ALPHA_EVOLVED,
                "New Alpha!",
                f"Generation {generation} | Fitness: {best_fitness:.2f}",
                level=AlertLevel.INFO,
                source="Darwin"
            )
        else:
            self.emit(
                EventType.GENERATION_COMPLETE,
                f"Generation {generation}",
                f"Best Fitness: {best_fitness:.2f}",
                level=AlertLevel.DEBUG,
                source="Darwin"
            )

    def error_alert(self, source: str, error: str):
        """Emit an error alert"""
        self.emit(
            EventType.ERROR,
            f"Error in {source}",
            error,
            level=AlertLevel.CRITICAL,
            source=source
        )

    # =========================================
    # QUERY METHODS
    # =========================================

    def get_alerts(
        self,
        level: AlertLevel = None,
        event_type: EventType = None,
        limit: int = 50,
        unacknowledged_only: bool = False
    ) -> List[Alert]:
        """Query alerts with filters"""
        with self._lock:
            if unacknowledged_only:
                alerts = list(self.unacknowledged.values())
            else:
                alerts = list(self.alerts)

        # Apply filters
        if level:
            alerts = [a for a in alerts if a.level == level]
        if event_type:
            alerts = [a for a in alerts if a.event_type == event_type]

        # Sort by timestamp (newest first) and limit
        alerts.sort(key=lambda a: a.timestamp, reverse=True)

        return alerts[:limit]

    def get_unacknowledged_count(self) -> int:
        """Get count of unacknowledged alerts"""
        return len(self.unacknowledged)

    def get_stats(self) -> Dict:
        """Get alert system statistics"""
        return {
            'total_alerts': sum(self.alert_counts.values()),
            'by_level': {k.value: v for k, v in self.alert_counts.items()},
            'by_event': {k.value: v for k, v in self.event_counts.items() if v > 0},
            'unacknowledged': len(self.unacknowledged),
            'is_running': self._running
        }

    def clear_history(self):
        """Clear alert history"""
        with self._lock:
            self.alerts.clear()
            self.unacknowledged.clear()
            self.alert_counts = {level: 0 for level in AlertLevel}
            self.event_counts = {event: 0 for event in EventType}

        logger.info("🔔 Alert history cleared")


# Global instance for easy access
_global_alert_system: Optional[AlertSystem] = None


def get_alert_system() -> AlertSystem:
    """Get or create global alert system"""
    global _global_alert_system
    if _global_alert_system is None:
        _global_alert_system = AlertSystem()
    return _global_alert_system


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test alert system
    alerts = AlertSystem()
    alerts.start()

    # Subscribe to events
    def on_signal(alert: Alert):
        print(f"  [CALLBACK] Signal received: {alert.data}")

    alerts.subscribe(EventType.SIGNAL_GENERATED, on_signal)

    # Emit some alerts
    alerts.emit(EventType.SYSTEM_START, "Test", "Testing alert system")
    alerts.signal_alert("STRONG_BUY", "BTC/USDT", 0.85, 50000)
    alerts.trade_alert("OPENED", "BTC/USDT", "LONG", 50000)
    alerts.trade_alert("CLOSED", "BTC/USDT", "LONG", 51000, pnl=100)
    alerts.risk_alert("drawdown", "Drawdown at 8%", AlertLevel.WARNING)
    alerts.evolution_alert(5, 45.3, alpha_updated=True)

    # Wait for processing
    time.sleep(1)

    # Query alerts
    print("\n" + "="*60)
    print("ALERT SUMMARY")
    print("="*60)

    recent = alerts.get_alerts(limit=5)
    for alert in recent:
        print(f"  [{alert.level.value}] {alert.title}: {alert.message}")

    print(f"\nStats: {alerts.get_stats()}")

    alerts.stop()
