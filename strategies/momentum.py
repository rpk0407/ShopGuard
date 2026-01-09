"""
Momentum Trading Strategies

Strategies based on momentum and trend-following principles:
- Simple momentum: Buy winners, sell losers
- Dual momentum: Combine absolute and relative momentum
- Cross-sectional momentum: Rank-based portfolio selection
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from api.strategy import Strategy, StrategyConfig, Signal, StrategyContext


@dataclass
class MomentumConfig(StrategyConfig):
    """Configuration for momentum strategy"""
    lookback_period: int = 20  # Days to look back for momentum
    holding_period: int = 5  # Days to hold positions
    num_positions: int = 5  # Number of concurrent positions
    momentum_threshold: float = 0.02  # Minimum momentum to trade
    rebalance_frequency: int = 5  # Days between rebalancing


class MomentumStrategy(Strategy):
    """
    Simple Momentum Strategy

    Logic:
    1. Calculate price momentum over lookback period
    2. Buy top N stocks with positive momentum > threshold
    3. Hold for holding period
    4. Rebalance periodically

    Academic basis:
    - Jegadeesh & Titman (1993) "Returns to Buying Winners and Selling Losers"
    - Momentum persists over 3-12 month horizons
    """

    def __init__(self, config: MomentumConfig):
        super().__init__(config)
        self.config = config
        self.price_history: Dict[str, List[float]] = {s: [] for s in config.symbols}
        self.last_rebalance = None
        self.entry_dates: Dict[str, datetime] = {}

    def on_start(self):
        """Initialize strategy"""
        self.log("Momentum strategy started")
        self.log(f"Tracking {len(self.symbols)} symbols")
        self.log(f"Lookback: {self.config.lookback_period} days")
        self.log(f"Top {self.config.num_positions} positions")

    def on_data(self, context: StrategyContext) -> List[Signal]:
        """Generate trading signals based on momentum"""
        signals = []

        # Update price history
        for symbol in self.symbols:
            price = context.get_price(symbol)
            if price is not None:
                self.price_history[symbol].append(price)
                # Keep only lookback period
                if len(self.price_history[symbol]) > self.config.lookback_period:
                    self.price_history[symbol].pop(0)

        # Check if we need to rebalance
        should_rebalance = False
        if self.last_rebalance is None:
            should_rebalance = True
        elif (context.timestamp - self.last_rebalance).days >= self.config.rebalance_frequency:
            should_rebalance = True

        if not should_rebalance:
            # Check for exits (holding period exceeded)
            signals.extend(self._check_exits(context))
            return signals

        # Calculate momentum for all symbols
        momentum_scores = {}
        for symbol in self.symbols:
            momentum = self._calculate_momentum(symbol)
            if momentum is not None:
                momentum_scores[symbol] = momentum

        if not momentum_scores:
            return signals

        # Rank by momentum
        ranked_symbols = sorted(
            momentum_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Select top N with positive momentum above threshold
        buy_candidates = [
            (symbol, score) for symbol, score in ranked_symbols
            if score > self.config.momentum_threshold
        ][:self.config.num_positions]

        # Current positions
        current_positions = {
            symbol for symbol, qty in context.positions.items()
            if qty != 0
        }

        # Exit positions not in buy list
        for symbol in current_positions:
            if symbol not in [s for s, _ in buy_candidates]:
                signals.append(Signal(
                    symbol=symbol,
                    direction=-1.0,
                    strength=1.0,
                    confidence=0.8,
                    metadata={'reason': 'momentum_exit', 'action': 'close'}
                ))

        # Enter new positions
        for symbol, momentum_score in buy_candidates:
            if symbol not in current_positions:
                # Calculate signal strength based on momentum magnitude
                strength = min(1.0, abs(momentum_score) / 0.10)  # Cap at 10% momentum

                signals.append(Signal(
                    symbol=symbol,
                    direction=1.0,
                    strength=strength,
                    confidence=0.75,
                    metadata={
                        'reason': 'momentum_entry',
                        'momentum_score': momentum_score,
                        'rank': buy_candidates.index((symbol, momentum_score)) + 1
                    }
                ))
                self.entry_dates[symbol] = context.timestamp

        self.last_rebalance = context.timestamp
        return signals

    def _calculate_momentum(self, symbol: str) -> Optional[float]:
        """Calculate price momentum"""
        prices = self.price_history.get(symbol, [])

        if len(prices) < self.config.lookback_period:
            return None

        # Simple momentum: (current - old) / old
        current_price = prices[-1]
        old_price = prices[0]

        if old_price == 0:
            return None

        momentum = (current_price - old_price) / old_price
        return momentum

    def _check_exits(self, context: StrategyContext) -> List[Signal]:
        """Check if we should exit based on holding period"""
        signals = []

        for symbol, entry_date in list(self.entry_dates.items()):
            # Check if holding period exceeded
            days_held = (context.timestamp - entry_date).days

            if days_held >= self.config.holding_period:
                position = context.get_position(symbol)
                if position != 0:
                    signals.append(Signal(
                        symbol=symbol,
                        direction=-1.0,
                        strength=1.0,
                        confidence=0.8,
                        metadata={
                            'reason': 'holding_period_exit',
                            'days_held': days_held
                        }
                    ))
                # Remove from entry dates
                del self.entry_dates[symbol]

        return signals

    def on_stop(self):
        """Cleanup when strategy stops"""
        self.log("Momentum strategy stopped")


class DualMomentumStrategy(Strategy):
    """
    Dual Momentum Strategy (Antonacci)

    Combines:
    1. Absolute momentum (time-series): Asset vs its own past
    2. Relative momentum (cross-sectional): Asset vs other assets

    Logic:
    - Calculate absolute momentum (12-month return)
    - If positive, calculate relative momentum vs peers
    - Invest in top relative momentum assets
    - If absolute momentum negative, go to cash/bonds

    Academic basis:
    - Antonacci (2014) "Dual Momentum Investing"
    - Combines trend-following with relative strength
    """

    def __init__(self, config: MomentumConfig):
        super().__init__(config)
        self.config = config
        self.price_history: Dict[str, List[float]] = {s: [] for s in config.symbols}
        self.last_rebalance = None

    def on_start(self):
        """Initialize strategy"""
        self.log("Dual Momentum strategy started")

    def on_data(self, context: StrategyContext) -> List[Signal]:
        """Generate dual momentum signals"""
        signals = []

        # Update price history
        for symbol in self.symbols:
            price = context.get_price(symbol)
            if price is not None:
                self.price_history[symbol].append(price)
                if len(self.price_history[symbol]) > 252:  # Keep 1 year
                    self.price_history[symbol].pop(0)

        # Check rebalance
        should_rebalance = (
            self.last_rebalance is None or
            (context.timestamp - self.last_rebalance).days >= self.config.rebalance_frequency
        )

        if not should_rebalance:
            return signals

        # Calculate absolute and relative momentum
        momentum_data = {}
        for symbol in self.symbols:
            absolute = self._calculate_absolute_momentum(symbol)
            relative = self._calculate_relative_momentum(symbol)

            if absolute is not None and relative is not None:
                momentum_data[symbol] = {
                    'absolute': absolute,
                    'relative': relative
                }

        if not momentum_data:
            return signals

        # Rank by relative momentum
        ranked = sorted(
            momentum_data.items(),
            key=lambda x: x[1]['relative'],
            reverse=True
        )

        # Select top N with positive absolute momentum
        buy_candidates = [
            symbol for symbol, data in ranked
            if data['absolute'] > 0
        ][:self.config.num_positions]

        # Current positions
        current_positions = {
            symbol for symbol, qty in context.positions.items()
            if qty != 0
        }

        # Exit positions not in buy list
        for symbol in current_positions:
            if symbol not in buy_candidates:
                signals.append(Signal(
                    symbol=symbol,
                    direction=-1.0,
                    strength=1.0,
                    confidence=0.85,
                    metadata={'reason': 'dual_momentum_exit'}
                ))

        # Enter new positions
        for symbol in buy_candidates:
            if symbol not in current_positions:
                data = momentum_data[symbol]

                # Confidence based on both absolute and relative strength
                confidence = 0.7 + 0.15 * min(1.0, data['absolute'] / 0.20)

                signals.append(Signal(
                    symbol=symbol,
                    direction=1.0,
                    strength=0.9,
                    confidence=confidence,
                    metadata={
                        'reason': 'dual_momentum_entry',
                        'absolute_momentum': data['absolute'],
                        'relative_momentum': data['relative']
                    }
                ))

        self.last_rebalance = context.timestamp
        return signals

    def _calculate_absolute_momentum(self, symbol: str) -> Optional[float]:
        """Calculate absolute momentum (12-month return)"""
        prices = self.price_history.get(symbol, [])

        if len(prices) < 252:  # Need 1 year
            return None

        current = prices[-1]
        year_ago = prices[-252]

        if year_ago == 0:
            return None

        return (current - year_ago) / year_ago

    def _calculate_relative_momentum(self, symbol: str) -> Optional[float]:
        """Calculate relative momentum vs all symbols"""
        my_momentum = self._calculate_absolute_momentum(symbol)
        if my_momentum is None:
            return None

        # Calculate average momentum of all symbols
        all_momentums = []
        for s in self.symbols:
            m = self._calculate_absolute_momentum(s)
            if m is not None:
                all_momentums.append(m)

        if not all_momentums:
            return None

        avg_momentum = np.mean(all_momentums)

        # Relative = my momentum - average momentum
        return my_momentum - avg_momentum

    def on_stop(self):
        """Cleanup"""
        self.log("Dual Momentum strategy stopped")
