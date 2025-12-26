"""
Stochastic Process Models

Mathematical foundation for price dynamics modeling.

Key Insight: These models are DESCRIPTIVE, not PREDICTIVE. They help us:
1. Simulate realistic price paths for testing
2. Price derivatives and understand risk
3. Detect when real markets deviate from model assumptions (the actual edge)
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional
from abc import ABC, abstractmethod


@dataclass
class ProcessParameters:
    """Parameters for stochastic processes."""
    mu: float       # Drift (annualized expected return)
    sigma: float    # Volatility (annualized standard deviation)
    dt: float       # Time step (in years, e.g., 1/252 for daily)


class StochasticProcess(ABC):
    """Abstract base for stochastic process simulators."""

    @abstractmethod
    def simulate(self, s0: float, n_steps: int, n_paths: int) -> np.ndarray:
        """Generate simulated price paths."""
        pass

    @abstractmethod
    def theoretical_distribution(self, s0: float, t: float) -> Tuple[float, float]:
        """Return theoretical mean and variance at time t."""
        pass


class GeometricBrownianMotion(StochasticProcess):
    """
    Geometric Brownian Motion (GBM)

    The standard model for stock prices: dS = μS·dt + σS·dW

    Where:
    - S: Asset price
    - μ: Drift (expected return)
    - σ: Volatility
    - W: Wiener process (Brownian motion)

    Solution: S(t) = S(0) · exp((μ - σ²/2)t + σW(t))

    WHY IT MATTERS:
    Real markets deviate from GBM in predictable ways:
    - Fat tails (more extreme moves than GBM predicts)
    - Volatility clustering (GARCH effects)
    - Mean reversion in some asset classes
    - Jump discontinuities during news events

    Detecting these deviations IS the trading signal.
    """

    def __init__(self, params: ProcessParameters):
        self.params = params

    def simulate(self, s0: float, n_steps: int, n_paths: int = 1) -> np.ndarray:
        """
        Generate price paths using exact solution (not Euler discretization).

        Args:
            s0: Initial price
            n_steps: Number of time steps
            n_paths: Number of independent paths

        Returns:
            Array of shape (n_paths, n_steps + 1) with price paths
        """
        dt = self.params.dt
        mu = self.params.mu
        sigma = self.params.sigma

        # Generate Brownian increments
        # dW ~ N(0, dt) => dW = sqrt(dt) * Z where Z ~ N(0,1)
        dW = np.random.normal(0, np.sqrt(dt), size=(n_paths, n_steps))

        # Exact solution: S(t+dt) = S(t) * exp((μ - σ²/2)dt + σ*dW)
        # This avoids discretization error from Euler-Maruyama
        drift_term = (mu - 0.5 * sigma**2) * dt
        diffusion_term = sigma * dW

        log_returns = drift_term + diffusion_term

        # Cumulative sum of log returns
        log_prices = np.zeros((n_paths, n_steps + 1))
        log_prices[:, 0] = np.log(s0)
        log_prices[:, 1:] = np.log(s0) + np.cumsum(log_returns, axis=1)

        return np.exp(log_prices)

    def theoretical_distribution(self, s0: float, t: float) -> Tuple[float, float]:
        """
        Theoretical moments of GBM at time t.

        For GBM, S(t) is log-normally distributed:
        - E[S(t)] = S(0) * exp(μt)
        - Var[S(t)] = S(0)² * exp(2μt) * (exp(σ²t) - 1)
        """
        mu = self.params.mu
        sigma = self.params.sigma

        mean = s0 * np.exp(mu * t)
        variance = s0**2 * np.exp(2 * mu * t) * (np.exp(sigma**2 * t) - 1)

        return mean, variance


class OrnsteinUhlenbeck(StochasticProcess):
    """
    Ornstein-Uhlenbeck Process (Mean-Reverting)

    dX = θ(μ - X)dt + σdW

    Where:
    - X: Process value
    - θ: Speed of mean reversion (higher = faster reversion)
    - μ: Long-term mean
    - σ: Volatility

    WHY IT MATTERS FOR TRADING:
    Many spread/pairs relationships are mean-reverting:
    - Pairs of correlated stocks
    - Futures basis (spot vs futures)
    - Interest rate spreads
    - Currency carry trades

    The O-U process lets us:
    1. Estimate the equilibrium level (μ)
    2. Measure how fast deviations correct (θ)
    3. Calculate optimal entry/exit thresholds

    Half-life of mean reversion: t_half = ln(2) / θ
    """

    def __init__(self, theta: float, mu: float, sigma: float, dt: float):
        self.theta = theta  # Mean reversion speed
        self.mu = mu        # Long-term mean
        self.sigma = sigma  # Volatility
        self.dt = dt        # Time step

    def simulate(self, x0: float, n_steps: int, n_paths: int = 1) -> np.ndarray:
        """
        Simulate O-U paths using exact discretization.

        Exact solution over interval dt:
        X(t+dt) = X(t)*exp(-θdt) + μ(1-exp(-θdt)) + σ*sqrt((1-exp(-2θdt))/(2θ)) * Z
        """
        theta = self.theta
        mu = self.mu
        sigma = self.sigma
        dt = self.dt

        paths = np.zeros((n_paths, n_steps + 1))
        paths[:, 0] = x0

        exp_decay = np.exp(-theta * dt)
        mean_adjustment = mu * (1 - exp_decay)

        # Variance of the noise term
        if theta > 0:
            noise_std = sigma * np.sqrt((1 - np.exp(-2 * theta * dt)) / (2 * theta))
        else:
            noise_std = sigma * np.sqrt(dt)

        for t in range(n_steps):
            noise = np.random.normal(0, noise_std, n_paths)
            paths[:, t + 1] = paths[:, t] * exp_decay + mean_adjustment + noise

        return paths

    def theoretical_distribution(self, x0: float, t: float) -> Tuple[float, float]:
        """
        Theoretical moments of O-U process at time t.

        E[X(t)] = μ + (x0 - μ) * exp(-θt)
        Var[X(t)] = σ²/(2θ) * (1 - exp(-2θt))
        """
        mean = self.mu + (x0 - self.mu) * np.exp(-self.theta * t)
        variance = (self.sigma**2 / (2 * self.theta)) * (1 - np.exp(-2 * self.theta * t))
        return mean, variance

    def half_life(self) -> float:
        """Time for deviation to decay by 50%."""
        return np.log(2) / self.theta

    def equilibrium_variance(self) -> float:
        """Long-run variance as t -> infinity."""
        return self.sigma**2 / (2 * self.theta)


class JumpDiffusion(StochasticProcess):
    """
    Merton Jump-Diffusion Model

    dS/S = μdt + σdW + dJ

    Where J is a compound Poisson process:
    - Jumps arrive with intensity λ (Poisson)
    - Jump sizes are normally distributed with mean μ_j and std σ_j

    WHY IT MATTERS:
    GBM underestimates tail risk. Real markets have:
    - Earnings announcements (scheduled jumps)
    - Geopolitical events (unscheduled jumps)
    - Flash crashes (liquidity-driven jumps)

    This model captures the fat tails that GBM misses.
    Option pricing using this model explains the "volatility smile."
    """

    def __init__(
        self,
        params: ProcessParameters,
        jump_intensity: float,      # λ: expected jumps per year
        jump_mean: float,           # μ_j: average jump size (log)
        jump_std: float             # σ_j: jump size volatility
    ):
        self.params = params
        self.lam = jump_intensity
        self.jump_mean = jump_mean
        self.jump_std = jump_std

    def simulate(self, s0: float, n_steps: int, n_paths: int = 1) -> np.ndarray:
        """
        Simulate jump-diffusion paths.

        The process combines:
        1. Continuous GBM component
        2. Discrete Poisson jumps with log-normal sizes
        """
        dt = self.params.dt
        mu = self.params.mu
        sigma = self.params.sigma

        paths = np.zeros((n_paths, n_steps + 1))
        paths[:, 0] = s0

        # Compensated drift to make process a martingale under risk-neutral measure
        # E[exp(J)] = exp(μ_j + σ_j²/2)
        jump_compensation = self.lam * (np.exp(self.jump_mean + 0.5 * self.jump_std**2) - 1)
        compensated_mu = mu - jump_compensation

        for t in range(n_steps):
            # GBM component
            dW = np.random.normal(0, np.sqrt(dt), n_paths)
            gbm_return = (compensated_mu - 0.5 * sigma**2) * dt + sigma * dW

            # Jump component
            # Number of jumps in this interval ~ Poisson(λ * dt)
            n_jumps = np.random.poisson(self.lam * dt, n_paths)

            # Total jump size (sum of individual jumps)
            jump_returns = np.zeros(n_paths)
            for i in range(n_paths):
                if n_jumps[i] > 0:
                    individual_jumps = np.random.normal(
                        self.jump_mean, self.jump_std, n_jumps[i]
                    )
                    jump_returns[i] = np.sum(individual_jumps)

            # Combine components
            total_log_return = gbm_return + jump_returns
            paths[:, t + 1] = paths[:, t] * np.exp(total_log_return)

        return paths

    def theoretical_distribution(self, s0: float, t: float) -> Tuple[float, float]:
        """
        Moments are more complex due to jump component.
        Returns approximate values under small-jump approximation.
        """
        mu = self.params.mu
        sigma = self.params.sigma

        # Total variance includes jump contribution
        total_var = sigma**2 + self.lam * (self.jump_mean**2 + self.jump_std**2)

        mean = s0 * np.exp(mu * t)
        variance = s0**2 * np.exp(2 * mu * t) * (np.exp(total_var * t) - 1)

        return mean, variance


def estimate_gbm_parameters(prices: np.ndarray, dt: float = 1/252) -> ProcessParameters:
    """
    Estimate GBM parameters from historical prices.

    Uses log-returns which are normally distributed under GBM.

    Args:
        prices: Array of historical prices
        dt: Time step in years (1/252 for daily data)

    Returns:
        ProcessParameters with estimated mu, sigma, dt
    """
    log_returns = np.diff(np.log(prices))

    # Maximum likelihood estimators
    mu_hat = np.mean(log_returns) / dt + 0.5 * np.var(log_returns) / dt
    sigma_hat = np.std(log_returns) / np.sqrt(dt)

    return ProcessParameters(mu=mu_hat, sigma=sigma_hat, dt=dt)


def estimate_ou_parameters(spread: np.ndarray, dt: float = 1/252) -> Tuple[float, float, float]:
    """
    Estimate O-U parameters using OLS regression.

    The discrete O-U process:
    X(t+1) - X(t) = θ(μ - X(t))dt + σ√dt·ε

    Rearranging: ΔX(t) = a + b·X(t) + error
    where a = θμdt, b = -θdt

    Returns:
        Tuple of (theta, mu, sigma)
    """
    dX = np.diff(spread)
    X = spread[:-1]

    # OLS: ΔX = a + b·X
    # Using matrix formulation for numerical stability
    X_matrix = np.column_stack([np.ones_like(X), X])
    coeffs, residuals, _, _ = np.linalg.lstsq(X_matrix, dX, rcond=None)

    a, b = coeffs

    theta = -b / dt
    mu = a / (theta * dt) if theta > 0 else np.mean(spread)

    # Estimate sigma from residuals
    residual_std = np.std(dX - a - b * X)
    sigma = residual_std / np.sqrt(dt)

    return theta, mu, sigma
