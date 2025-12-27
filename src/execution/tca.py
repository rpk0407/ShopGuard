"""
Transaction Cost Analysis (TCA)

Measures execution quality:
- Slippage vs benchmarks (VWAP, arrival, etc.)
- Market impact estimation
- Cost attribution

Good TCA is essential for:
- Evaluating broker/algo performance
- Improving execution
- Accurate P&L attribution
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum


class Benchmark(Enum):
    """Execution benchmarks."""
    ARRIVAL = "arrival"  # Price at order arrival
    VWAP = "vwap"  # Volume-weighted average
    TWAP = "twap"  # Time-weighted average
    CLOSE = "close"  # Closing price
    OPEN = "open"  # Opening price
    PREVIOUS_CLOSE = "previous_close"  # Previous day close
    INTERVAL_VWAP = "interval_vwap"  # VWAP during execution window


@dataclass
class Execution:
    """Single execution record."""
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    price: float
    timestamp: datetime
    venue: str
    order_id: str
    fees: float = 0.0


@dataclass
class OrderSummary:
    """Summary of an order's executions."""
    order_id: str
    symbol: str
    side: str
    total_quantity: int
    executed_quantity: int
    avg_price: float
    vwap: float
    first_execution: datetime
    last_execution: datetime
    num_fills: int
    total_fees: float
    venues_used: List[str]


@dataclass
class TCAResult:
    """Transaction cost analysis results."""
    order_id: str
    symbol: str
    side: str
    quantity: int
    avg_price: float

    # Costs in basis points
    total_cost_bps: float
    spread_cost_bps: float
    timing_cost_bps: float
    impact_cost_bps: float
    fee_cost_bps: float

    # Slippage vs benchmarks
    slippage_vs_arrival_bps: float
    slippage_vs_vwap_bps: float
    slippage_vs_twap_bps: float

    # Execution quality metrics
    fill_rate: float
    participation_rate: float
    execution_duration_seconds: float

    # Alpha preserved
    alpha_capture_pct: float


@dataclass
class ExecutionQuality:
    """Aggregate execution quality metrics."""
    total_orders: int
    total_quantity: int
    total_value: float

    # Aggregate costs
    avg_cost_bps: float
    avg_spread_cost_bps: float
    avg_impact_cost_bps: float

    # Performance
    pct_beat_arrival: float
    pct_beat_vwap: float
    avg_fill_rate: float

    # By venue
    venue_stats: Dict[str, Dict]

    # By time of day
    time_stats: Dict[str, Dict]


class TransactionCostAnalyzer:
    """
    Comprehensive transaction cost analysis.

    Measures and attributes execution costs to understand
    where value is being lost.
    """

    def __init__(self):
        # Execution history
        self.executions: Dict[str, List[Execution]] = {}

        # Market data for benchmarks
        self.market_data: Dict[str, Dict] = {}

    def add_execution(self, execution: Execution):
        """Record an execution."""
        if execution.order_id not in self.executions:
            self.executions[execution.order_id] = []
        self.executions[execution.order_id].append(execution)

    def set_market_data(
        self,
        symbol: str,
        date: datetime,
        data: Dict
    ):
        """
        Set market data for TCA.

        data should contain:
        - 'open': opening price
        - 'close': closing price
        - 'vwap': daily VWAP
        - 'volume': daily volume
        - 'ticks': list of (timestamp, price, volume) for intraday VWAP
        """
        key = f"{symbol}_{date.strftime('%Y%m%d')}"
        self.market_data[key] = data

    def analyze_order(
        self,
        order_id: str,
        arrival_price: float,
        decision_price: Optional[float] = None
    ) -> TCAResult:
        """
        Analyze execution costs for an order.

        Args:
            order_id: Order to analyze
            arrival_price: Price when order arrived
            decision_price: Price when trading decision was made

        Returns:
            TCAResult with cost breakdown
        """
        if order_id not in self.executions:
            raise ValueError(f"No executions found for order {order_id}")

        execs = self.executions[order_id]
        if not execs:
            raise ValueError(f"No executions for order {order_id}")

        symbol = execs[0].symbol
        side = execs[0].side

        # Calculate weighted average execution price
        total_value = sum(e.quantity * e.price for e in execs)
        total_qty = sum(e.quantity for e in execs)
        avg_price = total_value / total_qty if total_qty > 0 else 0

        # Total fees
        total_fees = sum(e.fees for e in execs)

        # Get market data
        date = execs[0].timestamp.date()
        market_key = f"{symbol}_{date.strftime('%Y%m%d')}"
        mkt_data = self.market_data.get(market_key, {})

        # Calculate benchmarks
        interval_vwap = self._calculate_interval_vwap(execs, mkt_data)
        twap = self._calculate_interval_twap(execs, mkt_data)
        market_vwap = mkt_data.get('vwap', arrival_price)

        # Slippage calculations (in bps)
        direction = 1 if side == 'buy' else -1

        slippage_arrival = direction * (avg_price - arrival_price) / arrival_price * 10000
        slippage_vwap = direction * (avg_price - market_vwap) / market_vwap * 10000 if market_vwap else 0
        slippage_twap = direction * (avg_price - twap) / twap * 10000 if twap else 0

        # Cost breakdown
        spread = mkt_data.get('avg_spread', 0.0001)  # Default 1 bp
        spread_cost = spread / 2 * 10000  # Half spread in bps

        # Fee cost
        fee_cost = (total_fees / total_value * 10000) if total_value > 0 else 0

        # Impact = slippage - spread - timing
        # Timing = how price moved during execution
        price_at_end = execs[-1].price
        timing_cost = direction * (price_at_end - arrival_price) / arrival_price * 10000

        impact_cost = slippage_arrival - spread_cost - timing_cost

        # Total cost
        total_cost = spread_cost + abs(timing_cost) + max(0, impact_cost) + fee_cost

        # Execution quality
        first_exec = min(execs, key=lambda e: e.timestamp)
        last_exec = max(execs, key=lambda e: e.timestamp)
        duration = (last_exec.timestamp - first_exec.timestamp).total_seconds()

        # Participation rate
        market_volume = mkt_data.get('volume', 0)
        participation = total_qty / market_volume if market_volume > 0 else 0

        # Alpha capture (how much of expected alpha was preserved)
        expected_alpha = mkt_data.get('expected_alpha', 0)
        realized_alpha = -slippage_arrival if expected_alpha else 0
        alpha_capture = realized_alpha / expected_alpha * 100 if expected_alpha else 100

        return TCAResult(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=total_qty,
            avg_price=avg_price,
            total_cost_bps=total_cost,
            spread_cost_bps=spread_cost,
            timing_cost_bps=timing_cost,
            impact_cost_bps=impact_cost,
            fee_cost_bps=fee_cost,
            slippage_vs_arrival_bps=slippage_arrival,
            slippage_vs_vwap_bps=slippage_vwap,
            slippage_vs_twap_bps=slippage_twap,
            fill_rate=1.0,  # Assume filled
            participation_rate=participation,
            execution_duration_seconds=duration,
            alpha_capture_pct=alpha_capture
        )

    def _calculate_interval_vwap(
        self,
        executions: List[Execution],
        market_data: Dict
    ) -> float:
        """Calculate VWAP during execution interval."""
        if not executions:
            return 0.0

        start = min(e.timestamp for e in executions)
        end = max(e.timestamp for e in executions)

        ticks = market_data.get('ticks', [])
        if not ticks:
            # Fall back to our executions
            total_value = sum(e.quantity * e.price for e in executions)
            total_qty = sum(e.quantity for e in executions)
            return total_value / total_qty if total_qty > 0 else 0

        # Filter ticks in interval
        interval_ticks = [
            t for t in ticks
            if start <= t[0] <= end
        ]

        if not interval_ticks:
            return market_data.get('vwap', 0)

        total_value = sum(t[1] * t[2] for t in interval_ticks)  # price * volume
        total_volume = sum(t[2] for t in interval_ticks)

        return total_value / total_volume if total_volume > 0 else 0

    def _calculate_interval_twap(
        self,
        executions: List[Execution],
        market_data: Dict
    ) -> float:
        """Calculate TWAP during execution interval."""
        if not executions:
            return 0.0

        ticks = market_data.get('ticks', [])
        if not ticks:
            # Fall back to simple average of execution prices
            return np.mean([e.price for e in executions])

        start = min(e.timestamp for e in executions)
        end = max(e.timestamp for e in executions)

        interval_ticks = [
            t for t in ticks
            if start <= t[0] <= end
        ]

        if not interval_ticks:
            return np.mean([e.price for e in executions])

        return np.mean([t[1] for t in interval_ticks])

    def get_order_summary(self, order_id: str) -> OrderSummary:
        """Get summary of order executions."""
        if order_id not in self.executions:
            raise ValueError(f"Order {order_id} not found")

        execs = self.executions[order_id]
        if not execs:
            raise ValueError(f"No executions for order {order_id}")

        total_value = sum(e.quantity * e.price for e in execs)
        total_qty = sum(e.quantity for e in execs)
        avg_price = total_value / total_qty if total_qty > 0 else 0

        venues = list(set(e.venue for e in execs))

        return OrderSummary(
            order_id=order_id,
            symbol=execs[0].symbol,
            side=execs[0].side,
            total_quantity=total_qty,  # Would need expected qty
            executed_quantity=total_qty,
            avg_price=avg_price,
            vwap=avg_price,  # Our VWAP
            first_execution=min(e.timestamp for e in execs),
            last_execution=max(e.timestamp for e in execs),
            num_fills=len(execs),
            total_fees=sum(e.fees for e in execs),
            venues_used=venues
        )

    def get_aggregate_quality(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> ExecutionQuality:
        """Calculate aggregate execution quality metrics."""
        results = []
        venue_data: Dict[str, List[float]] = {}
        time_data: Dict[str, List[float]] = {}

        for order_id in self.executions:
            execs = self.executions[order_id]
            if not execs:
                continue

            first_exec = min(execs, key=lambda e: e.timestamp)
            if not (start_date <= first_exec.timestamp <= end_date):
                continue

            try:
                arrival = execs[0].price  # Approximate
                result = self.analyze_order(order_id, arrival)
                results.append(result)

                # By venue
                for exec in execs:
                    if exec.venue not in venue_data:
                        venue_data[exec.venue] = []
                    venue_data[exec.venue].append(result.total_cost_bps)

                # By time of day
                hour = first_exec.timestamp.hour
                if hour < 10:
                    period = "open"
                elif hour < 14:
                    period = "midday"
                else:
                    period = "close"

                if period not in time_data:
                    time_data[period] = []
                time_data[period].append(result.total_cost_bps)

            except Exception:
                continue

        if not results:
            return ExecutionQuality(
                total_orders=0,
                total_quantity=0,
                total_value=0,
                avg_cost_bps=0,
                avg_spread_cost_bps=0,
                avg_impact_cost_bps=0,
                pct_beat_arrival=0,
                pct_beat_vwap=0,
                avg_fill_rate=0,
                venue_stats={},
                time_stats={}
            )

        total_qty = sum(r.quantity for r in results)
        total_value = sum(r.quantity * r.avg_price for r in results)

        # Aggregate stats
        avg_cost = np.mean([r.total_cost_bps for r in results])
        avg_spread = np.mean([r.spread_cost_bps for r in results])
        avg_impact = np.mean([r.impact_cost_bps for r in results])

        # Win rates
        beat_arrival = sum(1 for r in results if r.slippage_vs_arrival_bps < 0) / len(results)
        beat_vwap = sum(1 for r in results if r.slippage_vs_vwap_bps < 0) / len(results)

        # Venue stats
        venue_stats = {
            venue: {
                'avg_cost_bps': np.mean(costs),
                'num_orders': len(costs)
            }
            for venue, costs in venue_data.items()
        }

        # Time stats
        time_stats = {
            period: {
                'avg_cost_bps': np.mean(costs),
                'num_orders': len(costs)
            }
            for period, costs in time_data.items()
        }

        return ExecutionQuality(
            total_orders=len(results),
            total_quantity=total_qty,
            total_value=total_value,
            avg_cost_bps=avg_cost,
            avg_spread_cost_bps=avg_spread,
            avg_impact_cost_bps=avg_impact,
            pct_beat_arrival=beat_arrival * 100,
            pct_beat_vwap=beat_vwap * 100,
            avg_fill_rate=np.mean([r.fill_rate for r in results]),
            venue_stats=venue_stats,
            time_stats=time_stats
        )

    def generate_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Generate TCA report."""
        quality = self.get_aggregate_quality(start_date, end_date)

        report = []
        report.append("=" * 60)
        report.append("TRANSACTION COST ANALYSIS REPORT")
        report.append(f"Period: {start_date.date()} to {end_date.date()}")
        report.append("=" * 60)
        report.append("")
        report.append("SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Orders: {quality.total_orders:,}")
        report.append(f"Total Quantity: {quality.total_quantity:,}")
        report.append(f"Total Value: ${quality.total_value:,.2f}")
        report.append("")
        report.append("COSTS (basis points)")
        report.append("-" * 40)
        report.append(f"Average Total Cost: {quality.avg_cost_bps:.2f} bps")
        report.append(f"  - Spread Cost: {quality.avg_spread_cost_bps:.2f} bps")
        report.append(f"  - Impact Cost: {quality.avg_impact_cost_bps:.2f} bps")
        report.append("")
        report.append("PERFORMANCE")
        report.append("-" * 40)
        report.append(f"Beat Arrival Price: {quality.pct_beat_arrival:.1f}%")
        report.append(f"Beat VWAP: {quality.pct_beat_vwap:.1f}%")
        report.append(f"Average Fill Rate: {quality.avg_fill_rate:.1%}")
        report.append("")

        if quality.venue_stats:
            report.append("BY VENUE")
            report.append("-" * 40)
            for venue, stats in quality.venue_stats.items():
                report.append(f"  {venue}: {stats['avg_cost_bps']:.2f} bps ({stats['num_orders']} orders)")
            report.append("")

        if quality.time_stats:
            report.append("BY TIME OF DAY")
            report.append("-" * 40)
            for period, stats in quality.time_stats.items():
                report.append(f"  {period}: {stats['avg_cost_bps']:.2f} bps ({stats['num_orders']} orders)")

        return "\n".join(report)
