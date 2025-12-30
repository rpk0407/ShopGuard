"""
TITAN ECOSYSTEM - Complete Trading Infrastructure
=================================================

The Biological Trading Organism:

┌─────────────────────────────────────────────────────────────────────────┐
│                           TITAN ECOSYSTEM                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────┐     THE NUCLEUS (Decision Center)                    │
│   │  TITAN BRAIN │     - Three-pillar convergence                       │
│   │   (nucleus)  │     - Signal generation                              │
│   └──────┬───────┘     - Dynamic thresholds from Darwin                 │
│          │                                                               │
│   ┌──────┴───────┐     THE DNA (Evolution)                              │
│   │    DARWIN    │     - Genetic algorithm                              │
│   │    (dna)     │     - Population of 50 mutants                       │
│   └──────────────┘     - Natural selection                              │
│                                                                          │
│   ┌──────────────┐     THE MEMBRANE (Protection)                        │
│   │ RISK MANAGER │     - Position sizing (Kelly)                        │
│   │  (membrane)  │     - Drawdown protection                            │
│   └──────────────┘     - Circuit breakers                               │
│                                                                          │
│   ┌──────────────┐     THE MITOCHONDRIA (Energy/Execution)              │
│   │   EXECUTOR   │     - Order management                               │
│   │(mitochondria)│     - Slippage simulation                            │
│   └──────────────┘     - Fill tracking                                  │
│                                                                          │
│   ┌──────────────┐     THE RECEPTORS (Sensing)                          │
│   │   REGIME     │     - Market regime detection                        │
│   │ (receptors)  │     - Volatility regimes                             │
│   └──────────────┘     - Correlation matrix                             │
│                                                                          │
│   ┌──────────────┐     THE MEMORY (Learning)                            │
│   │   JOURNAL    │     - Trade logging                                  │
│   │   (memory)   │     - Pattern recognition                            │
│   └──────────────┘     - Performance analytics                          │
│                                                                          │
│   ┌──────────────┐     THE NERVOUS SYSTEM (Communication)               │
│   │   ALERTS     │     - Signal propagation                             │
│   │  (nervous)   │     - Event notifications                            │
│   └──────────────┘     - Cross-component messaging                      │
│                                                                          │
│   ┌──────────────┐     THE ENVIRONMENT (Simulation)                     │
│   │   MATRIX     │     - Synthetic market data                          │
│   │(environment) │     - Perfect storm events                           │
│   └──────────────┘     - GBM price dynamics                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

Data Flow:
    MATRIX → RECEPTORS → TITAN BRAIN → RISK MANAGER → EXECUTOR → JOURNAL
       ↑                      ↑              ↓
       └──────────────────────┴──── DARWIN (evolving) ────→ ALERTS

"""

# Re-export all ecosystem components
from .titan_brain import TitanBrain, EvolvingBrain, BrainConfig, TradingSignal, SignalType
from .fast_math import FastMath, NUMBA_AVAILABLE
from .risk_manager import RiskManager, RiskConfig, PositionSizer
from .executor import OrderExecutor, Order, OrderStatus, Fill
from .regime import RegimeDetector, MarketRegime, VolatilityState
from .journal import TradeJournal, TradeRecord, PerformanceMetrics
from .alerts import AlertSystem, Alert, AlertLevel, EventType
from .ecosystem import TitanEcosystem, EcosystemConfig, EcosystemState, get_ecosystem, create_ecosystem

__all__ = [
    # Brain
    'TitanBrain', 'EvolvingBrain', 'BrainConfig', 'TradingSignal', 'SignalType',
    # Math
    'FastMath', 'NUMBA_AVAILABLE',
    # Risk
    'RiskManager', 'RiskConfig', 'PositionSizer',
    # Execution
    'OrderExecutor', 'Order', 'OrderStatus', 'Fill',
    # Regime
    'RegimeDetector', 'MarketRegime', 'VolatilityState',
    # Journal
    'TradeJournal', 'TradeRecord', 'PerformanceMetrics',
    # Alerts
    'AlertSystem', 'Alert', 'AlertLevel', 'EventType',
    # Ecosystem
    'TitanEcosystem', 'EcosystemConfig', 'EcosystemState', 'get_ecosystem', 'create_ecosystem',
]
