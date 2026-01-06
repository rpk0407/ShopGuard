"""
TQO MVP Backtesting Framework

Rigorous backtesting with:
- Realistic cost modeling
- Walk-forward validation
- Performance metrics (Sharpe, Sortino, etc.)
"""
from .metrics import BacktestMetrics, calculate_metrics
from .engine import BacktestEngine, BacktestResult

__all__ = [
    'BacktestMetrics',
    'calculate_metrics',
    'BacktestEngine',
    'BacktestResult',
]
