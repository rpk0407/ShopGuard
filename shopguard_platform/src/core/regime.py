"""
THE RECEPTORS - Market Regime Detection
========================================
Senses the market environment and adapts strategy accordingly.

Features:
- Market regime classification (trending, ranging, volatile)
- Volatility regime detection
- Correlation analysis
- Cycle detection
- Trend strength measurement
"""

import math
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_UP = "trending_up"       # Strong uptrend
    TRENDING_DOWN = "trending_down"   # Strong downtrend
    RANGING = "ranging"               # Sideways, mean-reverting
    VOLATILE = "volatile"             # High volatility, unclear direction
    BREAKOUT = "breakout"             # Transitioning from range
    ACCUMULATION = "accumulation"     # Low vol, preparing for move
    DISTRIBUTION = "distribution"     # High vol, preparing for drop


class VolatilityState(Enum):
    """Volatility regime"""
    VERY_LOW = "very_low"      # < 0.5x baseline
    LOW = "low"                # 0.5-0.8x baseline
    NORMAL = "normal"          # 0.8-1.2x baseline
    ELEVATED = "elevated"      # 1.2-2x baseline
    HIGH = "high"              # 2-3x baseline
    EXTREME = "extreme"        # > 3x baseline


class TrendStrength(Enum):
    """Trend strength classification"""
    NONE = "none"              # ADX < 20
    WEAK = "weak"              # ADX 20-30
    MODERATE = "moderate"      # ADX 30-40
    STRONG = "strong"          # ADX 40-50
    VERY_STRONG = "very_strong"  # ADX > 50


@dataclass
class RegimeState:
    """Current regime detection state"""
    # Primary regime
    regime: MarketRegime
    regime_confidence: float  # 0-1
    regime_duration: int  # Ticks in current regime

    # Volatility
    volatility_state: VolatilityState
    current_volatility: float
    baseline_volatility: float
    volatility_percentile: float

    # Trend
    trend_direction: int  # 1=up, -1=down, 0=none
    trend_strength: TrendStrength
    adx_value: float

    # Momentum
    momentum: float  # Positive=bullish, negative=bearish
    momentum_acceleration: float

    # Cycle
    cycle_phase: str  # "expansion", "peak", "contraction", "trough"
    cycle_position: float  # 0-1, position within cycle

    # Correlations
    btc_correlation: float
    market_correlation: float

    # Recommendations
    optimal_strategy: str
    position_size_multiplier: float


class RegimeDetector:
    """
    THE RECEPTORS
    =============
    Detects market regimes and adapts trading parameters.

    Uses multiple indicators:
    - ADX for trend strength
    - ATR for volatility
    - Hurst for mean reversion vs trending
    - Bollinger Band width for squeeze detection
    - RSI for momentum
    """

    def __init__(self, lookback: int = 100):
        self.lookback = lookback

        # Price history per asset
        self.price_history: Dict[str, deque] = {}
        self.returns_history: Dict[str, deque] = {}

        # Regime tracking
        self.current_regimes: Dict[str, MarketRegime] = {}
        self.regime_start_times: Dict[str, float] = {}
        self.regime_durations: Dict[str, int] = {}

        # Baseline volatility (learned over time)
        self.baseline_volatility: Dict[str, float] = {}
        self.volatility_history: Dict[str, deque] = {}

        # Correlation tracking
        self.btc_prices: deque = deque(maxlen=lookback)

        logger.info("👁️ Regime Detector (Receptors) initialized")

    def update(self, asset: str, price: float, btc_price: Optional[float] = None) -> RegimeState:
        """
        Update with new price and detect current regime.
        Returns full regime state.
        """
        # Initialize if needed
        if asset not in self.price_history:
            self.price_history[asset] = deque(maxlen=self.lookback)
            self.returns_history[asset] = deque(maxlen=self.lookback)
            self.volatility_history[asset] = deque(maxlen=500)
            self.baseline_volatility[asset] = 0.02  # Default 2%
            self.current_regimes[asset] = MarketRegime.RANGING
            self.regime_start_times[asset] = time.time()
            self.regime_durations[asset] = 0

        # Update price history
        if len(self.price_history[asset]) > 0:
            ret = (price - self.price_history[asset][-1]) / self.price_history[asset][-1]
            self.returns_history[asset].append(ret)

        self.price_history[asset].append(price)

        # Update BTC correlation tracking
        if btc_price:
            self.btc_prices.append(btc_price)

        # Need minimum history
        if len(self.price_history[asset]) < 20:
            return self._default_state(asset)

        # Calculate all indicators
        prices = np.array(self.price_history[asset])
        returns = np.array(self.returns_history[asset]) if len(self.returns_history[asset]) > 0 else np.array([0])

        # Volatility analysis
        current_vol = self._calculate_volatility(returns)
        self._update_baseline_volatility(asset, current_vol)
        vol_state = self._classify_volatility(asset, current_vol)

        # Trend analysis
        adx = self._calculate_adx(prices)
        trend_dir = self._calculate_trend_direction(prices)
        trend_strength = self._classify_trend_strength(adx)

        # Momentum
        momentum = self._calculate_momentum(prices)
        momentum_acc = self._calculate_momentum_acceleration(returns)

        # Regime classification
        regime = self._classify_regime(prices, returns, adx, current_vol, trend_dir)

        # Update regime tracking
        if regime != self.current_regimes.get(asset):
            self.current_regimes[asset] = regime
            self.regime_start_times[asset] = time.time()
            self.regime_durations[asset] = 0
        else:
            self.regime_durations[asset] += 1

        # Cycle detection
        cycle_phase, cycle_pos = self._detect_cycle(prices, returns)

        # Correlation
        btc_corr = self._calculate_btc_correlation(asset) if btc_price else 0

        # Regime confidence
        confidence = self._calculate_regime_confidence(adx, current_vol, self.baseline_volatility[asset])

        # Strategy recommendation
        strategy, size_mult = self._recommend_strategy(regime, vol_state, trend_strength)

        return RegimeState(
            regime=regime,
            regime_confidence=confidence,
            regime_duration=self.regime_durations[asset],
            volatility_state=vol_state,
            current_volatility=current_vol,
            baseline_volatility=self.baseline_volatility[asset],
            volatility_percentile=self._volatility_percentile(asset, current_vol),
            trend_direction=trend_dir,
            trend_strength=trend_strength,
            adx_value=adx,
            momentum=momentum,
            momentum_acceleration=momentum_acc,
            cycle_phase=cycle_phase,
            cycle_position=cycle_pos,
            btc_correlation=btc_corr,
            market_correlation=btc_corr,  # Simplified
            optimal_strategy=strategy,
            position_size_multiplier=size_mult
        )

    def _default_state(self, asset: str) -> RegimeState:
        """Return default state when insufficient data"""
        return RegimeState(
            regime=MarketRegime.RANGING,
            regime_confidence=0.0,
            regime_duration=0,
            volatility_state=VolatilityState.NORMAL,
            current_volatility=0.02,
            baseline_volatility=0.02,
            volatility_percentile=50.0,
            trend_direction=0,
            trend_strength=TrendStrength.NONE,
            adx_value=0,
            momentum=0,
            momentum_acceleration=0,
            cycle_phase="unknown",
            cycle_position=0.5,
            btc_correlation=0,
            market_correlation=0,
            optimal_strategy="wait",
            position_size_multiplier=0.5
        )

    def _calculate_volatility(self, returns: np.ndarray) -> float:
        """Calculate annualized volatility"""
        if len(returns) < 2:
            return 0.02

        std = np.std(returns)
        # Annualize (assuming ~252 trading days, 24/7 for crypto)
        return std * np.sqrt(365 * 24)  # Hourly data assumption

    def _update_baseline_volatility(self, asset: str, current_vol: float):
        """Update baseline volatility using EMA"""
        self.volatility_history[asset].append(current_vol)

        if len(self.volatility_history[asset]) > 50:
            # Use median of recent volatility as baseline
            recent = list(self.volatility_history[asset])[-100:]
            self.baseline_volatility[asset] = np.median(recent)

    def _classify_volatility(self, asset: str, current_vol: float) -> VolatilityState:
        """Classify current volatility relative to baseline"""
        baseline = self.baseline_volatility[asset]
        if baseline == 0:
            return VolatilityState.NORMAL

        ratio = current_vol / baseline

        if ratio < 0.5:
            return VolatilityState.VERY_LOW
        elif ratio < 0.8:
            return VolatilityState.LOW
        elif ratio < 1.2:
            return VolatilityState.NORMAL
        elif ratio < 2.0:
            return VolatilityState.ELEVATED
        elif ratio < 3.0:
            return VolatilityState.HIGH
        else:
            return VolatilityState.EXTREME

    def _volatility_percentile(self, asset: str, current_vol: float) -> float:
        """Calculate percentile of current volatility"""
        if len(self.volatility_history[asset]) < 10:
            return 50.0

        history = np.array(self.volatility_history[asset])
        return float(np.sum(history < current_vol) / len(history) * 100)

    def _calculate_adx(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate Average Directional Index"""
        if len(prices) < period + 1:
            return 0

        # Simplified ADX calculation
        highs = prices  # Using price as proxy for high
        lows = prices * 0.99  # Approximate low

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - prices[:-1]),
                np.abs(lows[1:] - prices[:-1])
            )
        )

        atr = np.mean(tr[-period:])
        if atr == 0:
            return 0

        # Directional movement
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        plus_di = 100 * np.mean(plus_dm[-period:]) / atr
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)

        return float(dx)

    def _classify_trend_strength(self, adx: float) -> TrendStrength:
        """Classify trend strength from ADX"""
        if adx < 20:
            return TrendStrength.NONE
        elif adx < 30:
            return TrendStrength.WEAK
        elif adx < 40:
            return TrendStrength.MODERATE
        elif adx < 50:
            return TrendStrength.STRONG
        else:
            return TrendStrength.VERY_STRONG

    def _calculate_trend_direction(self, prices: np.ndarray) -> int:
        """Determine trend direction using moving averages"""
        if len(prices) < 20:
            return 0

        short_ma = np.mean(prices[-10:])
        long_ma = np.mean(prices[-20:])

        if short_ma > long_ma * 1.005:
            return 1  # Uptrend
        elif short_ma < long_ma * 0.995:
            return -1  # Downtrend
        else:
            return 0  # No clear trend

    def _calculate_momentum(self, prices: np.ndarray) -> float:
        """Calculate price momentum"""
        if len(prices) < 10:
            return 0

        return (prices[-1] - prices[-10]) / prices[-10]

    def _calculate_momentum_acceleration(self, returns: np.ndarray) -> float:
        """Calculate momentum acceleration (change in momentum)"""
        if len(returns) < 10:
            return 0

        recent_momentum = np.mean(returns[-5:])
        older_momentum = np.mean(returns[-10:-5])

        return recent_momentum - older_momentum

    def _classify_regime(
        self,
        prices: np.ndarray,
        returns: np.ndarray,
        adx: float,
        volatility: float,
        trend_dir: int
    ) -> MarketRegime:
        """Classify the current market regime"""
        baseline_vol = np.median(list(self.volatility_history.get('BTC/USDT', [0.02])) or [0.02])
        vol_ratio = volatility / max(baseline_vol, 0.01)

        # High volatility regime
        if vol_ratio > 2.5:
            return MarketRegime.VOLATILE

        # Strong trend
        if adx > 30:
            if trend_dir > 0:
                return MarketRegime.TRENDING_UP
            elif trend_dir < 0:
                return MarketRegime.TRENDING_DOWN

        # Low volatility (accumulation/distribution)
        if vol_ratio < 0.6:
            momentum = self._calculate_momentum(prices)
            if momentum > 0.01:
                return MarketRegime.ACCUMULATION
            elif momentum < -0.01:
                return MarketRegime.DISTRIBUTION
            else:
                return MarketRegime.RANGING

        # Breakout detection
        if len(prices) > 20:
            recent_range = np.max(prices[-5:]) - np.min(prices[-5:])
            longer_range = np.max(prices[-20:]) - np.min(prices[-20:])

            if recent_range > longer_range * 0.7:  # Range expansion
                return MarketRegime.BREAKOUT

        # Default to ranging
        return MarketRegime.RANGING

    def _detect_cycle(self, prices: np.ndarray, returns: np.ndarray) -> Tuple[str, float]:
        """Detect market cycle phase"""
        if len(prices) < 30:
            return "unknown", 0.5

        # Simple cycle detection using momentum and rate of change
        momentum = self._calculate_momentum(prices)
        acceleration = self._calculate_momentum_acceleration(returns)

        if momentum > 0 and acceleration > 0:
            phase = "expansion"
            position = 0.25
        elif momentum > 0 and acceleration <= 0:
            phase = "peak"
            position = 0.5
        elif momentum <= 0 and acceleration < 0:
            phase = "contraction"
            position = 0.75
        else:
            phase = "trough"
            position = 0.0

        return phase, position

    def _calculate_btc_correlation(self, asset: str) -> float:
        """Calculate correlation with BTC"""
        if asset == "BTC/USDT" or len(self.btc_prices) < 20:
            return 1.0

        if asset not in self.price_history or len(self.price_history[asset]) < 20:
            return 0

        asset_returns = np.diff(np.array(self.price_history[asset])[-20:])
        btc_returns = np.diff(np.array(self.btc_prices)[-20:])

        if len(asset_returns) != len(btc_returns):
            min_len = min(len(asset_returns), len(btc_returns))
            asset_returns = asset_returns[-min_len:]
            btc_returns = btc_returns[-min_len:]

        if len(asset_returns) < 5:
            return 0

        correlation = np.corrcoef(asset_returns, btc_returns)[0, 1]
        return float(correlation) if not np.isnan(correlation) else 0

    def _calculate_regime_confidence(
        self,
        adx: float,
        current_vol: float,
        baseline_vol: float
    ) -> float:
        """Calculate confidence in current regime classification"""
        # Higher ADX = more confident in trend regime
        adx_confidence = min(adx / 50, 1.0)

        # Stable volatility = more confident
        vol_ratio = current_vol / max(baseline_vol, 0.01)
        vol_stability = 1 - min(abs(vol_ratio - 1) / 2, 0.5)

        return (adx_confidence + vol_stability) / 2

    def _recommend_strategy(
        self,
        regime: MarketRegime,
        vol_state: VolatilityState,
        trend_strength: TrendStrength
    ) -> Tuple[str, float]:
        """Recommend strategy and position size multiplier"""
        strategies = {
            MarketRegime.TRENDING_UP: ("trend_following", 1.2),
            MarketRegime.TRENDING_DOWN: ("trend_following_short", 1.0),
            MarketRegime.RANGING: ("mean_reversion", 0.8),
            MarketRegime.VOLATILE: ("reduce_exposure", 0.3),
            MarketRegime.BREAKOUT: ("breakout", 1.0),
            MarketRegime.ACCUMULATION: ("scale_in", 1.5),
            MarketRegime.DISTRIBUTION: ("scale_out", 0.5),
        }

        strategy, base_mult = strategies.get(regime, ("wait", 0.5))

        # Adjust for volatility
        vol_adjustments = {
            VolatilityState.VERY_LOW: 0.7,
            VolatilityState.LOW: 0.9,
            VolatilityState.NORMAL: 1.0,
            VolatilityState.ELEVATED: 0.8,
            VolatilityState.HIGH: 0.5,
            VolatilityState.EXTREME: 0.2,
        }

        vol_mult = vol_adjustments.get(vol_state, 1.0)

        return strategy, base_mult * vol_mult

    def get_regime(self, asset: str) -> MarketRegime:
        """Get current regime for asset"""
        return self.current_regimes.get(asset, MarketRegime.RANGING)

    def get_stats(self) -> Dict:
        """Get regime detection statistics"""
        return {
            'tracked_assets': list(self.current_regimes.keys()),
            'current_regimes': {k: v.value for k, v in self.current_regimes.items()},
            'regime_durations': dict(self.regime_durations),
            'baseline_volatilities': dict(self.baseline_volatility)
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test regime detector
    detector = RegimeDetector()

    # Simulate price data
    np.random.seed(42)
    price = 100.0

    print("Simulating market phases...")

    # Trending phase
    for i in range(50):
        price *= 1 + np.random.normal(0.002, 0.01)  # Uptrend
        state = detector.update("BTC/USDT", price)

    print(f"\nAfter uptrend:")
    print(f"  Regime: {state.regime.value}")
    print(f"  Trend: {state.trend_strength.value} (ADX: {state.adx_value:.1f})")
    print(f"  Volatility: {state.volatility_state.value}")

    # Volatile phase
    for i in range(30):
        price *= 1 + np.random.normal(0, 0.03)  # High vol
        state = detector.update("BTC/USDT", price)

    print(f"\nAfter volatile phase:")
    print(f"  Regime: {state.regime.value}")
    print(f"  Volatility: {state.volatility_state.value}")
    print(f"  Recommendation: {state.optimal_strategy} (size mult: {state.position_size_multiplier:.2f})")

    print(f"\nStats: {detector.get_stats()}")
