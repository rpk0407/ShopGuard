"""
Strategy Framework

Base classes and interfaces for trading strategies:
- Strategy lifecycle management
- Signal generation
- Position management
- Risk controls
"""

import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum


class StrategyState(Enum):
    """Strategy lifecycle states."""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class Signal:
    """Trading signal."""
    symbol: str
    direction: float  # -1 (short) to +1 (long)
    strength: float  # 0 to 1
    confidence: float  # 0 to 1
    timestamp: datetime = field(default_factory=datetime.now)
    expiry: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        if self.expiry is None:
            return True
        return datetime.now() < self.expiry

    @property
    def target_position(self) -> float:
        """Normalized target position (-1 to 1)."""
        return self.direction * self.strength * self.confidence


@dataclass
class StrategyContext:
    """
    Context provided to strategies.

    Contains market data, positions, and system state.
    """
    timestamp: datetime
    prices: Dict[str, float]
    positions: Dict[str, int]
    cash: float
    equity: float
    market_data: Dict[str, Any] = field(default_factory=dict)

    def get_price(self, symbol: str) -> Optional[float]:
        return self.prices.get(symbol)

    def get_position(self, symbol: str) -> int:
        return self.positions.get(symbol, 0)

    def get_exposure(self, symbol: str) -> float:
        pos = self.get_position(symbol)
        price = self.get_price(symbol)
        if price is None:
            return 0.0
        return abs(pos * price)


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    name: str
    version: str = "1.0"
    symbols: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    max_position_pct: float = 0.1  # Max position as % of equity
    max_order_pct: float = 0.05  # Max order as % of equity
    cooldown_seconds: float = 0.0  # Min time between signals


class Strategy(ABC):
    """
    Base class for trading strategies.

    Strategies generate signals based on market data.
    The execution layer handles order management.
    """

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.state = StrategyState.CREATED
        self._last_signal_time: Dict[str, datetime] = {}
        self._signals: List[Signal] = []

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def symbols(self) -> List[str]:
        return self.config.symbols

    def initialize(self, context: StrategyContext):
        """Initialize strategy. Override for custom initialization."""
        self.state = StrategyState.INITIALIZING
        self.on_initialize(context)
        self.state = StrategyState.RUNNING

    def on_initialize(self, context: StrategyContext):
        """Override for custom initialization logic."""
        pass

    @abstractmethod
    def on_data(self, context: StrategyContext) -> List[Signal]:
        """
        Process new market data and generate signals.

        Must be implemented by subclasses.
        """
        pass

    def generate_signals(self, context: StrategyContext) -> List[Signal]:
        """Generate signals with cooldown and validation."""
        if self.state != StrategyState.RUNNING:
            return []

        try:
            raw_signals = self.on_data(context)

            # Apply cooldown
            filtered_signals = []
            for signal in raw_signals:
                last_time = self._last_signal_time.get(signal.symbol)
                if last_time:
                    elapsed = (context.timestamp - last_time).total_seconds()
                    if elapsed < self.config.cooldown_seconds:
                        continue

                filtered_signals.append(signal)
                self._last_signal_time[signal.symbol] = context.timestamp

            self._signals.extend(filtered_signals)
            return filtered_signals

        except Exception as e:
            self.state = StrategyState.ERROR
            return []

    def pause(self):
        """Pause strategy."""
        if self.state == StrategyState.RUNNING:
            self.state = StrategyState.PAUSED

    def resume(self):
        """Resume strategy."""
        if self.state == StrategyState.PAUSED:
            self.state = StrategyState.RUNNING

    def stop(self):
        """Stop strategy."""
        self.state = StrategyState.STOPPING
        self.on_stop()
        self.state = StrategyState.STOPPED

    def on_stop(self):
        """Override for cleanup logic."""
        pass

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Get a strategy parameter."""
        return self.config.parameters.get(name, default)


class SignalGenerator:
    """
    Manages multiple strategies and aggregates signals.
    """

    def __init__(self):
        self.strategies: Dict[str, Strategy] = {}
        self._weights: Dict[str, float] = {}

    def add_strategy(self, strategy: Strategy, weight: float = 1.0):
        """Add a strategy."""
        self.strategies[strategy.name] = strategy
        self._weights[strategy.name] = weight

    def remove_strategy(self, name: str):
        """Remove a strategy."""
        if name in self.strategies:
            self.strategies[name].stop()
            del self.strategies[name]
            del self._weights[name]

    def initialize_all(self, context: StrategyContext):
        """Initialize all strategies."""
        for strategy in self.strategies.values():
            strategy.initialize(context)

    def generate_signals(self, context: StrategyContext) -> Dict[str, Signal]:
        """
        Generate and aggregate signals from all strategies.

        Returns combined signal per symbol.
        """
        all_signals: Dict[str, List[tuple]] = {}  # symbol -> [(signal, weight)]

        for name, strategy in self.strategies.items():
            if strategy.state != StrategyState.RUNNING:
                continue

            weight = self._weights[name]
            signals = strategy.generate_signals(context)

            for signal in signals:
                if signal.symbol not in all_signals:
                    all_signals[signal.symbol] = []
                all_signals[signal.symbol].append((signal, weight))

        # Aggregate signals per symbol
        combined: Dict[str, Signal] = {}

        for symbol, signals_weights in all_signals.items():
            if not signals_weights:
                continue

            total_weight = sum(w for _, w in signals_weights)
            if total_weight == 0:
                continue

            # Weighted average
            direction = sum(s.direction * w for s, w in signals_weights) / total_weight
            strength = sum(s.strength * w for s, w in signals_weights) / total_weight
            confidence = sum(s.confidence * w for s, w in signals_weights) / total_weight

            combined[symbol] = Signal(
                symbol=symbol,
                direction=np.clip(direction, -1, 1),
                strength=np.clip(strength, 0, 1),
                confidence=np.clip(confidence, 0, 1),
                timestamp=context.timestamp,
                metadata={'strategies': [s.symbol for s, _ in signals_weights]}
            )

        return combined

    def pause_all(self):
        """Pause all strategies."""
        for strategy in self.strategies.values():
            strategy.pause()

    def resume_all(self):
        """Resume all strategies."""
        for strategy in self.strategies.values():
            strategy.resume()

    def stop_all(self):
        """Stop all strategies."""
        for strategy in self.strategies.values():
            strategy.stop()


# Example strategy implementations

class MomentumStrategy(Strategy):
    """Simple momentum strategy example."""

    def on_initialize(self, context: StrategyContext):
        self.lookback = self.get_parameter('lookback', 20)
        self.threshold = self.get_parameter('threshold', 0.02)
        self.price_history: Dict[str, List[float]] = {
            s: [] for s in self.symbols
        }

    def on_data(self, context: StrategyContext) -> List[Signal]:
        signals = []

        for symbol in self.symbols:
            price = context.get_price(symbol)
            if price is None:
                continue

            self.price_history[symbol].append(price)

            # Keep only lookback period
            if len(self.price_history[symbol]) > self.lookback:
                self.price_history[symbol] = self.price_history[symbol][-self.lookback:]

            if len(self.price_history[symbol]) < self.lookback:
                continue

            # Calculate momentum
            returns = (price - self.price_history[symbol][0]) / self.price_history[symbol][0]

            if abs(returns) > self.threshold:
                signals.append(Signal(
                    symbol=symbol,
                    direction=1.0 if returns > 0 else -1.0,
                    strength=min(1.0, abs(returns) / self.threshold),
                    confidence=0.6,
                    timestamp=context.timestamp
                ))

        return signals


class MeanReversionStrategy(Strategy):
    """Simple mean reversion strategy example."""

    def on_initialize(self, context: StrategyContext):
        self.lookback = self.get_parameter('lookback', 20)
        self.num_std = self.get_parameter('num_std', 2.0)
        self.price_history: Dict[str, List[float]] = {
            s: [] for s in self.symbols
        }

    def on_data(self, context: StrategyContext) -> List[Signal]:
        signals = []

        for symbol in self.symbols:
            price = context.get_price(symbol)
            if price is None:
                continue

            self.price_history[symbol].append(price)

            if len(self.price_history[symbol]) > self.lookback:
                self.price_history[symbol] = self.price_history[symbol][-self.lookback:]

            if len(self.price_history[symbol]) < self.lookback:
                continue

            prices = np.array(self.price_history[symbol])
            mean = np.mean(prices)
            std = np.std(prices)

            if std == 0:
                continue

            z_score = (price - mean) / std

            if abs(z_score) > self.num_std:
                # Mean reversion: go opposite of deviation
                signals.append(Signal(
                    symbol=symbol,
                    direction=-1.0 if z_score > 0 else 1.0,
                    strength=min(1.0, abs(z_score) / (self.num_std * 2)),
                    confidence=0.5,
                    timestamp=context.timestamp
                ))

        return signals
