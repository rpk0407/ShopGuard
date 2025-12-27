"""
Smart Order Routing (SOR)

Routes orders to venues to minimize execution cost:
- Exchange fees
- Market impact
- Information leakage
- Latency

Modern markets are fragmented - SOR is essential.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from collections import deque


class VenueType(Enum):
    """Types of execution venues."""
    PRIMARY_EXCHANGE = "primary"  # NYSE, NASDAQ
    REGIONAL_EXCHANGE = "regional"  # BATS, IEX
    DARK_POOL = "dark_pool"  # Crossing networks
    ECN = "ecn"  # Electronic Communication Network
    MARKET_MAKER = "market_maker"  # Internalization
    ATS = "ats"  # Alternative Trading System


class RoutingStrategy(Enum):
    """Order routing strategies."""
    BEST_PRICE = "best_price"  # Route to best price
    BEST_LIQUIDITY = "best_liquidity"  # Route to deepest book
    MINIMIZE_IMPACT = "minimize_impact"  # Split to reduce impact
    MINIMIZE_COST = "minimize_cost"  # Optimize total cost
    SPEED = "speed"  # Fastest execution
    DARK_FIRST = "dark_first"  # Try dark pools first


@dataclass
class Venue:
    """Execution venue."""
    id: str
    name: str
    venue_type: VenueType

    # Fee structure
    maker_fee: float  # Fee for adding liquidity (negative = rebate)
    taker_fee: float  # Fee for taking liquidity

    # Performance metrics
    latency_us: float  # Round-trip latency in microseconds
    fill_rate: float  # Historical fill rate (0-1)
    avg_spread: float  # Average spread in bps

    # Current state
    is_available: bool = True
    current_latency_us: float = 0


@dataclass
class VenueLiquidity:
    """Current liquidity at a venue."""
    venue_id: str
    bid_price: float
    bid_size: int
    ask_price: float
    ask_size: int
    timestamp: datetime

    @property
    def spread(self) -> float:
        """Spread in absolute terms."""
        return self.ask_price - self.bid_price

    @property
    def spread_bps(self) -> float:
        """Spread in basis points."""
        mid = (self.bid_price + self.ask_price) / 2
        return self.spread / mid * 10000 if mid > 0 else 0

    @property
    def mid_price(self) -> float:
        """Mid price."""
        return (self.bid_price + self.ask_price) / 2


@dataclass
class RoutedOrder:
    """Order routed to a venue."""
    venue_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    order_type: str  # 'limit', 'market', 'ioc'
    limit_price: Optional[float]
    priority: int = 1  # 1 = highest priority


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    orders: List[RoutedOrder]
    expected_fill_rate: float
    expected_cost_bps: float
    expected_latency_us: float
    rationale: str


class VenueSelection:
    """
    Venue selection and ranking.

    Scores venues based on multiple criteria:
    - Price improvement potential
    - Fill probability
    - Total cost (fees + spread)
    - Latency
    """

    def __init__(self, venues: Dict[str, Venue]):
        """
        Initialize venue selector.

        Args:
            venues: Dictionary of venue_id -> Venue
        """
        self.venues = venues

        # Track venue performance
        self.venue_metrics: Dict[str, Dict] = {
            v_id: {
                'fills': deque(maxlen=1000),
                'costs': deque(maxlen=1000),
                'latencies': deque(maxlen=1000)
            }
            for v_id in venues
        }

    def score_venue(
        self,
        venue_id: str,
        liquidity: VenueLiquidity,
        side: str,
        quantity: int,
        urgency: float = 0.5
    ) -> Tuple[float, Dict]:
        """
        Score a venue for an order.

        Returns (score, breakdown).
        Higher score = better venue.
        """
        venue = self.venues.get(venue_id)
        if not venue or not venue.is_available:
            return 0.0, {'reason': 'unavailable'}

        # Price score (how good is the price vs NBBO?)
        if side == 'buy':
            price = liquidity.ask_price
            available = liquidity.ask_size
        else:
            price = liquidity.bid_price
            available = liquidity.bid_size

        price_score = 1.0  # Base score

        # Adjust for spread
        spread_penalty = liquidity.spread_bps / 10  # Normalize
        price_score -= spread_penalty

        # Liquidity score (can we fill here?)
        fill_ratio = min(1.0, available / quantity) if quantity > 0 else 0
        liquidity_score = fill_ratio * venue.fill_rate

        # Cost score (fees)
        # Assume we're taking liquidity for urgency > 0.5
        if urgency > 0.5:
            fee_bps = venue.taker_fee * 10000
        else:
            fee_bps = venue.maker_fee * 10000

        cost_score = 1.0 - abs(fee_bps) / 10  # Normalize

        # Latency score (matters more for urgent orders)
        latency_score = 1.0 - (venue.latency_us / 1000) * urgency

        # Combine scores
        if urgency > 0.7:
            # Urgent: prioritize speed and fill
            weights = {
                'price': 0.2,
                'liquidity': 0.4,
                'cost': 0.1,
                'latency': 0.3
            }
        else:
            # Patient: prioritize price and cost
            weights = {
                'price': 0.4,
                'liquidity': 0.2,
                'cost': 0.3,
                'latency': 0.1
            }

        total_score = (
            weights['price'] * price_score +
            weights['liquidity'] * liquidity_score +
            weights['cost'] * cost_score +
            weights['latency'] * latency_score
        )

        breakdown = {
            'price_score': price_score,
            'liquidity_score': liquidity_score,
            'cost_score': cost_score,
            'latency_score': latency_score,
            'weights': weights
        }

        return max(0, total_score), breakdown

    def rank_venues(
        self,
        liquidity: Dict[str, VenueLiquidity],
        side: str,
        quantity: int,
        urgency: float = 0.5
    ) -> List[Tuple[str, float, Dict]]:
        """
        Rank venues for an order.

        Returns list of (venue_id, score, breakdown) sorted by score.
        """
        rankings = []

        for venue_id, liq in liquidity.items():
            score, breakdown = self.score_venue(
                venue_id, liq, side, quantity, urgency
            )
            if score > 0:
                rankings.append((venue_id, score, breakdown))

        # Sort by score descending
        rankings.sort(key=lambda x: x[1], reverse=True)

        return rankings

    def update_metrics(
        self,
        venue_id: str,
        was_filled: bool,
        cost_bps: float,
        latency_us: float
    ):
        """Update venue performance metrics."""
        if venue_id in self.venue_metrics:
            self.venue_metrics[venue_id]['fills'].append(was_filled)
            self.venue_metrics[venue_id]['costs'].append(cost_bps)
            self.venue_metrics[venue_id]['latencies'].append(latency_us)

    def get_venue_stats(self, venue_id: str) -> Dict:
        """Get performance statistics for a venue."""
        if venue_id not in self.venue_metrics:
            return {}

        metrics = self.venue_metrics[venue_id]

        fills = list(metrics['fills'])
        costs = list(metrics['costs'])
        latencies = list(metrics['latencies'])

        return {
            'fill_rate': np.mean(fills) if fills else 0,
            'avg_cost_bps': np.mean(costs) if costs else 0,
            'avg_latency_us': np.mean(latencies) if latencies else 0,
            'sample_size': len(fills)
        }


class SmartOrderRouter:
    """
    Smart Order Router for optimal execution.

    Routes orders across venues to minimize total cost:
    - Explicit costs (fees)
    - Implicit costs (spread, impact)
    - Opportunity costs (timing)
    """

    def __init__(
        self,
        venues: Dict[str, Venue],
        default_strategy: RoutingStrategy = RoutingStrategy.MINIMIZE_COST
    ):
        """
        Initialize smart order router.

        Args:
            venues: Available execution venues
            default_strategy: Default routing strategy
        """
        self.venues = venues
        self.default_strategy = default_strategy
        self.venue_selector = VenueSelection(venues)

        # Liquidity cache
        self.liquidity_cache: Dict[str, Dict[str, VenueLiquidity]] = {}

    def update_liquidity(
        self,
        symbol: str,
        venue_id: str,
        liquidity: VenueLiquidity
    ):
        """Update liquidity for a symbol at a venue."""
        if symbol not in self.liquidity_cache:
            self.liquidity_cache[symbol] = {}
        self.liquidity_cache[symbol][venue_id] = liquidity

    def get_nbbo(self, symbol: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Get National Best Bid and Offer.

        Returns (best_bid, best_bid_size, best_ask, best_ask_size).
        """
        if symbol not in self.liquidity_cache:
            return None

        liquidity = self.liquidity_cache[symbol]

        best_bid = 0.0
        best_bid_size = 0
        best_ask = float('inf')
        best_ask_size = 0

        for liq in liquidity.values():
            if liq.bid_price > best_bid:
                best_bid = liq.bid_price
                best_bid_size = liq.bid_size
            elif liq.bid_price == best_bid:
                best_bid_size += liq.bid_size

            if liq.ask_price < best_ask:
                best_ask = liq.ask_price
                best_ask_size = liq.ask_size
            elif liq.ask_price == best_ask:
                best_ask_size += liq.ask_size

        if best_ask == float('inf'):
            return None

        return best_bid, best_bid_size, best_ask, best_ask_size

    def route_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        strategy: RoutingStrategy = None,
        urgency: float = 0.5,
        limit_price: Optional[float] = None
    ) -> RoutingDecision:
        """
        Route an order across venues.

        Args:
            symbol: Symbol to trade
            side: 'buy' or 'sell'
            quantity: Number of shares
            strategy: Routing strategy
            urgency: How urgent (0 = patient, 1 = immediate)
            limit_price: Optional limit price

        Returns:
            RoutingDecision with orders and analysis
        """
        strategy = strategy or self.default_strategy

        if symbol not in self.liquidity_cache:
            return RoutingDecision(
                orders=[],
                expected_fill_rate=0,
                expected_cost_bps=0,
                expected_latency_us=0,
                rationale="No liquidity data available"
            )

        liquidity = self.liquidity_cache[symbol]

        if strategy == RoutingStrategy.BEST_PRICE:
            return self._route_best_price(symbol, side, quantity, liquidity, limit_price)
        elif strategy == RoutingStrategy.BEST_LIQUIDITY:
            return self._route_best_liquidity(symbol, side, quantity, liquidity, limit_price)
        elif strategy == RoutingStrategy.MINIMIZE_IMPACT:
            return self._route_minimize_impact(symbol, side, quantity, liquidity, limit_price)
        elif strategy == RoutingStrategy.MINIMIZE_COST:
            return self._route_minimize_cost(symbol, side, quantity, liquidity, urgency, limit_price)
        elif strategy == RoutingStrategy.DARK_FIRST:
            return self._route_dark_first(symbol, side, quantity, liquidity, limit_price)
        else:
            return self._route_minimize_cost(symbol, side, quantity, liquidity, urgency, limit_price)

    def _route_best_price(
        self,
        symbol: str,
        side: str,
        quantity: int,
        liquidity: Dict[str, VenueLiquidity],
        limit_price: Optional[float]
    ) -> RoutingDecision:
        """Route to venue with best price."""
        best_venue = None
        best_price = float('inf') if side == 'buy' else 0.0

        for venue_id, liq in liquidity.items():
            if side == 'buy':
                if liq.ask_price < best_price:
                    best_price = liq.ask_price
                    best_venue = venue_id
            else:
                if liq.bid_price > best_price:
                    best_price = liq.bid_price
                    best_venue = venue_id

        if not best_venue:
            return RoutingDecision(
                orders=[],
                expected_fill_rate=0,
                expected_cost_bps=0,
                expected_latency_us=0,
                rationale="No venue available"
            )

        order = RoutedOrder(
            venue_id=best_venue,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type='limit' if limit_price else 'ioc',
            limit_price=limit_price or best_price
        )

        return RoutingDecision(
            orders=[order],
            expected_fill_rate=0.8,
            expected_cost_bps=self._estimate_cost([order], liquidity),
            expected_latency_us=self.venues[best_venue].latency_us,
            rationale=f"Best price at {best_venue}"
        )

    def _route_best_liquidity(
        self,
        symbol: str,
        side: str,
        quantity: int,
        liquidity: Dict[str, VenueLiquidity],
        limit_price: Optional[float]
    ) -> RoutingDecision:
        """Route to venue with most liquidity."""
        best_venue = None
        best_size = 0

        for venue_id, liq in liquidity.items():
            size = liq.ask_size if side == 'buy' else liq.bid_size
            if size > best_size:
                best_size = size
                best_venue = venue_id

        if not best_venue:
            return RoutingDecision(
                orders=[],
                expected_fill_rate=0,
                expected_cost_bps=0,
                expected_latency_us=0,
                rationale="No venue available"
            )

        liq = liquidity[best_venue]
        price = liq.ask_price if side == 'buy' else liq.bid_price

        order = RoutedOrder(
            venue_id=best_venue,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type='limit',
            limit_price=limit_price or price
        )

        fill_rate = min(1.0, best_size / quantity)

        return RoutingDecision(
            orders=[order],
            expected_fill_rate=fill_rate,
            expected_cost_bps=self._estimate_cost([order], liquidity),
            expected_latency_us=self.venues[best_venue].latency_us,
            rationale=f"Most liquidity at {best_venue} ({best_size} shares)"
        )

    def _route_minimize_impact(
        self,
        symbol: str,
        side: str,
        quantity: int,
        liquidity: Dict[str, VenueLiquidity],
        limit_price: Optional[float]
    ) -> RoutingDecision:
        """
        Split order across venues to minimize market impact.

        Large orders should be split to avoid moving the market.
        """
        orders = []
        remaining = quantity

        # Sort venues by available liquidity
        sorted_venues = sorted(
            liquidity.items(),
            key=lambda x: x[1].ask_size if side == 'buy' else x[1].bid_size,
            reverse=True
        )

        for venue_id, liq in sorted_venues:
            if remaining <= 0:
                break

            available = liq.ask_size if side == 'buy' else liq.bid_size
            price = liq.ask_price if side == 'buy' else liq.bid_price

            # Take up to 20% of available liquidity to minimize impact
            order_qty = min(remaining, int(available * 0.2))

            if order_qty > 0:
                orders.append(RoutedOrder(
                    venue_id=venue_id,
                    symbol=symbol,
                    side=side,
                    quantity=order_qty,
                    order_type='limit',
                    limit_price=limit_price or price,
                    priority=len(orders) + 1
                ))
                remaining -= order_qty

        if not orders:
            return RoutingDecision(
                orders=[],
                expected_fill_rate=0,
                expected_cost_bps=0,
                expected_latency_us=0,
                rationale="Could not route order"
            )

        total_routed = sum(o.quantity for o in orders)
        fill_rate = total_routed / quantity

        return RoutingDecision(
            orders=orders,
            expected_fill_rate=fill_rate,
            expected_cost_bps=self._estimate_cost(orders, liquidity),
            expected_latency_us=max(self.venues[o.venue_id].latency_us for o in orders),
            rationale=f"Split across {len(orders)} venues to minimize impact"
        )

    def _route_minimize_cost(
        self,
        symbol: str,
        side: str,
        quantity: int,
        liquidity: Dict[str, VenueLiquidity],
        urgency: float,
        limit_price: Optional[float]
    ) -> RoutingDecision:
        """
        Route to minimize total execution cost.

        Considers:
        - Exchange fees
        - Spread cost
        - Expected market impact
        """
        # Rank venues
        rankings = self.venue_selector.rank_venues(
            liquidity, side, quantity, urgency
        )

        if not rankings:
            return RoutingDecision(
                orders=[],
                expected_fill_rate=0,
                expected_cost_bps=0,
                expected_latency_us=0,
                rationale="No suitable venue"
            )

        orders = []
        remaining = quantity

        for venue_id, score, _ in rankings:
            if remaining <= 0:
                break

            liq = liquidity[venue_id]
            available = liq.ask_size if side == 'buy' else liq.bid_size
            price = liq.ask_price if side == 'buy' else liq.bid_price

            order_qty = min(remaining, available)

            if order_qty > 0:
                orders.append(RoutedOrder(
                    venue_id=venue_id,
                    symbol=symbol,
                    side=side,
                    quantity=order_qty,
                    order_type='limit',
                    limit_price=limit_price or price,
                    priority=len(orders) + 1
                ))
                remaining -= order_qty

        total_routed = sum(o.quantity for o in orders)
        fill_rate = total_routed / quantity if quantity > 0 else 0

        return RoutingDecision(
            orders=orders,
            expected_fill_rate=fill_rate,
            expected_cost_bps=self._estimate_cost(orders, liquidity),
            expected_latency_us=np.mean([self.venues[o.venue_id].latency_us for o in orders]) if orders else 0,
            rationale=f"Cost-optimized routing across {len(orders)} venues"
        )

    def _route_dark_first(
        self,
        symbol: str,
        side: str,
        quantity: int,
        liquidity: Dict[str, VenueLiquidity],
        limit_price: Optional[float]
    ) -> RoutingDecision:
        """
        Try dark pools first to minimize information leakage.

        Dark pools don't display orders, reducing market impact.
        """
        orders = []
        remaining = quantity

        # First, try dark pools
        dark_venues = [
            v_id for v_id, v in self.venues.items()
            if v.venue_type == VenueType.DARK_POOL and v_id in liquidity
        ]

        for venue_id in dark_venues:
            if remaining <= 0:
                break

            liq = liquidity[venue_id]
            available = liq.ask_size if side == 'buy' else liq.bid_size
            price = liq.ask_price if side == 'buy' else liq.bid_price

            order_qty = min(remaining, available)

            if order_qty > 0:
                orders.append(RoutedOrder(
                    venue_id=venue_id,
                    symbol=symbol,
                    side=side,
                    quantity=order_qty,
                    order_type='limit',
                    limit_price=limit_price or price,
                    priority=1  # High priority for dark
                ))
                remaining -= order_qty

        # Then, route remaining to lit venues
        if remaining > 0:
            lit_venues = [
                v_id for v_id, v in self.venues.items()
                if v.venue_type != VenueType.DARK_POOL and v_id in liquidity
            ]

            for venue_id in lit_venues:
                if remaining <= 0:
                    break

                liq = liquidity[venue_id]
                available = liq.ask_size if side == 'buy' else liq.bid_size
                price = liq.ask_price if side == 'buy' else liq.bid_price

                order_qty = min(remaining, available)

                if order_qty > 0:
                    orders.append(RoutedOrder(
                        venue_id=venue_id,
                        symbol=symbol,
                        side=side,
                        quantity=order_qty,
                        order_type='limit',
                        limit_price=limit_price or price,
                        priority=2  # Lower priority for lit
                    ))
                    remaining -= order_qty

        total_routed = sum(o.quantity for o in orders)
        fill_rate = total_routed / quantity if quantity > 0 else 0

        dark_qty = sum(o.quantity for o in orders if o.priority == 1)

        return RoutingDecision(
            orders=orders,
            expected_fill_rate=fill_rate,
            expected_cost_bps=self._estimate_cost(orders, liquidity),
            expected_latency_us=np.mean([self.venues[o.venue_id].latency_us for o in orders]) if orders else 0,
            rationale=f"Dark first: {dark_qty}/{quantity} shares to dark pools"
        )

    def _estimate_cost(
        self,
        orders: List[RoutedOrder],
        liquidity: Dict[str, VenueLiquidity]
    ) -> float:
        """Estimate total execution cost in basis points."""
        if not orders:
            return 0.0

        total_cost = 0.0
        total_value = 0.0

        for order in orders:
            venue = self.venues[order.venue_id]
            liq = liquidity.get(order.venue_id)

            if not liq:
                continue

            # Price
            price = order.limit_price or (
                liq.ask_price if order.side == 'buy' else liq.bid_price
            )
            value = price * order.quantity

            # Fee (assume taker)
            fee = abs(venue.taker_fee) * value

            # Half spread
            spread_cost = (liq.spread_bps / 2 / 10000) * value

            total_cost += fee + spread_cost
            total_value += value

        if total_value == 0:
            return 0.0

        return (total_cost / total_value) * 10000  # In bps

    def analyze_routing(
        self,
        symbol: str,
        side: str,
        quantity: int
    ) -> Dict:
        """
        Analyze all routing strategies for an order.

        Useful for comparing strategies.
        """
        strategies = [
            RoutingStrategy.BEST_PRICE,
            RoutingStrategy.BEST_LIQUIDITY,
            RoutingStrategy.MINIMIZE_IMPACT,
            RoutingStrategy.MINIMIZE_COST,
            RoutingStrategy.DARK_FIRST
        ]

        results = {}

        for strategy in strategies:
            decision = self.route_order(symbol, side, quantity, strategy)
            results[strategy.value] = {
                'num_venues': len(decision.orders),
                'expected_fill_rate': decision.expected_fill_rate,
                'expected_cost_bps': decision.expected_cost_bps,
                'expected_latency_us': decision.expected_latency_us,
                'rationale': decision.rationale
            }

        return results
