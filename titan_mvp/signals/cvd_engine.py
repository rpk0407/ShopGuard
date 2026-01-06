"""
CVD Engine (Micro-Cortex)

Detects order flow divergences between price and Cumulative Volume Delta.

This is the PRIMARY alpha source for the MVP strategy.

Theory:
- When price makes a Lower Low but CVD makes a Higher Low:
  → Sellers are exhausted, buyers are absorbing → BULLISH
- When price makes a Higher High but CVD makes a Lower High:
  → Buyers are exhausted, selling into strength → BEARISH

Implementation notes:
- Uses Z-score normalization for statistical significance
- Requires minimum divergence persistence (not just one candle)
- Grades divergence strength from 0-1
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import statistics
import logging

from ..config.constants import (
    CVD_LOOKBACK_CANDLES,
    CVD_DIVERGENCE_MIN_PERSISTENCE,
    CVD_ZSCORE_THRESHOLD,
    CVD_SMOOTHING_PERIOD,
    BULLISH_DIVERGENCE_MIN_DEPTH,
    BEARISH_DIVERGENCE_MIN_HEIGHT,
)
from ..data.candles import Candle

logger = logging.getLogger(__name__)


class DivergenceType(Enum):
    """Type of CVD-Price divergence."""
    NONE = "none"
    BULLISH = "bullish"       # Price LL, CVD HL → Buy signal
    BEARISH = "bearish"       # Price HH, CVD LH → Sell signal
    HIDDEN_BULLISH = "hidden_bullish"  # Price HL, CVD LL → Continuation
    HIDDEN_BEARISH = "hidden_bearish"  # Price LH, CVD HH → Continuation


@dataclass
class SwingPoint:
    """A swing high or low in price or CVD."""
    index: int
    value: float
    is_high: bool  # True = swing high, False = swing low


@dataclass
class CVDSignal:
    """
    CVD divergence signal.

    Attributes:
        divergence_type: Type of divergence detected
        strength: Divergence strength (0-1)
        persistence: How many candles divergence has persisted
        price_swing: Price swing point
        cvd_swing: CVD swing point
        zscore: Z-score of CVD deviation
        confidence: Overall confidence in signal
    """
    divergence_type: DivergenceType
    strength: float  # 0-1
    persistence: int  # candles
    price_swing: Optional[SwingPoint] = None
    cvd_swing: Optional[SwingPoint] = None
    zscore: float = 0.0
    confidence: float = 0.0

    @property
    def is_bullish(self) -> bool:
        return self.divergence_type in [DivergenceType.BULLISH, DivergenceType.HIDDEN_BULLISH]

    @property
    def is_bearish(self) -> bool:
        return self.divergence_type in [DivergenceType.BEARISH, DivergenceType.HIDDEN_BEARISH]

    @property
    def is_valid(self) -> bool:
        """Signal is valid if strength and confidence meet thresholds."""
        return (
            self.divergence_type != DivergenceType.NONE and
            self.strength > 0.3 and
            self.persistence >= CVD_DIVERGENCE_MIN_PERSISTENCE and
            abs(self.zscore) >= CVD_ZSCORE_THRESHOLD
        )

    def to_dict(self) -> dict:
        return {
            'divergence_type': self.divergence_type.value,
            'strength': round(self.strength, 3),
            'persistence': self.persistence,
            'zscore': round(self.zscore, 2),
            'confidence': round(self.confidence, 3),
            'is_valid': self.is_valid,
        }


class CVDEngine:
    """
    Cumulative Volume Delta Engine.

    Detects divergences between price action and order flow.
    This is the core of the Micro-Cortex signal generator.

    Usage:
        engine = CVDEngine()
        signal = engine.analyze(candles)
        if signal.is_valid:
            # Generate trade signal
    """

    def __init__(
        self,
        lookback: int = CVD_LOOKBACK_CANDLES,
        min_persistence: int = CVD_DIVERGENCE_MIN_PERSISTENCE,
        zscore_threshold: float = CVD_ZSCORE_THRESHOLD,
        smoothing: int = CVD_SMOOTHING_PERIOD
    ):
        """
        Initialize CVD Engine.

        Args:
            lookback: Candles to analyze for divergence
            min_persistence: Minimum candles divergence must persist
            zscore_threshold: Z-score threshold for significance
            smoothing: EMA period for CVD smoothing
        """
        self.lookback = lookback
        self.min_persistence = min_persistence
        self.zscore_threshold = zscore_threshold
        self.smoothing = smoothing

        # State
        self._last_signal: Optional[CVDSignal] = None
        self._divergence_start_idx: Optional[int] = None

        logger.info(
            "CVD Engine initialized: lookback=%d, min_persistence=%d, zscore_threshold=%.1f",
            lookback, min_persistence, zscore_threshold
        )

    def analyze(self, candles: List[Candle]) -> CVDSignal:
        """
        Analyze candles for CVD divergence.

        Args:
            candles: List of candles (oldest first)

        Returns:
            CVDSignal with divergence detection results
        """
        if len(candles) < self.lookback:
            return CVDSignal(
                divergence_type=DivergenceType.NONE,
                strength=0.0,
                persistence=0,
                confidence=0.0
            )

        # Get recent candles
        recent = candles[-self.lookback:]

        # Extract price and CVD series
        closes = [c.close for c in recent]
        cvd = self._calculate_cvd(recent)

        # Smooth CVD if needed
        if self.smoothing > 1:
            cvd = self._ema_smooth(cvd, self.smoothing)

        # Find swing points
        price_swings = self._find_swings(closes)
        cvd_swings = self._find_swings(cvd)

        # Detect divergence
        divergence = self._detect_divergence(closes, cvd, price_swings, cvd_swings)

        # Calculate Z-score
        zscore = self._calculate_zscore(cvd)

        # Calculate persistence
        persistence = self._calculate_persistence(divergence, closes, cvd)

        # Calculate strength
        strength = self._calculate_strength(closes, cvd, price_swings, cvd_swings, divergence)

        # Calculate confidence
        confidence = self._calculate_confidence(strength, persistence, abs(zscore))

        signal = CVDSignal(
            divergence_type=divergence,
            strength=strength,
            persistence=persistence,
            price_swing=price_swings[-1] if price_swings else None,
            cvd_swing=cvd_swings[-1] if cvd_swings else None,
            zscore=zscore,
            confidence=confidence
        )

        self._last_signal = signal
        return signal

    def _calculate_cvd(self, candles: List[Candle]) -> List[float]:
        """Calculate cumulative volume delta from candles."""
        cvd = []
        running = 0.0
        for candle in candles:
            running += candle.delta
            cvd.append(running)
        return cvd

    def _ema_smooth(self, data: List[float], period: int) -> List[float]:
        """Apply EMA smoothing to reduce noise."""
        if len(data) < period:
            return data

        multiplier = 2 / (period + 1)
        smoothed = [data[0]]

        for i in range(1, len(data)):
            smoothed.append(
                (data[i] - smoothed[-1]) * multiplier + smoothed[-1]
            )

        return smoothed

    def _find_swings(self, data: List[float], window: int = 5) -> List[SwingPoint]:
        """
        Find swing highs and lows in data.

        A swing high is a point higher than `window` points on each side.
        A swing low is a point lower than `window` points on each side.
        """
        swings = []

        for i in range(window, len(data) - window):
            # Check for swing high
            is_high = all(
                data[i] > data[i-j] and data[i] > data[i+j]
                for j in range(1, window + 1)
            )
            if is_high:
                swings.append(SwingPoint(index=i, value=data[i], is_high=True))
                continue

            # Check for swing low
            is_low = all(
                data[i] < data[i-j] and data[i] < data[i+j]
                for j in range(1, window + 1)
            )
            if is_low:
                swings.append(SwingPoint(index=i, value=data[i], is_high=False))

        return swings

    def _detect_divergence(
        self,
        price: List[float],
        cvd: List[float],
        price_swings: List[SwingPoint],
        cvd_swings: List[SwingPoint]
    ) -> DivergenceType:
        """
        Detect divergence between price and CVD.

        Regular Bullish: Price LL, CVD HL (buyers absorbing)
        Regular Bearish: Price HH, CVD LH (sellers distributing)
        """
        # Need at least 2 swing points of same type
        price_lows = [s for s in price_swings if not s.is_high]
        price_highs = [s for s in price_swings if s.is_high]
        cvd_lows = [s for s in cvd_swings if not s.is_high]
        cvd_highs = [s for s in cvd_swings if s.is_high]

        # Check for bullish divergence (Price LL, CVD HL)
        if len(price_lows) >= 2 and len(cvd_lows) >= 2:
            # Compare last two swing lows
            price_making_ll = price_lows[-1].value < price_lows[-2].value
            cvd_making_hl = cvd_lows[-1].value > cvd_lows[-2].value

            # Minimum price drop requirement
            price_drop = (price_lows[-2].value - price_lows[-1].value) / price_lows[-2].value

            if price_making_ll and cvd_making_hl and price_drop >= BULLISH_DIVERGENCE_MIN_DEPTH:
                return DivergenceType.BULLISH

        # Check for bearish divergence (Price HH, CVD LH)
        if len(price_highs) >= 2 and len(cvd_highs) >= 2:
            # Compare last two swing highs
            price_making_hh = price_highs[-1].value > price_highs[-2].value
            cvd_making_lh = cvd_highs[-1].value < cvd_highs[-2].value

            # Minimum price rise requirement
            price_rise = (price_highs[-1].value - price_highs[-2].value) / price_highs[-2].value

            if price_making_hh and cvd_making_lh and price_rise >= BEARISH_DIVERGENCE_MIN_HEIGHT:
                return DivergenceType.BEARISH

        # Check for hidden divergences (continuation patterns)
        if len(price_lows) >= 2 and len(cvd_lows) >= 2:
            price_making_hl = price_lows[-1].value > price_lows[-2].value
            cvd_making_ll = cvd_lows[-1].value < cvd_lows[-2].value

            if price_making_hl and cvd_making_ll:
                return DivergenceType.HIDDEN_BULLISH

        if len(price_highs) >= 2 and len(cvd_highs) >= 2:
            price_making_lh = price_highs[-1].value < price_highs[-2].value
            cvd_making_hh = cvd_highs[-1].value > cvd_highs[-2].value

            if price_making_lh and cvd_making_hh:
                return DivergenceType.HIDDEN_BEARISH

        return DivergenceType.NONE

    def _calculate_zscore(self, cvd: List[float]) -> float:
        """
        Calculate Z-score of recent CVD change vs historical.

        Higher Z-score = more significant CVD deviation.
        """
        if len(cvd) < 20:
            return 0.0

        # Calculate CVD changes
        changes = [cvd[i] - cvd[i-1] for i in range(1, len(cvd))]

        # Recent change (last 5 periods)
        recent_change = sum(changes[-5:])

        # Historical distribution
        historical = changes[:-5]
        if len(historical) < 10:
            return 0.0

        mean = statistics.mean(historical)
        std = statistics.stdev(historical) if len(historical) > 1 else 1.0

        if std == 0:
            return 0.0

        return (recent_change - mean * 5) / (std * (5 ** 0.5))

    def _calculate_persistence(
        self,
        divergence: DivergenceType,
        price: List[float],
        cvd: List[float]
    ) -> int:
        """
        Calculate how many candles the divergence has persisted.

        Persistence is important - flash divergences are often noise.
        """
        if divergence == DivergenceType.NONE:
            return 0

        # Simple approach: count candles since divergence started
        # by looking at price/CVD correlation breakdown
        persistence = 0

        for i in range(len(price) - 1, max(0, len(price) - 20), -1):
            # Check if divergence pattern continues
            if divergence in [DivergenceType.BULLISH, DivergenceType.HIDDEN_BULLISH]:
                # Price down or flat, CVD up
                price_down = price[i] <= price[i-1] if i > 0 else True
                cvd_up = cvd[i] >= cvd[i-1] if i > 0 else True
                if price_down or cvd_up:
                    persistence += 1
                else:
                    break
            else:
                # Price up or flat, CVD down
                price_up = price[i] >= price[i-1] if i > 0 else True
                cvd_down = cvd[i] <= cvd[i-1] if i > 0 else True
                if price_up or cvd_down:
                    persistence += 1
                else:
                    break

        return persistence

    def _calculate_strength(
        self,
        price: List[float],
        cvd: List[float],
        price_swings: List[SwingPoint],
        cvd_swings: List[SwingPoint],
        divergence: DivergenceType
    ) -> float:
        """
        Calculate divergence strength (0-1).

        Factors:
        - Magnitude of price vs CVD divergence
        - Clarity of swing points
        - Trend context
        """
        if divergence == DivergenceType.NONE:
            return 0.0

        strength = 0.0

        # Factor 1: Price-CVD divergence magnitude (0-0.4)
        if len(price) > 10 and len(cvd) > 10:
            price_change = (price[-1] - price[-10]) / price[-10]
            cvd_change = (cvd[-1] - cvd[-10]) / (abs(cvd[-10]) + 1)

            # Divergence = opposite signs or significantly different magnitudes
            if price_change * cvd_change < 0:
                # Opposite directions
                strength += 0.4
            elif abs(price_change - cvd_change) > 0.05:
                # Different magnitudes
                strength += 0.2

        # Factor 2: Swing point clarity (0-0.3)
        if price_swings and cvd_swings:
            # Clear swings = strength
            recent_price_swings = [s for s in price_swings if s.index >= len(price) - 15]
            recent_cvd_swings = [s for s in cvd_swings if s.index >= len(cvd) - 15]

            if len(recent_price_swings) >= 2 and len(recent_cvd_swings) >= 2:
                strength += 0.3
            elif recent_price_swings and recent_cvd_swings:
                strength += 0.15

        # Factor 3: Volume confirmation (0-0.3)
        # Higher volume on divergence = stronger signal
        # This would need volume data, simplified here
        strength += 0.15  # Default partial credit

        return min(1.0, strength)

    def _calculate_confidence(
        self,
        strength: float,
        persistence: int,
        zscore_abs: float
    ) -> float:
        """
        Calculate overall confidence in the signal.

        Combines strength, persistence, and statistical significance.
        """
        # Weights
        strength_weight = 0.4
        persistence_weight = 0.3
        zscore_weight = 0.3

        # Normalize persistence (max at 10 candles)
        persistence_score = min(1.0, persistence / 10)

        # Normalize Z-score (max at 3.0)
        zscore_score = min(1.0, zscore_abs / 3.0)

        confidence = (
            strength * strength_weight +
            persistence_score * persistence_weight +
            zscore_score * zscore_weight
        )

        return round(confidence, 3)

    @property
    def last_signal(self) -> Optional[CVDSignal]:
        """Get the most recent signal."""
        return self._last_signal

    def reset(self) -> None:
        """Reset engine state."""
        self._last_signal = None
        self._divergence_start_idx = None
