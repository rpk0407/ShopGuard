"""
Market Regime Classifier

Specialized model for identifying market regimes:
- Bull/Bear markets
- High/Low volatility periods
- Trending vs Range-bound
- Risk-on/Risk-off environments
- Liquidity conditions

Uses Hidden Markov Models + Neural Networks for regime detection.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from collections import deque


class MarketRegime(Enum):
    STRONG_BULL = "strong_bull"
    BULL = "bull"
    NEUTRAL = "neutral"
    BEAR = "bear"
    STRONG_BEAR = "strong_bear"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRENDING = "trending"
    RANGE_BOUND = "range_bound"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    CRISIS = "crisis"
    RECOVERY = "recovery"


class VolatilityRegime(Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


class TrendStrength(Enum):
    STRONG_DOWN = -2
    DOWN = -1
    NEUTRAL = 0
    UP = 1
    STRONG_UP = 2


@dataclass
class RegimeState:
    primary_regime: MarketRegime
    volatility_regime: VolatilityRegime
    trend_strength: TrendStrength
    confidence: float
    duration: int  # How long in this regime
    transition_probability: float  # Probability of regime change
    features: Dict[str, float]


class HiddenMarkovModel:
    """Hidden Markov Model for regime detection"""

    def __init__(self, n_states: int = 5):
        self.n_states = n_states
        # Transition matrix (state i -> state j)
        self.A = np.ones((n_states, n_states)) / n_states
        # Emission probabilities (Gaussian parameters)
        self.means = np.linspace(-0.02, 0.02, n_states)
        self.stds = np.ones(n_states) * 0.01
        # Initial state distribution
        self.pi = np.ones(n_states) / n_states
        # Current state probabilities
        self.state_probs = np.ones(n_states) / n_states

    def _emission_prob(self, observation: float, state: int) -> float:
        """Gaussian emission probability"""
        z = (observation - self.means[state]) / self.stds[state]
        return np.exp(-0.5 * z * z) / (self.stds[state] * np.sqrt(2 * np.pi))

    def forward_step(self, observation: float) -> np.ndarray:
        """Single forward step of HMM"""
        emissions = np.array([self._emission_prob(observation, s) for s in range(self.n_states)])
        new_probs = emissions * (self.A.T @ self.state_probs)
        new_probs /= new_probs.sum() + 1e-10
        self.state_probs = new_probs
        return new_probs

    def predict_state(self, observations: np.ndarray) -> int:
        """Predict most likely current state"""
        for obs in observations:
            self.forward_step(obs)
        return np.argmax(self.state_probs)

    def fit(self, observations: np.ndarray, n_iterations: int = 10):
        """Baum-Welch algorithm for parameter estimation"""
        n = len(observations)
        for _ in range(n_iterations):
            # E-step: Forward-backward
            alpha = np.zeros((n, self.n_states))
            beta = np.zeros((n, self.n_states))

            # Forward
            for s in range(self.n_states):
                alpha[0, s] = self.pi[s] * self._emission_prob(observations[0], s)
            alpha[0] /= alpha[0].sum() + 1e-10

            for t in range(1, n):
                for s in range(self.n_states):
                    alpha[t, s] = self._emission_prob(observations[t], s) * (alpha[t-1] @ self.A[:, s])
                alpha[t] /= alpha[t].sum() + 1e-10

            # Backward
            beta[-1] = 1
            for t in range(n-2, -1, -1):
                for s in range(self.n_states):
                    beta[t, s] = sum(self.A[s, j] * self._emission_prob(observations[t+1], j) * beta[t+1, j]
                                     for j in range(self.n_states))
                beta[t] /= beta[t].sum() + 1e-10

            # M-step: Update parameters
            gamma = alpha * beta
            gamma /= gamma.sum(axis=1, keepdims=True) + 1e-10

            # Update means and stds
            for s in range(self.n_states):
                weights = gamma[:, s]
                self.means[s] = np.sum(weights * observations) / (np.sum(weights) + 1e-10)
                self.stds[s] = np.sqrt(np.sum(weights * (observations - self.means[s])**2) / (np.sum(weights) + 1e-10))
                self.stds[s] = max(self.stds[s], 0.001)

            # Update transition matrix
            for i in range(self.n_states):
                for j in range(self.n_states):
                    num = sum(gamma[t, i] * self.A[i, j] * self._emission_prob(observations[t+1], j) * beta[t+1, j]
                              for t in range(n-1))
                    self.A[i, j] = num / (gamma[:-1, i].sum() + 1e-10)
            self.A /= self.A.sum(axis=1, keepdims=True) + 1e-10


class VolatilityEstimator:
    """Estimate volatility using multiple methods"""

    def __init__(self, window: int = 20):
        self.window = window
        self.history = deque(maxlen=252)  # 1 year of data

    def add_return(self, ret: float):
        self.history.append(ret)

    def realized_volatility(self) -> float:
        """Standard deviation of returns"""
        if len(self.history) < 2:
            return 0.02
        return np.std(list(self.history)[-self.window:]) * np.sqrt(252)

    def parkinson_volatility(self, highs: np.ndarray, lows: np.ndarray) -> float:
        """Parkinson volatility using high-low range"""
        log_hl = np.log(highs / lows)
        return np.sqrt(np.mean(log_hl**2) / (4 * np.log(2))) * np.sqrt(252)

    def garman_klass_volatility(self, opens: np.ndarray, highs: np.ndarray,
                                 lows: np.ndarray, closes: np.ndarray) -> float:
        """Garman-Klass volatility estimator"""
        log_hl = np.log(highs / lows)
        log_co = np.log(closes / opens)
        term1 = 0.5 * log_hl**2
        term2 = (2 * np.log(2) - 1) * log_co**2
        return np.sqrt(np.mean(term1 - term2) * 252)

    def classify_regime(self, vol: float) -> VolatilityRegime:
        """Classify volatility regime"""
        if vol < 0.10:
            return VolatilityRegime.VERY_LOW
        elif vol < 0.15:
            return VolatilityRegime.LOW
        elif vol < 0.25:
            return VolatilityRegime.NORMAL
        elif vol < 0.40:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME


class TrendDetector:
    """Detect trend strength and direction"""

    def __init__(self):
        self.ema_short = None
        self.ema_long = None

    def update(self, price: float, short_period: int = 20, long_period: int = 50):
        """Update EMAs"""
        alpha_short = 2 / (short_period + 1)
        alpha_long = 2 / (long_period + 1)

        if self.ema_short is None:
            self.ema_short = price
            self.ema_long = price
        else:
            self.ema_short = alpha_short * price + (1 - alpha_short) * self.ema_short
            self.ema_long = alpha_long * price + (1 - alpha_long) * self.ema_long

    def get_trend(self, prices: np.ndarray) -> TrendStrength:
        """Calculate trend strength"""
        if len(prices) < 20:
            return TrendStrength.NEUTRAL

        # Update with all prices
        for p in prices:
            self.update(p)

        # Calculate trend metrics
        short_vs_long = (self.ema_short - self.ema_long) / self.ema_long

        # ADX-like calculation
        returns = np.diff(prices) / prices[:-1]
        up_moves = np.where(returns > 0, returns, 0)
        down_moves = np.where(returns < 0, -returns, 0)

        avg_up = np.mean(up_moves[-14:]) if len(up_moves) >= 14 else np.mean(up_moves)
        avg_down = np.mean(down_moves[-14:]) if len(down_moves) >= 14 else np.mean(down_moves)

        if avg_up + avg_down > 0:
            dmi = (avg_up - avg_down) / (avg_up + avg_down)
        else:
            dmi = 0

        # Combine signals
        trend_score = short_vs_long * 50 + dmi * 0.5

        if trend_score > 0.03:
            return TrendStrength.STRONG_UP
        elif trend_score > 0.01:
            return TrendStrength.UP
        elif trend_score < -0.03:
            return TrendStrength.STRONG_DOWN
        elif trend_score < -0.01:
            return TrendStrength.DOWN
        else:
            return TrendStrength.NEUTRAL


class RegimeNeuralNetwork:
    """Neural network for regime classification"""

    def __init__(self, input_size: int = 20, hidden_size: int = 64, n_regimes: int = 5):
        self.W1 = np.random.randn(input_size, hidden_size) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros(hidden_size)
        self.W2 = np.random.randn(hidden_size, hidden_size // 2) * np.sqrt(2.0 / hidden_size)
        self.b2 = np.zeros(hidden_size // 2)
        self.W3 = np.random.randn(hidden_size // 2, n_regimes) * np.sqrt(2.0 / (hidden_size // 2))
        self.b3 = np.zeros(n_regimes)

    def forward(self, x: np.ndarray) -> np.ndarray:
        h1 = np.maximum(0, np.dot(x, self.W1) + self.b1)
        h2 = np.maximum(0, np.dot(h1, self.W2) + self.b2)
        logits = np.dot(h2, self.W3) + self.b3
        exp_x = np.exp(logits - np.max(logits))
        return exp_x / exp_x.sum()

    def predict(self, features: np.ndarray) -> Tuple[int, float]:
        probs = self.forward(features)
        regime_idx = np.argmax(probs)
        confidence = probs[regime_idx]
        return regime_idx, confidence


class MarketRegimeClassifier:
    """Complete market regime classification system"""

    def __init__(self):
        self.hmm = HiddenMarkovModel(n_states=5)
        self.volatility = VolatilityEstimator()
        self.trend = TrendDetector()
        self.nn = RegimeNeuralNetwork()

        # Regime history
        self.regime_history: List[RegimeState] = []
        self.current_regime: Optional[RegimeState] = None
        self.regime_duration = 0

        # Regime mapping
        self.hmm_to_regime = {
            0: MarketRegime.STRONG_BEAR,
            1: MarketRegime.BEAR,
            2: MarketRegime.NEUTRAL,
            3: MarketRegime.BULL,
            4: MarketRegime.STRONG_BULL
        }

    def extract_features(self, prices: np.ndarray, volumes: Optional[np.ndarray] = None) -> np.ndarray:
        """Extract features for regime classification"""
        returns = np.diff(prices) / prices[:-1]

        features = []
        # Return statistics
        features.append(np.mean(returns[-20:]) if len(returns) >= 20 else np.mean(returns))
        features.append(np.std(returns[-20:]) if len(returns) >= 20 else np.std(returns))
        features.append(np.mean(returns[-5:]) if len(returns) >= 5 else np.mean(returns))

        # Momentum
        if len(prices) >= 20:
            features.append((prices[-1] / prices[-20] - 1))
        else:
            features.append(0)

        if len(prices) >= 50:
            features.append((prices[-1] / prices[-50] - 1))
        else:
            features.append(0)

        # Volatility
        features.append(self.volatility.realized_volatility())

        # Skewness and kurtosis
        if len(returns) >= 20:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                skew = np.mean(((returns - mean_ret) / std_ret) ** 3)
                kurt = np.mean(((returns - mean_ret) / std_ret) ** 4) - 3
            else:
                skew, kurt = 0, 0
            features.extend([skew, kurt])
        else:
            features.extend([0, 0])

        # Up/down ratio
        up_days = np.sum(returns > 0)
        down_days = np.sum(returns < 0)
        features.append(up_days / (down_days + 1))

        # Max drawdown
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (running_max - cumulative) / running_max
        features.append(np.max(drawdown))

        # Volume features
        if volumes is not None and len(volumes) >= 20:
            features.append(np.mean(volumes[-5:]) / np.mean(volumes[-20:]))
            features.append(np.std(volumes[-20:]) / np.mean(volumes[-20:]))
        else:
            features.extend([1.0, 0.5])

        # Trend strength
        trend = self.trend.get_trend(prices)
        features.append(trend.value / 2)

        # Autocorrelation
        if len(returns) >= 10:
            autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
            features.append(autocorr if not np.isnan(autocorr) else 0)
        else:
            features.append(0)

        # Pad to expected size
        while len(features) < 20:
            features.append(0)

        return np.array(features[:20])

    def classify(self, prices: np.ndarray, volumes: Optional[np.ndarray] = None) -> RegimeState:
        """Classify current market regime"""
        returns = np.diff(prices) / prices[:-1]

        # Update volatility estimator
        for r in returns[-20:]:
            self.volatility.add_return(r)

        # HMM prediction
        hmm_state = self.hmm.predict_state(returns[-50:] if len(returns) >= 50 else returns)
        primary_regime = self.hmm_to_regime[hmm_state]

        # Volatility regime
        vol = self.volatility.realized_volatility()
        vol_regime = self.volatility.classify_regime(vol)

        # Trend strength
        trend = self.trend.get_trend(prices)

        # Neural network for confidence
        features = self.extract_features(prices, volumes)
        nn_regime, nn_confidence = self.nn.predict(features)

        # Combine confidences
        confidence = (self.hmm.state_probs[hmm_state] + nn_confidence) / 2

        # Check for regime change
        if self.current_regime and self.current_regime.primary_regime == primary_regime:
            self.regime_duration += 1
        else:
            self.regime_duration = 1

        # Transition probability
        if self.regime_duration > 1:
            transition_prob = 1 - (1 - 0.1) ** self.regime_duration  # Increasing with duration
        else:
            transition_prob = 0.1

        # Override for extreme conditions
        if vol_regime == VolatilityRegime.EXTREME and trend.value <= -1:
            primary_regime = MarketRegime.CRISIS
            confidence = 0.9
        elif vol_regime == VolatilityRegime.VERY_LOW and trend.value >= 1:
            primary_regime = MarketRegime.STRONG_BULL
            confidence = 0.85

        state = RegimeState(
            primary_regime=primary_regime,
            volatility_regime=vol_regime,
            trend_strength=trend,
            confidence=confidence,
            duration=self.regime_duration,
            transition_probability=transition_prob,
            features={
                'volatility': vol,
                'momentum_20d': features[3] if len(features) > 3 else 0,
                'momentum_50d': features[4] if len(features) > 4 else 0,
                'max_drawdown': features[9] if len(features) > 9 else 0
            }
        )

        self.current_regime = state
        self.regime_history.append(state)

        return state

    def get_trading_bias(self) -> Dict[str, Any]:
        """Get trading bias based on current regime"""
        if not self.current_regime:
            return {'bias': 'neutral', 'position_size': 1.0, 'risk_level': 'normal'}

        regime = self.current_regime.primary_regime
        vol_regime = self.current_regime.volatility_regime

        # Determine bias
        if regime in [MarketRegime.STRONG_BULL, MarketRegime.BULL, MarketRegime.RISK_ON]:
            bias = 'long'
            base_size = 1.2 if regime == MarketRegime.STRONG_BULL else 1.0
        elif regime in [MarketRegime.STRONG_BEAR, MarketRegime.BEAR, MarketRegime.CRISIS]:
            bias = 'short'
            base_size = 1.2 if regime == MarketRegime.STRONG_BEAR else 1.0
        else:
            bias = 'neutral'
            base_size = 0.8

        # Adjust for volatility
        vol_adjustments = {
            VolatilityRegime.VERY_LOW: 1.3,
            VolatilityRegime.LOW: 1.1,
            VolatilityRegime.NORMAL: 1.0,
            VolatilityRegime.HIGH: 0.7,
            VolatilityRegime.EXTREME: 0.4
        }
        position_size = base_size * vol_adjustments[vol_regime]

        # Risk level
        if vol_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
            risk_level = 'elevated'
        elif regime == MarketRegime.CRISIS:
            risk_level = 'crisis'
        else:
            risk_level = 'normal'

        return {
            'bias': bias,
            'position_size': round(position_size, 2),
            'risk_level': risk_level,
            'regime': regime.value,
            'volatility': vol_regime.value,
            'confidence': self.current_regime.confidence,
            'trend': self.current_regime.trend_strength.name
        }

    def fit(self, prices: np.ndarray):
        """Train the regime classifier on historical data"""
        returns = np.diff(prices) / prices[:-1]
        self.hmm.fit(returns)


class MultiAssetRegimeAnalyzer:
    """Analyze regimes across multiple assets for correlation/divergence"""

    def __init__(self):
        self.classifiers: Dict[str, MarketRegimeClassifier] = {}
        self.correlations: Dict[Tuple[str, str], float] = {}

    def add_asset(self, symbol: str):
        self.classifiers[symbol] = MarketRegimeClassifier()

    def update(self, symbol: str, prices: np.ndarray, volumes: Optional[np.ndarray] = None) -> RegimeState:
        if symbol not in self.classifiers:
            self.add_asset(symbol)
        return self.classifiers[symbol].classify(prices, volumes)

    def get_market_consensus(self) -> Dict[str, Any]:
        """Get consensus regime across all assets"""
        if not self.classifiers:
            return {'consensus': 'unknown', 'agreement': 0}

        regimes = [c.current_regime.primary_regime for c in self.classifiers.values() if c.current_regime]
        if not regimes:
            return {'consensus': 'unknown', 'agreement': 0}

        # Count regimes
        from collections import Counter
        counts = Counter(regimes)
        most_common = counts.most_common(1)[0]

        return {
            'consensus': most_common[0].value,
            'agreement': most_common[1] / len(regimes),
            'distribution': {r.value: c / len(regimes) for r, c in counts.items()}
        }

    def detect_divergences(self) -> List[Dict]:
        """Detect diverging regimes between correlated assets"""
        divergences = []
        symbols = list(self.classifiers.keys())

        for i, s1 in enumerate(symbols):
            for s2 in symbols[i+1:]:
                c1, c2 = self.classifiers[s1], self.classifiers[s2]
                if c1.current_regime and c2.current_regime:
                    r1, r2 = c1.current_regime.primary_regime, c2.current_regime.primary_regime

                    # Check for divergence
                    bullish = {MarketRegime.STRONG_BULL, MarketRegime.BULL, MarketRegime.RISK_ON}
                    bearish = {MarketRegime.STRONG_BEAR, MarketRegime.BEAR, MarketRegime.CRISIS}

                    if (r1 in bullish and r2 in bearish) or (r1 in bearish and r2 in bullish):
                        divergences.append({
                            'asset1': s1, 'regime1': r1.value,
                            'asset2': s2, 'regime2': r2.value,
                            'type': 'regime_divergence'
                        })

        return divergences
