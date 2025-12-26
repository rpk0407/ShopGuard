"""
Bayesian Parameter Estimation

For robust estimation under uncertainty.

WHY BAYESIAN FOR TRADING:
1. Incorporates prior beliefs (regime knowledge, macro views)
2. Produces probability distributions, not point estimates
3. Naturally handles small samples (crucial for regime detection)
4. Updates beliefs as new data arrives (online learning)
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Callable
from scipy import stats


@dataclass
class BayesianEstimate:
    """Result of Bayesian parameter estimation."""
    posterior_mean: float
    posterior_std: float
    credible_interval_95: Tuple[float, float]
    prior_mean: float
    prior_std: float
    data_points: int
    effective_sample_size: float  # How much the data moved us from prior


class BayesianParameterEstimator:
    """
    Bayesian estimation for trading parameters.

    Key parameters we estimate:
    - Expected returns (drift)
    - Volatility (and volatility of volatility)
    - Correlation structures
    - Mean reversion speeds
    """

    def estimate_mean_normal(
        self,
        data: np.ndarray,
        prior_mean: float = 0.0,
        prior_std: float = 0.10,
        known_variance: Optional[float] = None
    ) -> BayesianEstimate:
        """
        Bayesian estimation of mean with normal prior.

        Conjugate prior: Normal-Normal model

        Prior: μ ~ N(μ₀, τ₀²)
        Likelihood: x_i | μ ~ N(μ, σ²)
        Posterior: μ | data ~ N(μₙ, τₙ²)

        Where:
        μₙ = (μ₀/τ₀² + n*x̄/σ²) / (1/τ₀² + n/σ²)
        τₙ² = 1 / (1/τ₀² + n/σ²)

        This shows the BAYESIAN UPDATE formula:
        Posterior precision = Prior precision + Data precision
        """
        n = len(data)
        sample_mean = np.mean(data)

        # Use sample variance if not provided
        if known_variance is None:
            known_variance = np.var(data, ddof=1)

        prior_precision = 1 / prior_std**2
        data_precision = n / known_variance

        posterior_precision = prior_precision + data_precision
        posterior_variance = 1 / posterior_precision
        posterior_std = np.sqrt(posterior_variance)

        posterior_mean = (
            prior_mean * prior_precision + sample_mean * data_precision
        ) / posterior_precision

        # 95% credible interval
        ci_lower = posterior_mean - 1.96 * posterior_std
        ci_upper = posterior_mean + 1.96 * posterior_std

        # Effective sample size: how much did data move us from prior?
        # This is data precision / posterior precision
        ess = data_precision / posterior_precision

        return BayesianEstimate(
            posterior_mean=posterior_mean,
            posterior_std=posterior_std,
            credible_interval_95=(ci_lower, ci_upper),
            prior_mean=prior_mean,
            prior_std=prior_std,
            data_points=n,
            effective_sample_size=ess
        )

    def estimate_volatility(
        self,
        returns: np.ndarray,
        prior_vol: float = 0.20,
        prior_strength: float = 10.0
    ) -> BayesianEstimate:
        """
        Bayesian estimation of volatility using Inverse-Gamma prior.

        Conjugate prior for variance in normal model:
        σ² ~ Inverse-Gamma(α₀, β₀)

        Prior parameters from prior_vol and prior_strength:
        α₀ = prior_strength / 2
        β₀ = prior_strength * prior_vol² / 2

        Posterior:
        σ² | data ~ Inverse-Gamma(αₙ, βₙ)
        αₙ = α₀ + n/2
        βₙ = β₀ + Σ(xᵢ - x̄)²/2
        """
        n = len(returns)
        sample_var = np.var(returns, ddof=1)

        # Prior parameters
        alpha_0 = prior_strength / 2
        beta_0 = prior_strength * prior_vol**2 / 2

        # Posterior parameters
        alpha_n = alpha_0 + n / 2
        sum_sq = np.sum((returns - np.mean(returns))**2)
        beta_n = beta_0 + sum_sq / 2

        # Posterior mean and variance for σ² (Inverse-Gamma moments)
        # E[σ²] = β/(α-1) for α > 1
        # Var[σ²] = β²/((α-1)²(α-2)) for α > 2
        if alpha_n > 1:
            posterior_var_mean = beta_n / (alpha_n - 1)
        else:
            posterior_var_mean = sample_var

        # Convert to volatility (σ = √σ²)
        posterior_vol = np.sqrt(posterior_var_mean)

        # Approximate std of volatility using delta method
        if alpha_n > 2:
            var_of_var = beta_n**2 / ((alpha_n - 1)**2 * (alpha_n - 2))
            posterior_std = np.sqrt(var_of_var) / (2 * posterior_vol)
        else:
            posterior_std = posterior_vol * 0.2  # Rough approximation

        # Credible interval (via inverse-gamma quantiles, then sqrt)
        ig = stats.invgamma(alpha_n, scale=beta_n)
        ci_lower = np.sqrt(ig.ppf(0.025))
        ci_upper = np.sqrt(ig.ppf(0.975))

        # Effective sample size
        ess = n / (n + prior_strength)

        return BayesianEstimate(
            posterior_mean=posterior_vol,
            posterior_std=posterior_std,
            credible_interval_95=(ci_lower, ci_upper),
            prior_mean=prior_vol,
            prior_std=prior_vol * 0.3,  # Approximate
            data_points=n,
            effective_sample_size=ess
        )

    def estimate_win_rate(
        self,
        wins: int,
        total: int,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0
    ) -> BayesianEstimate:
        """
        Bayesian estimation of win rate using Beta prior.

        Perfect for estimating strategy success probabilities.

        Prior: p ~ Beta(α₀, β₀)
        - α₀ = β₀ = 1: Uniform prior (no prior belief)
        - α₀ = β₀ = 0.5: Jeffreys prior (uninformative)
        - α₀ > β₀: Prior belief of positive edge

        Posterior: p | data ~ Beta(α₀ + wins, β₀ + losses)
        """
        losses = total - wins

        # Posterior parameters
        alpha_n = prior_alpha + wins
        beta_n = prior_beta + losses

        # Posterior mean and std
        posterior_mean = alpha_n / (alpha_n + beta_n)
        posterior_var = (alpha_n * beta_n) / ((alpha_n + beta_n)**2 * (alpha_n + beta_n + 1))
        posterior_std = np.sqrt(posterior_var)

        # Credible interval
        beta_dist = stats.beta(alpha_n, beta_n)
        ci_lower = beta_dist.ppf(0.025)
        ci_upper = beta_dist.ppf(0.975)

        # Prior mean for reference
        prior_mean = prior_alpha / (prior_alpha + prior_beta)
        prior_std = np.sqrt(
            (prior_alpha * prior_beta) /
            ((prior_alpha + prior_beta)**2 * (prior_alpha + prior_beta + 1))
        )

        # Effective sample size
        ess = total / (total + prior_alpha + prior_beta)

        return BayesianEstimate(
            posterior_mean=posterior_mean,
            posterior_std=posterior_std,
            credible_interval_95=(ci_lower, ci_upper),
            prior_mean=prior_mean,
            prior_std=prior_std,
            data_points=total,
            effective_sample_size=ess
        )


class OnlineBayesianUpdater:
    """
    Online Bayesian updating for real-time parameter estimation.

    Updates beliefs incrementally as new data arrives without
    reprocessing the entire history.

    This is crucial for:
    1. Real-time regime detection
    2. Adaptive position sizing
    3. Dynamic volatility estimation
    """

    def __init__(self, prior_mean: float, prior_precision: float):
        """
        Initialize with prior beliefs.

        Args:
            prior_mean: Initial belief about the mean
            prior_precision: 1/variance of prior (higher = more confident)
        """
        self.current_mean = prior_mean
        self.current_precision = prior_precision
        self.n_observations = 0

    def update(self, observation: float, observation_precision: float = 1.0) -> Tuple[float, float]:
        """
        Update beliefs with a single new observation.

        Args:
            observation: New data point
            observation_precision: Precision of this observation (1/variance)

        Returns:
            Tuple of (updated_mean, updated_precision)
        """
        # Bayesian update: new precision = old precision + observation precision
        new_precision = self.current_precision + observation_precision

        # New mean is precision-weighted average
        new_mean = (
            self.current_mean * self.current_precision +
            observation * observation_precision
        ) / new_precision

        self.current_mean = new_mean
        self.current_precision = new_precision
        self.n_observations += 1

        return new_mean, new_precision

    def update_batch(self, observations: np.ndarray, observation_precision: float = 1.0) -> Tuple[float, float]:
        """Update with a batch of observations."""
        for obs in observations:
            self.update(obs, observation_precision)
        return self.current_mean, self.current_precision

    @property
    def current_std(self) -> float:
        """Current posterior standard deviation."""
        return 1 / np.sqrt(self.current_precision)

    @property
    def credible_interval_95(self) -> Tuple[float, float]:
        """Current 95% credible interval."""
        margin = 1.96 * self.current_std
        return (self.current_mean - margin, self.current_mean + margin)


def bayesian_sharpe_ratio(
    returns: np.ndarray,
    prior_sharpe: float = 0.0,
    prior_strength: float = 10,
) -> Dict[str, float]:
    """
    Bayesian estimation of Sharpe ratio.

    WHY THIS MATTERS:
    A backtest showing 2.0 Sharpe over 2 years has massive uncertainty.
    The 95% CI might be [0.5, 3.5] - you could have edge, or noise.

    This function gives you:
    1. Point estimate
    2. Credible interval
    3. Probability that true Sharpe > 0 (probability of real edge)
    """
    n = len(returns)
    sample_mean = np.mean(returns)
    sample_std = np.std(returns, ddof=1)

    if sample_std == 0:
        return {
            "point_estimate": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "prob_positive": 0.5
        }

    sample_sharpe = sample_mean / sample_std

    # Standard error of Sharpe ratio (Lo, 2002)
    # SE(SR) ≈ sqrt((1 + 0.5*SR²)/n) for normal returns
    se_sharpe = np.sqrt((1 + 0.5 * sample_sharpe**2) / n)

    # Bayesian shrinkage toward prior
    prior_precision = prior_strength
    data_precision = 1 / se_sharpe**2

    posterior_precision = prior_precision + data_precision
    posterior_mean = (
        prior_sharpe * prior_precision + sample_sharpe * data_precision
    ) / posterior_precision
    posterior_std = 1 / np.sqrt(posterior_precision)

    # Probability true Sharpe > 0
    prob_positive = 1 - stats.norm.cdf(0, posterior_mean, posterior_std)

    return {
        "point_estimate": posterior_mean,
        "ci_lower": posterior_mean - 1.96 * posterior_std,
        "ci_upper": posterior_mean + 1.96 * posterior_std,
        "prob_positive": prob_positive,
        "sample_sharpe": sample_sharpe,
        "sample_sharpe_se": se_sharpe
    }
