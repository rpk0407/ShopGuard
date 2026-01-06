"""
Candle (OHLCV) Data Structures

Aggregates trades into candles for higher timeframe analysis.
Used for ATR calculation and divergence detection.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Deque, Callable
from collections import deque
from datetime import datetime
from enum import Enum

from .trades import Trade, TradeSide


@dataclass
class Candle:
    """
    OHLCV candle with extended metrics.

    Includes CVD (delta) for order flow analysis.
    """
    timestamp: int  # Candle open time (milliseconds)
    open: float
    high: float
    low: float
    close: float
    volume: float

    # Extended metrics for order flow
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    trade_count: int = 0

    # Candle metadata
    timeframe: str = "1m"  # e.g., "1m", "5m", "1h"
    is_complete: bool = False

    @property
    def delta(self) -> float:
        """Volume delta (buy - sell)."""
        return self.buy_volume - self.sell_volume

    @property
    def range(self) -> float:
        """High - Low range."""
        return self.high - self.low

    @property
    def body(self) -> float:
        """Candle body size (absolute)."""
        return abs(self.close - self.open)

    @property
    def body_ratio(self) -> float:
        """Body to range ratio."""
        if self.range == 0:
            return 0.0
        return self.body / self.range

    @property
    def is_bullish(self) -> bool:
        """True if close > open."""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """True if close < open."""
        return self.close < self.open

    @property
    def upper_wick(self) -> float:
        """Upper wick size."""
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        """Lower wick size."""
        return min(self.open, self.close) - self.low

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.timestamp / 1000)

    @property
    def vwap(self) -> float:
        """Typical price (HLC average)."""
        return (self.high + self.low + self.close) / 3

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'buy_volume': self.buy_volume,
            'sell_volume': self.sell_volume,
            'delta': self.delta,
            'trade_count': self.trade_count,
            'timeframe': self.timeframe,
            'is_complete': self.is_complete,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Candle':
        return cls(
            timestamp=data['timestamp'],
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            volume=data['volume'],
            buy_volume=data.get('buy_volume', 0.0),
            sell_volume=data.get('sell_volume', 0.0),
            trade_count=data.get('trade_count', 0),
            timeframe=data.get('timeframe', '1m'),
            is_complete=data.get('is_complete', True),
        )


# Timeframe to milliseconds mapping
TIMEFRAME_MS = {
    '1m': 60 * 1000,
    '3m': 3 * 60 * 1000,
    '5m': 5 * 60 * 1000,
    '15m': 15 * 60 * 1000,
    '30m': 30 * 60 * 1000,
    '1h': 60 * 60 * 1000,
    '4h': 4 * 60 * 60 * 1000,
    '1d': 24 * 60 * 60 * 1000,
}


class CandleAggregator:
    """
    Aggregates trades into candles.

    Builds candles in real-time from trade stream.
    Supports multiple timeframes simultaneously.
    """

    def __init__(
        self,
        timeframe: str = "1m",
        max_candles: int = 1000,
        on_candle_complete: Optional[Callable[[Candle], None]] = None
    ):
        """
        Initialize candle aggregator.

        Args:
            timeframe: Candle timeframe (e.g., "1m", "5m", "1h")
            max_candles: Maximum candles to keep in memory
            on_candle_complete: Callback when candle closes
        """
        if timeframe not in TIMEFRAME_MS:
            raise ValueError(f"Unknown timeframe: {timeframe}. Valid: {list(TIMEFRAME_MS.keys())}")

        self.timeframe = timeframe
        self.timeframe_ms = TIMEFRAME_MS[timeframe]
        self.max_candles = max_candles
        self.on_candle_complete = on_candle_complete

        # Completed candles
        self._candles: Deque[Candle] = deque(maxlen=max_candles)

        # Current (incomplete) candle
        self._current: Optional[Candle] = None

    def add_trade(self, trade: Trade) -> Optional[Candle]:
        """
        Process a trade and update candles.

        Args:
            trade: Trade to process

        Returns:
            Completed candle if this trade closed a candle, else None
        """
        # Calculate candle start time (floor to timeframe)
        candle_start = (trade.timestamp // self.timeframe_ms) * self.timeframe_ms

        completed_candle = None

        # Check if we need to start a new candle
        if self._current is None:
            # First candle
            self._current = self._create_candle(candle_start, trade)
        elif candle_start > self._current.timestamp:
            # New candle - close current one
            self._current.is_complete = True
            completed_candle = self._current
            self._candles.append(completed_candle)

            # Callback
            if self.on_candle_complete:
                self.on_candle_complete(completed_candle)

            # Start new candle
            self._current = self._create_candle(candle_start, trade)
        else:
            # Update current candle
            self._update_candle(self._current, trade)

        return completed_candle

    def _create_candle(self, timestamp: int, trade: Trade) -> Candle:
        """Create new candle from first trade."""
        return Candle(
            timestamp=timestamp,
            open=trade.price,
            high=trade.price,
            low=trade.price,
            close=trade.price,
            volume=trade.size,
            buy_volume=trade.size if trade.side == TradeSide.BUY else 0.0,
            sell_volume=trade.size if trade.side == TradeSide.SELL else 0.0,
            trade_count=1,
            timeframe=self.timeframe,
            is_complete=False,
        )

    def _update_candle(self, candle: Candle, trade: Trade) -> None:
        """Update candle with new trade."""
        candle.high = max(candle.high, trade.price)
        candle.low = min(candle.low, trade.price)
        candle.close = trade.price
        candle.volume += trade.size
        candle.trade_count += 1

        if trade.side == TradeSide.BUY:
            candle.buy_volume += trade.size
        else:
            candle.sell_volume += trade.size

    @property
    def candles(self) -> List[Candle]:
        """All completed candles."""
        return list(self._candles)

    @property
    def current_candle(self) -> Optional[Candle]:
        """Current incomplete candle."""
        return self._current

    def get_closes(self, n: Optional[int] = None) -> List[float]:
        """Get closing prices."""
        candles = self.candles
        if n is not None:
            candles = candles[-n:]
        return [c.close for c in candles]

    def get_highs(self, n: Optional[int] = None) -> List[float]:
        """Get high prices."""
        candles = self.candles
        if n is not None:
            candles = candles[-n:]
        return [c.high for c in candles]

    def get_lows(self, n: Optional[int] = None) -> List[float]:
        """Get low prices."""
        candles = self.candles
        if n is not None:
            candles = candles[-n:]
        return [c.low for c in candles]

    def get_volumes(self, n: Optional[int] = None) -> List[float]:
        """Get volumes."""
        candles = self.candles
        if n is not None:
            candles = candles[-n:]
        return [c.volume for c in candles]

    def get_deltas(self, n: Optional[int] = None) -> List[float]:
        """Get CVD deltas per candle."""
        candles = self.candles
        if n is not None:
            candles = candles[-n:]
        return [c.delta for c in candles]

    def get_cvd_series(self, n: Optional[int] = None) -> List[float]:
        """Get cumulative CVD series from candles."""
        deltas = self.get_deltas(n)
        cvd = []
        running = 0.0
        for d in deltas:
            running += d
            cvd.append(running)
        return cvd

    def reset(self) -> None:
        """Reset all state."""
        self._candles.clear()
        self._current = None

    def __len__(self) -> int:
        return len(self._candles)
