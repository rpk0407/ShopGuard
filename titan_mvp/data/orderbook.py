"""
Order Book Processor

Maintains Level 2 order book data for spread and depth analysis.
Secondary to trade data for this MVP, but useful for execution.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import bisect


@dataclass
class OrderBookLevel:
    """Single price level in order book."""
    price: float
    size: float

    @property
    def value(self) -> float:
        """Value at this level."""
        return self.price * self.size


@dataclass
class OrderBookSnapshot:
    """
    Point-in-time order book snapshot.

    Includes computed metrics useful for trading decisions.
    """
    timestamp: int  # milliseconds
    bids: List[OrderBookLevel]  # Sorted high to low
    asks: List[OrderBookLevel]  # Sorted low to high

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        """Highest bid."""
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        """Lowest ask."""
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        """Mid price between best bid and ask."""
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Absolute spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None

    @property
    def spread_bps(self) -> Optional[float]:
        """Spread in basis points."""
        if self.spread and self.mid_price:
            return (self.spread / self.mid_price) * 10000
        return None

    @property
    def bid_depth(self) -> float:
        """Total bid size."""
        return sum(level.size for level in self.bids)

    @property
    def ask_depth(self) -> float:
        """Total ask size."""
        return sum(level.size for level in self.asks)

    @property
    def depth_imbalance(self) -> float:
        """
        Order book imbalance: (bid_depth - ask_depth) / (bid_depth + ask_depth)
        Range: -1 (all asks) to +1 (all bids)
        """
        total = self.bid_depth + self.ask_depth
        if total == 0:
            return 0.0
        return (self.bid_depth - self.ask_depth) / total

    def bid_depth_at_pct(self, pct: float = 0.01) -> float:
        """
        Bid depth within percentage of mid price.

        Args:
            pct: Percentage (e.g., 0.01 = 1%)

        Returns:
            Total bid size within range
        """
        if not self.mid_price:
            return 0.0

        floor_price = self.mid_price * (1 - pct)
        return sum(
            level.size for level in self.bids
            if level.price >= floor_price
        )

    def ask_depth_at_pct(self, pct: float = 0.01) -> float:
        """
        Ask depth within percentage of mid price.

        Args:
            pct: Percentage (e.g., 0.01 = 1%)

        Returns:
            Total ask size within range
        """
        if not self.mid_price:
            return 0.0

        ceiling_price = self.mid_price * (1 + pct)
        return sum(
            level.size for level in self.asks
            if level.price <= ceiling_price
        )

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'bids': [(l.price, l.size) for l in self.bids],
            'asks': [(l.price, l.size) for l in self.asks],
            'mid_price': self.mid_price,
            'spread_bps': self.spread_bps,
            'depth_imbalance': self.depth_imbalance,
        }


class OrderBook:
    """
    Real-time order book manager.

    Maintains current order book state and computes metrics.
    Handles both snapshots and incremental updates.
    """

    def __init__(self, max_levels: int = 50):
        """
        Initialize order book.

        Args:
            max_levels: Maximum price levels to track per side
        """
        self.max_levels = max_levels

        # Price -> Size mapping
        self._bids: Dict[float, float] = {}
        self._asks: Dict[float, float] = {}

        # Sorted price lists for fast lookup
        self._bid_prices: List[float] = []  # Sorted descending
        self._ask_prices: List[float] = []  # Sorted ascending

        # Last update time
        self._last_update: int = 0

    def update_from_snapshot(
        self,
        timestamp: int,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]]
    ) -> None:
        """
        Update from full snapshot.

        Args:
            timestamp: Update time (milliseconds)
            bids: List of (price, size) tuples
            asks: List of (price, size) tuples
        """
        # Clear existing data
        self._bids.clear()
        self._asks.clear()

        # Add bids
        for price, size in bids[:self.max_levels]:
            if size > 0:
                self._bids[price] = size

        # Add asks
        for price, size in asks[:self.max_levels]:
            if size > 0:
                self._asks[price] = size

        # Update sorted lists
        self._bid_prices = sorted(self._bids.keys(), reverse=True)
        self._ask_prices = sorted(self._asks.keys())

        self._last_update = timestamp

    def update_level(
        self,
        timestamp: int,
        side: str,  # 'bid' or 'ask'
        price: float,
        size: float
    ) -> None:
        """
        Update single price level (incremental update).

        Args:
            timestamp: Update time
            side: 'bid' or 'ask'
            price: Price level
            size: New size (0 = remove level)
        """
        book = self._bids if side == 'bid' else self._asks
        prices = self._bid_prices if side == 'bid' else self._ask_prices

        if size > 0:
            # Add or update level
            if price not in book:
                # Insert into sorted list
                if side == 'bid':
                    # Descending order
                    idx = bisect.bisect_left([-p for p in prices], -price)
                    prices.insert(idx, price)
                else:
                    # Ascending order
                    idx = bisect.bisect_left(prices, price)
                    prices.insert(idx, price)

            book[price] = size
        else:
            # Remove level
            if price in book:
                del book[price]
                prices.remove(price)

        self._last_update = timestamp

    def get_snapshot(self) -> OrderBookSnapshot:
        """Get current order book snapshot."""
        return OrderBookSnapshot(
            timestamp=self._last_update,
            bids=[
                OrderBookLevel(price=p, size=self._bids[p])
                for p in self._bid_prices[:self.max_levels]
            ],
            asks=[
                OrderBookLevel(price=p, size=self._asks[p])
                for p in self._ask_prices[:self.max_levels]
            ],
        )

    @property
    def mid_price(self) -> Optional[float]:
        """Current mid price."""
        if not self._bid_prices or not self._ask_prices:
            return None
        return (self._bid_prices[0] + self._ask_prices[0]) / 2

    @property
    def spread(self) -> Optional[float]:
        """Current spread."""
        if not self._bid_prices or not self._ask_prices:
            return None
        return self._ask_prices[0] - self._bid_prices[0]

    @property
    def spread_bps(self) -> Optional[float]:
        """Current spread in basis points."""
        if self.spread and self.mid_price:
            return (self.spread / self.mid_price) * 10000
        return None

    def reset(self) -> None:
        """Reset order book."""
        self._bids.clear()
        self._asks.clear()
        self._bid_prices.clear()
        self._ask_prices.clear()
        self._last_update = 0
