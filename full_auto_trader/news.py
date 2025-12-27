"""
News Analysis - Fetches and analyzes financial news
Uses FREE sources (no API key needed):
- Google News RSS
- Yahoo Finance News
- Finviz News
"""
import re
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import requests
from xml.etree import ElementTree


@dataclass
class NewsArticle:
    """A news article"""
    title: str
    source: str
    url: str
    published: datetime
    symbols: List[str] = field(default_factory=list)
    sentiment: float = 0.0  # -1 to 1
    impact: float = 0.0     # 0 to 1


class NewsAnalyzer:
    """
    Fetches and analyzes financial news from FREE sources
    No API keys needed!
    """

    # Keywords for sentiment analysis
    POSITIVE_WORDS = [
        "surge", "soar", "jump", "rally", "gain", "rise", "up", "high", "record",
        "beat", "exceed", "profit", "growth", "bullish", "buy", "upgrade", "boom",
        "breakthrough", "success", "win", "positive", "strong", "recover", "moon",
        "breakout", "momentum", "outperform", "innovation", "partnership", "deal"
    ]

    NEGATIVE_WORDS = [
        "crash", "plunge", "drop", "fall", "decline", "down", "low", "miss",
        "loss", "fear", "bearish", "sell", "downgrade", "weak", "fail", "cut",
        "warning", "risk", "concern", "trouble", "crisis", "scandal", "fraud",
        "investigation", "lawsuit", "bankruptcy", "layoff", "recession", "dump"
    ]

    HIGH_IMPACT_WORDS = [
        "breaking", "urgent", "alert", "major", "significant", "massive",
        "record", "unprecedented", "shock", "surprise", "unexpected", "crash",
        "surge", "plunge", "fed", "regulation", "sec", "investigation", "earnings"
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        self._cache: Dict[str, List[NewsArticle]] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 300  # 5 minutes

    def _is_cached(self, key: str) -> bool:
        if key not in self._cache:
            return False
        if datetime.now() - self._cache_time[key] > timedelta(seconds=self._cache_ttl):
            return False
        return True

    def _analyze_sentiment(self, text: str) -> tuple:
        """
        Analyze sentiment of text
        Returns (sentiment, impact) where:
        - sentiment: -1 (very negative) to 1 (very positive)
        - impact: 0 (low) to 1 (high)
        """
        text_lower = text.lower()
        words = re.findall(r'\w+', text_lower)

        positive_count = sum(1 for word in words if word in self.POSITIVE_WORDS)
        negative_count = sum(1 for word in words if word in self.NEGATIVE_WORDS)
        impact_count = sum(1 for word in words if word in self.HIGH_IMPACT_WORDS)

        total = positive_count + negative_count
        if total == 0:
            sentiment = 0
        else:
            sentiment = (positive_count - negative_count) / total

        # Impact based on impact words and total sentiment words
        impact = min(1.0, (impact_count * 0.3) + (total * 0.1))

        return sentiment, impact

    def _extract_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from text"""
        # Common patterns: $AAPL, (AAPL), AAPL:
        patterns = [
            r'\$([A-Z]{1,5})',           # $AAPL
            r'\(([A-Z]{1,5})\)',          # (AAPL)
            r'([A-Z]{2,5})(?:\'s|:|\s)',  # AAPL's, AAPL:, AAPL
        ]

        symbols = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            symbols.update(matches)

        # Also check for known symbols
        known_symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "AMD", "SPY", "QQQ"]
        for symbol in known_symbols:
            if symbol in text.upper():
                symbols.add(symbol)

        # Check for crypto
        if "bitcoin" in text.lower() or "btc" in text.lower():
            symbols.add("BTC")
        if "ethereum" in text.lower() or "eth" in text.lower():
            symbols.add("ETH")

        return list(symbols)

    def get_google_news(self, query: str = "stock market") -> List[NewsArticle]:
        """Fetch news from Google News RSS (FREE)"""
        cache_key = f"google_{query}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()

            root = ElementTree.fromstring(resp.content)
            articles = []

            for item in root.findall(".//item")[:20]:  # Last 20 articles
                title = item.find("title").text or ""
                link = item.find("link").text or ""
                pub_date = item.find("pubDate").text or ""

                # Parse date
                try:
                    published = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                except:
                    published = datetime.now()

                sentiment, impact = self._analyze_sentiment(title)
                symbols = self._extract_symbols(title)

                articles.append(NewsArticle(
                    title=title,
                    source="Google News",
                    url=link,
                    published=published,
                    symbols=symbols,
                    sentiment=sentiment,
                    impact=impact
                ))

            self._cache[cache_key] = articles
            self._cache_time[cache_key] = datetime.now()
            return articles

        except Exception as e:
            print(f"Error fetching Google News: {e}")
            return []

    def get_symbol_news(self, symbol: str) -> List[NewsArticle]:
        """Get news for a specific symbol"""
        # Search for the symbol
        articles = self.get_google_news(f"{symbol} stock")

        # Also search company name for major stocks
        company_names = {
            "AAPL": "Apple",
            "GOOGL": "Google",
            "MSFT": "Microsoft",
            "AMZN": "Amazon",
            "NVDA": "Nvidia",
            "TSLA": "Tesla",
            "META": "Meta Facebook",
            "AMD": "AMD",
            "BTC": "Bitcoin",
            "ETH": "Ethereum"
        }

        if symbol in company_names:
            articles += self.get_google_news(company_names[symbol])

        # Deduplicate by URL
        seen = set()
        unique = []
        for article in articles:
            if article.url not in seen:
                seen.add(article.url)
                unique.append(article)

        # Sort by published date
        unique.sort(key=lambda x: x.published, reverse=True)
        return unique[:10]

    def get_market_news(self) -> List[NewsArticle]:
        """Get general market news"""
        queries = [
            "stock market today",
            "S&P 500",
            "NASDAQ",
            "cryptocurrency bitcoin"
        ]

        all_articles = []
        for query in queries:
            articles = self.get_google_news(query)
            all_articles.extend(articles)
            time.sleep(0.5)  # Rate limiting

        # Deduplicate
        seen = set()
        unique = []
        for article in all_articles:
            if article.url not in seen:
                seen.add(article.url)
                unique.append(article)

        unique.sort(key=lambda x: x.published, reverse=True)
        return unique[:20]

    def get_sentiment_summary(self, symbols: List[str] = None) -> Dict[str, dict]:
        """
        Get sentiment summary for symbols
        Returns dict with sentiment scores and recent news
        """
        if symbols is None:
            symbols = ["AAPL", "NVDA", "TSLA", "BTC", "ETH", "SPY"]

        results = {}
        for symbol in symbols:
            articles = self.get_symbol_news(symbol)

            if not articles:
                results[symbol] = {
                    "sentiment": 0,
                    "impact": 0,
                    "news_count": 0,
                    "latest_news": []
                }
                continue

            # Calculate aggregate sentiment
            avg_sentiment = sum(a.sentiment for a in articles) / len(articles)
            max_impact = max(a.impact for a in articles)

            results[symbol] = {
                "sentiment": avg_sentiment,
                "impact": max_impact,
                "news_count": len(articles),
                "latest_news": [
                    {"title": a.title, "sentiment": a.sentiment, "time": a.published.isoformat()}
                    for a in articles[:5]
                ]
            }

            time.sleep(0.3)

        return results


# Quick test
if __name__ == "__main__":
    analyzer = NewsAnalyzer()

    print("\n📰 MARKET NEWS")
    print("=" * 60)

    news = analyzer.get_market_news()
    for article in news[:5]:
        sentiment_emoji = "🟢" if article.sentiment > 0.1 else "🔴" if article.sentiment < -0.1 else "⚪"
        print(f"{sentiment_emoji} {article.title[:70]}...")
        print(f"   Sentiment: {article.sentiment:.2f} | Impact: {article.impact:.2f}")
        print()

    print("\n📊 SENTIMENT SUMMARY")
    print("=" * 60)
    summary = analyzer.get_sentiment_summary(["NVDA", "BTC", "TSLA"])
    for symbol, data in summary.items():
        emoji = "🟢" if data["sentiment"] > 0 else "🔴" if data["sentiment"] < 0 else "⚪"
        print(f"{emoji} {symbol}: Sentiment {data['sentiment']:.2f} | News: {data['news_count']}")
