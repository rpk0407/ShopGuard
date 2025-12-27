"""
Market Impact Models

Large orders move prices. Understanding this is critical:
- Temporary impact: Price moves during execution
- Permanent impact: Information revealed moves equilibrium
- Decay: How temporary impact fades

Key models:
- Almgren-Chriss: Optimal execution with impact
- Kyle: Linear permanent impact
- Obizhaeva-Wang: Transient impact with decay
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List
from scipy.optimize import minimize


@dataclass
class ImpactParams:
    """Market impact parameters."""
    temporary_coeff: float  # Temporary impact coefficient
    permanent_coeff: float  # Permanent impact coefficient
    decay_rate: float  # Decay rate for transient impact
    daily_volume: float  # Average daily volume
    volatility: float  # Daily volatility
    spread: float  # Bid-ask spread


@dataclass
class ExecutionCost:
    """Breakdown of execution costs."""
    temporary_impact_cost: float
    permanent_impact_cost: float
    spread_cost: float
    timing_risk_cost: float
    total_cost: float


class MarketImpactModel:
    """
    Base class for market impact models.

    Market impact is nonlinear:
    - Small orders: ~linear impact
    - Large orders: square-root impact
    - Very large orders: can move markets permanently
    """

    def estimate_impact(
        self,
        quantity: int,
        direction: int,  # 1 = buy, -1 = sell
        execution_time: float,  # Time to execute in days
        params: ImpactParams
    ) -> ExecutionCost:
        """
        Estimate total market impact cost.

        Override in subclasses.
        """
        raise NotImplementedError

    def optimal_execution_schedule(
        self,
        quantity: int,
        direction: int,
        max_time: float,
        params: ImpactParams,
        risk_aversion: float = 1e-6
    ) -> List[Tuple[float, int]]:
        """
        Calculate optimal execution schedule.

        Returns list of (time, quantity) tuples.
        """
        raise NotImplementedError


class SquareRootImpact(MarketImpactModel):
    """
    Square-root impact model.

    Impact ∝ sqrt(participation rate)

    This is the most common empirical observation:
    - Impact grows slower than linearly with size
    - Reflects gradual absorption by market
    """

    def __init__(self, eta: float = 0.1, gamma: float = 0.5):
        """
        Initialize square-root impact model.

        Args:
            eta: Impact coefficient
            gamma: Exponent (0.5 for square-root)
        """
        self.eta = eta
        self.gamma = gamma

    def estimate_impact(
        self,
        quantity: int,
        direction: int,
        execution_time: float,
        params: ImpactParams
    ) -> ExecutionCost:
        """Estimate impact using square-root model."""
        # Participation rate
        expected_volume = params.daily_volume * execution_time
        participation = abs(quantity) / expected_volume if expected_volume > 0 else 1

        # Temporary impact (square-root of participation)
        temp_impact = self.eta * params.volatility * (participation ** self.gamma)
        temp_impact_cost = temp_impact * abs(quantity)

        # Permanent impact (linear in order flow)
        perm_impact = params.permanent_coeff * abs(quantity) / params.daily_volume
        perm_impact_cost = 0.5 * perm_impact * abs(quantity)  # Half for average price

        # Spread cost
        spread_cost = 0.5 * params.spread * abs(quantity)

        # Timing risk (volatility during execution)
        timing_risk = params.volatility * np.sqrt(execution_time) * abs(quantity)

        total = temp_impact_cost + perm_impact_cost + spread_cost

        return ExecutionCost(
            temporary_impact_cost=temp_impact_cost,
            permanent_impact_cost=perm_impact_cost,
            spread_cost=spread_cost,
            timing_risk_cost=timing_risk,
            total_cost=total
        )


class AlmgrenChriss(MarketImpactModel):
    """
    Almgren-Chriss optimal execution model.

    The seminal model for optimal execution:
    - Trades off market impact vs timing risk
    - Derives optimal VWAP-like trajectory
    - Risk aversion determines speed

    Reference: Almgren & Chriss (2000)
    """

    def __init__(self):
        pass

    def estimate_impact(
        self,
        quantity: int,
        direction: int,
        execution_time: float,
        params: ImpactParams
    ) -> ExecutionCost:
        """
        Estimate execution cost using Almgren-Chriss.

        Args:
            quantity: Number of shares
            direction: 1 for buy, -1 for sell
            execution_time: Time to execute (days)
            params: Market impact parameters
        """
        X = abs(quantity)  # Total quantity
        T = execution_time  # Total time
        sigma = params.volatility
        eta = params.temporary_coeff
        gamma = params.permanent_coeff
        S = params.spread

        # Assuming N steps (for continuous approximation)
        N = max(1, int(T * 390))  # Minute-level
        tau = T / N

        # Permanent impact cost (linear)
        permanent_cost = 0.5 * gamma * X ** 2 / params.daily_volume

        # Temporary impact cost (depends on execution rate)
        # For uniform execution: rate = X / T
        execution_rate = X / T if T > 0 else X
        temporary_cost = eta * sigma * execution_rate * X / np.sqrt(params.daily_volume)

        # Spread cost
        spread_cost = 0.5 * S * X

        # Timing risk (variance of execution)
        timing_risk = sigma * np.sqrt(T) * X

        total = permanent_cost + temporary_cost + spread_cost

        return ExecutionCost(
            temporary_impact_cost=temporary_cost,
            permanent_impact_cost=permanent_cost,
            spread_cost=spread_cost,
            timing_risk_cost=timing_risk,
            total_cost=total
        )

    def optimal_execution_schedule(
        self,
        quantity: int,
        direction: int,
        max_time: float,
        params: ImpactParams,
        risk_aversion: float = 1e-6
    ) -> List[Tuple[float, int]]:
        """
        Calculate optimal execution trajectory.

        The optimal trajectory balances:
        - Front-loading: reduces timing risk
        - Back-loading: reduces market impact

        Returns list of (time, cumulative_quantity) points.
        """
        X = abs(quantity)
        T = max_time
        sigma = params.volatility
        eta = params.temporary_coeff
        gamma = params.permanent_coeff
        lam = risk_aversion

        # Number of time steps
        N = min(100, max(10, int(T * 390)))  # Up to 100 steps
        tau = T / N

        # Almgren-Chriss parameter
        kappa_sq = lam * sigma ** 2 / (eta * (1 + gamma * tau / (2 * eta)))
        kappa = np.sqrt(kappa_sq) if kappa_sq > 0 else 0.01

        schedule = []
        cumulative = 0

        for j in range(N + 1):
            t = j * tau

            # Optimal trajectory (exponential decay)
            if kappa * T > 1e-10:
                x_j = X * np.sinh(kappa * (T - t)) / np.sinh(kappa * T)
            else:
                # Linear case for very patient trading
                x_j = X * (1 - t / T)

            # Shares to trade in this period
            trade_qty = int(cumulative) - int(x_j)
            cumulative = x_j

            schedule.append((t, int(X - x_j)))

        return schedule

    def optimal_execution_rate(
        self,
        remaining_quantity: int,
        remaining_time: float,
        params: ImpactParams,
        risk_aversion: float = 1e-6
    ) -> float:
        """
        Get optimal execution rate at current point.

        Useful for real-time adjustment.
        """
        X = abs(remaining_quantity)
        T = remaining_time
        sigma = params.volatility
        eta = params.temporary_coeff

        if T <= 0:
            return X  # Execute immediately

        # Simplified: balance impact vs risk
        # Aggressive (high risk aversion) = faster
        # Patient = slower

        # Base rate: uniform
        base_rate = X / T

        # Adjust for risk aversion
        adjustment = np.sqrt(risk_aversion * sigma ** 2 / eta)

        optimal_rate = base_rate * (1 + adjustment)

        return optimal_rate


class TransientImpact(MarketImpactModel):
    """
    Transient impact model with decay.

    Temporary impact decays over time:
    - Immediate impact upon trading
    - Exponential decay as market absorbs
    - Useful for large orders executed over time

    Based on Obizhaeva-Wang (2013).
    """

    def __init__(self, decay_rate: float = 0.1):
        """
        Initialize transient impact model.

        Args:
            decay_rate: Rate at which impact decays (per unit time)
        """
        self.decay_rate = decay_rate

    def estimate_impact(
        self,
        quantity: int,
        direction: int,
        execution_time: float,
        params: ImpactParams
    ) -> ExecutionCost:
        """Estimate impact with decay."""
        X = abs(quantity)
        T = execution_time
        rho = self.decay_rate

        # Permanent impact
        permanent_impact = params.permanent_coeff * X / params.daily_volume
        permanent_cost = 0.5 * permanent_impact * X

        # Transient impact with decay
        # For uniform execution, integrate over time
        if rho * T > 1e-10:
            decay_factor = (1 - np.exp(-rho * T)) / (rho * T)
        else:
            decay_factor = 1.0

        temp_impact = params.temporary_coeff * (X / T) if T > 0 else params.temporary_coeff * X
        temp_cost = temp_impact * X * decay_factor

        # Spread
        spread_cost = 0.5 * params.spread * X

        # Timing risk
        timing_risk = params.volatility * np.sqrt(T) * X

        return ExecutionCost(
            temporary_impact_cost=temp_cost,
            permanent_impact_cost=permanent_cost,
            spread_cost=spread_cost,
            timing_risk_cost=timing_risk,
            total_cost=temp_cost + permanent_cost + spread_cost
        )

    def impact_at_time(
        self,
        trades: List[Tuple[float, int]],
        current_time: float,
        params: ImpactParams
    ) -> float:
        """
        Calculate accumulated impact at a given time.

        Args:
            trades: List of (time, quantity) of past trades
            current_time: Time to evaluate
            params: Impact parameters

        Returns:
            Current price impact
        """
        total_impact = 0.0
        rho = self.decay_rate

        for trade_time, trade_qty in trades:
            if trade_time <= current_time:
                # Time since trade
                dt = current_time - trade_time

                # Decayed temporary impact
                temp_impact = params.temporary_coeff * trade_qty * np.exp(-rho * dt)

                # Permanent impact (no decay)
                perm_impact = params.permanent_coeff * trade_qty / params.daily_volume

                total_impact += temp_impact + perm_impact

        return total_impact

    def optimal_wait_time(
        self,
        last_trade_size: int,
        next_trade_size: int,
        params: ImpactParams
    ) -> float:
        """
        Calculate optimal wait time between trades.

        Waiting allows impact to decay, but incurs timing risk.
        """
        rho = self.decay_rate

        if rho <= 0:
            return 0.0

        # Impact from last trade
        last_impact = params.temporary_coeff * last_trade_size

        # Cost of waiting vs executing
        # Wait benefit: impact decay
        # Wait cost: timing risk

        # Solve for optimal wait time
        # This is a simplified heuristic
        sigma = params.volatility

        # If next trade is large, wait for decay
        size_ratio = next_trade_size / (last_trade_size + 1)

        # Optimal wait ~ log(impact) / decay_rate
        optimal_wait = np.log(1 + last_impact / (sigma * next_trade_size + 1)) / rho

        return max(0, min(optimal_wait, 1.0))  # Cap at 1 day


class KyleModel:
    """
    Kyle's market microstructure model.

    Models price impact from informed trading:
    - Market maker learns from order flow
    - Price moves to offset expected informed trading
    - Lambda = impact coefficient

    Key insight: Impact is linear in order flow.
    """

    def __init__(self, sigma_v: float = 0.01, sigma_u: float = 1000):
        """
        Initialize Kyle model.

        Args:
            sigma_v: Volatility of fundamental value
            sigma_u: Noise trader volume
        """
        self.sigma_v = sigma_v
        self.sigma_u = sigma_u

        # Kyle's lambda
        self.lambda_kyle = sigma_v / (2 * sigma_u)

    def price_impact(self, order_flow: float) -> float:
        """
        Calculate price impact from order flow.

        Args:
            order_flow: Net buy - sell volume

        Returns:
            Expected price change
        """
        return self.lambda_kyle * order_flow

    def optimal_informed_strategy(
        self,
        private_info: float,
        num_periods: int = 10
    ) -> List[float]:
        """
        Calculate optimal trading strategy for informed trader.

        An informed trader should split their order to avoid
        revealing too much information.

        Args:
            private_info: Information advantage (expected price move)
            num_periods: Number of trading periods

        Returns:
            List of trade sizes per period
        """
        # In Kyle model, informed trader trades:
        # x_t = (v - p_t) / (2 * lambda * (T - t + 1))

        trades = []
        remaining_info = private_info

        for t in range(num_periods):
            remaining_periods = num_periods - t
            trade_size = remaining_info / (2 * remaining_periods)
            trades.append(trade_size)

            # Update remaining information (market learns)
            remaining_info -= 2 * self.lambda_kyle * trade_size

        return trades


def estimate_impact_params(
    prices: np.ndarray,
    volumes: np.ndarray,
    trades: List[Tuple[int, float]],  # (quantity, price) pairs
    adv: float
) -> ImpactParams:
    """
    Estimate impact parameters from historical data.

    Args:
        prices: Historical price series
        volumes: Historical volume series
        trades: List of our trades (quantity, avg_price)
        adv: Average daily volume

    Returns:
        Estimated impact parameters
    """
    # Volatility
    returns = np.diff(np.log(prices))
    daily_vol = np.std(returns) * np.sqrt(252)

    # Spread (estimate from price changes)
    spread = np.median(np.abs(returns)) * 2

    # Impact coefficients (would need regression in practice)
    # Using typical values
    temp_coeff = 0.1 * daily_vol
    perm_coeff = 0.1

    # Decay rate (typical values)
    decay_rate = 0.5  # Half-life of ~1.4 time units

    return ImpactParams(
        temporary_coeff=temp_coeff,
        permanent_coeff=perm_coeff,
        decay_rate=decay_rate,
        daily_volume=adv,
        volatility=daily_vol,
        spread=spread
    )
