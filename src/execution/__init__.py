"""
Advanced Execution Module

Execution quality is a major source of alpha decay.
This module provides:
- Smart Order Routing (SOR)
- Transaction Cost Analysis (TCA)
- Market Impact Models
- Execution Algorithms (TWAP, VWAP, Implementation Shortfall)
"""

from .smart_router import SmartOrderRouter, VenueSelection, RoutingStrategy
from .market_impact import MarketImpactModel, AlmgrenChriss, TransientImpact
from .algorithms import TWAPExecutor, VWAPExecutor, ImplementationShortfall
from .tca import TransactionCostAnalyzer, ExecutionQuality

__all__ = [
    'SmartOrderRouter',
    'VenueSelection',
    'RoutingStrategy',
    'MarketImpactModel',
    'AlmgrenChriss',
    'TransientImpact',
    'TWAPExecutor',
    'VWAPExecutor',
    'ImplementationShortfall',
    'TransactionCostAnalyzer',
    'ExecutionQuality',
]
