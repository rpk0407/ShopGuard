"""
Hyperliquid Broker
==================
Unified broker interface for Hyperliquid DEX.
Combines REST client and WebSocket for complete trading functionality.

Features:
- Order execution with ATR-based risk management
- Real-time CVD tracking
- Position management
- Funding rate monitoring
- Integrated with TitanBrain signals
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from .client import (
    HyperliquidClient,
    OrderSide,
    OrderType,
    TimeInForce,
    OrderResult,
    Position,
    AccountInfo
)
from .websocket import (
    HyperliquidWebSocket,
    CVDState,
    Trade,
    OrderBook
)

logger = logging.getLogger(__name__)


class BrokerState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    TRADING = "trading"
    ERROR = "error"


@dataclass
class TradeSignal:
    """Signal from TitanBrain to execute"""
    asset: str
    side: str  # "BUY" or "SELL"
    size_pct: float  # Percentage of available capital
    confidence: float
    stop_loss: float
    take_profit: float
    signal_type: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutedTrade:
    """Record of executed trade"""
    trade_id: str
    asset: str
    side: str
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: float
    signal_confidence: float
    order_result: OrderResult


@dataclass
class BrokerConfig:
    """Broker configuration"""
    # API
    private_key: str = ""
    testnet: bool = True

    # Risk Management
    max_position_pct: float = 0.25  # Max 25% of capital per position
    max_leverage: int = 3  # Conservative 3x
    max_concurrent_positions: int = 3
    min_confidence: float = 0.6  # Minimum signal confidence to trade

    # Execution
    use_limit_orders: bool = True  # Use limit (post-only) for maker fees
    limit_offset_pct: float = 0.0005  # 0.05% offset for limit orders
    market_slippage_pct: float = 0.01  # 1% max slippage for market orders

    # Assets
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH"])


class HyperliquidBroker:
    """
    Hyperliquid Broker

    Unified interface for trading on Hyperliquid DEX.
    Integrates REST client, WebSocket streaming, and risk management.

    Usage:
        broker = HyperliquidBroker(config)
        await broker.connect()

        # Execute signal from TitanBrain
        result = await broker.execute_signal(signal)

        # Get real-time CVD
        cvd = broker.get_cvd("BTC")

        # Close position
        await broker.close_position("BTC")
    """

    def __init__(self, config: BrokerConfig = None):
        self.config = config or BrokerConfig()
        self.state = BrokerState.DISCONNECTED

        # Initialize client and websocket
        self.client: Optional[HyperliquidClient] = None
        self.ws: Optional[HyperliquidWebSocket] = None
        self._ws_task: Optional[asyncio.Task] = None

        # State
        self.account: Optional[AccountInfo] = None
        self.executed_trades: List[ExecutedTrade] = []
        self._last_account_update = 0
        self._account_update_interval = 5  # seconds

        # Callbacks
        self.on_trade: Optional[Callable[[Trade], None]] = None
        self.on_cvd_update: Optional[Callable[[CVDState], None]] = None
        self.on_fill: Optional[Callable[[Dict], None]] = None
        self.on_position_update: Optional[Callable[[Position], None]] = None

        logger.info("HyperliquidBroker initialized")

    async def connect(self) -> bool:
        """Connect to Hyperliquid (REST + WebSocket)"""
        self.state = BrokerState.CONNECTING

        try:
            # Initialize REST client
            self.client = HyperliquidClient(
                private_key=self.config.private_key if self.config.private_key else None,
                testnet=self.config.testnet
            )

            # Get initial account state
            if self.config.private_key:
                self.account = self.client.get_account()
                if self.account:
                    logger.info(f"Account equity: ${self.account.equity:,.2f}")

            # Initialize WebSocket
            self.ws = HyperliquidWebSocket(
                testnet=self.config.testnet,
                user_address=self.client.address
            )

            # Set up callbacks
            self.ws.on_trade = self._handle_trade
            self.ws.on_cvd_update = self._handle_cvd_update
            self.ws.on_user_fill = self._handle_fill

            # Connect WebSocket
            if not await self.ws.connect():
                logger.error("WebSocket connection failed")
                self.state = BrokerState.ERROR
                return False

            # Subscribe to assets
            await self.ws.subscribe_trades(self.config.assets)
            await self.ws.subscribe_all_mids()

            if self.client.address:
                await self.ws.subscribe_user_events(self.client.address)

            # Start WebSocket task
            self._ws_task = asyncio.create_task(self.ws.run_forever())

            self.state = BrokerState.CONNECTED
            logger.info("HyperliquidBroker connected")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.state = BrokerState.ERROR
            return False

    async def disconnect(self):
        """Disconnect from Hyperliquid"""
        if self.ws:
            await self.ws.disconnect()

        if self._ws_task:
            self._ws_task.cancel()

        self.state = BrokerState.DISCONNECTED
        logger.info("HyperliquidBroker disconnected")

    def _handle_trade(self, trade: Trade):
        """Handle incoming trade from WebSocket"""
        if self.on_trade:
            self.on_trade(trade)

    def _handle_cvd_update(self, cvd: CVDState):
        """Handle CVD update from WebSocket"""
        if self.on_cvd_update:
            self.on_cvd_update(cvd)

    def _handle_fill(self, fill: Dict):
        """Handle fill notification"""
        if self.on_fill:
            self.on_fill(fill)

        # Refresh account on fill
        self._refresh_account()

    def _refresh_account(self):
        """Refresh account info"""
        if self.client and time.time() - self._last_account_update > self._account_update_interval:
            self.account = self.client.get_account()
            self._last_account_update = time.time()

    # =========================================
    # TRADING METHODS
    # =========================================

    async def execute_signal(self, signal: TradeSignal) -> Optional[ExecutedTrade]:
        """
        Execute a trading signal from TitanBrain.

        Args:
            signal: TradeSignal with asset, side, size, stops

        Returns:
            ExecutedTrade if successful, None if rejected
        """
        if self.state != BrokerState.CONNECTED:
            logger.warning("Not connected, cannot execute signal")
            return None

        # Validate confidence
        if signal.confidence < self.config.min_confidence:
            logger.info(f"Signal confidence {signal.confidence:.2f} below threshold")
            return None

        # Refresh account
        self._refresh_account()
        if not self.account:
            logger.error("Cannot get account info")
            return None

        # Check position limits
        current_positions = len([p for p in self.account.positions if p.size != 0])
        if current_positions >= self.config.max_concurrent_positions:
            logger.info("Max concurrent positions reached")
            return None

        # Check if already have position in this asset
        for pos in self.account.positions:
            if pos.asset == signal.asset and pos.size != 0:
                logger.info(f"Already have position in {signal.asset}")
                return None

        # Calculate position size
        available = self.account.available_balance
        max_position_value = available * self.config.max_position_pct * signal.size_pct
        max_position_value *= self.config.max_leverage

        current_price = self.client.get_price(signal.asset)
        if current_price == 0:
            logger.error(f"Cannot get price for {signal.asset}")
            return None

        size = max_position_value / current_price

        # Get asset info for size decimals
        asset_info = self.client.get_asset_info(signal.asset)
        if asset_info:
            sz_decimals = asset_info["sz_decimals"]
            size = round(size, sz_decimals)

        if size == 0:
            logger.warning("Calculated size is 0")
            return None

        logger.info(f"Executing {signal.side} {size} {signal.asset} @ ${current_price:,.2f}")

        # Set leverage
        self.client.set_leverage(signal.asset, self.config.max_leverage)

        # Place order
        side = OrderSide.BUY if signal.side == "BUY" else OrderSide.SELL

        if self.config.use_limit_orders:
            # Use limit order for maker fees
            if side == OrderSide.BUY:
                price = current_price * (1 - self.config.limit_offset_pct)
            else:
                price = current_price * (1 + self.config.limit_offset_pct)

            result = self.client.place_order(
                asset=signal.asset,
                side=side,
                size=size,
                price=price,
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.ALO  # Post-only for 0% maker fee
            )
        else:
            # Market order
            result = self.client.place_order(
                asset=signal.asset,
                side=side,
                size=size,
                order_type=OrderType.MARKET
            )

        if not result.success:
            logger.error(f"Order failed: {result.error}")
            return None

        # Create trade record
        executed = ExecutedTrade(
            trade_id=result.order_id or str(int(time.time() * 1000)),
            asset=signal.asset,
            side=signal.side,
            size=size,
            entry_price=result.avg_price or current_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            timestamp=time.time(),
            signal_confidence=signal.confidence,
            order_result=result
        )

        self.executed_trades.append(executed)

        logger.info(f"Trade executed: {executed.trade_id} - {signal.side} {size} {signal.asset}")

        return executed

    async def close_position(self, asset: str, reason: str = "manual") -> bool:
        """Close position for an asset"""
        if not self.client:
            return False

        result = self.client.close_position(asset)

        if result.success:
            logger.info(f"Position closed: {asset} ({reason})")
            return True

        logger.error(f"Failed to close position: {result.error}")
        return False

    async def close_all_positions(self, reason: str = "emergency") -> bool:
        """Close all positions"""
        if not self.client or not self.account:
            return False

        success = True
        for pos in self.account.positions:
            if pos.size != 0:
                if not await self.close_position(pos.asset, reason):
                    success = False

        return success

    async def check_stop_loss_take_profit(self):
        """Check and execute stop loss / take profit for all positions"""
        if not self.client or not self.account:
            return

        for pos in self.account.positions:
            if pos.size == 0:
                continue

            # Find corresponding executed trade
            trade = None
            for t in self.executed_trades:
                if t.asset == pos.asset:
                    trade = t
                    break

            if not trade:
                continue

            current_price = pos.mark_price

            # Check stop loss
            if pos.size > 0:  # Long
                if current_price <= trade.stop_loss:
                    logger.warning(f"STOP LOSS triggered for {pos.asset}")
                    await self.close_position(pos.asset, "stop_loss")
                elif current_price >= trade.take_profit:
                    logger.info(f"TAKE PROFIT triggered for {pos.asset}")
                    await self.close_position(pos.asset, "take_profit")
            else:  # Short
                if current_price >= trade.stop_loss:
                    logger.warning(f"STOP LOSS triggered for {pos.asset}")
                    await self.close_position(pos.asset, "stop_loss")
                elif current_price <= trade.take_profit:
                    logger.info(f"TAKE PROFIT triggered for {pos.asset}")
                    await self.close_position(pos.asset, "take_profit")

    # =========================================
    # DATA METHODS
    # =========================================

    def get_cvd(self, asset: str) -> Optional[CVDState]:
        """Get current CVD state for an asset"""
        if self.ws:
            return self.ws.get_cvd(asset)
        return None

    def get_all_cvd(self) -> Dict[str, CVDState]:
        """Get CVD for all tracked assets"""
        if self.ws:
            return self.ws.cvd_states
        return {}

    def get_price(self, asset: str) -> float:
        """Get current price for an asset"""
        if self.client:
            return self.client.get_price(asset)
        return 0.0

    def get_funding_rate(self, asset: str) -> float:
        """Get current funding rate"""
        if self.client:
            return self.client.get_funding_rate(asset)
        return 0.0

    def get_all_funding_rates(self) -> Dict[str, float]:
        """Get funding rates for all assets"""
        if self.client:
            return self.client.get_all_funding_rates()
        return {}

    def get_positions(self) -> List[Position]:
        """Get all current positions"""
        self._refresh_account()
        if self.account:
            return self.account.positions
        return []

    def get_account_summary(self) -> Optional[AccountInfo]:
        """Get account summary"""
        self._refresh_account()
        return self.account

    # =========================================
    # STATUS METHODS
    # =========================================

    def get_status(self) -> Dict:
        """Get broker status"""
        return {
            "state": self.state.value,
            "testnet": self.config.testnet,
            "connected": self.state == BrokerState.CONNECTED,
            "client": self.client.get_status() if self.client else None,
            "websocket": self.ws.get_status() if self.ws else None,
            "account": {
                "equity": self.account.equity if self.account else 0,
                "available": self.account.available_balance if self.account else 0,
                "positions": len(self.account.positions) if self.account else 0
            } if self.account else None,
            "executed_trades": len(self.executed_trades),
            "tracked_assets": self.config.assets
        }

    def get_stats(self) -> Dict:
        """Get trading statistics"""
        if not self.executed_trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0
            }

        # Calculate stats from executed trades
        total_trades = len(self.executed_trades)

        # Note: Full P&L calculation would require tracking closes
        return {
            "total_trades": total_trades,
            "assets_traded": list(set(t.asset for t in self.executed_trades)),
            "avg_confidence": sum(t.signal_confidence for t in self.executed_trades) / total_trades
        }


# =========================================
# FACTORY FUNCTIONS
# =========================================

def create_broker(
    private_key: str = "",
    testnet: bool = True,
    assets: List[str] = None
) -> HyperliquidBroker:
    """Create a configured Hyperliquid broker"""
    config = BrokerConfig(
        private_key=private_key,
        testnet=testnet,
        assets=assets or ["BTC", "ETH"]
    )
    return HyperliquidBroker(config)


async def quick_test():
    """Quick test of the broker (no private key needed for read-only)"""
    print("\n" + "=" * 60)
    print("HYPERLIQUID BROKER TEST")
    print("=" * 60 + "\n")

    # Create broker without private key (read-only mode)
    broker = create_broker(testnet=True, assets=["BTC", "ETH"])

    # Connect
    print("Connecting...")
    if not await broker.connect():
        print("Connection failed!")
        return

    print("Connected!")
    print(f"Status: {broker.get_status()}")

    # Get prices
    btc_price = broker.get_price("BTC")
    eth_price = broker.get_price("ETH")
    print(f"\nBTC: ${btc_price:,.2f}")
    print(f"ETH: ${eth_price:,.2f}")

    # Get funding rates
    funding = broker.get_all_funding_rates()
    print(f"\nFunding Rates:")
    for asset, rate in list(funding.items())[:5]:
        print(f"  {asset}: {rate*100:.4f}%")

    # Wait for some CVD data
    print("\nWaiting for CVD data (10 seconds)...")
    await asyncio.sleep(10)

    # Get CVD
    for asset in ["BTC", "ETH"]:
        cvd = broker.get_cvd(asset)
        if cvd:
            print(f"\n{asset} CVD:")
            print(f"  CVD: {cvd.cvd:,.2f}")
            print(f"  Buy Vol: {cvd.buy_volume:,.2f}")
            print(f"  Sell Vol: {cvd.sell_volume:,.2f}")
            print(f"  Trades: {cvd.trade_count}")
            print(f"  Divergence: {cvd.get_divergence()}")

    # Disconnect
    await broker.disconnect()
    print("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(quick_test())
