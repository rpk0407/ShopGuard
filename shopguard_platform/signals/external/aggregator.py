"""
External Signal Aggregator
==========================
Combines signals from multiple external sources into unified trading signals.

Integration with TitanBrain:
- External signals feed into the signal generation pipeline
- Each source has configurable weight
- Signals are normalized and combined with technical analysis
- Confidence thresholds filter noise

Signal Flow:
1. Polymarket -> Prediction probability changes
2. Social -> Sentiment + volume spikes
3. News -> Breaking news impact
4. Aggregator -> Weighted combination
5. TitanBrain -> Final signal with technical confirmation
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

from .polymarket import PolymarketScanner, PredictionSignal
from .social_sentiment import SocialSentimentAnalyzer, SentimentSignal
from .news_sentiment import NewsSentimentScanner, NewsSignal

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of external signals"""
    PREDICTION_MARKET = "prediction"
    SOCIAL_SENTIMENT = "social"
    NEWS = "news"


@dataclass
class ExternalSignalConfig:
    """Configuration for external signal sources"""
    # Enable/disable sources
    enable_polymarket: bool = True
    enable_social: bool = True
    enable_news: bool = True

    # Source weights (should sum to 1.0)
    weight_polymarket: float = 0.3
    weight_social: float = 0.3
    weight_news: float = 0.4

    # API keys (optional)
    twitter_bearer_token: Optional[str] = None
    newsapi_key: Optional[str] = None
    lunarcrush_api_key: Optional[str] = None

    # Refresh intervals (seconds)
    polymarket_interval: int = 300  # 5 minutes
    social_interval: int = 300      # 5 minutes
    news_interval: int = 120        # 2 minutes

    # Thresholds
    min_confidence: float = 0.3     # Minimum confidence to include
    min_signal_strength: float = 0.2  # Minimum |direction| to trigger

    # Assets to track
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH", "SOL"])


@dataclass
class AggregatedSignal:
    """Combined signal from all external sources"""
    asset: str
    direction: float           # -1 to +1
    confidence: float          # 0 to 1
    urgency: float            # 0 to 1 (time sensitivity)

    # Component signals
    prediction_signal: Optional[float] = None
    social_signal: Optional[float] = None
    news_signal: Optional[float] = None

    # Metadata
    source_count: int = 0      # Number of active sources
    dominant_source: Optional[SignalType] = None
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "asset": self.asset,
            "direction": self.direction,
            "confidence": self.confidence,
            "urgency": self.urgency,
            "prediction_signal": self.prediction_signal,
            "social_signal": self.social_signal,
            "news_signal": self.news_signal,
            "source_count": self.source_count,
            "dominant_source": self.dominant_source.value if self.dominant_source else None,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat()
        }


class SignalAggregator:
    """
    Aggregates external signals for trading decisions.

    Usage:
        config = ExternalSignalConfig(
            enable_polymarket=True,
            enable_social=True,
            enable_news=True,
            assets=["BTC", "ETH"]
        )

        aggregator = SignalAggregator(config)
        await aggregator.start()

        # Get current signal for BTC
        signal = aggregator.get_signal("BTC")

        # Or subscribe to signals
        aggregator.on_signal = my_callback
    """

    def __init__(self, config: ExternalSignalConfig):
        self.config = config

        # Initialize scanners based on config
        self.polymarket: Optional[PolymarketScanner] = None
        self.social: Optional[SocialSentimentAnalyzer] = None
        self.news: Optional[NewsSentimentScanner] = None

        if config.enable_polymarket:
            self.polymarket = PolymarketScanner(
                refresh_interval=config.polymarket_interval
            )

        if config.enable_social:
            self.social = SocialSentimentAnalyzer(
                twitter_bearer_token=config.twitter_bearer_token,
                lunarcrush_api_key=config.lunarcrush_api_key,
                refresh_interval=config.social_interval
            )

        if config.enable_news:
            self.news = NewsSentimentScanner(
                newsapi_key=config.newsapi_key,
                refresh_interval=config.news_interval
            )

        # Signal storage
        self.signals: Dict[str, AggregatedSignal] = {}
        self.signal_history: Dict[str, List[AggregatedSignal]] = {}

        # Callbacks
        self.on_signal: Optional[Callable[[AggregatedSignal], None]] = None
        self.on_urgent_signal: Optional[Callable[[AggregatedSignal], None]] = None

        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the aggregator"""
        logger.info("Starting external signal aggregator...")

        # Set up callbacks on individual scanners
        if self.polymarket:
            self.polymarket.on_signal = self._on_prediction_signal

        if self.social:
            self.social.on_signal = self._on_social_signal

        if self.news:
            self.news.on_signal = self._on_news_signal
            self.news.on_breaking_news = self._on_breaking_news

        self._running = True

        # Initial refresh
        self.refresh_all()

        # Start background refresh loop
        self._task = asyncio.create_task(self._refresh_loop())

        logger.info(f"External signals active for: {self.config.assets}")

    async def stop(self):
        """Stop the aggregator"""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("External signal aggregator stopped")

    async def _refresh_loop(self):
        """Background refresh loop"""
        while self._running:
            try:
                self.refresh_all()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Refresh error: {e}")
                await asyncio.sleep(30)

    def refresh_all(self):
        """Refresh all signal sources"""
        if self.polymarket:
            self.polymarket.refresh_markets()

        if self.social:
            self.social.refresh_data(self.config.assets)

        if self.news:
            self.news.refresh_news()

        # Aggregate signals for each asset
        for asset in self.config.assets:
            self._aggregate_signal(asset)

    def _on_prediction_signal(self, signal: PredictionSignal):
        """Handle prediction market signal"""
        self._aggregate_signal(signal.asset)

    def _on_social_signal(self, signal: SentimentSignal):
        """Handle social sentiment signal"""
        self._aggregate_signal(signal.asset)

    def _on_news_signal(self, signal: NewsSignal):
        """Handle news signal"""
        self._aggregate_signal(signal.asset)

    def _on_breaking_news(self, article):
        """Handle breaking news - high urgency"""
        for asset in article.mentioned_assets:
            if asset in self.config.assets:
                signal = self.signals.get(asset)
                if signal and self.on_urgent_signal:
                    signal.urgency = max(signal.urgency, 0.8)
                    self.on_urgent_signal(signal)

    def _aggregate_signal(self, asset: str):
        """Aggregate signals for a single asset"""
        components = []
        weights = []
        urgency = 0.0

        # Get prediction market signal
        prediction_direction = None
        if self.polymarket:
            pred_signal = self.polymarket.get_current_signal(asset)
            if pred_signal and pred_signal.confidence >= self.config.min_confidence:
                components.append(pred_signal.direction)
                weights.append(self.config.weight_polymarket * pred_signal.confidence)
                prediction_direction = pred_signal.direction

        # Get social sentiment signal
        social_direction = None
        if self.social:
            social_signal = self.social.get_current_signal(asset)
            if social_signal and social_signal.confidence >= self.config.min_confidence:
                components.append(social_signal.direction)
                weights.append(self.config.weight_social * social_signal.confidence)
                social_direction = social_signal.direction

        # Get news signal
        news_direction = None
        if self.news:
            news_signal = self.news.get_current_signal(asset)
            if news_signal and news_signal.confidence >= self.config.min_confidence:
                components.append(news_signal.direction)
                weights.append(self.config.weight_news * news_signal.confidence)
                news_direction = news_signal.direction
                urgency = max(urgency, news_signal.urgency)

        # Calculate weighted average
        if not components:
            # No signals available
            signal = AggregatedSignal(
                asset=asset,
                direction=0,
                confidence=0,
                urgency=0,
                reasoning="No external signals available"
            )
        else:
            total_weight = sum(weights)
            weighted_direction = sum(c * w for c, w in zip(components, weights)) / total_weight

            # Confidence based on agreement between sources
            if len(components) > 1:
                # Check if sources agree
                signs = [1 if c > 0 else -1 if c < 0 else 0 for c in components]
                agreement = sum(signs) / len(signs)
                confidence = (total_weight / len(components)) * (0.5 + 0.5 * abs(agreement))
            else:
                confidence = total_weight

            # Determine dominant source
            max_contribution = 0
            dominant = None
            if prediction_direction is not None:
                contrib = abs(prediction_direction * self.config.weight_polymarket)
                if contrib > max_contribution:
                    max_contribution = contrib
                    dominant = SignalType.PREDICTION_MARKET

            if social_direction is not None:
                contrib = abs(social_direction * self.config.weight_social)
                if contrib > max_contribution:
                    max_contribution = contrib
                    dominant = SignalType.SOCIAL_SENTIMENT

            if news_direction is not None:
                contrib = abs(news_direction * self.config.weight_news)
                if contrib > max_contribution:
                    dominant = SignalType.NEWS

            # Generate reasoning
            reasons = []
            if prediction_direction is not None:
                reasons.append(f"Prediction: {'bullish' if prediction_direction > 0 else 'bearish'}")
            if social_direction is not None:
                reasons.append(f"Social: {'bullish' if social_direction > 0 else 'bearish'}")
            if news_direction is not None:
                reasons.append(f"News: {'bullish' if news_direction > 0 else 'bearish'}")

            signal = AggregatedSignal(
                asset=asset,
                direction=weighted_direction,
                confidence=confidence,
                urgency=urgency,
                prediction_signal=prediction_direction,
                social_signal=social_direction,
                news_signal=news_direction,
                source_count=len(components),
                dominant_source=dominant,
                reasoning=", ".join(reasons)
            )

        # Store signal
        old_signal = self.signals.get(asset)
        self.signals[asset] = signal

        # Track history
        if asset not in self.signal_history:
            self.signal_history[asset] = []
        self.signal_history[asset].append(signal)

        # Keep last 100 signals
        if len(self.signal_history[asset]) > 100:
            self.signal_history[asset] = self.signal_history[asset][-100:]

        # Emit signal if significant change
        if self.on_signal:
            if abs(signal.direction) >= self.config.min_signal_strength:
                if old_signal is None or abs(signal.direction - old_signal.direction) > 0.1:
                    self.on_signal(signal)

    def get_signal(self, asset: str) -> Optional[AggregatedSignal]:
        """Get current aggregated signal for an asset"""
        self.refresh_all()
        return self.signals.get(asset)

    def get_all_signals(self) -> Dict[str, AggregatedSignal]:
        """Get current signals for all tracked assets"""
        self.refresh_all()
        return self.signals.copy()

    def get_signal_for_titan(self, asset: str) -> Optional[Dict[str, float]]:
        """
        Get signal in format expected by TitanBrain.

        Returns dict with:
        - external_direction: -1 to 1
        - external_confidence: 0 to 1
        - external_urgency: 0 to 1
        """
        signal = self.get_signal(asset)

        if signal is None or signal.confidence < self.config.min_confidence:
            return None

        return {
            "external_direction": signal.direction,
            "external_confidence": signal.confidence,
            "external_urgency": signal.urgency,
            "prediction_signal": signal.prediction_signal or 0,
            "social_signal": signal.social_signal or 0,
            "news_signal": signal.news_signal or 0
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all external signals"""
        summary = {
            "sources": {
                "polymarket": self.polymarket is not None,
                "social": self.social is not None,
                "news": self.news is not None
            },
            "assets": {},
            "overall_sentiment": 0,
            "urgent_count": 0
        }

        total_direction = 0
        count = 0

        for asset in self.config.assets:
            signal = self.signals.get(asset)
            if signal:
                summary["assets"][asset] = {
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "urgency": signal.urgency,
                    "sources": signal.source_count,
                    "dominant": signal.dominant_source.value if signal.dominant_source else None
                }

                total_direction += signal.direction
                count += 1

                if signal.urgency > 0.5:
                    summary["urgent_count"] += 1

        if count > 0:
            summary["overall_sentiment"] = total_direction / count

        # Add source-specific summaries
        if self.polymarket:
            summary["polymarket"] = self.polymarket.get_market_summary()

        if self.social:
            summary["social"] = self.social.get_social_summary(self.config.assets)

        if self.news:
            summary["news"] = self.news.get_news_summary()

        return summary


# Demo function
async def demo_aggregator():
    """Demo the signal aggregator"""
    print("\n=== External Signal Aggregator Demo ===\n")

    config = ExternalSignalConfig(
        enable_polymarket=True,
        enable_social=True,
        enable_news=True,
        assets=["BTC", "ETH", "SOL"],
        min_confidence=0.2
    )

    aggregator = SignalAggregator(config)

    def on_signal(signal: AggregatedSignal):
        direction = "BULLISH" if signal.direction > 0 else "BEARISH" if signal.direction < 0 else "NEUTRAL"
        print(f"\n  AGGREGATED SIGNAL: {signal.asset} {direction}")
        print(f"    Direction: {signal.direction:.2f}")
        print(f"    Confidence: {signal.confidence:.2f}")
        print(f"    Urgency: {signal.urgency:.2f}")
        print(f"    Sources: {signal.source_count}")
        if signal.dominant_source:
            print(f"    Dominant: {signal.dominant_source.value}")
        print(f"    Reasoning: {signal.reasoning}")

    def on_urgent(signal: AggregatedSignal):
        print(f"\n  ⚡ URGENT: {signal.asset} - {signal.reasoning}")

    aggregator.on_signal = on_signal
    aggregator.on_urgent_signal = on_urgent

    print("Starting aggregator...")
    await aggregator.start()

    print("\nFetching signals...")
    await asyncio.sleep(2)

    # Get summary
    summary = aggregator.get_summary()

    print("\n--- Summary ---")
    print(f"Active Sources: {[k for k, v in summary['sources'].items() if v]}")
    print(f"Overall Sentiment: {summary['overall_sentiment']:.2f}")
    print(f"Urgent Signals: {summary['urgent_count']}")

    print("\n--- Asset Signals ---")
    for asset, data in summary.get("assets", {}).items():
        direction = "BULLISH" if data["direction"] > 0 else "BEARISH" if data["direction"] < 0 else "NEUTRAL"
        print(f"\n{asset}: {direction}")
        print(f"  Direction: {data['direction']:.2f}")
        print(f"  Confidence: {data['confidence']:.2f}")
        print(f"  Sources: {data['sources']}")

    # Get TitanBrain-compatible signal
    print("\n--- TitanBrain Integration ---")
    for asset in config.assets:
        titan_signal = aggregator.get_signal_for_titan(asset)
        if titan_signal:
            print(f"\n{asset}:")
            print(f"  external_direction: {titan_signal['external_direction']:.2f}")
            print(f"  external_confidence: {titan_signal['external_confidence']:.2f}")
            print(f"  external_urgency: {titan_signal['external_urgency']:.2f}")

    await aggregator.stop()
    print("\nDemo complete!")


if __name__ == "__main__":
    asyncio.run(demo_aggregator())
