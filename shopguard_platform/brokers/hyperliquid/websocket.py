"""
Hyperliquid WebSocket Client
============================
Real-time streaming for trades, orderbook, and user events.

Features:
- Trade stream (for CVD calculation)
- L2 orderbook stream
- User fills and order updates
- Automatic reconnection
- Heartbeat monitoring
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    import websockets
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

logger = logging.getLogger(__name__)


class SubscriptionType(Enum):
    TRADES = "trades"
    L2_BOOK = "l2Book"
    CANDLE = "candle"
    USER_EVENTS = "userEvents"
    ALL_MIDS = "allMids"


@dataclass
class Trade:
    """Single trade from the stream"""
    asset: str
    price: float
    size: float
    side: str  # "B" for buy, "A" for sell
    timestamp: int
    trade_id: str


@dataclass
class OrderBookLevel:
    """Single level in the order book"""
    price: float
    size: float


@dataclass
class OrderBook:
    """L2 order book snapshot"""
    asset: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: int


@dataclass
class CVDState:
    """Cumulative Volume Delta state for an asset"""
    asset: str
    cvd: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    trade_count: int = 0
    last_update: float = 0.0

    # Rolling window for divergence detection
    cvd_history: List[float] = field(default_factory=list)
    price_history: List[float] = field(default_factory=list)
    max_history: int = 100

    def add_trade(self, price: float, size: float, is_buy: bool):
        """Add a trade to the CVD calculation"""
        if is_buy:
            self.buy_volume += size
            self.cvd += size
        else:
            self.sell_volume += size
            self.cvd -= size

        self.trade_count += 1
        self.last_update = time.time()

        # Update history
        self.cvd_history.append(self.cvd)
        self.price_history.append(price)

        if len(self.cvd_history) > self.max_history:
            self.cvd_history.pop(0)
            self.price_history.pop(0)

    def get_divergence(self) -> Optional[str]:
        """
        Detect divergence between price and CVD.

        Returns:
            "BULLISH" - Price down, CVD up (sellers exhausted)
            "BEARISH" - Price up, CVD down (buyers exhausted)
            None - No divergence
        """
        if len(self.cvd_history) < 20:
            return None

        # Compare last 20 values
        recent_cvd = self.cvd_history[-20:]
        recent_price = self.price_history[-20:]

        price_trend = recent_price[-1] - recent_price[0]
        cvd_trend = recent_cvd[-1] - recent_cvd[0]

        # Bullish divergence: price down, CVD up
        if price_trend < 0 and cvd_trend > 0:
            return "BULLISH"

        # Bearish divergence: price up, CVD down
        if price_trend > 0 and cvd_trend < 0:
            return "BEARISH"

        return None

    def reset(self):
        """Reset CVD state"""
        self.cvd = 0.0
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.trade_count = 0
        self.cvd_history.clear()
        self.price_history.clear()


class HyperliquidWebSocket:
    """
    Hyperliquid WebSocket Client

    Streams real-time data for:
    - Trades (calculate CVD)
    - L2 orderbook
    - User events (fills, order updates)

    Usage:
        ws = HyperliquidWebSocket(testnet=True)

        # Set callbacks
        ws.on_trade = lambda trade: print(f"Trade: {trade}")
        ws.on_cvd_update = lambda cvd: print(f"CVD: {cvd.cvd}")

        # Start streaming
        await ws.connect()
        await ws.subscribe_trades(["BTC", "ETH"])

        # Run until cancelled
        await ws.run_forever()
    """

    MAINNET_WS = "wss://api.hyperliquid.xyz/ws"
    TESTNET_WS = "wss://api.hyperliquid-testnet.xyz/ws"

    def __init__(
        self,
        testnet: bool = True,
        user_address: Optional[str] = None
    ):
        if not WS_AVAILABLE:
            raise ImportError("websockets required. Install with: pip install websockets")

        self.testnet = testnet
        self.ws_url = self.TESTNET_WS if testnet else self.MAINNET_WS
        self.user_address = user_address

        self.ws = None
        self._running = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60
        self._last_message_time = 0
        self._heartbeat_interval = 30

        # Subscriptions
        self._subscriptions: Dict[str, List[str]] = {}

        # CVD tracking per asset
        self.cvd_states: Dict[str, CVDState] = {}

        # Callbacks
        self.on_trade: Optional[Callable[[Trade], None]] = None
        self.on_orderbook: Optional[Callable[[OrderBook], None]] = None
        self.on_cvd_update: Optional[Callable[[CVDState], None]] = None
        self.on_user_fill: Optional[Callable[[Dict], None]] = None
        self.on_user_order: Optional[Callable[[Dict], None]] = None
        self.on_price_update: Optional[Callable[[str, float], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        self.on_reconnect: Optional[Callable[[], None]] = None

        logger.info(f"HyperliquidWebSocket initialized (testnet={testnet})")

    async def connect(self) -> bool:
        """Connect to WebSocket"""
        try:
            self.ws = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5
            )
            self._running = True
            self._reconnect_delay = 1
            self._last_message_time = time.time()

            logger.info(f"Connected to {self.ws_url}")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from WebSocket"""
        self._running = False
        if self.ws:
            await self.ws.close()
            self.ws = None

        if self.on_disconnect:
            self.on_disconnect()

        logger.info("Disconnected from WebSocket")

    async def _send(self, message: Dict):
        """Send a message to WebSocket"""
        if not self.ws:
            return

        try:
            await self.ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Send failed: {e}")

    async def subscribe_trades(self, assets: List[str]):
        """Subscribe to trade stream for assets"""
        for asset in assets:
            await self._send({
                "method": "subscribe",
                "subscription": {
                    "type": "trades",
                    "coin": asset
                }
            })

            # Initialize CVD state
            if asset not in self.cvd_states:
                self.cvd_states[asset] = CVDState(asset=asset)

            self._subscriptions.setdefault("trades", []).append(asset)

        logger.info(f"Subscribed to trades: {assets}")

    async def subscribe_orderbook(self, assets: List[str]):
        """Subscribe to L2 orderbook for assets"""
        for asset in assets:
            await self._send({
                "method": "subscribe",
                "subscription": {
                    "type": "l2Book",
                    "coin": asset
                }
            })

            self._subscriptions.setdefault("l2Book", []).append(asset)

        logger.info(f"Subscribed to orderbook: {assets}")

    async def subscribe_all_mids(self):
        """Subscribe to all mid prices"""
        await self._send({
            "method": "subscribe",
            "subscription": {"type": "allMids"}
        })

        self._subscriptions["allMids"] = ["all"]
        logger.info("Subscribed to all mids")

    async def subscribe_user_events(self, address: str):
        """Subscribe to user-specific events (fills, orders)"""
        self.user_address = address

        await self._send({
            "method": "subscribe",
            "subscription": {
                "type": "userEvents",
                "user": address
            }
        })

        self._subscriptions["userEvents"] = [address]
        logger.info(f"Subscribed to user events for {address[:10]}...")

    async def unsubscribe(self, sub_type: str, asset: Optional[str] = None):
        """Unsubscribe from a channel"""
        payload = {"type": sub_type}
        if asset:
            payload["coin"] = asset

        await self._send({
            "method": "unsubscribe",
            "subscription": payload
        })

    async def _handle_message(self, message: str):
        """Process incoming WebSocket message"""
        self._last_message_time = time.time()

        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {message[:100]}")
            return

        channel = data.get("channel")

        if channel == "trades":
            await self._handle_trades(data.get("data", []))

        elif channel == "l2Book":
            await self._handle_orderbook(data.get("data", {}))

        elif channel == "allMids":
            await self._handle_all_mids(data.get("data", {}))

        elif channel == "user":
            await self._handle_user_event(data.get("data", {}))

        elif channel == "subscriptionResponse":
            logger.debug(f"Subscription confirmed: {data}")

        elif channel == "pong":
            pass  # Heartbeat response

        else:
            logger.debug(f"Unknown channel: {channel}")

    async def _handle_trades(self, trades: List[Dict]):
        """Process trade stream data"""
        for trade_data in trades:
            asset = trade_data.get("coin")
            if not asset:
                continue

            trade = Trade(
                asset=asset,
                price=float(trade_data.get("px", 0)),
                size=float(trade_data.get("sz", 0)),
                side=trade_data.get("side", ""),
                timestamp=trade_data.get("time", 0),
                trade_id=str(trade_data.get("tid", ""))
            )

            # Update CVD
            is_buy = trade.side == "B"
            cvd_state = self.cvd_states.get(asset)

            if cvd_state:
                cvd_state.add_trade(trade.price, trade.size, is_buy)

                if self.on_cvd_update:
                    self.on_cvd_update(cvd_state)

            # Callback
            if self.on_trade:
                self.on_trade(trade)

    async def _handle_orderbook(self, data: Dict):
        """Process orderbook data"""
        asset = data.get("coin")
        if not asset:
            return

        levels = data.get("levels", [[], []])

        orderbook = OrderBook(
            asset=asset,
            bids=[OrderBookLevel(float(l["px"]), float(l["sz"])) for l in levels[0]],
            asks=[OrderBookLevel(float(l["px"]), float(l["sz"])) for l in levels[1]],
            timestamp=data.get("time", int(time.time() * 1000))
        )

        if self.on_orderbook:
            self.on_orderbook(orderbook)

    async def _handle_all_mids(self, data: Dict):
        """Process all mid prices"""
        mids = data.get("mids", {})

        for asset, price in mids.items():
            if self.on_price_update:
                self.on_price_update(asset, float(price))

    async def _handle_user_event(self, data: Dict):
        """Process user events (fills, orders)"""
        fills = data.get("fills", [])
        for fill in fills:
            if self.on_user_fill:
                self.on_user_fill(fill)

        # Order updates are in different format
        if "order" in data:
            if self.on_user_order:
                self.on_user_order(data["order"])

    async def _heartbeat(self):
        """Send periodic heartbeat"""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)

                if not self._running or not self.ws:
                    break

                # Check for stale connection
                if time.time() - self._last_message_time > self._heartbeat_interval * 2:
                    logger.warning("Connection seems stale, reconnecting...")
                    await self._reconnect()
                    continue

                # Send ping
                await self._send({"method": "ping"})

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def _reconnect(self):
        """Attempt to reconnect"""
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
            self.ws = None

        while self._running:
            logger.info(f"Reconnecting in {self._reconnect_delay}s...")
            await asyncio.sleep(self._reconnect_delay)

            if await self.connect():
                # Resubscribe
                await self._resubscribe()

                if self.on_reconnect:
                    self.on_reconnect()

                return

            # Exponential backoff
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                self._max_reconnect_delay
            )

    async def _resubscribe(self):
        """Resubscribe to all channels after reconnect"""
        for sub_type, items in self._subscriptions.items():
            if sub_type == "trades":
                await self.subscribe_trades(items)
            elif sub_type == "l2Book":
                await self.subscribe_orderbook(items)
            elif sub_type == "allMids":
                await self.subscribe_all_mids()
            elif sub_type == "userEvents" and self.user_address:
                await self.subscribe_user_events(self.user_address)

    async def run_forever(self):
        """Run the WebSocket client until stopped"""
        if not self.ws:
            if not await self.connect():
                return

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(self._heartbeat())

        try:
            async for message in self.ws:
                if not self._running:
                    break
                await self._handle_message(message)

        except websockets.ConnectionClosed:
            logger.warning("Connection closed")
            if self._running:
                await self._reconnect()
                if self._running:
                    await self.run_forever()

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            if self._running:
                await self._reconnect()
                if self._running:
                    await self.run_forever()

        finally:
            heartbeat_task.cancel()

    def get_cvd(self, asset: str) -> Optional[CVDState]:
        """Get current CVD state for an asset"""
        return self.cvd_states.get(asset)

    def reset_cvd(self, asset: str):
        """Reset CVD for an asset"""
        if asset in self.cvd_states:
            self.cvd_states[asset].reset()

    def get_status(self) -> Dict:
        """Get WebSocket status"""
        return {
            "connected": self.ws is not None and self.ws.open,
            "testnet": self.testnet,
            "subscriptions": self._subscriptions,
            "cvd_assets": list(self.cvd_states.keys()),
            "last_message": self._last_message_time
        }


# Async context manager for easy usage
class HyperliquidStream:
    """
    Context manager for Hyperliquid WebSocket streaming.

    Usage:
        async with HyperliquidStream(["BTC", "ETH"]) as stream:
            async for cvd_update in stream.cvd_updates():
                print(f"{cvd_update.asset}: CVD={cvd_update.cvd}")
    """

    def __init__(
        self,
        assets: List[str],
        testnet: bool = True,
        user_address: Optional[str] = None
    ):
        self.assets = assets
        self.testnet = testnet
        self.user_address = user_address
        self.ws: Optional[HyperliquidWebSocket] = None
        self._task: Optional[asyncio.Task] = None
        self._cvd_queue: asyncio.Queue = asyncio.Queue()
        self._trade_queue: asyncio.Queue = asyncio.Queue()

    async def __aenter__(self):
        self.ws = HyperliquidWebSocket(
            testnet=self.testnet,
            user_address=self.user_address
        )

        # Set up callbacks
        self.ws.on_cvd_update = lambda cvd: asyncio.create_task(
            self._cvd_queue.put(cvd)
        )
        self.ws.on_trade = lambda trade: asyncio.create_task(
            self._trade_queue.put(trade)
        )

        await self.ws.connect()
        await self.ws.subscribe_trades(self.assets)

        # Start background task
        self._task = asyncio.create_task(self.ws.run_forever())

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.ws:
            await self.ws.disconnect()
        if self._task:
            self._task.cancel()

    async def cvd_updates(self):
        """Async generator for CVD updates"""
        while True:
            cvd = await self._cvd_queue.get()
            yield cvd

    async def trades(self):
        """Async generator for trades"""
        while True:
            trade = await self._trade_queue.get()
            yield trade

    def get_cvd(self, asset: str) -> Optional[CVDState]:
        """Get current CVD for an asset"""
        if self.ws:
            return self.ws.get_cvd(asset)
        return None
