"""
Hyperliquid REST API Client
===========================
Core client for interacting with Hyperliquid's REST API.

Authentication uses EIP-712 typed data signing with your private key.
For security, use API wallets (can trade but not withdraw).
"""

import time
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass
from enum import Enum

try:
    import requests
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "B"
    SELL = "A"  # Ask


class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"


class TimeInForce(Enum):
    GTC = "Gtc"  # Good til cancelled
    IOC = "Ioc"  # Immediate or cancel
    ALO = "Alo"  # Add liquidity only (post-only)


@dataclass
class OrderResult:
    """Result of an order placement"""
    success: bool
    order_id: Optional[str] = None
    status: Optional[str] = None
    filled_size: float = 0.0
    avg_price: float = 0.0
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


@dataclass
class Position:
    """Current position info"""
    asset: str
    size: float  # Positive = long, negative = short
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    liquidation_price: float
    leverage: float
    margin_used: float


@dataclass
class AccountInfo:
    """Account summary"""
    equity: float
    available_balance: float
    margin_used: float
    unrealized_pnl: float
    positions: List[Position]


class HyperliquidClient:
    """
    Hyperliquid REST API Client

    Usage:
        client = HyperliquidClient(private_key="0x...", testnet=True)

        # Get account info
        account = client.get_account()

        # Place order
        result = client.place_order(
            asset="BTC",
            side=OrderSide.BUY,
            size=0.001,
            price=95000.0,
            order_type=OrderType.LIMIT
        )
    """

    # API endpoints
    MAINNET_URL = "https://api.hyperliquid.xyz"
    TESTNET_URL = "https://api.hyperliquid-testnet.xyz"

    # EIP-712 domain for signing
    DOMAIN = {
        "name": "Exchange",
        "version": "1",
        "chainId": 1337,  # Hyperliquid L1
        "verifyingContract": "0x0000000000000000000000000000000000000000"
    }

    def __init__(
        self,
        private_key: Optional[str] = None,
        testnet: bool = True,
        vault_address: Optional[str] = None
    ):
        """
        Initialize Hyperliquid client.

        Args:
            private_key: Ethereum private key for signing (0x prefixed)
            testnet: Use testnet (recommended for development)
            vault_address: Optional vault address for vault trading
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "eth_account and requests required. "
                "Install with: pip install eth-account requests"
            )

        self.testnet = testnet
        self.base_url = self.TESTNET_URL if testnet else self.MAINNET_URL
        self.vault_address = vault_address

        # Set up account from private key
        self.account = None
        self.address = None

        if private_key:
            self.set_private_key(private_key)

        # Asset info cache
        self._asset_info: Dict[str, Dict] = {}
        self._last_meta_fetch = 0

        logger.info(f"HyperliquidClient initialized (testnet={testnet})")

    def set_private_key(self, private_key: str):
        """Set or update the private key for signing"""
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key

        self.account = Account.from_key(private_key)
        self.address = self.account.address
        logger.info(f"Account set: {self.address[:10]}...{self.address[-6:]}")

    @property
    def connected(self) -> bool:
        """Check if client is configured"""
        return self.account is not None

    # =========================================
    # INFO API (Public, no auth required)
    # =========================================

    def _info_request(self, request_type: str, payload: Dict = None) -> Dict:
        """Make a request to the info API"""
        url = f"{self.base_url}/info"
        data = {"type": request_type}
        if payload:
            data.update(payload)

        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Info request failed: {e}")
            return {"error": str(e)}

    def get_meta(self) -> Dict:
        """Get exchange metadata (assets, leverage, etc.)"""
        return self._info_request("meta")

    def get_asset_info(self, asset: str) -> Optional[Dict]:
        """Get info for a specific asset"""
        # Refresh cache every 5 minutes
        if time.time() - self._last_meta_fetch > 300:
            meta = self.get_meta()
            if "universe" in meta:
                for i, info in enumerate(meta["universe"]):
                    self._asset_info[info["name"]] = {
                        "index": i,
                        "sz_decimals": info.get("szDecimals", 8),
                        "max_leverage": info.get("maxLeverage", 50)
                    }
            self._last_meta_fetch = time.time()

        return self._asset_info.get(asset)

    def get_all_mids(self) -> Dict[str, float]:
        """Get mid prices for all assets"""
        result = self._info_request("allMids")
        if isinstance(result, dict) and "error" not in result:
            return {k: float(v) for k, v in result.items()}
        return {}

    def get_price(self, asset: str) -> float:
        """Get current mid price for an asset"""
        mids = self.get_all_mids()
        return mids.get(asset, 0.0)

    def get_orderbook(self, asset: str) -> Dict:
        """Get L2 orderbook for an asset"""
        return self._info_request("l2Book", {"coin": asset})

    def get_recent_trades(self, asset: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for an asset"""
        result = self._info_request("recentTrades", {"coin": asset})
        if isinstance(result, list):
            return result[:limit]
        return []

    def get_candles(
        self,
        asset: str,
        interval: str = "1m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict]:
        """
        Get candlestick data.

        Args:
            asset: Asset symbol (e.g., "BTC")
            interval: Candle interval ("1m", "5m", "15m", "1h", "4h", "1d")
            start_time: Start timestamp in ms
            end_time: End timestamp in ms
        """
        payload = {
            "coin": asset,
            "interval": interval,
            "startTime": start_time or int((time.time() - 86400) * 1000),
            "endTime": end_time or int(time.time() * 1000)
        }
        return self._info_request("candleSnapshot", payload)

    def get_funding_rate(self, asset: str) -> float:
        """Get current funding rate for an asset"""
        meta = self._info_request("metaAndAssetCtxs")
        if isinstance(meta, list) and len(meta) > 1:
            for ctx in meta[1]:
                if ctx.get("coin") == asset:
                    return float(ctx.get("funding", 0))
        return 0.0

    def get_all_funding_rates(self) -> Dict[str, float]:
        """Get funding rates for all assets"""
        meta = self._info_request("metaAndAssetCtxs")
        rates = {}
        if isinstance(meta, list) and len(meta) > 1:
            for ctx in meta[1]:
                coin = ctx.get("coin")
                if coin:
                    rates[coin] = float(ctx.get("funding", 0))
        return rates

    def get_open_interest(self, asset: str) -> float:
        """Get open interest for an asset"""
        meta = self._info_request("metaAndAssetCtxs")
        if isinstance(meta, list) and len(meta) > 1:
            for ctx in meta[1]:
                if ctx.get("coin") == asset:
                    return float(ctx.get("openInterest", 0))
        return 0.0

    # =========================================
    # USER INFO (Requires address)
    # =========================================

    def get_account(self) -> Optional[AccountInfo]:
        """Get account summary with positions"""
        if not self.address:
            logger.error("No address configured")
            return None

        result = self._info_request("clearinghouseState", {"user": self.address})

        if "error" in result:
            logger.error(f"Failed to get account: {result['error']}")
            return None

        # Parse margin summary
        margin = result.get("marginSummary", {})

        # Parse positions
        positions = []
        for pos_data in result.get("assetPositions", []):
            pos = pos_data.get("position", {})
            if float(pos.get("szi", 0)) != 0:
                positions.append(Position(
                    asset=pos.get("coin", ""),
                    size=float(pos.get("szi", 0)),
                    entry_price=float(pos.get("entryPx", 0)),
                    mark_price=float(pos.get("positionValue", 0)) / float(pos.get("szi", 1)) if float(pos.get("szi", 0)) != 0 else 0,
                    unrealized_pnl=float(pos.get("unrealizedPnl", 0)),
                    liquidation_price=float(pos.get("liquidationPx", 0)) if pos.get("liquidationPx") else 0,
                    leverage=float(pos.get("leverage", {}).get("value", 1)),
                    margin_used=float(pos.get("marginUsed", 0))
                ))

        return AccountInfo(
            equity=float(margin.get("accountValue", 0)),
            available_balance=float(margin.get("withdrawable", 0)),
            margin_used=float(margin.get("totalMarginUsed", 0)),
            unrealized_pnl=float(margin.get("totalUnrealizedPnl", 0)),
            positions=positions
        )

    def get_open_orders(self, asset: Optional[str] = None) -> List[Dict]:
        """Get open orders, optionally filtered by asset"""
        if not self.address:
            return []

        result = self._info_request("openOrders", {"user": self.address})

        if isinstance(result, list):
            if asset:
                return [o for o in result if o.get("coin") == asset]
            return result
        return []

    def get_user_fills(self, limit: int = 100) -> List[Dict]:
        """Get recent fills for the user"""
        if not self.address:
            return []

        result = self._info_request("userFills", {"user": self.address})

        if isinstance(result, list):
            return result[:limit]
        return []

    def get_user_funding_history(self, start_time: Optional[int] = None) -> List[Dict]:
        """Get funding payment history"""
        if not self.address:
            return []

        payload = {"user": self.address}
        if start_time:
            payload["startTime"] = start_time

        return self._info_request("userFunding", payload)

    # =========================================
    # EXCHANGE API (Requires signing)
    # =========================================

    def _sign_action(self, action: Dict, nonce: int) -> Dict:
        """Sign an action using EIP-712 typed data"""
        if not self.account:
            raise ValueError("No private key configured")

        # Build the typed data structure
        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"}
                ],
                "Agent": [
                    {"name": "source", "type": "string"},
                    {"name": "connectionId", "type": "bytes32"}
                ]
            },
            "primaryType": "Agent",
            "domain": self.DOMAIN,
            "message": {
                "source": "a",
                "connectionId": hashlib.sha256(
                    json.dumps(action, separators=(',', ':')).encode()
                ).digest()
            }
        }

        # Sign the typed data
        signed = self.account.sign_message(encode_typed_data(typed_data))

        return {
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": signed.v
        }

    def _exchange_request(self, action: Dict) -> Dict:
        """Make a signed request to the exchange API"""
        if not self.account:
            return {"error": "No private key configured"}

        nonce = int(time.time() * 1000)
        action["nonce"] = nonce

        signature = self._sign_action(action, nonce)

        payload = {
            "action": action,
            "nonce": nonce,
            "signature": signature,
            "vaultAddress": self.vault_address
        }

        url = f"{self.base_url}/exchange"

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Exchange request failed: {e}")
            return {"error": str(e)}

    def place_order(
        self,
        asset: str,
        side: OrderSide,
        size: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC,
        reduce_only: bool = False,
        client_id: Optional[str] = None
    ) -> OrderResult:
        """
        Place an order.

        Args:
            asset: Asset symbol (e.g., "BTC")
            side: OrderSide.BUY or OrderSide.SELL
            size: Order size in base asset
            price: Limit price (required for limit orders)
            order_type: LIMIT or MARKET
            time_in_force: GTC, IOC, or ALO (post-only)
            reduce_only: If True, only reduces position
            client_id: Optional client order ID

        Returns:
            OrderResult with order details
        """
        # Get asset info for size decimals
        asset_info = self.get_asset_info(asset)
        if not asset_info:
            return OrderResult(success=False, error=f"Unknown asset: {asset}")

        # Round size to appropriate decimals
        sz_decimals = asset_info["sz_decimals"]
        size = round(size, sz_decimals)

        # For market orders, use a far limit price
        if order_type == OrderType.MARKET:
            current_price = self.get_price(asset)
            if current_price == 0:
                return OrderResult(success=False, error="Could not get current price")

            # Use 1% slippage for market orders
            if side == OrderSide.BUY:
                price = current_price * 1.01
            else:
                price = current_price * 0.99

            time_in_force = TimeInForce.IOC

        if price is None:
            return OrderResult(success=False, error="Price required for limit orders")

        # Build order
        order = {
            "a": asset_info["index"],  # Asset index
            "b": side == OrderSide.BUY,
            "p": str(price),
            "s": str(size),
            "r": reduce_only,
            "t": {
                "limit": {"tif": time_in_force.value}
            }
        }

        if client_id:
            order["c"] = client_id

        action = {
            "type": "order",
            "orders": [order],
            "grouping": "na"
        }

        result = self._exchange_request(action)

        if "error" in result:
            return OrderResult(success=False, error=result["error"], raw_response=result)

        # Parse response
        if "response" in result:
            resp = result["response"]
            if resp.get("type") == "order":
                statuses = resp.get("data", {}).get("statuses", [])
                if statuses:
                    status = statuses[0]
                    if "resting" in status:
                        return OrderResult(
                            success=True,
                            order_id=str(status["resting"]["oid"]),
                            status="resting",
                            raw_response=result
                        )
                    elif "filled" in status:
                        filled = status["filled"]
                        return OrderResult(
                            success=True,
                            order_id=str(filled.get("oid", "")),
                            status="filled",
                            filled_size=float(filled.get("totalSz", 0)),
                            avg_price=float(filled.get("avgPx", 0)),
                            raw_response=result
                        )
                    elif "error" in status:
                        return OrderResult(
                            success=False,
                            error=status["error"],
                            raw_response=result
                        )

        return OrderResult(success=False, error="Unknown response format", raw_response=result)

    def cancel_order(self, asset: str, order_id: int) -> bool:
        """Cancel an order by ID"""
        asset_info = self.get_asset_info(asset)
        if not asset_info:
            return False

        action = {
            "type": "cancel",
            "cancels": [{"a": asset_info["index"], "o": order_id}]
        }

        result = self._exchange_request(action)
        return "error" not in result

    def cancel_all_orders(self, asset: Optional[str] = None) -> bool:
        """Cancel all open orders, optionally for a specific asset"""
        open_orders = self.get_open_orders(asset)

        if not open_orders:
            return True

        cancels = []
        for order in open_orders:
            asset_info = self.get_asset_info(order["coin"])
            if asset_info:
                cancels.append({
                    "a": asset_info["index"],
                    "o": order["oid"]
                })

        if not cancels:
            return True

        action = {
            "type": "cancel",
            "cancels": cancels
        }

        result = self._exchange_request(action)
        return "error" not in result

    def set_leverage(self, asset: str, leverage: int, is_cross: bool = True) -> bool:
        """
        Set leverage for an asset.

        Args:
            asset: Asset symbol
            leverage: Leverage multiplier (1-50)
            is_cross: True for cross margin, False for isolated
        """
        asset_info = self.get_asset_info(asset)
        if not asset_info:
            return False

        action = {
            "type": "updateLeverage",
            "asset": asset_info["index"],
            "isCross": is_cross,
            "leverage": leverage
        }

        result = self._exchange_request(action)
        return "error" not in result

    def close_position(self, asset: str) -> OrderResult:
        """Close entire position for an asset"""
        account = self.get_account()
        if not account:
            return OrderResult(success=False, error="Could not get account")

        # Find position
        position = None
        for pos in account.positions:
            if pos.asset == asset:
                position = pos
                break

        if not position or position.size == 0:
            return OrderResult(success=True, status="no_position")

        # Determine side to close
        side = OrderSide.SELL if position.size > 0 else OrderSide.BUY
        size = abs(position.size)

        return self.place_order(
            asset=asset,
            side=side,
            size=size,
            order_type=OrderType.MARKET,
            reduce_only=True
        )

    # =========================================
    # UTILITY METHODS
    # =========================================

    def get_status(self) -> Dict:
        """Get client connection status"""
        return {
            "connected": self.connected,
            "testnet": self.testnet,
            "address": self.address[:10] + "..." + self.address[-6:] if self.address else None,
            "base_url": self.base_url
        }


# Convenience function
def create_client(
    private_key: Optional[str] = None,
    testnet: bool = True
) -> HyperliquidClient:
    """Create a Hyperliquid client"""
    return HyperliquidClient(private_key=private_key, testnet=testnet)
