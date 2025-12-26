"""
Feature Engineering for Trading ML

Features are the bridge between raw data and model predictions.

CRITICAL PRINCIPLES:
1. NO LOOKAHEAD: Features must only use past data at each point
2. NORMALIZATION: Features should be stationary (or made stationary)
3. ROBUSTNESS: Handle missing data, outliers, regime changes
4. INTERPRETABILITY: Know what each feature represents

Feature Categories:
- Price-based: Returns, volatility, momentum
- Volume-based: Relative volume, order flow
- Technical: Support/resistance, patterns
- Order book: Bid-ask spread, depth imbalance
- Sentiment: News, social media, analyst ratings
- Macro: Rates, VIX, sector performance
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Callable
from enum import Enum


class FeatureCategory(Enum):
    """Categories of features."""
    PRICE = "price"
    VOLUME = "volume"
    TECHNICAL = "technical"
    ORDERBOOK = "orderbook"
    SENTIMENT = "sentiment"
    MACRO = "macro"


@dataclass
class FeatureSet:
    """Container for feature data and metadata."""
    values: np.ndarray                      # (T, n_features)
    names: List[str]                        # Feature names
    categories: Dict[str, FeatureCategory]  # Name -> category mapping
    lookback: int                           # Required history
    timestamp_idx: Optional[np.ndarray] = None


class FeatureEngineer:
    """
    Feature engineering pipeline for trading.

    Handles:
    - Feature computation with proper alignment
    - Normalization (z-score, rank, etc.)
    - Feature selection
    - Missing value handling
    """

    def __init__(self, price_col: str = "close"):
        self.price_col = price_col
        self.feature_funcs: Dict[str, Callable] = {}
        self.normalization_params: Dict[str, Tuple[float, float]] = {}

        # Register default features
        self._register_default_features()

    def _register_default_features(self):
        """Register standard trading features."""
        # Price features
        self.register_feature("returns_1d", self._compute_returns, {"period": 1})
        self.register_feature("returns_5d", self._compute_returns, {"period": 5})
        self.register_feature("returns_21d", self._compute_returns, {"period": 21})

        # Volatility features
        self.register_feature("volatility_10d", self._compute_volatility, {"window": 10})
        self.register_feature("volatility_21d", self._compute_volatility, {"window": 21})
        self.register_feature("volatility_ratio", self._compute_vol_ratio, {})

        # Momentum features
        self.register_feature("momentum_roc_10", self._compute_roc, {"period": 10})
        self.register_feature("momentum_roc_21", self._compute_roc, {"period": 21})

        # Mean reversion features
        self.register_feature("zscore_20", self._compute_zscore, {"window": 20})
        self.register_feature("zscore_60", self._compute_zscore, {"window": 60})

        # Trend features
        self.register_feature("trend_strength", self._compute_trend_strength, {})
        self.register_feature("price_vs_ma20", self._compute_price_vs_ma, {"window": 20})
        self.register_feature("price_vs_ma50", self._compute_price_vs_ma, {"window": 50})

    def register_feature(
        self,
        name: str,
        func: Callable,
        params: dict
    ):
        """Register a feature computation function."""
        self.feature_funcs[name] = (func, params)

    def compute_features(
        self,
        prices: np.ndarray,
        volumes: Optional[np.ndarray] = None,
        high: Optional[np.ndarray] = None,
        low: Optional[np.ndarray] = None,
        normalize: bool = True
    ) -> FeatureSet:
        """
        Compute all registered features.

        Args:
            prices: Close prices
            volumes: Optional volume data
            high: Optional high prices
            low: Optional low prices
            normalize: Whether to normalize features

        Returns:
            FeatureSet with computed features
        """
        features = {}
        max_lookback = 0

        for name, (func, params) in self.feature_funcs.items():
            try:
                feature_values = func(
                    prices=prices,
                    volumes=volumes,
                    high=high,
                    low=low,
                    **params
                )
                features[name] = feature_values

                # Track lookback
                first_valid = np.argmax(~np.isnan(feature_values))
                max_lookback = max(max_lookback, first_valid)

            except Exception as e:
                print(f"Warning: Failed to compute {name}: {e}")
                features[name] = np.full(len(prices), np.nan)

        # Stack features
        feature_matrix = np.column_stack([features[name] for name in features.keys()])
        feature_names = list(features.keys())

        # Handle NaN values
        feature_matrix = self._handle_missing(feature_matrix)

        # Normalize
        if normalize:
            feature_matrix = self._normalize_features(feature_matrix, feature_names)

        return FeatureSet(
            values=feature_matrix,
            names=feature_names,
            categories={name: FeatureCategory.PRICE for name in feature_names},
            lookback=max_lookback
        )

    def _handle_missing(self, features: np.ndarray) -> np.ndarray:
        """Handle missing values with forward fill then mean."""
        result = features.copy()

        for col in range(features.shape[1]):
            # Forward fill
            mask = np.isnan(result[:, col])
            idx = np.where(~mask, np.arange(len(mask)), 0)
            np.maximum.accumulate(idx, out=idx)
            result[:, col] = result[idx, col]

            # Fill remaining with column mean
            remaining_nan = np.isnan(result[:, col])
            if remaining_nan.any():
                col_mean = np.nanmean(result[:, col])
                result[remaining_nan, col] = col_mean if not np.isnan(col_mean) else 0

        return result

    def _normalize_features(
        self,
        features: np.ndarray,
        names: List[str]
    ) -> np.ndarray:
        """
        Normalize features using rolling z-score.

        Rolling normalization is crucial because:
        1. Financial distributions change over time
        2. Static normalization would cause lookahead bias
        3. Recent statistics are more relevant
        """
        window = 252  # One year rolling window
        result = np.zeros_like(features)

        for t in range(len(features)):
            start = max(0, t - window)
            window_data = features[start:t+1]

            if len(window_data) < 20:
                # Not enough data, use expanding window
                mean = np.nanmean(features[:t+1], axis=0)
                std = np.nanstd(features[:t+1], axis=0) + 1e-8
            else:
                mean = np.nanmean(window_data, axis=0)
                std = np.nanstd(window_data, axis=0) + 1e-8

            result[t] = (features[t] - mean) / std

        # Clip extreme values
        result = np.clip(result, -5, 5)

        return result

    # =========================================================================
    # Feature Computation Functions
    # =========================================================================

    def _compute_returns(
        self,
        prices: np.ndarray,
        period: int = 1,
        **kwargs
    ) -> np.ndarray:
        """Simple returns over period."""
        returns = np.full(len(prices), np.nan)
        returns[period:] = (prices[period:] - prices[:-period]) / prices[:-period]
        return returns

    def _compute_volatility(
        self,
        prices: np.ndarray,
        window: int = 20,
        **kwargs
    ) -> np.ndarray:
        """Rolling volatility (annualized)."""
        returns = np.diff(np.log(prices))
        vol = np.full(len(prices), np.nan)

        for t in range(window, len(prices)):
            vol[t] = np.std(returns[t-window:t]) * np.sqrt(252)

        return vol

    def _compute_vol_ratio(
        self,
        prices: np.ndarray,
        **kwargs
    ) -> np.ndarray:
        """Short-term vol / long-term vol (regime indicator)."""
        short_vol = self._compute_volatility(prices, window=10, **kwargs)
        long_vol = self._compute_volatility(prices, window=60, **kwargs)

        ratio = short_vol / (long_vol + 1e-8)
        return ratio

    def _compute_roc(
        self,
        prices: np.ndarray,
        period: int = 10,
        **kwargs
    ) -> np.ndarray:
        """Rate of change (momentum)."""
        roc = np.full(len(prices), np.nan)
        roc[period:] = (prices[period:] / prices[:-period]) - 1
        return roc

    def _compute_zscore(
        self,
        prices: np.ndarray,
        window: int = 20,
        **kwargs
    ) -> np.ndarray:
        """Z-score of price relative to rolling window."""
        zscore = np.full(len(prices), np.nan)

        for t in range(window, len(prices)):
            window_prices = prices[t-window:t]
            mean = np.mean(window_prices)
            std = np.std(window_prices) + 1e-8
            zscore[t] = (prices[t] - mean) / std

        return zscore

    def _compute_trend_strength(
        self,
        prices: np.ndarray,
        **kwargs
    ) -> np.ndarray:
        """
        Trend strength indicator.

        Uses R-squared of linear regression on log prices.
        High R² = strong trend, Low R² = choppy/mean-reverting.
        """
        window = 20
        strength = np.full(len(prices), np.nan)

        log_prices = np.log(prices)

        for t in range(window, len(prices)):
            y = log_prices[t-window:t]
            x = np.arange(window)

            # Linear regression
            x_mean = x.mean()
            y_mean = y.mean()

            ss_xy = np.sum((x - x_mean) * (y - y_mean))
            ss_xx = np.sum((x - x_mean) ** 2)
            ss_yy = np.sum((y - y_mean) ** 2)

            if ss_xx > 0 and ss_yy > 0:
                r_squared = (ss_xy ** 2) / (ss_xx * ss_yy)
                # Sign indicates direction
                sign = 1 if ss_xy > 0 else -1
                strength[t] = sign * r_squared
            else:
                strength[t] = 0

        return strength

    def _compute_price_vs_ma(
        self,
        prices: np.ndarray,
        window: int = 20,
        **kwargs
    ) -> np.ndarray:
        """Price relative to moving average."""
        ma = np.full(len(prices), np.nan)
        for t in range(window, len(prices)):
            ma[t] = np.mean(prices[t-window:t])

        return (prices - ma) / (ma + 1e-8)


class OrderBookFeatures:
    """
    Features derived from order book data.

    Order book features are crucial for:
    - Understanding short-term price pressure
    - Detecting large orders (icebergs)
    - Identifying market maker behavior
    - Predicting intraday volatility
    """

    @staticmethod
    def compute_bid_ask_spread(bid: np.ndarray, ask: np.ndarray) -> np.ndarray:
        """Bid-ask spread as percentage of mid."""
        mid = (bid + ask) / 2
        return (ask - bid) / mid

    @staticmethod
    def compute_depth_imbalance(
        bid_size: np.ndarray,
        ask_size: np.ndarray
    ) -> np.ndarray:
        """
        Order book imbalance.

        Imbalance = (bid_size - ask_size) / (bid_size + ask_size)
        Positive = buying pressure, Negative = selling pressure
        """
        total = bid_size + ask_size + 1e-8
        return (bid_size - ask_size) / total

    @staticmethod
    def compute_volume_weighted_price(
        prices: np.ndarray,
        volumes: np.ndarray,
        window: int = 20
    ) -> np.ndarray:
        """VWAP deviation (institutional benchmark)."""
        vwap = np.full(len(prices), np.nan)

        for t in range(window, len(prices)):
            price_vol = prices[t-window:t] * volumes[t-window:t]
            vwap[t] = np.sum(price_vol) / (np.sum(volumes[t-window:t]) + 1e-8)

        return (prices - vwap) / (vwap + 1e-8)


class SentimentFeatures:
    """
    Features from sentiment data (news, social media).

    CAUTION: Sentiment data is:
    1. Noisy and often lagging
    2. Subject to manipulation
    3. Regime-dependent in effectiveness
    """

    @staticmethod
    def compute_sentiment_momentum(
        sentiment: np.ndarray,
        window: int = 5
    ) -> np.ndarray:
        """Change in sentiment (more predictive than level)."""
        momentum = np.full(len(sentiment), np.nan)
        momentum[window:] = sentiment[window:] - sentiment[:-window]
        return momentum

    @staticmethod
    def compute_sentiment_dispersion(
        positive: np.ndarray,
        negative: np.ndarray,
        neutral: np.ndarray
    ) -> np.ndarray:
        """
        Dispersion of sentiment.

        High dispersion = uncertainty, often precedes volatility.
        """
        total = positive + negative + neutral + 1e-8
        p_pos = positive / total
        p_neg = negative / total
        p_neu = neutral / total

        # Entropy as measure of dispersion
        entropy = -(
            p_pos * np.log(p_pos + 1e-8) +
            p_neg * np.log(p_neg + 1e-8) +
            p_neu * np.log(p_neu + 1e-8)
        )

        return entropy
