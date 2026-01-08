"""
News Impact Filter
==================
Filters news to separate real market-moving events from noise.

The Problem:
- 90% of crypto "news" is noise that doesn't affect price
- Retail panics at every FUD headline
- Real impact events are rare but significant
- Following noise = becoming exit liquidity

Categories of News:
1. NOISE (Ignore):
   - Price analysis articles ("BTC could go to $X")
   - Opinion pieces
   - Old news repackaged
   - Minor exchange listings
   - Celebrity tweets (usually)

2. MINOR IMPACT (Monitor):
   - Small partnerships
   - Minor protocol updates
   - Exchange additions/removals
   - Whale wallet movements (unless huge)

3. MAJOR IMPACT (React):
   - Regulatory actions (SEC lawsuits, country bans)
   - Exchange hacks (if > $100M)
   - Protocol exploits
   - Major institutional moves (BlackRock, Fidelity)
   - Macroeconomic events (Fed, CPI)

4. CRITICAL (Immediate):
   - Exchange insolvency (FTX-level)
   - Major stablecoin depeg
   - Protocol failure
   - Government crackdowns
   - ETF approvals/rejections

This module classifies news and filters out noise.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Set
from collections import deque

logger = logging.getLogger(__name__)


class NewsImpact(Enum):
    """Impact level of news"""
    NOISE = 0           # Ignore completely
    MINOR = 1           # Monitor, don't trade
    MODERATE = 2        # Consider in signals
    MAJOR = 3           # Trade-worthy
    CRITICAL = 4        # Immediate action


class NewsAction(Enum):
    """Recommended action for news"""
    IGNORE = "ignore"                 # Don't react
    MONITOR = "monitor"               # Watch but don't trade
    WAIT_CONFIRMATION = "wait"        # Wait for price confirmation
    CONSIDER_POSITION = "consider"    # Factor into next trade
    REDUCE_EXPOSURE = "reduce"        # Lower position size
    EXIT_POSITIONS = "exit"           # Close positions
    COUNTER_TRADE = "counter"         # Trade against retail reaction


@dataclass
class FilteredNews:
    """News item after filtering and classification"""
    title: str
    source: str
    category: str
    impact: NewsImpact
    action: NewsAction
    confidence: float           # Confidence in classification
    is_noise: bool
    is_fud: bool               # Fear, Uncertainty, Doubt
    is_fomo: bool              # Fear Of Missing Out
    delay_reaction: int        # Minutes to wait before reacting
    reasoning: str
    original_sentiment: float  # Original sentiment score
    adjusted_sentiment: float  # Sentiment after filtering
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NewsFilterConfig:
    """Configuration for news filtering"""
    # Minimum thresholds to consider news
    min_source_credibility: float = 0.5
    min_impact_score: float = 0.3

    # Noise filtering
    ignore_price_predictions: bool = True
    ignore_opinion_pieces: bool = True
    ignore_old_news: bool = True  # > 24h old
    ignore_minor_events: bool = True

    # Reaction delays (minutes)
    default_reaction_delay: int = 30
    fud_reaction_delay: int = 60  # Wait longer for FUD
    fomo_reaction_delay: int = 45

    # Counter-trade settings
    counter_trade_retail_panic: bool = True
    counter_trade_retail_fomo: bool = True


class NewsImpactFilter:
    """
    Filters and classifies news to avoid noise.

    Key Principles:
    1. Most news is noise - default to ignoring
    2. Wait for confirmation before reacting
    3. Counter-trade retail overreaction
    4. Only react to genuine market-moving events
    5. Don't be the exit liquidity for FUD/FOMO

    Signal Adjustment:
    - NOISE: Set sentiment to 0 (ignore)
    - FUD: Reduce magnitude or reverse (contrarian)
    - FOMO: Reduce magnitude or reverse
    - Legitimate: Pass through with confidence
    """

    # Patterns for noise detection
    NOISE_PATTERNS = [
        r"could (go|reach|hit)",           # Price predictions
        r"(might|may|possibly)",            # Speculation
        r"(analyst|expert) (says|thinks)",  # Opinion
        r"(prediction|forecast)",           # Forecasts
        r"(opinion|editorial)",             # Opinion pieces
        r"here'?s why",                     # Clickbait
        r"(top \d|best \d|\d+ reasons)",   # Listicles
        r"you won'?t believe",              # Clickbait
        r"breaking:.*old",                  # Old news
    ]

    # Patterns for FUD detection
    FUD_PATTERNS = [
        r"(crash|plunge|collapse|tank)",
        r"(ban|crackdown|illegal)",
        r"(scam|fraud|ponzi)",
        r"(death cross|bearish)",
        r"(bubble|overvalued)",
        r"(sell-off|dump|rekt)",
        r"(warning|caution|danger)",
        r"(fear|panic|worried)",
    ]

    # Patterns for FOMO detection
    FOMO_PATTERNS = [
        r"(moon|mooning|rocket|🚀)",
        r"(surge|soar|skyrocket)",
        r"(massive|huge|insane) (gains|pump)",
        r"(buy now|last chance|don'?t miss)",
        r"(golden cross|bullish)",
        r"(undervalued|cheap)",
        r"(institutional buying|smart money)",
        r"(fomo|fear of missing)",
    ]

    # High credibility sources
    HIGH_CREDIBILITY_SOURCES = [
        "reuters", "bloomberg", "wsj", "ft",
        "sec.gov", "federalreserve", "official",
    ]

    # Medium credibility sources
    MEDIUM_CREDIBILITY_SOURCES = [
        "coindesk", "theblock", "decrypt",
        "cointelegraph", "bitcoinmagazine",
    ]

    # Low credibility sources (often noise)
    LOW_CREDIBILITY_SOURCES = [
        "random blog", "medium.com", "twitter",
        "reddit", "telegram", "youtube",
    ]

    # Keywords for major impact events
    MAJOR_IMPACT_KEYWORDS = [
        r"(sec|cftc|doj).*(lawsuit|charges|action)",
        r"(blackrock|fidelity|vanguard).*(etf|filing|approval)",
        r"(hack|exploit|breach).*(million|\$\d{6,})",
        r"(fed|fomc).*(rate|decision|meeting)",
        r"(country|nation).*(ban|legalize)",
        r"exchange.*(insolvency|bankrupt|hack)",
        r"stablecoin.*(depeg|collapse)",
    ]

    def __init__(self, config: NewsFilterConfig = None):
        self.config = config or NewsFilterConfig()

        # Compile regex patterns
        self._noise_regex = [re.compile(p, re.I) for p in self.NOISE_PATTERNS]
        self._fud_regex = [re.compile(p, re.I) for p in self.FUD_PATTERNS]
        self._fomo_regex = [re.compile(p, re.I) for p in self.FOMO_PATTERNS]
        self._major_regex = [re.compile(p, re.I) for p in self.MAJOR_IMPACT_KEYWORDS]

        # History tracking
        self.filtered_news: deque = deque(maxlen=1000)
        self.noise_count: int = 0
        self.signal_count: int = 0

        # Callbacks
        self.on_major_news: Optional[Callable[[FilteredNews], None]] = None

    def _get_source_credibility(self, source: str) -> float:
        """Get credibility score for a news source"""
        source_lower = source.lower()

        for high in self.HIGH_CREDIBILITY_SOURCES:
            if high in source_lower:
                return 0.9

        for medium in self.MEDIUM_CREDIBILITY_SOURCES:
            if medium in source_lower:
                return 0.6

        for low in self.LOW_CREDIBILITY_SOURCES:
            if low in source_lower:
                return 0.3

        return 0.5  # Unknown source

    def _is_noise(self, title: str, content: str = "") -> bool:
        """Check if news item is noise"""
        text = f"{title} {content}".lower()

        for pattern in self._noise_regex:
            if pattern.search(text):
                return True

        return False

    def _is_fud(self, title: str, content: str = "") -> bool:
        """Check if news item is FUD"""
        text = f"{title} {content}".lower()

        fud_count = sum(1 for p in self._fud_regex if p.search(text))
        return fud_count >= 2  # Multiple FUD keywords = FUD

    def _is_fomo(self, title: str, content: str = "") -> bool:
        """Check if news item is FOMO-inducing"""
        text = f"{title} {content}".lower()

        fomo_count = sum(1 for p in self._fomo_regex if p.search(text))
        return fomo_count >= 2  # Multiple FOMO keywords = FOMO

    def _is_major_event(self, title: str, content: str = "") -> bool:
        """Check if news item is a major market-moving event"""
        text = f"{title} {content}".lower()

        for pattern in self._major_regex:
            if pattern.search(text):
                return True

        return False

    def _calculate_impact(
        self,
        is_noise: bool,
        is_fud: bool,
        is_fomo: bool,
        is_major: bool,
        source_credibility: float
    ) -> NewsImpact:
        """Calculate news impact level"""
        if is_noise and not is_major:
            return NewsImpact.NOISE

        if is_major:
            if source_credibility >= 0.7:
                return NewsImpact.CRITICAL
            else:
                return NewsImpact.MAJOR

        if is_fud or is_fomo:
            # FUD/FOMO from credible sources = moderate
            # FUD/FOMO from low credibility = noise
            if source_credibility >= 0.6:
                return NewsImpact.MODERATE
            else:
                return NewsImpact.MINOR

        # Default based on source credibility
        if source_credibility >= 0.7:
            return NewsImpact.MODERATE
        elif source_credibility >= 0.5:
            return NewsImpact.MINOR
        else:
            return NewsImpact.NOISE

    def _determine_action(
        self,
        impact: NewsImpact,
        is_fud: bool,
        is_fomo: bool,
        original_sentiment: float
    ) -> NewsAction:
        """Determine recommended action"""
        if impact == NewsImpact.NOISE:
            return NewsAction.IGNORE

        if impact == NewsImpact.MINOR:
            return NewsAction.MONITOR

        if impact == NewsImpact.CRITICAL:
            if original_sentiment < -0.5:
                return NewsAction.REDUCE_EXPOSURE
            elif original_sentiment > 0.5:
                return NewsAction.CONSIDER_POSITION
            else:
                return NewsAction.WAIT_CONFIRMATION

        if impact in [NewsImpact.MODERATE, NewsImpact.MAJOR]:
            # Contrarian approach for FUD/FOMO
            if is_fud and self.config.counter_trade_retail_panic:
                return NewsAction.COUNTER_TRADE
            if is_fomo and self.config.counter_trade_retail_fomo:
                return NewsAction.COUNTER_TRADE

            return NewsAction.WAIT_CONFIRMATION

        return NewsAction.MONITOR

    def _adjust_sentiment(
        self,
        original_sentiment: float,
        impact: NewsImpact,
        is_fud: bool,
        is_fomo: bool,
        action: NewsAction
    ) -> float:
        """Adjust sentiment based on filtering"""

        # Noise = no sentiment
        if impact == NewsImpact.NOISE:
            return 0.0

        # Counter-trade = reverse sentiment
        if action == NewsAction.COUNTER_TRADE:
            # Don't fully reverse, but dampen significantly
            return -original_sentiment * 0.5

        # FUD/FOMO from low credibility = dampen
        if is_fud or is_fomo:
            return original_sentiment * 0.3

        # Minor impact = dampen
        if impact == NewsImpact.MINOR:
            return original_sentiment * 0.5

        # Major/Critical = pass through with confidence
        if impact in [NewsImpact.MAJOR, NewsImpact.CRITICAL]:
            return original_sentiment * 0.9

        return original_sentiment * 0.7

    def filter_news(
        self,
        title: str,
        source: str,
        original_sentiment: float,
        content: str = "",
        category: str = "general"
    ) -> FilteredNews:
        """
        Filter and classify a news item.

        Args:
            title: News headline
            source: Source name
            original_sentiment: Raw sentiment score (-1 to 1)
            content: Optional article content
            category: News category

        Returns:
            FilteredNews with classification and recommendation
        """
        # Get source credibility
        credibility = self._get_source_credibility(source)

        # Detect patterns
        is_noise = self._is_noise(title, content)
        is_fud = self._is_fud(title, content)
        is_fomo = self._is_fomo(title, content)
        is_major = self._is_major_event(title, content)

        # Calculate impact
        impact = self._calculate_impact(
            is_noise, is_fud, is_fomo, is_major, credibility
        )

        # Determine action
        action = self._determine_action(
            impact, is_fud, is_fomo, original_sentiment
        )

        # Adjust sentiment
        adjusted_sentiment = self._adjust_sentiment(
            original_sentiment, impact, is_fud, is_fomo, action
        )

        # Determine delay
        if is_fud:
            delay = self.config.fud_reaction_delay
        elif is_fomo:
            delay = self.config.fomo_reaction_delay
        elif impact == NewsImpact.CRITICAL:
            delay = 5  # Fast reaction for critical
        else:
            delay = self.config.default_reaction_delay

        # Generate reasoning
        reasons = []
        if is_noise:
            reasons.append("noise/speculation")
        if is_fud:
            reasons.append("FUD pattern detected")
        if is_fomo:
            reasons.append("FOMO pattern detected")
        if is_major:
            reasons.append("major market event")
        if credibility < 0.5:
            reasons.append(f"low credibility source ({credibility:.1f})")

        reasoning = f"Impact: {impact.name}. " + "; ".join(reasons) if reasons else f"Standard news, impact: {impact.name}"

        # Calculate confidence
        confidence = credibility
        if is_major:
            confidence = min(1.0, confidence + 0.2)
        if is_noise:
            confidence = max(0.3, confidence - 0.2)

        result = FilteredNews(
            title=title,
            source=source,
            category=category,
            impact=impact,
            action=action,
            confidence=confidence,
            is_noise=is_noise,
            is_fud=is_fud,
            is_fomo=is_fomo,
            delay_reaction=delay,
            reasoning=reasoning,
            original_sentiment=original_sentiment,
            adjusted_sentiment=adjusted_sentiment
        )

        # Track statistics
        if impact == NewsImpact.NOISE:
            self.noise_count += 1
        else:
            self.signal_count += 1

        self.filtered_news.append(result)

        # Callback for major news
        if impact in [NewsImpact.MAJOR, NewsImpact.CRITICAL]:
            if self.on_major_news:
                self.on_major_news(result)

        return result

    def get_filter_stats(self) -> Dict:
        """Get filtering statistics"""
        total = self.noise_count + self.signal_count
        noise_pct = (self.noise_count / total * 100) if total > 0 else 0

        return {
            "total_processed": total,
            "noise_filtered": self.noise_count,
            "signals_passed": self.signal_count,
            "noise_percentage": f"{noise_pct:.1f}%",
            "signal_percentage": f"{100-noise_pct:.1f}%"
        }

    def bulk_filter(
        self,
        news_items: List[Dict]
    ) -> List[FilteredNews]:
        """Filter multiple news items and return only non-noise"""
        results = []

        for item in news_items:
            filtered = self.filter_news(
                title=item.get("title", ""),
                source=item.get("source", ""),
                original_sentiment=item.get("sentiment", 0),
                content=item.get("content", ""),
                category=item.get("category", "general")
            )

            # Only return non-noise with significant impact
            if filtered.impact != NewsImpact.NOISE:
                results.append(filtered)

        return results


# Demo
async def demo_news_filter():
    """Demo the news impact filter"""
    print("\n=== News Impact Filter ===")
    print("Filtering noise from real market-moving news\n")

    filter = NewsImpactFilter()

    def on_major(news: FilteredNews):
        print(f"\n  📰 MAJOR NEWS: {news.title[:60]}...")
        print(f"      Impact: {news.impact.name}")
        print(f"      Action: {news.action.value}")

    filter.on_major_news = on_major

    # Test various headlines
    test_headlines = [
        # Noise
        {"title": "Analyst says Bitcoin could reach $100k by end of year", "source": "cryptoblog.com", "sentiment": 0.8},
        {"title": "Top 10 reasons why Ethereum might moon", "source": "medium.com", "sentiment": 0.7},
        {"title": "Here's why experts think crypto is the future", "source": "twitter.com", "sentiment": 0.6},

        # FUD
        {"title": "WARNING: Bitcoin crash imminent as death cross forms", "source": "twitter.com", "sentiment": -0.9},
        {"title": "Crypto market in PANIC as prices plunge", "source": "cryptonews.com", "sentiment": -0.8},
        {"title": "Is Bitcoin a SCAM? The truth revealed", "source": "youtube.com", "sentiment": -0.7},

        # FOMO
        {"title": "Bitcoin MOONING! Don't miss this rocket to $200k! 🚀🚀🚀", "source": "twitter.com", "sentiment": 0.95},
        {"title": "MASSIVE institutional buying - smart money loading up!", "source": "reddit.com", "sentiment": 0.85},

        # Legitimate minor
        {"title": "Coinbase adds support for new altcoin", "source": "coindesk", "sentiment": 0.3},
        {"title": "Protocol upgrade scheduled for next week", "source": "decrypt", "sentiment": 0.2},

        # Major events
        {"title": "SEC files lawsuit against major crypto exchange", "source": "reuters", "sentiment": -0.7},
        {"title": "BlackRock spot Bitcoin ETF receives preliminary approval", "source": "bloomberg", "sentiment": 0.8},
        {"title": "Exchange hacked for $500 million in largest DeFi exploit", "source": "theblock", "sentiment": -0.9},
        {"title": "Federal Reserve announces rate decision", "source": "federalreserve.gov", "sentiment": -0.2},
    ]

    print("Processing headlines...\n")

    for item in test_headlines:
        result = filter.filter_news(
            title=item["title"],
            source=item["source"],
            original_sentiment=item["sentiment"]
        )

        # Show results
        icon = "🗑️" if result.is_noise else "📊" if result.impact.value <= 2 else "🚨"
        print(f"{icon} [{result.impact.name:8}] {result.title[:55]}...")
        print(f"   Source: {result.source} | Action: {result.action.value}")
        print(f"   Original sentiment: {result.original_sentiment:.2f} → Adjusted: {result.adjusted_sentiment:.2f}")
        if result.is_fud:
            print(f"   ⚠️  FUD detected - counter-trade retail panic")
        if result.is_fomo:
            print(f"   ⚠️  FOMO detected - counter-trade retail greed")
        print()

    # Show stats
    stats = filter.get_filter_stats()
    print("\n--- Filter Statistics ---")
    print(f"Total processed: {stats['total_processed']}")
    print(f"Noise filtered: {stats['noise_filtered']} ({stats['noise_percentage']})")
    print(f"Signals passed: {stats['signals_passed']} ({stats['signal_percentage']})")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_news_filter())
