"""
AI/ML Architecture for Quantitative Trading

This module implements:
- Neural network architectures (LSTM, Transformer, Attention)
- Reinforcement learning agents (PPO, SAC)
- Feature engineering pipelines
- Model ensemble methods

HONEST CAVEATS:
1. ML models overfit. Always use proper cross-validation with purging/embargo.
2. Financial data is non-stationary. Models degrade over time.
3. Transaction costs eat alpha. Include realistic costs in training.
4. Markets are adversarial. Your alpha attracts competition.
"""

from .networks.temporal import TemporalFusionNetwork, LSTMEncoder, TransformerEncoder
from .agents.ppo_agent import TradingPPOAgent
from .features.engineering import FeatureEngineer

__all__ = [
    "TemporalFusionNetwork",
    "LSTMEncoder",
    "TransformerEncoder",
    "TradingPPOAgent",
    "FeatureEngineer",
]
