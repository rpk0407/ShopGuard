"""
Copula Models for Dependency Structure

Copulas separate the modeling of marginal distributions from dependency structure.
This is crucial for:
1. Portfolio risk (correlations spike in crises)
2. Pairs trading (joint distribution of spreads)
3. Tail risk (extreme co-movements)
4. Multi-asset derivatives pricing

Sklar's Theorem:
For any joint distribution F(x,y) with marginals F_X and F_Y,
there exists a copula C such that:
F(x,y) = C(F_X(x), F_Y(y))

Conversely, given a copula and marginals, we can construct any joint distribution.
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict
from scipy import stats, optimize
from scipy.special import gammaln
from abc import ABC, abstractmethod


@dataclass
class CopulaParams:
    """Parameters for copula model."""
    family: str
    theta: float              # Main dependence parameter
    tail_dependence: Dict[str, float] = None  # Lower and upper tail dependence

    def __post_init__(self):
        if self.tail_dependence is None:
            self.tail_dependence = {}


@dataclass
class CopulaFitResult:
    """Result of copula fitting."""
    params: CopulaParams
    log_likelihood: float
    aic: float
    kendall_tau: float        # Kendall's rank correlation
    spearman_rho: float       # Spearman's rank correlation


class Copula(ABC):
    """Abstract base class for copulas."""

    @abstractmethod
    def cdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Copula CDF: C(u, v)."""
        pass

    @abstractmethod
    def pdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Copula PDF (density): c(u, v)."""
        pass

    @abstractmethod
    def sample(self, n: int) -> np.ndarray:
        """Sample from copula."""
        pass

    @abstractmethod
    def fit(self, u: np.ndarray, v: np.ndarray) -> CopulaFitResult:
        """Fit copula to pseudo-observations."""
        pass


class GaussianCopula(Copula):
    """
    Gaussian (Normal) Copula

    C(u, v) = Φ_ρ(Φ⁻¹(u), Φ⁻¹(v))

    Where:
    - Φ_ρ: Bivariate standard normal CDF with correlation ρ
    - Φ⁻¹: Inverse standard normal CDF

    Properties:
    - No tail dependence (underestimates joint extremes!)
    - Symmetric dependence
    - Easy to extend to higher dimensions

    WARNING: Gaussian copula famously failed in 2008 crisis
    because it underestimated tail dependence in CDO pricing.
    """

    def __init__(self, rho: float = 0.0):
        """
        Initialize Gaussian copula.

        Args:
            rho: Correlation parameter in [-1, 1]
        """
        if not -1 <= rho <= 1:
            raise ValueError("rho must be in [-1, 1]")
        self.rho = rho

    def cdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute copula CDF."""
        x = stats.norm.ppf(u)
        y = stats.norm.ppf(v)

        # Bivariate normal CDF
        cov = np.array([[1, self.rho], [self.rho, 1]])
        result = np.zeros_like(u)

        for i in range(len(u)):
            rv = stats.multivariate_normal(mean=[0, 0], cov=cov)
            result[i] = rv.cdf([x[i], y[i]])

        return result

    def pdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute copula density."""
        x = stats.norm.ppf(np.clip(u, 1e-10, 1-1e-10))
        y = stats.norm.ppf(np.clip(v, 1e-10, 1-1e-10))

        rho = self.rho
        rho2 = rho ** 2

        # Copula density formula
        term1 = 1 / np.sqrt(1 - rho2)
        term2 = np.exp(-(rho2 * (x**2 + y**2) - 2*rho*x*y) / (2*(1 - rho2)))

        return term1 * term2

    def sample(self, n: int) -> np.ndarray:
        """Sample from Gaussian copula."""
        cov = np.array([[1, self.rho], [self.rho, 1]])
        z = np.random.multivariate_normal([0, 0], cov, n)
        u = stats.norm.cdf(z)
        return u

    def fit(self, u: np.ndarray, v: np.ndarray) -> CopulaFitResult:
        """Fit Gaussian copula using MLE."""
        # Transform to normal scale
        x = stats.norm.ppf(np.clip(u, 1e-10, 1-1e-10))
        y = stats.norm.ppf(np.clip(v, 1e-10, 1-1e-10))

        # MLE for correlation
        self.rho = np.corrcoef(x, y)[0, 1]

        # Log-likelihood
        ll = np.sum(np.log(self.pdf(u, v) + 1e-10))

        # Rank correlations
        kendall_tau = stats.kendalltau(u, v)[0]
        spearman_rho = stats.spearmanr(u, v)[0]

        return CopulaFitResult(
            params=CopulaParams(
                family='gaussian',
                theta=self.rho,
                tail_dependence={'lower': 0, 'upper': 0}  # No tail dependence!
            ),
            log_likelihood=ll,
            aic=2 - 2 * ll,
            kendall_tau=kendall_tau,
            spearman_rho=spearman_rho
        )


class TCopula(Copula):
    """
    Student-t Copula

    Like Gaussian but with fatter tails.
    Has symmetric tail dependence: λ_L = λ_U > 0

    Tail dependence coefficient:
    λ = 2 * t_{ν+1}(-√((ν+1)(1-ρ)/(1+ρ)))

    This captures the fact that extreme events tend to occur together.
    """

    def __init__(self, rho: float = 0.0, df: float = 4.0):
        """
        Initialize t-copula.

        Args:
            rho: Correlation parameter
            df: Degrees of freedom (lower = fatter tails)
        """
        self.rho = rho
        self.df = df

    def cdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute t-copula CDF (numerical integration needed)."""
        # Simplified implementation using simulation
        n_sim = 10000
        samples = self.sample(n_sim)
        result = np.zeros_like(u)

        for i in range(len(u)):
            result[i] = np.mean((samples[:, 0] <= u[i]) & (samples[:, 1] <= v[i]))

        return result

    def pdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute t-copula density."""
        u = np.clip(u, 1e-10, 1-1e-10)
        v = np.clip(v, 1e-10, 1-1e-10)

        x = stats.t.ppf(u, self.df)
        y = stats.t.ppf(v, self.df)

        rho = self.rho
        df = self.df

        # t-copula density formula
        term1 = (1 / (2 * np.pi * np.sqrt(1 - rho**2)))
        term2 = (gammaln((df + 2) / 2) - gammaln(df / 2)) * 2
        term3 = (gammaln(df / 2) - gammaln((df + 1) / 2)) * 2

        quad_form = (x**2 - 2*rho*x*y + y**2) / (1 - rho**2)

        log_density = (
            term2 - term3 -
            np.log(1 - rho**2) / 2 -
            ((df + 2) / 2) * np.log(1 + quad_form / df) +
            ((df + 1) / 2) * (np.log(1 + x**2/df) + np.log(1 + y**2/df))
        )

        return np.exp(log_density)

    def sample(self, n: int) -> np.ndarray:
        """Sample from t-copula."""
        # Method: generate multivariate t, then transform to uniforms
        cov = np.array([[1, self.rho], [self.rho, 1]])

        # Multivariate t = Normal / sqrt(chi2/df)
        z = np.random.multivariate_normal([0, 0], cov, n)
        s = np.random.chisquare(self.df, n) / self.df
        t = z / np.sqrt(s)[:, np.newaxis]

        u = stats.t.cdf(t, self.df)
        return u

    def fit(self, u: np.ndarray, v: np.ndarray) -> CopulaFitResult:
        """Fit t-copula using MLE."""
        # Transform to t scale for initial rho estimate
        x = stats.t.ppf(np.clip(u, 1e-10, 1-1e-10), 4)
        y = stats.t.ppf(np.clip(v, 1e-10, 1-1e-10), 4)

        def neg_ll(params):
            rho, log_df = params
            self.rho = np.clip(rho, -0.99, 0.99)
            self.df = np.exp(log_df)
            return -np.sum(np.log(self.pdf(u, v) + 1e-10))

        result = optimize.minimize(
            neg_ll,
            [np.corrcoef(x, y)[0, 1], np.log(4)],
            method='L-BFGS-B',
            bounds=[(-0.99, 0.99), (np.log(2), np.log(100))]
        )

        self.rho = result.x[0]
        self.df = np.exp(result.x[1])

        ll = -result.fun

        # Tail dependence
        tail_dep = self._tail_dependence()

        return CopulaFitResult(
            params=CopulaParams(
                family='t',
                theta=self.rho,
                tail_dependence={'lower': tail_dep, 'upper': tail_dep}
            ),
            log_likelihood=ll,
            aic=4 - 2 * ll,  # 2 parameters
            kendall_tau=stats.kendalltau(u, v)[0],
            spearman_rho=stats.spearmanr(u, v)[0]
        )

    def _tail_dependence(self) -> float:
        """Compute tail dependence coefficient."""
        df = self.df
        rho = self.rho
        coef = np.sqrt((df + 1) * (1 - rho) / (1 + rho))
        return 2 * stats.t.cdf(-coef, df + 1)


class ClaytonCopula(Copula):
    """
    Clayton Copula (Archimedean)

    C(u, v) = (u^{-θ} + v^{-θ} - 1)^{-1/θ}

    Properties:
    - Lower tail dependence: λ_L = 2^{-1/θ} > 0
    - No upper tail dependence: λ_U = 0
    - Good for modeling joint downside risk

    Financial interpretation:
    Assets are more dependent during market crashes than rallies.
    """

    def __init__(self, theta: float = 1.0):
        """
        Initialize Clayton copula.

        Args:
            theta: Dependence parameter (θ > 0)
        """
        if theta <= 0:
            raise ValueError("theta must be positive")
        self.theta = theta

    def cdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute Clayton copula CDF."""
        u = np.clip(u, 1e-10, 1-1e-10)
        v = np.clip(v, 1e-10, 1-1e-10)

        return np.power(
            np.power(u, -self.theta) + np.power(v, -self.theta) - 1,
            -1/self.theta
        )

    def pdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute Clayton copula density."""
        u = np.clip(u, 1e-10, 1-1e-10)
        v = np.clip(v, 1e-10, 1-1e-10)

        theta = self.theta

        term1 = (1 + theta)
        term2 = np.power(u * v, -theta - 1)
        term3 = np.power(
            np.power(u, -theta) + np.power(v, -theta) - 1,
            -1/theta - 2
        )

        return term1 * term2 * term3

    def sample(self, n: int) -> np.ndarray:
        """Sample from Clayton copula using conditional method."""
        u = np.random.uniform(0, 1, n)
        w = np.random.uniform(0, 1, n)

        # Conditional inverse
        theta = self.theta
        v = np.power(
            np.power(
                np.power(w, -theta/(1+theta)) - 1,
                -1
            ) * np.power(u, -theta) + 1,
            -1/theta
        )

        return np.column_stack([u, v])

    def fit(self, u: np.ndarray, v: np.ndarray) -> CopulaFitResult:
        """Fit Clayton copula using MLE."""
        # Estimate theta from Kendall's tau
        tau = stats.kendalltau(u, v)[0]
        theta_init = max(0.1, 2 * tau / (1 - tau))

        def neg_ll(theta):
            if theta <= 0:
                return 1e10
            self.theta = theta
            return -np.sum(np.log(self.pdf(u, v) + 1e-10))

        result = optimize.minimize_scalar(
            neg_ll,
            bounds=(0.01, 50),
            method='bounded'
        )

        self.theta = result.x
        ll = -result.fun

        # Lower tail dependence
        lower_tail = np.power(2, -1/self.theta)

        return CopulaFitResult(
            params=CopulaParams(
                family='clayton',
                theta=self.theta,
                tail_dependence={'lower': lower_tail, 'upper': 0}
            ),
            log_likelihood=ll,
            aic=2 - 2 * ll,
            kendall_tau=tau,
            spearman_rho=stats.spearmanr(u, v)[0]
        )


class GumbelCopula(Copula):
    """
    Gumbel Copula (Archimedean)

    C(u, v) = exp(-((−ln u)^θ + (−ln v)^θ)^{1/θ})

    Properties:
    - Upper tail dependence: λ_U = 2 - 2^{1/θ} > 0
    - No lower tail dependence: λ_L = 0
    - Good for modeling joint upside (bubbles)

    Complementary to Clayton for asymmetric dependence.
    """

    def __init__(self, theta: float = 2.0):
        """
        Initialize Gumbel copula.

        Args:
            theta: Dependence parameter (θ ≥ 1)
        """
        if theta < 1:
            raise ValueError("theta must be >= 1")
        self.theta = theta

    def cdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute Gumbel copula CDF."""
        u = np.clip(u, 1e-10, 1-1e-10)
        v = np.clip(v, 1e-10, 1-1e-10)

        log_u = -np.log(u)
        log_v = -np.log(v)

        return np.exp(-np.power(
            np.power(log_u, self.theta) + np.power(log_v, self.theta),
            1/self.theta
        ))

    def pdf(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Compute Gumbel copula density."""
        u = np.clip(u, 1e-10, 1-1e-10)
        v = np.clip(v, 1e-10, 1-1e-10)

        theta = self.theta
        log_u = -np.log(u)
        log_v = -np.log(v)

        A = np.power(log_u, theta) + np.power(log_v, theta)
        C = np.exp(-np.power(A, 1/theta))

        term1 = C / (u * v)
        term2 = np.power(log_u * log_v, theta - 1)
        term3 = np.power(A, 1/theta - 2)
        term4 = np.power(A, 1/theta) + theta - 1

        return term1 * term2 * term3 * term4

    def sample(self, n: int) -> np.ndarray:
        """Sample from Gumbel copula."""
        # Marshall-Olkin method using stable distribution
        # Simplified: use rejection sampling
        samples = []
        while len(samples) < n:
            u = np.random.uniform(0, 1, 2)
            if np.random.uniform() < self.pdf(u[0:1], u[1:2])[0]:
                samples.append(u)

        return np.array(samples[:n])

    def fit(self, u: np.ndarray, v: np.ndarray) -> CopulaFitResult:
        """Fit Gumbel copula."""
        tau = stats.kendalltau(u, v)[0]
        theta_init = max(1.0, 1 / (1 - tau))

        def neg_ll(theta):
            if theta < 1:
                return 1e10
            self.theta = theta
            return -np.sum(np.log(self.pdf(u, v) + 1e-10))

        result = optimize.minimize_scalar(
            neg_ll,
            bounds=(1.0, 50),
            method='bounded'
        )

        self.theta = result.x
        ll = -result.fun

        # Upper tail dependence
        upper_tail = 2 - np.power(2, 1/self.theta)

        return CopulaFitResult(
            params=CopulaParams(
                family='gumbel',
                theta=self.theta,
                tail_dependence={'lower': 0, 'upper': upper_tail}
            ),
            log_likelihood=ll,
            aic=2 - 2 * ll,
            kendall_tau=tau,
            spearman_rho=stats.spearmanr(u, v)[0]
        )


def select_best_copula(
    u: np.ndarray,
    v: np.ndarray
) -> Tuple[str, Copula, CopulaFitResult]:
    """
    Fit multiple copulas and select best by AIC.

    Returns:
        Tuple of (copula_name, fitted_copula, fit_result)
    """
    copulas = {
        'gaussian': GaussianCopula(),
        't': TCopula(),
        'clayton': ClaytonCopula(),
        'gumbel': GumbelCopula()
    }

    results = {}
    for name, copula in copulas.items():
        try:
            result = copula.fit(u, v)
            results[name] = (copula, result)
        except Exception:
            continue

    if not results:
        raise ValueError("No copula could be fitted")

    best_name = min(results.keys(), key=lambda k: results[k][1].aic)
    best_copula, best_result = results[best_name]

    return best_name, best_copula, best_result


def empirical_copula(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute empirical copula (pseudo-observations).

    Transforms data to uniform margins using ranks.
    """
    n = len(x)
    u = (stats.rankdata(x) - 0.5) / n
    v = (stats.rankdata(y) - 0.5) / n
    return u, v


def tail_dependence_test(
    u: np.ndarray,
    v: np.ndarray,
    threshold: float = 0.05
) -> Dict[str, float]:
    """
    Non-parametric estimation of tail dependence.

    Lower tail: P(U < q | V < q)
    Upper tail: P(U > 1-q | V > 1-q)
    """
    q = threshold
    n = len(u)

    # Lower tail
    lower_joint = np.sum((u < q) & (v < q)) / n
    lower_marginal = np.sum(u < q) / n
    lower_tail = lower_joint / lower_marginal if lower_marginal > 0 else 0

    # Upper tail
    upper_joint = np.sum((u > 1-q) & (v > 1-q)) / n
    upper_marginal = np.sum(u > 1-q) / n
    upper_tail = upper_joint / upper_marginal if upper_marginal > 0 else 0

    return {
        'lower_tail_dependence': lower_tail,
        'upper_tail_dependence': upper_tail,
        'threshold': q
    }
