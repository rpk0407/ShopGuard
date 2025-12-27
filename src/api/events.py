"""
Event System

Event-driven architecture for the trading system:
- Decoupled components
- Async event handling
- Event sourcing support
"""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
from enum import Enum
from collections import defaultdict
import threading
import queue


class EventType(Enum):
    """Core event types."""
    # Market events
    TICK = "tick"
    BAR = "bar"
    QUOTE = "quote"
    TRADE = "trade"

    # Order events
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIALLY_FILLED = "order_partially_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"

    # Position events
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"

    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_EXPIRED = "signal_expired"

    # Risk events
    RISK_LIMIT_BREACH = "risk_limit_breach"
    DRAWDOWN_WARNING = "drawdown_warning"
    KILL_SWITCH_TRIGGERED = "kill_switch_triggered"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class Event:
    """Base event class."""
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    data: Dict = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.event_type, str):
            self.event_type = EventType(self.event_type)


# Specific event types for type safety

@dataclass
class TickEvent(Event):
    """Market tick event."""
    symbol: str = ""
    price: float = 0.0
    volume: int = 0

    def __post_init__(self):
        self.event_type = EventType.TICK
        self.data = {
            'symbol': self.symbol,
            'price': self.price,
            'volume': self.volume
        }


@dataclass
class OrderEvent(Event):
    """Order-related event."""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: int = 0
    price: float = 0.0

    def __post_init__(self):
        self.data = {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price
        }


@dataclass
class SignalEvent(Event):
    """Signal event."""
    symbol: str = ""
    direction: float = 0.0
    strength: float = 0.0
    strategy: str = ""

    def __post_init__(self):
        self.event_type = EventType.SIGNAL_GENERATED
        self.data = {
            'symbol': self.symbol,
            'direction': self.direction,
            'strength': self.strength,
            'strategy': self.strategy
        }


EventHandler = Callable[[Event], None]


class EventBus:
    """
    Central event bus for the trading system.

    Provides:
    - Pub/sub event distribution
    - Sync and async handling
    - Event filtering
    - Event replay
    """

    def __init__(self, async_mode: bool = False):
        """
        Initialize event bus.

        Args:
            async_mode: If True, events are processed in background thread
        """
        self.async_mode = async_mode

        # Handlers by event type
        self._handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)

        # Catch-all handlers
        self._global_handlers: List[EventHandler] = []

        # Event history for replay
        self._history: List[Event] = []
        self._history_size = 10000

        # Async queue
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._lock = threading.Lock()

        # Stats
        self._stats = {
            'events_published': 0,
            'events_handled': 0,
            'errors': 0
        }

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler
    ):
        """Subscribe to an event type."""
        with self._lock:
            self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler):
        """Subscribe to all events."""
        with self._lock:
            self._global_handlers.append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler
    ):
        """Unsubscribe from an event type."""
        with self._lock:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

    def publish(self, event: Event):
        """Publish an event."""
        self._stats['events_published'] += 1

        # Store in history
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]

        if self.async_mode:
            self._queue.put(event)
        else:
            self._dispatch(event)

    def _dispatch(self, event: Event):
        """Dispatch event to handlers."""
        handlers = []

        with self._lock:
            # Type-specific handlers
            handlers.extend(self._handlers.get(event.event_type, []))
            # Global handlers
            handlers.extend(self._global_handlers)

        for handler in handlers:
            try:
                handler(event)
                self._stats['events_handled'] += 1
            except Exception as e:
                self._stats['errors'] += 1

    def start(self):
        """Start async event processing."""
        if not self.async_mode or self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop async event processing."""
        self._running = False
        if self._thread:
            self._queue.put(None)  # Sentinel to unblock
            self._thread.join(timeout=5)

    def _process_loop(self):
        """Background event processing loop."""
        while self._running:
            try:
                event = self._queue.get(timeout=1)
                if event is None:
                    break
                self._dispatch(event)
            except queue.Empty:
                continue

    def replay(
        self,
        start: datetime = None,
        end: datetime = None,
        event_types: List[EventType] = None
    ):
        """Replay historical events."""
        with self._lock:
            events = self._history.copy()

        for event in events:
            # Filter by time
            if start and event.timestamp < start:
                continue
            if end and event.timestamp > end:
                continue

            # Filter by type
            if event_types and event.event_type not in event_types:
                continue

            self._dispatch(event)

    def get_history(
        self,
        event_type: EventType = None,
        limit: int = 100
    ) -> List[Event]:
        """Get event history."""
        with self._lock:
            events = self._history.copy()

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def get_stats(self) -> Dict:
        """Get event bus statistics."""
        return {
            **self._stats,
            'handlers': sum(len(h) for h in self._handlers.values()),
            'global_handlers': len(self._global_handlers),
            'history_size': len(self._history),
            'queue_size': self._queue.qsize() if self.async_mode else 0
        }


class EventSourced:
    """
    Mixin for event-sourced entities.

    Maintains state through event application.
    """

    def __init__(self):
        self._events: List[Event] = []
        self._version: int = 0

    def apply_event(self, event: Event):
        """Apply an event to update state."""
        self._events.append(event)
        self._version += 1
        self._handle_event(event)

    def _handle_event(self, event: Event):
        """Override to handle specific events."""
        pass

    def get_events(self) -> List[Event]:
        """Get all applied events."""
        return self._events.copy()

    @property
    def version(self) -> int:
        """Get current version."""
        return self._version

    def rebuild_from_events(self, events: List[Event]):
        """Rebuild state from event history."""
        self._events = []
        self._version = 0
        for event in events:
            self.apply_event(event)
