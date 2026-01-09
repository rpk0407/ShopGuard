"""
TITAN Unified Signal Pipeline
==============================
The master signal processor that combines ALL sources:
- Technical Analysis (Entropy, Hurst, CVD)
- External Alpha (Polymarket, Social, News)
- Smart Money Protection (Whale Detection, Liquidity Traps)
- Signal Quality Cross-Validation

Philosophy: "Don't be exit liquidity!"

Usage:
    pipeline = UnifiedSignalPipeline(config)
    await pipeline.start()

    # Process signals
    signal = await pipeline.process(asset, price, candles)

    if signal.should_trade:
        # Execute trade
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

# External Alpha
from .external import SignalAggregator, ExternalSignalConfig, AggregatedSignal
from .external.whale_manipulation import WhaleManipulationDetector
from .external.liquidity_trap import LiquidityTrapDetector
from .external.signal_quality import SignalQualityAnalyzer, SignalInput, SignalQuality
from .external.sentiment_extremes import SentimentExtremesAnalyzer

logger = logging.getLogger(__name__)


class SignalDecision(Enum):
    """Final signal decision"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    BLOCKED = "BLOCKED"  # Blocked by protection checks


@dataclass
class UnifiedSignal:
    """
    The final unified signal combining all sources.

    This is what the execution engine acts on.
    """
    # Decision
    decision: SignalDecision
    should_trade: bool
    direction: float  # -1 to 1

    # Confidence & Quality
    confidence: float  # 0 to 1
    quality: SignalQuality
    position_multiplier: float  # 0 to 1

    # Components
    technical_signal: float  # From entropy/hurst/cvd
    external_signal: float   # From polymarket/social/news
    smart_money_signal: float  # Whale tracking

    # Protection Flags
    manipulation_detected: bool
    trap_detected: bool
    entropy_tradeable: bool

    # Risk Parameters
    suggested_stop_pct: float
    suggested_target_pct: float
    risk_reward_ratio: float

    # Metadata
    asset: str
    price: float
    timestamp: float
    reasoning: str
    sources_count: int

    def to_dict(self) -> Dict:
        return {
            'decision': self.decision.value,
            'should_trade': self.should_trade,
            'direction': round(self.direction, 3),
            'confidence': round(self.confidence, 3),
            'quality': self.quality.value,
            'position_multiplier': round(self.position_multiplier, 3),
            'signals': {
                'technical': round(self.technical_signal, 3),
                'external': round(self.external_signal, 3),
                'smart_money': round(self.smart_money_signal, 3),
            },
            'protection': {
                'manipulation': self.manipulation_detected,
                'trap': self.trap_detected,
                'entropy_ok': self.entropy_tradeable,
            },
            'risk': {
                'stop_pct': round(self.suggested_stop_pct * 100, 2),
                'target_pct': round(self.suggested_target_pct * 100, 2),
                'rr_ratio': round(self.risk_reward_ratio, 2),
            },
            'asset': self.asset,
            'price': self.price,
            'sources': self.sources_count,
            'reasoning': self.reasoning,
        }


@dataclass
class PipelineConfig:
    """Unified pipeline configuration"""
    # Assets
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH"])

    # Weights for signal combination
    technical_weight: float = 0.5
    external_weight: float = 0.25
    smart_money_weight: float = 0.25

    # Thresholds
    min_confidence: float = 0.6
    min_quality: SignalQuality = SignalQuality.MODERATE

    # Protection
    enable_whale_detection: bool = True
    enable_trap_detection: bool = True
    block_on_manipulation: bool = True

    # Risk defaults
    default_stop_pct: float = 0.02
    default_target_pct: float = 0.04
    min_risk_reward: float = 2.0


class UnifiedSignalPipeline:
    """
    THE TITAN UNIFIED SIGNAL PIPELINE
    ==================================

    Combines all signal sources into one unified output:

    1. TECHNICAL ANALYSIS
       - Entropy Filter (market order/chaos)
       - Hurst Exponent (trend persistence)
       - CVD (order flow divergence)

    2. EXTERNAL ALPHA
       - Polymarket (prediction markets)
       - Social Sentiment (Twitter, Reddit)
       - News Sentiment (filtered noise)

    3. SMART MONEY PROTECTION
       - Whale Manipulation Detection
       - Liquidity Trap Detection
       - Signal Quality Cross-Validation

    Output: UnifiedSignal with GO/NO-GO decision
    """

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()

        # External alpha aggregator
        self.external_aggregator: Optional[SignalAggregator] = None

        # Protection components
        self.whale_detector = WhaleManipulationDetector()
        self.trap_detector = LiquidityTrapDetector()
        self.quality_analyzer = SignalQualityAnalyzer()
        self.sentiment_analyzer = SentimentExtremesAnalyzer()

        # State
        self._running = False
        self._price_history: Dict[str, List[float]] = {}

        # Stats
        self.stats = {
            'signals_processed': 0,
            'trades_approved': 0,
            'trades_blocked': 0,
            'manipulation_blocks': 0,
            'trap_blocks': 0,
            'quality_blocks': 0,
        }

        logger.info("🚀 Unified Signal Pipeline initialized")

    async def start(self):
        """Start the pipeline and all components"""
        logger.info("Starting Unified Signal Pipeline...")

        # Initialize external aggregator
        external_config = ExternalSignalConfig(
            enable_polymarket=True,
            enable_social=True,
            enable_news=True,
            assets=self.config.assets
        )
        self.external_aggregator = SignalAggregator(external_config)
        await self.external_aggregator.start()

        self._running = True
        logger.info("✅ Unified Signal Pipeline started")

    async def stop(self):
        """Stop the pipeline"""
        self._running = False
        if self.external_aggregator:
            await self.external_aggregator.stop()
        logger.info("Unified Signal Pipeline stopped")

    async def process(
        self,
        asset: str,
        price: float,
        technical_data: Dict = None,
        fear_greed_index: int = 50
    ) -> UnifiedSignal:
        """
        Process all signals and return unified decision.

        Args:
            asset: Asset symbol (e.g., "BTC")
            price: Current price
            technical_data: Dict with entropy, hurst, cvd values
            fear_greed_index: Current Fear & Greed index (0-100)

        Returns:
            UnifiedSignal with trading decision
        """
        self.stats['signals_processed'] += 1
        timestamp = time.time()

        # Update price history
        if asset not in self._price_history:
            self._price_history[asset] = []
        self._price_history[asset].append(price)
        if len(self._price_history[asset]) > 200:
            self._price_history[asset] = self._price_history[asset][-200:]

        # Default technical data
        tech = technical_data or {}
        entropy = tech.get('entropy', 2.0)
        hurst = tech.get('hurst', 0.5)
        cvd = tech.get('cvd', 0)
        cvd_divergence = tech.get('cvd_divergence', None)

        # ========================================
        # 1. TECHNICAL SIGNAL
        # ========================================

        technical_signal = self._calculate_technical_signal(
            entropy, hurst, cvd, cvd_divergence
        )
        entropy_tradeable = entropy < 2.5 and hurst > 0.45

        # ========================================
        # 2. EXTERNAL ALPHA SIGNAL
        # ========================================

        external_signal = 0.0
        external_confidence = 0.0
        sources_count = 0

        if self.external_aggregator:
            ext_data = self.external_aggregator.get_signal_for_titan(asset)
            if ext_data:
                external_signal = ext_data.get('external_direction', 0)
                external_confidence = ext_data.get('external_confidence', 0)
                sources_count = ext_data.get('source_count', 0)

        # ========================================
        # 3. SENTIMENT EXTREMES (CONTRARIAN)
        # ========================================

        sentiment_result = self.sentiment_analyzer.analyze(fear_greed_index)
        contrarian_signal = sentiment_result.contrarian_signal

        # ========================================
        # 4. SMART MONEY PROTECTION
        # ========================================

        # Check whale manipulation
        manipulation_detected = False
        if self.config.enable_whale_detection:
            whale_result = self.whale_detector.analyze_whale_activity(
                asset=asset,
                whale_direction=external_signal,
                is_highly_visible=False
            )
            if whale_result.is_manipulation:
                manipulation_detected = True
                self.stats['manipulation_blocks'] += 1
                logger.warning(f"🐋 {asset}: Whale manipulation detected!")

        # Check liquidity trap
        trap_detected = False
        trap_type = None
        if self.config.enable_trap_detection:
            trap_result = self.trap_detector.detect_trap(
                asset=asset,
                retail_sentiment=contrarian_signal * -1,  # Inverse of contrarian
                smart_money_flow=external_signal,
                price_momentum=tech.get('momentum', 0),
                volume_spike=tech.get('volume_spike', False)
            )
            if trap_result.is_trap:
                trap_detected = True
                trap_type = trap_result.trap_type
                self.stats['trap_blocks'] += 1
                logger.warning(f"🪤 {asset}: Liquidity trap detected: {trap_type}")

        # ========================================
        # 5. SIGNAL QUALITY CHECK
        # ========================================

        # Add signals to quality analyzer
        self.quality_analyzer.add_signal(asset, SignalInput(
            source="technical",
            direction=technical_signal,
            confidence=0.7 if entropy_tradeable else 0.3,
            timestamp=timestamp
        ))

        if abs(external_signal) > 0.1:
            self.quality_analyzer.add_signal(asset, SignalInput(
                source="external",
                direction=external_signal,
                confidence=external_confidence,
                timestamp=timestamp
            ))

        if abs(contrarian_signal) > 0.2:
            self.quality_analyzer.add_signal(asset, SignalInput(
                source="sentiment",
                direction=contrarian_signal,
                confidence=sentiment_result.confidence,
                timestamp=timestamp
            ))

        quality_result = self.quality_analyzer.assess_quality(asset)
        quality = quality_result.quality
        position_multiplier = self.quality_analyzer.get_position_multiplier(asset)

        # ========================================
        # 6. COMBINE SIGNALS
        # ========================================

        # Weighted combination
        combined_signal = (
            technical_signal * self.config.technical_weight +
            external_signal * self.config.external_weight +
            contrarian_signal * self.config.smart_money_weight
        )

        # Apply smart money adjustment
        smart_money_signal = external_signal
        if manipulation_detected:
            smart_money_signal *= -0.5  # Reduce trust
        if trap_detected:
            if trap_type and "PANIC" in str(trap_type):
                smart_money_signal = 0.5  # Panic trap = buy opportunity
            else:
                smart_money_signal *= 0.3  # Reduce other trap signals

        # Final confidence
        base_confidence = (
            abs(technical_signal) * 0.4 +
            external_confidence * 0.3 +
            sentiment_result.confidence * 0.3
        )
        confidence = base_confidence * quality_result.score

        # ========================================
        # 7. MAKE DECISION
        # ========================================

        should_trade = True
        reasoning_parts = []

        # Block checks
        if self.config.block_on_manipulation and manipulation_detected:
            should_trade = False
            reasoning_parts.append("BLOCKED: Whale manipulation detected")

        if self.config.block_on_manipulation and trap_detected:
            # Panic traps are buy opportunities!
            if trap_type and "PANIC" in str(trap_type):
                reasoning_parts.append("PANIC TRAP: Buy opportunity (whales accumulating)")
            else:
                should_trade = False
                reasoning_parts.append(f"BLOCKED: Liquidity trap ({trap_type})")

        if not entropy_tradeable:
            confidence *= 0.5
            reasoning_parts.append("Entropy filter: Caution")

        if quality.value in ["low", "unreliable"]:
            should_trade = False
            self.stats['quality_blocks'] += 1
            reasoning_parts.append(f"BLOCKED: Low signal quality ({quality.value})")

        if confidence < self.config.min_confidence:
            should_trade = False
            reasoning_parts.append(f"Low confidence ({confidence:.2f})")

        # Determine direction and decision
        direction = combined_signal
        if should_trade:
            self.stats['trades_approved'] += 1
            if direction > 0.5:
                decision = SignalDecision.STRONG_BUY
                reasoning_parts.append("Strong bullish convergence")
            elif direction > 0.2:
                decision = SignalDecision.BUY
                reasoning_parts.append("Bullish signal")
            elif direction < -0.5:
                decision = SignalDecision.STRONG_SELL
                reasoning_parts.append("Strong bearish convergence")
            elif direction < -0.2:
                decision = SignalDecision.SELL
                reasoning_parts.append("Bearish signal")
            else:
                decision = SignalDecision.HOLD
                should_trade = False
                reasoning_parts.append("No clear direction")
        else:
            self.stats['trades_blocked'] += 1
            decision = SignalDecision.BLOCKED

        # Risk parameters
        volatility = tech.get('atr_pct', 0.02)
        stop_pct = max(self.config.default_stop_pct, volatility * 1.5)
        target_pct = stop_pct * self.config.min_risk_reward
        rr_ratio = target_pct / stop_pct if stop_pct > 0 else 0

        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Standard signal"

        return UnifiedSignal(
            decision=decision,
            should_trade=should_trade,
            direction=direction,
            confidence=confidence,
            quality=quality,
            position_multiplier=position_multiplier,
            technical_signal=technical_signal,
            external_signal=external_signal,
            smart_money_signal=smart_money_signal,
            manipulation_detected=manipulation_detected,
            trap_detected=trap_detected,
            entropy_tradeable=entropy_tradeable,
            suggested_stop_pct=stop_pct,
            suggested_target_pct=target_pct,
            risk_reward_ratio=rr_ratio,
            asset=asset,
            price=price,
            timestamp=timestamp,
            reasoning=reasoning,
            sources_count=sources_count + 2  # +2 for technical and sentiment
        )

    def _calculate_technical_signal(
        self,
        entropy: float,
        hurst: float,
        cvd: float,
        cvd_divergence: Optional[str]
    ) -> float:
        """Calculate technical signal from entropy, hurst, CVD"""
        signal = 0.0

        # Entropy check (low = ordered = good)
        if entropy < 2.0:
            signal += 0.2
        elif entropy > 3.0:
            signal -= 0.2

        # Hurst check (high = trending)
        if hurst > 0.65:
            signal += 0.3  # Strong trend
        elif hurst > 0.55:
            signal += 0.15  # Weak trend
        elif hurst < 0.45:
            signal -= 0.1  # Mean reverting

        # CVD divergence
        if cvd_divergence == "BULLISH":
            signal += 0.4
        elif cvd_divergence == "BEARISH":
            signal -= 0.4
        elif cvd > 0:
            signal += min(0.2, cvd / 1000)
        elif cvd < 0:
            signal -= min(0.2, abs(cvd) / 1000)

        return max(-1.0, min(1.0, signal))

    def get_stats(self) -> Dict:
        """Get pipeline statistics"""
        total = self.stats['trades_approved'] + self.stats['trades_blocked']
        approval_rate = self.stats['trades_approved'] / total if total > 0 else 0

        return {
            **self.stats,
            'approval_rate': f"{approval_rate*100:.1f}%",
        }

    def reset_stats(self):
        """Reset statistics"""
        self.stats = {k: 0 for k in self.stats}


# Demo
async def demo_pipeline():
    """Demo the unified pipeline"""
    print("\n" + "=" * 60)
    print("TITAN UNIFIED SIGNAL PIPELINE DEMO")
    print("=" * 60 + "\n")

    config = PipelineConfig(
        assets=["BTC", "ETH"],
        min_confidence=0.5,
        block_on_manipulation=True
    )

    pipeline = UnifiedSignalPipeline(config)
    await pipeline.start()

    # Simulate different market conditions
    scenarios = [
        {
            "name": "Strong Bullish Setup",
            "asset": "BTC",
            "price": 95000,
            "technical": {"entropy": 1.8, "hurst": 0.72, "cvd": 500, "cvd_divergence": "BULLISH"},
            "fear_greed": 35
        },
        {
            "name": "Whale Manipulation Suspected",
            "asset": "BTC",
            "price": 95500,
            "technical": {"entropy": 2.5, "hurst": 0.55, "cvd": 200, "cvd_divergence": None},
            "fear_greed": 75
        },
        {
            "name": "Panic Trap (Buy Opportunity)",
            "asset": "ETH",
            "price": 3200,
            "technical": {"entropy": 2.8, "hurst": 0.45, "cvd": -300, "cvd_divergence": None},
            "fear_greed": 15
        },
        {
            "name": "Chaotic Market (No Trade)",
            "asset": "BTC",
            "price": 94000,
            "technical": {"entropy": 3.5, "hurst": 0.48, "cvd": 50, "cvd_divergence": None},
            "fear_greed": 50
        },
    ]

    for scenario in scenarios:
        print(f"\n{'─' * 60}")
        print(f"Scenario: {scenario['name']}")
        print(f"{'─' * 60}")

        signal = await pipeline.process(
            asset=scenario['asset'],
            price=scenario['price'],
            technical_data=scenario['technical'],
            fear_greed_index=scenario['fear_greed']
        )

        print(f"\n  Decision: {signal.decision.value}")
        print(f"  Should Trade: {signal.should_trade}")
        print(f"  Direction: {signal.direction:+.3f}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Quality: {signal.quality.value}")
        print(f"  Position Mult: {signal.position_multiplier:.2f}")
        print(f"\n  Reasoning: {signal.reasoning}")

        if signal.should_trade:
            print(f"\n  Risk/Reward: {signal.risk_reward_ratio:.1f}:1")
            print(f"  Stop: {signal.suggested_stop_pct*100:.2f}%")
            print(f"  Target: {signal.suggested_target_pct*100:.2f}%")

    await pipeline.stop()

    print(f"\n{'=' * 60}")
    print("Pipeline Stats:")
    for k, v in pipeline.get_stats().items():
        print(f"  {k}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo_pipeline())
