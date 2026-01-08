"""
Signals Module
==============
Signal generation for trading decisions.

Submodules:
- external: External alpha sources (prediction markets, social, news)
"""

from .external import (
    # Polymarket
    PolymarketScanner,
    PredictionSignal,
    MarketCategory,
    # Social
    SocialSentimentAnalyzer,
    SentimentSignal,
    Platform,
    # News
    NewsSentimentScanner,
    NewsSignal,
    NewsSource,
    # Aggregator
    SignalAggregator,
    AggregatedSignal,
    ExternalSignalConfig,
)

__all__ = [
    'PolymarketScanner',
    'PredictionSignal',
    'MarketCategory',
    'SocialSentimentAnalyzer',
    'SentimentSignal',
    'Platform',
    'NewsSentimentScanner',
    'NewsSignal',
    'NewsSource',
    'SignalAggregator',
    'AggregatedSignal',
    'ExternalSignalConfig',
]
