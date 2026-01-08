"""
External Alpha Sources
======================
Alternative data signals for enhanced trading decisions.

Sources:
- Prediction Markets (Polymarket) - Market-implied probabilities
- Social Sentiment (Twitter/Reddit) - Crowd sentiment analysis
- News Sentiment - Breaking news impact assessment

Integration:
- All signals feed into TitanBrain via unified interface
- Each source provides confidence-weighted signals
- Signals are normalized to [-1, 1] range (bearish to bullish)
"""

from .polymarket import PolymarketScanner, PredictionSignal, MarketCategory
from .social_sentiment import SocialSentimentAnalyzer, SentimentSignal, Platform
from .news_sentiment import NewsSentimentScanner, NewsSignal, NewsSource
from .aggregator import SignalAggregator, AggregatedSignal, ExternalSignalConfig

__all__ = [
    # Polymarket
    'PolymarketScanner',
    'PredictionSignal',
    'MarketCategory',
    # Social Sentiment
    'SocialSentimentAnalyzer',
    'SentimentSignal',
    'Platform',
    # News Sentiment
    'NewsSentimentScanner',
    'NewsSignal',
    'NewsSource',
    # Aggregator
    'SignalAggregator',
    'AggregatedSignal',
    'ExternalSignalConfig',
]
