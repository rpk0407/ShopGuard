"""
Regime Switching Models (Markov Switching)

Financial markets exhibit distinct regimes:
- Bull vs Bear markets
- High vs Low volatility
- Trending vs Mean-reverting
- Risk-on vs Risk-off

Regime switching models capture these dynamics by allowing parameters
to change based on an unobserved state variable that follows a Markov chain.

Applications:
1. Volatility forecasting (regime-dependent vol)
2. Asset allocation (risk-on/risk-off)
3. Strategy selection (trend-following vs mean-reversion)
4. Tail risk estimation
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, List
from scipy import optimize, stats
from scipy.special import logsumexp
from enum import Enum


class RegimeType(Enum):
    """Common regime characterizations."""
    BULL = "bull"
    BEAR = "bear"
    HIGH_VOL = "high_volatility"
    LOW_VOL = "low_volatility"
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    CRISIS = "crisis"
    NORMAL = "normal"


@dataclass
class RegimeParams:
    """Parameters for a single regime."""
    mean: float           # Regime-specific mean
    variance: float       # Regime-specific variance
    label: Optional[str] = None

    @property
    def volatility(self) -> float:
        return np.sqrt(self.variance)


@dataclass
class MarkovSwitchingResult:
    """Result of Markov Switching estimation."""
    regime_params: List[RegimeParams]
    transition_matrix: np.ndarray      # P[regime_t | regime_{t-1}]
    filtered_probs: np.ndarray         # P[regime_t | data_1:t]
    smoothed_probs: np.ndarray         # P[regime_t | data_1:T]
    predicted_regime: np.ndarray       # Most likely regime at each t
    log_likelihood: float
    aic: float
    bic: float


class MarkovSwitchingModel:
    """
    Markov Regime Switching Model (Hamilton, 1989)

    The model assumes:
    - K discrete regimes (states)
    - Regime evolution follows first-order Markov chain
    - Observations are regime-dependent

    For returns:
    r_t | S_t=k ~ N(μ_k, σ²_k)
    P(S_t=j | S_{t-1}=i) = p_ij

    Estimation uses Hamilton filter (forward algorithm)
    and Kim smoother (backward algorithm).
    """

    def __init__(self, n_regimes: int = 2):
        """
        Initialize model.

        Args:
            n_regimes: Number of regimes (2 = bull/bear, 3 adds crisis)
        """
        self.n_regimes = n_regimes
        self.regime_params: Optional[List[RegimeParams]] = None
        self.transition_matrix: Optional[np.ndarray] = None
        self.returns: Optional[np.ndarray] = None

    def fit(self, returns: np.ndarray) -> MarkovSwitchingResult:
        """
        Fit Markov Switching model using Maximum Likelihood.

        Uses EM algorithm:
        1. E-step: Compute regime probabilities given parameters
        2. M-step: Update parameters given regime probabilities
        """
        self.returns = returns
        n = len(returns)
        k = self.n_regimes

        # Initialize parameters using k-means on returns
        sorted_returns = np.sort(returns)
        chunk_size = n // k
        initial_means = [np.mean(sorted_returns[i*chunk_size:(i+1)*chunk_size])
                        for i in range(k)]
        initial_vars = [np.var(sorted_returns[i*chunk_size:(i+1)*chunk_size])
                       for i in range(k)]

        # Initial transition matrix (high persistence)
        initial_trans = np.eye(k) * 0.95 + np.ones((k, k)) * 0.05 / k

        # Pack parameters for optimization
        def pack_params(means, variances, trans):
            return np.concatenate([
                means,
                np.log(variances),  # Log for positivity
                trans[:-1, :].flatten()  # Last row determined by normalization
            ])

        def unpack_params(params):
            means = params[:k]
            variances = np.exp(params[k:2*k])
            trans_flat = params[2*k:]
            trans = np.zeros((k, k))
            trans[:-1, :] = trans_flat.reshape(k-1, k)
            # Normalize rows
            for i in range(k-1):
                trans[i, :] = np.clip(trans[i, :], 0.001, 0.999)
                trans[i, :] /= trans[i, :].sum()
            trans[-1, :] = 1 - trans[:-1, :].sum(axis=0)
            trans[-1, :] = np.clip(trans[-1, :], 0.001, 0.999)
            trans[-1, :] /= trans[-1, :].sum()
            return means, variances, trans

        initial_params = pack_params(
            np.array(initial_means),
            np.array(initial_vars),
            initial_trans
        )

        # Optimize
        def neg_log_likelihood(params):
            means, variances, trans = unpack_params(params)
            try:
                ll, _, _ = self._hamilton_filter(returns, means, variances, trans)
                return -ll
            except Exception:
                return 1e10

        result = optimize.minimize(
            neg_log_likelihood,
            initial_params,
            method='L-BFGS-B',
            options={'maxiter': 1000}
        )

        # Extract final parameters
        means, variances, trans = unpack_params(result.x)

        # Run filter and smoother with final parameters
        ll, filtered_probs, pred_probs = self._hamilton_filter(
            returns, means, variances, trans
        )
        smoothed_probs = self._kim_smoother(filtered_probs, pred_probs, trans)

        # Store results
        self.regime_params = [
            RegimeParams(mean=means[i], variance=variances[i])
            for i in range(k)
        ]
        self.transition_matrix = trans

        # Label regimes by volatility (low vol = regime 0)
        vol_order = np.argsort([p.volatility for p in self.regime_params])
        for i, idx in enumerate(vol_order):
            if i == 0:
                self.regime_params[idx].label = "Low Volatility"
            elif i == k - 1:
                self.regime_params[idx].label = "High Volatility"
            else:
                self.regime_params[idx].label = f"Medium Volatility {i}"

        # Most likely regime
        predicted_regime = np.argmax(smoothed_probs, axis=1)

        # Model selection criteria
        n_params = 2 * k + k * (k - 1)  # means, variances, transition probs
        aic = 2 * n_params - 2 * ll
        bic = n_params * np.log(n) - 2 * ll

        return MarkovSwitchingResult(
            regime_params=self.regime_params,
            transition_matrix=trans,
            filtered_probs=filtered_probs,
            smoothed_probs=smoothed_probs,
            predicted_regime=predicted_regime,
            log_likelihood=ll,
            aic=aic,
            bic=bic
        )

    def _hamilton_filter(
        self,
        returns: np.ndarray,
        means: np.ndarray,
        variances: np.ndarray,
        trans: np.ndarray
    ) -> Tuple[float, np.ndarray, np.ndarray]:
        """
        Hamilton filter (forward algorithm).

        Computes P(S_t | y_1, ..., y_t) recursively.
        """
        n = len(returns)
        k = self.n_regimes

        filtered_probs = np.zeros((n, k))
        pred_probs = np.zeros((n, k))  # P(S_t | y_1:t-1)

        # Ergodic probabilities for initialization
        eigvals, eigvecs = np.linalg.eig(trans.T)
        idx = np.argmin(np.abs(eigvals - 1))
        ergodic = np.real(eigvecs[:, idx])
        ergodic = ergodic / ergodic.sum()

        pred_probs[0] = ergodic
        log_likelihood = 0

        for t in range(n):
            # Likelihood of observation in each regime
            regime_liks = np.zeros(k)
            for j in range(k):
                regime_liks[j] = stats.norm.pdf(
                    returns[t], loc=means[j], scale=np.sqrt(variances[j])
                )

            # Joint probability P(y_t, S_t | y_1:t-1)
            joint = regime_liks * pred_probs[t]

            # Marginal likelihood P(y_t | y_1:t-1)
            marginal = np.sum(joint)
            if marginal < 1e-300:
                marginal = 1e-300

            log_likelihood += np.log(marginal)

            # Filtered probability P(S_t | y_1:t)
            filtered_probs[t] = joint / marginal

            # Predicted probability for next period
            if t < n - 1:
                pred_probs[t + 1] = trans.T @ filtered_probs[t]

        return log_likelihood, filtered_probs, pred_probs

    def _kim_smoother(
        self,
        filtered_probs: np.ndarray,
        pred_probs: np.ndarray,
        trans: np.ndarray
    ) -> np.ndarray:
        """
        Kim smoother (backward algorithm).

        Computes P(S_t | y_1, ..., y_T) using backward recursion.
        """
        n, k = filtered_probs.shape
        smoothed_probs = np.zeros((n, k))
        smoothed_probs[-1] = filtered_probs[-1]

        for t in range(n - 2, -1, -1):
            for i in range(k):
                # P(S_t=i | y_1:T) = P(S_t=i | y_1:t) * Σ_j P(S_{t+1}=j | S_t=i) * P(S_{t+1}=j | y_1:T) / P(S_{t+1}=j | y_1:t)
                factor = 0
                for j in range(k):
                    if pred_probs[t + 1, j] > 1e-300:
                        factor += trans[i, j] * smoothed_probs[t + 1, j] / pred_probs[t + 1, j]
                smoothed_probs[t, i] = filtered_probs[t, i] * factor

            # Normalize
            smoothed_probs[t] /= smoothed_probs[t].sum()

        return smoothed_probs

    def predict_regime(self, horizon: int = 1) -> np.ndarray:
        """
        Predict regime probabilities for future periods.

        Uses transition matrix to extrapolate.
        """
        if self.transition_matrix is None:
            raise ValueError("Model must be fit first")

        # Start from last filtered probability
        current_prob = self._last_filtered_prob()

        predictions = np.zeros((horizon, self.n_regimes))
        for h in range(horizon):
            current_prob = self.transition_matrix.T @ current_prob
            predictions[h] = current_prob

        return predictions

    def _last_filtered_prob(self) -> np.ndarray:
        """Get last filtered probability (needs to be stored from fit)."""
        # This should be stored from fit()
        return np.ones(self.n_regimes) / self.n_regimes

    def regime_conditional_forecast(
        self,
        current_regime_probs: np.ndarray,
        horizon: int
    ) -> Dict[str, np.ndarray]:
        """
        Forecast returns conditional on regime evolution.

        Returns expected return and volatility for each horizon.
        """
        if self.regime_params is None:
            raise ValueError("Model must be fit first")

        means = np.array([p.mean for p in self.regime_params])
        vols = np.array([p.volatility for p in self.regime_params])

        expected_returns = np.zeros(horizon)
        expected_vols = np.zeros(horizon)

        prob = current_regime_probs.copy()
        for h in range(horizon):
            prob = self.transition_matrix.T @ prob
            expected_returns[h] = np.sum(prob * means)
            expected_vols[h] = np.sqrt(np.sum(prob * vols**2))

        return {
            'expected_return': expected_returns,
            'expected_volatility': expected_vols,
            'regime_probs': self.predict_regime(horizon)
        }


class ThreeRegimeModel(MarkovSwitchingModel):
    """
    Three-regime model: Normal, Expansion, Crisis

    Commonly used characterization:
    - Regime 0: Low volatility, moderate positive returns (normal)
    - Regime 1: Low volatility, high returns (expansion/bubble)
    - Regime 2: High volatility, negative returns (crisis)
    """

    def __init__(self):
        super().__init__(n_regimes=3)

    def fit(self, returns: np.ndarray) -> MarkovSwitchingResult:
        result = super().fit(returns)

        # Relabel based on characteristics
        for i, param in enumerate(result.regime_params):
            if param.volatility > np.median([p.volatility for p in result.regime_params]) * 1.5:
                param.label = "Crisis"
            elif param.mean > np.median([p.mean for p in result.regime_params]):
                param.label = "Expansion"
            else:
                param.label = "Normal"

        return result


class RegimeAwareStrategy:
    """
    Trading strategy that adapts to detected regime.

    Example applications:
    - Use momentum in trending regimes
    - Use mean-reversion in normal regimes
    - Reduce exposure in crisis regimes
    """

    def __init__(self, regime_model: MarkovSwitchingModel):
        self.regime_model = regime_model

        # Strategy parameters per regime
        self.regime_strategies = {
            'Crisis': {'exposure': 0.2, 'strategy': 'defensive'},
            'Normal': {'exposure': 1.0, 'strategy': 'balanced'},
            'Expansion': {'exposure': 1.5, 'strategy': 'momentum'},
            'High Volatility': {'exposure': 0.5, 'strategy': 'mean_reversion'},
            'Low Volatility': {'exposure': 1.2, 'strategy': 'momentum'}
        }

    def get_position_adjustment(
        self,
        current_regime_probs: np.ndarray
    ) -> Tuple[float, str]:
        """
        Get position adjustment based on regime probabilities.

        Returns:
            Tuple of (exposure_multiplier, suggested_strategy)
        """
        if self.regime_model.regime_params is None:
            return 1.0, 'unknown'

        # Weighted average of regime-specific exposures
        total_exposure = 0
        strategy_votes = {}

        for i, param in enumerate(self.regime_model.regime_params):
            label = param.label or f"Regime_{i}"
            prob = current_regime_probs[i]

            if label in self.regime_strategies:
                regime_config = self.regime_strategies[label]
                total_exposure += prob * regime_config['exposure']
                strat = regime_config['strategy']
                strategy_votes[strat] = strategy_votes.get(strat, 0) + prob

        # Most probable strategy
        best_strategy = max(strategy_votes.keys(), key=lambda k: strategy_votes[k])

        return total_exposure, best_strategy


def detect_regime_change(
    smoothed_probs: np.ndarray,
    threshold: float = 0.7
) -> List[int]:
    """
    Detect regime change points.

    A regime change is detected when the most likely regime changes
    and the new regime has probability > threshold.
    """
    most_likely = np.argmax(smoothed_probs, axis=1)
    max_probs = np.max(smoothed_probs, axis=1)

    change_points = []
    for t in range(1, len(most_likely)):
        if most_likely[t] != most_likely[t-1] and max_probs[t] > threshold:
            change_points.append(t)

    return change_points


def expected_regime_duration(transition_matrix: np.ndarray) -> np.ndarray:
    """
    Compute expected duration (in periods) of each regime.

    E[duration of regime i] = 1 / (1 - p_ii)
    """
    return 1 / (1 - np.diag(transition_matrix))
