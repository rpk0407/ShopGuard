"""
Smart Money Signal Aggregator
=============================
Aggregates external signals with a CONTRARIAN smart money approach.

Core Philosophy:
    "The market is designed to transfer wealth from the impatient to the patient,
     from the emotional to the rational, from the retail to the institutions."

This aggregator does NOT follow the herd. Instead:
1. Tracks what SMART MONEY (whales) is doing
2. Tracks what RETAIL (dumb money) is doing
3. Generates signals based on DIVERGENCE between them
4. When retail panics but whales accumulate = BUY
5. When retail FOMs but whales distribute = SELL

Signal Priority (highest to lowest):
1. Smart Money Flow (whale tracking, exchange flows)
2. Liquidity Trap Detection (don't be exit liquidity)
3. Sentiment Extremes (Fear & Greed contrarian)
4. Filtered News (only real market-moving events)
5. Social Sentiment (inverted - contrarian)

The goal: NEVER be exit liquidity for smart money.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

# Import our smart money components
from .smart_money import SmartMoneyTracker, SmartMoneySignal
from .sentiment_extremes import SentimentExtremesDetector, ContrarianSignal, FearGreedState
from .liquidity_trap import LiquidityTrapDetector, TrapSignal, TrapSeverity
from .news_filter import NewsImpactFilter, FilteredNews, NewsImpact, NewsAction

# Import original components for data gathering (not signal generation)
from .polymarket import PolymarketScanner
from .social_sentiment import SocialSentimentAnalyzer
from .news_sentiment import NewsSentimentScanner

logger = logging.getLogger(__name__)


class SignalMode(Enum):
    """Signal generation mode"""
    CONTRARIAN = "contrarian"       # Default: Trade against retail
    FOLLOW_WHALES = "follow_whales"  # Follow smart money only
    DEFENSIVE = "defensive"          # Avoid traps, don't counter-trade
    AGGRESSIVE = "aggressive"        # Counter-trade all extremes


@dataclass
class ExternalSignalConfig:
    """Configuration for external signal aggregation"""
    # Mode
    mode: SignalMode = SignalMode.CONTRARIAN

    # Enable/disable components
    enable_smart_money: bool = True
    enable_sentiment_extremes: bool = True
    enable_liquidity_trap: bool = True
    enable_news_filter: bool = True
    enable_polymarket: bool = True
    enable_social: bool = True

    # Weights for signal combination (smart money weighted highest)
    weight_smart_money: float = 0.40      # Whale activity
    weight_trap_detection: float = 0.25   # Liquidity traps
    weight_sentiment: float = 0.20        # Fear & Greed contrarian
    weight_news: float = 0.10             # Filtered news only
    weight_polymarket: float = 0.05       # Prediction markets

    # API keys
    whale_alert_api_key: Optional[str] = None
    twitter_bearer_token: Optional[str] = None
    newsapi_key: Optional[str] = None

    # Thresholds
    min_confidence: float = 0.4
    min_signal_strength: float = 0.3
    trap_severity_threshold: int = 2  # Block trades if trap severity >= this

    # Reaction delays
    news_reaction_delay: int = 30  # Minutes to wait after news

    # Assets
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH", "SOL"])


@dataclass
class AggregatedSignal:
    """Aggregated signal from all smart money sources"""
    asset: str
    direction: float           # -1 to +1 (contrarian-adjusted)
    confidence: float          # 0 to 1
    urgency: float            # 0 to 1

    # Component signals
    smart_money_signal: Optional[float] = None
    retail_sentiment: Optional[float] = None
    contrarian_signal: Optional[float] = None
    trap_detected: bool = False
    trap_type: Optional[str] = None

    # Analysis
    whale_retail_divergence: float = 0
    fear_greed_value: float = 50
    is_extreme_sentiment: bool = False

    # Metadata
    source_count: int = 0
    mode: SignalMode = SignalMode.CONTRARIAN
    reasoning: str = ""
    recommendation: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "asset": self.asset,
            "direction": self.direction,
            "confidence": self.confidence,
            "urgency": self.urgency,
            "smart_money_signal": self.smart_money_signal,
            "retail_sentiment": self.retail_sentiment,
            "whale_retail_divergence": self.whale_retail_divergence,
            "trap_detected": self.trap_detected,
            "trap_type": self.trap_type,
            "fear_greed": self.fear_greed_value,
            "is_extreme": self.is_extreme_sentiment,
            "mode": self.mode.value,
            "reasoning": self.reasoning,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp.isoformat()
        }


class SignalAggregator:
    """
    Smart Money Signal Aggregator - Contrarian approach.

    Usage:
        config = ExternalSignalConfig(
            mode=SignalMode.CONTRARIAN,
            assets=["BTC", "ETH"]
        )

        aggregator = SignalAggregator(config)
        await aggregator.start()

        # Before any trade
        signal = aggregator.get_signal("BTC")

        if signal.trap_detected:
            print(f"TRAP DETECTED: {signal.trap_type}")
            print(f"Recommendation: {signal.recommendation}")
            # Don't trade!

        if signal.direction > 0.3:
            print(f"CONTRARIAN BUY: Whales accumulating while retail panics")
    """

    def __init__(self, config: ExternalSignalConfig):
        self.config = config

        # Initialize smart money components
        self.smart_money: Optional[SmartMoneyTracker] = None
        self.sentiment_detector: Optional[SentimentExtremesDetector] = None
        self.trap_detector: Optional[LiquidityTrapDetector] = None
        self.news_filter: Optional[NewsImpactFilter] = None

        # Initialize data gathering components
        self.polymarket: Optional[PolymarketScanner] = None
        self.social: Optional[SocialSentimentAnalyzer] = None
        self.news: Optional[NewsSentimentScanner] = None

        if config.enable_smart_money:
            self.smart_money = SmartMoneyTracker(
                whale_alert_api_key=config.whale_alert_api_key
            )

        if config.enable_sentiment_extremes:
            self.sentiment_detector = SentimentExtremesDetector()

        if config.enable_liquidity_trap:
            self.trap_detector = LiquidityTrapDetector()

        if config.enable_news_filter:
            self.news_filter = NewsImpactFilter()

        if config.enable_polymarket:
            self.polymarket = PolymarketScanner()

        if config.enable_social:
            self.social = SocialSentimentAnalyzer(
                twitter_bearer_token=config.twitter_bearer_token
            )

        # Always enable news scanner for data (filter handles classification)
        self.news = NewsSentimentScanner(newsapi_key=config.newsapi_key)

        # Signal storage
        self.signals: Dict[str, AggregatedSignal] = {}
        self.price_cache: Dict[str, float] = {}

        # Callbacks
        self.on_signal: Optional[Callable[[AggregatedSignal], None]] = None
        self.on_trap_alert: Optional[Callable[[TrapSignal], None]] = None
        self.on_extreme_sentiment: Optional[Callable[[FearGreedState], None]] = None

        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the aggregator"""
        logger.info(f"Starting Smart Money Aggregator in {self.config.mode.value} mode...")

        # Set up callbacks
        if self.smart_money:
            self.smart_money.on_signal = self._on_smart_money_signal

        if self.sentiment_detector:
            self.sentiment_detector.on_extreme_detected = self._on_extreme_sentiment

        if self.trap_detector:
            self.trap_detector.on_trap_detected = self._on_trap_detected

        self._running = True

        # Initial refresh
        self.refresh_all()

        # Background refresh
        self._task = asyncio.create_task(self._refresh_loop())

        logger.info(f"Smart Money Aggregator active for: {self.config.assets}")

    async def stop(self):
        """Stop the aggregator"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Smart Money Aggregator stopped")

    async def _refresh_loop(self):
        """Background refresh loop"""
        while self._running:
            try:
                self.refresh_all()
                await asyncio.sleep(120)  # Refresh every 2 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Refresh error: {e}")
                await asyncio.sleep(60)

    def refresh_all(self):
        """Refresh all data sources"""
        # Gather retail sentiment from social/news
        if self.social:
            self.social.refresh_data(self.config.assets)

        if self.news:
            self.news.refresh_news()

        if self.polymarket:
            self.polymarket.refresh_markets()

        # Update smart money tracking
        if self.smart_money:
            self.smart_money.refresh_data(self.config.assets)

        # Aggregate for each asset
        for asset in self.config.assets:
            self._aggregate_signal(asset)

    def _get_retail_sentiment(self, asset: str) -> float:
        """Get retail sentiment from social/news sources"""
        sentiments = []
        weights = []

        # Social sentiment
        if self.social:
            social_signal = self.social.get_current_signal(asset)
            if social_signal:
                sentiments.append(social_signal.direction)
                weights.append(0.6)

        # News sentiment (raw, before filtering)
        if self.news:
            news_signal = self.news.get_current_signal(asset)
            if news_signal:
                sentiments.append(news_signal.direction)
                weights.append(0.4)

        if not sentiments:
            return 0

        return sum(s * w for s, w in zip(sentiments, weights)) / sum(weights)

    def _get_filtered_news_sentiment(self, asset: str) -> float:
        """Get filtered news sentiment (noise removed)"""
        if not self.news or not self.news_filter:
            return 0

        # Get recent news articles
        recent_news = [
            article for article in self.news.articles.values()
            if asset in article.mentioned_assets
        ]

        if not recent_news:
            return 0

        filtered_sentiments = []

        for article in recent_news[:10]:  # Last 10 articles
            filtered = self.news_filter.filter_news(
                title=article.title,
                source=article.source.value,
                original_sentiment=article.sentiment_score,
                content=article.summary,
                category=article.category.value
            )

            # Only use non-noise news
            if filtered.impact != NewsImpact.NOISE:
                filtered_sentiments.append(filtered.adjusted_sentiment)

        if not filtered_sentiments:
            return 0

        return sum(filtered_sentiments) / len(filtered_sentiments)

    def _aggregate_signal(self, asset: str):
        """Aggregate signals for an asset using smart money approach"""
        components = []
        weights = []
        reasons = []

        # 1. Get retail sentiment (what the herd is doing)
        retail_sentiment = self._get_retail_sentiment(asset)

        # 2. Feed sentiment to Fear & Greed detector
        if self.sentiment_detector:
            self.sentiment_detector.add_reading(
                "social",
                self.sentiment_detector.convert_social_sentiment(retail_sentiment)
            )
            fg_state = self.sentiment_detector.update()
            fear_greed = fg_state.value
            is_extreme = fg_state.zone.value in ["extreme_fear", "extreme_greed"]
        else:
            fear_greed = 50
            is_extreme = False

        # 3. Get smart money signal
        smart_money_direction = 0
        if self.smart_money:
            sm_signal = self.smart_money.get_signal(asset, retail_sentiment)
            if sm_signal:
                smart_money_direction = sm_signal.direction
                components.append(smart_money_direction)
                weights.append(self.config.weight_smart_money)
                reasons.append(f"Smart Money: {sm_signal.signal_type}")

        # 4. Calculate whale-retail divergence
        divergence = smart_money_direction - retail_sentiment

        # 5. Check for liquidity traps
        trap_detected = False
        trap_type = None
        trap_recommendation = ""

        if self.trap_detector:
            current_price = self.price_cache.get(asset, 50000)  # Default
            price_24h = current_price * 0.98  # Estimate

            trap = self.trap_detector.check_for_trap(
                asset=asset,
                retail_sentiment=retail_sentiment,
                whale_direction=smart_money_direction,
                current_price=current_price,
                price_24h_ago=price_24h
            )

            if trap.severity.value >= self.config.trap_severity_threshold:
                trap_detected = True
                trap_type = trap.trap_type.value
                trap_recommendation = trap.recommendation
                reasons.append(f"TRAP: {trap_type}")

        # 6. Get contrarian signal from sentiment extremes
        contrarian_direction = 0
        if self.sentiment_detector:
            contrarian = self.sentiment_detector.get_contrarian_signal(asset)
            if contrarian:
                contrarian_direction = contrarian.direction
                components.append(contrarian_direction)
                weights.append(self.config.weight_sentiment)
                if is_extreme:
                    reasons.append(f"Extreme {'Fear' if contrarian_direction > 0 else 'Greed'}")

        # 7. Get filtered news signal
        news_direction = self._get_filtered_news_sentiment(asset)
        if abs(news_direction) > 0.2:
            components.append(news_direction)
            weights.append(self.config.weight_news)
            reasons.append("Filtered News")

        # 8. Get polymarket signal (less important)
        if self.polymarket:
            pm_signal = self.polymarket.get_current_signal(asset)
            if pm_signal and pm_signal.confidence > 0.4:
                components.append(pm_signal.direction)
                weights.append(self.config.weight_polymarket)
                reasons.append("Prediction Market")

        # === AGGREGATE BASED ON MODE ===
        if not components:
            direction = 0
            confidence = 0
            recommendation = "No signals available"
        else:
            if self.config.mode == SignalMode.CONTRARIAN:
                # Contrarian mode: Follow smart money, fade retail
                if abs(divergence) > 0.5:
                    # Strong divergence - contrarian opportunity
                    direction = smart_money_direction  # Follow whales
                    confidence = min(1.0, abs(divergence))
                    if direction > 0:
                        recommendation = "CONTRARIAN BUY: Whales accumulating while retail panics"
                    else:
                        recommendation = "CONTRARIAN SELL: Whales distributing while retail FOMOs"
                else:
                    # Low divergence - use weighted average
                    total_weight = sum(weights)
                    direction = sum(c * w for c, w in zip(components, weights)) / total_weight
                    confidence = total_weight / len(components)
                    recommendation = "Following smart money flow"

            elif self.config.mode == SignalMode.FOLLOW_WHALES:
                # Only follow whale signals, ignore retail completely
                direction = smart_money_direction
                confidence = 0.7 if abs(direction) > 0.3 else 0.4
                recommendation = "Following whale activity only"

            elif self.config.mode == SignalMode.DEFENSIVE:
                # Avoid traps, don't counter-trade
                if trap_detected:
                    direction = 0
                    confidence = 0
                    recommendation = f"BLOCKED: {trap_recommendation}"
                else:
                    total_weight = sum(weights)
                    direction = sum(c * w for c, w in zip(components, weights)) / total_weight
                    confidence = total_weight / len(components) * 0.7
                    recommendation = "Defensive mode - proceed with caution"

            elif self.config.mode == SignalMode.AGGRESSIVE:
                # Aggressive counter-trading
                if is_extreme:
                    direction = contrarian_direction * 1.2  # Amplify
                    confidence = 0.85
                    recommendation = f"AGGRESSIVE: Counter-trading extreme sentiment"
                else:
                    direction = smart_money_direction
                    confidence = 0.6
                    recommendation = "Following smart money"

            # Clamp direction
            direction = max(-1, min(1, direction))

        # Block trade if trap detected and severity high
        if trap_detected and self.config.mode != SignalMode.AGGRESSIVE:
            confidence *= 0.3  # Heavily reduce confidence
            if trap_type in ["fomo_trap", "panic_trap"]:
                recommendation = f"⚠️ {trap_recommendation}"

        # Calculate urgency
        urgency = 0
        if is_extreme:
            urgency = 0.7
        if trap_detected:
            urgency = 0.9  # High urgency to avoid trap

        # Create aggregated signal
        signal = AggregatedSignal(
            asset=asset,
            direction=direction,
            confidence=confidence,
            urgency=urgency,
            smart_money_signal=smart_money_direction,
            retail_sentiment=retail_sentiment,
            contrarian_signal=contrarian_direction,
            trap_detected=trap_detected,
            trap_type=trap_type,
            whale_retail_divergence=divergence,
            fear_greed_value=fear_greed,
            is_extreme_sentiment=is_extreme,
            source_count=len(components),
            mode=self.config.mode,
            reasoning="; ".join(reasons) if reasons else "No significant signals",
            recommendation=recommendation
        )

        self.signals[asset] = signal

        # Emit callbacks
        if self.on_signal and abs(direction) > self.config.min_signal_strength:
            self.on_signal(signal)

    # Callbacks
    def _on_smart_money_signal(self, signal: SmartMoneySignal):
        logger.info(f"Smart Money: {signal.asset} {signal.signal_type} (direction: {signal.direction:.2f})")

    def _on_extreme_sentiment(self, state: FearGreedState):
        logger.info(f"Extreme Sentiment: {state.zone.value} (F&G: {state.value:.0f})")
        if self.on_extreme_sentiment:
            self.on_extreme_sentiment(state)

    def _on_trap_detected(self, trap: TrapSignal):
        logger.warning(f"TRAP DETECTED: {trap.asset} {trap.trap_type.value} (severity: {trap.severity.name})")
        if self.on_trap_alert:
            self.on_trap_alert(trap)

    # Public API
    def get_signal(self, asset: str) -> Optional[AggregatedSignal]:
        """Get current aggregated signal for an asset"""
        self.refresh_all()
        return self.signals.get(asset)

    def get_signal_for_titan(self, asset: str) -> Optional[Dict[str, float]]:
        """Get signal in format expected by TitanBrain"""
        signal = self.get_signal(asset)

        if signal is None or signal.confidence < self.config.min_confidence:
            return None

        # If trap detected, reduce signal or block
        if signal.trap_detected:
            direction = 0  # Block the signal
            confidence = 0.1
        else:
            direction = signal.direction
            confidence = signal.confidence

        return {
            "external_direction": direction,
            "external_confidence": confidence,
            "external_urgency": signal.urgency,
            "smart_money_signal": signal.smart_money_signal or 0,
            "retail_sentiment": signal.retail_sentiment or 0,
            "divergence": signal.whale_retail_divergence,
            "trap_detected": 1 if signal.trap_detected else 0,
            "fear_greed": signal.fear_greed_value,
        }

    def is_safe_to_trade(self, asset: str, direction: str) -> tuple[bool, str]:
        """Check if it's safe to enter a trade"""
        signal = self.get_signal(asset)

        if signal is None:
            return True, "No external data"

        # Check for trap
        if signal.trap_detected:
            return False, f"TRAP: {signal.trap_type} - {signal.recommendation}"

        # Check alignment with smart money
        intended = 1 if direction.upper() == "BUY" else -1

        if signal.smart_money_signal:
            alignment = intended * signal.smart_money_signal

            if alignment < -0.3:
                return False, f"Against smart money flow ({signal.smart_money_signal:.2f})"

        # Check if at extreme (contrarian opportunity)
        if signal.is_extreme_sentiment:
            if (signal.direction > 0 and direction.upper() == "SELL") or \
               (signal.direction < 0 and direction.upper() == "BUY"):
                return False, f"Trading against contrarian signal (F&G: {signal.fear_greed_value:.0f})"

        return True, "Trade aligned with smart money"

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all signals"""
        self.refresh_all()

        summary = {
            "mode": self.config.mode.value,
            "assets": {},
            "overall_sentiment": 0,
            "trap_count": 0,
            "extreme_count": 0
        }

        for asset in self.config.assets:
            signal = self.signals.get(asset)
            if signal:
                summary["assets"][asset] = {
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "smart_money": signal.smart_money_signal,
                    "retail": signal.retail_sentiment,
                    "divergence": signal.whale_retail_divergence,
                    "trap": signal.trap_type,
                    "recommendation": signal.recommendation
                }

                summary["overall_sentiment"] += signal.direction
                if signal.trap_detected:
                    summary["trap_count"] += 1
                if signal.is_extreme_sentiment:
                    summary["extreme_count"] += 1

        if self.config.assets:
            summary["overall_sentiment"] /= len(self.config.assets)

        return summary

    def update_price(self, asset: str, price: float):
        """Update price cache (needed for trap detection)"""
        self.price_cache[asset] = price


# Demo
async def demo_smart_aggregator():
    """Demo the smart money aggregator"""
    print("\n" + "="*60)
    print("SMART MONEY SIGNAL AGGREGATOR")
    print("'Don't be exit liquidity'")
    print("="*60 + "\n")

    config = ExternalSignalConfig(
        mode=SignalMode.CONTRARIAN,
        assets=["BTC", "ETH"],
        min_confidence=0.3
    )

    aggregator = SignalAggregator(config)

    def on_signal(signal: AggregatedSignal):
        direction = "BUY" if signal.direction > 0 else "SELL" if signal.direction < 0 else "HOLD"
        print(f"\n📊 SIGNAL: {signal.asset} {direction}")
        print(f"   Direction: {signal.direction:.2f}")
        print(f"   Confidence: {signal.confidence:.2f}")
        print(f"   Smart Money: {signal.smart_money_signal or 0:.2f}")
        print(f"   Retail: {signal.retail_sentiment or 0:.2f}")
        print(f"   Divergence: {signal.whale_retail_divergence:.2f}")
        if signal.trap_detected:
            print(f"   ⚠️ TRAP: {signal.trap_type}")
        print(f"   Recommendation: {signal.recommendation}")

    def on_trap(trap: TrapSignal):
        print(f"\n🚨 TRAP ALERT: {trap.asset}")
        print(f"   Type: {trap.trap_type.value}")
        print(f"   Severity: {trap.severity.name}")
        print(f"   {trap.recommendation}")

    aggregator.on_signal = on_signal
    aggregator.on_trap_alert = on_trap

    print("Starting aggregator...")
    await aggregator.start()

    print("\nFetching signals...")
    await asyncio.sleep(2)

    # Get summary
    summary = aggregator.get_summary()

    print("\n--- Summary ---")
    print(f"Mode: {summary['mode']}")
    print(f"Traps detected: {summary['trap_count']}")
    print(f"Extreme sentiment: {summary['extreme_count']}")

    for asset, data in summary.get("assets", {}).items():
        print(f"\n{asset}:")
        print(f"  Direction: {data['direction']:.2f}")
        print(f"  Smart Money: {data['smart_money'] or 0:.2f}")
        print(f"  Retail: {data['retail'] or 0:.2f}")
        print(f"  Divergence: {data['divergence']:.2f}")
        if data['trap']:
            print(f"  ⚠️ Trap: {data['trap']}")
        print(f"  Recommendation: {data['recommendation']}")

    # Check trade safety
    print("\n--- Trade Safety Check ---")
    for asset in config.assets:
        is_safe, reason = aggregator.is_safe_to_trade(asset, "BUY")
        status = "✅ SAFE" if is_safe else "❌ BLOCKED"
        print(f"{asset} BUY: {status} - {reason}")

    await aggregator.stop()
    print("\nDemo complete!")


if __name__ == "__main__":
    asyncio.run(demo_smart_aggregator())
