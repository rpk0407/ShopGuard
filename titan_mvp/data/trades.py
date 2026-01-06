"""
Trade Data Processor

Processes raw trade data for CVD calculation.
This is the foundation for order flow analysis.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Deque, Callable
from collections import deque
from datetime import datetime
from enum import Enum
import statistics


class TradeSide(Enum):
    """Trade aggressor side."""
    BUY = "buy"    # Buyer was aggressor (lifted ask)
    SELL = "sell"  # Seller was aggressor (hit bid)


@dataclass
class Trade:
    """
    Single trade record.

    Attributes:
        timestamp: Trade execution time (milliseconds)
        price: Execution price
        size: Trade size in base currency
        side: Aggressor side (BUY = buyer aggressor, SELL = seller aggressor)
        trade_id: Unique identifier
    """
    timestamp: int  # milliseconds
    price: float
    size: float
    side: TradeSide
    trade_id: Optional[str] = None

    @property
    def value(self) -> float:
        """Trade value in quote currency."""
        return self.price * self.size

    @property
    def signed_size(self) -> float:
        """Signed size: positive for buys, negative for sells."""
        return self.size if self.side == TradeSide.BUY else -self.size

    @property
    def signed_value(self) -> float:
        """Signed value: positive for buys, negative for sells."""
        return self.value if self.side == TradeSide.BUY else -self.value

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.timestamp / 1000)

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'price': self.price,
            'size': self.size,
            'side': self.side.value,
            'trade_id': self.trade_id,
            'value': self.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Trade':
        return cls(
            timestamp=data['timestamp'],
            price=data['price'],
            size=data['size'],
            side=TradeSide(data['side']),
            trade_id=data.get('trade_id'),
        )


@dataclass
class TradeStats:
    """
    Aggregated trade statistics over a period.

    Used for CVD calculation and volume analysis.
    """
    # Volume
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    total_volume: float = 0.0

    # Value (in quote currency)
    buy_value: float = 0.0
    sell_value: float = 0.0
    total_value: float = 0.0

    # Count
    buy_count: int = 0
    sell_count: int = 0
    total_count: int = 0

    # Price
    vwap: float = 0.0  # Volume-weighted average price
    high: float = 0.0
    low: float = float('inf')

    # CVD contribution
    delta: float = 0.0  # buy_volume - sell_volume

    @property
    def buy_ratio(self) -> float:
        """Ratio of buy volume to total volume."""
        if self.total_volume == 0:
            return 0.5
        return self.buy_volume / self.total_volume

    @property
    def imbalance(self) -> float:
        """
        Order flow imbalance: (buy - sell) / (buy + sell)
        Range: -1 (all sells) to +1 (all buys)
        """
        if self.total_volume == 0:
            return 0.0
        return (self.buy_volume - self.sell_volume) / self.total_volume


class TradeAggregator:
    """
    Aggregates trades for CVD calculation.

    Maintains rolling window of trades and computes:
    - Cumulative Volume Delta (CVD)
    - Volume imbalance
    - Trade statistics

    This is the core data structure for the Micro-Cortex.
    """

    def __init__(
        self,
        max_trades: int = 10000,
        on_trade: Optional[Callable[[Trade], None]] = None
    ):
        """
        Initialize trade aggregator.

        Args:
            max_trades: Maximum trades to keep in memory
            on_trade: Callback for each new trade
        """
        self.max_trades = max_trades
        self.on_trade = on_trade

        # Trade storage (deque for O(1) append/pop)
        self._trades: Deque[Trade] = deque(maxlen=max_trades)

        # Running CVD (cumulative)
        self._cvd: float = 0.0

        # Statistics
        self._total_buy_volume: float = 0.0
        self._total_sell_volume: float = 0.0
        self._trade_count: int = 0

    def add_trade(self, trade: Trade) -> None:
        """
        Add a trade to the aggregator.

        Args:
            trade: Trade to add
        """
        # Add to deque
        self._trades.append(trade)

        # Update CVD
        self._cvd += trade.signed_size

        # Update totals
        if trade.side == TradeSide.BUY:
            self._total_buy_volume += trade.size
        else:
            self._total_sell_volume += trade.size

        self._trade_count += 1

        # Callback
        if self.on_trade:
            self.on_trade(trade)

    def add_trades(self, trades: List[Trade]) -> None:
        """Add multiple trades."""
        for trade in trades:
            self.add_trade(trade)

    @property
    def cvd(self) -> float:
        """Current Cumulative Volume Delta."""
        return self._cvd

    @property
    def trades(self) -> List[Trade]:
        """All trades in memory."""
        return list(self._trades)

    @property
    def trade_count(self) -> int:
        """Total trades processed."""
        return self._trade_count

    def get_cvd_series(self, n: Optional[int] = None) -> List[float]:
        """
        Get CVD as a time series.

        Args:
            n: Number of most recent trades (None = all)

        Returns:
            List of cumulative CVD values
        """
        trades = list(self._trades)
        if n is not None:
            trades = trades[-n:]

        cvd_series = []
        running_cvd = 0.0

        for trade in trades:
            running_cvd += trade.signed_size
            cvd_series.append(running_cvd)

        return cvd_series

    def get_delta_series(self, n: Optional[int] = None) -> List[float]:
        """
        Get delta (signed size) as a time series.

        Args:
            n: Number of most recent trades (None = all)

        Returns:
            List of signed sizes
        """
        trades = list(self._trades)
        if n is not None:
            trades = trades[-n:]

        return [t.signed_size for t in trades]

    def get_stats(self, n: Optional[int] = None) -> TradeStats:
        """
        Calculate statistics for recent trades.

        Args:
            n: Number of most recent trades (None = all)

        Returns:
            TradeStats for the period
        """
        trades = list(self._trades)
        if n is not None:
            trades = trades[-n:]

        if not trades:
            return TradeStats()

        stats = TradeStats()

        total_value = 0.0
        total_volume = 0.0

        for trade in trades:
            if trade.side == TradeSide.BUY:
                stats.buy_volume += trade.size
                stats.buy_value += trade.value
                stats.buy_count += 1
            else:
                stats.sell_volume += trade.size
                stats.sell_value += trade.value
                stats.sell_count += 1

            stats.high = max(stats.high, trade.price)
            stats.low = min(stats.low, trade.price)

            total_value += trade.value
            total_volume += trade.size

        stats.total_volume = stats.buy_volume + stats.sell_volume
        stats.total_value = stats.buy_value + stats.sell_value
        stats.total_count = stats.buy_count + stats.sell_count

        stats.delta = stats.buy_volume - stats.sell_volume

        # VWAP
        if total_volume > 0:
            stats.vwap = total_value / total_volume
        else:
            stats.vwap = trades[-1].price if trades else 0.0

        return stats

    def get_imbalance(self, n: int = 100) -> float:
        """
        Calculate order flow imbalance for recent trades.

        Args:
            n: Number of trades to consider

        Returns:
            Imbalance in range [-1, 1]
        """
        stats = self.get_stats(n)
        return stats.imbalance

    def get_cvd_zscore(self, lookback: int = 100, current_window: int = 20) -> float:
        """
        Calculate Z-score of recent CVD vs historical.

        Used for detecting significant CVD deviations.

        Args:
            lookback: Historical period for mean/std
            current_window: Recent period to compare

        Returns:
            Z-score of current CVD vs historical
        """
        cvd_series = self.get_cvd_series(lookback + current_window)

        if len(cvd_series) < lookback:
            return 0.0

        # Historical CVD changes
        historical = []
        for i in range(1, lookback):
            historical.append(cvd_series[i] - cvd_series[i-1])

        if len(historical) < 10:
            return 0.0

        # Current CVD change
        current_start = cvd_series[-current_window] if current_window < len(cvd_series) else cvd_series[0]
        current_end = cvd_series[-1]
        current_change = current_end - current_start

        # Z-score
        mean = statistics.mean(historical)
        std = statistics.stdev(historical) if len(historical) > 1 else 1.0

        if std == 0:
            return 0.0

        return (current_change - mean * current_window) / (std * (current_window ** 0.5))

    def reset(self) -> None:
        """Reset all state."""
        self._trades.clear()
        self._cvd = 0.0
        self._total_buy_volume = 0.0
        self._total_sell_volume = 0.0
        self._trade_count = 0

    def __len__(self) -> int:
        return len(self._trades)
