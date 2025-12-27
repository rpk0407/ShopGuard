"""
API Layer and Strategy Framework

Provides:
- REST API for system control
- Strategy base classes
- Event-driven architecture
- System orchestration
"""

from .strategy import Strategy, StrategyContext, SignalGenerator
from .events import Event, EventBus, EventHandler
from .engine import TradingEngine, EngineConfig

__all__ = [
    'Strategy',
    'StrategyContext',
    'SignalGenerator',
    'Event',
    'EventBus',
    'EventHandler',
    'TradingEngine',
    'EngineConfig',
]
