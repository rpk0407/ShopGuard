"""
Whale Manipulation Detector
===========================
Detects when whale activity is likely manipulation vs genuine accumulation.

The Problem with Blindly Following Whales:
1. Whales KNOW they're being watched
2. They can fake accumulation to attract copy traders
3. Then dump on the copy traders (you become THEIR exit liquidity)
4. Spoofing: Large orders placed with intent to cancel
5. Coordinated pump & dump schemes

Signs of Whale Manipulation:
- Sudden large visible moves (real whales hide their activity)
- Activity during low liquidity periods
- Patterns that repeat (scripted behavior)
- Quick reversal after public attention
- Single whale acting alone (vs multiple independent whales)

Signs of Genuine Accumulation:
- Slow, steady buying over time (stealth)
- Multiple independent whales doing the same thing
- Activity spread across different times
- No immediate selling after buying
- Consistent with on-chain fundamentals

This module adds skepticism to whale tracking.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class ManipulationType(Enum):
    """Types of whale manipulation"""
    NONE = "none"                      # Likely genuine
    SPOOFING = "spoofing"              # Fake orders to move price
    WASH_TRADING = "wash_trading"      # Trading with self
    PUMP_BAIT = "pump_bait"           # Attracting buyers before dump
    DUMP_BAIT = "dump_bait"           # Attracting sellers before pump
    COORDINATED = "coordinated"        # Multiple wallets, same controller
    ATTENTION_SEEKING = "attention"    # Deliberately visible activity


class ConfidenceLevel(Enum):
    """Confidence in whale signal being genuine"""
    VERY_LOW = 1      # Likely manipulation
    LOW = 2           # Suspicious
    MEDIUM = 3        # Uncertain
    HIGH = 4          # Probably genuine
    VERY_HIGH = 5     # Multiple confirmations


@dataclass
class WhaleActivity:
    """Tracked whale activity"""
    wallet_id: str
    asset: str
    direction: str          # "BUY" or "SELL"
    amount_usd: float
    timestamp: datetime
    is_visible: bool        # Was this publicly broadcast?
    execution_speed: str    # "instant", "gradual", "stealth"
    market_impact: float    # How much did price move?


@dataclass
class ManipulationSignal:
    """Result of manipulation analysis"""
    asset: str
    is_manipulation: bool
    manipulation_type: ManipulationType
    confidence: ConfidenceLevel
    whale_count: int           # Number of independent whales
    consensus: float           # -1 to +1, agreement among whales
    time_consistency: float    # 0-1, how spread out is activity
    reversal_risk: float       # 0-1, likelihood of quick reversal
    adjusted_direction: float  # Direction after skepticism applied
    reasoning: str
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)


class WhaleManipulationDetector:
    """
    Detects whale manipulation to avoid being their exit liquidity.

    Key Principles:
    1. REAL whales try to HIDE their activity (stealth accumulation)
    2. VISIBLE whale activity is often bait (they WANT you to see it)
    3. Single whale = suspicious, multiple independent whales = more credible
    4. Instant large moves = likely manipulation, gradual = more genuine
    5. Always apply time delay - manipulation usually reverses quickly

    Scoring System:
    - Multiple independent whales: +2 confidence
    - Gradual/stealth execution: +1 confidence
    - Consistent with fundamentals: +1 confidence
    - Single whale acting alone: -2 confidence
    - Highly visible/broadcast: -1 confidence
    - Quick reversal history: -2 confidence
    - Low liquidity timing: -1 confidence

    Usage:
        detector = WhaleManipulationDetector()

        # Before trusting whale signal:
        result = detector.analyze_whale_activity(
            asset="BTC",
            whale_direction=0.7,
            whale_activities=[...],
            market_conditions={...}
        )

        if result.is_manipulation:
            print("MANIPULATION DETECTED - Don't follow this whale")
        elif result.confidence.value < 3:
            print("LOW CONFIDENCE - Apply extra skepticism")
    """

    # Thresholds
    MIN_WHALES_FOR_CONSENSUS = 3      # Need 3+ whales to trust
    STEALTH_THRESHOLD = 0.02          # Max 2% price impact for "stealth"
    REVERSAL_WINDOW_HOURS = 24        # Check for reversals in this window
    VISIBILITY_PENALTY = 0.3          # Reduce confidence for visible moves
    SINGLE_WHALE_PENALTY = 0.5        # Reduce confidence for single whale

    def __init__(
        self,
        history_hours: int = 168,     # 1 week history
        min_consensus_confidence: float = 0.6,
    ):
        self.history_hours = history_hours
        self.min_consensus_confidence = min_consensus_confidence

        # Activity tracking
        self.whale_activities: Dict[str, List[WhaleActivity]] = {}  # asset -> activities
        self.whale_history: Dict[str, deque] = {}  # wallet -> history
        self.manipulation_history: Dict[str, List[ManipulationSignal]] = {}

        # Known manipulator wallets (would be populated from data)
        self.suspicious_wallets: set = set()
        self.trusted_wallets: set = set()

    def add_activity(self, activity: WhaleActivity):
        """Track whale activity"""
        if activity.asset not in self.whale_activities:
            self.whale_activities[activity.asset] = []

        self.whale_activities[activity.asset].append(activity)

        # Keep last week
        cutoff = datetime.now() - timedelta(hours=self.history_hours)
        self.whale_activities[activity.asset] = [
            a for a in self.whale_activities[activity.asset]
            if a.timestamp > cutoff
        ]

        # Track by wallet
        if activity.wallet_id not in self.whale_history:
            self.whale_history[activity.wallet_id] = deque(maxlen=100)
        self.whale_history[activity.wallet_id].append(activity)

    def _count_independent_whales(self, asset: str, direction: str) -> int:
        """Count independent whales moving in same direction"""
        recent = self._get_recent_activities(asset, hours=24)

        wallets = set()
        for activity in recent:
            if activity.direction == direction:
                wallets.add(activity.wallet_id)

        return len(wallets)

    def _get_recent_activities(
        self,
        asset: str,
        hours: int = 24
    ) -> List[WhaleActivity]:
        """Get recent activities for an asset"""
        if asset not in self.whale_activities:
            return []

        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            a for a in self.whale_activities[asset]
            if a.timestamp > cutoff
        ]

    def _calculate_consensus(self, asset: str) -> Tuple[float, int]:
        """
        Calculate consensus among whales.

        Returns (consensus_score, whale_count)
        - consensus_score: -1 (all selling) to +1 (all buying)
        - whale_count: number of unique whales
        """
        recent = self._get_recent_activities(asset, hours=48)

        if not recent:
            return 0, 0

        buy_volume = 0
        sell_volume = 0
        wallets = set()

        for activity in recent:
            wallets.add(activity.wallet_id)
            if activity.direction == "BUY":
                buy_volume += activity.amount_usd
            else:
                sell_volume += activity.amount_usd

        total = buy_volume + sell_volume
        if total == 0:
            return 0, len(wallets)

        consensus = (buy_volume - sell_volume) / total
        return consensus, len(wallets)

    def _check_execution_pattern(self, asset: str) -> Tuple[str, float]:
        """
        Analyze execution pattern.

        Returns (pattern_type, suspicion_score)
        - "stealth": Low visibility, spread over time
        - "gradual": Medium visibility, somewhat spread
        - "instant": High visibility, concentrated
        """
        recent = self._get_recent_activities(asset, hours=24)

        if not recent:
            return "unknown", 0.5

        # Check time spread
        if len(recent) < 2:
            return "instant", 0.7  # Single large move = suspicious

        timestamps = [a.timestamp for a in recent]
        time_spread = (max(timestamps) - min(timestamps)).total_seconds() / 3600

        # Check visibility
        visible_count = sum(1 for a in recent if a.is_visible)
        visibility_ratio = visible_count / len(recent)

        # Check market impact
        avg_impact = sum(a.market_impact for a in recent) / len(recent)

        # Score
        if time_spread > 12 and visibility_ratio < 0.3 and avg_impact < self.STEALTH_THRESHOLD:
            return "stealth", 0.2
        elif time_spread > 6 and visibility_ratio < 0.6:
            return "gradual", 0.4
        else:
            return "instant", 0.8

    def _check_reversal_history(self, asset: str) -> float:
        """
        Check if recent whale activity was followed by reversals.

        Returns reversal_risk (0-1)
        """
        activities = self._get_recent_activities(asset, hours=72)

        if len(activities) < 2:
            return 0.3  # Unknown

        # Look for pattern: big move followed by opposite move
        reversals = 0
        for i in range(len(activities) - 1):
            current = activities[i]
            next_act = activities[i + 1]

            # Same wallet, opposite direction within 24h
            if (current.wallet_id == next_act.wallet_id and
                current.direction != next_act.direction):
                time_diff = (next_act.timestamp - current.timestamp).total_seconds() / 3600
                if time_diff < 24:
                    reversals += 1

        reversal_ratio = reversals / (len(activities) - 1) if len(activities) > 1 else 0
        return min(1.0, reversal_ratio * 2)

    def _check_for_spoofing(self, asset: str) -> bool:
        """Check for spoofing patterns (large orders that get cancelled)"""
        # This would integrate with order book data
        # For now, return False (no spoofing detected)
        return False

    def _check_coordination(self, asset: str) -> bool:
        """Check if multiple wallets appear coordinated (same controller)"""
        recent = self._get_recent_activities(asset, hours=24)

        if len(recent) < 3:
            return False

        # Check for suspicious timing patterns
        # Multiple wallets acting within seconds = likely coordinated
        timestamps = sorted([a.timestamp for a in recent])

        coordinated_count = 0
        for i in range(len(timestamps) - 1):
            time_diff = (timestamps[i + 1] - timestamps[i]).total_seconds()
            if time_diff < 60:  # Within 1 minute
                coordinated_count += 1

        return coordinated_count > len(timestamps) * 0.5

    def _calculate_confidence(
        self,
        whale_count: int,
        execution_pattern: str,
        reversal_risk: float,
        is_visible: bool,
        is_coordinated: bool,
        consensus: float
    ) -> ConfidenceLevel:
        """Calculate confidence in whale signal being genuine"""
        score = 3.0  # Start at medium

        # Multiple independent whales = more confidence
        if whale_count >= self.MIN_WHALES_FOR_CONSENSUS:
            score += 1.5
        elif whale_count == 1:
            score -= 1.5
        elif whale_count == 2:
            score -= 0.5

        # Execution pattern
        if execution_pattern == "stealth":
            score += 1
        elif execution_pattern == "instant":
            score -= 1

        # Reversal history
        score -= reversal_risk * 2

        # Visibility penalty (visible = likely bait)
        if is_visible:
            score -= 0.5

        # Coordination penalty
        if is_coordinated:
            score -= 1.5

        # Strong consensus bonus
        if abs(consensus) > 0.7 and whale_count >= 3:
            score += 0.5

        # Clamp to 1-5
        score = max(1, min(5, score))

        confidence_map = {
            1: ConfidenceLevel.VERY_LOW,
            2: ConfidenceLevel.LOW,
            3: ConfidenceLevel.MEDIUM,
            4: ConfidenceLevel.HIGH,
            5: ConfidenceLevel.VERY_HIGH
        }

        return confidence_map[int(score)]

    def _detect_manipulation_type(
        self,
        whale_count: int,
        execution_pattern: str,
        reversal_risk: float,
        is_coordinated: bool,
        is_spoofing: bool,
        consensus: float
    ) -> ManipulationType:
        """Detect the type of manipulation if any"""
        if is_spoofing:
            return ManipulationType.SPOOFING

        if is_coordinated:
            return ManipulationType.COORDINATED

        if reversal_risk > 0.6:
            if consensus > 0:
                return ManipulationType.PUMP_BAIT
            else:
                return ManipulationType.DUMP_BAIT

        if whale_count == 1 and execution_pattern == "instant":
            return ManipulationType.ATTENTION_SEEKING

        return ManipulationType.NONE

    def analyze_whale_activity(
        self,
        asset: str,
        whale_direction: float,
        is_highly_visible: bool = False
    ) -> ManipulationSignal:
        """
        Analyze whale activity for manipulation.

        Args:
            asset: Asset symbol
            whale_direction: Current whale signal direction (-1 to 1)
            is_highly_visible: Was this whale activity publicly broadcast?

        Returns:
            ManipulationSignal with analysis results
        """
        # Calculate consensus and whale count
        consensus, whale_count = self._calculate_consensus(asset)

        # Analyze execution pattern
        execution_pattern, pattern_suspicion = self._check_execution_pattern(asset)

        # Check reversal history
        reversal_risk = self._check_reversal_history(asset)

        # Check for specific manipulation types
        is_spoofing = self._check_for_spoofing(asset)
        is_coordinated = self._check_coordination(asset)

        # Calculate confidence
        confidence = self._calculate_confidence(
            whale_count=whale_count,
            execution_pattern=execution_pattern,
            reversal_risk=reversal_risk,
            is_visible=is_highly_visible,
            is_coordinated=is_coordinated,
            consensus=consensus
        )

        # Detect manipulation type
        manipulation_type = self._detect_manipulation_type(
            whale_count=whale_count,
            execution_pattern=execution_pattern,
            reversal_risk=reversal_risk,
            is_coordinated=is_coordinated,
            is_spoofing=is_spoofing,
            consensus=consensus
        )

        is_manipulation = manipulation_type != ManipulationType.NONE

        # Calculate time consistency (how spread out is activity)
        time_consistency = 1.0 - pattern_suspicion

        # Adjust direction based on confidence
        # Low confidence = reduce signal, very low = might invert (counter-trade the manipulation)
        if confidence == ConfidenceLevel.VERY_LOW:
            adjusted_direction = -whale_direction * 0.3  # Slightly counter-trade
        elif confidence == ConfidenceLevel.LOW:
            adjusted_direction = whale_direction * 0.3  # Heavy skepticism
        elif confidence == ConfidenceLevel.MEDIUM:
            adjusted_direction = whale_direction * 0.6  # Moderate skepticism
        elif confidence == ConfidenceLevel.HIGH:
            adjusted_direction = whale_direction * 0.85  # Light skepticism
        else:  # VERY_HIGH
            adjusted_direction = whale_direction * 0.95  # Trust but verify

        # Generate reasoning
        reasons = []
        if whale_count < self.MIN_WHALES_FOR_CONSENSUS:
            reasons.append(f"Only {whale_count} whale(s) - need {self.MIN_WHALES_FOR_CONSENSUS}+ for consensus")
        else:
            reasons.append(f"{whale_count} independent whales agree")

        if execution_pattern == "instant":
            reasons.append("Instant execution = suspicious")
        elif execution_pattern == "stealth":
            reasons.append("Stealth execution = more genuine")

        if reversal_risk > 0.5:
            reasons.append(f"High reversal risk ({reversal_risk:.0%})")

        if is_coordinated:
            reasons.append("Coordinated wallets detected")

        if is_highly_visible:
            reasons.append("Highly visible = likely bait")

        reasoning = "; ".join(reasons)

        # Generate recommendation
        if is_manipulation:
            if manipulation_type in [ManipulationType.PUMP_BAIT, ManipulationType.DUMP_BAIT]:
                recommendation = f"MANIPULATION: {manipulation_type.value} - Consider counter-trading or staying flat"
            else:
                recommendation = f"MANIPULATION: {manipulation_type.value} - Do NOT follow this signal"
        elif confidence.value <= 2:
            recommendation = "LOW CONFIDENCE: Apply heavy skepticism, reduce position size or skip"
        elif confidence.value == 3:
            recommendation = "MEDIUM CONFIDENCE: Proceed with caution, use tight stops"
        else:
            recommendation = "HIGH CONFIDENCE: Signal appears genuine, standard risk management"

        signal = ManipulationSignal(
            asset=asset,
            is_manipulation=is_manipulation,
            manipulation_type=manipulation_type,
            confidence=confidence,
            whale_count=whale_count,
            consensus=consensus,
            time_consistency=time_consistency,
            reversal_risk=reversal_risk,
            adjusted_direction=adjusted_direction,
            reasoning=reasoning,
            recommendation=recommendation
        )

        # Store in history
        if asset not in self.manipulation_history:
            self.manipulation_history[asset] = []
        self.manipulation_history[asset].append(signal)

        return signal

    def get_adjusted_whale_signal(
        self,
        asset: str,
        raw_whale_direction: float,
        is_broadcast: bool = False
    ) -> Tuple[float, float, str]:
        """
        Get whale signal adjusted for manipulation risk.

        Returns (adjusted_direction, confidence_score, recommendation)
        """
        result = self.analyze_whale_activity(
            asset=asset,
            whale_direction=raw_whale_direction,
            is_highly_visible=is_broadcast
        )

        confidence_score = result.confidence.value / 5.0

        return (
            result.adjusted_direction,
            confidence_score,
            result.recommendation
        )


# Demo
async def demo_whale_manipulation():
    """Demo the whale manipulation detector"""
    print("\n" + "="*60)
    print("WHALE MANIPULATION DETECTOR")
    print("'Don't be exit liquidity for the whales either!'")
    print("="*60 + "\n")

    detector = WhaleManipulationDetector()

    # Simulate different scenarios

    # Scenario 1: Single whale, instant move, highly visible
    print("--- Scenario 1: Single Whale Pump (Suspicious) ---")
    detector.add_activity(WhaleActivity(
        wallet_id="whale_1",
        asset="BTC",
        direction="BUY",
        amount_usd=5_000_000,
        timestamp=datetime.now(),
        is_visible=True,
        execution_speed="instant",
        market_impact=0.03
    ))

    result1 = detector.analyze_whale_activity("BTC", 0.8, is_highly_visible=True)
    print(f"  Manipulation: {result1.is_manipulation} ({result1.manipulation_type.value})")
    print(f"  Confidence: {result1.confidence.name}")
    print(f"  Whale count: {result1.whale_count}")
    print(f"  Raw signal: 0.80 → Adjusted: {result1.adjusted_direction:.2f}")
    print(f"  Reasoning: {result1.reasoning}")
    print(f"  Recommendation: {result1.recommendation}")

    # Scenario 2: Multiple whales, stealth accumulation
    print("\n--- Scenario 2: Multiple Whales, Stealth (More Genuine) ---")

    # Clear and add new activities
    detector.whale_activities["ETH"] = []

    for i in range(5):
        detector.add_activity(WhaleActivity(
            wallet_id=f"whale_{i}",
            asset="ETH",
            direction="BUY",
            amount_usd=1_000_000,
            timestamp=datetime.now() - timedelta(hours=i*4),
            is_visible=False,
            execution_speed="gradual",
            market_impact=0.005
        ))

    result2 = detector.analyze_whale_activity("ETH", 0.7, is_highly_visible=False)
    print(f"  Manipulation: {result2.is_manipulation} ({result2.manipulation_type.value})")
    print(f"  Confidence: {result2.confidence.name}")
    print(f"  Whale count: {result2.whale_count}")
    print(f"  Raw signal: 0.70 → Adjusted: {result2.adjusted_direction:.2f}")
    print(f"  Reasoning: {result2.reasoning}")
    print(f"  Recommendation: {result2.recommendation}")

    # Scenario 3: Whale with reversal history (pump and dump pattern)
    print("\n--- Scenario 3: Whale with Reversal History (Pump & Dump) ---")

    detector.whale_activities["SOL"] = []

    # Add pump then dump pattern
    detector.add_activity(WhaleActivity(
        wallet_id="whale_suspicious",
        asset="SOL",
        direction="BUY",
        amount_usd=3_000_000,
        timestamp=datetime.now() - timedelta(hours=20),
        is_visible=True,
        execution_speed="instant",
        market_impact=0.04
    ))
    detector.add_activity(WhaleActivity(
        wallet_id="whale_suspicious",
        asset="SOL",
        direction="SELL",
        amount_usd=3_000_000,
        timestamp=datetime.now() - timedelta(hours=8),
        is_visible=False,
        execution_speed="instant",
        market_impact=0.05
    ))
    # Now buying again...
    detector.add_activity(WhaleActivity(
        wallet_id="whale_suspicious",
        asset="SOL",
        direction="BUY",
        amount_usd=2_000_000,
        timestamp=datetime.now(),
        is_visible=True,
        execution_speed="instant",
        market_impact=0.03
    ))

    result3 = detector.analyze_whale_activity("SOL", 0.6, is_highly_visible=True)
    print(f"  Manipulation: {result3.is_manipulation} ({result3.manipulation_type.value})")
    print(f"  Confidence: {result3.confidence.name}")
    print(f"  Reversal risk: {result3.reversal_risk:.0%}")
    print(f"  Raw signal: 0.60 → Adjusted: {result3.adjusted_direction:.2f}")
    print(f"  Reasoning: {result3.reasoning}")
    print(f"  Recommendation: {result3.recommendation}")

    print("\n" + "="*60)
    print("KEY TAKEAWAYS:")
    print("1. Single whale = suspicious, multiple independent = trustworthy")
    print("2. Visible/broadcast = likely bait, stealth = genuine")
    print("3. Instant moves = suspicious, gradual = genuine")
    print("4. Check reversal history - past pump & dump = don't trust")
    print("5. Always apply skepticism - reduce signal, never follow blindly")
    print("="*60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_whale_manipulation())
