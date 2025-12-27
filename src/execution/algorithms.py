"""
Execution Algorithms

Standard execution algorithms for large orders:
- TWAP: Time-Weighted Average Price
- VWAP: Volume-Weighted Average Price
- Implementation Shortfall: Minimize tracking error
- POV: Percentage of Volume

The goal: Execute large orders without moving the market.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod


class AlgoState(Enum):
    """Execution algorithm state."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class AlgoOrder:
    """Order from execution algorithm."""
    symbol: str
    side: str
    quantity: int
    limit_price: Optional[float]
    order_type: str
    time_in_force: str = "IOC"  # Immediate or Cancel


@dataclass
class AlgoProgress:
    """Execution progress tracking."""
    total_quantity: int
    executed_quantity: int
    remaining_quantity: int
    avg_execution_price: float
    target_price: float  # Benchmark price
    slippage_bps: float
    elapsed_time: float
    remaining_time: float
    state: AlgoState


@dataclass
class SliceSchedule:
    """Schedule of order slices."""
    times: List[datetime]
    quantities: List[int]
    current_index: int = 0


class ExecutionAlgorithm(ABC):
    """Base class for execution algorithms."""

    def __init__(
        self,
        symbol: str,
        side: str,
        total_quantity: int,
        start_time: datetime,
        end_time: datetime,
        limit_price: Optional[float] = None
    ):
        self.symbol = symbol
        self.side = side
        self.total_quantity = total_quantity
        self.start_time = start_time
        self.end_time = end_time
        self.limit_price = limit_price

        self.executed_quantity = 0
        self.execution_prices: List[Tuple[int, float]] = []
        self.state = AlgoState.PENDING

        self.schedule: Optional[SliceSchedule] = None

    @property
    def remaining_quantity(self) -> int:
        return self.total_quantity - self.executed_quantity

    @property
    def avg_price(self) -> float:
        if not self.execution_prices:
            return 0.0
        total_value = sum(qty * price for qty, price in self.execution_prices)
        total_qty = sum(qty for qty, _ in self.execution_prices)
        return total_value / total_qty if total_qty > 0 else 0.0

    @abstractmethod
    def generate_schedule(self, **kwargs) -> SliceSchedule:
        """Generate execution schedule."""
        pass

    @abstractmethod
    def get_next_slice(
        self,
        current_time: datetime,
        market_data: dict
    ) -> Optional[AlgoOrder]:
        """Get next order slice to execute."""
        pass

    def record_execution(self, quantity: int, price: float):
        """Record an execution."""
        self.execution_prices.append((quantity, price))
        self.executed_quantity += quantity

        if self.executed_quantity >= self.total_quantity:
            self.state = AlgoState.COMPLETED

    def get_progress(self, current_time: datetime) -> AlgoProgress:
        """Get current execution progress."""
        elapsed = (current_time - self.start_time).total_seconds()
        total_duration = (self.end_time - self.start_time).total_seconds()
        remaining = max(0, total_duration - elapsed)

        # Calculate slippage
        target = self.execution_prices[0][1] if self.execution_prices else 0
        slippage = 0.0
        if target > 0 and self.avg_price > 0:
            if self.side == 'buy':
                slippage = (self.avg_price - target) / target * 10000
            else:
                slippage = (target - self.avg_price) / target * 10000

        return AlgoProgress(
            total_quantity=self.total_quantity,
            executed_quantity=self.executed_quantity,
            remaining_quantity=self.remaining_quantity,
            avg_execution_price=self.avg_price,
            target_price=target,
            slippage_bps=slippage,
            elapsed_time=elapsed,
            remaining_time=remaining,
            state=self.state
        )

    def pause(self):
        """Pause execution."""
        if self.state == AlgoState.ACTIVE:
            self.state = AlgoState.PAUSED

    def resume(self):
        """Resume execution."""
        if self.state == AlgoState.PAUSED:
            self.state = AlgoState.ACTIVE

    def cancel(self):
        """Cancel execution."""
        self.state = AlgoState.CANCELLED


class TWAPExecutor(ExecutionAlgorithm):
    """
    Time-Weighted Average Price execution.

    Splits order evenly across time:
    - Simple and predictable
    - Ignores market conditions
    - Good for stable markets

    Best for: Illiquid markets where VWAP is noisy.
    """

    def __init__(
        self,
        symbol: str,
        side: str,
        total_quantity: int,
        start_time: datetime,
        end_time: datetime,
        num_slices: int = 10,
        limit_price: Optional[float] = None,
        randomize: bool = True
    ):
        super().__init__(symbol, side, total_quantity, start_time, end_time, limit_price)
        self.num_slices = num_slices
        self.randomize = randomize

    def generate_schedule(self, **kwargs) -> SliceSchedule:
        """Generate TWAP schedule."""
        duration = (self.end_time - self.start_time).total_seconds()
        interval = duration / self.num_slices

        times = []
        quantities = []
        base_qty = self.total_quantity // self.num_slices
        remainder = self.total_quantity % self.num_slices

        for i in range(self.num_slices):
            # Time for this slice
            slice_time = self.start_time + timedelta(seconds=i * interval)

            # Add randomization to avoid being predictable
            if self.randomize and interval > 60:
                jitter = np.random.uniform(-interval * 0.1, interval * 0.1)
                slice_time += timedelta(seconds=jitter)

            times.append(slice_time)

            # Quantity for this slice
            qty = base_qty + (1 if i < remainder else 0)

            # Random quantity variation
            if self.randomize and self.num_slices > 5:
                variation = np.random.uniform(0.8, 1.2)
                qty = int(qty * variation)

            quantities.append(qty)

        # Adjust to match total
        total_scheduled = sum(quantities)
        if total_scheduled != self.total_quantity:
            quantities[-1] += self.total_quantity - total_scheduled

        self.schedule = SliceSchedule(times=times, quantities=quantities)
        return self.schedule

    def get_next_slice(
        self,
        current_time: datetime,
        market_data: dict
    ) -> Optional[AlgoOrder]:
        """Get next TWAP slice."""
        if self.state == AlgoState.COMPLETED or self.state == AlgoState.CANCELLED:
            return None

        if self.state == AlgoState.PENDING:
            self.state = AlgoState.ACTIVE
            self.generate_schedule()

        if self.state == AlgoState.PAUSED:
            return None

        if self.schedule is None:
            return None

        # Check if we should execute
        idx = self.schedule.current_index
        if idx >= len(self.schedule.times):
            self.state = AlgoState.COMPLETED
            return None

        next_time = self.schedule.times[idx]
        if current_time < next_time:
            return None

        # Execute this slice
        qty = min(self.schedule.quantities[idx], self.remaining_quantity)
        self.schedule.current_index += 1

        if qty <= 0:
            return None

        # Determine limit price
        limit = self.limit_price
        if limit is None:
            # Use market price with slight edge
            if self.side == 'buy':
                limit = market_data.get('ask', 0) * 1.001  # Slightly above ask
            else:
                limit = market_data.get('bid', 0) * 0.999  # Slightly below bid

        return AlgoOrder(
            symbol=self.symbol,
            side=self.side,
            quantity=qty,
            limit_price=limit,
            order_type='limit',
            time_in_force='IOC'
        )


class VWAPExecutor(ExecutionAlgorithm):
    """
    Volume-Weighted Average Price execution.

    Matches historical volume profile:
    - Trades more when market is active
    - Reduces market impact
    - Good benchmark for large orders

    Best for: Liquid markets with predictable volume.
    """

    def __init__(
        self,
        symbol: str,
        side: str,
        total_quantity: int,
        start_time: datetime,
        end_time: datetime,
        volume_profile: Optional[List[float]] = None,
        num_slices: int = 78,  # 5-minute intervals for 6.5 hour day
        limit_price: Optional[float] = None,
        participation_rate: float = 0.1
    ):
        super().__init__(symbol, side, total_quantity, start_time, end_time, limit_price)
        self.volume_profile = volume_profile or self._default_volume_profile()
        self.num_slices = num_slices
        self.participation_rate = participation_rate

    def _default_volume_profile(self) -> List[float]:
        """
        Default U-shaped intraday volume profile.

        Higher volume at open and close, lower midday.
        """
        # Normalized volume weights for each interval
        profile = []
        for i in range(78):  # 5-minute intervals
            hour = i / 12  # Hours from open

            # U-shape: high at open, low at midday, high at close
            if hour < 1:
                weight = 2.0 - hour  # Decreasing from open
            elif hour < 5.5:
                weight = 0.8 + 0.1 * np.sin((hour - 1) * np.pi / 4.5)  # Flat-ish midday
            else:
                weight = 0.8 + (hour - 5.5) * 1.2  # Increasing to close

            profile.append(weight)

        # Normalize
        total = sum(profile)
        return [w / total for w in profile]

    def generate_schedule(
        self,
        actual_volume: Optional[List[float]] = None,
        **kwargs
    ) -> SliceSchedule:
        """
        Generate VWAP schedule.

        Args:
            actual_volume: Real-time volume if available
        """
        profile = actual_volume or self.volume_profile
        duration = (self.end_time - self.start_time).total_seconds()
        interval = duration / len(profile)

        times = []
        quantities = []

        for i, weight in enumerate(profile):
            slice_time = self.start_time + timedelta(seconds=i * interval)
            times.append(slice_time)

            qty = int(self.total_quantity * weight)
            quantities.append(qty)

        # Adjust to match total
        total_scheduled = sum(quantities)
        if total_scheduled != self.total_quantity:
            diff = self.total_quantity - total_scheduled
            # Distribute difference proportionally
            for i in range(abs(diff)):
                idx = i % len(quantities)
                quantities[idx] += 1 if diff > 0 else -1

        self.schedule = SliceSchedule(times=times, quantities=quantities)
        return self.schedule

    def get_next_slice(
        self,
        current_time: datetime,
        market_data: dict
    ) -> Optional[AlgoOrder]:
        """Get next VWAP slice with real-time adjustment."""
        if self.state in [AlgoState.COMPLETED, AlgoState.CANCELLED, AlgoState.PAUSED]:
            return None

        if self.state == AlgoState.PENDING:
            self.state = AlgoState.ACTIVE
            self.generate_schedule()

        if self.schedule is None:
            return None

        idx = self.schedule.current_index
        if idx >= len(self.schedule.times):
            self.state = AlgoState.COMPLETED
            return None

        next_time = self.schedule.times[idx]
        if current_time < next_time:
            return None

        # Adjust quantity based on actual volume
        base_qty = self.schedule.quantities[idx]
        actual_volume = market_data.get('interval_volume', 0)
        expected_volume = market_data.get('expected_volume', actual_volume)

        if expected_volume > 0:
            # Adjust participation based on actual vs expected
            volume_ratio = actual_volume / expected_volume
            adjusted_qty = int(base_qty * min(2.0, max(0.5, volume_ratio)))
        else:
            adjusted_qty = base_qty

        qty = min(adjusted_qty, self.remaining_quantity)
        self.schedule.current_index += 1

        if qty <= 0:
            return None

        # Limit price
        limit = self.limit_price
        if limit is None:
            if self.side == 'buy':
                limit = market_data.get('ask', 0) * 1.001
            else:
                limit = market_data.get('bid', 0) * 0.999

        return AlgoOrder(
            symbol=self.symbol,
            side=self.side,
            quantity=qty,
            limit_price=limit,
            order_type='limit',
            time_in_force='IOC'
        )


class ImplementationShortfall(ExecutionAlgorithm):
    """
    Implementation Shortfall (IS) execution.

    Minimizes difference from decision price:
    - Aggressive at start to lock in price
    - Adaptive to market conditions
    - Balances urgency vs impact

    Best for: Orders where timing matters.
    """

    def __init__(
        self,
        symbol: str,
        side: str,
        total_quantity: int,
        start_time: datetime,
        end_time: datetime,
        decision_price: float,
        limit_price: Optional[float] = None,
        risk_aversion: float = 0.5,
        volatility: float = 0.02,
        impact_coeff: float = 0.1
    ):
        super().__init__(symbol, side, total_quantity, start_time, end_time, limit_price)
        self.decision_price = decision_price
        self.risk_aversion = risk_aversion
        self.volatility = volatility
        self.impact_coeff = impact_coeff

        # IS parameters
        self.kappa = self._calculate_kappa()

    def _calculate_kappa(self) -> float:
        """Calculate optimal trade rate parameter."""
        # kappa determines speed: higher = more aggressive
        # Based on Almgren-Chriss
        lam = self.risk_aversion
        sigma = self.volatility
        eta = self.impact_coeff

        kappa_sq = lam * sigma ** 2 / eta
        return np.sqrt(max(0.001, kappa_sq))

    def generate_schedule(self, **kwargs) -> SliceSchedule:
        """
        Generate IS schedule (exponential decay).

        More aggressive at start, tapering off.
        """
        duration = (self.end_time - self.start_time).total_seconds() / 3600  # hours
        num_slices = max(10, int(duration * 12))  # 5-minute intervals

        times = []
        quantities = []

        interval = duration / num_slices

        for i in range(num_slices):
            t = i * interval
            slice_time = self.start_time + timedelta(hours=t)
            times.append(slice_time)

            # Exponential decay trajectory
            # x(t) = X * sinh(kappa * (T-t)) / sinh(kappa * T)
            remaining_time = duration - t
            if self.kappa * duration > 1e-10:
                remaining_frac = np.sinh(self.kappa * remaining_time) / np.sinh(self.kappa * duration)
            else:
                remaining_frac = remaining_time / duration

            cumulative = self.total_quantity * (1 - remaining_frac)
            prev_cumulative = 0 if i == 0 else (
                self.total_quantity * (1 - np.sinh(self.kappa * (duration - (i-1)*interval)) /
                                       np.sinh(self.kappa * duration))
                if self.kappa * duration > 1e-10 else
                self.total_quantity * (1 - (duration - (i-1)*interval) / duration)
            )

            qty = int(cumulative - prev_cumulative)
            quantities.append(max(1, qty))

        # Adjust to match total
        total_scheduled = sum(quantities)
        if total_scheduled != self.total_quantity:
            quantities[-1] += self.total_quantity - total_scheduled

        self.schedule = SliceSchedule(times=times, quantities=quantities)
        return self.schedule

    def get_next_slice(
        self,
        current_time: datetime,
        market_data: dict
    ) -> Optional[AlgoOrder]:
        """Get next IS slice with adaptive behavior."""
        if self.state in [AlgoState.COMPLETED, AlgoState.CANCELLED, AlgoState.PAUSED]:
            return None

        if self.state == AlgoState.PENDING:
            self.state = AlgoState.ACTIVE
            self.generate_schedule()

        if self.schedule is None:
            return None

        idx = self.schedule.current_index
        if idx >= len(self.schedule.times):
            self.state = AlgoState.COMPLETED
            return None

        next_time = self.schedule.times[idx]
        if current_time < next_time:
            return None

        # Adaptive: adjust based on price movement
        current_price = market_data.get('mid', self.decision_price)
        price_move = (current_price - self.decision_price) / self.decision_price

        base_qty = self.schedule.quantities[idx]

        # If price moved against us, be more aggressive
        # If price moved in our favor, slow down
        if self.side == 'buy':
            urgency_adjust = 1 + price_move * 2  # Higher if price rose
        else:
            urgency_adjust = 1 - price_move * 2  # Higher if price fell

        adjusted_qty = int(base_qty * np.clip(urgency_adjust, 0.5, 2.0))
        qty = min(adjusted_qty, self.remaining_quantity)

        self.schedule.current_index += 1

        if qty <= 0:
            return None

        # Aggressive pricing for IS
        if self.side == 'buy':
            limit = market_data.get('ask', 0) * 1.002  # Cross the spread
        else:
            limit = market_data.get('bid', 0) * 0.998

        return AlgoOrder(
            symbol=self.symbol,
            side=self.side,
            quantity=qty,
            limit_price=limit,
            order_type='limit',
            time_in_force='IOC'
        )

    def get_implementation_shortfall(self, current_price: float) -> float:
        """
        Calculate current implementation shortfall.

        Returns shortfall in basis points.
        """
        if self.executed_quantity == 0:
            return 0.0

        if self.side == 'buy':
            shortfall = (self.avg_price - self.decision_price) / self.decision_price
        else:
            shortfall = (self.decision_price - self.avg_price) / self.decision_price

        return shortfall * 10000  # In bps


class POVExecutor(ExecutionAlgorithm):
    """
    Percentage of Volume (POV) execution.

    Trades a fixed percentage of market volume:
    - Naturally adapts to market activity
    - Lower impact than forcing volume
    - May not complete in time

    Best for: Patient orders in varying liquidity.
    """

    def __init__(
        self,
        symbol: str,
        side: str,
        total_quantity: int,
        start_time: datetime,
        end_time: datetime,
        target_pov: float = 0.1,  # 10% of volume
        limit_price: Optional[float] = None,
        min_slice: int = 100
    ):
        super().__init__(symbol, side, total_quantity, start_time, end_time, limit_price)
        self.target_pov = target_pov
        self.min_slice = min_slice

        self.last_check_time: Optional[datetime] = None
        self.cumulative_market_volume: int = 0

    def generate_schedule(self, **kwargs) -> SliceSchedule:
        """POV doesn't use a fixed schedule - it's adaptive."""
        # Return empty schedule - we use real-time volume
        self.schedule = SliceSchedule(times=[], quantities=[])
        return self.schedule

    def get_next_slice(
        self,
        current_time: datetime,
        market_data: dict
    ) -> Optional[AlgoOrder]:
        """Get next POV slice based on market volume."""
        if self.state in [AlgoState.COMPLETED, AlgoState.CANCELLED, AlgoState.PAUSED]:
            return None

        if self.state == AlgoState.PENDING:
            self.state = AlgoState.ACTIVE
            self.last_check_time = current_time

        # Check time
        if current_time > self.end_time:
            self.state = AlgoState.COMPLETED
            return None

        # Calculate volume since last check
        interval_volume = market_data.get('interval_volume', 0)
        self.cumulative_market_volume += interval_volume

        # Calculate our target quantity based on POV
        target_executed = int(self.cumulative_market_volume * self.target_pov)
        target_executed = min(target_executed, self.total_quantity)

        # How much should we trade?
        qty = target_executed - self.executed_quantity

        if qty < self.min_slice:
            return None

        qty = min(qty, self.remaining_quantity)

        if qty <= 0:
            return None

        # Price
        if self.side == 'buy':
            limit = market_data.get('ask', 0) * 1.001
        else:
            limit = market_data.get('bid', 0) * 0.999

        self.last_check_time = current_time

        return AlgoOrder(
            symbol=self.symbol,
            side=self.side,
            quantity=qty,
            limit_price=limit,
            order_type='limit',
            time_in_force='IOC'
        )
