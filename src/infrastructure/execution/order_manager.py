"""
Order Management System

Handles the full order lifecycle:
1. Order creation and validation
2. Risk checks before submission
3. Order routing to venues
4. Fill tracking and reporting
5. Position reconciliation

PRODUCTION NOTES:
- This is a simplified implementation
- Real systems need FIX protocol support
- Order IDs must be globally unique
- All state changes must be persisted
- Need failover and recovery logic
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
from datetime import datetime
import threading
from queue import Queue, Empty


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    IOC = "ioc"           # Immediate or Cancel
    FOK = "fok"           # Fill or Kill
    TWAP = "twap"         # Time-Weighted Average Price
    VWAP = "vwap"         # Volume-Weighted Average Price


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"           # Created, not yet validated
    VALIDATED = "validated"       # Passed risk checks
    SUBMITTED = "submitted"       # Sent to venue
    ACKNOWLEDGED = "acknowledged" # Venue confirmed receipt
    PARTIALLY_FILLED = "partial"  # Some fills received
    FILLED = "filled"             # Fully executed
    CANCELLED = "cancelled"       # Cancelled by user or system
    REJECTED = "rejected"         # Rejected by venue or risk
    EXPIRED = "expired"           # Time-in-force expired


@dataclass
class Order:
    """
    Order representation.

    Contains all information needed to:
    - Execute the order
    - Track its lifecycle
    - Calculate P&L
    """
    # Identification
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_order_id: str = ""
    parent_order_id: Optional[str] = None  # For child orders

    # Order details
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None

    # Execution
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    fees: float = 0.0

    # Status
    status: OrderStatus = OrderStatus.PENDING
    status_message: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    # Metadata
    strategy_id: str = ""
    venue: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def remaining_quantity(self) -> float:
        """Quantity yet to be filled."""
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        """Whether order is in terminal state."""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        ]

    @property
    def fill_percentage(self) -> float:
        """Percentage of order filled."""
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity * 100


@dataclass
class Fill:
    """Individual fill (execution) record."""
    fill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    fees: float = 0.0
    venue: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    liquidity: str = ""  # "maker" or "taker"


class OrderManager:
    """
    Central order management system.

    Responsibilities:
    - Maintain order state
    - Validate orders before submission
    - Route orders to appropriate venues
    - Track fills and positions
    - Provide order event callbacks
    """

    def __init__(self):
        # Order storage
        self.orders: Dict[str, Order] = {}
        self.fills: Dict[str, List[Fill]] = {}  # order_id -> fills

        # Callbacks
        self.on_order_update: Optional[Callable[[Order], None]] = None
        self.on_fill: Optional[Callable[[Fill], None]] = None

        # Thread safety
        self._lock = threading.Lock()

        # Order queue for async processing
        self.order_queue: Queue = Queue()

        # Active orders by symbol
        self.active_orders: Dict[str, List[str]] = {}  # symbol -> [order_ids]

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        strategy_id: str = "",
        **kwargs
    ) -> Order:
        """
        Create a new order.

        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            order_type: Type of order
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            strategy_id: ID of strategy placing order

        Returns:
            Created Order object
        """
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            strategy_id=strategy_id,
            **kwargs
        )

        with self._lock:
            self.orders[order.order_id] = order
            self.fills[order.order_id] = []

        return order

    def validate_order(self, order: Order) -> Tuple[bool, str]:
        """
        Validate order before submission.

        Checks:
        - Required fields present
        - Price/quantity sanity
        - Symbol validity
        - Risk limits (delegated to RiskManager)
        """
        # Basic validation
        if not order.symbol:
            return False, "Symbol is required"

        if order.quantity <= 0:
            return False, "Quantity must be positive"

        if order.order_type == OrderType.LIMIT and order.limit_price is None:
            return False, "Limit price required for limit orders"

        if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and order.stop_price is None:
            return False, "Stop price required for stop orders"

        # Limit price sanity (prevent fat-finger errors)
        if order.limit_price is not None and order.limit_price <= 0:
            return False, "Limit price must be positive"

        # Update status
        order.status = OrderStatus.VALIDATED
        return True, "Order validated"

    def submit_order(self, order: Order) -> bool:
        """
        Submit validated order for execution.

        Returns True if submission was queued successfully.
        """
        if order.status != OrderStatus.VALIDATED:
            valid, msg = self.validate_order(order)
            if not valid:
                order.status = OrderStatus.REJECTED
                order.status_message = msg
                self._notify_update(order)
                return False

        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now()

        # Add to active orders
        with self._lock:
            if order.symbol not in self.active_orders:
                self.active_orders[order.symbol] = []
            self.active_orders[order.symbol].append(order.order_id)

        # Queue for processing
        self.order_queue.put(order)

        self._notify_update(order)
        return True

    def cancel_order(self, order_id: str) -> bool:
        """
        Request cancellation of an order.

        Returns True if cancellation was submitted.
        """
        with self._lock:
            order = self.orders.get(order_id)
            if order is None:
                return False

            if order.is_complete:
                return False

            order.status = OrderStatus.CANCELLED
            order.status_message = "Cancelled by user"

            # Remove from active orders
            if order.symbol in self.active_orders:
                if order_id in self.active_orders[order.symbol]:
                    self.active_orders[order.symbol].remove(order_id)

        self._notify_update(order)
        return True

    def cancel_all(self, symbol: Optional[str] = None, strategy_id: Optional[str] = None):
        """Cancel all orders, optionally filtered by symbol or strategy."""
        with self._lock:
            for order_id, order in self.orders.items():
                if order.is_complete:
                    continue

                if symbol and order.symbol != symbol:
                    continue

                if strategy_id and order.strategy_id != strategy_id:
                    continue

                order.status = OrderStatus.CANCELLED
                order.status_message = "Cancelled by cancel_all"
                self._notify_update(order)

    def record_fill(self, order_id: str, fill: Fill):
        """
        Record a fill for an order.

        Updates order state and notifies callbacks.
        """
        with self._lock:
            order = self.orders.get(order_id)
            if order is None:
                return

            # Update order with fill
            order.filled_quantity += fill.quantity
            order.fees += fill.fees

            # Update average fill price
            if order.filled_quantity > 0:
                prev_value = order.average_fill_price * (order.filled_quantity - fill.quantity)
                new_value = prev_value + fill.price * fill.quantity
                order.average_fill_price = new_value / order.filled_quantity

            # Update status
            if order.filled_quantity >= order.quantity:
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.now()

                # Remove from active orders
                if order.symbol in self.active_orders:
                    if order_id in self.active_orders[order.symbol]:
                        self.active_orders[order.symbol].remove(order_id)
            else:
                order.status = OrderStatus.PARTIALLY_FILLED

            # Record fill
            self.fills[order_id].append(fill)

        self._notify_update(order)
        if self.on_fill:
            self.on_fill(fill)

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)

    def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all active (non-complete) orders."""
        with self._lock:
            active = []
            for order in self.orders.values():
                if not order.is_complete:
                    if symbol is None or order.symbol == symbol:
                        active.append(order)
            return active

    def get_fills(self, order_id: str) -> List[Fill]:
        """Get all fills for an order."""
        return self.fills.get(order_id, [])

    def _notify_update(self, order: Order):
        """Notify listeners of order update."""
        if self.on_order_update:
            self.on_order_update(order)


# Type alias for import convenience
from typing import Tuple
