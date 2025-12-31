"""
DYNAMIC RISK ENGINE - The Smart Shield
========================================
Professional-grade risk management using ATR (Average True Range)
to create stops that breathe with the market.

No more suicide 3% stops in a volatile crash.
No more getting stopped out by noise in tight markets.

Key Concepts:
- ATR measures actual market volatility over N periods
- Stops are set as multiples of ATR (typically 1.5-2x)
- Take Profits use risk/reward ratios (typically 2:1 or 3:1)
- Position sizing adjusts to volatility (smaller in chaos)
"""

import math
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """Market volatility classification"""
    ULTRA_LOW = "ultra_low"      # ATR < 0.5% - Tight, boring market
    LOW = "low"                   # ATR 0.5-1% - Normal calm
    NORMAL = "normal"             # ATR 1-2% - Healthy volatility
    ELEVATED = "elevated"         # ATR 2-3% - Getting spicy
    HIGH = "high"                 # ATR 3-5% - Danger zone
    EXTREME = "extreme"           # ATR > 5% - Crash/melt-up territory


@dataclass
class RiskCalculation:
    """Complete risk calculation for a trade"""
    # Entry
    entry_price: float
    direction: str  # "LONG" or "SHORT"

    # Dynamic Stops
    stop_loss: float
    stop_distance: float
    stop_distance_pct: float

    # Dynamic Targets
    take_profit: float
    tp_distance: float
    tp_distance_pct: float

    # Risk/Reward
    risk_reward_ratio: float

    # Volatility Context
    atr: float
    atr_pct: float
    volatility_regime: VolatilityRegime
    atr_multiple_used: float

    # Position Sizing
    recommended_size_pct: float  # % of portfolio
    max_loss_amount: float  # $ at risk if stopped
    potential_profit: float  # $ if TP hit

    # Quality Score
    trade_quality: str  # "A+", "A", "B", "C", "AVOID"
    quality_reason: str

    def to_dict(self) -> Dict:
        return {
            'entry': self.entry_price,
            'direction': self.direction,
            'stop_loss': round(self.stop_loss, 2),
            'take_profit': round(self.take_profit, 2),
            'stop_distance_pct': round(self.stop_distance_pct * 100, 2),
            'tp_distance_pct': round(self.tp_distance_pct * 100, 2),
            'risk_reward': round(self.risk_reward_ratio, 2),
            'atr': round(self.atr, 2),
            'atr_pct': round(self.atr_pct * 100, 3),
            'volatility_regime': self.volatility_regime.value,
            'recommended_size_pct': round(self.recommended_size_pct * 100, 2),
            'max_loss': round(self.max_loss_amount, 2),
            'potential_profit': round(self.potential_profit, 2),
            'trade_quality': self.trade_quality,
            'quality_reason': self.quality_reason
        }


class DynamicRiskEngine:
    """
    THE SMART SHIELD
    ================
    Professional ATR-based risk management.

    Unlike amateur fixed-percentage stops:
    - In tight markets: Stops are CLOSER (avoid getting chopped)
    - In volatile markets: Stops are WIDER (give room to breathe)
    - In extreme volatility: REDUCE SIZE or STAY OUT
    """

    def __init__(
        self,
        atr_period: int = 14,
        default_atr_multiple: float = 1.5,
        default_rr_ratio: float = 2.0,
        max_risk_per_trade: float = 0.02,  # 2% max risk per trade
        max_position_size: float = 0.25    # 25% max position
    ):
        self.atr_period = atr_period
        self.default_atr_multiple = default_atr_multiple
        self.default_rr_ratio = default_rr_ratio
        self.max_risk_per_trade = max_risk_per_trade
        self.max_position_size = max_position_size

        # ATR regime thresholds (as % of price)
        self.regime_thresholds = {
            VolatilityRegime.ULTRA_LOW: 0.005,   # < 0.5%
            VolatilityRegime.LOW: 0.01,          # 0.5-1%
            VolatilityRegime.NORMAL: 0.02,       # 1-2%
            VolatilityRegime.ELEVATED: 0.03,     # 2-3%
            VolatilityRegime.HIGH: 0.05,         # 3-5%
            # Anything above is EXTREME
        }

        logger.info(f"Dynamic Risk Engine initialized: ATR({atr_period}), {default_atr_multiple}x stop, {default_rr_ratio}:1 R/R")

    def calculate_atr(self, price_history: List[float], period: int = None) -> float:
        """
        Calculate Average True Range from price history.

        True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
        ATR = SMA of True Range over N periods

        Since we only have closing prices, we estimate:
        TR ≈ |Close - PrevClose| * 1.5 (empirical adjustment)
        """
        if period is None:
            period = self.atr_period

        if len(price_history) < period + 1:
            # Not enough data - use simple volatility estimate
            if len(price_history) < 2:
                return price_history[-1] * 0.02  # Default 2% ATR

            # Use available data
            returns = []
            for i in range(1, len(price_history)):
                ret = abs(price_history[i] - price_history[i-1])
                returns.append(ret)

            return sum(returns) / len(returns) * 1.5

        # Calculate True Range approximation
        true_ranges = []
        for i in range(1, len(price_history)):
            tr = abs(price_history[i] - price_history[i-1])
            true_ranges.append(tr)

        # Adjust for intraday range (empirical: close-to-close is ~60% of true range)
        true_ranges = [tr * 1.5 for tr in true_ranges]

        # Calculate ATR (Simple Moving Average of last N true ranges)
        recent_tr = true_ranges[-period:]
        atr = sum(recent_tr) / len(recent_tr)

        return atr

    def calculate_atr_from_ohlc(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = None
    ) -> float:
        """
        Calculate proper ATR from OHLC data.
        Use this when you have full candlestick data.
        """
        if period is None:
            period = self.atr_period

        if len(closes) < period + 1:
            return closes[-1] * 0.02  # Default

        true_ranges = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_prev_close = abs(highs[i] - closes[i-1])
            low_prev_close = abs(lows[i] - closes[i-1])

            tr = max(high_low, high_prev_close, low_prev_close)
            true_ranges.append(tr)

        # EMA-style ATR (Wilder's smoothing)
        atr = sum(true_ranges[:period]) / period

        for tr in true_ranges[period:]:
            atr = (atr * (period - 1) + tr) / period

        return atr

    def classify_volatility(self, atr: float, current_price: float) -> VolatilityRegime:
        """Classify current volatility regime based on ATR as % of price"""
        atr_pct = atr / current_price

        if atr_pct < self.regime_thresholds[VolatilityRegime.ULTRA_LOW]:
            return VolatilityRegime.ULTRA_LOW
        elif atr_pct < self.regime_thresholds[VolatilityRegime.LOW]:
            return VolatilityRegime.LOW
        elif atr_pct < self.regime_thresholds[VolatilityRegime.NORMAL]:
            return VolatilityRegime.NORMAL
        elif atr_pct < self.regime_thresholds[VolatilityRegime.ELEVATED]:
            return VolatilityRegime.ELEVATED
        elif atr_pct < self.regime_thresholds[VolatilityRegime.HIGH]:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME

    def get_atr_multiple_for_regime(self, regime: VolatilityRegime) -> float:
        """
        Adjust ATR multiple based on volatility regime.

        - Low vol: Use TIGHTER stops (1.0-1.2x ATR)
        - Normal: Standard stops (1.5x ATR)
        - High vol: WIDER stops (2.0-2.5x ATR) or reduce size
        """
        multipliers = {
            VolatilityRegime.ULTRA_LOW: 1.0,   # Very tight, market is sleeping
            VolatilityRegime.LOW: 1.2,         # Slightly tight
            VolatilityRegime.NORMAL: 1.5,      # Standard
            VolatilityRegime.ELEVATED: 1.8,    # Give more room
            VolatilityRegime.HIGH: 2.0,        # Wide stops
            VolatilityRegime.EXTREME: 2.5,     # Very wide, but reduce size!
        }
        return multipliers.get(regime, self.default_atr_multiple)

    def get_position_size_adjustment(self, regime: VolatilityRegime) -> float:
        """
        Adjust position size based on volatility.

        Higher volatility = Smaller position
        This maintains consistent dollar risk across regimes.
        """
        adjustments = {
            VolatilityRegime.ULTRA_LOW: 1.0,   # Full size
            VolatilityRegime.LOW: 1.0,         # Full size
            VolatilityRegime.NORMAL: 0.8,      # Slightly reduced
            VolatilityRegime.ELEVATED: 0.6,    # Reduced
            VolatilityRegime.HIGH: 0.4,        # Significantly reduced
            VolatilityRegime.EXTREME: 0.2,     # Minimal exposure
        }
        return adjustments.get(regime, 1.0)

    def calculate_dynamic_risk(
        self,
        entry_price: float,
        direction: str,
        price_history: List[float],
        portfolio_value: float,
        signal_confidence: float = 0.7,
        custom_rr_ratio: float = None
    ) -> RiskCalculation:
        """
        MAIN METHOD: Calculate complete risk parameters for a trade.

        Args:
            entry_price: Intended entry price
            direction: "LONG" or "SHORT"
            price_history: List of recent prices (for ATR calculation)
            portfolio_value: Total portfolio value in $
            signal_confidence: 0-1 confidence score (affects sizing)
            custom_rr_ratio: Override default risk/reward ratio

        Returns:
            RiskCalculation with all risk parameters
        """
        # Calculate ATR
        atr = self.calculate_atr(price_history)
        atr_pct = atr / entry_price

        # Classify volatility regime
        regime = self.classify_volatility(atr, entry_price)

        # Get adjusted ATR multiple for this regime
        atr_multiple = self.get_atr_multiple_for_regime(regime)

        # Calculate stop distance
        stop_distance = atr * atr_multiple
        stop_distance_pct = stop_distance / entry_price

        # Calculate stop price
        if direction.upper() == "LONG":
            stop_loss = entry_price - stop_distance
        else:
            stop_loss = entry_price + stop_distance

        # Calculate take profit using R:R ratio
        rr_ratio = custom_rr_ratio or self.default_rr_ratio
        tp_distance = stop_distance * rr_ratio
        tp_distance_pct = tp_distance / entry_price

        if direction.upper() == "LONG":
            take_profit = entry_price + tp_distance
        else:
            take_profit = entry_price - tp_distance

        # Calculate position sizing
        size_adjustment = self.get_position_size_adjustment(regime)
        confidence_adjustment = 0.5 + (signal_confidence * 0.5)  # 0.5 to 1.0

        # Base size from max risk per trade
        # If we risk 2% of portfolio and stop is 3% away, position = 2%/3% = 66% of portfolio
        base_size = self.max_risk_per_trade / stop_distance_pct

        # Apply adjustments
        recommended_size = min(
            base_size * size_adjustment * confidence_adjustment,
            self.max_position_size
        )

        # Calculate dollar amounts
        position_value = portfolio_value * recommended_size
        max_loss = position_value * stop_distance_pct
        potential_profit = position_value * tp_distance_pct

        # Assess trade quality
        trade_quality, quality_reason = self._assess_trade_quality(
            regime, signal_confidence, rr_ratio, stop_distance_pct
        )

        return RiskCalculation(
            entry_price=entry_price,
            direction=direction.upper(),
            stop_loss=stop_loss,
            stop_distance=stop_distance,
            stop_distance_pct=stop_distance_pct,
            take_profit=take_profit,
            tp_distance=tp_distance,
            tp_distance_pct=tp_distance_pct,
            risk_reward_ratio=rr_ratio,
            atr=atr,
            atr_pct=atr_pct,
            volatility_regime=regime,
            atr_multiple_used=atr_multiple,
            recommended_size_pct=recommended_size,
            max_loss_amount=max_loss,
            potential_profit=potential_profit,
            trade_quality=trade_quality,
            quality_reason=quality_reason
        )

    def _assess_trade_quality(
        self,
        regime: VolatilityRegime,
        confidence: float,
        rr_ratio: float,
        stop_pct: float
    ) -> Tuple[str, str]:
        """
        Assess overall trade quality.

        Returns: (grade, reason)
        """
        # Extreme volatility = avoid
        if regime == VolatilityRegime.EXTREME:
            return "AVOID", "Extreme volatility - capital preservation mode"

        # High volatility with low confidence = avoid
        if regime == VolatilityRegime.HIGH and confidence < 0.6:
            return "AVOID", "High volatility with weak signal - too risky"

        # Calculate quality score
        score = 0
        reasons = []

        # Confidence contribution (0-40 points)
        score += confidence * 40
        if confidence >= 0.8:
            reasons.append("strong signal")
        elif confidence >= 0.6:
            reasons.append("decent signal")
        else:
            reasons.append("weak signal")

        # R:R contribution (0-30 points)
        if rr_ratio >= 3:
            score += 30
            reasons.append("excellent R:R")
        elif rr_ratio >= 2:
            score += 20
            reasons.append("good R:R")
        elif rr_ratio >= 1.5:
            score += 10
            reasons.append("acceptable R:R")
        else:
            reasons.append("poor R:R")

        # Volatility contribution (0-30 points)
        vol_scores = {
            VolatilityRegime.ULTRA_LOW: 15,  # Too quiet can mean low opportunity
            VolatilityRegime.LOW: 25,
            VolatilityRegime.NORMAL: 30,     # Ideal
            VolatilityRegime.ELEVATED: 20,
            VolatilityRegime.HIGH: 10,
        }
        score += vol_scores.get(regime, 0)
        reasons.append(f"{regime.value} volatility")

        # Grade based on score
        if score >= 85:
            grade = "A+"
        elif score >= 75:
            grade = "A"
        elif score >= 60:
            grade = "B"
        elif score >= 45:
            grade = "C"
        else:
            grade = "D"

        reason = f"{grade} trade: {', '.join(reasons)}"

        return grade, reason

    def format_trade_ticket(self, calc: RiskCalculation, portfolio_value: float) -> str:
        """
        Format a professional trade ticket for display.
        """
        position_value = portfolio_value * calc.recommended_size_pct

        ticket = f"""
╔══════════════════════════════════════════════════════════════╗
║                      TRADE TICKET                            ║
╠══════════════════════════════════════════════════════════════╣
║  Direction: {calc.direction:<10}  Quality: {calc.trade_quality:<5}                    ║
╠══════════════════════════════════════════════════════════════╣
║  ENTRY:       ${calc.entry_price:>12,.2f}                              ║
║  STOP LOSS:   ${calc.stop_loss:>12,.2f}  ({calc.stop_distance_pct*100:>5.2f}% risk)           ║
║  TAKE PROFIT: ${calc.take_profit:>12,.2f}  ({calc.tp_distance_pct*100:>5.2f}% reward)         ║
╠══════════════════════════════════════════════════════════════╣
║  Risk/Reward: {calc.risk_reward_ratio:.1f}:1                                         ║
║  ATR({self.atr_period}):     ${calc.atr:>8,.2f}  ({calc.atr_pct*100:.2f}% of price)           ║
║  Volatility:  {calc.volatility_regime.value:<12}                              ║
╠══════════════════════════════════════════════════════════════╣
║  POSITION SIZE                                               ║
║  Recommended: {calc.recommended_size_pct*100:>5.1f}% of portfolio (${position_value:>,.0f})        ║
║                                                              ║
║  If STOPPED:  -${calc.max_loss_amount:>8,.2f}  (max loss)                   ║
║  If TP HIT:   +${calc.potential_profit:>8,.2f}  (potential profit)          ║
╠══════════════════════════════════════════════════════════════╣
║  {calc.quality_reason:<60} ║
╚══════════════════════════════════════════════════════════════╝
"""
        return ticket


# Singleton instance
_risk_engine: Optional[DynamicRiskEngine] = None


def get_risk_engine() -> DynamicRiskEngine:
    """Get or create global risk engine instance"""
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = DynamicRiskEngine()
    return _risk_engine


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test the engine
    engine = DynamicRiskEngine()

    # Simulate BTC price history
    import random
    base_price = 95000
    prices = [base_price]
    for _ in range(50):
        change = random.gauss(0, 0.015) * prices[-1]  # ~1.5% daily volatility
        prices.append(prices[-1] + change)

    # Calculate risk for a LONG trade
    calc = engine.calculate_dynamic_risk(
        entry_price=prices[-1],
        direction="LONG",
        price_history=prices,
        portfolio_value=10000,
        signal_confidence=0.75
    )

    print(engine.format_trade_ticket(calc, 10000))
    print("\nRisk Calculation Details:")
    for k, v in calc.to_dict().items():
        print(f"  {k}: {v}")
