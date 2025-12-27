"""
High-Frequency Trading Components

Ultra-low latency infrastructure for:
- Order book analysis and modeling
- Market microstructure signals
- Market making strategies
- Execution optimization

CRITICAL: In production HFT:
- Core loops must be in C++/Rust
- Latency measured in microseconds
- Co-location with exchange required
- Direct market access essential
"""

from .orderbook import OrderBookAnalyzer, OrderBookState, LOBFeatures
from .microstructure import MicrostructureSignals, ToxicityMetrics
from .market_making import MarketMaker, InventoryManager, QuoteGenerator
from .latency import LatencyMonitor, LatencyOptimizer

__all__ = [
    "OrderBookAnalyzer",
    "OrderBookState",
    "LOBFeatures",
    "MicrostructureSignals",
    "ToxicityMetrics",
    "MarketMaker",
    "InventoryManager",
    "QuoteGenerator",
    "LatencyMonitor",
    "LatencyOptimizer",
]
