#!/usr/bin/env python3
"""
TITAN External Alpha Sources - Comprehensive Demo
==================================================
Demonstrates all components of the smart money signal system.

Philosophy: "Don't be exit liquidity!"

Components Demonstrated:
1. Smart Money Tracking - Whale vs retail divergence
2. Whale Manipulation Detection - Don't blindly follow whales
3. Sentiment Extremes - Fear & Greed contrarian signals
4. Liquidity Trap Detection - Avoid traps
5. News Filtering - Separate signal from noise
6. Signal Quality - Cross-validate before trading
7. Aggregator - Combine all signals

Run: python -m shopguard_platform.signals.external.demo
"""

import asyncio
from datetime import datetime, timedelta

# Import all components
from .smart_money import SmartMoneyTracker
from .whale_manipulation import WhaleManipulationDetector, WhaleActivity
from .sentiment_extremes import SentimentExtremesDetector, SentimentZone
from .liquidity_trap import LiquidityTrapDetector, TrapType
from .news_filter import NewsImpactFilter
from .signal_quality import SignalQualityAnalyzer, SignalInput, SignalQuality
from .aggregator import SignalAggregator, ExternalSignalConfig, SignalMode


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def demo_whale_manipulation():
    """Demo: Whale Manipulation Detection"""
    print_header("1. WHALE MANIPULATION DETECTION")
    print("\"Even whales manipulate people who blindly copy trade them\"")

    detector = WhaleManipulationDetector()
    now = datetime.now()

    # Scenario 1: Single whale, visible, instant (suspicious)
    print("\n--- Scenario: Single Whale Pump (Suspicious) ---")
    detector.add_activity(WhaleActivity(
        wallet_id="whale_1",
        asset="BTC",
        direction="BUY",
        amount_usd=10_000_000,
        timestamp=now,
        is_visible=True,
        execution_speed="instant",
        market_impact=0.05
    ))

    result = detector.analyze_whale_activity("BTC", 0.9, is_highly_visible=True)
    print(f"  Single whale, $10M instant visible buy")
    print(f"  → Manipulation Detected: {result.is_manipulation}")
    print(f"  → Confidence: {result.confidence.name}")
    print(f"  → Raw Signal 0.90 → Adjusted: {result.adjusted_direction:.2f}")
    print(f"  → Action: {result.recommendation}")

    # Scenario 2: Multiple whales, stealth (genuine)
    print("\n--- Scenario: Multiple Whales Stealth (Genuine) ---")
    detector.whale_activities["ETH"] = []

    for i in range(5):
        detector.add_activity(WhaleActivity(
            wallet_id=f"whale_{i}",
            asset="ETH",
            direction="BUY",
            amount_usd=2_000_000,
            timestamp=now - timedelta(hours=i * 4),
            is_visible=False,
            execution_speed="gradual",
            market_impact=0.01
        ))

    result = detector.analyze_whale_activity("ETH", 0.7, is_highly_visible=False)
    print(f"  5 independent whales, gradual stealth accumulation")
    print(f"  → Manipulation Detected: {result.is_manipulation}")
    print(f"  → Confidence: {result.confidence.name}")
    print(f"  → Raw Signal 0.70 → Adjusted: {result.adjusted_direction:.2f}")
    print(f"  → Action: {result.recommendation}")


def demo_sentiment_extremes():
    """Demo: Sentiment Extremes / Fear & Greed"""
    print_header("2. SENTIMENT EXTREMES (Fear & Greed)")
    print("\"Be fearful when others are greedy, and greedy when others are fearful\"")

    detector = SentimentExtremesDetector()

    scenarios = [
        {"name": "Extreme Fear", "social": -0.9, "news": -0.8, "volatility": 90},
        {"name": "Neutral", "social": 0.1, "news": 0.0, "volatility": 40},
        {"name": "Extreme Greed", "social": 0.9, "news": 0.85, "volatility": 20},
    ]

    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")

        # Add readings
        detector.add_reading("social", detector.convert_social_sentiment(scenario["social"]))
        detector.add_reading("news", detector.convert_news_sentiment(scenario["news"]))
        detector.add_reading("volatility", 100 - scenario["volatility"])

        # Get state
        state = detector.update()
        signal = detector.get_contrarian_signal("BTC")

        print(f"  Fear & Greed: {state.value:.0f}")
        print(f"  Zone: {state.zone.value}")
        print(f"  Contrarian Signal: {state.contrarian_signal:.2f}")

        if signal:
            direction = "CONTRARIAN BUY" if signal.direction > 0 else "CONTRARIAN SELL"
            print(f"  → Trade: {direction} (strength: {signal.signal_strength.name})")


def demo_liquidity_trap():
    """Demo: Liquidity Trap Detection"""
    print_header("3. LIQUIDITY TRAP DETECTION")
    print("\"Don't be exit liquidity for the whales!\"")

    detector = LiquidityTrapDetector()

    scenarios = [
        {
            "name": "FOMO Trap - Retail buying the top",
            "retail": 0.85,
            "whale": -0.6,
            "price_change": 0.08
        },
        {
            "name": "Panic Trap - Retail selling the bottom",
            "retail": -0.9,
            "whale": 0.7,
            "price_change": -0.12
        },
        {
            "name": "Healthy Trend - Aligned",
            "retail": 0.5,
            "whale": 0.4,
            "price_change": 0.05
        }
    ]

    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")

        base_price = 50000
        current_price = base_price * (1 + scenario["price_change"])

        trap = detector.check_for_trap(
            asset="BTC",
            retail_sentiment=scenario["retail"],
            whale_direction=scenario["whale"],
            current_price=current_price,
            price_24h_ago=base_price
        )

        print(f"  Retail: {trap.retail_sentiment:.2f}, Whales: {trap.smart_money_direction:.2f}")
        print(f"  Divergence: {trap.divergence:.2f}")
        print(f"  Trap Type: {trap.trap_type.value}")
        print(f"  Severity: {trap.severity.name}")
        print(f"  → {trap.recommendation}")


def demo_news_filter():
    """Demo: News Impact Filter"""
    print_header("4. NEWS IMPACT FILTER")
    print("\"90% of news is noise - filter it out\"")

    filter = NewsImpactFilter()

    headlines = [
        # Noise
        ("Analyst says Bitcoin could reach $100k", "cryptoblog.com", 0.8),
        # FUD
        ("WARNING: Bitcoin crash imminent", "twitter.com", -0.9),
        # FOMO
        ("Bitcoin MOONING! Don't miss! 🚀🚀🚀", "twitter.com", 0.95),
        # Major
        ("SEC files lawsuit against exchange", "reuters", -0.7),
        ("BlackRock ETF receives approval", "bloomberg", 0.8),
    ]

    for title, source, sentiment in headlines:
        result = filter.filter_news(title, source, sentiment)

        icon = "🗑️" if result.is_noise else "📊" if result.impact.value <= 2 else "🚨"
        print(f"\n{icon} [{result.impact.name:8}] {title[:45]}...")
        print(f"   Source: {source}")
        print(f"   Original: {sentiment:.2f} → Adjusted: {result.adjusted_sentiment:.2f}")
        print(f"   Action: {result.action.value}")

        if result.is_fud:
            print("   ⚠️ FUD detected - counter-trade retail panic")
        if result.is_fomo:
            print("   ⚠️ FOMO detected - counter-trade retail greed")


def demo_signal_quality():
    """Demo: Signal Quality Cross-Validation"""
    print_header("5. SIGNAL QUALITY CROSS-VALIDATION")
    print("\"Never trade on single-source signals\"")

    analyzer = SignalQualityAnalyzer()
    now = datetime.now()

    # Scenario 1: Strong agreement
    print("\n--- Scenario: Strong Agreement (4 bullish sources) ---")
    analyzer.add_signal("BTC", SignalInput("smart_money", 0.7, 0.85, now))
    analyzer.add_signal("BTC", SignalInput("sentiment", 0.6, 0.80, now))
    analyzer.add_signal("BTC", SignalInput("news", 0.5, 0.75, now))
    analyzer.add_signal("BTC", SignalInput("polymarket", 0.4, 0.70, now))

    score = analyzer.assess_quality("BTC")
    print(f"  Quality: {score.quality.value}")
    print(f"  Agreement: {score.source_agreement:.0%}")
    print(f"  Position Multiplier: {analyzer.get_position_multiplier('BTC'):.0%}")
    print(f"  → {score.recommendation}")

    # Scenario 2: Conflicting signals
    print("\n--- Scenario: Conflicting Signals ---")
    analyzer.clear_signals("ETH")
    analyzer.add_signal("ETH", SignalInput("smart_money", 0.7, 0.8, now))
    analyzer.add_signal("ETH", SignalInput("sentiment", -0.6, 0.75, now))
    analyzer.add_signal("ETH", SignalInput("news", 0.5, 0.7, now))
    analyzer.add_signal("ETH", SignalInput("trap_detector", -0.8, 0.9, now))

    score = analyzer.assess_quality("ETH")
    print(f"  Quality: {score.quality.value}")
    print(f"  Bullish: {score.sources_bullish}, Bearish: {score.sources_bearish}")
    print(f"  Position Multiplier: {analyzer.get_position_multiplier('ETH'):.0%}")
    print(f"  → {score.recommendation}")

    # Scenario 3: Single source (unreliable)
    print("\n--- Scenario: Single Source (Unreliable) ---")
    analyzer.clear_signals("SOL")
    analyzer.add_signal("SOL", SignalInput("smart_money", 0.8, 0.9, now))

    score = analyzer.assess_quality("SOL")
    print(f"  Quality: {score.quality.value}")
    print(f"  Sources: {score.sources_bullish + score.sources_bearish + score.sources_neutral}")
    print(f"  Position Multiplier: {analyzer.get_position_multiplier('SOL'):.0%}")
    print(f"  → {score.recommendation}")


def demo_full_system():
    """Demo: Full Signal Aggregator"""
    print_header("6. FULL SIGNAL AGGREGATOR")
    print("\"Combining all components for the final signal\"")

    config = ExternalSignalConfig(
        mode=SignalMode.CONTRARIAN,
        assets=["BTC", "ETH"],
        enable_smart_money=True,
        enable_sentiment_extremes=True,
        enable_liquidity_trap=True,
        enable_news_filter=True,
        enable_whale_manipulation=True,
        enable_quality_check=True,
        min_quality=SignalQuality.MODERATE
    )

    aggregator = SignalAggregator(config)

    print("\nConfiguration:")
    print(f"  Mode: {config.mode.value}")
    print(f"  Quality Check: {config.enable_quality_check}")
    print(f"  Min Quality: {config.min_quality.value}")
    print(f"  Whale Manipulation Check: {config.enable_whale_manipulation}")

    for asset in config.assets:
        print(f"\n--- {asset} ---")
        signal = aggregator.get_signal(asset)

        if signal:
            print(f"  Direction: {signal.direction:.2f}")
            print(f"  Confidence: {signal.confidence:.2f}")
            print(f"  Smart Money: {signal.smart_money_signal or 0:.2f}")
            print(f"  Whale Confidence: {signal.whale_confidence:.2f}")
            print(f"  Signal Quality: {signal.signal_quality}")
            print(f"  Position Multiplier: {signal.position_multiplier:.0%}")
            print(f"  Trap: {signal.trap_type}")
            print(f"  Manipulation: {signal.manipulation_detected}")
            print(f"  → {signal.recommendation}")

            # Safety check
            is_safe, reason = aggregator.is_safe_to_trade(asset, "BUY")
            status = "✅ SAFE" if is_safe else "❌ BLOCKED"
            print(f"\n  BUY Check: {status}")
            print(f"  Reason: {reason}")


def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("  TITAN EXTERNAL ALPHA SOURCES - COMPREHENSIVE DEMO")
    print("  \"Don't be exit liquidity!\"")
    print("=" * 60)

    # Run all demos
    demo_whale_manipulation()
    demo_sentiment_extremes()
    demo_liquidity_trap()
    demo_news_filter()
    demo_signal_quality()
    demo_full_system()

    # Summary
    print_header("SUMMARY - Key Protections")
    print("""
1. WHALE MANIPULATION: Single whale = suspicious, multiple = trustworthy
2. SENTIMENT EXTREMES: Extreme fear = BUY, Extreme greed = SELL
3. LIQUIDITY TRAPS: Retail vs whale divergence = TRAP warning
4. NEWS FILTER: 90% is noise, only react to major events
5. QUALITY CHECK: Never trade on single-source signals

Core Philosophy:
- Don't follow the dumb money (retail panic/FOMO)
- Don't blindly follow smart money (whales manipulate too)
- Require multiple independent sources to agree
- When in doubt, stay out
""")


if __name__ == "__main__":
    main()
