"""
Execution Engine

Core execution logic including:
- Order routing
- Execution algorithms (TWAP, VWAP, etc.)
- Smart order routing
- Latency optimization

ARCHITECTURE NOTES:
- In production, the hot path should be in Rust/C++
- Python is used here for clarity and rapid iteration
- Real systems need sub-millisecond latency
- FIX protocol is the industry standard
"""

import time
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from queue import Queue, Empty
from datetime import datetime, timedelta
import numpy as np

from .order_manager import Order, OrderType, OrderSide, OrderStatus, Fill, OrderManager


@dataclass
class ExecutionConfig:
    """Configuration for execution engine."""
    # Latency settings
    max_latency_ms: float = 100.0           # Max acceptable latency
    heartbeat_interval_ms: float = 1000.0   # Venue heartbeat

    # Execution settings
    default_venue: str = "PRIMARY"
    enable_smart_routing: bool = True
    max_child_orders: int = 10              # For parent/child orders

    # Algo settings
    twap_slice_interval_sec: float = 60.0   # 1-minute slices
    vwap_participation_rate: float = 0.10   # 10% of volume

    # Safety
    max_order_value: float = 1000000.0      # Max single order value
    max_daily_turnover: float = 10000000.0  # Max daily trading volume


@dataclass
class VenueState:
    """State of a trading venue."""
    venue_id: str
    is_connected: bool = False
    last_heartbeat: datetime = None
    latency_ms: float = 0.0
    error_count: int = 0
    daily_volume: float = 0.0


class ExecutionEngine:
    """
    Core execution engine.

    Handles:
    - Order lifecycle management
    - Execution algorithm implementation
    - Venue connectivity
    - Latency monitoring
    """

    def __init__(
        self,
        order_manager: OrderManager,
        config: ExecutionConfig = None
    ):
        self.order_manager = order_manager
        self.config = config or ExecutionConfig()

        # Venue management
        self.venues: Dict[str, VenueState] = {}
        self._register_venue(self.config.default_venue)

        # Execution state
        self.running = False
        self._execution_thread: Optional[threading.Thread] = None
        self._algo_threads: Dict[str, threading.Thread] = {}

        # Metrics
        self.daily_turnover = 0.0
        self.total_fills = 0
        self.average_latency_ms = 0.0

        # Price feed (would be from market data in production)
        self.last_prices: Dict[str, float] = {}

        # Callbacks
        self.on_execution_error: Optional[Callable[[str, str], None]] = None

    def start(self):
        """Start execution engine."""
        self.running = True
        self._execution_thread = threading.Thread(
            target=self._execution_loop,
            daemon=True
        )
        self._execution_thread.start()

    def stop(self):
        """Stop execution engine gracefully."""
        self.running = False
        if self._execution_thread:
            self._execution_thread.join(timeout=5.0)

        # Stop all algo threads
        for thread in self._algo_threads.values():
            thread.join(timeout=2.0)

    def execute_order(self, order: Order) -> bool:
        """
        Execute an order based on its type.

        Routes to appropriate execution algorithm.
        """
        # Pre-execution checks
        if not self._pre_execution_check(order):
            return False

        # Route based on order type
        if order.order_type == OrderType.TWAP:
            return self._execute_twap(order)
        elif order.order_type == OrderType.VWAP:
            return self._execute_vwap(order)
        elif order.order_type in [OrderType.MARKET, OrderType.LIMIT]:
            return self._execute_direct(order)
        else:
            return self._execute_direct(order)

    def _pre_execution_check(self, order: Order) -> bool:
        """Pre-execution safety checks."""
        # Check venue connectivity
        venue = self.venues.get(self.config.default_venue)
        if venue is None or not venue.is_connected:
            order.status = OrderStatus.REJECTED
            order.status_message = "Venue not connected"
            return False

        # Check order value
        price = self.last_prices.get(order.symbol, 0)
        order_value = order.quantity * price
        if order_value > self.config.max_order_value:
            order.status = OrderStatus.REJECTED
            order.status_message = f"Order value ${order_value:.2f} exceeds max ${self.config.max_order_value:.2f}"
            return False

        # Check daily turnover
        if self.daily_turnover + order_value > self.config.max_daily_turnover:
            order.status = OrderStatus.REJECTED
            order.status_message = "Daily turnover limit exceeded"
            return False

        return True

    def _execute_direct(self, order: Order) -> bool:
        """
        Direct execution (market or limit order).

        In a real system, this would:
        1. Encode order in FIX format
        2. Send to venue gateway
        3. Await acknowledgment
        4. Handle fills asynchronously
        """
        order.status = OrderStatus.ACKNOWLEDGED
        order.venue = self.config.default_venue

        # Simulate execution (in real system, this would be async)
        self._simulate_fill(order)

        return True

    def _execute_twap(self, order: Order) -> bool:
        """
        Time-Weighted Average Price execution.

        Splits order into equal slices over time to minimize market impact.

        TWAP Algorithm:
        1. Calculate total execution time
        2. Divide into N slices
        3. Execute each slice at regular intervals
        4. Adjust for partial fills
        """
        # Calculate slices
        slice_interval = self.config.twap_slice_interval_sec
        n_slices = min(
            self.config.max_child_orders,
            max(1, int(order.quantity / 100))  # At least 100 units per slice
        )

        slice_quantity = order.quantity / n_slices

        # Start TWAP thread
        def twap_worker():
            remaining = order.quantity

            for i in range(n_slices):
                if not self.running or order.status == OrderStatus.CANCELLED:
                    break

                # Create child order
                child_qty = min(slice_quantity, remaining)
                child = self.order_manager.create_order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=child_qty,
                    order_type=OrderType.LIMIT,
                    limit_price=self.last_prices.get(order.symbol, 0),
                    parent_order_id=order.order_id,
                    strategy_id=order.strategy_id
                )

                # Execute child
                self._execute_direct(child)

                remaining -= child.filled_quantity

                # Update parent
                order.filled_quantity = order.quantity - remaining

                # Wait for next slice
                if i < n_slices - 1:
                    time.sleep(slice_interval)

            # Finalize parent order
            if remaining <= 0:
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.now()
            else:
                order.status = OrderStatus.PARTIALLY_FILLED

        thread = threading.Thread(target=twap_worker, daemon=True)
        self._algo_threads[order.order_id] = thread
        thread.start()

        return True

    def _execute_vwap(self, order: Order) -> bool:
        """
        Volume-Weighted Average Price execution.

        Trades proportionally to market volume to achieve VWAP.

        VWAP Algorithm:
        1. Predict volume profile for execution window
        2. Calculate target participation at each interval
        3. Adjust execution pace based on actual vs expected volume
        """
        # Simplified VWAP - in reality, need volume predictions
        # For now, use TWAP with volume-adjusted slices

        # Would need real-time volume data here
        # Falling back to TWAP-like behavior
        return self._execute_twap(order)

    def _simulate_fill(self, order: Order):
        """
        Simulate order fill (for backtesting/simulation).

        In production, fills come from venue asynchronously.
        """
        # Get current price
        price = self.last_prices.get(order.symbol)
        if price is None:
            order.status = OrderStatus.REJECTED
            order.status_message = "No price available"
            return

        # Simulate slippage
        slippage = 0.0001  # 1 bp
        if order.side == OrderSide.BUY:
            fill_price = price * (1 + slippage)
        else:
            fill_price = price * (1 - slippage)

        # Create fill
        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            fees=order.quantity * fill_price * 0.0001,  # 1 bp fee
            venue=order.venue,
            liquidity="taker"
        )

        # Record fill
        self.order_manager.record_fill(order.order_id, fill)

        # Update metrics
        self.daily_turnover += order.quantity * fill_price
        self.total_fills += 1

    def _execution_loop(self):
        """Main execution loop - processes order queue."""
        while self.running:
            try:
                # Get order from queue
                order = self.order_manager.order_queue.get(timeout=0.1)

                # Execute
                start_time = time.time()
                success = self.execute_order(order)
                latency = (time.time() - start_time) * 1000

                # Update latency metrics
                self.average_latency_ms = 0.9 * self.average_latency_ms + 0.1 * latency

                if latency > self.config.max_latency_ms:
                    if self.on_execution_error:
                        self.on_execution_error(
                            order.order_id,
                            f"High latency: {latency:.1f}ms"
                        )

            except Empty:
                continue
            except Exception as e:
                if self.on_execution_error:
                    self.on_execution_error("", str(e))

    def _register_venue(self, venue_id: str):
        """Register a trading venue."""
        self.venues[venue_id] = VenueState(
            venue_id=venue_id,
            is_connected=True,  # Assume connected for simulation
            last_heartbeat=datetime.now()
        )

    def update_price(self, symbol: str, price: float):
        """Update last price for a symbol (from market data)."""
        self.last_prices[symbol] = price

    def get_metrics(self) -> Dict:
        """Get execution engine metrics."""
        return {
            "daily_turnover": self.daily_turnover,
            "total_fills": self.total_fills,
            "average_latency_ms": self.average_latency_ms,
            "active_orders": len(self.order_manager.get_active_orders()),
            "venue_status": {
                vid: {"connected": v.is_connected, "latency_ms": v.latency_ms}
                for vid, v in self.venues.items()
            }
        }


# =============================================================================
# EXECUTION ALGORITHMS (Pseudocode for production implementation)
# =============================================================================

"""
PRODUCTION EXECUTION ALGORITHMS

These would be implemented in Rust/C++ for latency-critical applications.

1. TWAP (Time-Weighted Average Price)
   - Split order into N slices
   - Execute each slice at regular intervals
   - Adjust for fills and market conditions

2. VWAP (Volume-Weighted Average Price)
   - Predict volume profile (historical + current day)
   - Calculate participation rate at each interval
   - Execute proportionally to volume

3. Implementation Shortfall (IS)
   - Trade aggressively at start
   - Slow down as execution progresses
   - Balance urgency vs impact

4. Arrival Price
   - Benchmark to price at arrival
   - Minimize slippage from arrival

5. POV (Percentage of Volume)
   - Maintain constant percentage of market volume
   - Adaptive to actual trading activity

SMART ORDER ROUTING (SOR):
- Scan multiple venues for best prices
- Consider fees and rebates
- Account for latency differences
- Handle fragmented liquidity
"""
