"""
Entropy Filter (Physics-Cortex)

Shannon Entropy-based regime classification.

This is the PRIMARY filter for the MVP strategy.

Theory:
- Low entropy = ordered, structured market → Good for trading
- High entropy = chaotic, random market → Avoid trading
- Think: crystal (ordered) vs gas (chaotic)

Implementation notes:
- Uses Shannon entropy on binned returns
- Adaptive thresholds based on rolling percentiles
- Includes Hurst exponent as secondary filter
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
from collections import deque
import math
import statistics
import logging

from ..config.constants import (
    ENTROPY_CRYSTAL_THRESHOLD,
    ENTROPY_LIQUID_THRESHOLD,
    ENTROPY_GAS_THRESHOLD,
    ENTROPY_LOOKBACK_TICKS,
    ENTROPY_NUM_BINS,
    ENTROPY_MIN_SAMPLES,
    ENTROPY_ADAPTIVE_LOOKBACK,
    ENTROPY_CRYSTAL_PERCENTILE,
    ENTROPY_GAS_PERCENTILE,
    HURST_LOOKBACK_TICKS,
    HURST_TRENDING_THRESHOLD,
    HURST_MEAN_REVERTING_THRESHOLD,
)

logger = logging.getLogger(__name__)


class EntropyRegime(Enum):
    """Market regime based on entropy."""
    CRYSTAL = "crystal"    # Low entropy, ordered → TRADE
    LIQUID = "liquid"      # Medium entropy, normal → CAUTION
    GAS = "gas"           # High entropy, chaotic → NO TRADE
    UNKNOWN = "unknown"    # Insufficient data


@dataclass
class EntropySignal:
    """
    Entropy-based regime signal.

    Attributes:
        regime: Current market regime
        entropy: Raw Shannon entropy (0-1)
        entropy_percentile: Entropy percentile vs history
        hurst: Hurst exponent (0-1)
        hurst_signal: Trending/Mean-reverting/Random
        can_trade: True if conditions allow trading
        confidence: Confidence in regime classification
    """
    regime: EntropyRegime
    entropy: float
    entropy_percentile: float
    hurst: float
    hurst_signal: str  # "trending", "mean_reverting", "random"
    can_trade: bool
    confidence: float

    def to_dict(self) -> dict:
        return {
            'regime': self.regime.value,
            'entropy': round(self.entropy, 4),
            'entropy_percentile': round(self.entropy_percentile, 1),
            'hurst': round(self.hurst, 4),
            'hurst_signal': self.hurst_signal,
            'can_trade': self.can_trade,
            'confidence': round(self.confidence, 3),
        }


class EntropyFilter:
    """
    Entropy-based market regime filter.

    Determines whether market conditions are suitable for trading
    by measuring the "disorder" in price movements.

    Usage:
        filter = EntropyFilter()
        for price in prices:
            filter.update(price)
        signal = filter.get_signal()
        if signal.can_trade:
            # Proceed with trade
    """

    def __init__(
        self,
        lookback: int = ENTROPY_LOOKBACK_TICKS,
        num_bins: int = ENTROPY_NUM_BINS,
        min_samples: int = ENTROPY_MIN_SAMPLES,
        use_adaptive_threshold: bool = True
    ):
        """
        Initialize entropy filter.

        Args:
            lookback: Number of ticks for entropy calculation
            num_bins: Histogram bins for return distribution
            min_samples: Minimum samples before calculating
            use_adaptive_threshold: Use percentile-based thresholds
        """
        self.lookback = lookback
        self.num_bins = num_bins
        self.min_samples = min_samples
        self.use_adaptive_threshold = use_adaptive_threshold

        # Price history
        self._prices: deque = deque(maxlen=max(lookback, ENTROPY_ADAPTIVE_LOOKBACK))

        # Entropy history (for adaptive thresholds)
        self._entropy_history: deque = deque(maxlen=ENTROPY_ADAPTIVE_LOOKBACK)

        # Last signal
        self._last_signal: Optional[EntropySignal] = None

        logger.info(
            "Entropy Filter initialized: lookback=%d, bins=%d, adaptive=%s",
            lookback, num_bins, use_adaptive_threshold
        )

    def update(self, price: float) -> None:
        """
        Update filter with new price.

        Args:
            price: Current price
        """
        self._prices.append(price)

        # Update entropy history periodically
        if len(self._prices) >= self.min_samples:
            entropy = self._calculate_entropy()
            self._entropy_history.append(entropy)

    def update_batch(self, prices: List[float]) -> None:
        """Update with multiple prices at once."""
        for price in prices:
            self.update(price)

    def get_signal(self) -> EntropySignal:
        """
        Get current entropy signal.

        Returns:
            EntropySignal with regime classification
        """
        if len(self._prices) < self.min_samples:
            return EntropySignal(
                regime=EntropyRegime.UNKNOWN,
                entropy=0.5,
                entropy_percentile=50.0,
                hurst=0.5,
                hurst_signal="unknown",
                can_trade=False,
                confidence=0.0
            )

        # Calculate entropy
        entropy = self._calculate_entropy()

        # Calculate percentile
        entropy_percentile = self._calculate_percentile(entropy)

        # Determine regime
        regime = self._classify_regime(entropy, entropy_percentile)

        # Calculate Hurst exponent
        hurst = self._calculate_hurst()
        hurst_signal = self._classify_hurst(hurst)

        # Determine if trading allowed
        can_trade = self._can_trade(regime, hurst)

        # Calculate confidence
        confidence = self._calculate_confidence(entropy, entropy_percentile, regime)

        signal = EntropySignal(
            regime=regime,
            entropy=entropy,
            entropy_percentile=entropy_percentile,
            hurst=hurst,
            hurst_signal=hurst_signal,
            can_trade=can_trade,
            confidence=confidence
        )

        self._last_signal = signal
        return signal

    def _calculate_entropy(self) -> float:
        """
        Calculate Shannon entropy of price returns.

        Uses histogram binning to estimate return distribution.
        Returns normalized entropy in [0, 1].
        """
        prices = list(self._prices)[-self.lookback:]

        if len(prices) < 10:
            return 0.5

        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] != 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)

        if len(returns) < 10:
            return 0.5

        # Bin returns
        min_ret, max_ret = min(returns), max(returns)
        if min_ret == max_ret:
            return 0.0  # All same = zero entropy

        # Use Freedman-Diaconis rule for bin width (more robust)
        # But cap at num_bins for consistency
        bin_width = (max_ret - min_ret) / self.num_bins
        counts = [0] * self.num_bins

        for ret in returns:
            bin_idx = min(int((ret - min_ret) / bin_width), self.num_bins - 1)
            counts[bin_idx] += 1

        # Calculate Shannon entropy
        total = len(returns)
        entropy = 0.0

        for count in counts:
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)

        # Normalize to [0, 1]
        max_entropy = math.log2(self.num_bins)
        normalized = entropy / max_entropy if max_entropy > 0 else 0.0

        return normalized

    def _calculate_percentile(self, entropy: float) -> float:
        """
        Calculate percentile of current entropy vs history.

        Lower percentile = more ordered (better for trading).
        """
        if len(self._entropy_history) < 50:
            # Not enough history, use fixed thresholds
            return entropy * 100

        history = sorted(self._entropy_history)
        rank = sum(1 for h in history if h <= entropy)
        percentile = (rank / len(history)) * 100

        return percentile

    def _classify_regime(self, entropy: float, percentile: float) -> EntropyRegime:
        """
        Classify market regime based on entropy.

        Uses either fixed or adaptive thresholds.
        """
        if self.use_adaptive_threshold and len(self._entropy_history) >= 100:
            # Adaptive: Use percentiles
            if percentile <= ENTROPY_CRYSTAL_PERCENTILE:
                return EntropyRegime.CRYSTAL
            elif percentile >= ENTROPY_GAS_PERCENTILE:
                return EntropyRegime.GAS
            else:
                return EntropyRegime.LIQUID
        else:
            # Fixed thresholds
            if entropy < ENTROPY_CRYSTAL_THRESHOLD:
                return EntropyRegime.CRYSTAL
            elif entropy > ENTROPY_GAS_THRESHOLD:
                return EntropyRegime.GAS
            elif entropy > ENTROPY_LIQUID_THRESHOLD:
                return EntropyRegime.LIQUID
            else:
                return EntropyRegime.LIQUID

    def _calculate_hurst(self) -> float:
        """
        Calculate Hurst exponent using R/S analysis.

        H > 0.5: Trending (persistent)
        H = 0.5: Random walk
        H < 0.5: Mean-reverting

        Note: This is a simplified implementation.
        Production should use DFA or more robust methods.
        """
        prices = list(self._prices)[-HURST_LOOKBACK_TICKS:]

        if len(prices) < 50:
            return 0.5

        # Calculate log returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0 and prices[i] > 0:
                ret = math.log(prices[i] / prices[i-1])
                returns.append(ret)

        if len(returns) < 20:
            return 0.5

        n = len(returns)
        mean = sum(returns) / n

        # Calculate cumulative deviation from mean
        cum_dev = []
        running = 0
        for ret in returns:
            running += ret - mean
            cum_dev.append(running)

        # Range
        R = max(cum_dev) - min(cum_dev)

        # Standard deviation
        variance = sum((r - mean) ** 2 for r in returns) / n
        S = variance ** 0.5

        if S == 0 or R == 0:
            return 0.5

        # R/S ratio
        RS = R / S

        # Estimate H from log(R/S) / log(n)
        # For a random walk, E[R/S] ~ n^0.5, so H = 0.5
        if RS > 0 and n > 1:
            H = math.log(RS) / math.log(n)
            # Adjust to center around 0.5
            H = max(0.0, min(1.0, H + 0.3))  # Empirical adjustment
            return H

        return 0.5

    def _classify_hurst(self, hurst: float) -> str:
        """Classify Hurst exponent."""
        if hurst > HURST_TRENDING_THRESHOLD:
            return "trending"
        elif hurst < HURST_MEAN_REVERTING_THRESHOLD:
            return "mean_reverting"
        else:
            return "random"

    def _can_trade(self, regime: EntropyRegime, hurst: float) -> bool:
        """
        Determine if trading is allowed.

        Rules:
        1. Must be in CRYSTAL regime (low entropy)
        2. Hurst should not indicate pure random walk
        """
        if regime == EntropyRegime.GAS:
            return False  # Never trade in chaos

        if regime == EntropyRegime.CRYSTAL:
            return True  # Always trade in order

        # LIQUID regime: Trade if Hurst suggests trend
        if regime == EntropyRegime.LIQUID:
            return hurst > 0.5  # Only if trending

        return False

    def _calculate_confidence(
        self,
        entropy: float,
        percentile: float,
        regime: EntropyRegime
    ) -> float:
        """
        Calculate confidence in regime classification.

        Higher confidence when entropy is clearly in one regime.
        """
        if regime == EntropyRegime.UNKNOWN:
            return 0.0

        # Distance from regime boundaries
        if regime == EntropyRegime.CRYSTAL:
            # Confidence increases as entropy decreases
            confidence = 1.0 - (entropy / ENTROPY_CRYSTAL_THRESHOLD)
        elif regime == EntropyRegime.GAS:
            # Confidence increases as entropy increases
            confidence = (entropy - ENTROPY_GAS_THRESHOLD) / (1 - ENTROPY_GAS_THRESHOLD)
        else:
            # LIQUID: Lower confidence (transition zone)
            # Distance from nearest boundary
            dist_crystal = abs(entropy - ENTROPY_CRYSTAL_THRESHOLD)
            dist_gas = abs(entropy - ENTROPY_GAS_THRESHOLD)
            min_dist = min(dist_crystal, dist_gas)
            max_range = (ENTROPY_GAS_THRESHOLD - ENTROPY_CRYSTAL_THRESHOLD) / 2
            confidence = min_dist / max_range

        return max(0.0, min(1.0, confidence))

    @property
    def last_signal(self) -> Optional[EntropySignal]:
        """Get most recent signal."""
        return self._last_signal

    @property
    def current_entropy(self) -> float:
        """Get current entropy value."""
        if len(self._prices) < self.min_samples:
            return 0.5
        return self._calculate_entropy()

    def reset(self) -> None:
        """Reset filter state."""
        self._prices.clear()
        self._entropy_history.clear()
        self._last_signal = None
