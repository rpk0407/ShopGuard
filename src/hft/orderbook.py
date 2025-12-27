"""
Limit Order Book Analysis and Modeling

The limit order book (LOB) is the fundamental structure of modern markets.
Understanding its dynamics is essential for:
1. Price prediction (short-term)
2. Execution optimization
3. Market making
4. Detecting informed trading

LOB Structure:
- Bid side: Buy orders (decreasing price)
- Ask side: Sell orders (increasing price)
- Spread: Best ask - Best bid
- Depth: Volume at each price level
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque
from datetime import datetime
import heapq


@dataclass
class OrderBookLevel:
    """Single price level in order book."""
    price: float
    quantity: float
    order_count: int = 1
    last_update: datetime = None


@dataclass
class OrderBookState:
    """Complete order book snapshot."""
    symbol: str
    timestamp: datetime
    bids: List[OrderBookLevel]  # Best bid first
    asks: List[OrderBookLevel]  # Best ask first
    sequence: int = 0

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> float:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return 0

    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return float('inf')

    @property
    def spread_bps(self) -> float:
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 10000
        return float('inf')

    @property
    def microprice(self) -> float:
        """
        Microprice: Volume-weighted mid price.

        Accounts for imbalance at best levels.
        Better short-term price predictor than mid.
        """
        if not self.best_bid or not self.best_ask:
            return self.mid_price

        bid_vol = self.best_bid.quantity
        ask_vol = self.best_ask.quantity
        total = bid_vol + ask_vol

        if total == 0:
            return self.mid_price

        return (
            self.best_ask.price * bid_vol +
            self.best_bid.price * ask_vol
        ) / total


@dataclass
class LOBFeatures:
    """
    Features extracted from limit order book.

    These are the inputs to ML models for price prediction.
    """
    # Price features
    mid_price: float
    microprice: float
    spread: float
    spread_bps: float

    # Depth features
    bid_depth_1: float       # Best bid size
    ask_depth_1: float       # Best ask size
    bid_depth_5: float       # Top 5 bid levels
    ask_depth_5: float       # Top 5 ask levels
    bid_depth_10: float      # Top 10 levels
    ask_depth_10: float

    # Imbalance features
    imbalance_1: float       # (bid1 - ask1) / (bid1 + ask1)
    imbalance_5: float       # Top 5 levels imbalance
    imbalance_10: float      # Top 10 levels imbalance
    weighted_imbalance: float  # Distance-weighted

    # Pressure features
    bid_pressure: float      # Rate of bid additions
    ask_pressure: float      # Rate of ask additions
    net_pressure: float      # Net order flow

    # Volatility features
    price_volatility: float   # Recent price moves
    spread_volatility: float  # Spread variability

    # Derived features
    kyle_lambda: float       # Price impact coefficient
    depth_ratio: float       # bid_depth / ask_depth
    order_flow_toxicity: float


class OrderBookAnalyzer:
    """
    Real-time order book analysis.

    Computes features and signals from LOB dynamics.
    """

    def __init__(self, depth_levels: int = 10, history_length: int = 100):
        """
        Initialize analyzer.

        Args:
            depth_levels: Number of price levels to track
            history_length: Number of snapshots to keep
        """
        self.depth_levels = depth_levels
        self.history_length = history_length

        # Historical data
        self.snapshots: deque = deque(maxlen=history_length)
        self.trade_flow: deque = deque(maxlen=1000)
        self.mid_prices: deque = deque(maxlen=history_length)

        # Running statistics
        self.total_bid_adds = 0
        self.total_ask_adds = 0
        self.total_bid_cancels = 0
        self.total_ask_cancels = 0

    def update(self, state: OrderBookState):
        """Update analyzer with new order book snapshot."""
        self.snapshots.append(state)
        self.mid_prices.append(state.mid_price)

    def record_trade(
        self,
        price: float,
        quantity: float,
        side: str,
        timestamp: datetime
    ):
        """Record a trade execution."""
        self.trade_flow.append({
            'price': price,
            'quantity': quantity,
            'side': side,
            'timestamp': timestamp
        })

    def compute_features(self, state: OrderBookState) -> LOBFeatures:
        """
        Compute full feature set from current order book.

        These features are predictive of short-term price moves.
        """
        # Basic price features
        mid_price = state.mid_price
        microprice = state.microprice
        spread = state.spread
        spread_bps = state.spread_bps

        # Depth features
        bid_depths = self._compute_cumulative_depth(state.bids, [1, 5, 10])
        ask_depths = self._compute_cumulative_depth(state.asks, [1, 5, 10])

        # Imbalance features
        imbalances = self._compute_imbalances(state)

        # Pressure features (from recent history)
        pressure = self._compute_pressure()

        # Volatility
        volatility = self._compute_volatility()

        # Kyle's lambda (price impact)
        kyle_lambda = self._estimate_kyle_lambda()

        # Order flow toxicity (VPIN-like)
        toxicity = self._compute_toxicity()

        return LOBFeatures(
            mid_price=mid_price,
            microprice=microprice,
            spread=spread,
            spread_bps=spread_bps,
            bid_depth_1=bid_depths[0],
            ask_depth_1=ask_depths[0],
            bid_depth_5=bid_depths[1],
            ask_depth_5=ask_depths[1],
            bid_depth_10=bid_depths[2],
            ask_depth_10=ask_depths[2],
            imbalance_1=imbalances['level_1'],
            imbalance_5=imbalances['level_5'],
            imbalance_10=imbalances['level_10'],
            weighted_imbalance=imbalances['weighted'],
            bid_pressure=pressure['bid'],
            ask_pressure=pressure['ask'],
            net_pressure=pressure['net'],
            price_volatility=volatility['price'],
            spread_volatility=volatility['spread'],
            kyle_lambda=kyle_lambda,
            depth_ratio=bid_depths[2] / (ask_depths[2] + 1e-10),
            order_flow_toxicity=toxicity
        )

    def _compute_cumulative_depth(
        self,
        levels: List[OrderBookLevel],
        depths: List[int]
    ) -> List[float]:
        """Compute cumulative depth at various levels."""
        results = []
        cumsum = 0

        for target_depth in depths:
            for i, level in enumerate(levels[:target_depth]):
                if i < len(levels):
                    cumsum += levels[i].quantity
            results.append(cumsum)

        return results

    def _compute_imbalances(self, state: OrderBookState) -> Dict[str, float]:
        """
        Compute order book imbalances at various depths.

        Imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        Positive = buying pressure, Negative = selling pressure
        """
        results = {}

        for depth, name in [(1, 'level_1'), (5, 'level_5'), (10, 'level_10')]:
            bid_vol = sum(l.quantity for l in state.bids[:depth])
            ask_vol = sum(l.quantity for l in state.asks[:depth])
            total = bid_vol + ask_vol

            if total > 0:
                results[name] = (bid_vol - ask_vol) / total
            else:
                results[name] = 0

        # Weighted imbalance (closer levels weighted more)
        weighted_bid = sum(
            l.quantity / (i + 1)
            for i, l in enumerate(state.bids[:10])
        )
        weighted_ask = sum(
            l.quantity / (i + 1)
            for i, l in enumerate(state.asks[:10])
        )
        total_weighted = weighted_bid + weighted_ask

        if total_weighted > 0:
            results['weighted'] = (weighted_bid - weighted_ask) / total_weighted
        else:
            results['weighted'] = 0

        return results

    def _compute_pressure(self) -> Dict[str, float]:
        """Compute order flow pressure from recent activity."""
        if len(self.trade_flow) < 2:
            return {'bid': 0, 'ask': 0, 'net': 0}

        recent_trades = list(self.trade_flow)[-100:]

        buy_volume = sum(t['quantity'] for t in recent_trades if t['side'] == 'buy')
        sell_volume = sum(t['quantity'] for t in recent_trades if t['side'] == 'sell')
        total = buy_volume + sell_volume

        if total > 0:
            return {
                'bid': buy_volume / total,
                'ask': sell_volume / total,
                'net': (buy_volume - sell_volume) / total
            }
        return {'bid': 0.5, 'ask': 0.5, 'net': 0}

    def _compute_volatility(self) -> Dict[str, float]:
        """Compute recent volatility measures."""
        if len(self.mid_prices) < 10:
            return {'price': 0, 'spread': 0}

        prices = np.array(self.mid_prices)
        returns = np.diff(prices) / prices[:-1]

        spreads = [s.spread for s in self.snapshots if hasattr(s, 'spread')]

        return {
            'price': np.std(returns) if len(returns) > 0 else 0,
            'spread': np.std(spreads) if len(spreads) > 1 else 0
        }

    def _estimate_kyle_lambda(self) -> float:
        """
        Estimate Kyle's lambda (price impact coefficient).

        ΔP = λ * (Buy Volume - Sell Volume)

        Higher lambda = less liquid, more price impact.
        """
        if len(self.trade_flow) < 20 or len(self.mid_prices) < 20:
            return 0

        # Use regression approach
        price_changes = np.diff(list(self.mid_prices)[-20:])

        # Compute signed volume (OFI) for each period
        recent_trades = list(self.trade_flow)[-20:]
        signed_volumes = []

        for t in recent_trades:
            if t['side'] == 'buy':
                signed_volumes.append(t['quantity'])
            else:
                signed_volumes.append(-t['quantity'])

        if len(price_changes) != len(signed_volumes):
            return 0

        # Simple regression: lambda = cov(ΔP, OFI) / var(OFI)
        signed_volumes = np.array(signed_volumes[:len(price_changes)])
        var_ofi = np.var(signed_volumes)

        if var_ofi > 0:
            return np.cov(price_changes, signed_volumes)[0, 1] / var_ofi
        return 0

    def _compute_toxicity(self) -> float:
        """
        Compute order flow toxicity (VPIN-inspired).

        Toxic flow = informed traders trading aggressively.
        High toxicity often precedes volatility.
        """
        if len(self.trade_flow) < 50:
            return 0

        recent = list(self.trade_flow)[-50:]

        buy_volume = sum(t['quantity'] for t in recent if t['side'] == 'buy')
        sell_volume = sum(t['quantity'] for t in recent if t['side'] == 'sell')
        total = buy_volume + sell_volume

        if total == 0:
            return 0

        # Toxicity = |buy - sell| / total (imbalance ratio)
        return abs(buy_volume - sell_volume) / total


class OrderFlowImbalance:
    """
    Order Flow Imbalance (OFI) Computation

    OFI measures the net buying/selling pressure at each price level.
    It's computed from changes in the order book.

    OFI_t = Σ (ΔBid_n - ΔAsk_n)

    Strong predictor of short-term price moves.
    """

    def __init__(self):
        self.prev_bids: Dict[float, float] = {}
        self.prev_asks: Dict[float, float] = {}
        self.ofi_history: deque = deque(maxlen=1000)

    def compute(self, state: OrderBookState) -> float:
        """
        Compute OFI from current and previous state.

        Returns:
            Net order flow imbalance (positive = buying pressure)
        """
        ofi = 0

        # Process bid changes
        current_bids = {l.price: l.quantity for l in state.bids}

        for price, qty in current_bids.items():
            prev_qty = self.prev_bids.get(price, 0)
            if qty > prev_qty:
                # Bid size increased (buying interest)
                ofi += (qty - prev_qty)
            elif qty < prev_qty:
                # Bid size decreased (less buying interest)
                ofi -= (prev_qty - qty)

        # Process ask changes
        current_asks = {l.price: l.quantity for l in state.asks}

        for price, qty in current_asks.items():
            prev_qty = self.prev_asks.get(price, 0)
            if qty > prev_qty:
                # Ask size increased (selling interest)
                ofi -= (qty - prev_qty)
            elif qty < prev_qty:
                # Ask size decreased (less selling interest)
                ofi += (prev_qty - qty)

        # Update state
        self.prev_bids = current_bids
        self.prev_asks = current_asks
        self.ofi_history.append(ofi)

        return ofi

    def get_cumulative_ofi(self, n: int = 10) -> float:
        """Get cumulative OFI over last n updates."""
        if len(self.ofi_history) < n:
            return sum(self.ofi_history)
        return sum(list(self.ofi_history)[-n:])


class PriceImpactModel:
    """
    Price impact modeling for execution optimization.

    Models how our orders affect market prices.
    Critical for optimal execution of large orders.
    """

    def __init__(self):
        self.impact_history: List[Tuple[float, float]] = []  # (size, impact)

    def estimate_impact(
        self,
        order_size: float,
        state: OrderBookState,
        side: str
    ) -> float:
        """
        Estimate price impact of an order.

        Uses square-root model: Impact ∝ √(size / ADV)

        Args:
            order_size: Size of order to execute
            state: Current order book
            side: 'buy' or 'sell'

        Returns:
            Estimated price impact in basis points
        """
        # Immediate impact: walk through order book
        if side == 'buy':
            levels = state.asks
        else:
            levels = state.bids

        remaining = order_size
        total_cost = 0
        mid = state.mid_price

        for level in levels:
            if remaining <= 0:
                break

            fill_qty = min(remaining, level.quantity)
            total_cost += fill_qty * level.price
            remaining -= fill_qty

        if order_size > 0:
            avg_price = total_cost / order_size
            immediate_impact = abs(avg_price - mid) / mid * 10000
        else:
            immediate_impact = 0

        # Permanent impact (square-root model)
        # Calibrate from historical data
        sigma = 0.02  # Daily volatility
        adv = 1000000  # Average daily volume (should be calibrated)
        participation = order_size / adv

        permanent_impact = sigma * np.sqrt(participation) * 10000

        return immediate_impact + permanent_impact

    def optimal_execution_schedule(
        self,
        total_size: float,
        time_horizon: int,
        urgency: float = 0.5
    ) -> np.ndarray:
        """
        Compute optimal execution schedule (Almgren-Chriss).

        Trades off:
        - Execution risk (variance from delayed execution)
        - Market impact (cost from aggressive execution)

        Args:
            total_size: Total quantity to execute
            time_horizon: Number of periods to execute over
            urgency: 0 = patient (minimize impact), 1 = urgent (minimize risk)

        Returns:
            Array of quantities to trade each period
        """
        # Almgren-Chriss optimal schedule
        # x_t = X * (1 - t/T) for linear schedule
        # Adjust for urgency

        n = time_horizon
        schedule = np.zeros(n)

        if urgency >= 1:
            # Execute immediately
            schedule[0] = total_size
        elif urgency <= 0:
            # Execute uniformly
            schedule = np.ones(n) * total_size / n
        else:
            # Interpolate between TWAP and front-loaded
            # Higher urgency = more front-loaded
            kappa = urgency * 5  # Urgency parameter

            for t in range(n):
                schedule[t] = total_size * np.sinh(kappa * (1 - t/n)) / np.sinh(kappa)

            # Normalize to total size
            schedule = schedule / schedule.sum() * total_size

        return schedule


class OrderBookReconstructor:
    """
    Reconstruct order book from message feed.

    Processes:
    - Add order
    - Modify order
    - Delete order
    - Trade messages

    Essential for handling L3 (order-by-order) data.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[str, Dict] = {}  # order_id -> {price, qty}
        self.asks: Dict[str, Dict] = {}
        self.sequence = 0

    def add_order(
        self,
        order_id: str,
        side: str,
        price: float,
        quantity: float
    ):
        """Process add order message."""
        order = {'price': price, 'quantity': quantity}

        if side == 'buy':
            self.bids[order_id] = order
        else:
            self.asks[order_id] = order

        self.sequence += 1

    def modify_order(self, order_id: str, new_quantity: float):
        """Process modify order message."""
        if order_id in self.bids:
            self.bids[order_id]['quantity'] = new_quantity
        elif order_id in self.asks:
            self.asks[order_id]['quantity'] = new_quantity

        self.sequence += 1

    def delete_order(self, order_id: str):
        """Process delete order message."""
        self.bids.pop(order_id, None)
        self.asks.pop(order_id, None)
        self.sequence += 1

    def trade(self, order_id: str, quantity: float):
        """Process trade message (reduce order size)."""
        if order_id in self.bids:
            self.bids[order_id]['quantity'] -= quantity
            if self.bids[order_id]['quantity'] <= 0:
                del self.bids[order_id]
        elif order_id in self.asks:
            self.asks[order_id]['quantity'] -= quantity
            if self.asks[order_id]['quantity'] <= 0:
                del self.asks[order_id]

        self.sequence += 1

    def get_state(self) -> OrderBookState:
        """Get current order book state."""
        # Aggregate by price level
        bid_levels = {}
        for order in self.bids.values():
            price = order['price']
            if price not in bid_levels:
                bid_levels[price] = OrderBookLevel(price=price, quantity=0, order_count=0)
            bid_levels[price].quantity += order['quantity']
            bid_levels[price].order_count += 1

        ask_levels = {}
        for order in self.asks.values():
            price = order['price']
            if price not in ask_levels:
                ask_levels[price] = OrderBookLevel(price=price, quantity=0, order_count=0)
            ask_levels[price].quantity += order['quantity']
            ask_levels[price].order_count += 1

        # Sort (bids descending, asks ascending)
        sorted_bids = sorted(bid_levels.values(), key=lambda x: -x.price)
        sorted_asks = sorted(ask_levels.values(), key=lambda x: x.price)

        return OrderBookState(
            symbol=self.symbol,
            timestamp=datetime.now(),
            bids=sorted_bids,
            asks=sorted_asks,
            sequence=self.sequence
        )
