"""
Core Mathematical Models for Quantitative Trading Research

This module implements foundational stochastic and statistical models:
- Geometric Brownian Motion (GBM) for price simulation
- Kelly Criterion for optimal position sizing
- Monte Carlo engines for scenario analysis
- Bayesian inference for parameter estimation
"""

from .stochastic import GeometricBrownianMotion, OrnsteinUhlenbeck, JumpDiffusion
from .position_sizing import KellyCriterion, FractionalKelly
from .monte_carlo import MonteCarloEngine, ScenarioAnalyzer
from .bayesian import BayesianParameterEstimator

__all__ = [
    "GeometricBrownianMotion",
    "OrnsteinUhlenbeck",
    "JumpDiffusion",
    "KellyCriterion",
    "FractionalKelly",
    "MonteCarloEngine",
    "ScenarioAnalyzer",
    "BayesianParameterEstimator",
]
