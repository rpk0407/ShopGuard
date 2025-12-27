"""
Alternative Data Processing Module

Non-traditional data sources for alpha generation:
- News and social media sentiment
- Macroeconomic indicators
- Satellite imagery features
- Web scraping signals
"""

from .sentiment import SentimentAnalyzer, NewsSentiment, SocialMediaSentiment
from .nlp import FinancialNLP, EntityExtractor, EventDetector
from .macro import MacroIndicators, EconomicCalendar, CrossAssetSignals

__all__ = [
    'SentimentAnalyzer',
    'NewsSentiment',
    'SocialMediaSentiment',
    'FinancialNLP',
    'EntityExtractor',
    'EventDetector',
    'MacroIndicators',
    'EconomicCalendar',
    'CrossAssetSignals',
]
