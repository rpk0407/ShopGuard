"""
Sentiment Extremes Detector (Fear & Greed Analysis)
====================================================
Detects when market sentiment reaches extremes that signal reversal opportunities.

Core Principle:
    Extreme fear = buying opportunity (everyone already sold)
    Extreme greed = selling opportunity (everyone already bought)

The Math:
- When Fear & Greed < 20: 80%+ of retail has sold -> who's left to sell?
- When Fear & Greed > 80: 80%+ of retail has bought -> who's left to buy?
- Historical data shows extreme readings often precede reversals

This module:
1. Aggregates sentiment from multiple sources
2. Calculates Fear & Greed index
3. Detects sentiment extremes
4. Generates CONTRARIAN signals (not following the herd)
"""

import logging
import time
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class SentimentZone(Enum):
    """Sentiment zones based on Fear & Greed"""
    EXTREME_FEAR = "extreme_fear"      # 0-20: Strong contrarian BUY
    FEAR = "fear"                       # 20-40: Mild contrarian BUY
    NEUTRAL = "neutral"                 # 40-60: No contrarian signal
    GREED = "greed"                     # 60-80: Mild contrarian SELL
    EXTREME_GREED = "extreme_greed"    # 80-100: Strong contrarian SELL


class SignalStrength(Enum):
    """Strength of contrarian signal"""
    NONE = 0
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    EXTREME = 4


@dataclass
class SentimentReading:
    """A single sentiment reading"""
    source: str
    value: float          # 0-100 (0 = extreme fear, 100 = extreme greed)
    weight: float         # Source weight for aggregation
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FearGreedState:
    """Current Fear & Greed state"""
    value: float                    # 0-100
    zone: SentimentZone
    previous_value: float           # For momentum
    momentum: float                 # Rate of change
    time_in_zone: int              # Hours in current zone
    contrarian_signal: float       # -1 (sell) to +1 (buy)
    signal_strength: SignalStrength
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ContrarianSignal:
    """Contrarian trading signal from sentiment extremes"""
    asset: str
    direction: float           # -1 (contrarian sell) to +1 (contrarian buy)
    confidence: float          # 0-1
    fear_greed: float         # Current F&G value
    zone: SentimentZone
    signal_strength: SignalStrength
    time_in_extreme: int      # Hours at extreme
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)


class SentimentExtremesDetector:
    """
    Detects sentiment extremes for contrarian trading.

    Key Insight:
    - Markets are driven by emotion, not logic
    - When everyone is fearful, the selling is exhausted
    - When everyone is greedy, the buying is exhausted
    - Extreme sentiment = high probability reversal zone

    Signal Logic:
    - Extreme Fear (< 20) + Time in zone > 24h = STRONG BUY
    - Fear (20-40) + Dropping momentum = MODERATE BUY
    - Extreme Greed (> 80) + Time in zone > 24h = STRONG SELL
    - Greed (60-80) + Rising momentum = MODERATE SELL

    Important:
    - Don't fight the trend in neutral zone
    - Patience: Wait for extremes, don't force trades
    - Confirmation: Combine with smart money signals
    """

    # Zone thresholds
    EXTREME_FEAR_THRESHOLD = 20
    FEAR_THRESHOLD = 40
    GREED_THRESHOLD = 60
    EXTREME_GREED_THRESHOLD = 80

    # Time thresholds for strong signals (hours)
    MIN_TIME_IN_EXTREME = 12  # Need at least 12 hours in extreme
    STRONG_TIME_THRESHOLD = 48  # 48+ hours = very strong signal

    def __init__(
        self,
        history_size: int = 168,  # 1 week of hourly data
        smoothing_window: int = 6,  # 6-hour smoothing
    ):
        self.history_size = history_size
        self.smoothing_window = smoothing_window

        # Data storage
        self.readings: Dict[str, deque] = {}  # source -> readings
        self.fear_greed_history: deque = deque(maxlen=history_size)
        self.current_state: Optional[FearGreedState] = None

        # Zone tracking
        self._zone_entry_time: Optional[datetime] = None
        self._current_zone: Optional[SentimentZone] = None

        # Callbacks
        self.on_extreme_detected: Optional[Callable[[FearGreedState], None]] = None
        self.on_signal: Optional[Callable[[ContrarianSignal], None]] = None

        # Source weights (how much each source contributes)
        self.source_weights = {
            "social": 0.25,         # Twitter/Reddit sentiment
            "news": 0.20,           # News sentiment
            "volatility": 0.15,     # Price volatility (VIX-like)
            "momentum": 0.15,       # Price momentum
            "volume": 0.10,         # Trading volume
            "dominance": 0.10,      # BTC dominance
            "funding": 0.05,        # Funding rates (leverage)
        }

    def add_reading(
        self,
        source: str,
        value: float,  # 0-100 scale
        weight: Optional[float] = None
    ):
        """Add a sentiment reading from a source"""
        if source not in self.readings:
            self.readings[source] = deque(maxlen=self.history_size)

        reading = SentimentReading(
            source=source,
            value=max(0, min(100, value)),  # Clamp to 0-100
            weight=weight or self.source_weights.get(source, 0.1)
        )

        self.readings[source].append(reading)

    def calculate_fear_greed(self) -> float:
        """Calculate aggregated Fear & Greed index"""
        if not self.readings:
            return 50  # Neutral if no data

        total_weight = 0
        weighted_sum = 0

        for source, readings in self.readings.items():
            if not readings:
                continue

            # Use most recent reading from each source
            recent = readings[-1]

            # Only use readings from last hour
            age = (datetime.now() - recent.timestamp).total_seconds() / 3600
            if age > 1:
                continue

            weighted_sum += recent.value * recent.weight
            total_weight += recent.weight

        if total_weight == 0:
            return 50

        return weighted_sum / total_weight

    def _get_zone(self, value: float) -> SentimentZone:
        """Determine sentiment zone from value"""
        if value < self.EXTREME_FEAR_THRESHOLD:
            return SentimentZone.EXTREME_FEAR
        elif value < self.FEAR_THRESHOLD:
            return SentimentZone.FEAR
        elif value < self.GREED_THRESHOLD:
            return SentimentZone.NEUTRAL
        elif value < self.EXTREME_GREED_THRESHOLD:
            return SentimentZone.GREED
        else:
            return SentimentZone.EXTREME_GREED

    def _calculate_momentum(self) -> float:
        """Calculate sentiment momentum (rate of change)"""
        if len(self.fear_greed_history) < 2:
            return 0

        # Compare current to 6 hours ago
        lookback = min(6, len(self.fear_greed_history) - 1)
        current = self.fear_greed_history[-1]
        past = self.fear_greed_history[-1 - lookback]

        return (current - past) / lookback

    def _get_signal_strength(
        self,
        zone: SentimentZone,
        time_in_zone: int,
        momentum: float
    ) -> SignalStrength:
        """Determine signal strength based on zone, time, and momentum"""

        # Only generate signals in fear/greed zones
        if zone == SentimentZone.NEUTRAL:
            return SignalStrength.NONE

        # Extreme zones
        if zone in [SentimentZone.EXTREME_FEAR, SentimentZone.EXTREME_GREED]:
            if time_in_zone >= self.STRONG_TIME_THRESHOLD:
                return SignalStrength.EXTREME
            elif time_in_zone >= self.MIN_TIME_IN_EXTREME:
                return SignalStrength.STRONG
            else:
                return SignalStrength.MODERATE

        # Regular fear/greed zones
        if zone in [SentimentZone.FEAR, SentimentZone.GREED]:
            # Momentum helps determine strength
            # In fear zone: falling momentum = exhaustion = stronger buy
            # In greed zone: rising momentum = exhaustion = stronger sell
            if zone == SentimentZone.FEAR and momentum < -1:
                return SignalStrength.MODERATE
            elif zone == SentimentZone.GREED and momentum > 1:
                return SignalStrength.MODERATE
            else:
                return SignalStrength.WEAK

        return SignalStrength.NONE

    def update(self) -> FearGreedState:
        """Update Fear & Greed state and check for extremes"""
        current_value = self.calculate_fear_greed()

        # Store in history
        self.fear_greed_history.append(current_value)

        # Determine zone
        zone = self._get_zone(current_value)

        # Track zone changes
        if zone != self._current_zone:
            self._current_zone = zone
            self._zone_entry_time = datetime.now()

        # Calculate time in zone
        time_in_zone = 0
        if self._zone_entry_time:
            time_in_zone = int(
                (datetime.now() - self._zone_entry_time).total_seconds() / 3600
            )

        # Calculate momentum
        momentum = self._calculate_momentum()

        # Previous value for comparison
        previous_value = self.fear_greed_history[-2] if len(self.fear_greed_history) > 1 else current_value

        # Get signal strength
        signal_strength = self._get_signal_strength(zone, time_in_zone, momentum)

        # Calculate contrarian signal
        # In extreme fear: positive (buy) signal
        # In extreme greed: negative (sell) signal
        if zone == SentimentZone.EXTREME_FEAR:
            contrarian_signal = 0.8 + (20 - current_value) / 100  # 0.8 to 1.0
            reasoning = f"Extreme Fear ({current_value:.0f}) - Market exhausted, contrarian BUY"
        elif zone == SentimentZone.FEAR:
            contrarian_signal = 0.3 + (40 - current_value) / 50  # 0.3 to 0.7
            reasoning = f"Fear ({current_value:.0f}) - Potential accumulation zone"
        elif zone == SentimentZone.GREED:
            contrarian_signal = -0.3 - (current_value - 60) / 50  # -0.3 to -0.7
            reasoning = f"Greed ({current_value:.0f}) - Potential distribution zone"
        elif zone == SentimentZone.EXTREME_GREED:
            contrarian_signal = -0.8 - (current_value - 80) / 100  # -0.8 to -1.0
            reasoning = f"Extreme Greed ({current_value:.0f}) - Market euphoric, contrarian SELL"
        else:
            contrarian_signal = 0
            reasoning = f"Neutral ({current_value:.0f}) - No contrarian edge"

        # Adjust by time in zone (longer = stronger)
        if signal_strength in [SignalStrength.STRONG, SignalStrength.EXTREME]:
            time_multiplier = min(1.5, 1 + time_in_zone / 72)  # Up to 1.5x after 72h
            contrarian_signal *= time_multiplier

        # Clamp to [-1, 1]
        contrarian_signal = max(-1, min(1, contrarian_signal))

        state = FearGreedState(
            value=current_value,
            zone=zone,
            previous_value=previous_value,
            momentum=momentum,
            time_in_zone=time_in_zone,
            contrarian_signal=contrarian_signal,
            signal_strength=signal_strength,
            reasoning=reasoning
        )

        self.current_state = state

        # Callback for extreme detection
        if zone in [SentimentZone.EXTREME_FEAR, SentimentZone.EXTREME_GREED]:
            if self.on_extreme_detected:
                self.on_extreme_detected(state)

        return state

    def get_contrarian_signal(self, asset: str) -> Optional[ContrarianSignal]:
        """Get contrarian trading signal for an asset"""
        state = self.update()

        # Only generate signals with sufficient strength
        if state.signal_strength == SignalStrength.NONE:
            return None

        # Confidence based on signal strength and time
        confidence_map = {
            SignalStrength.WEAK: 0.4,
            SignalStrength.MODERATE: 0.6,
            SignalStrength.STRONG: 0.8,
            SignalStrength.EXTREME: 0.95
        }

        confidence = confidence_map.get(state.signal_strength, 0.3)

        signal = ContrarianSignal(
            asset=asset,
            direction=state.contrarian_signal,
            confidence=confidence,
            fear_greed=state.value,
            zone=state.zone,
            signal_strength=state.signal_strength,
            time_in_extreme=state.time_in_zone,
            reasoning=state.reasoning
        )

        if self.on_signal and abs(signal.direction) > 0.3:
            self.on_signal(signal)

        return signal

    def get_state_summary(self) -> Dict:
        """Get summary of current sentiment state"""
        state = self.update()

        return {
            "fear_greed": state.value,
            "zone": state.zone.value,
            "momentum": state.momentum,
            "time_in_zone_hours": state.time_in_zone,
            "contrarian_signal": state.contrarian_signal,
            "signal_strength": state.signal_strength.name,
            "reasoning": state.reasoning,
            "is_extreme": state.zone in [
                SentimentZone.EXTREME_FEAR,
                SentimentZone.EXTREME_GREED
            ]
        }

    def convert_social_sentiment(self, raw_sentiment: float) -> float:
        """
        Convert raw social sentiment (-1 to +1) to Fear & Greed scale (0-100).

        Raw sentiment: -1 (very bearish) to +1 (very bullish)
        Fear & Greed: 0 (extreme fear) to 100 (extreme greed)
        """
        # Map [-1, 1] to [0, 100]
        return (raw_sentiment + 1) * 50

    def convert_news_sentiment(self, raw_sentiment: float, urgency: float = 0) -> float:
        """
        Convert news sentiment to Fear & Greed scale.

        Accounts for urgency - negative urgent news creates more fear.
        """
        base = (raw_sentiment + 1) * 50

        # Urgent negative news amplifies fear
        if urgency > 0.5 and raw_sentiment < 0:
            fear_amplifier = urgency * abs(raw_sentiment) * 20
            base = max(0, base - fear_amplifier)

        # Urgent positive news amplifies greed
        if urgency > 0.5 and raw_sentiment > 0:
            greed_amplifier = urgency * raw_sentiment * 20
            base = min(100, base + greed_amplifier)

        return base


# Demo
async def demo_sentiment_extremes():
    """Demo the sentiment extremes detector"""
    print("\n=== Sentiment Extremes Detector ===")
    print("'Be fearful when others are greedy, and greedy when others are fearful'\n")

    detector = SentimentExtremesDetector()

    def on_extreme(state: FearGreedState):
        print(f"  ⚠️  EXTREME DETECTED: {state.zone.value}")
        print(f"      Value: {state.value:.0f}")
        print(f"      Time in zone: {state.time_in_zone}h")

    def on_signal(signal: ContrarianSignal):
        direction = "BUY" if signal.direction > 0 else "SELL"
        print(f"\n  📊 CONTRARIAN SIGNAL: {signal.asset} {direction}")
        print(f"      Confidence: {signal.confidence:.2f}")
        print(f"      Reasoning: {signal.reasoning}")

    detector.on_extreme_detected = on_extreme
    detector.on_signal = on_signal

    # Simulate different scenarios
    scenarios = [
        {"name": "Market Panic", "social": -0.8, "news": -0.6, "volatility": 85},
        {"name": "Extreme Fear", "social": -0.9, "news": -0.7, "volatility": 90},
        {"name": "Recovery Beginning", "social": -0.5, "news": -0.3, "volatility": 60},
        {"name": "Neutral Market", "social": 0.1, "news": 0.0, "volatility": 40},
        {"name": "Building Greed", "social": 0.6, "news": 0.5, "volatility": 30},
        {"name": "Euphoria", "social": 0.9, "news": 0.8, "volatility": 25},
    ]

    for scenario in scenarios:
        print(f"\n--- Scenario: {scenario['name']} ---")

        # Add readings
        detector.add_reading(
            "social",
            detector.convert_social_sentiment(scenario["social"])
        )
        detector.add_reading(
            "news",
            detector.convert_news_sentiment(scenario["news"])
        )
        detector.add_reading(
            "volatility",
            100 - scenario["volatility"]  # High volatility = fear
        )

        # Get state
        summary = detector.get_state_summary()
        print(f"  Fear & Greed: {summary['fear_greed']:.0f}")
        print(f"  Zone: {summary['zone']}")
        print(f"  Contrarian Signal: {summary['contrarian_signal']:.2f}")
        print(f"  Reasoning: {summary['reasoning']}")

        # Get trading signal
        signal = detector.get_contrarian_signal("BTC")
        if signal:
            direction = "CONTRARIAN BUY" if signal.direction > 0 else "CONTRARIAN SELL"
            print(f"  → Trade: {direction} (strength: {signal.signal_strength.name})")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_sentiment_extremes())
