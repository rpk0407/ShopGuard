"""
Portfolio Optimization and Construction

This module implements:
- Mean-Variance (Markowitz) optimization
- Risk Parity / Equal Risk Contribution
- Black-Litterman with views
- Factor-based portfolio construction
- Robust optimization (handling estimation error)
- Transaction cost aware rebalancing
"""

from .optimization import (
    MeanVarianceOptimizer,
    RiskParityOptimizer,
    BlackLittermanModel,
    MinimumVariancePortfolio,
    MaxSharpePortfolio
)
from .construction import (
    PortfolioConstructor,
    FactorPortfolio,
    RebalanceOptimizer
)
from .risk import (
    PortfolioRiskAnalyzer,
    FactorRiskDecomposition,
    StressTestEngine
)

__all__ = [
    "MeanVarianceOptimizer",
    "RiskParityOptimizer",
    "BlackLittermanModel",
    "MinimumVariancePortfolio",
    "MaxSharpePortfolio",
    "PortfolioConstructor",
    "FactorPortfolio",
    "RebalanceOptimizer",
    "PortfolioRiskAnalyzer",
    "FactorRiskDecomposition",
    "StressTestEngine",
]
