"""
Sentiment Analysis for Financial Markets

Extracts sentiment signals from:
- News articles
- Social media (Twitter, Reddit, StockTwits)
- Earnings calls and SEC filings
- Analyst reports

Research shows:
- Sentiment has short-term predictive power (hours to days)
- Extreme sentiment often precedes reversals
- Sentiment divergence from price is informative
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import re


class SentimentSource(Enum):
    """Sources of sentiment data."""
    NEWS = "news"
    TWITTER = "twitter"
    REDDIT = "reddit"
    STOCKTWITS = "stocktwits"
    SEC_FILINGS = "sec_filings"
    EARNINGS_CALLS = "earnings_calls"
    ANALYST_REPORTS = "analyst_reports"


@dataclass
class SentimentScore:
    """Individual sentiment measurement."""
    source: SentimentSource
    symbol: str
    score: float  # -1 (bearish) to +1 (bullish)
    magnitude: float  # Strength of sentiment
    confidence: float  # Model confidence
    timestamp: datetime
    text_snippet: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def weighted_score(self) -> float:
        """Score weighted by magnitude and confidence."""
        return self.score * self.magnitude * self.confidence


@dataclass
class AggregateSentiment:
    """Aggregated sentiment across sources."""
    symbol: str
    overall_score: float
    bullish_ratio: float
    bearish_ratio: float
    neutral_ratio: float
    volume: int  # Number of mentions
    momentum: float  # Change in sentiment
    dispersion: float  # Disagreement level
    sources: Dict[SentimentSource, float]
    timestamp: datetime


class SentimentAnalyzer:
    """
    Multi-source sentiment analysis engine.

    Combines sentiment from multiple sources with
    source-specific weights based on historical accuracy.
    """

    # Default source weights (calibrated from research)
    DEFAULT_WEIGHTS = {
        SentimentSource.NEWS: 0.25,
        SentimentSource.TWITTER: 0.15,
        SentimentSource.REDDIT: 0.10,
        SentimentSource.STOCKTWITS: 0.15,
        SentimentSource.SEC_FILINGS: 0.15,
        SentimentSource.EARNINGS_CALLS: 0.10,
        SentimentSource.ANALYST_REPORTS: 0.10,
    }

    def __init__(
        self,
        source_weights: Dict[SentimentSource, float] = None,
        decay_halflife_hours: float = 24.0,
        history_days: int = 30
    ):
        """
        Initialize sentiment analyzer.

        Args:
            source_weights: Weight for each sentiment source
            decay_halflife_hours: Half-life for time decay
            history_days: Days of history to maintain
        """
        self.source_weights = source_weights or self.DEFAULT_WEIGHTS
        self.decay_halflife = decay_halflife_hours
        self.history_days = history_days

        # Sentiment history by symbol
        self.sentiment_history: Dict[str, deque] = {}

        # Lexicons for rule-based sentiment
        self._load_financial_lexicons()

    def _load_financial_lexicons(self):
        """Load financial-specific sentiment lexicons."""
        # Positive financial terms
        self.positive_terms = {
            'beat', 'beats', 'exceeded', 'outperform', 'upgrade',
            'bullish', 'rally', 'surge', 'soar', 'jump', 'gain',
            'profit', 'growth', 'strong', 'positive', 'optimistic',
            'momentum', 'breakout', 'recovery', 'expansion', 'record',
            'dividend', 'buyback', 'acquisition', 'innovation', 'partnership'
        }

        # Negative financial terms
        self.negative_terms = {
            'miss', 'missed', 'below', 'underperform', 'downgrade',
            'bearish', 'crash', 'plunge', 'tumble', 'fall', 'loss',
            'decline', 'weak', 'negative', 'pessimistic', 'risk',
            'breakdown', 'recession', 'contraction', 'warning', 'layoff',
            'lawsuit', 'investigation', 'fraud', 'default', 'bankruptcy'
        }

        # Intensifiers
        self.intensifiers = {
            'very': 1.5, 'extremely': 2.0, 'significantly': 1.5,
            'slightly': 0.5, 'somewhat': 0.7, 'massive': 2.0,
            'huge': 1.8, 'major': 1.5, 'minor': 0.5
        }

        # Negators
        self.negators = {'not', 'no', 'never', 'neither', 'hardly', 'barely'}

    def analyze_text(self, text: str, source: SentimentSource) -> SentimentScore:
        """
        Analyze sentiment of a single text.

        Uses a combination of:
        1. Lexicon-based analysis
        2. Rule-based patterns
        3. Context awareness
        """
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)

        positive_count = 0
        negative_count = 0
        intensity = 1.0

        # Sliding window for negation detection
        negation_window = 3
        negated = [False] * len(words)

        for i, word in enumerate(words):
            # Check for negators
            if word in self.negators:
                for j in range(i + 1, min(i + negation_window + 1, len(words))):
                    negated[j] = True

            # Check for intensifiers
            if word in self.intensifiers:
                intensity = self.intensifiers[word]

        # Count sentiment words
        for i, word in enumerate(words):
            multiplier = -1 if negated[i] else 1

            if word in self.positive_terms:
                positive_count += intensity * multiplier
            elif word in self.negative_terms:
                negative_count += intensity * multiplier

        # Calculate score
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            magnitude = 0.0
        else:
            score = (positive_count - negative_count) / (positive_count + negative_count + 1)
            magnitude = min(1.0, (positive_count + negative_count) / 10)

        # Confidence based on text length and sentiment clarity
        word_count = len(words)
        confidence = min(1.0, word_count / 50) * (0.5 + 0.5 * abs(score))

        return SentimentScore(
            source=source,
            symbol="",  # To be set by caller
            score=np.clip(score, -1, 1),
            magnitude=magnitude,
            confidence=confidence,
            timestamp=datetime.now(),
            text_snippet=text[:200] if len(text) > 200 else text
        )

    def add_sentiment(self, sentiment: SentimentScore):
        """Add a sentiment score to history."""
        symbol = sentiment.symbol

        if symbol not in self.sentiment_history:
            max_items = self.history_days * 1000  # ~1000 per day
            self.sentiment_history[symbol] = deque(maxlen=max_items)

        self.sentiment_history[symbol].append(sentiment)

    def get_aggregate_sentiment(
        self,
        symbol: str,
        lookback_hours: float = 24.0
    ) -> Optional[AggregateSentiment]:
        """
        Get aggregated sentiment for a symbol.

        Applies time decay and source weighting.
        """
        if symbol not in self.sentiment_history:
            return None

        now = datetime.now()
        cutoff = now - timedelta(hours=lookback_hours)
        decay_lambda = np.log(2) / self.decay_halflife

        # Collect recent sentiment scores
        scores_by_source: Dict[SentimentSource, List[float]] = {
            source: [] for source in SentimentSource
        }

        all_weighted_scores = []
        bullish = 0
        bearish = 0
        neutral = 0

        for sentiment in self.sentiment_history[symbol]:
            if sentiment.timestamp < cutoff:
                continue

            # Time decay
            hours_ago = (now - sentiment.timestamp).total_seconds() / 3600
            decay = np.exp(-decay_lambda * hours_ago)

            weighted = sentiment.weighted_score * decay
            scores_by_source[sentiment.source].append(weighted)
            all_weighted_scores.append(weighted)

            # Categorize
            if sentiment.score > 0.1:
                bullish += 1
            elif sentiment.score < -0.1:
                bearish += 1
            else:
                neutral += 1

        if not all_weighted_scores:
            return None

        # Calculate source averages
        source_scores = {}
        for source, scores in scores_by_source.items():
            if scores:
                source_scores[source] = np.mean(scores)

        # Calculate weighted overall score
        overall = 0.0
        total_weight = 0.0
        for source, score in source_scores.items():
            weight = self.source_weights.get(source, 0.1)
            overall += score * weight
            total_weight += weight

        if total_weight > 0:
            overall /= total_weight

        # Calculate ratios
        total_count = bullish + bearish + neutral

        # Calculate momentum (change in sentiment)
        recent_cutoff = now - timedelta(hours=lookback_hours / 4)
        recent_scores = [s for s in all_weighted_scores[-100:]]  # Recent subset
        older_scores = [s for s in all_weighted_scores[:-100]] if len(all_weighted_scores) > 100 else []

        if recent_scores and older_scores:
            momentum = np.mean(recent_scores) - np.mean(older_scores)
        else:
            momentum = 0.0

        return AggregateSentiment(
            symbol=symbol,
            overall_score=overall,
            bullish_ratio=bullish / total_count if total_count > 0 else 0,
            bearish_ratio=bearish / total_count if total_count > 0 else 0,
            neutral_ratio=neutral / total_count if total_count > 0 else 0,
            volume=total_count,
            momentum=momentum,
            dispersion=np.std(all_weighted_scores) if len(all_weighted_scores) > 1 else 0,
            sources=source_scores,
            timestamp=now
        )

    def get_sentiment_signal(
        self,
        symbol: str,
        lookback_hours: float = 24.0
    ) -> Tuple[float, float]:
        """
        Get trading signal from sentiment.

        Returns:
            (signal, confidence) where signal in [-1, 1]
        """
        agg = self.get_aggregate_sentiment(symbol, lookback_hours)

        if agg is None:
            return 0.0, 0.0

        # Base signal from overall sentiment
        signal = agg.overall_score

        # Adjust for momentum (sentiment acceleration)
        signal += 0.3 * agg.momentum

        # Confidence based on volume and agreement
        volume_factor = min(1.0, agg.volume / 100)  # Need ~100 data points
        agreement_factor = 1 - agg.dispersion  # High dispersion = low confidence

        confidence = volume_factor * max(0, agreement_factor)

        return np.clip(signal, -1, 1), confidence


class NewsSentiment:
    """
    News-specific sentiment analysis.

    Handles:
    - Breaking news detection
    - Headline vs body sentiment
    - Source credibility weighting
    """

    # News source credibility (higher = more reliable)
    SOURCE_CREDIBILITY = {
        'reuters': 0.95,
        'bloomberg': 0.95,
        'wsj': 0.90,
        'ft': 0.90,
        'cnbc': 0.75,
        'seeking_alpha': 0.60,
        'motley_fool': 0.50,
        'unknown': 0.40
    }

    def __init__(self, base_analyzer: SentimentAnalyzer = None):
        self.analyzer = base_analyzer or SentimentAnalyzer()

    def analyze_article(
        self,
        headline: str,
        body: str,
        source: str,
        symbols: List[str],
        published_at: datetime
    ) -> List[SentimentScore]:
        """
        Analyze a news article.

        Headlines are weighted more heavily as they contain
        the most important information.
        """
        # Analyze headline (more weight)
        headline_sentiment = self.analyzer.analyze_text(
            headline, SentimentSource.NEWS
        )

        # Analyze body
        body_sentiment = self.analyzer.analyze_text(
            body, SentimentSource.NEWS
        )

        # Combined score (70% headline, 30% body)
        combined_score = 0.7 * headline_sentiment.score + 0.3 * body_sentiment.score
        combined_magnitude = 0.7 * headline_sentiment.magnitude + 0.3 * body_sentiment.magnitude

        # Adjust confidence by source credibility
        credibility = self.SOURCE_CREDIBILITY.get(source.lower(), 0.4)
        combined_confidence = headline_sentiment.confidence * credibility

        # Create sentiment scores for each mentioned symbol
        results = []
        for symbol in symbols:
            results.append(SentimentScore(
                source=SentimentSource.NEWS,
                symbol=symbol,
                score=combined_score,
                magnitude=combined_magnitude,
                confidence=combined_confidence,
                timestamp=published_at,
                text_snippet=headline,
                metadata={'source': source, 'has_body': len(body) > 0}
            ))

        return results

    def detect_breaking_news(
        self,
        symbol: str,
        current_volume: int,
        historical_volume: float
    ) -> bool:
        """
        Detect if there's breaking news based on mention volume spike.

        Breaking news often precedes significant price moves.
        """
        if historical_volume == 0:
            return current_volume > 10

        volume_ratio = current_volume / historical_volume
        return volume_ratio > 3.0  # 3x normal volume


class SocialMediaSentiment:
    """
    Social media sentiment analysis.

    Special handling for:
    - Meme stocks and retail sentiment
    - Influencer impact
    - Bot detection
    - Echo chambers
    """

    def __init__(self, base_analyzer: SentimentAnalyzer = None):
        self.analyzer = base_analyzer or SentimentAnalyzer()

        # Track user influence scores
        self.user_influence: Dict[str, float] = {}

        # Known bot patterns
        self.bot_patterns = [
            r'^\$[A-Z]{1,5}\s+to\s+the\s+moon',
            r'guaranteed\s+\d+x',
            r'not\s+financial\s+advice.*buy',
        ]

    def analyze_post(
        self,
        text: str,
        platform: str,
        user_id: str,
        followers: int,
        engagement: int,
        symbols: List[str],
        posted_at: datetime
    ) -> List[SentimentScore]:
        """
        Analyze a social media post.

        Accounts for:
        - User influence (followers, historical accuracy)
        - Engagement (likes, retweets, comments)
        - Platform-specific patterns
        """
        # Check for bot patterns
        if self._is_likely_bot(text, user_id):
            return []  # Ignore likely bot posts

        # Map platform to source
        source_map = {
            'twitter': SentimentSource.TWITTER,
            'reddit': SentimentSource.REDDIT,
            'stocktwits': SentimentSource.STOCKTWITS,
        }
        source = source_map.get(platform.lower(), SentimentSource.TWITTER)

        # Base sentiment
        base_sentiment = self.analyzer.analyze_text(text, source)

        # Calculate influence multiplier
        influence = self._calculate_influence(user_id, followers, engagement)

        results = []
        for symbol in symbols:
            results.append(SentimentScore(
                source=source,
                symbol=symbol,
                score=base_sentiment.score,
                magnitude=base_sentiment.magnitude * influence,
                confidence=base_sentiment.confidence * min(1.0, influence),
                timestamp=posted_at,
                text_snippet=text[:140],
                metadata={
                    'platform': platform,
                    'user_id': user_id,
                    'followers': followers,
                    'engagement': engagement
                }
            ))

        return results

    def _is_likely_bot(self, text: str, user_id: str) -> bool:
        """Detect likely bot posts."""
        text_lower = text.lower()

        for pattern in self.bot_patterns:
            if re.search(pattern, text_lower):
                return True

        return False

    def _calculate_influence(
        self,
        user_id: str,
        followers: int,
        engagement: int
    ) -> float:
        """
        Calculate user influence score.

        Combines:
        - Follower count (log scale)
        - Engagement rate
        - Historical accuracy (if tracked)
        """
        # Log follower score (diminishing returns)
        follower_score = np.log10(max(1, followers)) / 6  # Normalize to ~1 for 1M followers

        # Engagement rate
        engagement_rate = engagement / max(1, followers)
        engagement_score = min(1.0, engagement_rate * 10)  # 10% engagement = max

        # Historical accuracy
        historical_score = self.user_influence.get(user_id, 0.5)

        # Combine
        influence = 0.3 * follower_score + 0.3 * engagement_score + 0.4 * historical_score

        return np.clip(influence, 0.1, 2.0)

    def detect_retail_frenzy(
        self,
        symbol: str,
        mention_volume: int,
        historical_volume: float,
        sentiment_score: float
    ) -> Tuple[bool, float]:
        """
        Detect retail trading frenzy (meme stock behavior).

        Returns:
            (is_frenzy, intensity)
        """
        if historical_volume == 0:
            return False, 0.0

        volume_ratio = mention_volume / historical_volume

        # Frenzy detection criteria:
        # 1. Volume spike > 5x normal
        # 2. Strong positive sentiment (> 0.5)
        # 3. High sentiment agreement

        is_frenzy = (
            volume_ratio > 5.0 and
            sentiment_score > 0.5
        )

        intensity = volume_ratio / 10.0 * sentiment_score if is_frenzy else 0.0

        return is_frenzy, min(1.0, intensity)
