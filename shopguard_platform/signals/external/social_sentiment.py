"""
Social Sentiment Analyzer
=========================
Analyzes sentiment from Twitter/X and Reddit for trading signals.

Key Insight:
- Social sentiment often leads price movements in crypto
- Reddit (r/cryptocurrency, r/bitcoin) captures retail sentiment
- Twitter/X captures influencer and whale sentiment
- Volume of mentions + sentiment = signal strength

Data Sources:
- Twitter/X API (requires API key)
- Reddit API (PRAW - Python Reddit API Wrapper)
- Alternative: Social scraping services (LunarCrush, Santiment)
"""

import logging
import time
import re
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def create_retry_session(retries: int = 3, backoff_factor: float = 1.0) -> requests.Session:
    """Create a requests session with retry logic for rate-limited APIs"""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        respect_retry_after_header=True
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class Platform(Enum):
    """Social media platforms"""
    TWITTER = "twitter"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    DISCORD = "discord"


@dataclass
class SocialPost:
    """A single social media post"""
    platform: Platform
    post_id: str
    text: str
    author: str
    timestamp: datetime
    likes: int = 0
    replies: int = 0
    retweets: int = 0  # or upvotes for Reddit
    sentiment_score: float = 0.0  # -1 to 1
    mentioned_assets: List[str] = field(default_factory=list)


@dataclass
class SentimentSignal:
    """Trading signal derived from social sentiment"""
    asset: str
    platform: Platform
    direction: float           # -1 (bearish) to +1 (bullish)
    confidence: float          # 0-1 confidence
    mention_count: int         # Number of mentions in time window
    avg_sentiment: float       # Average sentiment score
    volume_change: float       # % change vs previous period
    top_posts: List[str]       # Sample influential posts
    timestamp: datetime = field(default_factory=datetime.now)


class SocialSentimentAnalyzer:
    """
    Analyzes social media for crypto trading signals.

    Strategy:
    1. Track mention volume (spike detection)
    2. Analyze sentiment of mentions
    3. Weight by author influence (followers, karma)
    4. Detect FUD vs FOMO patterns
    5. Generate confidence-weighted signals

    Signal Generation:
    - High volume + positive sentiment = bullish
    - High volume + negative sentiment = bearish
    - Volume spike without sentiment shift = volatility warning
    """

    # Asset ticker mapping
    ASSET_PATTERNS = {
        "BTC": [r"\bbtc\b", r"\bbitcoin\b", r"₿"],
        "ETH": [r"\beth\b", r"\bethereum\b", r"\bether\b"],
        "SOL": [r"\bsol\b", r"\bsolana\b"],
        "DOGE": [r"\bdoge\b", r"\bdogecoin\b"],
        "XRP": [r"\bxrp\b", r"\bripple\b"],
        "BNB": [r"\bbnb\b", r"\bbinance\s+coin\b"],
        "ADA": [r"\bada\b", r"\bcardano\b"],
        "AVAX": [r"\bavax\b", r"\bavalanche\b"],
        "LINK": [r"\blink\b", r"\bchainlink\b"],
        "MATIC": [r"\bmatic\b", r"\bpolygon\b"],
    }

    # Sentiment lexicon (simplified)
    BULLISH_WORDS = [
        "moon", "mooning", "bullish", "pump", "buy", "long", "green",
        "rocket", "🚀", "lambo", "hodl", "diamond hands", "💎", "🙌",
        "breakout", "ath", "all time high", "adoption", "massive",
        "undervalued", "accumulate", "dip", "discount", "opportunity"
    ]

    BEARISH_WORDS = [
        "dump", "dumping", "bearish", "sell", "short", "red", "crash",
        "rekt", "scam", "rug", "rugpull", "ponzi", "dead", "worthless",
        "overvalued", "bubble", "collapse", "fear", "panic", "exit"
    ]

    # Reddit crypto subreddits
    REDDIT_SUBREDDITS = [
        "cryptocurrency", "bitcoin", "ethereum", "cryptomarkets",
        "altcoin", "defi", "solana", "wallstreetbets"
    ]

    # Twitter/X influential accounts to track
    TWITTER_INFLUENCERS = [
        "whale_alert", "lookonchain", "WatcherGuru", "BitcoinMagazine",
        "CryptoQuant", "santaborrar", "DocumentingBTC"
    ]

    def __init__(
        self,
        twitter_bearer_token: Optional[str] = None,
        reddit_client_id: Optional[str] = None,
        reddit_client_secret: Optional[str] = None,
        lunarcrush_api_key: Optional[str] = None,
        refresh_interval: int = 300,  # 5 minutes
    ):
        self.twitter_bearer_token = twitter_bearer_token
        self.reddit_client_id = reddit_client_id
        self.reddit_client_secret = reddit_client_secret
        self.lunarcrush_api_key = lunarcrush_api_key
        self.refresh_interval = refresh_interval

        # Data storage
        self.posts: Dict[str, List[SocialPost]] = {}  # asset -> posts
        self.signals: Dict[str, SentimentSignal] = {}  # asset -> latest signal
        self.historical_volume: Dict[str, List[int]] = {}  # For spike detection

        self.last_refresh: float = 0

        # Rate limiting
        self._reddit_last_request: float = 0
        self._reddit_min_interval: float = 2.0  # Reddit rate limit: wait 2s between requests

        # Callbacks
        self.on_signal: Optional[Callable[[SentimentSignal], None]] = None

        self._session = create_retry_session()

    def _analyze_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of text using lexicon-based approach.
        Returns score from -1 (bearish) to +1 (bullish).
        """
        text_lower = text.lower()

        bullish_count = sum(1 for word in self.BULLISH_WORDS if word in text_lower)
        bearish_count = sum(1 for word in self.BEARISH_WORDS if word in text_lower)

        total = bullish_count + bearish_count
        if total == 0:
            return 0.0

        # Normalize to [-1, 1]
        return (bullish_count - bearish_count) / total

    def _extract_assets(self, text: str) -> List[str]:
        """Extract mentioned crypto assets from text"""
        text_lower = text.lower()
        found = []

        for asset, patterns in self.ASSET_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    found.append(asset)
                    break

        return found

    def _fetch_lunarcrush(self, asset: str) -> Optional[Dict]:
        """Fetch social metrics from LunarCrush API"""
        if not self.lunarcrush_api_key:
            return None

        try:
            response = self._session.get(
                "https://lunarcrush.com/api4/public/coins",
                params={
                    "key": self.lunarcrush_api_key,
                    "symbol": asset,
                    "data": "market,social"
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("data"):
                return data["data"][0]
            return None

        except Exception as e:
            logger.warning(f"LunarCrush API error: {e}")
            return None

    def _wait_for_rate_limit(self):
        """Wait if needed to respect Reddit rate limits"""
        now = time.time()
        elapsed = now - self._reddit_last_request
        if elapsed < self._reddit_min_interval:
            wait_time = self._reddit_min_interval - elapsed + random.uniform(0.1, 0.5)
            time.sleep(wait_time)
        self._reddit_last_request = time.time()

    def _fetch_reddit_posts(self, asset: str, limit: int = 100) -> List[SocialPost]:
        """Fetch recent posts from Reddit with rate limiting"""
        posts = []

        # Without credentials, we can still fetch public JSON feeds
        for subreddit in self.REDDIT_SUBREDDITS[:3]:  # Limit subreddits
            try:
                # Rate limit before each request
                self._wait_for_rate_limit()

                url = f"https://www.reddit.com/r/{subreddit}/search.json"
                response = self._session.get(
                    url,
                    params={
                        "q": asset,
                        "sort": "new",
                        "limit": limit // 3,
                        "t": "day"
                    },
                    headers={"User-Agent": "TITAN-Trading/1.0 (by /u/TitanBot)"},
                    timeout=15
                )

                if response.status_code == 429:
                    logger.warning(f"Reddit rate limited for r/{subreddit}, waiting...")
                    time.sleep(5)
                    continue

                if response.status_code == 200:
                    data = response.json()
                    for child in data.get("data", {}).get("children", []):
                        post_data = child.get("data", {})

                        post = SocialPost(
                            platform=Platform.REDDIT,
                            post_id=post_data.get("id", ""),
                            text=f"{post_data.get('title', '')} {post_data.get('selftext', '')}",
                            author=post_data.get("author", ""),
                            timestamp=datetime.fromtimestamp(post_data.get("created_utc", 0)),
                            likes=post_data.get("score", 0),
                            replies=post_data.get("num_comments", 0)
                        )

                        # Analyze
                        post.sentiment_score = self._analyze_sentiment(post.text)
                        post.mentioned_assets = self._extract_assets(post.text)

                        posts.append(post)

            except Exception as e:
                logger.warning(f"Reddit fetch error for r/{subreddit}: {e}")
                continue

        return posts

    def _fetch_twitter_posts(self, asset: str, limit: int = 100) -> List[SocialPost]:
        """Fetch recent tweets (requires Bearer token)"""
        if not self.twitter_bearer_token:
            return []

        posts = []

        try:
            # Twitter API v2 search
            response = self._session.get(
                "https://api.twitter.com/2/tweets/search/recent",
                params={
                    "query": f"${asset} OR #{asset} -is:retweet lang:en",
                    "max_results": min(limit, 100),
                    "tweet.fields": "created_at,public_metrics,author_id"
                },
                headers={
                    "Authorization": f"Bearer {self.twitter_bearer_token}"
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                for tweet in data.get("data", []):
                    metrics = tweet.get("public_metrics", {})

                    post = SocialPost(
                        platform=Platform.TWITTER,
                        post_id=tweet.get("id", ""),
                        text=tweet.get("text", ""),
                        author=tweet.get("author_id", ""),
                        timestamp=datetime.fromisoformat(
                            tweet.get("created_at", "").replace("Z", "+00:00")
                        ),
                        likes=metrics.get("like_count", 0),
                        replies=metrics.get("reply_count", 0),
                        retweets=metrics.get("retweet_count", 0)
                    )

                    post.sentiment_score = self._analyze_sentiment(post.text)
                    post.mentioned_assets = self._extract_assets(post.text)

                    posts.append(post)

        except Exception as e:
            logger.warning(f"Twitter fetch error: {e}")

        return posts

    def refresh_data(self, assets: List[str]) -> Dict[str, int]:
        """Refresh social data for given assets"""
        now = time.time()

        if now - self.last_refresh < self.refresh_interval:
            return {a: len(self.posts.get(a, [])) for a in assets}

        logger.info(f"Refreshing social sentiment for {assets}...")

        counts = {}

        for asset in assets:
            all_posts = []

            # Fetch from Reddit (always available)
            reddit_posts = self._fetch_reddit_posts(asset)
            all_posts.extend(reddit_posts)

            # Fetch from Twitter if configured
            twitter_posts = self._fetch_twitter_posts(asset)
            all_posts.extend(twitter_posts)

            # Store posts
            old_posts = self.posts.get(asset, [])
            self.posts[asset] = all_posts
            counts[asset] = len(all_posts)

            # Track volume history for spike detection
            if asset not in self.historical_volume:
                self.historical_volume[asset] = []
            self.historical_volume[asset].append(len(all_posts))

            # Keep last 24 data points
            if len(self.historical_volume[asset]) > 24:
                self.historical_volume[asset] = self.historical_volume[asset][-24:]

            # Generate signal
            self._generate_signal(asset, all_posts, old_posts)

        self.last_refresh = now
        return counts

    def _generate_signal(
        self,
        asset: str,
        posts: List[SocialPost],
        old_posts: List[SocialPost]
    ):
        """Generate trading signal from social data"""
        if not posts:
            return

        # Calculate metrics
        mention_count = len(posts)
        old_count = len(old_posts) if old_posts else mention_count

        # Volume change
        volume_change = (mention_count - old_count) / max(old_count, 1)

        # Average sentiment
        sentiments = [p.sentiment_score for p in posts if p.sentiment_score != 0]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        # Weighted sentiment by engagement
        total_engagement = sum(p.likes + p.replies + p.retweets for p in posts)
        if total_engagement > 0:
            weighted_sentiment = sum(
                p.sentiment_score * (p.likes + p.replies + p.retweets)
                for p in posts
            ) / total_engagement
        else:
            weighted_sentiment = avg_sentiment

        # Calculate direction
        # Combine sentiment with volume spike
        direction = weighted_sentiment

        # Volume spike amplifies signal
        if abs(volume_change) > 0.5:  # 50%+ volume change
            direction *= (1 + min(abs(volume_change), 1))

        # Normalize to [-1, 1]
        direction = max(-1, min(1, direction))

        # Confidence based on volume and sentiment consistency
        historical_avg = sum(self.historical_volume.get(asset, [mention_count])) / max(len(self.historical_volume.get(asset, [1])), 1)
        volume_score = min(mention_count / max(historical_avg, 1), 2) / 2

        sentiment_variance = sum((s - avg_sentiment) ** 2 for s in sentiments) / max(len(sentiments), 1)
        consistency_score = max(0, 1 - sentiment_variance)

        confidence = (volume_score + consistency_score) / 2

        # Get top posts by engagement
        sorted_posts = sorted(
            posts,
            key=lambda p: p.likes + p.replies + p.retweets,
            reverse=True
        )[:3]

        top_post_texts = [p.text[:100] for p in sorted_posts]

        # Determine primary platform
        reddit_count = sum(1 for p in posts if p.platform == Platform.REDDIT)
        twitter_count = sum(1 for p in posts if p.platform == Platform.TWITTER)
        primary_platform = Platform.REDDIT if reddit_count >= twitter_count else Platform.TWITTER

        signal = SentimentSignal(
            asset=asset,
            platform=primary_platform,
            direction=direction,
            confidence=confidence,
            mention_count=mention_count,
            avg_sentiment=avg_sentiment,
            volume_change=volume_change,
            top_posts=top_post_texts
        )

        # Store and emit
        self.signals[asset] = signal

        if self.on_signal and abs(direction) > 0.2:  # Only emit significant signals
            self.on_signal(signal)
            logger.info(
                f"Social signal: {asset} {'BULLISH' if direction > 0 else 'BEARISH'} "
                f"(conf: {confidence:.2f}, mentions: {mention_count}, "
                f"sentiment: {avg_sentiment:.2f})"
            )

    def get_current_signal(self, asset: str) -> Optional[SentimentSignal]:
        """Get current signal for an asset"""
        self.refresh_data([asset])
        return self.signals.get(asset)

    def get_social_summary(self, assets: List[str]) -> Dict[str, any]:
        """Get summary of social sentiment across assets"""
        self.refresh_data(assets)

        summary = {
            "assets": {},
            "overall_sentiment": 0,
            "most_discussed": None,
            "biggest_sentiment_shift": None
        }

        total_mentions = 0
        weighted_sentiment = 0

        for asset in assets:
            signal = self.signals.get(asset)
            if signal:
                summary["assets"][asset] = {
                    "mentions": signal.mention_count,
                    "sentiment": signal.avg_sentiment,
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "volume_change": signal.volume_change
                }

                total_mentions += signal.mention_count
                weighted_sentiment += signal.avg_sentiment * signal.mention_count

        if total_mentions > 0:
            summary["overall_sentiment"] = weighted_sentiment / total_mentions

            # Most discussed
            summary["most_discussed"] = max(
                summary["assets"].items(),
                key=lambda x: x[1]["mentions"]
            )[0]

            # Biggest sentiment shift
            summary["biggest_sentiment_shift"] = max(
                summary["assets"].items(),
                key=lambda x: abs(x[1].get("volume_change", 0))
            )[0]

        return summary


# Demo function
async def demo_social_sentiment():
    """Demo the social sentiment analyzer"""
    print("\n=== Social Sentiment Analyzer ===\n")

    analyzer = SocialSentimentAnalyzer(
        refresh_interval=60  # 1 minute for demo
    )

    def on_signal(signal: SentimentSignal):
        direction = "BULLISH" if signal.direction > 0 else "BEARISH"
        print(f"\n  SIGNAL: {signal.asset} {direction}")
        print(f"    Platform: {signal.platform.value}")
        print(f"    Confidence: {signal.confidence:.2f}")
        print(f"    Mentions: {signal.mention_count}")
        print(f"    Avg Sentiment: {signal.avg_sentiment:.2f}")
        print(f"    Volume Change: {signal.volume_change*100:.1f}%")

    analyzer.on_signal = on_signal

    assets = ["BTC", "ETH", "SOL"]

    print(f"Analyzing social sentiment for {assets}...")
    print("(Fetching from Reddit - Twitter requires API key)\n")

    # Refresh data
    counts = analyzer.refresh_data(assets)
    for asset, count in counts.items():
        print(f"  {asset}: {count} posts analyzed")

    # Get summary
    print("\n--- Summary ---")
    summary = analyzer.get_social_summary(assets)

    print(f"Overall Sentiment: {summary['overall_sentiment']:.2f}")
    if summary["most_discussed"]:
        print(f"Most Discussed: {summary['most_discussed']}")
    if summary["biggest_sentiment_shift"]:
        print(f"Biggest Volume Change: {summary['biggest_sentiment_shift']}")

    print("\n--- Asset Details ---")
    for asset, data in summary["assets"].items():
        direction = "BULLISH" if data["direction"] > 0 else "BEARISH" if data["direction"] < 0 else "NEUTRAL"
        print(f"\n{asset}:")
        print(f"  Direction: {direction} ({data['direction']:.2f})")
        print(f"  Mentions: {data['mentions']}")
        print(f"  Sentiment: {data['sentiment']:.2f}")
        print(f"  Confidence: {data['confidence']:.2f}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_social_sentiment())
