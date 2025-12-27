"""
AI Agents Module

Complete AI trading infrastructure with:
- Market Intelligence Agent - Deep market analysis
- News & Event Analyzer - News and crisis detection
- Manipulation Detector - Avoid traps and scams
- Opportunity Sniper - Find high-probability trades
- Company Tracker - Fundamental analysis
- Trade Executor - Human-like execution
- Master Orchestrator - Coordinates everything

Usage:
    from ai_agents import MasterOrchestrator

    # Create and start the system
    orchestrator = MasterOrchestrator(initial_capital=100000)
    orchestrator.start(mode=SystemMode.PAPER_TRADING)

    # The AI handles everything, but YOU have control:
    orchestrator.add_to_watchlist('AAPL')
    orchestrator.set_risk_level(RiskLevel.MODERATE)
    orchestrator.enable_auto_trading(True)

    # Get status
    status = orchestrator.get_status()
"""

from .base import (
    BaseAgent,
    AgentState,
    Signal,
    SignalStrength,
    MarketSnapshot,
    MarketCondition,
    Memory,
    AgentOrchestrator,
    generate_unique_id,
    calculate_position_size
)

from .market_intelligence import (
    MarketIntelligenceAgent,
    MarketStructure,
    TrendDirection,
    MarketRegime
)

from .news_analyzer import (
    NewsAnalyzerAgent,
    NewsEvent,
    EventCategory,
    EventImpact,
    SentimentScore
)

from .manipulation_detector import (
    ManipulationDetectorAgent,
    ManipulationAlert,
    ManipulationType,
    AlertSeverity
)

from .opportunity_sniper import (
    OpportunitySniperAgent,
    Opportunity,
    OpportunityType,
    OpportunityQuality
)

from .company_tracker import (
    CompanyTrackerAgent,
    CompanyProfile,
    FinancialMetrics,
    FinancialHealth,
    GrowthProfile,
    ValuationLevel,
    MoatStrength
)

from .trade_executor import (
    AutonomousTradeExecutor,
    Order,
    OrderType,
    OrderStatus,
    Position,
    ExecutionStyle
)

from .orchestrator import (
    MasterOrchestrator,
    SystemMode,
    RiskLevel,
    TradingDecision,
    PerformanceMetrics
)

__all__ = [
    # Base
    'BaseAgent',
    'AgentState',
    'Signal',
    'SignalStrength',
    'MarketSnapshot',
    'MarketCondition',
    'Memory',
    'generate_unique_id',

    # Market Intelligence
    'MarketIntelligenceAgent',
    'MarketStructure',
    'TrendDirection',
    'MarketRegime',

    # News Analyzer
    'NewsAnalyzerAgent',
    'NewsEvent',
    'EventCategory',
    'EventImpact',
    'SentimentScore',

    # Manipulation Detector
    'ManipulationDetectorAgent',
    'ManipulationAlert',
    'ManipulationType',
    'AlertSeverity',

    # Opportunity Sniper
    'OpportunitySniperAgent',
    'Opportunity',
    'OpportunityType',
    'OpportunityQuality',

    # Company Tracker
    'CompanyTrackerAgent',
    'CompanyProfile',
    'FinancialMetrics',
    'FinancialHealth',
    'GrowthProfile',
    'ValuationLevel',
    'MoatStrength',

    # Trade Executor
    'AutonomousTradeExecutor',
    'Order',
    'OrderType',
    'OrderStatus',
    'Position',
    'ExecutionStyle',

    # Master Orchestrator
    'MasterOrchestrator',
    'SystemMode',
    'RiskLevel',
    'TradingDecision',
    'PerformanceMetrics',
]
