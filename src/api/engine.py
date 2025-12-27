"""
Trading Engine

Central orchestrator for the trading system:
- Coordinates all components
- Main event loop
- System lifecycle management
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import threading
import time

from .strategy import Strategy, StrategyContext, SignalGenerator, Signal
from .events import EventBus, Event, EventType


class EngineState(Enum):
    """Engine lifecycle states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class EngineConfig:
    """Trading engine configuration."""
    name: str = "TradingEngine"
    tick_interval_ms: float = 100  # Main loop interval
    max_positions: int = 100
    max_order_rate: float = 10.0  # Orders per second
    enable_trading: bool = True
    paper_trading: bool = True
    log_level: str = "INFO"


class TradingEngine:
    """
    Main trading engine.

    Orchestrates:
    - Market data ingestion
    - Strategy signal generation
    - Order execution
    - Risk management
    - Monitoring
    """

    def __init__(self, config: EngineConfig):
        self.config = config
        self.state = EngineState.STOPPED

        # Core components
        self.event_bus = EventBus(async_mode=True)
        self.signal_generator = SignalGenerator()

        # State
        self._prices: Dict[str, float] = {}
        self._positions: Dict[str, int] = {}
        self._cash: float = 1_000_000.0
        self._equity: float = 1_000_000.0

        # Pending signals and orders
        self._pending_signals: List[Signal] = []

        # Thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Stats
        self._stats = {
            'ticks_processed': 0,
            'signals_generated': 0,
            'orders_sent': 0,
            'start_time': None
        }

        # Set up event handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up event handlers."""
        self.event_bus.subscribe(EventType.TICK, self._on_tick)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._on_fill)
        self.event_bus.subscribe(EventType.RISK_LIMIT_BREACH, self._on_risk_breach)

    def add_strategy(self, strategy: Strategy, weight: float = 1.0):
        """Add a trading strategy."""
        self.signal_generator.add_strategy(strategy, weight)

    def remove_strategy(self, name: str):
        """Remove a strategy."""
        self.signal_generator.remove_strategy(name)

    def start(self):
        """Start the trading engine."""
        if self.state == EngineState.RUNNING:
            return

        self.state = EngineState.STARTING
        self._stats['start_time'] = datetime.now()

        # Start event bus
        self.event_bus.start()

        # Initialize strategies
        context = self._create_context()
        self.signal_generator.initialize_all(context)

        # Start main loop
        self._running = True
        self._thread = threading.Thread(target=self._main_loop, daemon=True)
        self._thread.start()

        self.state = EngineState.RUNNING

        # Publish start event
        self.event_bus.publish(Event(
            event_type=EventType.SYSTEM_START,
            source="engine",
            data={'config': self.config.name}
        ))

    def stop(self):
        """Stop the trading engine."""
        if self.state == EngineState.STOPPED:
            return

        self.state = EngineState.STOPPING

        # Stop main loop
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        # Stop strategies
        self.signal_generator.stop_all()

        # Stop event bus
        self.event_bus.stop()

        self.state = EngineState.STOPPED

        # Publish stop event
        self.event_bus.publish(Event(
            event_type=EventType.SYSTEM_STOP,
            source="engine"
        ))

    def pause(self):
        """Pause trading."""
        if self.state == EngineState.RUNNING:
            self.state = EngineState.PAUSED
            self.signal_generator.pause_all()

    def resume(self):
        """Resume trading."""
        if self.state == EngineState.PAUSED:
            self.state = EngineState.RUNNING
            self.signal_generator.resume_all()

    def _main_loop(self):
        """Main engine loop."""
        interval = self.config.tick_interval_ms / 1000.0

        while self._running:
            try:
                if self.state == EngineState.RUNNING:
                    self._tick()

                time.sleep(interval)

            except Exception as e:
                self.state = EngineState.ERROR
                self.event_bus.publish(Event(
                    event_type=EventType.ERROR,
                    source="engine",
                    data={'error': str(e)}
                ))

    def _tick(self):
        """Process one tick of the engine."""
        self._stats['ticks_processed'] += 1

        # Create context
        context = self._create_context()

        # Generate signals
        signals = self.signal_generator.generate_signals(context)

        for symbol, signal in signals.items():
            self._stats['signals_generated'] += 1
            self._pending_signals.append(signal)

            # Publish signal event
            self.event_bus.publish(Event(
                event_type=EventType.SIGNAL_GENERATED,
                source="engine",
                data={
                    'symbol': symbol,
                    'direction': signal.direction,
                    'strength': signal.strength
                }
            ))

        # Process pending signals
        if self.config.enable_trading:
            self._process_signals()

        # Publish heartbeat
        if self._stats['ticks_processed'] % 100 == 0:
            self.event_bus.publish(Event(
                event_type=EventType.HEARTBEAT,
                source="engine",
                data={'ticks': self._stats['ticks_processed']}
            ))

    def _create_context(self) -> StrategyContext:
        """Create strategy context."""
        with self._lock:
            return StrategyContext(
                timestamp=datetime.now(),
                prices=self._prices.copy(),
                positions=self._positions.copy(),
                cash=self._cash,
                equity=self._equity
            )

    def _process_signals(self):
        """Process pending signals into orders."""
        while self._pending_signals:
            signal = self._pending_signals.pop(0)

            if not signal.is_valid:
                continue

            # Calculate target position
            target = self._calculate_target_position(signal)
            current = self._positions.get(signal.symbol, 0)

            order_qty = target - current

            if order_qty != 0:
                self._send_order(signal.symbol, order_qty)

    def _calculate_target_position(self, signal: Signal) -> int:
        """Calculate target position from signal."""
        max_position = self._equity * self.config.max_positions / 100
        price = self._prices.get(signal.symbol, 100)

        # Target shares based on signal
        target_value = signal.target_position * max_position
        target_shares = int(target_value / price)

        return target_shares

    def _send_order(self, symbol: str, quantity: int):
        """Send an order (simulated in paper trading mode)."""
        self._stats['orders_sent'] += 1

        if self.config.paper_trading:
            # Simulate immediate fill
            price = self._prices.get(symbol, 100)
            self._execute_fill(symbol, quantity, price)

    def _execute_fill(self, symbol: str, quantity: int, price: float):
        """Execute a fill."""
        with self._lock:
            # Update position
            current = self._positions.get(symbol, 0)
            self._positions[symbol] = current + quantity

            # Update cash
            self._cash -= quantity * price

            # Update equity
            self._update_equity()

        # Publish fill event
        self.event_bus.publish(Event(
            event_type=EventType.ORDER_FILLED,
            source="engine",
            data={
                'symbol': symbol,
                'quantity': quantity,
                'price': price
            }
        ))

    def _update_equity(self):
        """Update total equity."""
        position_value = sum(
            qty * self._prices.get(sym, 0)
            for sym, qty in self._positions.items()
        )
        self._equity = self._cash + position_value

    # Event handlers

    def _on_tick(self, event: Event):
        """Handle tick events."""
        symbol = event.data.get('symbol')
        price = event.data.get('price')

        if symbol and price:
            with self._lock:
                self._prices[symbol] = price
                self._update_equity()

    def _on_fill(self, event: Event):
        """Handle fill events."""
        pass  # Already handled in _execute_fill

    def _on_risk_breach(self, event: Event):
        """Handle risk breach events."""
        self.pause()

    # Public API

    def update_price(self, symbol: str, price: float):
        """Update a price."""
        self.event_bus.publish(Event(
            event_type=EventType.TICK,
            source="market_data",
            data={'symbol': symbol, 'price': price}
        ))

    def get_positions(self) -> Dict[str, int]:
        """Get current positions."""
        with self._lock:
            return self._positions.copy()

    def get_equity(self) -> float:
        """Get current equity."""
        with self._lock:
            return self._equity

    def get_stats(self) -> Dict:
        """Get engine statistics."""
        uptime = 0
        if self._stats['start_time']:
            uptime = (datetime.now() - self._stats['start_time']).total_seconds()

        return {
            **self._stats,
            'state': self.state.value,
            'uptime_seconds': uptime,
            'strategies': len(self.signal_generator.strategies),
            'positions': len(self._positions),
            'equity': self._equity,
            'event_stats': self.event_bus.get_stats()
        }

    def get_status(self) -> Dict:
        """Get engine status."""
        return {
            'name': self.config.name,
            'state': self.state.value,
            'trading_enabled': self.config.enable_trading,
            'paper_trading': self.config.paper_trading,
            'equity': self._equity,
            'cash': self._cash,
            'num_positions': len(self._positions),
            'num_strategies': len(self.signal_generator.strategies)
        }
