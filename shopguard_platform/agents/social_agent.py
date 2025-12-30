"""
Social Sentiment Agent
======================
Analyzes social media and community sentiment for market insights.

Sources:
- Reddit (r/wallstreetbets, r/stocks, r/cryptocurrency, r/bitcoin, r/ethereum)
- Community discussions and trends

Analysis:
- Sentiment scoring
- Trending topics detection
- FOMO/FUD detection
- Whale watching (large position mentions)
- Contrarian indicators (extreme sentiment = potential reversal)

Circuit Breaker Pattern:
- Handles Reddit API failures gracefully
- Returns neutral signals instead of crashing
- Tracks failure states for recovery
"""
import re
import time
import requests
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from .base_agent import BaseAgent, AgentOpinion, Action, Confidence

# Import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from utils.logging_config import agent_logger as logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    Prevents cascade failures when external services are down.
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, return fallback immediately
    - HALF_OPEN: Testing if service recovered
    """
    failure_threshold: int = 3  # Failures before opening
    recovery_timeout: float = 60.0  # Seconds before trying again
    half_open_max_calls: int = 1  # Test calls in half-open

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    half_open_calls: int = 0

    def can_execute(self) -> bool:
        """Check if request should be allowed"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return False

    def record_success(self):
        """Record a successful call"""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker CLOSED - service recovered")
            self.state = CircuitState.CLOSED
        self.failure_count = 0

    def record_failure(self, error: str = ""):
        """Record a failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker OPEN - recovery failed: {error}")
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            logger.warning(f"Circuit breaker OPEN - threshold reached: {error}")
            self.state = CircuitState.OPEN

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "time_until_recovery": max(0, self.recovery_timeout - (time.time() - self.last_failure_time))
            if self.state == CircuitState.OPEN else 0
        }


@dataclass
class SocialPost:
    """Single social media post with analysis"""
    title: str
    content: str
    source: str  # reddit, etc.
    subreddit: str
    author: str
    score: int  # upvotes
    comments: int
    sentiment: float
    created: datetime
    url: str
    is_dd: bool = False  # Due Diligence post
    mentions_ticker: bool = False
    position_size: str = ""  # If mentioned


@dataclass
class ViralMetrics:
    """Viral K-Factor metrics for measuring information spread velocity"""
    k_factor: float  # Current K-Factor (rate of mention growth)
    acceleration: float  # Change in K-Factor (2nd derivative)
    mentions_t: int  # Current period mentions
    mentions_t_minus_1: int  # Previous period mentions
    is_viral: bool  # K > 1.2 and acceleration > 0
    viral_signal: str  # "EXPLOSIVE", "GROWING", "STABLE", "DECLINING"


@dataclass
class SocialAnalysis:
    """Comprehensive social sentiment analysis"""
    asset: str
    total_mentions: int
    sentiment_score: float
    sentiment_label: str
    fomo_level: float  # 0-1
    fud_level: float  # 0-1
    trending_score: float  # How much it's being discussed
    top_posts: List[SocialPost]
    key_narratives: List[str]
    whale_activity: List[str]
    contrarian_signal: bool  # Extreme sentiment = potential reversal
    viral_metrics: ViralMetrics = None  # New viral K-Factor metrics


class SocialAgent(BaseAgent):
    """
    Social Sentiment Agent
    Analyzes community sentiment and social media discussions

    Features circuit breaker pattern for Reddit API resilience.
    """

    def __init__(self):
        super().__init__(
            name="Social Sentiment Agent",
            specialty="Community sentiment, social media trends, and crowd psychology"
        )

        # Circuit breaker for Reddit API
        self.reddit_circuit = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0
        )

        # Subreddits to monitor
        self.crypto_subreddits = ['cryptocurrency', 'bitcoin', 'ethereum', 'CryptoMarkets']
        self.stock_subreddits = ['wallstreetbets', 'stocks', 'investing', 'options']

        # Sentiment keywords
        self.bullish_terms = {
            # WSB/Reddit slang
            'moon', 'mooning', 'rocket', '🚀', 'diamond hands', '💎🙌', 'hodl',
            'lfg', 'wagmi', 'bullish', 'buy the dip', 'btd', 'calls', 'long',
            'undervalued', 'gem', 'alpha', 'pump', 'send it', 'yolo',
            'to the moon', 'ath incoming', 'accumulate', 'loading up',

            # Positive sentiment
            'bullish', 'optimistic', 'confident', 'excited', 'love',
            'great', 'amazing', 'huge', 'massive', 'breakout'
        }

        self.bearish_terms = {
            # WSB/Reddit slang
            'rekt', 'rug', 'rugpull', 'dump', 'dumping', 'puts', 'short',
            'overvalued', 'scam', 'ponzi', 'crash', 'bear', 'ngmi',
            'paper hands', 'sell', 'exit', 'top signal', 'bagholding',

            # Negative sentiment
            'bearish', 'worried', 'concerned', 'scared', 'panic',
            'terrible', 'awful', 'dead', 'dying', 'collapse', 'fear'
        }

        # FOMO indicators
        self.fomo_terms = ['fomo', 'missing out', 'still early', 'last chance',
                          'dont miss', "don't miss", 'before it moons', 'buy now']

        # FUD indicators
        self.fud_terms = ['fud', 'dead coin', 'going to zero', 'exit scam',
                         'sell everything', 'get out now', 'warning', 'avoid']

        # Asset-specific terms
        self.asset_terms = {
            'BTC': ['bitcoin', 'btc', 'sats', 'satoshi'],
            'ETH': ['ethereum', 'eth', 'ether', 'vitalik'],
            'SPY': ['spy', 's&p', 'sp500', 'spx'],
            'QQQ': ['qqq', 'nasdaq', 'tech stocks'],
            'NVDA': ['nvda', 'nvidia', 'jensen']
        }

    def fetch_reddit_data(self, asset: str) -> List[SocialPost]:
        """
        Fetch posts from relevant subreddits with circuit breaker protection.

        Returns empty list if circuit is open (service unavailable).
        """
        # Check circuit breaker first
        if not self.reddit_circuit.can_execute():
            status = self.reddit_circuit.get_status()
            logger.warning(f"Reddit circuit OPEN - skipping fetch. Recovery in {status['time_until_recovery']:.0f}s")
            return []

        posts = []
        request_failed = False
        error_msg = ""

        # Determine which subreddits to check
        if asset in ['BTC', 'ETH']:
            subreddits = self.crypto_subreddits
        else:
            subreddits = self.stock_subreddits

        search_terms = self.asset_terms.get(asset, [asset.lower()])

        for subreddit in subreddits[:3]:  # Limit to avoid rate limiting
            try:
                # Reddit JSON API (no auth needed for public data)
                url = f"https://www.reddit.com/r/{subreddit}/search.json?q={search_terms[0]}&sort=hot&limit=15&t=day"
                headers = {'User-Agent': 'ShopGuard Trading Bot 1.0'}

                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()

                    for post in data.get('data', {}).get('children', []):
                        post_data = post.get('data', {})

                        title = post_data.get('title', '')
                        content = post_data.get('selftext', '')[:500]  # Limit content length

                        # Analyze sentiment
                        full_text = f"{title} {content}"
                        sentiment = self._analyze_sentiment(full_text)

                        # Check if it's a DD post
                        is_dd = 'dd' in title.lower() or 'due diligence' in title.lower()

                        # Check for position mentions
                        position = self._extract_position(full_text)

                        posts.append(SocialPost(
                            title=title,
                            content=content,
                            source='reddit',
                            subreddit=subreddit,
                            author=post_data.get('author', 'unknown'),
                            score=post_data.get('score', 0),
                            comments=post_data.get('num_comments', 0),
                            sentiment=sentiment,
                            created=datetime.fromtimestamp(post_data.get('created_utc', 0)),
                            url=f"https://reddit.com{post_data.get('permalink', '')}",
                            is_dd=is_dd,
                            mentions_ticker=any(term in full_text.lower() for term in search_terms),
                            position_size=position
                        ))
                elif response.status_code == 429:
                    # Rate limited
                    request_failed = True
                    error_msg = "Reddit rate limit (429)"
                    logger.warning(f"Reddit rate limited for r/{subreddit}")
                elif response.status_code >= 500:
                    # Server error
                    request_failed = True
                    error_msg = f"Reddit server error ({response.status_code})"
                    logger.error(f"Reddit server error {response.status_code} for r/{subreddit}")

            except requests.exceptions.Timeout:
                request_failed = True
                error_msg = "Reddit timeout"
                logger.warning(f"Reddit timeout for r/{subreddit}")
            except requests.exceptions.ConnectionError as e:
                request_failed = True
                error_msg = f"Reddit connection error: {str(e)[:50]}"
                logger.error(f"Reddit connection error for r/{subreddit}: {e}")
            except Exception as e:
                logger.debug(f"Reddit fetch error for r/{subreddit}: {e}")
                continue

        # Also check hot posts in main subreddits
        for subreddit in subreddits[:2]:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=20"
                headers = {'User-Agent': 'ShopGuard Trading Bot 1.0'}

                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()

                    for post in data.get('data', {}).get('children', []):
                        post_data = post.get('data', {})
                        title = post_data.get('title', '')
                        content = post_data.get('selftext', '')[:500]
                        full_text = f"{title} {content}".lower()

                        # Only include if mentions our asset
                        if any(term in full_text for term in search_terms):
                            sentiment = self._analyze_sentiment(full_text)

                            posts.append(SocialPost(
                                title=title,
                                content=content,
                                source='reddit',
                                subreddit=subreddit,
                                author=post_data.get('author', 'unknown'),
                                score=post_data.get('score', 0),
                                comments=post_data.get('num_comments', 0),
                                sentiment=sentiment,
                                created=datetime.fromtimestamp(post_data.get('created_utc', 0)),
                                url=f"https://reddit.com{post_data.get('permalink', '')}",
                                is_dd='dd' in title.lower(),
                                mentions_ticker=True,
                                position_size=self._extract_position(full_text)
                            ))

            except Exception as e:
                logger.debug(f"Reddit hot posts error for r/{subreddit}: {e}")
                continue

        # Update circuit breaker state
        if request_failed and not posts:
            self.reddit_circuit.record_failure(error_msg)
        elif posts:
            self.reddit_circuit.record_success()
            logger.debug(f"Fetched {len(posts)} posts for {asset}")

        # Sort by engagement (score + comments)
        posts.sort(key=lambda x: x.score + x.comments * 2, reverse=True)

        return posts[:25]  # Return top 25

    def get_circuit_status(self) -> Dict[str, Any]:
        """Get Reddit API circuit breaker status"""
        return self.reddit_circuit.get_status()

    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of social post"""
        text_lower = text.lower()
        score = 0.0

        # Count bullish terms
        for term in self.bullish_terms:
            if term in text_lower:
                if term in ['🚀', 'moon', 'diamond hands', '💎🙌']:
                    score += 0.2  # Strong bullish slang
                else:
                    score += 0.1

        # Count bearish terms
        for term in self.bearish_terms:
            if term in text_lower:
                if term in ['rekt', 'rug', 'scam', 'ponzi']:
                    score -= 0.2  # Strong bearish slang
                else:
                    score -= 0.1

        return max(-1, min(1, score))

    def _extract_position(self, text: str) -> str:
        """Extract position size if mentioned"""
        # Look for dollar amounts
        dollar_pattern = r'\$[\d,]+(?:k|K|m|M)?'
        matches = re.findall(dollar_pattern, text)

        if matches:
            return matches[0]

        # Look for share counts
        share_pattern = r'(\d+)\s*(?:shares|contracts|coins)'
        matches = re.findall(share_pattern, text.lower())

        if matches:
            return f"{matches[0]} units"

        return ""

    def _calculate_fomo_level(self, posts: List[SocialPost]) -> float:
        """Calculate FOMO level from posts"""
        if not posts:
            return 0.0

        fomo_count = 0
        for post in posts:
            text = f"{post.title} {post.content}".lower()
            if any(term in text for term in self.fomo_terms):
                fomo_count += 1
            # Also check for excessive rocket emojis
            if text.count('🚀') >= 3 or 'moon' in text and post.score > 100:
                fomo_count += 1

        return min(1.0, fomo_count / max(len(posts), 1) * 2)

    def _calculate_fud_level(self, posts: List[SocialPost]) -> float:
        """Calculate FUD level from posts"""
        if not posts:
            return 0.0

        fud_count = 0
        for post in posts:
            text = f"{post.title} {post.content}".lower()
            if any(term in text for term in self.fud_terms):
                fud_count += 1
            # Check for panic selling mentions
            if ('sell' in text or 'sold' in text) and ('all' in text or 'everything' in text):
                fud_count += 1

        return min(1.0, fud_count / max(len(posts), 1) * 2)

    def _extract_narratives(self, posts: List[SocialPost]) -> List[str]:
        """Extract key narratives being discussed"""
        narratives = []

        # Count common themes
        theme_counts = {}
        themes = {
            'etf': ['etf', 'approval', 'blackrock', 'grayscale'],
            'halving': ['halving', 'halvening', 'supply shock'],
            'institutional': ['institution', 'whale', 'fund', 'corporate'],
            'regulation': ['sec', 'regulation', 'lawsuit', 'legal'],
            'technology': ['upgrade', 'update', 'merge', 'fork', 'layer 2'],
            'macro': ['fed', 'inflation', 'rates', 'recession'],
            'earnings': ['earnings', 'revenue', 'beat', 'miss', 'guidance'],
            'ai_hype': ['ai', 'artificial intelligence', 'chatgpt', 'nvidia']
        }

        for post in posts:
            text = f"{post.title} {post.content}".lower()
            for theme, keywords in themes.items():
                if any(kw in text for kw in keywords):
                    theme_counts[theme] = theme_counts.get(theme, 0) + 1

        # Return top themes
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        return [theme for theme, count in sorted_themes[:4] if count >= 2]

    def _detect_whale_activity(self, posts: List[SocialPost]) -> List[str]:
        """Detect mentions of large positions or whale activity"""
        whale_mentions = []

        for post in posts:
            text = f"{post.title} {post.content}"

            # Check for large position mentions
            if post.position_size:
                # Parse and check if it's a significant amount
                size = post.position_size.lower()
                if 'k' in size or 'm' in size or '$' in size:
                    whale_mentions.append(f"{post.author}: {post.position_size} position")

            # Check for whale-related keywords
            whale_keywords = ['whale', 'big money', 'institution', 'fund buying', 'accumulating']
            if any(kw in text.lower() for kw in whale_keywords):
                whale_mentions.append(f"Whale activity mentioned: {post.title[:60]}...")

        return whale_mentions[:5]

    def _calculate_viral_k_factor(self, posts: List[SocialPost]) -> ViralMetrics:
        """
        Calculate Viral K-Factor - measures information spread velocity

        K-Factor = ΔMentions_t / ΔMentions_t-1

        Bio-Check Entry Condition:
        - K > 1.2 (viral growth)
        - Acceleration > 0 (momentum increasing)

        Exit Condition:
        - K < 0.8 (viral death)
        """
        if not posts or len(posts) < 2:
            return ViralMetrics(
                k_factor=1.0,
                acceleration=0.0,
                mentions_t=len(posts),
                mentions_t_minus_1=len(posts),
                is_viral=False,
                viral_signal="STABLE"
            )

        # Sort posts by creation time
        sorted_posts = sorted(posts, key=lambda x: x.created)

        # Divide into time periods (current vs previous half)
        mid_point = len(sorted_posts) // 2

        # Count mentions and engagement in each period
        period_1_posts = sorted_posts[:mid_point]  # Older posts
        period_2_posts = sorted_posts[mid_point:]  # Newer posts

        # Weight by engagement (score + comments)
        mentions_t_minus_1 = sum(1 + (p.score / 100) + (p.comments / 10) for p in period_1_posts)
        mentions_t = sum(1 + (p.score / 100) + (p.comments / 10) for p in period_2_posts)

        # Avoid division by zero
        if mentions_t_minus_1 == 0:
            mentions_t_minus_1 = 0.1

        # Calculate K-Factor (growth rate)
        k_factor = mentions_t / mentions_t_minus_1

        # Calculate acceleration (would need historical K values, approximating here)
        # Using engagement growth as proxy for acceleration
        avg_engagement_old = sum(p.score + p.comments for p in period_1_posts) / max(len(period_1_posts), 1)
        avg_engagement_new = sum(p.score + p.comments for p in period_2_posts) / max(len(period_2_posts), 1)

        if avg_engagement_old > 0:
            acceleration = (avg_engagement_new - avg_engagement_old) / avg_engagement_old
        else:
            acceleration = 0.0

        # Determine viral status
        is_viral = k_factor > 1.2 and acceleration > 0

        # Classify the viral signal
        if k_factor > 1.5 and acceleration > 0.3:
            viral_signal = "EXPLOSIVE"  # Strong entry signal
        elif k_factor > 1.2 and acceleration > 0:
            viral_signal = "GROWING"  # Entry signal
        elif k_factor > 0.8:
            viral_signal = "STABLE"  # Neutral
        else:
            viral_signal = "DECLINING"  # Exit signal (viral death)

        return ViralMetrics(
            k_factor=round(k_factor, 3),
            acceleration=round(acceleration, 3),
            mentions_t=int(mentions_t),
            mentions_t_minus_1=int(mentions_t_minus_1),
            is_viral=is_viral,
            viral_signal=viral_signal
        )

    def analyze(self, asset: str, data: Dict[str, Any]) -> AgentOpinion:
        """Perform comprehensive social sentiment analysis"""

        posts = self.fetch_reddit_data(asset)

        if not posts:
            return AgentOpinion(
                agent_name=self.name,
                asset=asset,
                action=Action.HOLD,
                confidence=Confidence.LOW,
                reasoning="Unable to fetch social data. No community sentiment available.",
                key_factors=["No social data available"],
                suggested_hold_time="N/A",
                entry_timing="Wait for social data",
                warnings=["Social analysis unavailable"]
            )

        # Calculate metrics
        sentiments = [p.sentiment for p in posts]
        avg_sentiment = sum(sentiments) / len(sentiments)

        fomo_level = self._calculate_fomo_level(posts)
        fud_level = self._calculate_fud_level(posts)

        narratives = self._extract_narratives(posts)
        whale_activity = self._detect_whale_activity(posts)

        # Calculate Viral K-Factor (Bio-Check)
        viral_metrics = self._calculate_viral_k_factor(posts)

        # Trending score based on engagement
        total_engagement = sum(p.score + p.comments for p in posts)
        trending_score = min(1.0, total_engagement / 5000)

        # Contrarian signal - extreme sentiment often precedes reversals
        contrarian_signal = abs(avg_sentiment) > 0.6 or fomo_level > 0.7 or fud_level > 0.7

        # Count sentiment distribution
        bullish_posts = sum(1 for s in sentiments if s > 0.1)
        bearish_posts = sum(1 for s in sentiments if s < -0.1)

        # DD posts (Due Diligence) carry more weight
        dd_posts = [p for p in posts if p.is_dd]
        if dd_posts:
            dd_sentiment = sum(p.sentiment for p in dd_posts) / len(dd_posts)
            # Weight DD sentiment more heavily
            avg_sentiment = (avg_sentiment + dd_sentiment) / 2

        # Generate recommendation
        action, confidence = self._generate_recommendation(
            avg_sentiment, fomo_level, fud_level, contrarian_signal, trending_score
        )

        # Build key factors
        key_factors = []
        key_factors.append(f"Community sentiment: {avg_sentiment:+.2f} ({self._sentiment_label(avg_sentiment)})")
        key_factors.append(f"Post distribution: {bullish_posts} bullish, {bearish_posts} bearish")
        key_factors.append(f"FOMO level: {fomo_level:.0%} | FUD level: {fud_level:.0%}")
        key_factors.append(f"Trending score: {trending_score:.0%}")

        if narratives:
            key_factors.append(f"Key narratives: {', '.join(narratives)}")
        if whale_activity:
            key_factors.append(f"🐋 Whale activity detected")
        if contrarian_signal:
            key_factors.append("⚠️ CONTRARIAN SIGNAL: Extreme sentiment may precede reversal")

        # Add Viral K-Factor to key factors
        key_factors.append(f"📈 Viral K-Factor: {viral_metrics.k_factor:.2f} ({viral_metrics.viral_signal})")
        if viral_metrics.is_viral:
            key_factors.append("🔥 BIO-CHECK PASSED: Viral growth with positive acceleration")

        # Reasoning
        reasoning = self._build_reasoning(avg_sentiment, fomo_level, fud_level, contrarian_signal, narratives)

        # Warnings
        warnings = []
        if fomo_level > 0.6:
            warnings.append("High FOMO - be cautious of buying at the top")
        if fud_level > 0.6:
            warnings.append("High FUD - may be capitulation (potential bottom)")
        if contrarian_signal:
            warnings.append("Extreme sentiment historically precedes reversals")
        if trending_score > 0.8:
            warnings.append("Asset is highly discussed - increased volatility expected")

        # Hold time based on social momentum
        if fomo_level > 0.5:
            hold_time = "2-4 hours (high FOMO environment, quick reversal possible)"
        elif fud_level > 0.5:
            hold_time = "1-2 days (let panic selling exhaust)"
        else:
            hold_time = "8-16 hours (normal social conditions)"

        # Entry timing
        if action == Action.STRONG_BUY:
            entry_timing = "Strong community support - can enter now"
        elif action == Action.BUY:
            entry_timing = "Positive sentiment - enter on minor dips"
        elif action == Action.STRONG_SELL:
            entry_timing = "Strong negative sentiment - consider exiting"
        elif action == Action.SELL:
            entry_timing = "Sentiment weakening - reduce position"
        else:
            entry_timing = "Wait for clearer sentiment direction"

        return AgentOpinion(
            agent_name=self.name,
            asset=asset,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            suggested_hold_time=hold_time,
            entry_timing=entry_timing,
            indicators={
                "sentiment": avg_sentiment,
                "fomo_level": fomo_level,
                "fud_level": fud_level,
                "trending_score": trending_score,
                "contrarian_signal": contrarian_signal,
                "bullish_posts": bullish_posts,
                "bearish_posts": bearish_posts,
                "narratives": narratives,
                "whale_activity": whale_activity,
                "top_posts": [{"title": p.title, "score": p.score, "sentiment": p.sentiment}
                             for p in posts[:5]],
                # Viral K-Factor metrics (Bio-Check)
                "viral_k_factor": viral_metrics.k_factor,
                "viral_acceleration": viral_metrics.acceleration,
                "viral_signal": viral_metrics.viral_signal,
                "viral_is_active": viral_metrics.is_viral,
                "bio_check_passed": viral_metrics.is_viral  # Entry condition: K > 1.2 AND acceleration > 0
            },
            warnings=warnings
        )

    def _sentiment_label(self, score: float) -> str:
        if score > 0.4:
            return "Very Bullish 🚀"
        elif score > 0.15:
            return "Bullish"
        elif score < -0.4:
            return "Very Bearish 📉"
        elif score < -0.15:
            return "Bearish"
        else:
            return "Neutral"

    def _generate_recommendation(self, sentiment: float, fomo: float, fud: float,
                                  contrarian: bool, trending: float) -> Tuple[Action, Confidence]:
        """Generate recommendation from social analysis"""

        score = sentiment

        # Adjust for FOMO/FUD with contrarian logic
        if contrarian:
            # High FOMO = potential top, High FUD = potential bottom
            if fomo > 0.7:
                score -= 0.2  # Reduce bullish signal
            if fud > 0.7:
                score += 0.2  # Reduce bearish signal
        else:
            # Normal conditions - sentiment is valid signal
            if fomo > 0.5:
                score += 0.1
            if fud > 0.5:
                score -= 0.1

        # Trending increases conviction
        confidence_boost = trending > 0.5

        if score > 0.35:
            return Action.STRONG_BUY, Confidence.HIGH if confidence_boost else Confidence.MEDIUM
        elif score > 0.15:
            return Action.BUY, Confidence.MEDIUM if confidence_boost else Confidence.LOW
        elif score < -0.35:
            return Action.STRONG_SELL, Confidence.HIGH if confidence_boost else Confidence.MEDIUM
        elif score < -0.15:
            return Action.SELL, Confidence.MEDIUM if confidence_boost else Confidence.LOW
        else:
            return Action.HOLD, Confidence.LOW

    def _build_reasoning(self, sentiment: float, fomo: float, fud: float,
                         contrarian: bool, narratives: List[str]) -> str:
        """Build detailed reasoning"""

        reasoning = f"Social sentiment analysis shows {self._sentiment_label(sentiment)} community mood. "

        if fomo > 0.5:
            reasoning += f"FOMO levels are elevated ({fomo:.0%}), suggesting high excitement. "
        if fud > 0.5:
            reasoning += f"FUD levels are significant ({fud:.0%}), indicating fear in the market. "

        if contrarian:
            reasoning += "⚠️ CONTRARIAN ALERT: Extreme sentiment often precedes reversals. "
            if fomo > 0.6:
                reasoning += "High FOMO may indicate we're near a local top. "
            if fud > 0.6:
                reasoning += "Extreme FUD may indicate capitulation - potential buying opportunity. "

        if narratives:
            reasoning += f"Key community narratives: {', '.join(narratives)}. "

        return reasoning

    def get_teaching_content(self) -> Dict[str, Any]:
        """Educational content about social sentiment"""
        return {
            "name": self.name,
            "specialty": self.specialty,
            "lessons": [
                {
                    "title": "Understanding Social Sentiment",
                    "content": """
Social media sentiment can predict price moves - but it's a double-edged sword.

WHY SOCIAL SENTIMENT MATTERS:
• Retail traders heavily influenced by social media
• Viral posts can move markets
• FOMO/FUD create self-fulfilling prophecies
• Large communities = significant buying/selling pressure

KEY PLATFORMS:
1. Reddit (r/wallstreetbets, r/cryptocurrency)
   - Meme-driven, high-volume discussions
   - Can move small/mid-cap assets significantly

2. Twitter/X (Crypto Twitter, FinTwit)
   - Breaking news spreads fast
   - Influencer effects

3. Discord/Telegram
   - Private groups, insider sentiment
   - Often ahead of public sentiment

THE CONTRARIAN EDGE:
"Be fearful when others are greedy, greedy when others are fearful" - Buffett
Extreme sentiment often marks tops and bottoms.
"""
                },
                {
                    "title": "Decoding WSB and Crypto Slang",
                    "content": """
Understanding the language of social traders:

BULLISH TERMS:
🚀 Rocket emoji = expecting price to moon
💎🙌 Diamond hands = holding through volatility
HODL = Hold On for Dear Life
WAGMI = We're All Gonna Make It
LFG = Let's F***ing Go
BTD = Buy The Dip
Ape in = Buy aggressively without research

BEARISH TERMS:
📉 Chart down emoji
Paper hands = selling at first sign of trouble
Rekt = wrecked (lost money)
Rug/Rugpull = scam where devs abandon project
NGMI = Not Gonna Make It
Bagholder = stuck holding losing position

NEUTRAL/ANALYSIS:
DD = Due Diligence (research post)
TA = Technical Analysis
FA = Fundamental Analysis
NFA = Not Financial Advice
DYOR = Do Your Own Research
"""
                },
                {
                    "title": "FOMO and FUD: The Twin Emotions",
                    "content": """
FOMO (Fear Of Missing Out) and FUD (Fear, Uncertainty, Doubt) drive markets.

RECOGNIZING FOMO:
• "This is the last chance to buy!"
• "It's going to 100x from here"
• "Don't miss the train"
• Excessive rocket emojis 🚀🚀🚀
• Everyone talking about how much they're up

TRADING FOMO:
- FOMO often marks TOPS
- When everyone is buying, who's left to buy?
- Consider taking profits when FOMO is extreme

RECOGNIZING FUD:
• "It's going to zero"
• "Sell everything now"
• "This is a scam"
• Panic selling posts
• Everyone talking about how much they've lost

TRADING FUD:
- FUD often marks BOTTOMS
- When everyone has sold, who's left to sell?
- Consider buying when FUD is extreme

THE CONTRARIAN PLAYBOOK:
1. Track sentiment metrics
2. Wait for extremes (>70% one direction)
3. Prepare for reversal
4. Enter when sentiment starts to shift
"""
                },
                {
                    "title": "Smart Money vs Dumb Money",
                    "content": """
Learn to distinguish smart money signals from noise:

SMART MONEY SIGNALS:
• Large position disclosures by experienced traders
• Detailed DD with research and numbers
• Contrarian positions (buying when others fearful)
• Consistent track record posters
• Focus on fundamentals and long-term

DUMB MONEY SIGNALS:
• "Just bought my first Bitcoin at ATH!"
• Posting gains without thesis
• Chasing what's already up 500%
• Emotional reactions to price moves
• "To the moon! 🚀🚀🚀" without substance

HOW TO USE THIS:
1. Follow smart money, fade dumb money
2. When retail is euphoric, smart money often exits
3. When retail capitulates, smart money accumulates
4. Track sentiment shifts, not just levels

REMEMBER:
Social media is a tool, not a strategy. Use it to gauge sentiment,
but never trade solely based on what strangers say online.
"""
                }
            ]
        }
