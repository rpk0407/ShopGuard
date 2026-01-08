"""
Hyperliquid Broker Module
=========================
Professional integration with Hyperliquid DEX for perpetual futures trading.

Features:
- REST API client for orders and account info
- WebSocket streaming for real-time data
- Order execution (market, limit, stop-loss, take-profit)
- Position management
- Funding rate monitoring
- Liquidation data access

Why Hyperliquid:
- Zero gas fees for order placement/cancellation
- Non-custodial (your keys = your funds)
- Visible mempool (MEV opportunities)
- 75%+ DEX perp market share
- 0% maker fees at high volume tiers
"""

from .client import HyperliquidClient, OrderSide, OrderType, TimeInForce
from .websocket import HyperliquidWebSocket, CVDState, Trade
from .broker import HyperliquidBroker, BrokerConfig, TradeSignal
from .funding import FundingScanner, FundingConfig, FundingOpportunity

__all__ = [
    # Client
    'HyperliquidClient',
    'OrderSide',
    'OrderType',
    'TimeInForce',
    # WebSocket
    'HyperliquidWebSocket',
    'CVDState',
    'Trade',
    # Broker
    'HyperliquidBroker',
    'BrokerConfig',
    'TradeSignal',
    # Funding
    'FundingScanner',
    'FundingConfig',
    'FundingOpportunity',
]
