"""
External Alpha Sources - Smart Money Edition
=============================================
Contrarian signals based on smart money vs retail divergence.

Core Philosophy:
    "Don't be exit liquidity for smart money."

Modules:
- smart_money: Whale/institutional tracking vs retail
- sentiment_extremes: Fear & Greed contrarian signals
- liquidity_trap: Detect when retail is being used as exit liquidity
- news_filter: Filter noise from real market-moving news
- aggregator: Combines all signals with smart money weighting

Data Gathering (for sentiment detection):
- polymarket: Prediction market signals
- social_sentiment: Twitter/Reddit sentiment
- news_sentiment: News sentiment

Signal Priority:
1. Smart Money Flow (40%) - What whales are doing
2. Liquidity Trap (25%) - Avoid being exit liquidity
3. Sentiment Extremes (20%) - Contrarian F&G signals
4. Filtered News (10%) - Only real market-moving events
5. Prediction Markets (5%) - Probability-based signals
"""

# Smart Money Components (Primary)
from .smart_money import SmartMoneyTracker, SmartMoneySignal, MoneyType, FlowDirection
from .sentiment_extremes import (
    SentimentExtremesDetector,
    ContrarianSignal,
    FearGreedState,
    SentimentZone,
    SignalStrength
)
from .liquidity_trap import (
    LiquidityTrapDetector,
    TrapSignal,
    TrapType,
    TrapSeverity,
    LiquidityState
)
from .news_filter import (
    NewsImpactFilter,
    FilteredNews,
    NewsImpact,
    NewsAction,
    NewsFilterConfig
)
from .whale_manipulation import (
    WhaleManipulationDetector,
    ManipulationSignal,
    ManipulationType,
    ConfidenceLevel,
    WhaleActivity
)
from .signal_quality import (
    SignalQualityAnalyzer,
    QualityScore,
    SignalQuality,
    SignalInput
)

# Data Gathering Components (Secondary)
from .polymarket import PolymarketScanner, PredictionSignal, MarketCategory
from .social_sentiment import SocialSentimentAnalyzer, SentimentSignal, Platform
from .news_sentiment import NewsSentimentScanner, NewsSignal, NewsSource

# Aggregator (Main Entry Point)
from .aggregator import (
    SignalAggregator,
    AggregatedSignal,
    ExternalSignalConfig,
    SignalMode
)

__all__ = [
    # Smart Money (Primary)
    'SmartMoneyTracker',
    'SmartMoneySignal',
    'MoneyType',
    'FlowDirection',

    # Sentiment Extremes
    'SentimentExtremesDetector',
    'ContrarianSignal',
    'FearGreedState',
    'SentimentZone',
    'SignalStrength',

    # Liquidity Trap Detection
    'LiquidityTrapDetector',
    'TrapSignal',
    'TrapType',
    'TrapSeverity',
    'LiquidityState',

    # News Filtering
    'NewsImpactFilter',
    'FilteredNews',
    'NewsImpact',
    'NewsAction',
    'NewsFilterConfig',

    # Whale Manipulation Detection
    'WhaleManipulationDetector',
    'ManipulationSignal',
    'ManipulationType',
    'ConfidenceLevel',
    'WhaleActivity',

    # Signal Quality Analysis
    'SignalQualityAnalyzer',
    'QualityScore',
    'SignalQuality',
    'SignalInput',

    # Data Gathering
    'PolymarketScanner',
    'PredictionSignal',
    'MarketCategory',
    'SocialSentimentAnalyzer',
    'SentimentSignal',
    'Platform',
    'NewsSentimentScanner',
    'NewsSignal',
    'NewsSource',

    # Main Aggregator
    'SignalAggregator',
    'AggregatedSignal',
    'ExternalSignalConfig',
    'SignalMode',
]
