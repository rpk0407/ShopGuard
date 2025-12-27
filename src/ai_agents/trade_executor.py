"""
Autonomous Trade Executor Agent

Executes trades intelligently with human-like behavior:
- Randomized order timing (no predictable patterns)
- Order size variation
- Multi-venue routing for best execution
- Slippage minimization
- Detection avoidance (not flagged as bot)
- Smart position sizing
- Dynamic stop-loss management
- Profit taking strategies
- Portfolio rebalancing
- Risk management

All while maintaining user control and safety.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum, auto
import numpy as np
import random
import time
import threading
from collections import deque

from .base import (
    BaseAgent, Signal, SignalStrength, MarketSnapshot,
    AgentState, generate_unique_id, normalize_confidence,
    calculate_position_size
)


class OrderType(Enum):
    """Order types"""
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()
    STOP_LIMIT = auto()
    TRAILING_STOP = auto()


class OrderStatus(Enum):
    """Order status"""
    PENDING = auto()
    SUBMITTED = auto()
    PARTIAL_FILL = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()
    EXPIRED = auto()


class ExecutionStyle(Enum):
    """Execution style to appear human"""
    AGGRESSIVE = auto()  # Fast execution, okay with slippage
    PATIENT = auto()     # Wait for good fills
    STEALTH = auto()     # Minimize footprint
    ICEBERG = auto()     # Hidden size


@dataclass
class Order:
    """Trade order"""
    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    order_type: OrderType
    limit_price: Optional[float]
    stop_price: Optional[float]
    status: OrderStatus
    created_at: datetime
    filled_quantity: float = 0
    filled_price: float = 0
    fills: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """Current position"""
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    opened_at: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_pct: Optional[float] = None


@dataclass
class ExecutionPlan:
    """Plan for executing a trade"""
    signal: Signal
    total_quantity: float
    slices: List[Dict]  # List of {quantity, delay, style}
    estimated_cost: float
    max_slippage: float
    time_limit: timedelta
    created_at: datetime


class AutonomousTradeExecutor(BaseAgent):
    """
    Executes trades autonomously while appearing human.

    Key features:
    - Randomized timing and sizing
    - Smart order routing
    - Position management
    - Risk controls
    - Human-like behavior patterns
    """

    def __init__(self, capital: float = 100000):
        super().__init__(
            agent_id=generate_unique_id('trade_executor'),
            name="Autonomous Trade Executor",
            description="Executes trades with human-like behavior"
        )

        # Capital and positions
        self.initial_capital = capital
        self.available_capital = capital
        self.positions: Dict[str, Position] = {}
        self.closed_positions: deque = deque(maxlen=500)

        # Order management
        self.pending_orders: Dict[str, Order] = {}
        self.order_history: deque = deque(maxlen=1000)

        # Execution plans
        self.active_plans: Dict[str, ExecutionPlan] = {}

        # Risk parameters
        self.max_position_size_pct = 0.10  # 10% max per position
        self.max_total_exposure_pct = 0.60  # 60% max total
        self.default_stop_loss_pct = 0.05  # 5% stop loss
        self.default_take_profit_pct = 0.15  # 15% take profit
        self.max_daily_loss_pct = 0.03  # 3% max daily loss

        # Human-like behavior settings
        self.min_order_delay = 0.5  # seconds
        self.max_order_delay = 5.0  # seconds
        self.time_between_trades = (10, 120)  # seconds
        self.order_size_variation = 0.15  # ±15% from calculated size
        self.price_improvement_attempts = 3

        # Trading session simulation
        self.session_trades = 0
        self.session_start = datetime.now()
        self.daily_pnl = 0

        # Execution statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_slippage = 0

        # User controls (safety)
        self.trading_enabled = False
        self.paper_trading = True  # Start in paper mode
        self.allowed_symbols: Set[str] = set()
        self.max_trades_per_day = 20

        # Callbacks for actual execution (to be connected to broker)
        self.on_order_submit: Optional[Callable] = None
        self.on_order_cancel: Optional[Callable] = None

    def analyze(self, snapshot: MarketSnapshot) -> Optional[Signal]:
        """
        Check positions and manage existing trades.
        Returns signal if action needed (stop hit, take profit, etc.)
        """
        self.state = AgentState.ANALYZING
        self.last_active = datetime.now()

        # Update position prices
        self._update_positions(snapshot)

        # Check stops and take profits
        exit_signal = self._check_position_exits(snapshot)
        if exit_signal:
            self.state = AgentState.IDLE
            return exit_signal

        # Check pending orders
        self._check_pending_orders(snapshot)

        # Execute active plans
        self._execute_active_plans(snapshot)

        self.state = AgentState.IDLE
        return None

    def execute_signal(self, signal: Signal, snapshot: MarketSnapshot) -> Optional[Order]:
        """
        Execute a trading signal.
        Creates execution plan and starts execution.
        """
        if not self.trading_enabled:
            return None

        if self.session_trades >= self.max_trades_per_day:
            return None

        # Check symbol restrictions
        if self.allowed_symbols and signal.symbol not in self.allowed_symbols:
            return None

        # Check risk limits
        if not self._check_risk_limits(signal, snapshot):
            return None

        self.state = AgentState.EXECUTING

        # Calculate position size
        current_price = snapshot.prices.get(signal.symbol, 0)
        if current_price == 0:
            self.state = AgentState.IDLE
            return None

        position_size = self._calculate_position_size(signal, current_price)
        if position_size == 0:
            self.state = AgentState.IDLE
            return None

        # Create execution plan
        plan = self._create_execution_plan(signal, position_size, current_price)
        self.active_plans[plan.signal.agent_id] = plan

        # Execute first slice
        order = self._execute_slice(plan, 0, snapshot)

        self.state = AgentState.IDLE
        return order

    def _check_risk_limits(self, signal: Signal, snapshot: MarketSnapshot) -> bool:
        """Check if trade passes risk limits"""
        # Daily loss limit
        if self.daily_pnl < -self.initial_capital * self.max_daily_loss_pct:
            return False

        # Check exposure limits
        current_exposure = sum(
            abs(p.quantity * p.current_price)
            for p in self.positions.values()
        )
        if current_exposure / self.initial_capital > self.max_total_exposure_pct:
            return False

        # Check if adding to losing position
        if signal.symbol in self.positions:
            pos = self.positions[signal.symbol]
            if pos.unrealized_pnl < 0:
                if signal.direction == 'long' and pos.quantity > 0:
                    return False  # Don't add to losing long
                if signal.direction == 'short' and pos.quantity < 0:
                    return False  # Don't add to losing short

        return True

    def _calculate_position_size(self, signal: Signal, price: float) -> float:
        """Calculate position size based on signal and risk"""
        # Base size from capital allocation
        max_position_value = self.available_capital * self.max_position_size_pct

        # Adjust for signal confidence
        confidence_factor = signal.confidence

        # Adjust for signal strength
        strength_factor = signal.strength.value / 5

        # Combined factor
        size_factor = confidence_factor * strength_factor

        # Calculate position value
        position_value = max_position_value * size_factor

        # Convert to shares
        shares = position_value / price

        # Add human-like variation
        variation = random.uniform(1 - self.order_size_variation, 1 + self.order_size_variation)
        shares = int(shares * variation)

        # Ensure minimum size
        if shares < 1:
            shares = 0

        return shares

    def _create_execution_plan(self, signal: Signal, total_quantity: float, price: float) -> ExecutionPlan:
        """Create execution plan with slicing for large orders"""
        # Determine number of slices based on size
        if total_quantity < 100:
            num_slices = 1
        elif total_quantity < 500:
            num_slices = random.randint(2, 3)
        elif total_quantity < 2000:
            num_slices = random.randint(3, 5)
        else:
            num_slices = random.randint(5, 10)

        # Create slices with random sizing
        slices = []
        remaining = total_quantity

        for i in range(num_slices):
            if i == num_slices - 1:
                slice_qty = remaining
            else:
                # Random portion of remaining
                portion = random.uniform(0.1, 0.5)
                slice_qty = int(remaining * portion)
                remaining -= slice_qty

            # Random delay between slices
            delay = random.uniform(*self.time_between_trades) if i > 0 else 0

            # Random execution style
            style = random.choice([ExecutionStyle.PATIENT, ExecutionStyle.STEALTH, ExecutionStyle.AGGRESSIVE])

            slices.append({
                'quantity': slice_qty,
                'delay': delay,
                'style': style,
                'executed': False
            })

        return ExecutionPlan(
            signal=signal,
            total_quantity=total_quantity,
            slices=slices,
            estimated_cost=total_quantity * price,
            max_slippage=0.01,  # 1% max slippage
            time_limit=timedelta(hours=1),
            created_at=datetime.now()
        )

    def _execute_slice(self, plan: ExecutionPlan, slice_idx: int, snapshot: MarketSnapshot) -> Optional[Order]:
        """Execute a single slice of the plan"""
        if slice_idx >= len(plan.slices):
            return None

        slice_info = plan.slices[slice_idx]
        if slice_info['executed']:
            return None

        # Add human-like delay
        self.add_human_delay()

        # Determine order type based on style
        current_price = snapshot.prices.get(plan.signal.symbol, 0)
        style = slice_info['style']

        if style == ExecutionStyle.AGGRESSIVE:
            order_type = OrderType.MARKET
            limit_price = None
        elif style == ExecutionStyle.PATIENT:
            order_type = OrderType.LIMIT
            # Try to get better price
            if plan.signal.direction == 'long':
                limit_price = current_price * 0.998  # 0.2% below
            else:
                limit_price = current_price * 1.002  # 0.2% above
        else:  # STEALTH
            order_type = OrderType.LIMIT
            limit_price = current_price

        # Create order
        order = Order(
            order_id=generate_unique_id('order'),
            symbol=plan.signal.symbol,
            side='buy' if plan.signal.direction == 'long' else 'sell',
            quantity=slice_info['quantity'],
            order_type=order_type,
            limit_price=limit_price,
            stop_price=None,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            metadata={
                'signal_id': plan.signal.agent_id,
                'slice_idx': slice_idx,
                'style': style.name
            }
        )

        # Submit order
        self._submit_order(order, snapshot)

        # Mark slice as executed
        plan.slices[slice_idx]['executed'] = True
        plan.slices[slice_idx]['order_id'] = order.order_id

        return order

    def _submit_order(self, order: Order, snapshot: MarketSnapshot):
        """Submit order (paper or live)"""
        order.status = OrderStatus.SUBMITTED
        self.pending_orders[order.order_id] = order

        if self.paper_trading:
            # Simulate fill
            self._simulate_fill(order, snapshot)
        else:
            # Call broker callback
            if self.on_order_submit:
                self.on_order_submit(order)

    def _simulate_fill(self, order: Order, snapshot: MarketSnapshot):
        """Simulate order fill for paper trading"""
        current_price = snapshot.prices.get(order.symbol, 0)

        # Calculate slippage
        if order.order_type == OrderType.MARKET:
            slippage = random.uniform(0, 0.002)  # 0-0.2% slippage
            if order.side == 'buy':
                fill_price = current_price * (1 + slippage)
            else:
                fill_price = current_price * (1 - slippage)
        else:
            # Limit order - check if can fill
            if order.side == 'buy' and order.limit_price and order.limit_price >= current_price:
                fill_price = order.limit_price
            elif order.side == 'sell' and order.limit_price and order.limit_price <= current_price:
                fill_price = order.limit_price
            else:
                # Order rests, may not fill immediately
                return

        # Fill the order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.fills.append({
            'price': fill_price,
            'quantity': order.quantity,
            'timestamp': datetime.now()
        })

        # Update position
        self._update_position_from_fill(order)

        # Move to history
        del self.pending_orders[order.order_id]
        self.order_history.append(order)

        # Update statistics
        self.session_trades += 1
        self.total_trades += 1
        self.total_slippage += abs(fill_price - current_price) / current_price

    def _update_position_from_fill(self, order: Order):
        """Update position after order fill"""
        symbol = order.symbol
        fill_qty = order.filled_quantity if order.side == 'buy' else -order.filled_quantity
        fill_price = order.filled_price

        if symbol in self.positions:
            pos = self.positions[symbol]

            # Update average price
            old_value = pos.quantity * pos.avg_entry_price
            new_value = fill_qty * fill_price

            new_quantity = pos.quantity + fill_qty

            if new_quantity == 0:
                # Position closed
                realized_pnl = (fill_price - pos.avg_entry_price) * (-fill_qty if fill_qty < 0 else fill_qty)
                if fill_qty < 0:  # Selling
                    realized_pnl = (fill_price - pos.avg_entry_price) * abs(fill_qty)
                else:  # Covering short
                    realized_pnl = (pos.avg_entry_price - fill_price) * abs(fill_qty)

                pos.realized_pnl += realized_pnl
                self.daily_pnl += realized_pnl
                self.available_capital += abs(pos.quantity) * pos.avg_entry_price + realized_pnl

                # Archive position
                self.closed_positions.append(pos)
                del self.positions[symbol]

                if realized_pnl > 0:
                    self.winning_trades += 1
            else:
                # Position modified
                if (pos.quantity > 0 and fill_qty > 0) or (pos.quantity < 0 and fill_qty < 0):
                    # Adding to position
                    pos.avg_entry_price = (old_value + new_value) / new_quantity
                pos.quantity = new_quantity
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=fill_qty,
                avg_entry_price=fill_price,
                current_price=fill_price,
                unrealized_pnl=0,
                realized_pnl=0,
                opened_at=datetime.now(),
                stop_loss=fill_price * (1 - self.default_stop_loss_pct) if fill_qty > 0 else fill_price * (1 + self.default_stop_loss_pct),
                take_profit=fill_price * (1 + self.default_take_profit_pct) if fill_qty > 0 else fill_price * (1 - self.default_take_profit_pct)
            )

            # Reduce available capital
            self.available_capital -= abs(fill_qty) * fill_price

    def _update_positions(self, snapshot: MarketSnapshot):
        """Update position values from market prices"""
        for symbol, pos in self.positions.items():
            if symbol in snapshot.prices:
                pos.current_price = snapshot.prices[symbol]

                if pos.quantity > 0:
                    pos.unrealized_pnl = (pos.current_price - pos.avg_entry_price) * pos.quantity
                else:
                    pos.unrealized_pnl = (pos.avg_entry_price - pos.current_price) * abs(pos.quantity)

    def _check_position_exits(self, snapshot: MarketSnapshot) -> Optional[Signal]:
        """Check if any position should be exited"""
        for symbol, pos in list(self.positions.items()):
            current_price = snapshot.prices.get(symbol, pos.current_price)

            # Check stop loss
            if pos.stop_loss:
                if pos.quantity > 0 and current_price <= pos.stop_loss:
                    return self._create_exit_signal(symbol, 'Stop loss hit', 'sell')
                elif pos.quantity < 0 and current_price >= pos.stop_loss:
                    return self._create_exit_signal(symbol, 'Stop loss hit', 'buy')

            # Check take profit
            if pos.take_profit:
                if pos.quantity > 0 and current_price >= pos.take_profit:
                    return self._create_exit_signal(symbol, 'Take profit reached', 'sell')
                elif pos.quantity < 0 and current_price <= pos.take_profit:
                    return self._create_exit_signal(symbol, 'Take profit reached', 'buy')

            # Check trailing stop
            if pos.trailing_stop_pct:
                self._update_trailing_stop(pos)

        return None

    def _create_exit_signal(self, symbol: str, reason: str, side: str) -> Signal:
        """Create exit signal for position management"""
        return Signal(
            agent_id=self.agent_id,
            symbol=symbol,
            direction='long' if side == 'buy' else 'short',
            strength=SignalStrength.VERY_STRONG,
            confidence=1.0,
            reasoning=reason,
            timestamp=datetime.now(),
            expiry=datetime.now() + timedelta(minutes=5),
            metadata={'action': 'exit', 'original_side': side}
        )

    def _update_trailing_stop(self, pos: Position):
        """Update trailing stop based on current price"""
        if not pos.trailing_stop_pct:
            return

        if pos.quantity > 0:
            # Long position - trail below price
            new_stop = pos.current_price * (1 - pos.trailing_stop_pct)
            if pos.stop_loss is None or new_stop > pos.stop_loss:
                pos.stop_loss = new_stop
        else:
            # Short position - trail above price
            new_stop = pos.current_price * (1 + pos.trailing_stop_pct)
            if pos.stop_loss is None or new_stop < pos.stop_loss:
                pos.stop_loss = new_stop

    def _check_pending_orders(self, snapshot: MarketSnapshot):
        """Check and update pending orders"""
        for order_id, order in list(self.pending_orders.items()):
            # Check for timeout
            age = datetime.now() - order.created_at
            if age > timedelta(minutes=30):
                order.status = OrderStatus.EXPIRED
                self.order_history.append(order)
                del self.pending_orders[order_id]
                continue

            # Try to fill limit orders
            if order.order_type == OrderType.LIMIT and order.status == OrderStatus.SUBMITTED:
                current_price = snapshot.prices.get(order.symbol, 0)

                if order.side == 'buy' and order.limit_price and current_price <= order.limit_price:
                    self._simulate_fill(order, snapshot)
                elif order.side == 'sell' and order.limit_price and current_price >= order.limit_price:
                    self._simulate_fill(order, snapshot)

    def _execute_active_plans(self, snapshot: MarketSnapshot):
        """Execute pending slices in active plans"""
        for plan_id, plan in list(self.active_plans.items()):
            # Check if plan expired
            if datetime.now() > plan.created_at + plan.time_limit:
                del self.active_plans[plan_id]
                continue

            # Find next unexecuted slice
            for i, slice_info in enumerate(plan.slices):
                if not slice_info['executed']:
                    # Check if delay has passed
                    prev_time = plan.created_at
                    for j in range(i):
                        prev_time += timedelta(seconds=plan.slices[j]['delay'])

                    if datetime.now() >= prev_time + timedelta(seconds=slice_info['delay']):
                        self._execute_slice(plan, i, snapshot)
                    break

            # Check if plan complete
            if all(s['executed'] for s in plan.slices):
                del self.active_plans[plan_id]

    def close_position(self, symbol: str, snapshot: MarketSnapshot) -> Optional[Order]:
        """Close entire position"""
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]

        order = Order(
            order_id=generate_unique_id('order'),
            symbol=symbol,
            side='sell' if pos.quantity > 0 else 'buy',
            quantity=abs(pos.quantity),
            order_type=OrderType.MARKET,
            limit_price=None,
            stop_price=None,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            metadata={'action': 'close_position'}
        )

        self._submit_order(order, snapshot)
        return order

    def close_all_positions(self, snapshot: MarketSnapshot) -> List[Order]:
        """Close all positions"""
        orders = []
        for symbol in list(self.positions.keys()):
            order = self.close_position(symbol, snapshot)
            if order:
                orders.append(order)
        return orders

    def set_stop_loss(self, symbol: str, stop_price: float):
        """Set stop loss for position"""
        if symbol in self.positions:
            self.positions[symbol].stop_loss = stop_price

    def set_take_profit(self, symbol: str, take_price: float):
        """Set take profit for position"""
        if symbol in self.positions:
            self.positions[symbol].take_profit = take_price

    def set_trailing_stop(self, symbol: str, trail_pct: float):
        """Set trailing stop for position"""
        if symbol in self.positions:
            self.positions[symbol].trailing_stop_pct = trail_pct
            self._update_trailing_stop(self.positions[symbol])

    def enable_trading(self, paper_mode: bool = True):
        """Enable trading"""
        self.trading_enabled = True
        self.paper_trading = paper_mode

    def disable_trading(self):
        """Disable trading"""
        self.trading_enabled = False

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary"""
        total_value = self.available_capital
        total_unrealized = 0

        positions_list = []
        for symbol, pos in self.positions.items():
            pos_value = abs(pos.quantity) * pos.current_price
            total_value += pos_value
            total_unrealized += pos.unrealized_pnl

            positions_list.append({
                'symbol': symbol,
                'quantity': pos.quantity,
                'entry_price': round(pos.avg_entry_price, 2),
                'current_price': round(pos.current_price, 2),
                'unrealized_pnl': round(pos.unrealized_pnl, 2),
                'stop_loss': round(pos.stop_loss, 2) if pos.stop_loss else None,
                'take_profit': round(pos.take_profit, 2) if pos.take_profit else None
            })

        return {
            'total_value': round(total_value, 2),
            'available_capital': round(self.available_capital, 2),
            'unrealized_pnl': round(total_unrealized, 2),
            'daily_pnl': round(self.daily_pnl, 2),
            'total_return': round((total_value - self.initial_capital) / self.initial_capital * 100, 2),
            'positions': positions_list,
            'pending_orders': len(self.pending_orders),
            'session_trades': self.session_trades,
            'win_rate': round(self.winning_trades / self.total_trades * 100, 1) if self.total_trades > 0 else 0,
            'avg_slippage': round(self.total_slippage / self.total_trades * 100, 3) if self.total_trades > 0 else 0,
            'trading_enabled': self.trading_enabled,
            'paper_mode': self.paper_trading
        }

    def learn(self, feedback: Dict[str, Any]):
        """Learn from trade outcomes"""
        outcome = feedback.get('outcome', 0)

        if outcome > 0:
            self.correct_signals += 1

        self.memory.record_trade(feedback, outcome)
