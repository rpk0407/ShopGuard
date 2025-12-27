"""
GARCH Family Models for Volatility Forecasting

GARCH (Generalized Autoregressive Conditional Heteroskedasticity) models
capture the key stylized facts of financial volatility:
1. Volatility clustering (high vol follows high vol)
2. Mean reversion in volatility
3. Leverage effect (negative returns -> higher future vol)
4. Fat tails in return distributions

This module implements:
- GARCH(1,1): The workhorse model
- EGARCH: Captures leverage effect
- GJR-GARCH: Asymmetric volatility response
- Component GARCH: Short-term and long-term volatility
- Realized GARCH: Incorporates high-frequency information
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, List
from scipy import optimize
from scipy import stats
from abc import ABC, abstractmethod


@dataclass
class GARCHParams:
    """Parameters for GARCH model."""
    omega: float      # Constant term
    alpha: float      # ARCH coefficient (shock impact)
    beta: float       # GARCH coefficient (persistence)
    gamma: float = 0  # Leverage coefficient (for asymmetric models)

    @property
    def persistence(self) -> float:
        """Volatility persistence (should be < 1 for stationarity)."""
        return self.alpha + self.beta

    @property
    def unconditional_variance(self) -> float:
        """Long-run variance."""
        if self.persistence >= 1:
            return np.inf
        return self.omega / (1 - self.persistence)

    @property
    def half_life(self) -> float:
        """Half-life of volatility shocks in periods."""
        if self.persistence <= 0 or self.persistence >= 1:
            return np.inf
        return np.log(0.5) / np.log(self.persistence)


@dataclass
class GARCHResult:
    """Result of GARCH estimation."""
    params: GARCHParams
    conditional_volatility: np.ndarray
    standardized_residuals: np.ndarray
    log_likelihood: float
    aic: float
    bic: float
    convergence: bool


class GARCHModel(ABC):
    """Abstract base class for GARCH models."""

    @abstractmethod
    def fit(self, returns: np.ndarray) -> GARCHResult:
        """Fit model to return series."""
        pass

    @abstractmethod
    def forecast(self, horizon: int) -> np.ndarray:
        """Forecast volatility."""
        pass

    @abstractmethod
    def simulate(self, n_steps: int, n_paths: int) -> np.ndarray:
        """Simulate return paths."""
        pass


class GARCH11(GARCHModel):
    """
    GARCH(1,1) Model - The Industry Standard

    σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}

    Where:
    - σ²_t: Conditional variance at time t
    - ω: Base variance level (ω > 0)
    - α: Reaction to market shocks (α ≥ 0)
    - β: Persistence of variance (β ≥ 0)
    - ε_{t-1}: Previous period's shock (return - mean)

    Constraints:
    - ω > 0, α ≥ 0, β ≥ 0
    - α + β < 1 (stationarity)

    Interpretation:
    - High α: Volatility reacts strongly to shocks
    - High β: Volatility is persistent
    - α + β close to 1: Long memory in volatility
    """

    def __init__(self):
        self.params: Optional[GARCHParams] = None
        self.returns: Optional[np.ndarray] = None
        self.conditional_var: Optional[np.ndarray] = None

    def fit(
        self,
        returns: np.ndarray,
        starting_params: Optional[Tuple] = None
    ) -> GARCHResult:
        """
        Fit GARCH(1,1) using Maximum Likelihood Estimation.

        Uses quasi-MLE assuming Gaussian innovations.
        """
        self.returns = returns
        n = len(returns)

        # Demean returns
        mean_return = np.mean(returns)
        eps = returns - mean_return

        # Initial parameter guess
        if starting_params is None:
            sample_var = np.var(returns)
            omega_init = sample_var * 0.1
            alpha_init = 0.1
            beta_init = 0.8
            starting_params = (omega_init, alpha_init, beta_init)

        # Bounds: omega > 0, alpha >= 0, beta >= 0, alpha + beta < 1
        bounds = [
            (1e-8, None),  # omega
            (0, 0.99),     # alpha
            (0, 0.99)      # beta
        ]

        # Constraint: alpha + beta < 1
        constraints = {'type': 'ineq', 'fun': lambda x: 0.999 - x[1] - x[2]}

        # Optimize
        result = optimize.minimize(
            lambda params: -self._log_likelihood(params, eps),
            starting_params,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 500}
        )

        # Extract parameters
        omega, alpha, beta = result.x
        self.params = GARCHParams(omega=omega, alpha=alpha, beta=beta)

        # Compute conditional volatility
        self.conditional_var = self._compute_conditional_variance(
            eps, omega, alpha, beta
        )

        # Compute standardized residuals
        std_resid = eps / np.sqrt(self.conditional_var)

        # Model selection criteria
        ll = -result.fun
        k = 3  # Number of parameters
        aic = 2 * k - 2 * ll
        bic = k * np.log(n) - 2 * ll

        return GARCHResult(
            params=self.params,
            conditional_volatility=np.sqrt(self.conditional_var),
            standardized_residuals=std_resid,
            log_likelihood=ll,
            aic=aic,
            bic=bic,
            convergence=result.success
        )

    def _log_likelihood(
        self,
        params: Tuple[float, float, float],
        eps: np.ndarray
    ) -> float:
        """Compute Gaussian log-likelihood."""
        omega, alpha, beta = params
        n = len(eps)

        sigma2 = self._compute_conditional_variance(eps, omega, alpha, beta)

        # Gaussian log-likelihood
        ll = -0.5 * np.sum(np.log(2 * np.pi) + np.log(sigma2) + eps**2 / sigma2)

        return ll

    def _compute_conditional_variance(
        self,
        eps: np.ndarray,
        omega: float,
        alpha: float,
        beta: float
    ) -> np.ndarray:
        """Recursively compute conditional variance."""
        n = len(eps)
        sigma2 = np.zeros(n)

        # Initialize with unconditional variance
        if alpha + beta < 1:
            sigma2[0] = omega / (1 - alpha - beta)
        else:
            sigma2[0] = np.var(eps)

        # Recursive computation
        for t in range(1, n):
            sigma2[t] = omega + alpha * eps[t-1]**2 + beta * sigma2[t-1]

        return sigma2

    def forecast(self, horizon: int) -> np.ndarray:
        """
        Forecast volatility for future periods.

        Uses analytical formula for GARCH(1,1) forecasts.
        """
        if self.params is None or self.conditional_var is None:
            raise ValueError("Model must be fit first")

        omega = self.params.omega
        alpha = self.params.alpha
        beta = self.params.beta
        persistence = alpha + beta

        # Last period's variance and shock
        last_var = self.conditional_var[-1]
        last_eps2 = (self.returns[-1] - np.mean(self.returns))**2

        forecasts = np.zeros(horizon)

        # One-step ahead
        forecasts[0] = omega + alpha * last_eps2 + beta * last_var

        # Multi-step ahead (analytical formula)
        unconditional_var = omega / (1 - persistence) if persistence < 1 else last_var

        for h in range(1, horizon):
            forecasts[h] = unconditional_var + \
                (persistence ** h) * (forecasts[0] - unconditional_var)

        return np.sqrt(forecasts)

    def simulate(self, n_steps: int, n_paths: int = 1000) -> np.ndarray:
        """
        Simulate return paths from fitted model.

        Uses the fitted parameters and last state.
        """
        if self.params is None:
            raise ValueError("Model must be fit first")

        omega = self.params.omega
        alpha = self.params.alpha
        beta = self.params.beta

        paths = np.zeros((n_paths, n_steps))
        sigma2 = np.zeros((n_paths, n_steps))

        # Initialize from last fitted values
        sigma2[:, 0] = self.conditional_var[-1]

        for t in range(n_steps):
            # Generate standardized innovations
            z = np.random.standard_normal(n_paths)

            # Returns
            paths[:, t] = np.sqrt(sigma2[:, t]) * z

            # Update variance for next period
            if t < n_steps - 1:
                sigma2[:, t+1] = omega + alpha * paths[:, t]**2 + beta * sigma2[:, t]

        return paths


class EGARCH(GARCHModel):
    """
    Exponential GARCH (Nelson, 1991)

    Models LOG of variance to ensure positivity without constraints:
    log(σ²_t) = ω + α·g(z_{t-1}) + β·log(σ²_{t-1})

    Where g(z) = θ·z + γ·(|z| - E[|z|])

    Key advantages:
    1. No positivity constraints needed
    2. Captures leverage effect (negative returns -> higher vol)
    3. Allows for asymmetric response to shocks
    """

    def __init__(self):
        self.params: Optional[Dict] = None
        self.returns: Optional[np.ndarray] = None
        self.log_var: Optional[np.ndarray] = None

    def fit(self, returns: np.ndarray) -> GARCHResult:
        """Fit EGARCH model."""
        self.returns = returns
        n = len(returns)

        mean_return = np.mean(returns)
        eps = returns - mean_return

        # Initial parameters: omega, alpha, beta, gamma (leverage)
        sample_var = np.var(returns)
        starting_params = (np.log(sample_var) * 0.1, 0.1, 0.9, -0.1)

        # EGARCH has no positivity constraints (models log variance)
        bounds = [
            (None, None),  # omega (log scale)
            (-1, 1),       # alpha
            (0, 0.999),    # beta
            (-1, 1)        # gamma (leverage)
        ]

        result = optimize.minimize(
            lambda params: -self._log_likelihood(params, eps),
            starting_params,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': 500}
        )

        omega, alpha, beta, gamma = result.x
        self.params = {'omega': omega, 'alpha': alpha, 'beta': beta, 'gamma': gamma}

        # Compute log variance
        self.log_var = self._compute_log_variance(eps, omega, alpha, beta, gamma)

        std_resid = eps / np.exp(self.log_var / 2)

        ll = -result.fun
        k = 4
        aic = 2 * k - 2 * ll
        bic = k * np.log(n) - 2 * ll

        return GARCHResult(
            params=GARCHParams(omega=omega, alpha=alpha, beta=beta, gamma=gamma),
            conditional_volatility=np.exp(self.log_var / 2),
            standardized_residuals=std_resid,
            log_likelihood=ll,
            aic=aic,
            bic=bic,
            convergence=result.success
        )

    def _compute_log_variance(
        self,
        eps: np.ndarray,
        omega: float,
        alpha: float,
        beta: float,
        gamma: float
    ) -> np.ndarray:
        """Compute log conditional variance."""
        n = len(eps)
        log_var = np.zeros(n)

        # Initialize
        log_var[0] = np.log(np.var(eps))

        # E[|z|] for standard normal
        expected_abs_z = np.sqrt(2 / np.pi)

        for t in range(1, n):
            z = eps[t-1] / np.exp(log_var[t-1] / 2)
            g_z = alpha * z + gamma * (np.abs(z) - expected_abs_z)
            log_var[t] = omega + g_z + beta * log_var[t-1]

        return log_var

    def _log_likelihood(self, params: Tuple, eps: np.ndarray) -> float:
        """Gaussian log-likelihood for EGARCH."""
        omega, alpha, beta, gamma = params
        log_var = self._compute_log_variance(eps, omega, alpha, beta, gamma)
        sigma2 = np.exp(log_var)

        ll = -0.5 * np.sum(np.log(2 * np.pi) + log_var + eps**2 / sigma2)
        return ll

    def forecast(self, horizon: int) -> np.ndarray:
        """Forecast EGARCH volatility."""
        if self.params is None:
            raise ValueError("Model must be fit first")

        # Simulation-based forecast for EGARCH
        n_sims = 10000
        simulated = self.simulate(horizon, n_sims)
        return np.std(simulated, axis=0)

    def simulate(self, n_steps: int, n_paths: int = 1000) -> np.ndarray:
        """Simulate from EGARCH."""
        if self.params is None:
            raise ValueError("Model must be fit first")

        omega = self.params['omega']
        alpha = self.params['alpha']
        beta = self.params['beta']
        gamma = self.params['gamma']

        expected_abs_z = np.sqrt(2 / np.pi)

        paths = np.zeros((n_paths, n_steps))
        log_var = np.zeros((n_paths, n_steps))
        log_var[:, 0] = self.log_var[-1]

        for t in range(n_steps):
            z = np.random.standard_normal(n_paths)
            paths[:, t] = np.exp(log_var[:, t] / 2) * z

            if t < n_steps - 1:
                g_z = alpha * z + gamma * (np.abs(z) - expected_abs_z)
                log_var[:, t+1] = omega + g_z + beta * log_var[:, t]

        return paths


class ComponentGARCH(GARCHModel):
    """
    Component GARCH (Engle & Lee, 1999)

    Decomposes volatility into:
    - Long-run (permanent) component q_t
    - Short-run (transitory) component (σ²_t - q_t)

    σ²_t = q_t + α(ε²_{t-1} - q_{t-1}) + β(σ²_{t-1} - q_{t-1})
    q_t = ω + ρ(q_{t-1} - ω) + φ(ε²_{t-1} - σ²_{t-1})

    Applications:
    - Separating noise from fundamental volatility changes
    - Long-term volatility forecasting
    - Understanding volatility drivers
    """

    def __init__(self):
        self.params: Optional[Dict] = None
        self.short_run: Optional[np.ndarray] = None
        self.long_run: Optional[np.ndarray] = None

    def fit(self, returns: np.ndarray) -> GARCHResult:
        """Fit Component GARCH."""
        n = len(returns)
        mean_return = np.mean(returns)
        eps = returns - mean_return
        sample_var = np.var(returns)

        # Parameters: omega, alpha, beta, rho, phi
        starting_params = (sample_var, 0.05, 0.90, 0.99, 0.02)

        bounds = [
            (1e-8, None),  # omega
            (0, 0.5),      # alpha
            (0, 0.99),     # beta
            (0.9, 0.9999), # rho (slow mean reversion for long-run)
            (0, 0.2)       # phi
        ]

        result = optimize.minimize(
            lambda params: -self._log_likelihood(params, eps),
            starting_params,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': 500}
        )

        omega, alpha, beta, rho, phi = result.x
        self.params = {
            'omega': omega, 'alpha': alpha, 'beta': beta,
            'rho': rho, 'phi': phi
        }

        sigma2, self.long_run = self._compute_variance(eps, *result.x)
        self.short_run = sigma2 - self.long_run

        std_resid = eps / np.sqrt(sigma2)

        ll = -result.fun
        k = 5
        aic = 2 * k - 2 * ll
        bic = k * np.log(n) - 2 * ll

        return GARCHResult(
            params=GARCHParams(omega=omega, alpha=alpha, beta=beta),
            conditional_volatility=np.sqrt(sigma2),
            standardized_residuals=std_resid,
            log_likelihood=ll,
            aic=aic,
            bic=bic,
            convergence=result.success
        )

    def _compute_variance(
        self,
        eps: np.ndarray,
        omega: float,
        alpha: float,
        beta: float,
        rho: float,
        phi: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute conditional variance and long-run component."""
        n = len(eps)
        sigma2 = np.zeros(n)
        q = np.zeros(n)  # Long-run component

        sigma2[0] = omega
        q[0] = omega

        for t in range(1, n):
            q[t] = omega + rho * (q[t-1] - omega) + phi * (eps[t-1]**2 - sigma2[t-1])
            sigma2[t] = q[t] + alpha * (eps[t-1]**2 - q[t-1]) + beta * (sigma2[t-1] - q[t-1])

        return sigma2, q

    def _log_likelihood(self, params: Tuple, eps: np.ndarray) -> float:
        """Log-likelihood for Component GARCH."""
        sigma2, _ = self._compute_variance(eps, *params)
        ll = -0.5 * np.sum(np.log(2 * np.pi) + np.log(sigma2) + eps**2 / sigma2)
        return ll

    def forecast(self, horizon: int) -> np.ndarray:
        """Forecast with component decomposition."""
        if self.params is None:
            raise ValueError("Model must be fit first")

        # Simplified forecast using long-run component
        rho = self.params['rho']
        omega = self.params['omega']
        last_q = self.long_run[-1]

        forecasts = np.zeros(horizon)
        q_forecast = last_q

        for h in range(horizon):
            q_forecast = omega + rho * (q_forecast - omega)
            forecasts[h] = q_forecast

        return np.sqrt(forecasts)

    def simulate(self, n_steps: int, n_paths: int = 1000) -> np.ndarray:
        """Simulate from Component GARCH."""
        # Implementation similar to GARCH(1,1) but with two components
        raise NotImplementedError("Component GARCH simulation")


def fit_best_garch(returns: np.ndarray) -> Tuple[str, GARCHResult]:
    """
    Fit multiple GARCH variants and select best by BIC.

    Returns:
        Tuple of (model_name, best_result)
    """
    models = {
        'GARCH(1,1)': GARCH11(),
        'EGARCH': EGARCH(),
        'Component GARCH': ComponentGARCH()
    }

    results = {}
    for name, model in models.items():
        try:
            result = model.fit(returns)
            results[name] = result
        except Exception:
            continue

    if not results:
        raise ValueError("No GARCH model converged")

    # Select by BIC
    best_name = min(results.keys(), key=lambda k: results[k].bic)
    return best_name, results[best_name]


def realized_volatility(
    high_freq_returns: np.ndarray,
    sampling_freq: str = '5min'
) -> float:
    """
    Compute realized volatility from high-frequency returns.

    RV = Σ r²_t (sum of squared intraday returns)

    This is the "ground truth" volatility that GARCH tries to forecast.
    """
    return np.sqrt(np.sum(high_freq_returns**2))


def volatility_forecast_evaluation(
    forecasts: np.ndarray,
    realized: np.ndarray
) -> Dict[str, float]:
    """
    Evaluate volatility forecasts against realized volatility.

    Metrics:
    - MSE: Mean Squared Error
    - QLIKE: Quasi-likelihood loss (robust to scale)
    - R²: Explained variance
    """
    mse = np.mean((forecasts - realized)**2)

    # QLIKE: log(σ²_forecast) + realized²/σ²_forecast
    qlike = np.mean(np.log(forecasts**2) + realized**2 / forecasts**2)

    # Mincer-Zarnowitz regression R²
    slope, intercept = np.polyfit(forecasts, realized, 1)
    predicted = slope * forecasts + intercept
    ss_res = np.sum((realized - predicted)**2)
    ss_tot = np.sum((realized - np.mean(realized))**2)
    r2 = 1 - ss_res / ss_tot

    return {
        'mse': mse,
        'rmse': np.sqrt(mse),
        'qlike': qlike,
        'r2': r2,
        'mz_slope': slope,
        'mz_intercept': intercept
    }
