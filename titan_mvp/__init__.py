"""
TQO MVP - Titan Quantitative Opportunities

A 2-factor systematic trading system:
1. CVD Divergence (Order Flow Analysis)
2. Entropy Filter (Regime Detection)

With ATR-based dynamic risk management.

Architecture:
    ┌─────────────────────────────────────────┐
    │           TITAN MVP ARCHITECTURE         │
    └─────────────────────────────────────────┘

    Data Layer (data/)
        └─> Trades, Candles, OrderBook

    Signal Layer (signals/)
        ├─> CVD Engine (Divergence Detection)
        ├─> Entropy Filter (Regime Classification)
        └─> Signal Combiner (Decision Gate)

    Risk Layer (risk/)
        ├─> ATR Calculator
        ├─> Position Sizer
        └─> Risk Manager

    Backtest Layer (backtest/)
        ├─> Metrics Calculator
        └─> Backtest Engine

Usage:
    from titan_mvp.signals import SignalCombiner
    from titan_mvp.risk import RiskManager
    from titan_mvp.backtest import BacktestEngine

    combiner = SignalCombiner()
    risk = RiskManager(initial_capital=10000)
    engine = BacktestEngine()

    result = engine.run(candles)
    print(result.metrics.summary())
"""

__version__ = "0.1.0"
__author__ = "TQO Team"

from .config import Settings, get_settings
from .signals import (
    CVDEngine,
    EntropyFilter,
    SignalCombiner,
    CombinedSignal,
    TradeDirection,
)
from .risk import (
    ATRCalculator,
    PositionSizer,
    RiskManager,
)
from .backtest import (
    BacktestEngine,
    BacktestMetrics,
)

__all__ = [
    # Config
    'Settings',
    'get_settings',
    # Signals
    'CVDEngine',
    'EntropyFilter',
    'SignalCombiner',
    'CombinedSignal',
    'TradeDirection',
    # Risk
    'ATRCalculator',
    'PositionSizer',
    'RiskManager',
    # Backtest
    'BacktestEngine',
    'BacktestMetrics',
]
