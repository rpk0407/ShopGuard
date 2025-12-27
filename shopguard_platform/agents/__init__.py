"""
ShopGuard Multi-Agent Trading System
=====================================
A sophisticated multi-agent architecture where specialized AI agents
collaborate to analyze markets, research opportunities, and make
informed trading decisions.

Agents:
- TechnicalAgent: Advanced chart analysis, indicators, patterns
- NewsAgent: Deep news research and sentiment analysis
- SocialAgent: Social media and community sentiment
- RiskAgent: Risk assessment and position sizing
- FundamentalAgent: On-chain/fundamental analysis
- Coordinator: Orchestrates all agents for consensus decisions
"""

from .base_agent import BaseAgent, AgentOpinion, Confidence
from .technical_agent import TechnicalAgent
from .news_agent import NewsAgent
from .social_agent import SocialAgent
from .risk_agent import RiskAgent
from .fundamental_agent import FundamentalAgent
from .coordinator import AgentCoordinator

__all__ = [
    'BaseAgent', 'AgentOpinion', 'Confidence',
    'TechnicalAgent', 'NewsAgent', 'SocialAgent',
    'RiskAgent', 'FundamentalAgent', 'AgentCoordinator'
]
