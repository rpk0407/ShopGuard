"""
🤖 FULL AUTO TRADER
====================
Complete automated trading system with:
- Real broker connections (Alpaca for stocks, Binance for crypto)
- News analysis from multiple sources
- Social media sentiment (Reddit, Twitter)
- AI-powered decision making
- Automatic execution with SL/TP
"""

from .config import Config
from .brokers import AlpacaBroker, PaperBroker
from .news import NewsAnalyzer
from .sentiment import SocialSentiment
from .brain import TradingBrain
from .executor import AutoExecutor

__version__ = "1.0.0"
