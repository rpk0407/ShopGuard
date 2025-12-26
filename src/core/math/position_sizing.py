"""
Position Sizing Models

The Kelly Criterion and variants for optimal capital allocation.

KEY INSIGHT: Position sizing is MORE important than signal generation.
A mediocre signal with proper sizing beats a great signal with poor sizing.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
from abc import ABC, abstractmethod


@dataclass
class TradeExpectation:
    """Expected characteristics of a trade opportunity."""
    win_probability: float    # P(win)
    avg_win: float           # E[return | win]
    avg_loss: float          # E[return | loss] (positive number)
    edge: float = None       # Optional: expected edge per trade

    def __post_init__(self):
        if self.edge is None:
            self.edge = (
                self.win_probability * self.avg_win -
                (1 - self.win_probability) * self.avg_loss
            )


class PositionSizer(ABC):
    """Abstract base for position sizing algorithms."""

    @abstractmethod
    def calculate_fraction(self, expectation: TradeExpectation) -> float:
        """Calculate optimal fraction of capital to risk."""
        pass


class KellyCriterion(PositionSizer):
    """
    Kelly Criterion for Optimal Position Sizing

    Derived from information theory by John Kelly (1956).
    Maximizes the expected logarithm of wealth (geometric growth rate).

    For binary outcomes (win/lose):
    f* = (p·b - q) / b = p - q/b

    Where:
    - f*: Optimal fraction of capital to bet
    - p: Probability of winning
    - q: Probability of losing (1 - p)
    - b: Odds received on the bet (win/loss ratio)

    For continuous returns:
    f* = μ / σ²

    Where:
    - μ: Expected excess return
    - σ²: Variance of returns

    WHY KELLY MATTERS:
    1. Maximizes long-term wealth (provably optimal for log utility)
    2. Never risks ruin (f* < 1 always)
    3. Has optimal geometric growth rate

    WHY FULL KELLY IS DANGEROUS:
    1. Assumes perfect knowledge of probabilities (we never have this)
    2. Results in extreme volatility (50% drawdowns are normal)
    3. Parameter estimation errors can be catastrophic

    PRACTICAL SOLUTION: Use fractional Kelly (0.25 to 0.5 of full Kelly)
    """

    def calculate_fraction(self, expectation: TradeExpectation) -> float:
        """
        Calculate full Kelly fraction.

        Formula: f* = (p·b - q) / b

        Where b = avg_win / avg_loss (the odds)
        """
        p = expectation.win_probability
        q = 1 - p
        b = expectation.avg_win / expectation.avg_loss

        kelly = (p * b - q) / b

        # Kelly should never exceed 1 or be negative
        return max(0.0, min(1.0, kelly))

    def calculate_from_returns(self, expected_return: float, variance: float) -> float:
        """
        Kelly for continuous returns.

        f* = μ / σ²

        This is the approximation valid for small edge and normal returns.
        """
        if variance <= 0:
            return 0.0

        return expected_return / variance


class FractionalKelly(PositionSizer):
    """
    Fractional Kelly for Practical Trading

    Uses a fraction of the full Kelly bet to:
    1. Account for parameter uncertainty
    2. Reduce volatility and drawdowns
    3. Provide margin of safety

    Recommended fractions:
    - 0.25: Very conservative (recommended for live trading)
    - 0.50: Moderate (good balance of growth and safety)
    - 0.75: Aggressive (only with high-confidence parameters)

    Mathematical justification (from Thorp):
    If your edge estimate has error ε, fractional Kelly with fraction f
    protects against errors of size f/(1-f) in your edge estimate.
    """

    def __init__(self, fraction: float = 0.25):
        """
        Initialize with Kelly fraction.

        Args:
            fraction: Fraction of full Kelly to use (0 < fraction <= 1)
        """
        if not 0 < fraction <= 1:
            raise ValueError("Fraction must be between 0 and 1")
        self.fraction = fraction

    def calculate_fraction(self, expectation: TradeExpectation) -> float:
        """Calculate fractional Kelly bet size."""
        full_kelly = KellyCriterion()
        return self.fraction * full_kelly.calculate_fraction(expectation)


class MultiAssetKelly:
    """
    Kelly Criterion for Portfolio of Correlated Assets

    When trading multiple assets, we must account for correlations.
    The optimal allocation vector f* solves:

    f* = Σ⁻¹ · μ

    Where:
    - Σ: Covariance matrix of returns
    - μ: Vector of expected excess returns

    This is equivalent to the mean-variance optimal portfolio with
    infinite risk tolerance (maximizing Sharpe ratio with leverage).

    CRITICAL CAVEATS:
    1. Covariance matrices are notoriously unstable
    2. Estimation error in Σ⁻¹ can be severe
    3. Use shrinkage estimators (Ledoit-Wolf) for robustness
    """

    def __init__(self, fraction: float = 0.25):
        self.fraction = fraction

    def calculate_allocation(
        self,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray
    ) -> np.ndarray:
        """
        Calculate optimal allocation across multiple assets.

        Args:
            expected_returns: Vector of expected excess returns
            covariance_matrix: Covariance matrix of returns

        Returns:
            Vector of optimal position sizes (fraction of capital)
        """
        try:
            # Use pseudo-inverse for numerical stability
            cov_inv = np.linalg.pinv(covariance_matrix)
            full_kelly = cov_inv @ expected_returns
        except np.linalg.LinAlgError:
            # Fallback to diagonal (independent assets)
            variances = np.diag(covariance_matrix)
            full_kelly = expected_returns / variances

        # Apply fractional Kelly
        allocation = self.fraction * full_kelly

        return allocation


def calculate_edge_from_history(
    returns: np.ndarray,
    risk_free_rate: float = 0.0
) -> TradeExpectation:
    """
    Estimate trade expectation from historical returns.

    IMPORTANT: This is BACKWARDS-LOOKING. Past performance does not
    guarantee future results. Use with extreme caution.
    """
    excess_returns = returns - risk_free_rate / 252  # Daily risk-free

    wins = excess_returns[excess_returns > 0]
    losses = excess_returns[excess_returns < 0]

    win_prob = len(wins) / len(excess_returns) if len(excess_returns) > 0 else 0.5
    avg_win = np.mean(wins) if len(wins) > 0 else 0.0
    avg_loss = -np.mean(losses) if len(losses) > 0 else 0.0

    return TradeExpectation(
        win_probability=win_prob,
        avg_win=avg_win,
        avg_loss=avg_loss if avg_loss > 0 else 0.001  # Avoid division by zero
    )


def kelly_criterion_simulation(
    win_prob: float,
    win_size: float,
    loss_size: float,
    fractions: List[float],
    n_bets: int = 1000,
    n_simulations: int = 1000
) -> dict:
    """
    Simulate different Kelly fractions to demonstrate the math.

    This function shows WHY Kelly is optimal and WHY fractional Kelly
    is preferred in practice.

    Returns dictionary with:
    - final_wealth: Average final wealth for each fraction
    - max_drawdown: Average maximum drawdown for each fraction
    - ruin_probability: Probability of losing 95%+ of capital
    """
    results = {f: {"final_wealth": [], "max_drawdown": [], "ruined": 0}
               for f in fractions}

    for fraction in fractions:
        for _ in range(n_simulations):
            wealth = 1.0
            peak_wealth = 1.0
            max_dd = 0.0

            for _ in range(n_bets):
                bet_size = fraction * wealth

                if np.random.random() < win_prob:
                    wealth += bet_size * win_size
                else:
                    wealth -= bet_size * loss_size

                peak_wealth = max(peak_wealth, wealth)
                drawdown = (peak_wealth - wealth) / peak_wealth
                max_dd = max(max_dd, drawdown)

                if wealth < 0.05:  # Ruin threshold (95% loss)
                    results[fraction]["ruined"] += 1
                    break

            results[fraction]["final_wealth"].append(wealth)
            results[fraction]["max_drawdown"].append(max_dd)

    # Compute statistics
    output = {}
    for fraction in fractions:
        output[fraction] = {
            "avg_final_wealth": np.mean(results[fraction]["final_wealth"]),
            "median_final_wealth": np.median(results[fraction]["final_wealth"]),
            "avg_max_drawdown": np.mean(results[fraction]["max_drawdown"]),
            "ruin_probability": results[fraction]["ruined"] / n_simulations
        }

    return output
