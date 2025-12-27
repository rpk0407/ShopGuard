"""
Live Trading Bot - Real automated trading system
"""
from .config import TradingConfig, STOCK_WATCHLIST, CRYPTO_WATCHLIST
from .price_fetcher import PriceFetcher
from .strategies import Strategy, MomentumStrategy, MeanReversionStrategy, RSIStrategy
from .portfolio import Portfolio, Position
from .signals import Signal, SignalType

__all__ = [
    "TradingConfig",
    "STOCK_WATCHLIST",
    "CRYPTO_WATCHLIST",
    "PriceFetcher",
    "Strategy",
    "MomentumStrategy",
    "MeanReversionStrategy",
    "RSIStrategy",
    "Portfolio",
    "Position",
    "Signal",
    "SignalType"
]
