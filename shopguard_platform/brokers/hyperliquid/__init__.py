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

from .client import HyperliquidClient
from .websocket import HyperliquidWebSocket
from .broker import HyperliquidBroker

__all__ = [
    'HyperliquidClient',
    'HyperliquidWebSocket',
    'HyperliquidBroker'
]
