"""
ATR (Average True Range) Calculator

Measures volatility for dynamic position sizing and stop placement.

True Range = max(
    High - Low,
    abs(High - Previous Close),
    abs(Low - Previous Close)
)

ATR = Smoothed average of True Range
"""
from dataclasses import dataclass
from typing import List, Optional
from collections import deque
import logging

from ..config.constants import ATR_PERIOD, ATR_SMOOTHING
from ..data.candles import Candle

logger = logging.getLogger(__name__)


@dataclass
class ATRValue:
    """ATR value with metadata."""
    atr: float
    atr_percent: float  # ATR as % of price
    true_range: float   # Most recent TR
    timestamp: int

    def to_dict(self) -> dict:
        return {
            'atr': round(self.atr, 4),
            'atr_percent': round(self.atr_percent, 4),
            'true_range': round(self.true_range, 4),
            'timestamp': self.timestamp,
        }


class ATRCalculator:
    """
    Average True Range calculator.

    Supports two smoothing methods:
    1. Wilder's smoothing (original, more responsive)
    2. EMA smoothing (standard)

    Usage:
        atr = ATRCalculator(period=14)
        for candle in candles:
            atr.update(candle)
        current_atr = atr.current_atr
    """

    def __init__(
        self,
        period: int = ATR_PERIOD,
        smoothing: str = ATR_SMOOTHING
    ):
        """
        Initialize ATR calculator.

        Args:
            period: ATR period (default 14)
            smoothing: 'wilder' or 'ema'
        """
        if smoothing not in ['wilder', 'ema']:
            raise ValueError(f"Unknown smoothing method: {smoothing}")

        self.period = period
        self.smoothing = smoothing

        # State
        self._prev_close: Optional[float] = None
        self._tr_history: deque = deque(maxlen=period * 2)
        self._atr: Optional[float] = None
        self._last_candle: Optional[Candle] = None

        # For Wilder's smoothing
        self._wilder_multiplier = 1 / period

        # For EMA smoothing
        self._ema_multiplier = 2 / (period + 1)

        logger.debug("ATR Calculator initialized: period=%d, smoothing=%s", period, smoothing)

    def update(self, candle: Candle) -> Optional[ATRValue]:
        """
        Update ATR with new candle.

        Args:
            candle: OHLCV candle

        Returns:
            ATRValue if enough data, else None
        """
        # Calculate True Range
        tr = self._calculate_true_range(candle)
        self._tr_history.append(tr)

        # Update previous close for next calculation
        self._prev_close = candle.close
        self._last_candle = candle

        # Need at least `period` TR values
        if len(self._tr_history) < self.period:
            return None

        # Calculate ATR
        if self._atr is None:
            # First ATR = simple average
            self._atr = sum(list(self._tr_history)[-self.period:]) / self.period
        else:
            # Smoothed ATR
            if self.smoothing == 'wilder':
                # Wilder's smoothing: ATR = ((period-1) * prev_ATR + TR) / period
                self._atr = ((self.period - 1) * self._atr + tr) / self.period
            else:
                # EMA smoothing
                self._atr = (tr - self._atr) * self._ema_multiplier + self._atr

        return ATRValue(
            atr=self._atr,
            atr_percent=(self._atr / candle.close) if candle.close > 0 else 0,
            true_range=tr,
            timestamp=candle.timestamp
        )

    def _calculate_true_range(self, candle: Candle) -> float:
        """
        Calculate True Range for a candle.

        TR = max(
            High - Low,
            |High - Previous Close|,
            |Low - Previous Close|
        )
        """
        high_low = candle.high - candle.low

        if self._prev_close is None:
            # First candle - use high-low only
            return high_low

        high_prev = abs(candle.high - self._prev_close)
        low_prev = abs(candle.low - self._prev_close)

        return max(high_low, high_prev, low_prev)

    def update_batch(self, candles: List[Candle]) -> Optional[ATRValue]:
        """
        Update with multiple candles.

        Args:
            candles: List of candles (oldest first)

        Returns:
            Final ATRValue
        """
        result = None
        for candle in candles:
            result = self.update(candle)
        return result

    @property
    def current_atr(self) -> Optional[float]:
        """Get current ATR value."""
        return self._atr

    @property
    def current_atr_percent(self) -> Optional[float]:
        """Get current ATR as percentage of price."""
        if self._atr is None or self._last_candle is None:
            return None
        if self._last_candle.close <= 0:
            return None
        return self._atr / self._last_candle.close

    def get_atr_value(self) -> Optional[ATRValue]:
        """Get full ATR value object."""
        if self._atr is None or self._last_candle is None:
            return None

        return ATRValue(
            atr=self._atr,
            atr_percent=self.current_atr_percent or 0,
            true_range=list(self._tr_history)[-1] if self._tr_history else 0,
            timestamp=self._last_candle.timestamp
        )

    def calculate_stop_distance(self, multiplier: float = 1.5) -> Optional[float]:
        """
        Calculate stop loss distance in price terms.

        Args:
            multiplier: ATR multiplier (default 1.5)

        Returns:
            Stop distance in price units
        """
        if self._atr is None:
            return None
        return self._atr * multiplier

    def calculate_target_distance(self, multiplier: float = 3.0) -> Optional[float]:
        """
        Calculate take profit distance in price terms.

        Args:
            multiplier: ATR multiplier (default 3.0)

        Returns:
            Target distance in price units
        """
        if self._atr is None:
            return None
        return self._atr * multiplier

    def reset(self) -> None:
        """Reset calculator state."""
        self._prev_close = None
        self._tr_history.clear()
        self._atr = None
        self._last_candle = None
