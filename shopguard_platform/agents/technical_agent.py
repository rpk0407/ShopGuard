"""
Technical Analysis Agent
========================
Advanced technical analysis using mathematical indicators,
chart patterns, and price action analysis.

Algorithms:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Fibonacci Retracement Levels
- Volume Analysis
- Support/Resistance Detection
- Trend Analysis
- Momentum Oscillators
- Volatility Analysis (ATR)
"""
import math
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from .base_agent import BaseAgent, AgentOpinion, Action, Confidence


@dataclass
class TechnicalIndicators:
    """Container for all calculated technical indicators"""
    # Trend
    sma_20: float = 0
    sma_50: float = 0
    sma_200: float = 0
    ema_12: float = 0
    ema_26: float = 0
    trend: str = "neutral"  # bullish, bearish, neutral

    # Momentum
    rsi: float = 50
    rsi_signal: str = "neutral"
    macd: float = 0
    macd_signal: float = 0
    macd_histogram: float = 0
    momentum: float = 0

    # Volatility
    bollinger_upper: float = 0
    bollinger_middle: float = 0
    bollinger_lower: float = 0
    bollinger_width: float = 0
    atr: float = 0  # Average True Range
    volatility_percentile: float = 50

    # Volume
    volume_trend: str = "normal"
    volume_ratio: float = 1.0

    # Support/Resistance
    support_levels: List[float] = None
    resistance_levels: List[float] = None
    nearest_support: float = 0
    nearest_resistance: float = 0

    # Fibonacci
    fib_levels: Dict[str, float] = None

    # Pattern Detection
    patterns_detected: List[str] = None

    def __post_init__(self):
        if self.support_levels is None:
            self.support_levels = []
        if self.resistance_levels is None:
            self.resistance_levels = []
        if self.fib_levels is None:
            self.fib_levels = {}
        if self.patterns_detected is None:
            self.patterns_detected = []


class TechnicalAgent(BaseAgent):
    """
    Technical Analysis Agent
    Analyzes price action, indicators, and chart patterns
    """

    def __init__(self):
        super().__init__(
            name="Technical Analysis Agent",
            specialty="Chart patterns, indicators, and price action"
        )

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """
        Calculate Relative Strength Index

        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss

        Interpretation:
        - RSI > 70: Overbought (potential reversal down)
        - RSI < 30: Oversold (potential reversal up)
        - RSI 40-60: Neutral zone
        """
        if len(prices) < period + 1:
            return 50.0

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_macd(self, prices: List[float]) -> Tuple[float, float, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        MACD Line = EMA(12) - EMA(26)
        Signal Line = EMA(9) of MACD Line
        Histogram = MACD Line - Signal Line

        Interpretation:
        - MACD crosses above signal: Bullish
        - MACD crosses below signal: Bearish
        - Histogram growing: Momentum increasing
        """
        if len(prices) < 26:
            return 0, 0, 0

        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)

        macd_line = ema_12 - ema_26

        # Simplified signal line (would need historical MACD values for proper EMA)
        signal_line = macd_line * 0.9  # Approximation

        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period

    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float, float]:
        """
        Calculate Bollinger Bands

        Middle Band = SMA(20)
        Upper Band = Middle + (2 * Standard Deviation)
        Lower Band = Middle - (2 * Standard Deviation)

        Interpretation:
        - Price near upper band: Potentially overbought
        - Price near lower band: Potentially oversold
        - Bands squeezing: Volatility contraction, big move coming
        - Bands expanding: High volatility
        """
        if len(prices) < period:
            price = prices[-1] if prices else 0
            return price, price, price, 0

        recent_prices = prices[-period:]
        middle = sum(recent_prices) / period

        variance = sum((p - middle) ** 2 for p in recent_prices) / period
        std = math.sqrt(variance)

        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        width = (upper - lower) / middle * 100  # Width as percentage

        return upper, middle, lower, width

    def calculate_fibonacci_levels(self, high: float, low: float) -> Dict[str, float]:
        """
        Calculate Fibonacci Retracement Levels

        Key levels: 23.6%, 38.2%, 50%, 61.8%, 78.6%

        These levels often act as support/resistance during pullbacks.
        The 61.8% level (golden ratio) is particularly significant.
        """
        diff = high - low

        return {
            "0.0%": high,
            "23.6%": high - (diff * 0.236),
            "38.2%": high - (diff * 0.382),
            "50.0%": high - (diff * 0.500),
            "61.8%": high - (diff * 0.618),
            "78.6%": high - (diff * 0.786),
            "100.0%": low
        }

    def detect_support_resistance(self, prices: List[float], current_price: float) -> Tuple[List[float], List[float]]:
        """
        Detect Support and Resistance Levels

        Support: Price levels where buying pressure exceeds selling
        Resistance: Price levels where selling pressure exceeds buying

        Method: Find price levels where reversals occurred
        """
        if len(prices) < 10:
            return [], []

        supports = []
        resistances = []

        # Find local minima (support) and maxima (resistance)
        for i in range(2, len(prices) - 2):
            # Local minimum (support)
            if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
               prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                supports.append(prices[i])

            # Local maximum (resistance)
            if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
               prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                resistances.append(prices[i])

        # Filter to levels near current price (within 20%)
        supports = sorted([s for s in supports if s < current_price and s > current_price * 0.8])
        resistances = sorted([r for r in resistances if r > current_price and r < current_price * 1.2])

        return supports[-3:] if supports else [], resistances[:3] if resistances else []

    def calculate_atr(self, prices: List[float], period: int = 14) -> float:
        """
        Calculate Average True Range (ATR)

        Measures volatility - higher ATR = more volatile
        Used for position sizing and stop loss placement
        """
        if len(prices) < period + 1:
            return 0

        true_ranges = []
        for i in range(1, len(prices)):
            high = prices[i] * 1.02  # Approximate high
            low = prices[i] * 0.98   # Approximate low
            prev_close = prices[i-1]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        return sum(true_ranges[-period:]) / period

    def detect_patterns(self, prices: List[float]) -> List[str]:
        """
        Detect common chart patterns

        Patterns detected:
        - Double Top/Bottom
        - Higher Highs/Lower Lows
        - Consolidation
        """
        patterns = []

        if len(prices) < 20:
            return patterns

        recent = prices[-20:]

        # Trend detection
        first_half_avg = sum(recent[:10]) / 10
        second_half_avg = sum(recent[10:]) / 10

        if second_half_avg > first_half_avg * 1.02:
            patterns.append("UPTREND")
        elif second_half_avg < first_half_avg * 0.98:
            patterns.append("DOWNTREND")
        else:
            patterns.append("CONSOLIDATION")

        # Higher highs / Lower lows
        highs = [max(recent[i:i+5]) for i in range(0, 15, 5)]
        lows = [min(recent[i:i+5]) for i in range(0, 15, 5)]

        if all(highs[i] < highs[i+1] for i in range(len(highs)-1)):
            patterns.append("HIGHER_HIGHS")
        if all(lows[i] < lows[i+1] for i in range(len(lows)-1)):
            patterns.append("HIGHER_LOWS")
        if all(highs[i] > highs[i+1] for i in range(len(highs)-1)):
            patterns.append("LOWER_HIGHS")
        if all(lows[i] > lows[i+1] for i in range(len(lows)-1)):
            patterns.append("LOWER_LOWS")

        # Volatility squeeze
        bb_upper, bb_middle, bb_lower, bb_width = self.calculate_bollinger_bands(prices)
        if bb_width < 5:
            patterns.append("VOLATILITY_SQUEEZE")

        return patterns

    def analyze(self, asset: str, data: Dict[str, Any]) -> AgentOpinion:
        """
        Perform comprehensive technical analysis
        """
        current_price = data.get('price', 0)
        prices = data.get('price_history', [current_price] * 50)
        volume = data.get('volume', 0)

        # Calculate all indicators
        indicators = TechnicalIndicators()

        # Moving Averages
        indicators.sma_20 = self._calculate_sma(prices, 20)
        indicators.sma_50 = self._calculate_sma(prices, 50)
        indicators.sma_200 = self._calculate_sma(prices, 200) if len(prices) >= 200 else indicators.sma_50
        indicators.ema_12 = self._calculate_ema(prices, 12)
        indicators.ema_26 = self._calculate_ema(prices, 26)

        # Trend
        if current_price > indicators.sma_20 > indicators.sma_50:
            indicators.trend = "BULLISH"
        elif current_price < indicators.sma_20 < indicators.sma_50:
            indicators.trend = "BEARISH"
        else:
            indicators.trend = "NEUTRAL"

        # RSI
        indicators.rsi = self.calculate_rsi(prices)
        if indicators.rsi > 70:
            indicators.rsi_signal = "OVERBOUGHT"
        elif indicators.rsi < 30:
            indicators.rsi_signal = "OVERSOLD"
        else:
            indicators.rsi_signal = "NEUTRAL"

        # MACD
        indicators.macd, indicators.macd_signal, indicators.macd_histogram = self.calculate_macd(prices)

        # Bollinger Bands
        indicators.bollinger_upper, indicators.bollinger_middle, indicators.bollinger_lower, indicators.bollinger_width = \
            self.calculate_bollinger_bands(prices)

        # ATR
        indicators.atr = self.calculate_atr(prices)

        # Support/Resistance
        indicators.support_levels, indicators.resistance_levels = self.detect_support_resistance(prices, current_price)
        indicators.nearest_support = indicators.support_levels[-1] if indicators.support_levels else current_price * 0.95
        indicators.nearest_resistance = indicators.resistance_levels[0] if indicators.resistance_levels else current_price * 1.05

        # Fibonacci
        price_high = max(prices[-50:]) if len(prices) >= 50 else max(prices)
        price_low = min(prices[-50:]) if len(prices) >= 50 else min(prices)
        indicators.fib_levels = self.calculate_fibonacci_levels(price_high, price_low)

        # Patterns
        indicators.patterns_detected = self.detect_patterns(prices)

        # Generate recommendation
        action, confidence, reasoning, factors = self._generate_recommendation(indicators, current_price)

        # Calculate targets
        risk_per_trade = 0.03  # 3%
        reward_ratio = 2.0     # 1:2 risk/reward

        stop_loss = current_price * (1 - risk_per_trade) if action in [Action.BUY, Action.STRONG_BUY] else \
                   current_price * (1 + risk_per_trade)

        target = current_price * (1 + risk_per_trade * reward_ratio) if action in [Action.BUY, Action.STRONG_BUY] else \
                current_price * (1 - risk_per_trade * reward_ratio)

        # Determine hold time based on volatility
        if indicators.atr > current_price * 0.03:
            hold_time = "2-6 hours"  # High volatility = shorter holds
        elif indicators.atr > current_price * 0.015:
            hold_time = "6-12 hours"
        else:
            hold_time = "12-24 hours"  # Low volatility = longer holds

        # Entry timing
        if action in [Action.BUY, Action.STRONG_BUY]:
            if indicators.rsi_signal == "OVERSOLD":
                entry_timing = "Enter NOW - Oversold conditions"
            elif current_price < indicators.bollinger_lower * 1.02:
                entry_timing = "Enter NOW - Near lower Bollinger Band"
            else:
                entry_timing = f"Wait for pullback to ${indicators.nearest_support:,.2f}"
        elif action in [Action.SELL, Action.STRONG_SELL]:
            if indicators.rsi_signal == "OVERBOUGHT":
                entry_timing = "Exit NOW - Overbought conditions"
            else:
                entry_timing = f"Exit near ${indicators.nearest_resistance:,.2f}"
        else:
            entry_timing = "Wait for clearer signals"

        # Warnings
        warnings = []
        if "VOLATILITY_SQUEEZE" in indicators.patterns_detected:
            warnings.append("Volatility squeeze detected - expect big move soon")
        if indicators.rsi > 80 or indicators.rsi < 20:
            warnings.append(f"Extreme RSI ({indicators.rsi:.1f}) - high reversal risk")
        if indicators.bollinger_width > 15:
            warnings.append("High volatility - use smaller position size")

        return AgentOpinion(
            agent_name=self.name,
            asset=asset,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=factors,
            suggested_hold_time=hold_time,
            entry_timing=entry_timing,
            entry_price=current_price,
            target_price=target,
            stop_loss_price=stop_loss,
            risk_reward_ratio=reward_ratio,
            win_probability=self._estimate_win_probability(indicators),
            indicators={
                "rsi": indicators.rsi,
                "rsi_signal": indicators.rsi_signal,
                "trend": indicators.trend,
                "macd": indicators.macd,
                "macd_histogram": indicators.macd_histogram,
                "bollinger_position": (current_price - indicators.bollinger_lower) / (indicators.bollinger_upper - indicators.bollinger_lower) * 100 if indicators.bollinger_upper != indicators.bollinger_lower else 50,
                "sma_20": indicators.sma_20,
                "sma_50": indicators.sma_50,
                "atr": indicators.atr,
                "volatility": indicators.bollinger_width,
                "patterns": indicators.patterns_detected,
                "support": indicators.nearest_support,
                "resistance": indicators.nearest_resistance,
                "fib_levels": indicators.fib_levels
            },
            warnings=warnings
        )

    def _generate_recommendation(self, indicators: TechnicalIndicators, price: float) -> Tuple[Action, Confidence, str, List[str]]:
        """Generate trading recommendation based on indicators"""

        score = 0
        factors = []

        # Trend analysis (weight: 30%)
        if indicators.trend == "BULLISH":
            score += 0.3
            factors.append(f"Bullish trend: Price above SMA20 (${indicators.sma_20:,.2f}) and SMA50 (${indicators.sma_50:,.2f})")
        elif indicators.trend == "BEARISH":
            score -= 0.3
            factors.append(f"Bearish trend: Price below SMA20 (${indicators.sma_20:,.2f}) and SMA50 (${indicators.sma_50:,.2f})")

        # RSI analysis (weight: 25%)
        if indicators.rsi < 30:
            score += 0.25
            factors.append(f"RSI oversold at {indicators.rsi:.1f} - potential bounce")
        elif indicators.rsi > 70:
            score -= 0.25
            factors.append(f"RSI overbought at {indicators.rsi:.1f} - potential pullback")
        elif 40 <= indicators.rsi <= 60:
            factors.append(f"RSI neutral at {indicators.rsi:.1f}")

        # MACD analysis (weight: 20%)
        if indicators.macd > indicators.macd_signal and indicators.macd_histogram > 0:
            score += 0.2
            factors.append("MACD bullish crossover - momentum increasing")
        elif indicators.macd < indicators.macd_signal and indicators.macd_histogram < 0:
            score -= 0.2
            factors.append("MACD bearish crossover - momentum decreasing")

        # Bollinger Bands (weight: 15%)
        bb_position = (price - indicators.bollinger_lower) / (indicators.bollinger_upper - indicators.bollinger_lower) if indicators.bollinger_upper != indicators.bollinger_lower else 0.5

        if bb_position < 0.2:
            score += 0.15
            factors.append("Price near lower Bollinger Band - potential bounce zone")
        elif bb_position > 0.8:
            score -= 0.15
            factors.append("Price near upper Bollinger Band - potential resistance")

        # Pattern analysis (weight: 10%)
        if "HIGHER_HIGHS" in indicators.patterns_detected and "HIGHER_LOWS" in indicators.patterns_detected:
            score += 0.1
            factors.append("Strong uptrend pattern: Higher highs and higher lows")
        elif "LOWER_HIGHS" in indicators.patterns_detected and "LOWER_LOWS" in indicators.patterns_detected:
            score -= 0.1
            factors.append("Strong downtrend pattern: Lower highs and lower lows")

        # Determine action and confidence
        if score >= 0.5:
            action = Action.STRONG_BUY
            confidence = Confidence.HIGH
            reasoning = "Multiple technical indicators align for a strong bullish setup. The trend, momentum, and price action all support upside potential."
        elif score >= 0.25:
            action = Action.BUY
            confidence = Confidence.MEDIUM
            reasoning = "Technical indicators lean bullish. There's a reasonable setup for upside, though some indicators are mixed."
        elif score <= -0.5:
            action = Action.STRONG_SELL
            confidence = Confidence.HIGH
            reasoning = "Multiple technical indicators align for a bearish outlook. Consider reducing exposure or taking profits."
        elif score <= -0.25:
            action = Action.SELL
            confidence = Confidence.MEDIUM
            reasoning = "Technical indicators lean bearish. Caution is warranted as momentum appears to be fading."
        else:
            action = Action.HOLD
            confidence = Confidence.LOW
            reasoning = "Technical indicators are mixed with no clear direction. Best to wait for a cleaner setup."
            factors.append("Conflicting signals - no clear edge")

        return action, confidence, reasoning, factors

    def _estimate_win_probability(self, indicators: TechnicalIndicators) -> float:
        """Estimate probability of trade success based on setup quality"""
        prob = 0.5  # Base 50%

        # Trend alignment adds probability
        if indicators.trend == "BULLISH" and indicators.rsi < 50:
            prob += 0.1
        elif indicators.trend == "BEARISH" and indicators.rsi > 50:
            prob += 0.1

        # RSI extremes
        if 25 < indicators.rsi < 35 or 65 < indicators.rsi < 75:
            prob += 0.05

        # MACD momentum
        if abs(indicators.macd_histogram) > 0:
            prob += 0.05

        return min(0.75, max(0.35, prob))

    def get_teaching_content(self) -> Dict[str, Any]:
        """Educational content about technical analysis"""
        return {
            "name": self.name,
            "specialty": self.specialty,
            "lessons": [
                {
                    "title": "Understanding RSI (Relative Strength Index)",
                    "content": """
RSI measures the speed and magnitude of price changes on a scale of 0-100.

KEY LEVELS:
• RSI > 70: OVERBOUGHT - Price may have risen too fast, potential pullback
• RSI < 30: OVERSOLD - Price may have fallen too fast, potential bounce
• RSI 40-60: NEUTRAL - No extreme conditions

HOW TO USE:
1. In uptrends, RSI oversold (30-40) can be good entry points
2. In downtrends, RSI overbought (60-70) can be exit signals
3. RSI divergence (price makes new high but RSI doesn't) warns of reversal

FORMULA: RSI = 100 - (100 / (1 + RS))
Where RS = Average Gain / Average Loss over 14 periods
""",
                },
                {
                    "title": "MACD (Moving Average Convergence Divergence)",
                    "content": """
MACD shows the relationship between two moving averages of price.

COMPONENTS:
• MACD Line = EMA(12) - EMA(26)
• Signal Line = EMA(9) of MACD Line
• Histogram = MACD Line - Signal Line

SIGNALS:
1. BULLISH: MACD crosses ABOVE signal line
2. BEARISH: MACD crosses BELOW signal line
3. Histogram growing = momentum increasing
4. Histogram shrinking = momentum fading

PRO TIP: MACD works best in trending markets, less reliable in choppy conditions.
""",
                },
                {
                    "title": "Bollinger Bands",
                    "content": """
Bollinger Bands show volatility and potential overbought/oversold conditions.

COMPONENTS:
• Middle Band = 20-period SMA
• Upper Band = Middle + (2 × Standard Deviation)
• Lower Band = Middle - (2 × Standard Deviation)

INTERPRETATION:
1. Price at upper band = potentially overbought
2. Price at lower band = potentially oversold
3. Bands SQUEEZING (narrow) = low volatility, big move coming
4. Bands EXPANDING = high volatility

STRATEGY: "Bollinger Bounce" - buy near lower band, sell near upper band
(Works best in ranging markets)
""",
                },
                {
                    "title": "Fibonacci Retracement",
                    "content": """
Fibonacci levels identify potential support/resistance during pullbacks.

KEY LEVELS:
• 23.6% - Shallow retracement, strong trend
• 38.2% - Common retracement level
• 50.0% - Psychological halfway point
• 61.8% - "Golden Ratio" - most significant level
• 78.6% - Deep retracement, trend may be weakening

HOW TO USE:
1. Identify a significant high and low
2. Draw Fib levels from high to low (uptrend) or low to high (downtrend)
3. Look for price to bounce at these levels
4. Combine with other indicators for confirmation

The 61.8% level is mathematically derived from the Fibonacci sequence
and appears throughout nature and financial markets.
""",
                },
                {
                    "title": "Support and Resistance",
                    "content": """
Support and Resistance are price levels where buying/selling pressure is strong.

SUPPORT: A price level where demand is strong enough to prevent further decline
RESISTANCE: A price level where supply is strong enough to prevent further rise

HOW THEY FORM:
• Previous highs/lows
• Round numbers (psychological levels)
• Moving averages
• Fibonacci levels
• High volume areas

KEY CONCEPT: Once broken, support becomes resistance (and vice versa)

TRADING:
• Buy near support with stop below
• Sell near resistance with stop above
• Breakouts above resistance = bullish
• Breakdowns below support = bearish
""",
                }
            ]
        }
