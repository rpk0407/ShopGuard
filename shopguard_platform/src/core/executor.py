"""
THE MITOCHONDRIA - Order Execution Engine
==========================================
Converts trading signals into executed orders.

Features:
- Order lifecycle management
- Simulated order book
- Slippage modeling
- Partial fills
- Order types (market, limit, stop)
- Execution quality metrics
"""

import time
import uuid
import random
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
from collections import deque
import threading

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order lifecycle status"""
    PENDING = "pending"           # Created, not submitted
    SUBMITTED = "submitted"       # Sent to exchange
    PARTIALLY_FILLED = "partial"  # Some fills received
    FILLED = "filled"            # Fully executed
    CANCELLED = "cancelled"      # User cancelled
    REJECTED = "rejected"        # Exchange rejected
    EXPIRED = "expired"          # Time expired


@dataclass
class Fill:
    """Single order fill"""
    fill_id: str
    order_id: str
    price: float
    quantity: float
    fee: float
    timestamp: float
    slippage: float  # Difference from expected price


@dataclass
class Order:
    """Order representation"""
    order_id: str
    asset: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None  # For limit orders
    stop_price: Optional[float] = None  # For stop orders

    # State
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    total_fees: float = 0.0

    # Timing
    created_at: float = field(default_factory=time.time)
    submitted_at: Optional[float] = None
    filled_at: Optional[float] = None

    # Metadata
    signal_id: Optional[str] = None
    strategy: str = "titan"

    # Fills
    fills: List[Fill] = field(default_factory=list)

    @property
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]

    def add_fill(self, fill: Fill):
        """Add a fill to the order"""
        self.fills.append(fill)
        self.filled_quantity += fill.quantity
        self.total_fees += fill.fee

        # Recalculate average fill price
        total_value = sum(f.price * f.quantity for f in self.fills)
        self.average_fill_price = total_value / self.filled_quantity if self.filled_quantity > 0 else 0

        # Update status
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
            self.filled_at = time.time()
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIALLY_FILLED


@dataclass
class ExecutionConfig:
    """Execution engine configuration"""
    # Fees
    maker_fee: float = 0.001  # 0.1%
    taker_fee: float = 0.002  # 0.2%

    # Slippage model
    base_slippage: float = 0.0005  # 0.05% base slippage
    volume_impact: float = 0.0001  # Additional slippage per 1% of volume

    # Latency simulation
    min_latency_ms: int = 10
    max_latency_ms: int = 100

    # Partial fills
    enable_partial_fills: bool = True
    min_fill_pct: float = 0.3  # Minimum 30% per fill

    # Order expiry
    default_expiry_seconds: int = 86400  # 24 hours


class OrderExecutor:
    """
    THE MITOCHONDRIA
    ================
    Handles order execution with realistic simulation.

    Simulates:
    - Order routing latency
    - Market impact and slippage
    - Partial fills
    - Fee calculation
    """

    def __init__(self, config: ExecutionConfig = None):
        self.config = config or ExecutionConfig()

        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.pending_orders: Dict[str, Order] = {}
        self.order_history: deque = deque(maxlen=1000)

        # Market state
        self.current_prices: Dict[str, float] = {}
        self.volumes: Dict[str, float] = {}  # Simulated volumes

        # Callbacks
        self.on_fill: Optional[Callable[[Fill], None]] = None
        self.on_order_update: Optional[Callable[[Order], None]] = None

        # Execution metrics
        self.total_orders = 0
        self.total_fills = 0
        self.total_slippage = 0.0
        self.total_fees = 0.0

        # Background processing
        self._running = False
        self._lock = threading.Lock()

        logger.info("⚡ Order Executor (Mitochondria) initialized")

    def update_market(self, asset: str, price: float, volume: float = 1000000):
        """Update market state for an asset"""
        with self._lock:
            self.current_prices[asset] = price
            self.volumes[asset] = volume

    def create_order(
        self,
        asset: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        signal_id: Optional[str] = None
    ) -> Order:
        """Create a new order"""
        order = Order(
            order_id=str(uuid.uuid4())[:8],
            asset=asset,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            signal_id=signal_id
        )

        with self._lock:
            self.orders[order.order_id] = order
            self.total_orders += 1

        logger.info(f"⚡ Order created: {order.order_id} {side.value} {quantity} {asset} @ {price or 'MARKET'}")

        return order

    def submit_order(self, order_id: str) -> bool:
        """Submit order for execution"""
        with self._lock:
            if order_id not in self.orders:
                return False

            order = self.orders[order_id]
            if order.status != OrderStatus.PENDING:
                return False

            order.status = OrderStatus.SUBMITTED
            order.submitted_at = time.time()
            self.pending_orders[order_id] = order

        logger.info(f"⚡ Order submitted: {order_id}")

        # Process immediately for market orders
        if order.order_type == OrderType.MARKET:
            self._execute_market_order(order)

        return True

    def _execute_market_order(self, order: Order):
        """Execute a market order with slippage simulation"""
        asset = order.asset

        with self._lock:
            if asset not in self.current_prices:
                order.status = OrderStatus.REJECTED
                logger.warning(f"⚡ Order rejected: {order.order_id} - No price for {asset}")
                return

            base_price = self.current_prices[asset]
            volume = self.volumes.get(asset, 1000000)

        # Calculate slippage
        slippage = self._calculate_slippage(order.quantity, base_price, volume, order.side)

        # Apply slippage to execution price
        if order.side == OrderSide.BUY:
            exec_price = base_price * (1 + slippage)
        else:
            exec_price = base_price * (1 - slippage)

        # Simulate latency
        latency = random.randint(self.config.min_latency_ms, self.config.max_latency_ms)
        time.sleep(latency / 1000)

        # Execute fills
        if self.config.enable_partial_fills and random.random() < 0.3:
            # Partial fill scenario
            self._execute_partial_fills(order, exec_price, slippage)
        else:
            # Full fill
            self._execute_full_fill(order, exec_price, slippage)

    def _calculate_slippage(
        self,
        quantity: float,
        price: float,
        volume: float,
        side: OrderSide
    ) -> float:
        """Calculate realistic slippage"""
        # Base slippage
        slippage = self.config.base_slippage

        # Volume impact
        order_value = quantity * price
        volume_pct = order_value / volume if volume > 0 else 0.01
        slippage += volume_pct * self.config.volume_impact * 100

        # Random component
        slippage *= random.uniform(0.5, 1.5)

        return slippage

    def _execute_full_fill(self, order: Order, exec_price: float, slippage: float):
        """Execute order with single full fill"""
        fee = self._calculate_fee(order.quantity, exec_price, OrderType.MARKET)

        fill = Fill(
            fill_id=str(uuid.uuid4())[:8],
            order_id=order.order_id,
            price=exec_price,
            quantity=order.quantity,
            fee=fee,
            timestamp=time.time(),
            slippage=slippage
        )

        with self._lock:
            order.add_fill(fill)
            self.total_fills += 1
            self.total_slippage += slippage * order.quantity * exec_price
            self.total_fees += fee

            if order.order_id in self.pending_orders:
                del self.pending_orders[order.order_id]

            self.order_history.append(order)

        logger.info(f"⚡ Fill: {fill.fill_id} - {order.quantity} @ ${exec_price:.4f} (slip: {slippage*100:.3f}%)")

        if self.on_fill:
            self.on_fill(fill)
        if self.on_order_update:
            self.on_order_update(order)

    def _execute_partial_fills(self, order: Order, base_price: float, base_slippage: float):
        """Execute order with multiple partial fills"""
        remaining = order.quantity
        fill_count = random.randint(2, 4)

        for i in range(fill_count):
            if remaining <= 0:
                break

            # Calculate fill size
            if i == fill_count - 1:
                fill_qty = remaining
            else:
                min_qty = remaining * self.config.min_fill_pct
                fill_qty = random.uniform(min_qty, remaining * 0.7)

            # Slight price variation between fills
            price_variation = random.uniform(-0.0005, 0.0005)
            fill_price = base_price * (1 + price_variation)
            fill_slippage = base_slippage + abs(price_variation)

            fee = self._calculate_fee(fill_qty, fill_price, OrderType.MARKET)

            fill = Fill(
                fill_id=str(uuid.uuid4())[:8],
                order_id=order.order_id,
                price=fill_price,
                quantity=fill_qty,
                fee=fee,
                timestamp=time.time(),
                slippage=fill_slippage
            )

            with self._lock:
                order.add_fill(fill)
                self.total_fills += 1
                self.total_slippage += fill_slippage * fill_qty * fill_price
                self.total_fees += fee

            remaining -= fill_qty

            logger.info(f"⚡ Partial fill: {fill.fill_id} - {fill_qty:.4f} @ ${fill_price:.4f}")

            if self.on_fill:
                self.on_fill(fill)

            # Small delay between fills
            time.sleep(random.uniform(0.01, 0.05))

        with self._lock:
            if order.order_id in self.pending_orders:
                del self.pending_orders[order.order_id]
            self.order_history.append(order)

        if self.on_order_update:
            self.on_order_update(order)

    def _calculate_fee(self, quantity: float, price: float, order_type: OrderType) -> float:
        """Calculate trading fee"""
        value = quantity * price

        if order_type == OrderType.LIMIT:
            return value * self.config.maker_fee
        else:
            return value * self.config.taker_fee

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        with self._lock:
            if order_id not in self.orders:
                return False

            order = self.orders[order_id]
            if order.is_complete:
                return False

            order.status = OrderStatus.CANCELLED

            if order_id in self.pending_orders:
                del self.pending_orders[order_id]

        logger.info(f"⚡ Order cancelled: {order_id}")

        if self.on_order_update:
            self.on_order_update(order)

        return True

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return self.orders.get(order_id)

    def get_open_orders(self, asset: Optional[str] = None) -> List[Order]:
        """Get all open orders, optionally filtered by asset"""
        with self._lock:
            orders = [o for o in self.pending_orders.values() if not o.is_complete]
            if asset:
                orders = [o for o in orders if o.asset == asset]
            return orders

    def execute_signal(
        self,
        asset: str,
        side: str,
        quantity: float,
        signal_id: Optional[str] = None
    ) -> Optional[Order]:
        """
        Convenience method: Create and execute a market order from a signal.
        Returns the filled order.
        """
        order_side = OrderSide.BUY if side.upper() in ["BUY", "LONG"] else OrderSide.SELL

        order = self.create_order(
            asset=asset,
            side=order_side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            signal_id=signal_id
        )

        self.submit_order(order.order_id)

        # Wait for completion (with timeout)
        timeout = 5
        start = time.time()
        while not order.is_complete and time.time() - start < timeout:
            time.sleep(0.01)

        return order if order.is_complete else None

    def get_stats(self) -> Dict:
        """Get execution statistics"""
        with self._lock:
            open_orders = len(self.pending_orders)
            completed_orders = len([o for o in self.orders.values() if o.is_complete])

            avg_slippage = self.total_slippage / self.total_orders if self.total_orders > 0 else 0
            fill_rate = self.total_fills / self.total_orders if self.total_orders > 0 else 0

        return {
            'total_orders': self.total_orders,
            'open_orders': open_orders,
            'completed_orders': completed_orders,
            'total_fills': self.total_fills,
            'fill_rate': fill_rate,
            'total_slippage': self.total_slippage,
            'avg_slippage_pct': avg_slippage * 100,
            'total_fees': self.total_fees
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test executor
    executor = OrderExecutor()

    # Set market price
    executor.update_market("BTC/USDT", 50000.0, 10000000)

    # Execute a signal
    order = executor.execute_signal("BTC/USDT", "BUY", 0.1)

    if order:
        print(f"\nOrder completed:")
        print(f"  ID: {order.order_id}")
        print(f"  Status: {order.status.value}")
        print(f"  Filled: {order.filled_quantity} @ ${order.average_fill_price:.2f}")
        print(f"  Fees: ${order.total_fees:.4f}")
        print(f"  Fills: {len(order.fills)}")

    print(f"\nStats: {executor.get_stats()}")
