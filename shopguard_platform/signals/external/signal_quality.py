"""
Signal Quality Analyzer
=======================
Cross-validates signals from multiple components to improve accuracy.

The Problem:
- Single source signals can be unreliable
- Components can contradict each other
- Need to assess overall confidence before trading

Solution:
- Cross-validate signals across multiple sources
- Weight by historical accuracy
- Require minimum agreement threshold
- Penalize conflicting signals

Quality Score Components:
1. Source Agreement (do multiple sources agree?)
2. Confidence Alignment (are confidence levels consistent?)
3. Time Consistency (are signals stable over time?)
4. Historical Accuracy (how accurate has this signal pattern been?)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class SignalQuality(Enum):
    """Quality rating for signals"""
    EXCELLENT = "excellent"    # 4+ sources agree, high confidence
    GOOD = "good"             # 3+ sources agree
    MODERATE = "moderate"      # 2+ sources agree
    LOW = "low"               # Only 1 source or conflicts
    UNRELIABLE = "unreliable" # Major conflicts or insufficient data


@dataclass
class QualityScore:
    """Quality assessment for a signal"""
    asset: str
    quality: SignalQuality
    overall_score: float           # 0-1
    source_agreement: float        # 0-1
    confidence_alignment: float    # 0-1
    time_consistency: float        # 0-1
    sources_bullish: int
    sources_bearish: int
    sources_neutral: int
    direction_consensus: float     # -1 to +1
    recommendation: str
    reasoning: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SignalInput:
    """Input signal from a component"""
    source: str
    direction: float      # -1 to +1
    confidence: float     # 0 to 1
    timestamp: datetime


class SignalQualityAnalyzer:
    """
    Analyzes quality of signals by cross-validating multiple sources.

    Key Principles:
    1. NEVER trade on single-source signals
    2. Require agreement threshold before action
    3. Conflicting signals = stay out
    4. Higher quality = higher position size

    Quality Thresholds:
    - EXCELLENT: Can take full position
    - GOOD: Can take 70% position
    - MODERATE: Can take 40% position
    - LOW: Skip or take 10% position
    - UNRELIABLE: Do NOT trade

    Usage:
        analyzer = SignalQualityAnalyzer()

        # Add signals from various components
        analyzer.add_signal("BTC", SignalInput("smart_money", 0.7, 0.8, now))
        analyzer.add_signal("BTC", SignalInput("sentiment", 0.6, 0.7, now))
        analyzer.add_signal("BTC", SignalInput("news", 0.5, 0.6, now))

        # Get quality assessment
        quality = analyzer.assess_quality("BTC")

        if quality.quality in [SignalQuality.EXCELLENT, SignalQuality.GOOD]:
            print("High quality signal - proceed with trade")
        else:
            print("Low quality - skip or reduce size")
    """

    # Thresholds
    AGREEMENT_THRESHOLD = 0.6    # 60% of sources must agree
    MIN_SOURCES = 2              # Need at least 2 sources
    DIRECTION_THRESHOLD = 0.3   # Minimum direction for bullish/bearish

    def __init__(
        self,
        history_size: int = 100,
        time_window_minutes: int = 30
    ):
        self.history_size = history_size
        self.time_window = timedelta(minutes=time_window_minutes)

        # Store signals by asset
        self.signals: Dict[str, List[SignalInput]] = {}
        self.quality_history: Dict[str, deque] = {}

    def add_signal(self, asset: str, signal: SignalInput):
        """Add a signal from a component"""
        if asset not in self.signals:
            self.signals[asset] = []

        # Remove stale signals from same source
        self.signals[asset] = [
            s for s in self.signals[asset]
            if s.source != signal.source or
            (datetime.now() - s.timestamp) < self.time_window
        ]

        self.signals[asset].append(signal)

    def _get_recent_signals(self, asset: str) -> List[SignalInput]:
        """Get signals within the time window"""
        cutoff = datetime.now() - self.time_window

        if asset not in self.signals:
            return []

        recent = [s for s in self.signals[asset] if s.timestamp > cutoff]

        # Deduplicate by source (keep most recent)
        by_source = {}
        for s in sorted(recent, key=lambda x: x.timestamp):
            by_source[s.source] = s

        return list(by_source.values())

    def _calculate_agreement(self, signals: List[SignalInput]) -> Tuple[float, int, int, int]:
        """
        Calculate agreement score among signals.

        Returns (agreement_score, bullish_count, bearish_count, neutral_count)
        """
        if not signals:
            return 0, 0, 0, 0

        bullish = sum(1 for s in signals if s.direction > self.DIRECTION_THRESHOLD)
        bearish = sum(1 for s in signals if s.direction < -self.DIRECTION_THRESHOLD)
        neutral = len(signals) - bullish - bearish

        total = len(signals)
        max_agreement = max(bullish, bearish, neutral)

        # Agreement score: how much do signals agree?
        # 1.0 = all agree, 0.0 = split evenly
        agreement = max_agreement / total if total > 0 else 0

        return agreement, bullish, bearish, neutral

    def _calculate_confidence_alignment(self, signals: List[SignalInput]) -> float:
        """
        Check if confidence levels are consistent.

        High variance in confidence = less reliable
        """
        if len(signals) < 2:
            return 0.5

        confidences = [s.confidence for s in signals]
        mean_conf = sum(confidences) / len(confidences)
        variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)

        # Convert variance to alignment score (low variance = high alignment)
        alignment = max(0, 1 - variance * 4)  # Scale variance
        return alignment

    def _calculate_time_consistency(self, asset: str) -> float:
        """
        Check if signals have been consistent over time.

        Signals that flip frequently = unreliable
        """
        if asset not in self.quality_history:
            return 0.5

        history = list(self.quality_history[asset])
        if len(history) < 3:
            return 0.5

        # Count direction changes
        directions = [q.direction_consensus for q in history[-10:]]
        changes = sum(
            1 for i in range(1, len(directions))
            if (directions[i] > 0) != (directions[i-1] > 0) and
            abs(directions[i]) > 0.2 and abs(directions[i-1]) > 0.2
        )

        # Fewer changes = more consistent
        consistency = max(0, 1 - changes / max(len(directions) - 1, 1))
        return consistency

    def _determine_quality(
        self,
        agreement: float,
        confidence_alignment: float,
        time_consistency: float,
        num_sources: int,
        has_conflicts: bool
    ) -> SignalQuality:
        """Determine signal quality rating"""

        # Insufficient data
        if num_sources < self.MIN_SOURCES:
            return SignalQuality.UNRELIABLE

        # Major conflicts between sources
        if has_conflicts:
            return SignalQuality.LOW

        # Calculate composite score
        composite = (
            agreement * 0.4 +
            confidence_alignment * 0.3 +
            time_consistency * 0.3
        )

        # Boost for more sources
        if num_sources >= 4:
            composite = min(1.0, composite + 0.1)

        if composite >= 0.8 and num_sources >= 3:
            return SignalQuality.EXCELLENT
        elif composite >= 0.65:
            return SignalQuality.GOOD
        elif composite >= 0.5:
            return SignalQuality.MODERATE
        elif composite >= 0.3:
            return SignalQuality.LOW
        else:
            return SignalQuality.UNRELIABLE

    def assess_quality(self, asset: str) -> QualityScore:
        """
        Assess overall signal quality for an asset.

        Returns QualityScore with rating and details.
        """
        signals = self._get_recent_signals(asset)
        reasons = []

        # Calculate metrics
        agreement, bullish, bearish, neutral = self._calculate_agreement(signals)
        confidence_alignment = self._calculate_confidence_alignment(signals)
        time_consistency = self._calculate_time_consistency(asset)

        # Direction consensus
        if signals:
            total_weight = sum(s.confidence for s in signals)
            if total_weight > 0:
                direction_consensus = sum(
                    s.direction * s.confidence for s in signals
                ) / total_weight
            else:
                direction_consensus = 0
        else:
            direction_consensus = 0

        # Check for conflicts
        has_conflicts = bullish > 0 and bearish > 0 and min(bullish, bearish) >= 2

        if has_conflicts:
            reasons.append(f"Conflicting signals: {bullish} bullish vs {bearish} bearish")

        # Determine quality
        quality = self._determine_quality(
            agreement,
            confidence_alignment,
            time_consistency,
            len(signals),
            has_conflicts
        )

        # Generate reasons
        if len(signals) < self.MIN_SOURCES:
            reasons.append(f"Insufficient sources ({len(signals)} < {self.MIN_SOURCES})")

        if agreement >= 0.7:
            reasons.append(f"Strong agreement ({agreement:.0%})")
        elif agreement < 0.5:
            reasons.append(f"Weak agreement ({agreement:.0%})")

        if confidence_alignment >= 0.7:
            reasons.append("Consistent confidence levels")
        elif confidence_alignment < 0.4:
            reasons.append("Inconsistent confidence levels")

        if time_consistency >= 0.7:
            reasons.append("Signals stable over time")
        elif time_consistency < 0.4:
            reasons.append("Signals fluctuating")

        # Generate recommendation
        if quality == SignalQuality.EXCELLENT:
            recommendation = "HIGH CONFIDENCE - Full position allowed"
        elif quality == SignalQuality.GOOD:
            recommendation = "GOOD - 70% position recommended"
        elif quality == SignalQuality.MODERATE:
            recommendation = "MODERATE - 40% position max"
        elif quality == SignalQuality.LOW:
            recommendation = "LOW QUALITY - Skip or 10% position"
        else:
            recommendation = "UNRELIABLE - Do NOT trade"

        # Overall score
        overall_score = (
            agreement * 0.35 +
            confidence_alignment * 0.25 +
            time_consistency * 0.25 +
            min(len(signals) / 4, 1.0) * 0.15
        )

        score = QualityScore(
            asset=asset,
            quality=quality,
            overall_score=overall_score,
            source_agreement=agreement,
            confidence_alignment=confidence_alignment,
            time_consistency=time_consistency,
            sources_bullish=bullish,
            sources_bearish=bearish,
            sources_neutral=neutral,
            direction_consensus=direction_consensus,
            recommendation=recommendation,
            reasoning=reasons
        )

        # Store in history
        if asset not in self.quality_history:
            self.quality_history[asset] = deque(maxlen=self.history_size)
        self.quality_history[asset].append(score)

        return score

    def get_position_multiplier(self, asset: str) -> float:
        """
        Get position size multiplier based on signal quality.

        Returns 0-1 multiplier to apply to position size.
        """
        quality = self.assess_quality(asset)

        multipliers = {
            SignalQuality.EXCELLENT: 1.0,
            SignalQuality.GOOD: 0.7,
            SignalQuality.MODERATE: 0.4,
            SignalQuality.LOW: 0.1,
            SignalQuality.UNRELIABLE: 0.0
        }

        return multipliers.get(quality.quality, 0.0)

    def should_trade(self, asset: str, min_quality: SignalQuality = SignalQuality.MODERATE) -> Tuple[bool, str]:
        """
        Check if signal quality is sufficient for trading.

        Returns (should_trade, reason)
        """
        score = self.assess_quality(asset)

        quality_order = [
            SignalQuality.UNRELIABLE,
            SignalQuality.LOW,
            SignalQuality.MODERATE,
            SignalQuality.GOOD,
            SignalQuality.EXCELLENT
        ]

        current_idx = quality_order.index(score.quality)
        required_idx = quality_order.index(min_quality)

        if current_idx >= required_idx:
            return True, score.recommendation
        else:
            return False, f"Quality {score.quality.value} below threshold {min_quality.value}"

    def clear_signals(self, asset: str):
        """Clear all signals for an asset"""
        if asset in self.signals:
            self.signals[asset] = []


# Demo
def demo_signal_quality():
    """Demo the signal quality analyzer"""
    print("\n" + "="*60)
    print("SIGNAL QUALITY ANALYZER")
    print("'Never trade on single-source signals'")
    print("="*60 + "\n")

    analyzer = SignalQualityAnalyzer()
    now = datetime.now()

    # Scenario 1: All sources agree (bullish)
    print("--- Scenario 1: Strong Agreement (Bullish) ---")
    analyzer.add_signal("BTC", SignalInput("smart_money", 0.7, 0.85, now))
    analyzer.add_signal("BTC", SignalInput("sentiment", 0.6, 0.75, now))
    analyzer.add_signal("BTC", SignalInput("news", 0.5, 0.70, now))
    analyzer.add_signal("BTC", SignalInput("polymarket", 0.4, 0.60, now))

    quality1 = analyzer.assess_quality("BTC")
    print(f"Quality: {quality1.quality.value}")
    print(f"Overall Score: {quality1.overall_score:.2f}")
    print(f"Agreement: {quality1.source_agreement:.2f}")
    print(f"Direction: {quality1.direction_consensus:.2f}")
    print(f"Recommendation: {quality1.recommendation}")
    print(f"Reasons: {', '.join(quality1.reasoning)}")

    # Scenario 2: Conflicting signals
    print("\n--- Scenario 2: Conflicting Signals ---")
    analyzer.clear_signals("ETH")
    analyzer.add_signal("ETH", SignalInput("smart_money", 0.7, 0.8, now))
    analyzer.add_signal("ETH", SignalInput("sentiment", -0.6, 0.75, now))
    analyzer.add_signal("ETH", SignalInput("news", 0.5, 0.7, now))
    analyzer.add_signal("ETH", SignalInput("trap_detector", -0.8, 0.9, now))

    quality2 = analyzer.assess_quality("ETH")
    print(f"Quality: {quality2.quality.value}")
    print(f"Overall Score: {quality2.overall_score:.2f}")
    print(f"Bullish: {quality2.sources_bullish}, Bearish: {quality2.sources_bearish}")
    print(f"Recommendation: {quality2.recommendation}")
    print(f"Reasons: {', '.join(quality2.reasoning)}")

    # Scenario 3: Insufficient data
    print("\n--- Scenario 3: Insufficient Data ---")
    analyzer.clear_signals("SOL")
    analyzer.add_signal("SOL", SignalInput("smart_money", 0.5, 0.7, now))

    quality3 = analyzer.assess_quality("SOL")
    print(f"Quality: {quality3.quality.value}")
    print(f"Recommendation: {quality3.recommendation}")
    print(f"Reasons: {', '.join(quality3.reasoning)}")

    # Position multipliers
    print("\n--- Position Multipliers ---")
    print(f"BTC: {analyzer.get_position_multiplier('BTC'):.0%}")
    print(f"ETH: {analyzer.get_position_multiplier('ETH'):.0%}")
    print(f"SOL: {analyzer.get_position_multiplier('SOL'):.0%}")


if __name__ == "__main__":
    demo_signal_quality()
