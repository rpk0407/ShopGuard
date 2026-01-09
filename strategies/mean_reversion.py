"""
Mean Reversion Trading Strategies

Strategies based on mean reversion principles:
- Simple mean reversion: Price reverts to moving average
- Pairs trading: Statistical arbitrage between correlated pairs
- Bollinger Bands: Price reverts when exceeding bands
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from collections import deque

from api.strategy import Strategy, StrategyConfig, Signal, StrategyContext


@dataclass
class MeanReversionConfig(StrategyConfig):
    """Configuration for mean reversion strategy"""
    lookback_period: int = 20  # MA period
    entry_threshold: float = 2.0  # Standard deviations for entry
    exit_threshold: float = 0.5  # Standard deviations for exit
    max_holding_period: int = 10  # Maximum days to hold


class MeanReversionStrategy(Strategy):
    """
    Simple Mean Reversion Strategy

    Logic:
    1. Calculate moving average and standard deviation
    2. Buy when price < MA - threshold * StdDev
    3. Sell when price > MA + threshold * StdDev
    4. Exit when price returns to MA ± exit_threshold * StdDev

    Academic basis:
    - Poterba & Summers (1988) "Mean Reversion in Stock Returns"
    - Works best in range-bound markets
    - Complement to momentum strategies
    """

    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)
        self.config = config
        self.price_history: Dict[str, deque] = {
            s: deque(maxlen=config.lookback_period) for s in config.symbols
        }
        self.entry_prices: Dict[str, float] = {}
        self.entry_dates: Dict[str, datetime] = {}

    def on_start(self):
        """Initialize strategy"""
        self.log("Mean Reversion strategy started")
        self.log(f"Lookback: {self.config.lookback_period} periods")
        self.log(f"Entry threshold: {self.config.entry_threshold} std devs")

    def on_data(self, context: StrategyContext) -> List[Signal]:
        """Generate mean reversion signals"""
        signals = []

        for symbol in self.symbols:
            price = context.get_price(symbol)
            if price is None:
                continue

            # Update price history
            self.price_history[symbol].append(price)

            # Need enough data
            if len(self.price_history[symbol]) < self.config.lookback_period:
                continue

            # Calculate statistics
            prices = list(self.price_history[symbol])
            ma = np.mean(prices)
            std = np.std(prices)

            if std == 0:
                continue

            # Calculate z-score
            z_score = (price - ma) / std

            # Current position
            position = context.get_position(symbol)

            # Check for exit signals first
            if position != 0:
                exit_signal = self._check_exit(symbol, position, z_score, context)
                if exit_signal:
                    signals.append(exit_signal)
                continue

            # Check for entry signals
            entry_signal = self._check_entry(symbol, z_score, price, context)
            if entry_signal:
                signals.append(entry_signal)

        return signals

    def _check_entry(
        self,
        symbol: str,
        z_score: float,
        price: float,
        context: StrategyContext
    ) -> Optional[Signal]:
        """Check for mean reversion entry"""

        # Oversold - buy signal
        if z_score < -self.config.entry_threshold:
            self.entry_prices[symbol] = price
            self.entry_dates[symbol] = context.timestamp

            return Signal(
                symbol=symbol,
                direction=1.0,
                strength=min(1.0, abs(z_score) / 3.0),  # Stronger signal for larger deviation
                confidence=0.7,
                metadata={
                    'reason': 'mean_reversion_oversold',
                    'z_score': z_score,
                    'entry_price': price
                }
            )

        # Overbought - sell signal
        elif z_score > self.config.entry_threshold:
            self.entry_prices[symbol] = price
            self.entry_dates[symbol] = context.timestamp

            return Signal(
                symbol=symbol,
                direction=-1.0,
                strength=min(1.0, abs(z_score) / 3.0),
                confidence=0.7,
                metadata={
                    'reason': 'mean_reversion_overbought',
                    'z_score': z_score,
                    'entry_price': price
                }
            )

        return None

    def _check_exit(
        self,
        symbol: str,
        position: int,
        z_score: float,
        context: StrategyContext
    ) -> Optional[Signal]:
        """Check for mean reversion exit"""

        # Exit when price reverts to mean
        should_exit = False
        reason = ""

        if position > 0:  # Long position
            if z_score > -self.config.exit_threshold:
                should_exit = True
                reason = "mean_reversion_exit_long"
        elif position < 0:  # Short position
            if z_score < self.config.exit_threshold:
                should_exit = True
                reason = "mean_reversion_exit_short"

        # Also exit if holding period exceeded
        if symbol in self.entry_dates:
            days_held = (context.timestamp - self.entry_dates[symbol]).days
            if days_held >= self.config.max_holding_period:
                should_exit = True
                reason = "max_holding_period"

        if should_exit:
            # Clean up
            self.entry_prices.pop(symbol, None)
            self.entry_dates.pop(symbol, None)

            return Signal(
                symbol=symbol,
                direction=-1.0 if position > 0 else 1.0,
                strength=1.0,
                confidence=0.8,
                metadata={
                    'reason': reason,
                    'z_score': z_score
                }
            )

        return None

    def on_stop(self):
        """Cleanup"""
        self.log("Mean Reversion strategy stopped")


@dataclass
class PairsTradingConfig(StrategyConfig):
    """Configuration for pairs trading"""
    lookback_period: int = 60
    entry_threshold: float = 2.0
    exit_threshold: float = 0.5
    correlation_threshold: float = 0.7
    cointegration_threshold: float = 0.05


class PairsTradingStrategy(Strategy):
    """
    Statistical Arbitrage - Pairs Trading

    Logic:
    1. Find pairs of stocks that are cointegrated
    2. Calculate spread = price_A - beta * price_B
    3. Trade when spread deviates from mean
    4. Long undervalued, short overvalued
    5. Exit when spread reverts

    Academic basis:
    - Gatev, Goetzmann & Rouwenhorst (2006)
    - Statistical arbitrage in equity markets
    - Market-neutral strategy
    """

    def __init__(self, config: PairsTradingConfig):
        super().__init__(config)
        self.config = config
        self.price_history: Dict[str, deque] = {
            s: deque(maxlen=config.lookback_period * 2) for s in config.symbols
        }
        self.pairs: List[Tuple[str, str, float]] = []  # (sym1, sym2, hedge_ratio)
        self.spread_history: Dict[Tuple[str, str], deque] = {}
        self.pair_positions: Dict[Tuple[str, str], str] = {}  # 'long' or 'short'

    def on_start(self):
        """Initialize and find pairs"""
        self.log("Pairs Trading strategy started")
        self._find_pairs()
        self.log(f"Found {len(self.pairs)} cointegrated pairs")

    def _find_pairs(self):
        """Find cointegrated pairs (simplified)"""
        # In production, would use proper cointegration test (Engle-Granger, Johansen)
        # This is a simplified correlation-based approach

        from itertools import combinations

        for sym1, sym2 in combinations(self.symbols, 2):
            # Need price history to test
            if len(self.price_history[sym1]) < self.config.lookback_period:
                continue
            if len(self.price_history[sym2]) < self.config.lookback_period:
                continue

            prices1 = np.array(list(self.price_history[sym1]))
            prices2 = np.array(list(self.price_history[sym2]))

            # Calculate correlation
            correlation = np.corrcoef(prices1, prices2)[0, 1]

            if abs(correlation) >= self.config.correlation_threshold:
                # Calculate hedge ratio (beta)
                beta = np.cov(prices1, prices2)[0, 1] / np.var(prices2)

                self.pairs.append((sym1, sym2, beta))
                self.spread_history[(sym1, sym2)] = deque(
                    maxlen=self.config.lookback_period
                )

                self.log(f"Pair found: {sym1}/{sym2}, correlation={correlation:.2f}, beta={beta:.2f}")

    def on_data(self, context: StrategyContext) -> List[Signal]:
        """Generate pairs trading signals"""
        signals = []

        # Update price history
        for symbol in self.symbols:
            price = context.get_price(symbol)
            if price is not None:
                self.price_history[symbol].append(price)

        # Analyze each pair
        for sym1, sym2, beta in self.pairs:
            pair_signals = self._analyze_pair(sym1, sym2, beta, context)
            signals.extend(pair_signals)

        return signals

    def _analyze_pair(
        self,
        sym1: str,
        sym2: str,
        beta: float,
        context: StrategyContext
    ) -> List[Signal]:
        """Analyze a single pair for trading opportunities"""
        signals = []

        price1 = context.get_price(sym1)
        price2 = context.get_price(sym2)

        if price1 is None or price2 is None:
            return signals

        # Calculate spread
        spread = price1 - beta * price2
        self.spread_history[(sym1, sym2)].append(spread)

        if len(self.spread_history[(sym1, sym2)]) < self.config.lookback_period:
            return signals

        # Calculate spread statistics
        spreads = list(self.spread_history[(sym1, sym2)])
        mean_spread = np.mean(spreads)
        std_spread = np.std(spreads)

        if std_spread == 0:
            return signals

        # Z-score of current spread
        z_score = (spread - mean_spread) / std_spread

        pair = (sym1, sym2)
        current_position = self.pair_positions.get(pair)

        # Check for exit
        if current_position is not None:
            if abs(z_score) < self.config.exit_threshold:
                # Exit position
                if current_position == 'long':
                    # Close long sym1, short sym2
                    signals.append(Signal(sym1, -1.0, 1.0, 0.8, metadata={'reason': 'pairs_exit'}))
                    signals.append(Signal(sym2, 1.0, 1.0, 0.8, metadata={'reason': 'pairs_exit'}))
                else:  # short
                    # Close short sym1, long sym2
                    signals.append(Signal(sym1, 1.0, 1.0, 0.8, metadata={'reason': 'pairs_exit'}))
                    signals.append(Signal(sym2, -1.0, 1.0, 0.8, metadata={'reason': 'pairs_exit'}))

                del self.pair_positions[pair]

        # Check for entry
        else:
            if z_score > self.config.entry_threshold:
                # Spread too high - short sym1, long sym2
                signals.append(Signal(
                    sym1, -1.0, 0.5, 0.75,
                    metadata={'reason': 'pairs_entry_short', 'z_score': z_score}
                ))
                signals.append(Signal(
                    sym2, 1.0, 0.5, 0.75,
                    metadata={'reason': 'pairs_entry_long', 'z_score': z_score, 'hedge_ratio': beta}
                ))
                self.pair_positions[pair] = 'short'

            elif z_score < -self.config.entry_threshold:
                # Spread too low - long sym1, short sym2
                signals.append(Signal(
                    sym1, 1.0, 0.5, 0.75,
                    metadata={'reason': 'pairs_entry_long', 'z_score': z_score}
                ))
                signals.append(Signal(
                    sym2, -1.0, 0.5, 0.75,
                    metadata={'reason': 'pairs_entry_short', 'z_score': z_score, 'hedge_ratio': beta}
                ))
                self.pair_positions[pair] = 'long'

        return signals

    def on_stop(self):
        """Cleanup"""
        self.log("Pairs Trading strategy stopped")
