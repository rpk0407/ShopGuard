"""
Market Intelligence Agent

Deep market understanding through:
- Multi-timeframe analysis
- Order flow analysis
- Liquidity detection
- Trend identification
- Support/resistance levels
- Market regime detection
- Correlation analysis
- Smart money tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
import numpy as np
from collections import deque

from .base import (
    BaseAgent, Signal, SignalStrength, MarketSnapshot,
    MarketCondition, Memory, AgentState, generate_unique_id, normalize_confidence
)


class TrendDirection(Enum):
    STRONG_UP = auto()
    UP = auto()
    SIDEWAYS = auto()
    DOWN = auto()
    STRONG_DOWN = auto()


class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_BULLISH = auto()
    TRENDING_BEARISH = auto()
    RANGING_TIGHT = auto()
    RANGING_WIDE = auto()
    VOLATILE_UP = auto()
    VOLATILE_DOWN = auto()
    BREAKOUT = auto()
    BREAKDOWN = auto()
    ACCUMULATION = auto()  # Smart money buying
    DISTRIBUTION = auto()  # Smart money selling


@dataclass
class PriceLevel:
    """Support/Resistance level"""
    price: float
    strength: float  # 0-1, how many times tested
    level_type: str  # 'support' or 'resistance'
    touches: int
    last_touch: datetime
    broken: bool = False


@dataclass
class OrderFlowData:
    """Order flow analysis data"""
    buy_volume: float
    sell_volume: float
    delta: float  # buy - sell
    cumulative_delta: float
    large_orders_buy: int
    large_orders_sell: int
    imbalance_ratio: float


@dataclass
class MarketStructure:
    """Complete market structure analysis"""
    symbol: str
    timestamp: datetime
    trend: TrendDirection
    regime: MarketRegime
    support_levels: List[PriceLevel]
    resistance_levels: List[PriceLevel]
    current_range: Tuple[float, float]
    volatility_percentile: float  # Where current vol is vs history
    momentum_score: float  # -1 to 1
    order_flow: OrderFlowData
    smart_money_direction: str  # 'buying', 'selling', 'neutral'
    liquidity_zones: List[Tuple[float, float]]  # Price ranges with high liquidity


class MarketIntelligenceAgent(BaseAgent):
    """
    Deep market analysis agent that understands market microstructure,
    identifies trends, detects smart money moves, and provides
    institutional-grade market intelligence.
    """

    def __init__(self):
        super().__init__(
            agent_id=generate_unique_id('market_intel'),
            name="Market Intelligence",
            description="Deep market analysis and structure identification"
        )

        # Price history per symbol
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.tick_data: Dict[str, deque] = {}

        # Analysis cache
        self.market_structures: Dict[str, MarketStructure] = {}
        self.regime_history: Dict[str, List[MarketRegime]] = {}

        # Configuration
        self.lookback_periods = [5, 10, 20, 50, 100, 200]
        self.volatility_window = 20
        self.level_threshold = 0.02  # 2% for S/R level detection

        # Pattern detection
        self.detected_patterns: Dict[str, List[Dict]] = {}

    def analyze(self, snapshot: MarketSnapshot) -> Optional[Signal]:
        """
        Perform comprehensive market analysis.
        Returns signal only when high-conviction opportunity detected.
        """
        self.state = AgentState.ANALYZING
        self.last_active = datetime.now()

        signals = []

        for symbol, price in snapshot.prices.items():
            # Update history
            self._update_history(symbol, price, snapshot.volumes.get(symbol, 0))

            # Perform multi-layer analysis
            structure = self._analyze_structure(symbol, snapshot)
            if structure:
                self.market_structures[symbol] = structure

                # Generate signal based on analysis
                signal = self._generate_signal(symbol, structure, snapshot)
                if signal:
                    signals.append(signal)

        self.state = AgentState.IDLE

        # Return highest confidence signal
        if signals:
            signals.sort(key=lambda s: s.score, reverse=True)
            return signals[0]

        return None

    def _update_history(self, symbol: str, price: float, volume: float):
        """Update price and volume history"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=500)
            self.volume_history[symbol] = deque(maxlen=500)

        self.price_history[symbol].append({
            'price': price,
            'timestamp': datetime.now()
        })
        self.volume_history[symbol].append(volume)

    def _analyze_structure(self, symbol: str, snapshot: MarketSnapshot) -> Optional[MarketStructure]:
        """Analyze complete market structure for a symbol"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 50:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]
        volumes = list(self.volume_history[symbol])

        # Multi-timeframe trend analysis
        trend = self._analyze_trend(prices)

        # Detect regime
        regime = self._detect_regime(prices, volumes)

        # Find support/resistance
        support_levels = self._find_support_levels(prices)
        resistance_levels = self._find_resistance_levels(prices)

        # Calculate volatility percentile
        vol_percentile = self._volatility_percentile(prices)

        # Momentum analysis
        momentum = self._calculate_momentum(prices)

        # Order flow analysis
        order_flow = self._analyze_order_flow(symbol, snapshot)

        # Smart money detection
        smart_money = self._detect_smart_money(prices, volumes, order_flow)

        # Liquidity zones
        liquidity_zones = self._find_liquidity_zones(prices, volumes)

        return MarketStructure(
            symbol=symbol,
            timestamp=datetime.now(),
            trend=trend,
            regime=regime,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            current_range=(min(prices[-20:]), max(prices[-20:])),
            volatility_percentile=vol_percentile,
            momentum_score=momentum,
            order_flow=order_flow,
            smart_money_direction=smart_money,
            liquidity_zones=liquidity_zones
        )

    def _analyze_trend(self, prices: List[float]) -> TrendDirection:
        """Multi-timeframe trend analysis"""
        if len(prices) < 50:
            return TrendDirection.SIDEWAYS

        # Calculate EMAs for multiple timeframes
        ema_fast = self._ema(prices, 10)
        ema_medium = self._ema(prices, 25)
        ema_slow = self._ema(prices, 50)

        current = prices[-1]

        # Score based on price position relative to EMAs
        score = 0
        if current > ema_fast:
            score += 1
        if current > ema_medium:
            score += 1
        if current > ema_slow:
            score += 1
        if ema_fast > ema_medium:
            score += 1
        if ema_medium > ema_slow:
            score += 1

        # Calculate price change momentum
        change_20 = (prices[-1] - prices[-20]) / prices[-20] if len(prices) >= 20 else 0

        if score >= 4 and change_20 > 0.05:
            return TrendDirection.STRONG_UP
        elif score >= 3:
            return TrendDirection.UP
        elif score <= 1 and change_20 < -0.05:
            return TrendDirection.STRONG_DOWN
        elif score <= 2:
            return TrendDirection.DOWN
        else:
            return TrendDirection.SIDEWAYS

    def _detect_regime(self, prices: List[float], volumes: List[float]) -> MarketRegime:
        """Detect current market regime"""
        if len(prices) < 50:
            return MarketRegime.RANGING_TIGHT

        # Calculate volatility
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * np.sqrt(252)

        # Calculate average true range
        high_low_range = max(prices[-20:]) - min(prices[-20:])
        avg_price = np.mean(prices[-20:])
        range_pct = high_low_range / avg_price

        # Trend strength
        trend = self._analyze_trend(prices)

        # Volume analysis
        avg_vol = np.mean(volumes[-50:]) if volumes else 1
        recent_vol = np.mean(volumes[-10:]) if volumes else 1
        vol_expansion = recent_vol / avg_vol if avg_vol > 0 else 1

        # Determine regime
        if volatility > 0.4:  # High volatility
            if trend in [TrendDirection.UP, TrendDirection.STRONG_UP]:
                return MarketRegime.VOLATILE_UP
            else:
                return MarketRegime.VOLATILE_DOWN

        if range_pct < 0.03:  # Tight range
            if vol_expansion > 1.5:
                # Volume expanding in tight range = accumulation/distribution
                if trend in [TrendDirection.UP, TrendDirection.STRONG_UP]:
                    return MarketRegime.ACCUMULATION
                else:
                    return MarketRegime.DISTRIBUTION
            return MarketRegime.RANGING_TIGHT

        if range_pct > 0.08:  # Wide range
            if trend == TrendDirection.STRONG_UP:
                return MarketRegime.BREAKOUT
            elif trend == TrendDirection.STRONG_DOWN:
                return MarketRegime.BREAKDOWN
            return MarketRegime.RANGING_WIDE

        # Normal trending
        if trend in [TrendDirection.UP, TrendDirection.STRONG_UP]:
            return MarketRegime.TRENDING_BULLISH
        elif trend in [TrendDirection.DOWN, TrendDirection.STRONG_DOWN]:
            return MarketRegime.TRENDING_BEARISH

        return MarketRegime.RANGING_TIGHT

    def _find_support_levels(self, prices: List[float]) -> List[PriceLevel]:
        """Find key support levels"""
        levels = []
        if len(prices) < 30:
            return levels

        # Find local minima
        for i in range(5, len(prices) - 5):
            if prices[i] == min(prices[i-5:i+6]):
                # Check if this level was tested multiple times
                touches = sum(1 for p in prices if abs(p - prices[i]) / prices[i] < 0.01)
                if touches >= 2:
                    levels.append(PriceLevel(
                        price=prices[i],
                        strength=min(1.0, touches / 5),
                        level_type='support',
                        touches=touches,
                        last_touch=datetime.now(),
                        broken=prices[-1] < prices[i]
                    ))

        # Sort by strength and return top 5
        levels.sort(key=lambda x: x.strength, reverse=True)
        return levels[:5]

    def _find_resistance_levels(self, prices: List[float]) -> List[PriceLevel]:
        """Find key resistance levels"""
        levels = []
        if len(prices) < 30:
            return levels

        # Find local maxima
        for i in range(5, len(prices) - 5):
            if prices[i] == max(prices[i-5:i+6]):
                touches = sum(1 for p in prices if abs(p - prices[i]) / prices[i] < 0.01)
                if touches >= 2:
                    levels.append(PriceLevel(
                        price=prices[i],
                        strength=min(1.0, touches / 5),
                        level_type='resistance',
                        touches=touches,
                        last_touch=datetime.now(),
                        broken=prices[-1] > prices[i]
                    ))

        levels.sort(key=lambda x: x.strength, reverse=True)
        return levels[:5]

    def _volatility_percentile(self, prices: List[float]) -> float:
        """Calculate where current volatility sits in historical distribution"""
        if len(prices) < 100:
            return 0.5

        returns = np.diff(prices) / prices[:-1]

        # Rolling volatility
        vol_history = []
        for i in range(20, len(returns)):
            vol = np.std(returns[i-20:i])
            vol_history.append(vol)

        if not vol_history:
            return 0.5

        current_vol = vol_history[-1]
        percentile = sum(1 for v in vol_history if v < current_vol) / len(vol_history)
        return percentile

    def _calculate_momentum(self, prices: List[float]) -> float:
        """Calculate momentum score (-1 to 1)"""
        if len(prices) < 20:
            return 0

        # Rate of change at different timeframes
        roc_5 = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
        roc_10 = (prices[-1] - prices[-10]) / prices[-10] if len(prices) >= 10 else 0
        roc_20 = (prices[-1] - prices[-20]) / prices[-20] if len(prices) >= 20 else 0

        # Weighted average
        momentum = roc_5 * 0.5 + roc_10 * 0.3 + roc_20 * 0.2

        # Normalize to -1 to 1
        return max(-1, min(1, momentum * 10))

    def _analyze_order_flow(self, symbol: str, snapshot: MarketSnapshot) -> OrderFlowData:
        """Analyze order flow for buy/sell pressure"""
        # Use order book imbalance and recent trades
        imbalance = snapshot.order_book_imbalance.get(symbol, 0)
        trades = snapshot.recent_trades.get(symbol, [])

        buy_volume = sum(t.get('volume', 0) for t in trades if t.get('side') == 'buy')
        sell_volume = sum(t.get('volume', 0) for t in trades if t.get('side') == 'sell')

        delta = buy_volume - sell_volume
        total_volume = buy_volume + sell_volume

        # Count large orders (institutional)
        large_threshold = np.mean([t.get('volume', 0) for t in trades]) * 3 if trades else 1000
        large_buys = sum(1 for t in trades if t.get('side') == 'buy' and t.get('volume', 0) > large_threshold)
        large_sells = sum(1 for t in trades if t.get('side') == 'sell' and t.get('volume', 0) > large_threshold)

        return OrderFlowData(
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            delta=delta,
            cumulative_delta=delta,  # Would accumulate over time in real implementation
            large_orders_buy=large_buys,
            large_orders_sell=large_sells,
            imbalance_ratio=imbalance
        )

    def _detect_smart_money(self, prices: List[float], volumes: List[float],
                            order_flow: OrderFlowData) -> str:
        """Detect smart money (institutional) activity"""
        if len(prices) < 20 or len(volumes) < 20:
            return 'neutral'

        # Signs of smart money buying:
        # 1. Large orders on buy side
        # 2. Price holding support with volume
        # 3. Absorption of selling (delta positive despite price not moving up)

        large_order_bias = order_flow.large_orders_buy - order_flow.large_orders_sell

        # Volume at lows vs highs
        price_median = np.median(prices[-20:])
        vol_at_lows = sum(v for p, v in zip(prices[-20:], volumes[-20:]) if p < price_median)
        vol_at_highs = sum(v for p, v in zip(prices[-20:], volumes[-20:]) if p >= price_median)

        if large_order_bias > 2 and vol_at_lows > vol_at_highs * 1.2:
            return 'buying'
        elif large_order_bias < -2 and vol_at_highs > vol_at_lows * 1.2:
            return 'selling'

        return 'neutral'

    def _find_liquidity_zones(self, prices: List[float], volumes: List[float]) -> List[Tuple[float, float]]:
        """Find price zones with high liquidity (high volume nodes)"""
        if len(prices) < 50 or len(volumes) < 50:
            return []

        # Create volume profile
        price_min, price_max = min(prices), max(prices)
        n_bins = 20
        bin_size = (price_max - price_min) / n_bins

        volume_profile = [0] * n_bins
        for p, v in zip(prices, volumes):
            bin_idx = min(int((p - price_min) / bin_size), n_bins - 1)
            volume_profile[bin_idx] += v

        # Find high volume zones (top 3)
        avg_vol = np.mean(volume_profile)
        zones = []
        for i, vol in enumerate(volume_profile):
            if vol > avg_vol * 1.5:
                zone_low = price_min + i * bin_size
                zone_high = zone_low + bin_size
                zones.append((zone_low, zone_high))

        return zones[:3]

    def _generate_signal(self, symbol: str, structure: MarketStructure,
                         snapshot: MarketSnapshot) -> Optional[Signal]:
        """Generate trading signal based on market structure"""
        current_price = snapshot.prices.get(symbol, 0)
        if current_price == 0:
            return None

        signal_direction = None
        confidence = 0.0
        reasoning_parts = []

        # Trend alignment check
        trend_bullish = structure.trend in [TrendDirection.UP, TrendDirection.STRONG_UP]
        trend_bearish = structure.trend in [TrendDirection.DOWN, TrendDirection.STRONG_DOWN]

        # Regime-based signals
        if structure.regime == MarketRegime.ACCUMULATION:
            signal_direction = 'long'
            confidence += 0.3
            reasoning_parts.append("Accumulation detected (smart money buying)")

        elif structure.regime == MarketRegime.DISTRIBUTION:
            signal_direction = 'short'
            confidence += 0.3
            reasoning_parts.append("Distribution detected (smart money selling)")

        elif structure.regime == MarketRegime.BREAKOUT and trend_bullish:
            signal_direction = 'long'
            confidence += 0.25
            reasoning_parts.append("Breakout with bullish trend")

        elif structure.regime == MarketRegime.BREAKDOWN and trend_bearish:
            signal_direction = 'short'
            confidence += 0.25
            reasoning_parts.append("Breakdown with bearish trend")

        # Smart money confirmation
        if structure.smart_money_direction == 'buying' and signal_direction == 'long':
            confidence += 0.2
            reasoning_parts.append("Smart money buying confirmed")
        elif structure.smart_money_direction == 'selling' and signal_direction == 'short':
            confidence += 0.2
            reasoning_parts.append("Smart money selling confirmed")

        # Support/resistance proximity
        for level in structure.support_levels:
            if abs(current_price - level.price) / current_price < 0.01:
                if trend_bullish:
                    signal_direction = 'long'
                    confidence += 0.15 * level.strength
                    reasoning_parts.append(f"At strong support ${level.price:.2f}")
                break

        for level in structure.resistance_levels:
            if abs(current_price - level.price) / current_price < 0.01:
                if trend_bearish:
                    signal_direction = 'short'
                    confidence += 0.15 * level.strength
                    reasoning_parts.append(f"At strong resistance ${level.price:.2f}")
                break

        # Momentum confirmation
        if structure.momentum_score > 0.5 and signal_direction == 'long':
            confidence += 0.1
            reasoning_parts.append("Strong bullish momentum")
        elif structure.momentum_score < -0.5 and signal_direction == 'short':
            confidence += 0.1
            reasoning_parts.append("Strong bearish momentum")

        # Order flow confirmation
        if structure.order_flow.delta > 0 and signal_direction == 'long':
            confidence += 0.1
            reasoning_parts.append("Positive order flow delta")
        elif structure.order_flow.delta < 0 and signal_direction == 'short':
            confidence += 0.1
            reasoning_parts.append("Negative order flow delta")

        # Only generate signal if confidence is sufficient
        if signal_direction and confidence >= 0.4:
            strength = SignalStrength.MODERATE
            if confidence >= 0.7:
                strength = SignalStrength.VERY_STRONG
            elif confidence >= 0.55:
                strength = SignalStrength.STRONG
            elif confidence < 0.45:
                strength = SignalStrength.WEAK

            self.signals_generated += 1

            return Signal(
                agent_id=self.agent_id,
                symbol=symbol,
                direction=signal_direction,
                strength=strength,
                confidence=normalize_confidence(confidence),
                reasoning=" | ".join(reasoning_parts),
                timestamp=datetime.now(),
                expiry=datetime.now() + timedelta(minutes=15),
                metadata={
                    'regime': structure.regime.name,
                    'trend': structure.trend.name,
                    'smart_money': structure.smart_money_direction,
                    'momentum': structure.momentum_score
                }
            )

        return None

    def _ema(self, data: List[float], period: int) -> float:
        """Calculate EMA"""
        if len(data) < period:
            return data[-1] if data else 0

        multiplier = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema

    def learn(self, feedback: Dict[str, Any]):
        """Learn from trade outcomes"""
        outcome = feedback.get('outcome', 0)
        signal_data = feedback.get('signal', {})

        if outcome > 0:
            self.correct_signals += 1
            self.memory.remember({
                'type': 'successful_signal',
                'regime': signal_data.get('regime'),
                'trend': signal_data.get('trend'),
                'smart_money': signal_data.get('smart_money')
            }, importance=0.8)
        else:
            self.memory.remember({
                'type': 'failed_signal',
                'regime': signal_data.get('regime'),
                'trend': signal_data.get('trend'),
                'smart_money': signal_data.get('smart_money')
            }, importance=0.7)

    def get_market_summary(self, symbol: str) -> Optional[Dict]:
        """Get human-readable market summary"""
        structure = self.market_structures.get(symbol)
        if not structure:
            return None

        return {
            'symbol': symbol,
            'trend': structure.trend.name,
            'regime': structure.regime.name,
            'momentum': round(structure.momentum_score, 2),
            'volatility_percentile': round(structure.volatility_percentile * 100, 1),
            'smart_money': structure.smart_money_direction,
            'key_support': [l.price for l in structure.support_levels[:3]],
            'key_resistance': [l.price for l in structure.resistance_levels[:3]],
            'liquidity_zones': structure.liquidity_zones
        }
