"""
Liquidity Trap Detector
=======================
Detects when retail traders are being used as exit liquidity by smart money.

The Pattern:
1. Smart money wants to exit large positions
2. They need retail to provide liquidity (buyers when they sell, sellers when they buy)
3. They manufacture narratives (FUD/FOMO) to attract retail
4. Retail becomes the exit liquidity, gets trapped

Common Trap Patterns:
- "Buy the dip" trap: Whales distribute during retail buying
- "Capitulation" trap: Whales accumulate during retail panic selling
- "Breakout" trap: Fake breakout to trigger FOMO, then dump
- "Breakdown" trap: Fake breakdown to trigger panic, then pump

Detection:
- High retail sentiment + whale distribution = TRAP (don't buy)
- Low retail sentiment + whale accumulation = OPPORTUNITY (buy the fear)
- Volume analysis: Retail buying into selling pressure
- Order book analysis: Thin liquidity behind apparent support/resistance

This module protects you from being the exit liquidity.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class TrapType(Enum):
    """Types of liquidity traps"""
    BULL_TRAP = "bull_trap"       # Fake pump to trap longs
    BEAR_TRAP = "bear_trap"       # Fake dump to trap shorts
    FOMO_TRAP = "fomo_trap"       # Retail FOMO into distribution
    PANIC_TRAP = "panic_trap"     # Retail panic into accumulation
    BREAKOUT_TRAP = "breakout"    # False breakout
    BREAKDOWN_TRAP = "breakdown"  # False breakdown
    NONE = "none"


class TrapSeverity(Enum):
    """Severity of detected trap"""
    NONE = 0
    LOW = 1          # Minor trap, be cautious
    MEDIUM = 2       # Significant trap, avoid
    HIGH = 3         # Major trap, counter-trade
    EXTREME = 4      # Obvious trap, strong counter-trade


@dataclass
class TrapSignal:
    """Detected liquidity trap signal"""
    asset: str
    trap_type: TrapType
    severity: TrapSeverity
    confidence: float                # 0-1
    retail_sentiment: float          # -1 to +1 (what retail is doing)
    smart_money_direction: float     # -1 to +1 (what whales are doing)
    divergence: float                # Degree of divergence
    recommendation: str              # What to do
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LiquidityState:
    """Current liquidity state analysis"""
    # Retail behavior
    retail_sentiment: float      # -1 (panic selling) to +1 (FOMO buying)
    retail_volume_pct: float     # % of volume from retail
    retail_positioning: str      # "long", "short", "neutral"

    # Smart money behavior
    whale_direction: float       # -1 (distributing) to +1 (accumulating)
    exchange_flow: float         # Positive = outflow (accumulation)
    whale_volume_pct: float      # % of volume from whales

    # Divergence analysis
    sentiment_price_divergence: float  # Price going up while sentiment drops (or vice versa)
    volume_price_divergence: float     # Volume contradicting price movement

    # Trap detection
    trap_probability: float      # 0-1
    trap_type: TrapType
    is_safe_to_trade: bool


class LiquidityTrapDetector:
    """
    Detects liquidity traps to avoid being exit liquidity.

    Core Logic:
    1. Monitor retail sentiment vs smart money flow
    2. Detect divergences (retail bullish + whales selling = trap)
    3. Analyze volume patterns (retail buying into distribution)
    4. Check for trap patterns (fake breakouts, stop hunts)

    Protection Modes:
    - DEFENSIVE: Avoid trades when trap detected
    - CONTRARIAN: Counter-trade the trap
    - AGGRESSIVE: Front-run the reversal

    Usage:
        detector = LiquidityTrapDetector()

        # Before any trade, check for traps
        trap = detector.check_for_trap(
            asset="BTC",
            retail_sentiment=0.8,    # Retail very bullish
            whale_direction=-0.5,    # But whales selling
            current_price=50000,
            price_24h_ago=48000
        )

        if trap.severity >= TrapSeverity.MEDIUM:
            print(f"TRAP DETECTED: {trap.trap_type.value}")
            print(f"Recommendation: {trap.recommendation}")
            # Don't take the trade!
    """

    # Divergence thresholds
    MINOR_DIVERGENCE = 0.3
    SIGNIFICANT_DIVERGENCE = 0.5
    EXTREME_DIVERGENCE = 0.7

    def __init__(
        self,
        lookback_periods: int = 24,
        sensitivity: float = 0.5,
    ):
        self.lookback_periods = lookback_periods
        self.sensitivity = sensitivity

        # History tracking
        self.price_history: Dict[str, deque] = {}
        self.sentiment_history: Dict[str, deque] = {}
        self.whale_history: Dict[str, deque] = {}
        self.trap_history: Dict[str, List[TrapSignal]] = {}

        # Callbacks
        self.on_trap_detected: Optional[Callable[[TrapSignal], None]] = None

    def _calculate_divergence(
        self,
        retail_sentiment: float,
        whale_direction: float
    ) -> Tuple[float, str]:
        """
        Calculate divergence between retail and smart money.

        Returns (divergence_score, interpretation)
        """
        # Direct divergence calculation
        # If retail is +0.8 (bullish) and whales are -0.5 (selling)
        # divergence = 0.8 - (-0.5) = 1.3 (very high)

        divergence = retail_sentiment - whale_direction

        if abs(divergence) < self.MINOR_DIVERGENCE:
            return abs(divergence), "aligned"
        elif divergence > self.SIGNIFICANT_DIVERGENCE:
            return divergence, "retail_bullish_whale_bearish"  # Bull trap risk
        elif divergence < -self.SIGNIFICANT_DIVERGENCE:
            return abs(divergence), "retail_bearish_whale_bullish"  # Bear trap risk
        else:
            return abs(divergence), "minor_divergence"

    def _detect_trap_type(
        self,
        retail_sentiment: float,
        whale_direction: float,
        price_change: float,
        divergence: float,
        divergence_type: str
    ) -> TrapType:
        """Detect the type of liquidity trap"""

        # FOMO Trap: Retail buying + whales selling + price rising
        if (retail_sentiment > 0.5 and
            whale_direction < -0.2 and
            price_change > 0):
            return TrapType.FOMO_TRAP

        # Panic Trap: Retail selling + whales buying + price falling
        if (retail_sentiment < -0.5 and
            whale_direction > 0.2 and
            price_change < 0):
            return TrapType.PANIC_TRAP

        # Bull Trap: Price pumping but whales distributing
        if (price_change > 0.05 and  # 5%+ pump
            whale_direction < -0.3 and
            retail_sentiment > 0.3):
            return TrapType.BULL_TRAP

        # Bear Trap: Price dumping but whales accumulating
        if (price_change < -0.05 and  # 5%+ dump
            whale_direction > 0.3 and
            retail_sentiment < -0.3):
            return TrapType.BEAR_TRAP

        # Breakout Trap: Price breaking resistance but no whale support
        if (price_change > 0.03 and
            whale_direction < 0 and
            divergence_type == "retail_bullish_whale_bearish"):
            return TrapType.BREAKOUT_TRAP

        # Breakdown Trap: Price breaking support but whales buying
        if (price_change < -0.03 and
            whale_direction > 0 and
            divergence_type == "retail_bearish_whale_bullish"):
            return TrapType.BREAKDOWN_TRAP

        return TrapType.NONE

    def _calculate_severity(
        self,
        divergence: float,
        trap_type: TrapType,
        retail_sentiment: float,
        time_at_extreme: int
    ) -> TrapSeverity:
        """Calculate trap severity"""

        if trap_type == TrapType.NONE:
            return TrapSeverity.NONE

        # Base severity from divergence
        if divergence >= self.EXTREME_DIVERGENCE:
            base_severity = 4
        elif divergence >= self.SIGNIFICANT_DIVERGENCE:
            base_severity = 3
        elif divergence >= self.MINOR_DIVERGENCE:
            base_severity = 2
        else:
            base_severity = 1

        # Amplify if retail sentiment is extreme
        if abs(retail_sentiment) > 0.8:
            base_severity = min(4, base_severity + 1)

        # Amplify if pattern has been building
        if time_at_extreme > 24:
            base_severity = min(4, base_severity + 1)

        severity_map = {
            1: TrapSeverity.LOW,
            2: TrapSeverity.MEDIUM,
            3: TrapSeverity.HIGH,
            4: TrapSeverity.EXTREME
        }

        return severity_map.get(base_severity, TrapSeverity.LOW)

    def _generate_recommendation(
        self,
        trap_type: TrapType,
        severity: TrapSeverity,
        whale_direction: float
    ) -> str:
        """Generate trading recommendation based on trap"""

        if trap_type == TrapType.NONE:
            return "No trap detected - trade normally"

        if severity == TrapSeverity.LOW:
            return "Minor trap risk - proceed with caution, use tight stops"

        if severity == TrapSeverity.MEDIUM:
            return "Significant trap risk - avoid this trade, wait for clarity"

        # High/Extreme severity - counter-trade
        if trap_type in [TrapType.FOMO_TRAP, TrapType.BULL_TRAP, TrapType.BREAKOUT_TRAP]:
            return "HIGH TRAP RISK - Do NOT buy. Consider shorting with whale direction."

        if trap_type in [TrapType.PANIC_TRAP, TrapType.BEAR_TRAP, TrapType.BREAKDOWN_TRAP]:
            return "HIGH TRAP RISK - Do NOT sell. Consider buying with whale direction."

        return "Trap detected - avoid trading against smart money"

    def check_for_trap(
        self,
        asset: str,
        retail_sentiment: float,
        whale_direction: float,
        current_price: float,
        price_24h_ago: float,
        time_at_sentiment_extreme: int = 0
    ) -> TrapSignal:
        """
        Check if current conditions represent a liquidity trap.

        Args:
            asset: Asset symbol
            retail_sentiment: Current retail sentiment (-1 to +1)
            whale_direction: Smart money direction (-1 to +1)
            current_price: Current price
            price_24h_ago: Price 24 hours ago
            time_at_sentiment_extreme: Hours at current sentiment extreme

        Returns:
            TrapSignal with trap analysis
        """
        # Calculate price change
        price_change = (current_price - price_24h_ago) / price_24h_ago

        # Calculate divergence
        divergence, divergence_type = self._calculate_divergence(
            retail_sentiment, whale_direction
        )

        # Detect trap type
        trap_type = self._detect_trap_type(
            retail_sentiment,
            whale_direction,
            price_change,
            divergence,
            divergence_type
        )

        # Calculate severity
        severity = self._calculate_severity(
            divergence,
            trap_type,
            retail_sentiment,
            time_at_sentiment_extreme
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            trap_type, severity, whale_direction
        )

        # Calculate confidence
        confidence = min(1.0, divergence / self.EXTREME_DIVERGENCE)
        if trap_type != TrapType.NONE:
            confidence = max(0.5, confidence)

        # Generate reasoning
        if trap_type == TrapType.NONE:
            reasoning = f"Retail ({retail_sentiment:.2f}) and whales ({whale_direction:.2f}) relatively aligned"
        else:
            reasoning = (
                f"{trap_type.value.upper()}: Retail sentiment {retail_sentiment:.2f} "
                f"while whales {whale_direction:.2f}. "
                f"Divergence: {divergence:.2f}. "
                f"Price change: {price_change*100:.1f}%"
            )

        signal = TrapSignal(
            asset=asset,
            trap_type=trap_type,
            severity=severity,
            confidence=confidence,
            retail_sentiment=retail_sentiment,
            smart_money_direction=whale_direction,
            divergence=divergence,
            recommendation=recommendation,
            reasoning=reasoning
        )

        # Store in history
        if asset not in self.trap_history:
            self.trap_history[asset] = []
        self.trap_history[asset].append(signal)

        # Keep last 100 signals
        if len(self.trap_history[asset]) > 100:
            self.trap_history[asset] = self.trap_history[asset][-100:]

        # Callback for trap detection
        if trap_type != TrapType.NONE and severity.value >= 2:
            if self.on_trap_detected:
                self.on_trap_detected(signal)
            logger.warning(
                f"TRAP DETECTED: {asset} {trap_type.value} "
                f"(severity: {severity.name}, divergence: {divergence:.2f})"
            )

        return signal

    def is_safe_to_trade(
        self,
        asset: str,
        intended_direction: str,  # "BUY" or "SELL"
        retail_sentiment: float,
        whale_direction: float,
        current_price: float,
        price_24h_ago: float
    ) -> Tuple[bool, str]:
        """
        Quick check if it's safe to enter a trade.

        Returns (is_safe, reason)
        """
        trap = self.check_for_trap(
            asset, retail_sentiment, whale_direction,
            current_price, price_24h_ago
        )

        # Always safe if no trap
        if trap.trap_type == TrapType.NONE:
            return True, "No trap detected"

        # Low severity - caution but ok
        if trap.severity == TrapSeverity.LOW:
            return True, f"Minor {trap.trap_type.value} risk - use tight stops"

        # Medium+ severity - check direction alignment
        if trap.severity.value >= 2:
            # If intended direction aligns with whales, might be ok
            if intended_direction == "BUY" and whale_direction > 0.2:
                return True, "Buying with smart money despite retail trap"
            if intended_direction == "SELL" and whale_direction < -0.2:
                return True, "Selling with smart money despite retail trap"

            # Otherwise, block the trade
            return False, trap.recommendation

        return True, "Trade appears safe"

    def get_trap_summary(self, asset: str) -> Dict:
        """Get summary of trap analysis for an asset"""
        recent_traps = self.trap_history.get(asset, [])

        # Get most recent trap
        latest = recent_traps[-1] if recent_traps else None

        # Count traps in last 24h
        cutoff = datetime.now() - timedelta(hours=24)
        recent_count = sum(
            1 for t in recent_traps
            if t.timestamp > cutoff and t.trap_type != TrapType.NONE
        )

        return {
            "asset": asset,
            "latest_trap": {
                "type": latest.trap_type.value if latest else "none",
                "severity": latest.severity.name if latest else "NONE",
                "confidence": latest.confidence if latest else 0,
                "recommendation": latest.recommendation if latest else "No data"
            } if latest else None,
            "traps_24h": recent_count,
            "is_currently_trapped": (
                latest is not None and
                latest.trap_type != TrapType.NONE and
                latest.severity.value >= 2
            )
        }


# Demo
async def demo_liquidity_trap():
    """Demo the liquidity trap detector"""
    print("\n=== Liquidity Trap Detector ===")
    print("Don't be exit liquidity for the whales!\n")

    detector = LiquidityTrapDetector()

    def on_trap(signal: TrapSignal):
        print(f"\n  🚨 TRAP ALERT: {signal.trap_type.value.upper()}")
        print(f"      Severity: {signal.severity.name}")
        print(f"      {signal.recommendation}")

    detector.on_trap_detected = on_trap

    # Simulate scenarios
    scenarios = [
        {
            "name": "FOMO Trap - Retail buying peak",
            "retail_sentiment": 0.85,
            "whale_direction": -0.6,
            "price_change": 0.08,  # 8% up
            "desc": "Everyone bullish, but whales silently dumping"
        },
        {
            "name": "Panic Trap - Retail selling bottom",
            "retail_sentiment": -0.9,
            "whale_direction": 0.7,
            "price_change": -0.12,  # 12% down
            "desc": "Mass panic, but whales accumulating heavily"
        },
        {
            "name": "Healthy uptrend",
            "retail_sentiment": 0.5,
            "whale_direction": 0.4,
            "price_change": 0.05,
            "desc": "Retail and whales both bullish - aligned"
        },
        {
            "name": "False Breakout Setup",
            "retail_sentiment": 0.75,
            "whale_direction": -0.4,
            "price_change": 0.04,
            "desc": "Price breaking out, retail excited, whales distributing"
        },
    ]

    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")
        print(f"  Context: {scenario['desc']}")

        base_price = 50000
        current_price = base_price * (1 + scenario['price_change'])

        trap = detector.check_for_trap(
            asset="BTC",
            retail_sentiment=scenario['retail_sentiment'],
            whale_direction=scenario['whale_direction'],
            current_price=current_price,
            price_24h_ago=base_price
        )

        print(f"\n  Retail Sentiment: {trap.retail_sentiment:.2f}")
        print(f"  Whale Direction: {trap.smart_money_direction:.2f}")
        print(f"  Divergence: {trap.divergence:.2f}")
        print(f"  Trap Type: {trap.trap_type.value}")
        print(f"  Severity: {trap.severity.name}")
        print(f"  Confidence: {trap.confidence:.2f}")
        print(f"  Recommendation: {trap.recommendation}")

        # Check if safe to buy
        is_safe, reason = detector.is_safe_to_trade(
            "BTC", "BUY",
            scenario['retail_sentiment'],
            scenario['whale_direction'],
            current_price, base_price
        )
        print(f"\n  Safe to BUY? {'✅ Yes' if is_safe else '❌ No'} - {reason}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_liquidity_trap())
