"""
Signal Combiner (Decision Gate)

Combines CVD and Entropy signals into final trade decision.

This is the brain that makes the GO/NO-GO decision.

Logic:
- Both CVD divergence AND low entropy required (AND gate)
- No trading in chaotic (high entropy) conditions
- Confidence-weighted position sizing
"""
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum
from datetime import datetime
import logging

from .cvd_engine import CVDEngine, CVDSignal, DivergenceType
from .entropy_filter import EntropyFilter, EntropySignal, EntropyRegime
from ..config.constants import (
    REQUIRE_CVD_SIGNAL,
    REQUIRE_ENTROPY_FILTER,
    REQUIRE_HURST_FILTER,
    CVD_SIGNAL_WEIGHT,
    ENTROPY_SIGNAL_WEIGHT,
    HURST_SIGNAL_WEIGHT,
    MIN_SIGNAL_CONFIDENCE,
    HIGH_CONFIDENCE_THRESHOLD,
)
from ..data.candles import Candle

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    """Trade direction."""
    LONG = "long"
    SHORT = "short"
    NONE = "none"


@dataclass
class CombinedSignal:
    """
    Final combined trading signal.

    This is what the execution engine acts on.
    """
    # Direction
    direction: TradeDirection
    should_trade: bool

    # Component signals
    cvd_signal: Optional[CVDSignal]
    entropy_signal: Optional[EntropySignal]

    # Combined metrics
    confidence: float
    strength: float

    # Metadata
    timestamp: datetime
    asset: str
    reason: str  # Human-readable explanation

    # Position sizing hint
    size_multiplier: float  # 0.5 = half size, 1.0 = full size, 1.5 = increased

    def to_dict(self) -> dict:
        return {
            'direction': self.direction.value,
            'should_trade': self.should_trade,
            'cvd_signal': self.cvd_signal.to_dict() if self.cvd_signal else None,
            'entropy_signal': self.entropy_signal.to_dict() if self.entropy_signal else None,
            'confidence': round(self.confidence, 3),
            'strength': round(self.strength, 3),
            'timestamp': self.timestamp.isoformat(),
            'asset': self.asset,
            'reason': self.reason,
            'size_multiplier': round(self.size_multiplier, 2),
        }


class SignalCombiner:
    """
    Combines multiple signals into final trade decision.

    This is the Decision Gate - the last checkpoint before execution.

    Modes:
    1. AND Gate (default): Both CVD and Entropy must agree
    2. Weighted: Use weighted average of signal confidences
    """

    def __init__(
        self,
        cvd_engine: Optional[CVDEngine] = None,
        entropy_filter: Optional[EntropyFilter] = None,
        mode: str = "and_gate"  # "and_gate" or "weighted"
    ):
        """
        Initialize signal combiner.

        Args:
            cvd_engine: CVD divergence engine
            entropy_filter: Entropy regime filter
            mode: Combination mode ("and_gate" or "weighted")
        """
        self.cvd_engine = cvd_engine or CVDEngine()
        self.entropy_filter = entropy_filter or EntropyFilter()
        self.mode = mode

        # Statistics
        self._signals_generated = 0
        self._trades_approved = 0
        self._trades_rejected = 0

        # Rejection reasons
        self._rejection_reasons: dict = {
            'no_cvd_divergence': 0,
            'high_entropy': 0,
            'low_confidence': 0,
            'conflicting_signals': 0,
        }

        logger.info("Signal Combiner initialized: mode=%s", mode)

    def analyze(
        self,
        candles: List[Candle],
        asset: str = "BTC"
    ) -> CombinedSignal:
        """
        Analyze candles and generate combined signal.

        Args:
            candles: List of candles (oldest first)
            asset: Asset symbol

        Returns:
            CombinedSignal with trade decision
        """
        timestamp = datetime.now()
        self._signals_generated += 1

        # Get CVD signal
        cvd_signal = self.cvd_engine.analyze(candles)

        # Get Entropy signal (using candle closes)
        prices = [c.close for c in candles]
        self.entropy_filter.update_batch(prices)
        entropy_signal = self.entropy_filter.get_signal()

        # Combine signals based on mode
        if self.mode == "and_gate":
            return self._combine_and_gate(
                cvd_signal, entropy_signal, timestamp, asset
            )
        else:
            return self._combine_weighted(
                cvd_signal, entropy_signal, timestamp, asset
            )

    def _combine_and_gate(
        self,
        cvd_signal: CVDSignal,
        entropy_signal: EntropySignal,
        timestamp: datetime,
        asset: str
    ) -> CombinedSignal:
        """
        AND Gate combination: All signals must agree.

        Requirements:
        1. CVD divergence detected (if required)
        2. Entropy regime allows trading (if required)
        3. Combined confidence above threshold
        """
        should_trade = True
        reason_parts = []

        # Check 1: CVD Divergence
        cvd_ok = True
        if REQUIRE_CVD_SIGNAL:
            if not cvd_signal.is_valid:
                cvd_ok = False
                should_trade = False
                self._rejection_reasons['no_cvd_divergence'] += 1
                reason_parts.append("No valid CVD divergence")
            else:
                reason_parts.append(f"CVD {cvd_signal.divergence_type.value}")

        # Check 2: Entropy Filter
        entropy_ok = True
        if REQUIRE_ENTROPY_FILTER:
            if not entropy_signal.can_trade:
                entropy_ok = False
                should_trade = False
                self._rejection_reasons['high_entropy'] += 1
                reason_parts.append(f"Entropy too high ({entropy_signal.regime.value})")
            else:
                reason_parts.append(f"Entropy OK ({entropy_signal.regime.value})")

        # Check 3: Hurst Filter (optional)
        if REQUIRE_HURST_FILTER:
            if entropy_signal.hurst_signal == "random":
                should_trade = False
                reason_parts.append("Random walk detected")

        # Determine direction from CVD
        direction = TradeDirection.NONE
        if cvd_ok and cvd_signal.is_bullish:
            direction = TradeDirection.LONG
        elif cvd_ok and cvd_signal.is_bearish:
            direction = TradeDirection.SHORT

        # Calculate combined confidence
        if cvd_ok and entropy_ok:
            confidence = (
                cvd_signal.confidence * CVD_SIGNAL_WEIGHT +
                entropy_signal.confidence * ENTROPY_SIGNAL_WEIGHT
            )
            # Normalize (weights may not sum to 1 if some filters disabled)
            total_weight = CVD_SIGNAL_WEIGHT + ENTROPY_SIGNAL_WEIGHT
            confidence = confidence / total_weight
        else:
            confidence = 0.0

        # Check confidence threshold
        if should_trade and confidence < MIN_SIGNAL_CONFIDENCE:
            should_trade = False
            self._rejection_reasons['low_confidence'] += 1
            reason_parts.append(f"Low confidence ({confidence:.2f})")

        # Calculate strength
        strength = cvd_signal.strength if cvd_ok else 0.0

        # Determine position size multiplier
        size_multiplier = self._calculate_size_multiplier(confidence, entropy_signal)

        # Build reason string
        reason = " | ".join(reason_parts) if reason_parts else "No signals"

        # Update stats
        if should_trade:
            self._trades_approved += 1
        else:
            self._trades_rejected += 1
            direction = TradeDirection.NONE

        return CombinedSignal(
            direction=direction,
            should_trade=should_trade,
            cvd_signal=cvd_signal,
            entropy_signal=entropy_signal,
            confidence=confidence,
            strength=strength,
            timestamp=timestamp,
            asset=asset,
            reason=reason,
            size_multiplier=size_multiplier,
        )

    def _combine_weighted(
        self,
        cvd_signal: CVDSignal,
        entropy_signal: EntropySignal,
        timestamp: datetime,
        asset: str
    ) -> CombinedSignal:
        """
        Weighted combination: Use weighted average of signals.

        More flexible than AND gate, allows partial signals.
        """
        # Calculate weighted score (-1 to +1)
        cvd_score = 0.0
        if cvd_signal.is_bullish:
            cvd_score = cvd_signal.confidence
        elif cvd_signal.is_bearish:
            cvd_score = -cvd_signal.confidence

        # Entropy doesn't have direction, just confidence
        entropy_modifier = entropy_signal.confidence if entropy_signal.can_trade else 0.0

        # Combine
        combined_score = cvd_score * CVD_SIGNAL_WEIGHT * entropy_modifier

        # Determine direction and should_trade
        if abs(combined_score) >= MIN_SIGNAL_CONFIDENCE:
            should_trade = True
            direction = TradeDirection.LONG if combined_score > 0 else TradeDirection.SHORT
            self._trades_approved += 1
        else:
            should_trade = False
            direction = TradeDirection.NONE
            self._trades_rejected += 1

        confidence = abs(combined_score)
        strength = cvd_signal.strength * entropy_modifier

        reason = f"Weighted score: {combined_score:.3f}"

        size_multiplier = self._calculate_size_multiplier(confidence, entropy_signal)

        return CombinedSignal(
            direction=direction,
            should_trade=should_trade,
            cvd_signal=cvd_signal,
            entropy_signal=entropy_signal,
            confidence=confidence,
            strength=strength,
            timestamp=timestamp,
            asset=asset,
            reason=reason,
            size_multiplier=size_multiplier,
        )

    def _calculate_size_multiplier(
        self,
        confidence: float,
        entropy_signal: EntropySignal
    ) -> float:
        """
        Calculate position size multiplier based on confidence.

        High confidence → larger size
        Low confidence → smaller size
        Crystal regime → bonus
        """
        multiplier = 1.0

        # Confidence-based scaling
        if confidence >= HIGH_CONFIDENCE_THRESHOLD:
            multiplier = 1.25  # 25% larger
        elif confidence < MIN_SIGNAL_CONFIDENCE + 0.1:
            multiplier = 0.5  # 50% smaller

        # Regime-based adjustment
        if entropy_signal.regime == EntropyRegime.CRYSTAL:
            multiplier *= 1.1  # 10% bonus in crystal regime
        elif entropy_signal.regime == EntropyRegime.LIQUID:
            multiplier *= 0.9  # 10% reduction in liquid

        return round(multiplier, 2)

    def get_stats(self) -> dict:
        """Get combiner statistics."""
        total = self._trades_approved + self._trades_rejected
        approval_rate = self._trades_approved / total if total > 0 else 0.0

        return {
            'signals_generated': self._signals_generated,
            'trades_approved': self._trades_approved,
            'trades_rejected': self._trades_rejected,
            'approval_rate': round(approval_rate, 3),
            'rejection_reasons': self._rejection_reasons.copy(),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._signals_generated = 0
        self._trades_approved = 0
        self._trades_rejected = 0
        self._rejection_reasons = {k: 0 for k in self._rejection_reasons}

    def reset(self) -> None:
        """Reset all state including underlying engines."""
        self.cvd_engine.reset()
        self.entropy_filter.reset()
        self.reset_stats()
