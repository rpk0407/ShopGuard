"""
Kalman Filtering for Financial Time Series

The Kalman filter is THE optimal linear filter for extracting signal
from noisy observations when both signal and noise are Gaussian.

Trading Applications:
1. Trend extraction (what's the "true" trend?)
2. Spread estimation for pairs trading
3. Dynamic beta estimation
4. Volatility filtering
5. Latent state estimation (market regime)
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class KalmanState:
    """Current state of Kalman filter."""
    state_mean: np.ndarray        # Estimated state μ
    state_covariance: np.ndarray  # Uncertainty in state Σ
    prediction_mean: float        # Predicted observation
    prediction_variance: float    # Uncertainty in prediction
    kalman_gain: np.ndarray       # How much to trust new observation


class KalmanFilter:
    """
    Kalman Filter for linear dynamical systems.

    State-space model:
    - State equation: x_t = F·x_{t-1} + w_t  (hidden state evolution)
    - Observation equation: y_t = H·x_t + v_t  (what we observe)

    Where:
    - x_t: Hidden state (e.g., true price, trend, beta)
    - y_t: Observed value (noisy price)
    - F: State transition matrix
    - H: Observation matrix
    - w_t ~ N(0, Q): Process noise
    - v_t ~ N(0, R): Observation noise

    The Kalman filter provides:
    1. PREDICTION: Where will state be next?
    2. UPDATE: How to incorporate new observation?
    3. SMOOTHING: Best estimate given ALL data (past and future)
    """

    def __init__(
        self,
        state_dim: int,
        obs_dim: int,
        F: np.ndarray,
        H: np.ndarray,
        Q: np.ndarray,
        R: np.ndarray,
        initial_state: np.ndarray = None,
        initial_covariance: np.ndarray = None
    ):
        """
        Initialize Kalman filter.

        Args:
            state_dim: Dimension of hidden state
            obs_dim: Dimension of observation
            F: State transition matrix (state_dim x state_dim)
            H: Observation matrix (obs_dim x state_dim)
            Q: Process noise covariance (state_dim x state_dim)
            R: Observation noise covariance (obs_dim x obs_dim)
            initial_state: Initial state estimate
            initial_covariance: Initial uncertainty
        """
        self.state_dim = state_dim
        self.obs_dim = obs_dim
        self.F = F
        self.H = H
        self.Q = Q
        self.R = R

        # Initialize state
        self.state = initial_state if initial_state is not None else np.zeros(state_dim)
        self.covariance = initial_covariance if initial_covariance is not None else np.eye(state_dim) * 100

    def predict(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prediction step: project state forward in time.

        x̂_{t|t-1} = F · x̂_{t-1|t-1}
        P_{t|t-1} = F · P_{t-1|t-1} · F' + Q
        """
        predicted_state = self.F @ self.state
        predicted_covariance = self.F @ self.covariance @ self.F.T + self.Q

        return predicted_state, predicted_covariance

    def update(self, observation: np.ndarray) -> KalmanState:
        """
        Update step: incorporate new observation.

        Innovation: z_t = y_t - H · x̂_{t|t-1}
        Innovation covariance: S_t = H · P_{t|t-1} · H' + R
        Kalman gain: K_t = P_{t|t-1} · H' · S_t^{-1}
        Updated state: x̂_{t|t} = x̂_{t|t-1} + K_t · z_t
        Updated covariance: P_{t|t} = (I - K_t · H) · P_{t|t-1}

        Returns:
            KalmanState with updated estimates
        """
        # Predict
        predicted_state, predicted_covariance = self.predict()

        # Innovation (prediction error)
        predicted_obs = self.H @ predicted_state
        innovation = observation - predicted_obs

        # Innovation covariance
        S = self.H @ predicted_covariance @ self.H.T + self.R

        # Kalman gain
        K = predicted_covariance @ self.H.T @ np.linalg.inv(S)

        # Update state
        self.state = predicted_state + K @ innovation
        self.covariance = (np.eye(self.state_dim) - K @ self.H) @ predicted_covariance

        return KalmanState(
            state_mean=self.state.copy(),
            state_covariance=self.covariance.copy(),
            prediction_mean=float(predicted_obs),
            prediction_variance=float(S),
            kalman_gain=K.copy()
        )

    def filter(self, observations: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run filter over entire observation sequence.

        Args:
            observations: Array of observations (T x obs_dim)

        Returns:
            Tuple of (filtered_states, filtered_covariances)
        """
        T = len(observations)
        filtered_states = np.zeros((T, self.state_dim))
        filtered_variances = np.zeros((T, self.state_dim, self.state_dim))

        for t in range(T):
            obs = observations[t] if observations.ndim > 1 else np.array([observations[t]])
            state = self.update(obs)
            filtered_states[t] = state.state_mean
            filtered_variances[t] = state.state_covariance

        return filtered_states, filtered_variances


class AdaptiveKalman:
    """
    Adaptive Kalman filter with time-varying noise estimation.

    In financial markets, both process noise (volatility) and
    observation noise vary over time. This filter adapts to these changes.

    Uses innovation-based adaptation:
    - If innovations are consistently large, increase Q
    - If innovations are consistently small, decrease Q
    """

    def __init__(
        self,
        initial_process_variance: float = 0.001,
        initial_obs_variance: float = 0.01,
        adaptation_rate: float = 0.1
    ):
        """
        Initialize adaptive 1D Kalman filter.

        Args:
            initial_process_variance: Initial Q (how much state changes)
            initial_obs_variance: Initial R (measurement noise)
            adaptation_rate: How fast to adapt Q and R (0-1)
        """
        self.Q = initial_process_variance
        self.R = initial_obs_variance
        self.adaptation_rate = adaptation_rate

        # State
        self.state = 0.0
        self.variance = 1.0

        # For adaptation
        self.innovation_sq_ma = 0.0

    def update(self, observation: float) -> Tuple[float, float]:
        """
        Update with new observation, adapting noise parameters.

        Returns:
            Tuple of (filtered_state, uncertainty)
        """
        # Predict
        predicted_state = self.state
        predicted_variance = self.variance + self.Q

        # Innovation
        innovation = observation - predicted_state
        S = predicted_variance + self.R

        # Kalman gain
        K = predicted_variance / S

        # Update state
        self.state = predicted_state + K * innovation
        self.variance = (1 - K) * predicted_variance

        # Adapt noise parameters based on innovation
        innovation_sq = innovation ** 2
        self.innovation_sq_ma = (
            self.adaptation_rate * innovation_sq +
            (1 - self.adaptation_rate) * self.innovation_sq_ma
        )

        # If innovations are larger than expected, increase Q
        expected_innovation_sq = S
        ratio = self.innovation_sq_ma / expected_innovation_sq

        if ratio > 1.5:
            self.Q *= (1 + self.adaptation_rate)
        elif ratio < 0.5:
            self.Q *= (1 - self.adaptation_rate * 0.5)

        # Keep Q bounded
        self.Q = np.clip(self.Q, 1e-6, 1.0)

        return self.state, self.variance

    def filter(self, observations: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Filter entire series."""
        T = len(observations)
        states = np.zeros(T)
        variances = np.zeros(T)

        # Initialize with first observation
        self.state = observations[0]
        self.variance = self.R

        for t in range(T):
            states[t], variances[t] = self.update(observations[t])

        return states, variances


def create_trend_filter(
    process_variance: float = 0.001,
    observation_variance: float = 0.01
) -> KalmanFilter:
    """
    Create Kalman filter for trend extraction.

    Local Linear Trend model:
    - State: [level, slope]
    - Level evolves: level_t = level_{t-1} + slope_{t-1} + w1
    - Slope evolves: slope_t = slope_{t-1} + w2
    - Observation: y_t = level_t + v_t
    """
    # State transition
    F = np.array([
        [1, 1],  # level_t = level_{t-1} + slope_{t-1}
        [0, 1]   # slope_t = slope_{t-1}
    ])

    # Observation matrix
    H = np.array([[1, 0]])  # We only observe level

    # Process noise (level and slope can deviate)
    Q = np.array([
        [process_variance, 0],
        [0, process_variance * 0.1]  # Slope changes more slowly
    ])

    # Observation noise
    R = np.array([[observation_variance]])

    return KalmanFilter(
        state_dim=2,
        obs_dim=1,
        F=F,
        H=H,
        Q=Q,
        R=R
    )


def create_beta_filter(
    beta_variance: float = 0.001,
    observation_variance: float = 0.01
) -> KalmanFilter:
    """
    Create Kalman filter for dynamic beta estimation.

    Model: y_t = alpha_t + beta_t * x_t + e_t

    Where beta is time-varying (random walk).
    Used for pairs trading and hedging.
    """
    # State: [alpha, beta]
    F = np.eye(2)  # Random walk on both

    # H is time-varying and will be set per observation
    H = np.array([[1, 0]])  # Placeholder

    Q = np.diag([beta_variance * 0.1, beta_variance])
    R = np.array([[observation_variance]])

    return KalmanFilter(
        state_dim=2,
        obs_dim=1,
        F=F,
        H=H,
        Q=Q,
        R=R
    )


def dynamic_hedge_ratio(
    y: np.ndarray,
    x: np.ndarray,
    beta_variance: float = 0.0001
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Estimate time-varying hedge ratio using Kalman filter.

    For pairs trading: y_t = alpha_t + beta_t * x_t + e_t

    The beta_t is our hedge ratio, and it's allowed to vary over time.

    Args:
        y: Dependent variable (asset we're trading)
        x: Independent variable (asset we're hedging with)
        beta_variance: How much beta can change per period

    Returns:
        Tuple of (alphas, betas) - time series of estimated parameters
    """
    T = len(y)

    # Initialize
    state = np.array([0.0, 1.0])  # [alpha, beta]
    covariance = np.eye(2) * 10

    F = np.eye(2)
    Q = np.diag([beta_variance * 0.1, beta_variance])
    R = np.var(y - x) * 0.1  # Rough initial estimate

    alphas = np.zeros(T)
    betas = np.zeros(T)

    for t in range(T):
        # Time-varying observation matrix
        H = np.array([[1, x[t]]])

        # Predict
        predicted_state = F @ state
        predicted_cov = F @ covariance @ F.T + Q

        # Update
        y_pred = H @ predicted_state
        innovation = y[t] - y_pred
        S = H @ predicted_cov @ H.T + R
        K = predicted_cov @ H.T / S

        state = predicted_state + K.flatten() * innovation
        covariance = (np.eye(2) - np.outer(K, H)) @ predicted_cov

        alphas[t] = state[0]
        betas[t] = state[1]

    return alphas, betas
