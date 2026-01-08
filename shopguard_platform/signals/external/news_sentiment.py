"""
News Sentiment Scanner
======================
Monitors crypto news sources for market-moving events.

Key Insight:
- Breaking news often precedes major price moves
- Regulatory news has outsized impact on crypto
- Hack/exploit news causes immediate dumps
- Institutional adoption news drives pumps

Data Sources:
- CoinDesk, CoinTelegraph, TheBlock
- General news APIs (NewsAPI, Google News)
- RSS feeds from major outlets
- On-chain alerts (exploits, large transfers)
"""

import logging
import time
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Set
import requests
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


class NewsSource(Enum):
    """News sources for crypto"""
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"
    THEBLOCK = "theblock"
    DECRYPT = "decrypt"
    BITCOINMAGAZINE = "bitcoin_magazine"
    GENERAL = "general"


class NewsCategory(Enum):
    """Categories of crypto news"""
    REGULATION = "regulation"
    INSTITUTIONAL = "institutional"
    SECURITY = "security"      # Hacks, exploits
    TECHNOLOGY = "technology"  # Upgrades, launches
    MARKET = "market"          # Price analysis
    ADOPTION = "adoption"
    MACRO = "macro"            # Fed, economy


@dataclass
class NewsArticle:
    """A single news article"""
    article_id: str
    title: str
    summary: str
    source: NewsSource
    category: NewsCategory
    url: str
    published: datetime
    sentiment_score: float = 0.0   # -1 to +1
    impact_score: float = 0.0      # 0 to 1 (how market-moving)
    mentioned_assets: List[str] = field(default_factory=list)


@dataclass
class NewsSignal:
    """Trading signal derived from news"""
    asset: str
    source: NewsSource
    direction: float           # -1 (bearish) to +1 (bullish)
    confidence: float          # 0-1
    urgency: float            # 0-1 (how time-sensitive)
    category: NewsCategory
    headline: str              # The triggering headline
    article_url: str
    timestamp: datetime = field(default_factory=datetime.now)


class NewsSentimentScanner:
    """
    Scans news sources for crypto trading signals.

    Strategy:
    1. Monitor RSS feeds from major crypto outlets
    2. Detect breaking news via keyword matching
    3. Categorize news by type (regulation, hack, adoption, etc.)
    4. Score sentiment and potential market impact
    5. Generate time-sensitive signals for execution

    Signal Priority:
    - CRITICAL: Hacks, exploits, regulatory actions -> immediate
    - HIGH: Institutional moves, major partnerships -> within minutes
    - MEDIUM: Technology upgrades, adoption news -> within hours
    - LOW: Market analysis, opinions -> informational only
    """

    # RSS feeds for crypto news
    RSS_FEEDS = {
        NewsSource.COINDESK: "https://www.coindesk.com/arc/outboundfeeds/rss/",
        NewsSource.COINTELEGRAPH: "https://cointelegraph.com/rss",
        NewsSource.DECRYPT: "https://decrypt.co/feed",
        NewsSource.BITCOINMAGAZINE: "https://bitcoinmagazine.com/feed",
    }

    # Keyword patterns for categorization
    CATEGORY_PATTERNS = {
        NewsCategory.REGULATION: [
            r"\bsec\b", r"\bcftc\b", r"\bregulat", r"\blawsuit\b", r"\bban\b",
            r"\blegal\b", r"\bcompliance\b", r"\benforcement\b", r"\bgensler\b",
            r"\blegislat\b", r"\bbill\b", r"\bcongresss?\b"
        ],
        NewsCategory.SECURITY: [
            r"\bhack\b", r"\bexploit\b", r"\bbreach\b", r"\bstolen\b", r"\bdrain\b",
            r"\battack\b", r"\bvulnerabil\b", r"\brug\s*pull\b", r"\bscam\b"
        ],
        NewsCategory.INSTITUTIONAL: [
            r"\binstitution\b", r"\bblackrock\b", r"\bfidelity\b", r"\betf\b",
            r"\bgrayscale\b", r"\bhedge\s*fund\b", r"\bbank\b", r"\bwallstreet\b",
            r"\bcustody\b", r"\basset\s*manager\b"
        ],
        NewsCategory.ADOPTION: [
            r"\badopt\b", r"\bpartner\b", r"\bintegrat\b", r"\baccept\b",
            r"\blaunch\b", r"\brollout\b", r"\bmainstream\b", r"\bretail\b"
        ],
        NewsCategory.TECHNOLOGY: [
            r"\bupgrade\b", r"\bfork\b", r"\bprotocol\b", r"\blayer\s*2\b",
            r"\bscaling\b", r"\btestnet\b", r"\bmainnet\b", r"\bv2\b"
        ],
        NewsCategory.MACRO: [
            r"\bfed\b", r"\binflation\b", r"\binterest\s*rate\b", r"\btreasury\b",
            r"\brecession\b", r"\bgdp\b", r"\bunemployment\b", r"\bdollar\b"
        ]
    }

    # Impact keywords (high market-moving potential)
    HIGH_IMPACT_KEYWORDS = [
        r"\bapprove[ds]?\b", r"\breject[eds]?\b", r"\bhack\b", r"\bbillion\b",
        r"\bban\b", r"\blawsuit\b", r"\bbankrupt\b", r"\bcollapse\b",
        r"\bbreaking\b", r"\burgent\b", r"\bjust\s+in\b", r"\bflash\b"
    ]

    # Sentiment patterns
    BULLISH_PATTERNS = [
        r"\bapprove[ds]?\b", r"\badopt\b", r"\bpartner\b", r"\blaunch\b",
        r"\bsurge[ds]?\b", r"\brall(y|ies)\b", r"\bbullish\b", r"\bgains?\b",
        r"\brecord\s*high\b", r"\bbreakout\b", r"\bsoar\b", r"\bpump\b"
    ]

    BEARISH_PATTERNS = [
        r"\breject[eds]?\b", r"\bban\b", r"\bhack\b", r"\bexploit\b",
        r"\bcrash\b", r"\bdump\b", r"\bplunge\b", r"\bbearish\b", r"\bsell\s*off\b",
        r"\bcollapse\b", r"\bfraud\b", r"\bscam\b", r"\blawsuit\b"
    ]

    # Asset patterns
    ASSET_PATTERNS = {
        "BTC": [r"\bbitcoin\b", r"\bbtc\b"],
        "ETH": [r"\bethereum\b", r"\beth\b", r"\bether\b"],
        "SOL": [r"\bsolana\b", r"\bsol\b"],
        "XRP": [r"\bripple\b", r"\bxrp\b"],
        "BNB": [r"\bbinance\b", r"\bbnb\b"],
        "DOGE": [r"\bdogecoin\b", r"\bdoge\b"],
        "ADA": [r"\bcardano\b", r"\bada\b"],
        "AVAX": [r"\bavalanche\b", r"\bavax\b"],
    }

    def __init__(
        self,
        newsapi_key: Optional[str] = None,
        refresh_interval: int = 120,  # 2 minutes
        lookback_hours: int = 24,
    ):
        self.newsapi_key = newsapi_key
        self.refresh_interval = refresh_interval
        self.lookback_hours = lookback_hours

        # Data storage
        self.articles: Dict[str, NewsArticle] = {}  # article_id -> article
        self.signals: List[NewsSignal] = []
        self.seen_ids: Set[str] = set()

        self.last_refresh: float = 0

        # Callbacks
        self.on_signal: Optional[Callable[[NewsSignal], None]] = None
        self.on_breaking_news: Optional[Callable[[NewsArticle], None]] = None

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "TITAN-Trading/1.0"
        })

    def _generate_article_id(self, title: str, source: str) -> str:
        """Generate unique ID for an article"""
        content = f"{title.lower().strip()}{source}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _parse_rss_feed(self, source: NewsSource, url: str) -> List[NewsArticle]:
        """Parse RSS feed and extract articles"""
        articles = []

        try:
            response = self._session.get(url, timeout=15)
            response.raise_for_status()

            root = ElementTree.fromstring(response.content)

            # Handle different RSS formats
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

            cutoff = datetime.now() - timedelta(hours=self.lookback_hours)

            for item in items[:50]:  # Limit to recent items
                try:
                    # Extract fields (RSS 2.0 format)
                    title_el = item.find("title")
                    title = title_el.text if title_el is not None else ""

                    desc_el = item.find("description")
                    summary = desc_el.text if desc_el is not None else ""

                    link_el = item.find("link")
                    url = link_el.text if link_el is not None else ""

                    pubdate_el = item.find("pubDate")
                    if pubdate_el is not None and pubdate_el.text:
                        # Parse various date formats
                        try:
                            published = datetime.strptime(
                                pubdate_el.text,
                                "%a, %d %b %Y %H:%M:%S %z"
                            ).replace(tzinfo=None)
                        except:
                            published = datetime.now()
                    else:
                        published = datetime.now()

                    # Skip old articles
                    if published < cutoff:
                        continue

                    article_id = self._generate_article_id(title, source.value)

                    # Skip already seen
                    if article_id in self.seen_ids:
                        continue

                    # Clean HTML from summary
                    summary = re.sub(r'<[^>]+>', '', summary or "")[:500]

                    article = NewsArticle(
                        article_id=article_id,
                        title=title,
                        summary=summary,
                        source=source,
                        category=NewsCategory.MARKET,  # Default, will be updated
                        url=url,
                        published=published
                    )

                    # Analyze article
                    self._analyze_article(article)

                    articles.append(article)

                except Exception as e:
                    logger.debug(f"Failed to parse item: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Failed to fetch RSS from {source.value}: {e}")

        return articles

    def _fetch_newsapi(self, query: str = "cryptocurrency") -> List[NewsArticle]:
        """Fetch from NewsAPI (requires API key)"""
        if not self.newsapi_key:
            return []

        articles = []

        try:
            response = self._session.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 50,
                    "apiKey": self.newsapi_key
                },
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            cutoff = datetime.now() - timedelta(hours=self.lookback_hours)

            for item in data.get("articles", []):
                try:
                    title = item.get("title", "")
                    article_id = self._generate_article_id(title, "newsapi")

                    if article_id in self.seen_ids:
                        continue

                    published_str = item.get("publishedAt", "")
                    try:
                        published = datetime.fromisoformat(published_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except:
                        published = datetime.now()

                    if published < cutoff:
                        continue

                    article = NewsArticle(
                        article_id=article_id,
                        title=title,
                        summary=item.get("description", "")[:500],
                        source=NewsSource.GENERAL,
                        category=NewsCategory.MARKET,
                        url=item.get("url", ""),
                        published=published
                    )

                    self._analyze_article(article)
                    articles.append(article)

                except Exception as e:
                    logger.debug(f"Failed to parse NewsAPI item: {e}")
                    continue

        except Exception as e:
            logger.warning(f"NewsAPI error: {e}")

        return articles

    def _analyze_article(self, article: NewsArticle):
        """Analyze article for sentiment, category, and impact"""
        text = f"{article.title} {article.summary}".lower()

        # Categorize
        max_matches = 0
        best_category = NewsCategory.MARKET

        for category, patterns in self.CATEGORY_PATTERNS.items():
            matches = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
            if matches > max_matches:
                max_matches = matches
                best_category = category

        article.category = best_category

        # Sentiment analysis
        bullish = sum(1 for p in self.BULLISH_PATTERNS if re.search(p, text, re.IGNORECASE))
        bearish = sum(1 for p in self.BEARISH_PATTERNS if re.search(p, text, re.IGNORECASE))

        total = bullish + bearish
        if total > 0:
            article.sentiment_score = (bullish - bearish) / total
        else:
            article.sentiment_score = 0

        # Impact score
        impact_matches = sum(1 for p in self.HIGH_IMPACT_KEYWORDS if re.search(p, text, re.IGNORECASE))
        article.impact_score = min(impact_matches / 3, 1.0)  # Normalize

        # Boost impact for certain categories
        if article.category == NewsCategory.SECURITY:
            article.impact_score = min(article.impact_score + 0.3, 1.0)
        elif article.category == NewsCategory.REGULATION:
            article.impact_score = min(article.impact_score + 0.2, 1.0)

        # Extract mentioned assets
        for asset, patterns in self.ASSET_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if asset not in article.mentioned_assets:
                        article.mentioned_assets.append(asset)
                    break

        # Default to BTC if no specific asset mentioned
        if not article.mentioned_assets:
            article.mentioned_assets = ["BTC"]

    def refresh_news(self) -> int:
        """Refresh news from all sources"""
        now = time.time()

        if now - self.last_refresh < self.refresh_interval:
            return len(self.articles)

        logger.info("Refreshing news feeds...")

        new_articles = []

        # Fetch from RSS feeds
        for source, url in self.RSS_FEEDS.items():
            articles = self._parse_rss_feed(source, url)
            new_articles.extend(articles)
            logger.debug(f"  {source.value}: {len(articles)} new articles")

        # Fetch from NewsAPI
        newsapi_articles = self._fetch_newsapi()
        new_articles.extend(newsapi_articles)

        # Process new articles
        for article in new_articles:
            self.seen_ids.add(article.article_id)
            self.articles[article.article_id] = article

            # Generate signals for high-impact articles
            if article.impact_score > 0.3:
                self._generate_signal(article)

                # Breaking news callback
                if article.impact_score > 0.6 and self.on_breaking_news:
                    self.on_breaking_news(article)

        # Clean up old articles
        cutoff = datetime.now() - timedelta(hours=self.lookback_hours * 2)
        self.articles = {
            k: v for k, v in self.articles.items()
            if v.published > cutoff
        }

        self.last_refresh = now

        logger.info(f"Processed {len(new_articles)} new articles, {len(self.articles)} total")
        return len(self.articles)

    def _generate_signal(self, article: NewsArticle):
        """Generate trading signal from news article"""
        # Calculate direction
        direction = article.sentiment_score

        # Category-specific adjustments
        if article.category == NewsCategory.SECURITY:
            # Hacks are always bearish
            direction = min(direction, -0.5)
        elif article.category == NewsCategory.REGULATION:
            # Regulation news amplified
            direction *= 1.5

        direction = max(-1, min(1, direction))

        # Calculate urgency
        age_minutes = (datetime.now() - article.published).total_seconds() / 60
        recency = max(0, 1 - age_minutes / 60)  # Decay over 1 hour

        urgency = article.impact_score * recency

        # Confidence based on impact and source
        confidence = article.impact_score * 0.7 + 0.3  # Base confidence

        # Generate signal for each mentioned asset
        for asset in article.mentioned_assets:
            signal = NewsSignal(
                asset=asset,
                source=article.source,
                direction=direction,
                confidence=confidence,
                urgency=urgency,
                category=article.category,
                headline=article.title,
                article_url=article.url
            )

            self.signals.append(signal)

            if self.on_signal:
                self.on_signal(signal)

            direction_str = "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "NEUTRAL"
            logger.info(
                f"News signal: {asset} {direction_str} "
                f"(urgency: {urgency:.2f}) - {article.title[:60]}..."
            )

    def get_current_signal(self, asset: str) -> Optional[NewsSignal]:
        """Get aggregated current signal for an asset"""
        self.refresh_news()

        # Get recent signals (last 2 hours)
        cutoff = datetime.now() - timedelta(hours=2)
        recent = [
            s for s in self.signals
            if s.asset == asset and s.timestamp > cutoff
        ]

        if not recent:
            return None

        # Weight by urgency and recency
        total_weight = 0
        weighted_direction = 0
        max_urgency = 0
        most_urgent_signal = None

        for signal in recent:
            age = (datetime.now() - signal.timestamp).total_seconds() / 3600
            weight = signal.urgency * (1 - age / 2)  # Decay over 2 hours

            total_weight += weight
            weighted_direction += signal.direction * weight

            if signal.urgency > max_urgency:
                max_urgency = signal.urgency
                most_urgent_signal = signal

        if total_weight == 0 or most_urgent_signal is None:
            return None

        # Create aggregated signal
        return NewsSignal(
            asset=asset,
            source=most_urgent_signal.source,
            direction=weighted_direction / total_weight,
            confidence=most_urgent_signal.confidence,
            urgency=max_urgency,
            category=most_urgent_signal.category,
            headline=f"Aggregated from {len(recent)} news items",
            article_url=most_urgent_signal.article_url
        )

    def get_news_summary(self) -> Dict[str, any]:
        """Get summary of recent news"""
        self.refresh_news()

        summary = {
            "total_articles": len(self.articles),
            "by_category": {},
            "by_source": {},
            "avg_sentiment": 0,
            "high_impact_count": 0,
            "recent_headlines": []
        }

        sentiments = []

        for article in self.articles.values():
            # By category
            cat = article.category.value
            if cat not in summary["by_category"]:
                summary["by_category"][cat] = 0
            summary["by_category"][cat] += 1

            # By source
            src = article.source.value
            if src not in summary["by_source"]:
                summary["by_source"][src] = 0
            summary["by_source"][src] += 1

            sentiments.append(article.sentiment_score)

            if article.impact_score > 0.5:
                summary["high_impact_count"] += 1

        if sentiments:
            summary["avg_sentiment"] = sum(sentiments) / len(sentiments)

        # Recent high-impact headlines
        sorted_articles = sorted(
            self.articles.values(),
            key=lambda a: (a.impact_score, a.published),
            reverse=True
        )[:5]

        for article in sorted_articles:
            direction = "🟢" if article.sentiment_score > 0.2 else "🔴" if article.sentiment_score < -0.2 else "⚪"
            summary["recent_headlines"].append({
                "title": article.title[:80],
                "category": article.category.value,
                "sentiment": direction,
                "impact": article.impact_score,
                "source": article.source.value
            })

        return summary


# Demo function
async def demo_news_scanner():
    """Demo the news sentiment scanner"""
    print("\n=== News Sentiment Scanner ===\n")

    scanner = NewsSentimentScanner(
        refresh_interval=30,  # 30 seconds for demo
        lookback_hours=48
    )

    def on_signal(signal: NewsSignal):
        direction = "BULLISH" if signal.direction > 0 else "BEARISH" if signal.direction < 0 else "NEUTRAL"
        print(f"\n  SIGNAL: {signal.asset} {direction}")
        print(f"    Category: {signal.category.value}")
        print(f"    Urgency: {signal.urgency:.2f}")
        print(f"    Headline: {signal.headline[:70]}...")

    def on_breaking(article: NewsArticle):
        print(f"\n  ⚡ BREAKING: {article.title[:70]}...")

    scanner.on_signal = on_signal
    scanner.on_breaking_news = on_breaking

    print("Fetching news from RSS feeds...\n")

    # Refresh
    count = scanner.refresh_news()
    print(f"Found {count} articles\n")

    # Summary
    summary = scanner.get_news_summary()

    print("--- Summary ---")
    print(f"Total Articles: {summary['total_articles']}")
    print(f"High Impact: {summary['high_impact_count']}")
    print(f"Avg Sentiment: {summary['avg_sentiment']:.2f}")

    print(f"\nBy Category:")
    for cat, count in summary["by_category"].items():
        print(f"  {cat}: {count}")

    print(f"\nBy Source:")
    for src, count in summary["by_source"].items():
        print(f"  {src}: {count}")

    print(f"\n--- Recent High-Impact Headlines ---")
    for item in summary["recent_headlines"]:
        print(f"\n{item['sentiment']} [{item['category']}] ({item['source']})")
        print(f"   {item['title']}")

    # Get signal for BTC
    btc_signal = scanner.get_current_signal("BTC")
    if btc_signal:
        direction = "BULLISH" if btc_signal.direction > 0 else "BEARISH" if btc_signal.direction < 0 else "NEUTRAL"
        print(f"\n--- BTC Signal ---")
        print(f"Direction: {direction} ({btc_signal.direction:.2f})")
        print(f"Urgency: {btc_signal.urgency:.2f}")
        print(f"Category: {btc_signal.category.value}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_news_scanner())
