"""
Trend Following Strategies

Strategies that follow market trends:
- Simple trend following with moving averages
- Breakout strategies
- Channel breakout (Donchian)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
from typing import List, Dict, Optional
from collections import deque
from dataclasses import dataclass

from api.strategy import Strategy, StrategyConfig, Signal, StrategyContext


@dataclass
class TrendFollowingConfig(StrategyConfig):
    """Configuration for trend following"""
    fast_period: int = 10
    slow_period: int = 50
    atr_period: int = 14
    atr_multiplier: float = 2.0


class TrendFollowingStrategy(Strategy):
    """
    Moving Average Crossover Trend Following

    Logic:
    1. Calculate fast and slow moving averages
    2. Buy when fast MA crosses above slow MA (golden cross)
    3. Sell when fast MA crosses below slow MA (death cross)
    4. Use ATR for position sizing and stops

    Academic basis:
    - Faber (2007) "A Quantitative Approach to Tactical Asset Allocation"
    - Simple, robust, works across asset classes
    """

    def __init__(self, config: TrendFollowingConfig):
        super().__init__(config)
        self.config = config
        self.price_history: Dict[str, deque] = {
            s: deque(maxlen=max(config.fast_period, config.slow_period) + 10)
            for s in config.symbols
        }
        self.previous_cross: Dict[str, Optional[str]] = {s: None for s in config.symbols}

    def on_start(self):
        """Initialize"""
        self.log("Trend Following strategy started")
        self.log(f"Fast MA: {self.config.fast_period}, Slow MA: {self.config.slow_period}")

    def on_data(self, context: StrategyContext) -> List[Signal]:
        """Generate trend following signals"""
        signals = []

        for symbol in self.symbols:
            price = context.get_price(symbol)
            if price is None:
                continue

            self.price_history[symbol].append(price)

            # Need enough data
            if len(self.price_history[symbol]) < self.config.slow_period:
                continue

            # Calculate MAs
            prices = list(self.price_history[symbol])
            fast_ma = np.mean(prices[-self.config.fast_period:])
            slow_ma = np.mean(prices[-self.config.slow_period:])

            # Detect crossover
            current_cross = 'above' if fast_ma > slow_ma else 'below'
            previous_cross = self.previous_cross[symbol]

            position = context.get_position(symbol)

            # Golden cross - buy signal
            if current_cross == 'above' and previous_cross == 'below' and position == 0:
                signals.append(Signal(
                    symbol=symbol,
                    direction=1.0,
                    strength=0.8,
                    confidence=0.75,
                    metadata={
                        'reason': 'golden_cross',
                        'fast_ma': fast_ma,
                        'slow_ma': slow_ma
                    }
                ))

            # Death cross - sell signal
            elif current_cross == 'below' and previous_cross == 'above' and position > 0:
                signals.append(Signal(
                    symbol=symbol,
                    direction=-1.0,
                    strength=1.0,
                    confidence=0.8,
                    metadata={
                        'reason': 'death_cross',
                        'fast_ma': fast_ma,
                        'slow_ma': slow_ma
                    }
                ))

            self.previous_cross[symbol] = current_cross

        return signals

    def on_stop(self):
        """Cleanup"""
        self.log("Trend Following strategy stopped")


@dataclass
class BreakoutConfig(StrategyConfig):
    """Configuration for breakout strategy"""
    lookback_period: int = 20  # Donchian channel period
    atr_period: int = 14
    volume_threshold: float = 1.5  # Volume must be X times average


class BreakoutStrategy(Strategy):
    """
    Donchian Channel Breakout Strategy

    Logic:
    1. Calculate highest high and lowest low over lookback period
    2. Buy when price breaks above channel with volume confirmation
    3. Sell when price breaks below channel
    4. Use ATR for stops

    Academic basis:
    - Richard Donchian (Turtle Traders)
    - Captures strong momentum moves
    - Used by famous trend followers
    """

    def __init__(self, config: BreakoutConfig):
        super().__init__(config)
        self.config = config
        self.price_history: Dict[str, deque] = {
            s: deque(maxlen=config.lookback_period + 10) for s in config.symbols
        }
        self.volume_history: Dict[str, deque] = {
            s: deque(maxlen=config.lookback_period) for s in config.symbols
        }
        self.in_breakout: Dict[str, bool] = {s: False for s in config.symbols}

    def on_start(self):
        """Initialize"""
        self.log("Breakout strategy started")
        self.log(f"Donchian period: {self.config.lookback_period}")

    def on_data(self, context: StrategyContext) -> List[Signal]:
        """Generate breakout signals"""
        signals = []

        for symbol in self.symbols:
            price = context.get_price(symbol)
            if price is None:
                continue

            # Update history
            self.price_history[symbol].append(price)

            # Get volume (from market_data if available)
            volume = context.market_data.get(symbol, {}).get('volume', 0)
            if volume > 0:
                self.volume_history[symbol].append(volume)

            # Need enough data
            if len(self.price_history[symbol]) < self.config.lookback_period:
                continue

            # Calculate Donchian channel
            prices = list(self.price_history[symbol])
            channel_high = max(prices[-self.config.lookback_period:])
            channel_low = min(prices[-self.config.lookback_period:])
            channel_mid = (channel_high + channel_low) / 2

            # Check volume
            volumes = list(self.volume_history[symbol])
            avg_volume = np.mean(volumes) if volumes else 0
            volume_confirmed = volume >= avg_volume * self.config.volume_threshold if avg_volume > 0 else True

            position = context.get_position(symbol)

            # Upside breakout
            if price > channel_high and volume_confirmed and position == 0 and not self.in_breakout[symbol]:
                signals.append(Signal(
                    symbol=symbol,
                    direction=1.0,
                    strength=0.9,
                    confidence=0.8,
                    metadata={
                        'reason': 'upside_breakout',
                        'breakout_level': channel_high,
                        'volume_ratio': volume / avg_volume if avg_volume > 0 else 0
                    }
                ))
                self.in_breakout[symbol] = True

            # Downside breakout (exit)
            elif price < channel_low and position > 0:
                signals.append(Signal(
                    symbol=symbol,
                    direction=-1.0,
                    strength=1.0,
                    confidence=0.85,
                    metadata={
                        'reason': 'downside_breakout',
                        'breakdown_level': channel_low
                    }
                ))
                self.in_breakout[symbol] = False

            # Reset breakout flag if price returns to channel
            if channel_low < price < channel_high:
                self.in_breakout[symbol] = False

        return signals

    def on_stop(self):
        """Cleanup"""
        self.log("Breakout strategy stopped")
