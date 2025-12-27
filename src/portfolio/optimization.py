"""
Portfolio Optimization Methods

Implements classical and modern portfolio optimization:
1. Mean-Variance (Markowitz, 1952)
2. Risk Parity (Qian, 2005)
3. Black-Litterman (1992)
4. Maximum Sharpe Ratio
5. Minimum Variance
6. Robust optimization

CRITICAL: Optimization is sensitive to inputs!
- Return estimates are very noisy
- Covariance estimates are more stable but still uncertain
- Small changes in inputs -> large changes in weights
- Use regularization and constraints liberally
"""

import numpy as np
from scipy import optimize
from scipy.linalg import sqrtm
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import warnings


@dataclass
class PortfolioWeights:
    """Portfolio weight allocation."""
    weights: np.ndarray
    asset_names: List[str]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    turnover: float = 0.0  # From previous weights

    def to_dict(self) -> Dict[str, float]:
        return dict(zip(self.asset_names, self.weights))


@dataclass
class OptimizationConstraints:
    """Constraints for portfolio optimization."""
    # Weight constraints
    min_weight: float = 0.0        # Minimum weight per asset
    max_weight: float = 1.0        # Maximum weight per asset

    # Portfolio constraints
    long_only: bool = True         # No short selling
    sum_to_one: bool = True        # Weights sum to 1

    # Risk constraints
    max_volatility: float = None   # Maximum portfolio volatility
    min_return: float = None       # Minimum expected return

    # Sector constraints
    sector_limits: Dict[str, float] = None  # Max weight per sector

    # Turnover constraints
    max_turnover: float = None     # Maximum turnover from current


class MeanVarianceOptimizer:
    """
    Markowitz Mean-Variance Optimization

    The grandfather of modern portfolio theory (1952).

    Objective: Maximize: μᵀw - λ/2 * wᵀΣw

    Where:
    - w: Portfolio weights
    - μ: Expected returns
    - Σ: Covariance matrix
    - λ: Risk aversion parameter

    KNOWN ISSUES:
    1. Extremely sensitive to return estimates
    2. Produces extreme / concentrated weights
    3. Estimation error is ignored

    Solutions:
    - Use constraints (max weight, min weight)
    - Regularization (shrinkage)
    - Robust optimization
    - Black-Litterman for better return estimates
    """

    def __init__(
        self,
        risk_aversion: float = 1.0,
        constraints: OptimizationConstraints = None
    ):
        self.risk_aversion = risk_aversion
        self.constraints = constraints or OptimizationConstraints()

    def optimize(
        self,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        asset_names: List[str] = None,
        current_weights: np.ndarray = None
    ) -> PortfolioWeights:
        """
        Find optimal portfolio weights.

        Args:
            expected_returns: Vector of expected returns
            covariance_matrix: Covariance matrix of returns
            asset_names: Names of assets
            current_weights: Current portfolio weights (for turnover)

        Returns:
            PortfolioWeights object
        """
        n_assets = len(expected_returns)

        if asset_names is None:
            asset_names = [f"Asset_{i}" for i in range(n_assets)]

        # Objective: Maximize μᵀw - λ/2 * wᵀΣw
        # Equivalently minimize: -μᵀw + λ/2 * wᵀΣw
        def objective(w):
            port_return = expected_returns @ w
            port_var = w @ covariance_matrix @ w
            return -port_return + 0.5 * self.risk_aversion * port_var

        def objective_gradient(w):
            return -expected_returns + self.risk_aversion * covariance_matrix @ w

        # Constraints
        constraints = []

        if self.constraints.sum_to_one:
            constraints.append({
                'type': 'eq',
                'fun': lambda w: np.sum(w) - 1
            })

        if self.constraints.max_volatility is not None:
            constraints.append({
                'type': 'ineq',
                'fun': lambda w: self.constraints.max_volatility**2 - w @ covariance_matrix @ w
            })

        if self.constraints.min_return is not None:
            constraints.append({
                'type': 'ineq',
                'fun': lambda w: expected_returns @ w - self.constraints.min_return
            })

        # Bounds
        if self.constraints.long_only:
            bounds = [(max(0, self.constraints.min_weight), self.constraints.max_weight)
                     for _ in range(n_assets)]
        else:
            bounds = [(self.constraints.min_weight, self.constraints.max_weight)
                     for _ in range(n_assets)]

        # Initial guess
        x0 = np.ones(n_assets) / n_assets

        # Optimize
        result = optimize.minimize(
            objective,
            x0,
            method='SLSQP',
            jac=objective_gradient,
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )

        if not result.success:
            warnings.warn(f"Optimization did not converge: {result.message}")

        weights = result.x

        # Normalize to ensure sum to 1
        if self.constraints.sum_to_one:
            weights = weights / np.sum(weights)

        # Compute portfolio metrics
        port_return = expected_returns @ weights
        port_vol = np.sqrt(weights @ covariance_matrix @ weights)
        sharpe = port_return / port_vol if port_vol > 0 else 0

        turnover = 0.0
        if current_weights is not None:
            turnover = np.sum(np.abs(weights - current_weights))

        return PortfolioWeights(
            weights=weights,
            asset_names=asset_names,
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            turnover=turnover
        )

    def efficient_frontier(
        self,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        n_points: int = 50
    ) -> List[PortfolioWeights]:
        """
        Compute the efficient frontier.

        Returns portfolios from minimum variance to maximum return.
        """
        # Find min variance portfolio
        min_var = MinimumVariancePortfolio(self.constraints).optimize(
            covariance_matrix
        )

        # Find max return achievable
        if self.constraints.long_only:
            max_ret = np.max(expected_returns)
        else:
            max_ret = expected_returns.max() * 2  # Allow leverage

        min_ret = min_var.expected_return

        target_returns = np.linspace(min_ret, max_ret, n_points)

        frontier = []
        for target in target_returns:
            self.constraints.min_return = target
            try:
                portfolio = self.optimize(expected_returns, covariance_matrix)
                if portfolio.expected_return >= target * 0.99:  # Allow small tolerance
                    frontier.append(portfolio)
            except Exception:
                continue

        return frontier


class RiskParityOptimizer:
    """
    Risk Parity (Equal Risk Contribution) Optimization

    Each asset contributes equally to total portfolio risk.

    Risk contribution of asset i: RC_i = w_i * (Σw)_i / σ_p

    Objective: Equal RC_i for all i

    Advantages over Mean-Variance:
    1. Doesn't require return estimates (only covariance)
    2. More stable over time
    3. Better diversification

    Disadvantage:
    - Doesn't maximize Sharpe ratio
    - May underweight high-alpha assets
    """

    def __init__(self, target_volatility: float = None):
        self.target_volatility = target_volatility

    def optimize(
        self,
        covariance_matrix: np.ndarray,
        asset_names: List[str] = None,
        risk_budgets: np.ndarray = None
    ) -> PortfolioWeights:
        """
        Find risk parity weights.

        Args:
            covariance_matrix: Covariance matrix
            asset_names: Asset names
            risk_budgets: Target risk budgets (default: equal)

        Returns:
            PortfolioWeights
        """
        n_assets = len(covariance_matrix)

        if asset_names is None:
            asset_names = [f"Asset_{i}" for i in range(n_assets)]

        if risk_budgets is None:
            risk_budgets = np.ones(n_assets) / n_assets
        else:
            risk_budgets = risk_budgets / risk_budgets.sum()

        # Objective: Minimize sum of (RC_i - b_i * σ_p)^2
        def objective(w):
            port_var = w @ covariance_matrix @ w
            port_vol = np.sqrt(port_var)

            marginal_risk = covariance_matrix @ w
            risk_contributions = w * marginal_risk / port_vol

            target_rc = risk_budgets * port_vol

            return np.sum((risk_contributions - target_rc)**2)

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        ]

        # Bounds (long only)
        bounds = [(0.001, 1.0) for _ in range(n_assets)]

        # Initial guess
        x0 = np.ones(n_assets) / n_assets

        # Optimize
        result = optimize.minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )

        weights = result.x / result.x.sum()

        # Scale to target volatility if specified
        if self.target_volatility is not None:
            current_vol = np.sqrt(weights @ covariance_matrix @ weights)
            scale = self.target_volatility / current_vol
            # Note: This changes weights sum, need leverage/deleveraging
            weights = weights * scale

        port_vol = np.sqrt(weights @ covariance_matrix @ weights)

        return PortfolioWeights(
            weights=weights,
            asset_names=asset_names,
            expected_return=0,  # Not using returns
            expected_volatility=port_vol,
            sharpe_ratio=0,
            turnover=0
        )

    def get_risk_contributions(
        self,
        weights: np.ndarray,
        covariance_matrix: np.ndarray
    ) -> np.ndarray:
        """Compute risk contribution of each asset."""
        port_var = weights @ covariance_matrix @ weights
        port_vol = np.sqrt(port_var)

        marginal_risk = covariance_matrix @ weights
        risk_contributions = weights * marginal_risk / port_vol

        return risk_contributions


class BlackLittermanModel:
    """
    Black-Litterman Model (1992)

    Combines:
    1. Market equilibrium returns (CAPM)
    2. Investor views

    Results in more stable expected returns than raw estimates.

    Key insight: Start from equilibrium, adjust for views.

    Formula:
    E[R] = [(τΣ)⁻¹ + P'Ω⁻¹P]⁻¹ × [(τΣ)⁻¹π + P'Ω⁻¹Q]

    Where:
    - π: Implied equilibrium returns
    - P: Pick matrix (which assets in each view)
    - Q: View returns
    - Ω: Uncertainty in views
    - τ: Scaling factor (usually 0.05-0.1)
    """

    def __init__(
        self,
        risk_aversion: float = 2.5,
        tau: float = 0.05
    ):
        """
        Initialize Black-Litterman model.

        Args:
            risk_aversion: Market risk aversion (δ)
            tau: Scaling factor for prior (lower = more trust in equilibrium)
        """
        self.risk_aversion = risk_aversion
        self.tau = tau

    def compute_equilibrium_returns(
        self,
        covariance_matrix: np.ndarray,
        market_weights: np.ndarray
    ) -> np.ndarray:
        """
        Compute implied equilibrium returns.

        π = δ × Σ × w_mkt

        These are the returns that would make market weights optimal.
        """
        return self.risk_aversion * covariance_matrix @ market_weights

    def posterior_returns(
        self,
        covariance_matrix: np.ndarray,
        market_weights: np.ndarray,
        views: List[Dict],
        view_confidence: float = 0.5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute posterior expected returns and covariance.

        Args:
            covariance_matrix: Prior covariance matrix
            market_weights: Market capitalization weights
            views: List of view dictionaries:
                   {'assets': [asset indices], 'returns': float, 'confidence': float}
            view_confidence: Default confidence in views (0-1)

        Returns:
            Tuple of (posterior_returns, posterior_covariance)
        """
        n_assets = len(market_weights)
        n_views = len(views)

        # Equilibrium returns
        pi = self.compute_equilibrium_returns(covariance_matrix, market_weights)

        if n_views == 0:
            return pi, covariance_matrix

        # Build P matrix (view portfolios)
        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)  # View returns

        for i, view in enumerate(views):
            assets = view['assets']
            if isinstance(assets, int):
                # Absolute view on single asset
                P[i, assets] = 1
            else:
                # Relative view (first asset outperforms second)
                P[i, assets[0]] = 1
                P[i, assets[1]] = -1
            Q[i] = view['returns']

        # Omega: Uncertainty in views
        # Proportional to variance of view portfolios
        omega_diag = []
        for i in range(n_views):
            conf = views[i].get('confidence', view_confidence)
            # Higher confidence = lower variance
            view_var = P[i] @ covariance_matrix @ P[i]
            omega_diag.append(view_var / conf)
        Omega = np.diag(omega_diag)

        # Posterior calculations
        tau_sigma = self.tau * covariance_matrix
        tau_sigma_inv = np.linalg.inv(tau_sigma)
        omega_inv = np.linalg.inv(Omega)

        # Posterior precision
        posterior_precision = tau_sigma_inv + P.T @ omega_inv @ P
        posterior_covariance = np.linalg.inv(posterior_precision)

        # Posterior mean
        posterior_mean = posterior_covariance @ (
            tau_sigma_inv @ pi + P.T @ omega_inv @ Q
        )

        return posterior_mean, posterior_covariance + covariance_matrix

    def optimize(
        self,
        covariance_matrix: np.ndarray,
        market_weights: np.ndarray,
        views: List[Dict],
        asset_names: List[str] = None,
        constraints: OptimizationConstraints = None
    ) -> PortfolioWeights:
        """
        Optimize portfolio using Black-Litterman returns.
        """
        posterior_returns, posterior_cov = self.posterior_returns(
            covariance_matrix, market_weights, views
        )

        optimizer = MeanVarianceOptimizer(
            risk_aversion=self.risk_aversion,
            constraints=constraints or OptimizationConstraints()
        )

        return optimizer.optimize(
            posterior_returns,
            posterior_cov,
            asset_names
        )


class MinimumVariancePortfolio:
    """
    Minimum Variance Portfolio

    Minimizes portfolio variance without return assumptions.

    Often performs surprisingly well in practice because:
    1. Doesn't rely on noisy return estimates
    2. Low-volatility anomaly (low vol stocks outperform)
    """

    def __init__(self, constraints: OptimizationConstraints = None):
        self.constraints = constraints or OptimizationConstraints()

    def optimize(
        self,
        covariance_matrix: np.ndarray,
        asset_names: List[str] = None
    ) -> PortfolioWeights:
        """Find minimum variance portfolio."""
        n_assets = len(covariance_matrix)

        if asset_names is None:
            asset_names = [f"Asset_{i}" for i in range(n_assets)]

        def objective(w):
            return w @ covariance_matrix @ w

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

        if self.constraints.long_only:
            bounds = [(0, 1) for _ in range(n_assets)]
        else:
            bounds = [(-1, 1) for _ in range(n_assets)]

        x0 = np.ones(n_assets) / n_assets

        result = optimize.minimize(
            objective, x0, method='SLSQP',
            bounds=bounds, constraints=constraints
        )

        weights = result.x / result.x.sum()
        port_vol = np.sqrt(weights @ covariance_matrix @ weights)

        return PortfolioWeights(
            weights=weights,
            asset_names=asset_names,
            expected_return=0,
            expected_volatility=port_vol,
            sharpe_ratio=0,
            turnover=0
        )


class MaxSharpePortfolio:
    """
    Maximum Sharpe Ratio Portfolio

    Maximizes risk-adjusted return.

    Sharpe = (E[R] - Rf) / σ
    """

    def __init__(
        self,
        risk_free_rate: float = 0.02,
        constraints: OptimizationConstraints = None
    ):
        self.risk_free_rate = risk_free_rate
        self.constraints = constraints or OptimizationConstraints()

    def optimize(
        self,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        asset_names: List[str] = None
    ) -> PortfolioWeights:
        """Find maximum Sharpe ratio portfolio."""
        n_assets = len(expected_returns)

        if asset_names is None:
            asset_names = [f"Asset_{i}" for i in range(n_assets)]

        excess_returns = expected_returns - self.risk_free_rate

        def neg_sharpe(w):
            port_return = excess_returns @ w
            port_vol = np.sqrt(w @ covariance_matrix @ w)
            return -port_return / (port_vol + 1e-8)

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

        if self.constraints.long_only:
            bounds = [(0, 1) for _ in range(n_assets)]
        else:
            bounds = [(-1, 1) for _ in range(n_assets)]

        x0 = np.ones(n_assets) / n_assets

        result = optimize.minimize(
            neg_sharpe, x0, method='SLSQP',
            bounds=bounds, constraints=constraints
        )

        weights = result.x / result.x.sum()
        port_return = expected_returns @ weights
        port_vol = np.sqrt(weights @ covariance_matrix @ weights)
        sharpe = (port_return - self.risk_free_rate) / port_vol

        return PortfolioWeights(
            weights=weights,
            asset_names=asset_names,
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            turnover=0
        )


class RobustOptimizer:
    """
    Robust Portfolio Optimization

    Accounts for uncertainty in parameter estimates.

    Methods:
    1. Shrinkage estimators for covariance
    2. Resampling (Michaud)
    3. Worst-case optimization
    """

    @staticmethod
    def shrink_covariance(
        sample_cov: np.ndarray,
        shrinkage_target: str = 'identity'
    ) -> np.ndarray:
        """
        Apply shrinkage to covariance matrix (Ledoit-Wolf).

        Shrunk_Σ = δ × F + (1-δ) × S

        Where F is the target and S is the sample covariance.
        """
        n = len(sample_cov)

        if shrinkage_target == 'identity':
            # Target: scaled identity matrix
            mu = np.trace(sample_cov) / n
            target = mu * np.eye(n)
        elif shrinkage_target == 'diagonal':
            # Target: diagonal of sample covariance
            target = np.diag(np.diag(sample_cov))
        else:
            target = np.eye(n) * np.trace(sample_cov) / n

        # Optimal shrinkage intensity (simplified Ledoit-Wolf)
        # Full formula is complex; using approximation
        delta = 0.2  # Can be computed more precisely

        return delta * target + (1 - delta) * sample_cov

    @staticmethod
    def resampled_frontier(
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        n_samples: int = 1000,
        n_points: int = 50
    ) -> List[PortfolioWeights]:
        """
        Michaud Resampled Efficient Frontier.

        1. Simulate many return/covariance scenarios
        2. Compute optimal portfolio for each
        3. Average the weights

        Produces more stable, diversified portfolios.
        """
        n_assets = len(expected_returns)

        # Use Cholesky for sampling
        L = np.linalg.cholesky(covariance_matrix)

        all_weights = []

        for _ in range(n_samples):
            # Sample returns from distribution
            z = np.random.standard_normal(n_assets)
            sampled_returns = expected_returns + L @ z * 0.1  # Scale noise

            # Sample covariance using Wishart-like distribution
            # Simplified: add noise to sample covariance
            noise = np.random.randn(n_assets, n_assets) * 0.05
            noise = (noise + noise.T) / 2  # Symmetrize
            sampled_cov = covariance_matrix + noise @ noise.T

            # Optimize
            try:
                optimizer = MeanVarianceOptimizer(risk_aversion=2)
                result = optimizer.optimize(sampled_returns, sampled_cov)
                all_weights.append(result.weights)
            except Exception:
                continue

        if not all_weights:
            return []

        # Average weights
        avg_weights = np.mean(all_weights, axis=0)
        avg_weights = avg_weights / avg_weights.sum()

        port_return = expected_returns @ avg_weights
        port_vol = np.sqrt(avg_weights @ covariance_matrix @ avg_weights)

        return [PortfolioWeights(
            weights=avg_weights,
            asset_names=[f"Asset_{i}" for i in range(n_assets)],
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=port_return / port_vol if port_vol > 0 else 0,
            turnover=0
        )]
