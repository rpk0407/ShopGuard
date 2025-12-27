"""
Social Media Sentiment Analysis
Fetches and analyzes sentiment from:
- Reddit (WSB, stocks, cryptocurrency) - FREE
- StockTwits - FREE
"""
import re
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import requests


@dataclass
class SocialPost:
    """A social media post"""
    platform: str
    title: str
    content: str
    author: str
    url: str
    score: int  # upvotes/likes
    comments: int
    timestamp: datetime
    symbols: List[str] = field(default_factory=list)
    sentiment: float = 0.0


class SocialSentiment:
    """
    Analyzes social media sentiment from FREE sources
    No API keys needed!
    """

    # Extended sentiment words for trading
    BULLISH_WORDS = [
        "moon", "rocket", "buy", "calls", "bull", "long", "yolo", "diamond",
        "hands", "tendies", "gains", "pump", "breakout", "squeeze", "undervalued",
        "dip", "accumulate", "hold", "hodl", "bullish", "upside", "potential",
        "growth", "strong", "beat", "crush", "soar", "surge", "rally", "green"
    ]

    BEARISH_WORDS = [
        "puts", "bear", "short", "sell", "crash", "dump", "bag", "loss",
        "overvalued", "bubble", "scam", "fraud", "bearish", "downside", "weak",
        "miss", "fail", "tank", "plunge", "red", "rip", "dead", "worthless"
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        self._cache: Dict[str, any] = {}
        self._cache_time: Dict[str, datetime] = {}

    def _is_cached(self, key: str, ttl: int = 300) -> bool:
        if key not in self._cache:
            return False
        if datetime.now() - self._cache_time[key] > timedelta(seconds=ttl):
            return False
        return True

    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text"""
        text_lower = text.lower()
        words = re.findall(r'\w+', text_lower)

        bullish = sum(1 for w in words if w in self.BULLISH_WORDS)
        bearish = sum(1 for w in words if w in self.BEARISH_WORDS)

        total = bullish + bearish
        if total == 0:
            return 0
        return (bullish - bearish) / total

    def _extract_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from text"""
        patterns = [
            r'\$([A-Z]{1,5})\b',
            r'\b([A-Z]{2,5})\b'
        ]

        symbols = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            symbols.update(matches)

        # Filter common words that aren't symbols
        common_words = {"I", "A", "THE", "AND", "OR", "FOR", "TO", "IN", "ON", "AT", "IS", "IT",
                        "BE", "AS", "SO", "IF", "DD", "WSB", "IMO", "CEO", "IPO", "ETF"}
        symbols = {s for s in symbols if s not in common_words and len(s) >= 2}

        # Check for crypto
        if "bitcoin" in text.lower() or "btc" in text.lower():
            symbols.add("BTC")
        if "ethereum" in text.lower() or "eth" in text.lower():
            symbols.add("ETH")

        return list(symbols)

    def get_reddit_posts(self, subreddit: str, limit: int = 25) -> List[SocialPost]:
        """
        Fetch posts from a subreddit using Reddit's JSON API (FREE)
        No API key needed!
        """
        cache_key = f"reddit_{subreddit}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            posts = []
            for item in data["data"]["children"]:
                post_data = item["data"]

                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")
                full_text = f"{title} {selftext}"

                symbols = self._extract_symbols(full_text)
                sentiment = self._analyze_sentiment(full_text)

                posts.append(SocialPost(
                    platform="reddit",
                    title=title,
                    content=selftext[:500],
                    author=post_data.get("author", ""),
                    url=f"https://reddit.com{post_data.get('permalink', '')}",
                    score=post_data.get("score", 0),
                    comments=post_data.get("num_comments", 0),
                    timestamp=datetime.fromtimestamp(post_data.get("created_utc", 0)),
                    symbols=symbols,
                    sentiment=sentiment
                ))

            self._cache[cache_key] = posts
            self._cache_time[cache_key] = datetime.now()
            return posts

        except Exception as e:
            print(f"Error fetching r/{subreddit}: {e}")
            return []

    def get_wsb_sentiment(self) -> Dict[str, dict]:
        """Get WallStreetBets sentiment for symbols"""
        posts = self.get_reddit_posts("wallstreetbets", limit=50)

        symbol_data: Dict[str, dict] = {}

        for post in posts:
            for symbol in post.symbols:
                if symbol not in symbol_data:
                    symbol_data[symbol] = {
                        "mentions": 0,
                        "total_score": 0,
                        "total_sentiment": 0,
                        "bullish_posts": 0,
                        "bearish_posts": 0,
                        "posts": []
                    }

                symbol_data[symbol]["mentions"] += 1
                symbol_data[symbol]["total_score"] += post.score
                symbol_data[symbol]["total_sentiment"] += post.sentiment

                if post.sentiment > 0.1:
                    symbol_data[symbol]["bullish_posts"] += 1
                elif post.sentiment < -0.1:
                    symbol_data[symbol]["bearish_posts"] += 1

                symbol_data[symbol]["posts"].append({
                    "title": post.title[:100],
                    "score": post.score,
                    "sentiment": post.sentiment
                })

        # Calculate averages
        for symbol in symbol_data:
            mentions = symbol_data[symbol]["mentions"]
            if mentions > 0:
                symbol_data[symbol]["avg_sentiment"] = symbol_data[symbol]["total_sentiment"] / mentions
            else:
                symbol_data[symbol]["avg_sentiment"] = 0

        # Sort by mentions
        return dict(sorted(symbol_data.items(), key=lambda x: x[1]["mentions"], reverse=True))

    def get_crypto_sentiment(self) -> Dict[str, dict]:
        """Get crypto sentiment from Reddit"""
        subreddits = ["cryptocurrency", "Bitcoin", "ethereum"]

        all_posts = []
        for sub in subreddits:
            posts = self.get_reddit_posts(sub, limit=25)
            all_posts.extend(posts)
            time.sleep(0.5)

        symbol_data: Dict[str, dict] = {}

        for post in all_posts:
            for symbol in post.symbols:
                if symbol not in symbol_data:
                    symbol_data[symbol] = {
                        "mentions": 0,
                        "total_sentiment": 0,
                        "posts": []
                    }

                symbol_data[symbol]["mentions"] += 1
                symbol_data[symbol]["total_sentiment"] += post.sentiment
                symbol_data[symbol]["posts"].append({
                    "title": post.title[:80],
                    "score": post.score,
                    "sentiment": post.sentiment
                })

        for symbol in symbol_data:
            mentions = symbol_data[symbol]["mentions"]
            symbol_data[symbol]["avg_sentiment"] = symbol_data[symbol]["total_sentiment"] / mentions if mentions > 0 else 0

        return dict(sorted(symbol_data.items(), key=lambda x: x[1]["mentions"], reverse=True))

    def get_all_sentiment(self, symbols: List[str] = None) -> Dict[str, dict]:
        """
        Get combined sentiment for symbols from all sources
        """
        if symbols is None:
            symbols = ["NVDA", "TSLA", "AAPL", "AMD", "SPY", "BTC", "ETH"]

        # Get WSB data
        wsb_data = self.get_wsb_sentiment()

        # Get crypto data
        crypto_data = self.get_crypto_sentiment()

        results = {}
        for symbol in symbols:
            wsb = wsb_data.get(symbol, {})
            crypto = crypto_data.get(symbol, {})

            mentions = wsb.get("mentions", 0) + crypto.get("mentions", 0)
            if mentions == 0:
                results[symbol] = {
                    "sentiment": 0,
                    "mentions": 0,
                    "buzz": "low",
                    "signal": "neutral"
                }
                continue

            # Weighted average sentiment
            wsb_mentions = wsb.get("mentions", 0)
            crypto_mentions = crypto.get("mentions", 0)
            wsb_sentiment = wsb.get("avg_sentiment", 0)
            crypto_sentiment = crypto.get("avg_sentiment", 0)

            avg_sentiment = (wsb_sentiment * wsb_mentions + crypto_sentiment * crypto_mentions) / mentions

            # Determine buzz level
            if mentions >= 20:
                buzz = "high"
            elif mentions >= 10:
                buzz = "medium"
            else:
                buzz = "low"

            # Determine signal
            if avg_sentiment > 0.3 and mentions >= 5:
                signal = "bullish"
            elif avg_sentiment < -0.3 and mentions >= 5:
                signal = "bearish"
            else:
                signal = "neutral"

            results[symbol] = {
                "sentiment": round(avg_sentiment, 3),
                "mentions": mentions,
                "buzz": buzz,
                "signal": signal,
                "wsb_mentions": wsb_mentions,
                "crypto_mentions": crypto_mentions
            }

        return results


# Quick test
if __name__ == "__main__":
    sentiment = SocialSentiment()

    print("\n🐒 WALLSTREETBETS SENTIMENT")
    print("=" * 60)

    wsb = sentiment.get_wsb_sentiment()
    for symbol, data in list(wsb.items())[:10]:
        emoji = "🟢" if data["avg_sentiment"] > 0 else "🔴" if data["avg_sentiment"] < 0 else "⚪"
        print(f"{emoji} ${symbol}: {data['mentions']} mentions | Sentiment: {data['avg_sentiment']:.2f}")

    print("\n📊 COMBINED SENTIMENT")
    print("=" * 60)
    combined = sentiment.get_all_sentiment(["NVDA", "TSLA", "BTC", "ETH", "SPY"])
    for symbol, data in combined.items():
        emoji = "🟢" if data["signal"] == "bullish" else "🔴" if data["signal"] == "bearish" else "⚪"
        print(f"{emoji} {symbol}: {data['signal'].upper()} | Mentions: {data['mentions']} | Buzz: {data['buzz']}")
