"""
Strategy Library

Pre-built trading strategies ready to use:
- Momentum strategies
- Mean reversion strategies
- Statistical arbitrage
- Machine learning strategies
- Multi-factor strategies

Usage:
    from strategies import MomentumStrategy

    strategy = MomentumStrategy(config)
    strategy.start()
"""

from .momentum import MomentumStrategy, DualMomentumStrategy
from .mean_reversion import MeanReversionStrategy, PairsTradingStrategy
from .ml_strategy import MLPredictionStrategy, EnsembleMLStrategy
from .statistical_arbitrage import StatisticalArbitrageStrategy
from .trend_following import TrendFollowingStrategy, BreakoutStrategy

__all__ = [
    'MomentumStrategy',
    'DualMomentumStrategy',
    'MeanReversionStrategy',
    'PairsTradingStrategy',
    'MLPredictionStrategy',
    'EnsembleMLStrategy',
    'StatisticalArbitrageStrategy',
    'TrendFollowingStrategy',
    'BreakoutStrategy'
]
