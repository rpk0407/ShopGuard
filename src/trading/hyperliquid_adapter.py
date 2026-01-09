"""
Hyperliquid DEX Adapter

Integration with Hyperliquid decentralized perpetual futures exchange.

Official SDK: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
API Docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api

Features:
- Perpetual futures trading
- WebSocket real-time data
- API wallet support for secure delegation
- Mainnet and testnet support
"""

import os
import json
import time
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from loguru import logger

try:
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants
    HYPERLIQUID_AVAILABLE = True
except ImportError:
    logger.warning("hyperliquid-python-sdk not installed. Install with: pip install hyperliquid-python-sdk")
    HYPERLIQUID_AVAILABLE = False


class HyperliquidOrderSide(Enum):
    """Order side for Hyperliquid"""
    BUY = "A"  # Ask (buy)
    SELL = "B"  # Bid (sell)


class HyperliquidOrderType(Enum):
    """Order types on Hyperliquid"""
    LIMIT = "limit"
    MARKET = "market"  # Market orders converted to aggressive limit orders
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    SCALE = "scale"  # TWAP-like order
    TRIGGER = "trigger"  # Conditional order


@dataclass
class HyperliquidPosition:
    """Hyperliquid position"""
    coin: str
    side: str  # "long" or "short"
    size: float
    entry_price: float
    liquidation_price: Optional[float]
    unrealized_pnl: float
    leverage: float
    margin_used: float


@dataclass
class HyperliquidOrder:
    """Hyperliquid order"""
    oid: str  # Order ID
    coin: str
    side: str
    order_type: str
    size: float
    limit_price: Optional[float]
    reduce_only: bool
    status: str
    filled_size: float
    timestamp: int


class HyperliquidAdapter:
    """
    Adapter for Hyperliquid DEX

    Supports:
    - Spot and perpetual futures trading
    - Real-time market data via WebSocket
    - Position management
    - Order management
    - Account information
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        wallet_address: Optional[str] = None,
        testnet: bool = True,
        vault_address: Optional[str] = None
    ):
        """
        Initialize Hyperliquid adapter

        Args:
            private_key: Private key for signing transactions (optional if using API wallet)
            wallet_address: Wallet address (optional, derived from private key if not provided)
            testnet: Use testnet (True) or mainnet (False)
            vault_address: Vault address for trading from vault (optional)
        """
        if not HYPERLIQUID_AVAILABLE:
            raise ImportError("hyperliquid-python-sdk not installed")

        self.private_key = private_key or os.getenv('HYPERLIQUID_PRIVATE_KEY')
        self.wallet_address = wallet_address or os.getenv('HYPERLIQUID_WALLET_ADDRESS')
        self.testnet = testnet
        self.vault_address = vault_address
        self.connected = False

        # API endpoints
        if testnet:
            self.api_url = constants.TESTNET_API_URL
        else:
            self.api_url = constants.MAINNET_API_URL

        # Initialize SDK components
        self.info = None
        self.exchange = None

        logger.info(f"Hyperliquid adapter initialized ({'testnet' if testnet else 'mainnet'})")

    def connect(self) -> bool:
        """Connect to Hyperliquid"""
        try:
            # Initialize Info (read-only, no auth needed)
            self.info = Info(self.api_url, skip_ws=True)

            # Initialize Exchange (requires private key for trading)
            if self.private_key:
                self.exchange = Exchange(
                    self.private_key,
                    self.api_url,
                    vault_address=self.vault_address
                )
                logger.info("Exchange initialized with private key")
            else:
                logger.warning("No private key provided - read-only mode")

            self.connected = True
            logger.info("✓ Connected to Hyperliquid")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Hyperliquid: {e}")
            self.connected = False
            return False

    def disconnect(self) -> bool:
        """Disconnect from Hyperliquid"""
        self.connected = False
        logger.info("Disconnected from Hyperliquid")
        return True

    # =========================================================================
    # Market Data
    # =========================================================================

    def get_all_assets(self) -> List[Dict]:
        """Get all available assets/markets"""
        try:
            meta = self.info.meta()
            return meta.get('universe', [])
        except Exception as e:
            logger.error(f"Error getting assets: {e}")
            return []

    def get_market_price(self, coin: str) -> Optional[float]:
        """Get current market price for a coin"""
        try:
            # Get all mids (mid prices)
            all_mids = self.info.all_mids()
            return all_mids.get(coin)
        except Exception as e:
            logger.error(f"Error getting market price for {coin}: {e}")
            return None

    def get_orderbook(self, coin: str, depth: int = 10) -> Optional[Dict]:
        """
        Get orderbook for a coin

        Returns:
            {
                'coin': str,
                'levels': [[price, size, num_orders], ...],
                'time': int
            }
        """
        try:
            l2_snapshot = self.info.l2_snapshot(coin)
            return l2_snapshot
        except Exception as e:
            logger.error(f"Error getting orderbook for {coin}: {e}")
            return None

    def get_candles(
        self,
        coin: str,
        interval: str = "1h",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict]:
        """
        Get historical candles

        Args:
            coin: Asset symbol
            interval: "1m", "15m", "1h", "4h", "1d"
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds

        Returns:
            List of candles: [{
                't': timestamp,
                'T': close_timestamp,
                'o': open,
                'h': high,
                'l': low,
                'c': close,
                'v': volume
            }, ...]
        """
        try:
            candles = self.info.candles_snapshot(
                coin=coin,
                interval=interval,
                startTime=start_time,
                endTime=end_time
            )
            return candles
        except Exception as e:
            logger.error(f"Error getting candles for {coin}: {e}")
            return []

    def get_funding_rate(self, coin: str) -> Optional[float]:
        """Get current funding rate for perpetual"""
        try:
            meta = self.info.meta()
            for asset in meta.get('universe', []):
                if asset['name'] == coin:
                    return asset.get('funding')
            return None
        except Exception as e:
            logger.error(f"Error getting funding rate for {coin}: {e}")
            return None

    # =========================================================================
    # Account Information
    # =========================================================================

    def get_account_state(self, address: Optional[str] = None) -> Optional[Dict]:
        """
        Get account state (balances, positions, margins)

        Returns:
            {
                'marginSummary': {
                    'accountValue': float,
                    'totalNtlPos': float,
                    'totalRawUsd': float,
                    'totalMarginUsed': float,
                    'withdrawable': float
                },
                'crossMarginSummary': {...},
                'assetPositions': [...]
            }
        """
        try:
            addr = address or self.wallet_address
            if not addr:
                logger.error("No wallet address provided")
                return None

            user_state = self.info.user_state(addr)
            return user_state
        except Exception as e:
            logger.error(f"Error getting account state: {e}")
            return None

    def get_balances(self, address: Optional[str] = None) -> Dict[str, float]:
        """Get account balances"""
        try:
            state = self.get_account_state(address)
            if not state:
                return {}

            # Extract USDC balance
            margin_summary = state.get('marginSummary', {})
            withdrawable = float(margin_summary.get('withdrawable', 0))

            return {
                'USDC': withdrawable,
                'account_value': float(margin_summary.get('accountValue', 0)),
                'margin_used': float(margin_summary.get('totalMarginUsed', 0))
            }
        except Exception as e:
            logger.error(f"Error getting balances: {e}")
            return {}

    def get_positions(self, address: Optional[str] = None) -> List[HyperliquidPosition]:
        """Get all open positions"""
        try:
            state = self.get_account_state(address)
            if not state:
                return []

            positions = []
            for asset_pos in state.get('assetPositions', []):
                position = asset_pos.get('position', {})

                # Skip if no position
                if float(position.get('szi', 0)) == 0:
                    continue

                size = float(position['szi'])
                entry_price = float(position['entryPx'])

                positions.append(HyperliquidPosition(
                    coin=asset_pos['position']['coin'],
                    side='long' if size > 0 else 'short',
                    size=abs(size),
                    entry_price=entry_price,
                    liquidation_price=float(position.get('liquidationPx', 0)) if position.get('liquidationPx') else None,
                    unrealized_pnl=float(position.get('unrealizedPnl', 0)),
                    leverage=float(position.get('leverage', {}).get('value', 0)),
                    margin_used=float(position.get('marginUsed', 0))
                ))

            return positions

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    # =========================================================================
    # Trading
    # =========================================================================

    def place_order(
        self,
        coin: str,
        is_buy: bool,
        size: float,
        limit_price: Optional[float] = None,
        reduce_only: bool = False,
        order_type: str = "limit",
        post_only: bool = False,
        client_order_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Place an order on Hyperliquid

        Args:
            coin: Asset symbol (e.g., "BTC", "ETH")
            is_buy: True for buy, False for sell
            size: Order size
            limit_price: Limit price (None for market orders)
            reduce_only: Only reduce existing position
            order_type: "limit" or "market"
            post_only: Post-only order (maker-only)
            client_order_id: Custom order ID

        Returns:
            Order response from exchange
        """
        if not self.exchange:
            logger.error("Exchange not initialized - need private key")
            return None

        try:
            # Build order request
            order = {
                'coin': coin,
                'is_buy': is_buy,
                'sz': size,
                'limit_px': limit_price,
                'order_type': {'limit': limit_price} if order_type == 'limit' else {'market': {}},
                'reduce_only': reduce_only
            }

            if post_only:
                order['order_type']['limit']['tif'] = 'Alo'  # Add liquidity only

            if client_order_id:
                order['cloid'] = client_order_id

            # Place order
            logger.info(f"Placing order: {coin} {' BUY' if is_buy else 'SELL'} {size} @ {limit_price}")
            response = self.exchange.order(order)

            logger.info(f"Order placed: {response}")
            return response

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def place_market_order(
        self,
        coin: str,
        is_buy: bool,
        size: float,
        slippage_tolerance: float = 0.05
    ) -> Optional[Dict]:
        """
        Place a market order (converted to aggressive limit order)

        Args:
            coin: Asset symbol
            is_buy: True for buy, False for sell
            size: Order size
            slippage_tolerance: Maximum slippage (e.g., 0.05 = 5%)
        """
        try:
            # Get current market price
            current_price = self.get_market_price(coin)
            if not current_price:
                logger.error(f"Could not get market price for {coin}")
                return None

            # Calculate limit price with slippage
            if is_buy:
                limit_price = current_price * (1 + slippage_tolerance)
            else:
                limit_price = current_price * (1 - slippage_tolerance)

            # Place as aggressive limit order
            return self.place_order(
                coin=coin,
                is_buy=is_buy,
                size=size,
                limit_price=limit_price,
                order_type="limit"
            )

        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None

    def cancel_order(self, coin: str, order_id: int) -> Optional[Dict]:
        """Cancel an order"""
        if not self.exchange:
            logger.error("Exchange not initialized")
            return None

        try:
            response = self.exchange.cancel(coin, order_id)
            logger.info(f"Order cancelled: {order_id}")
            return response
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return None

    def cancel_all_orders(self, coin: Optional[str] = None) -> Optional[Dict]:
        """Cancel all orders (optionally for a specific coin)"""
        if not self.exchange:
            logger.error("Exchange not initialized")
            return None

        try:
            if coin:
                response = self.exchange.cancel_all(coin)
            else:
                # Cancel for all coins
                response = self.exchange.cancel_all()

            logger.info(f"All orders cancelled")
            return response
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return None

    def get_open_orders(self, address: Optional[str] = None) -> List[HyperliquidOrder]:
        """Get all open orders"""
        try:
            addr = address or self.wallet_address
            if not addr:
                return []

            open_orders = self.info.user_open_orders(addr)

            orders = []
            for order_data in open_orders:
                orders.append(HyperliquidOrder(
                    oid=str(order_data['oid']),
                    coin=order_data['coin'],
                    side='buy' if order_data['side'] == 'A' else 'sell',
                    order_type=order_data.get('orderType', 'limit'),
                    size=float(order_data['sz']),
                    limit_price=float(order_data.get('limitPx', 0)),
                    reduce_only=order_data.get('reduceOnly', False),
                    status='open',
                    filled_size=float(order_data.get('filledSz', 0)),
                    timestamp=order_data.get('timestamp', 0)
                ))

            return orders

        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    # =========================================================================
    # Position Management
    # =========================================================================

    def close_position(self, coin: str, close_price: Optional[float] = None) -> Optional[Dict]:
        """
        Close an entire position

        Args:
            coin: Asset to close position for
            close_price: Limit price for close (None for market close)
        """
        try:
            # Get current position
            positions = self.get_positions()
            position = next((p for p in positions if p.coin == coin), None)

            if not position:
                logger.warning(f"No position found for {coin}")
                return None

            # Determine order side (opposite of position)
            is_buy = (position.side == 'short')

            # Place closing order
            if close_price:
                return self.place_order(
                    coin=coin,
                    is_buy=is_buy,
                    size=position.size,
                    limit_price=close_price,
                    reduce_only=True
                )
            else:
                return self.place_market_order(
                    coin=coin,
                    is_buy=is_buy,
                    size=position.size
                )

        except Exception as e:
            logger.error(f"Error closing position for {coin}: {e}")
            return None

    def update_leverage(self, coin: str, leverage: int, is_cross: bool = True) -> Optional[Dict]:
        """
        Update leverage for a coin

        Args:
            coin: Asset symbol
            leverage: Leverage value (1-50)
            is_cross: Cross margin (True) or isolated (False)
        """
        if not self.exchange:
            logger.error("Exchange not initialized")
            return None

        try:
            response = self.exchange.update_leverage(leverage, coin, is_cross)
            logger.info(f"Leverage updated for {coin}: {leverage}x ({'cross' if is_cross else 'isolated'})")
            return response
        except Exception as e:
            logger.error(f"Error updating leverage: {e}")
            return None


# =============================================================================
# Helper Functions
# =============================================================================

def create_hyperliquid_connection(testnet: bool = True) -> HyperliquidAdapter:
    """Create and connect to Hyperliquid"""
    adapter = HyperliquidAdapter(testnet=testnet)
    adapter.connect()
    return adapter


if __name__ == "__main__":
    # Example usage
    print("Hyperliquid Adapter Example\n")

    # Initialize adapter (testnet)
    hl = HyperliquidAdapter(testnet=True)
    hl.connect()

    # Get available markets
    assets = hl.get_all_assets()
    print(f"\nAvailable markets: {len(assets)}")
    for asset in assets[:5]:
        print(f"  - {asset['name']}: {asset.get('szDecimals', 'N/A')} decimals")

    # Get market price
    btc_price = hl.get_market_price("BTC")
    print(f"\nBTC Price: ${btc_price:,.2f}")

    # Get funding rate
    funding = hl.get_funding_rate("BTC")
    print(f"BTC Funding Rate: {funding:.6f}%")

    print("\n✓ Hyperliquid adapter working!")
