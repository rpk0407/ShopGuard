"""
Trading Module

Complete trading infrastructure for live and paper trading:
- Broker adapters (Alpaca, Binance, Paper)
- Live trading controller
- Risk management
- Market data management
"""

from .broker_adapters import (
    BrokerAdapter,
    PaperTradingAdapter,
    AlpacaAdapter,
    BinanceAdapter,
    BrokerFactory,
    MultiBrokerManager,
    OrderSide,
    OrderType,
    OrderStatus,
    AssetClass,
    Order,
    Position,
    Quote,
    AccountInfo
)

from .live_controller import (
    LiveTradingController,
    TradingMode,
    SignalAction,
    TradingSignal,
    TradeExecution,
    RiskParameters,
    RiskManager,
    MarketDataManager
)

__all__ = [
    # Broker Adapters
    'BrokerAdapter',
    'PaperTradingAdapter',
    'AlpacaAdapter',
    'BinanceAdapter',
    'BrokerFactory',
    'MultiBrokerManager',

    # Orders & Positions
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'AssetClass',
    'Order',
    'Position',
    'Quote',
    'AccountInfo',

    # Controller
    'LiveTradingController',
    'TradingMode',
    'SignalAction',
    'TradingSignal',
    'TradeExecution',
    'RiskParameters',
    'RiskManager',
    'MarketDataManager'
]
