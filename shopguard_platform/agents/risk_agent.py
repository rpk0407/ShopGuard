"""
Risk Assessment Agent
=====================
Evaluates risk levels and provides position sizing recommendations.

Analysis:
- Volatility assessment
- Drawdown risk calculation
- Position sizing using Kelly Criterion
- Risk/Reward evaluation
- Portfolio correlation
- Maximum loss scenarios
"""
import math
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from .base_agent import BaseAgent, AgentOpinion, Action, Confidence


@dataclass
class CVDMetrics:
    """Cumulative Volume Delta metrics for whale detection"""
    cvd_value: float  # Current CVD value
    cvd_trend: str  # "ACCUMULATING", "DISTRIBUTING", "NEUTRAL"
    divergence_type: str  # "BULLISH_ABSORPTION", "BEARISH_DISTRIBUTION", "NONE"
    whale_trap_detected: bool  # Price lower low + CVD higher low = whale absorption
    distribution_detected: bool  # Price higher high + CVD lower high = distribution
    micro_check_passed: bool  # Entry condition: whale_trap_detected == True
    signal_strength: float  # 0-1 how strong the divergence is


@dataclass
class RiskMetrics:
    """Risk metrics for an asset"""
    volatility: float  # Historical volatility %
    volatility_percentile: float  # How volatile vs history
    max_drawdown_potential: float  # Estimated max loss
    sharpe_estimate: float  # Risk-adjusted return estimate
    var_95: float  # Value at Risk 95%
    optimal_position_size: float  # Kelly criterion result
    risk_level: str  # low, medium, high, extreme
    correlation_warning: bool
    liquidation_risk: float
    cvd_metrics: CVDMetrics = None  # Whale detection metrics


class RiskAgent(BaseAgent):
    """
    Risk Assessment Agent
    Evaluates risk and provides position sizing guidance
    """

    def __init__(self):
        super().__init__(
            name="Risk Management Agent",
            specialty="Risk assessment, position sizing, and portfolio protection"
        )

        # Risk parameters
        self.max_position_size = 0.20  # Max 20% of portfolio per position
        self.max_daily_loss = 0.05  # Max 5% daily loss
        self.default_stop_loss = 0.03  # 3% default stop loss
        self.default_take_profit = 0.06  # 6% default take profit

        # Asset volatility profiles (baseline)
        self.volatility_profiles = {
            'BTC': {'base_vol': 0.04, 'category': 'crypto'},
            'ETH': {'base_vol': 0.05, 'category': 'crypto'},
            'SPY': {'base_vol': 0.01, 'category': 'index'},
            'QQQ': {'base_vol': 0.015, 'category': 'index'},
            'NVDA': {'base_vol': 0.03, 'category': 'stock'}
        }

    def calculate_volatility(self, prices: List[float]) -> Tuple[float, float]:
        """
        Calculate historical volatility

        Returns: (volatility, volatility_percentile)
        """
        if len(prices) < 10:
            return 0.02, 50.0

        # Calculate returns
        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                  for i in range(1, len(prices))]

        # Standard deviation of returns
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = math.sqrt(variance)

        # Annualized volatility (assuming daily data)
        annual_vol = volatility * math.sqrt(365)

        # Calculate percentile (how volatile vs typical)
        # Compare recent volatility to longer-term
        if len(returns) >= 20:
            recent_vol = math.sqrt(sum((r - mean_return) ** 2 for r in returns[-10:]) / 10)
            longer_vol = math.sqrt(sum((r - mean_return) ** 2 for r in returns[:10]) / 10)

            if longer_vol > 0:
                percentile = min(100, (recent_vol / longer_vol) * 50)
            else:
                percentile = 50
        else:
            percentile = 50

        return volatility, percentile

    def calculate_var(self, prices: List[float], confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR)

        VaR answers: "What's the maximum loss at X% confidence?"
        95% VaR = The loss level that won't be exceeded 95% of the time
        """
        if len(prices) < 20:
            return 0.05  # Default 5%

        # Calculate returns
        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                  for i in range(1, len(prices))]

        # Sort returns (worst to best)
        sorted_returns = sorted(returns)

        # Find the return at the confidence percentile
        index = int(len(sorted_returns) * (1 - confidence))
        var = abs(sorted_returns[index]) if index < len(sorted_returns) else abs(sorted_returns[0])

        return var

    def calculate_max_drawdown(self, prices: List[float]) -> float:
        """
        Calculate maximum drawdown from price history

        Max Drawdown = Largest peak-to-trough decline
        """
        if len(prices) < 2:
            return 0.10  # Default 10%

        peak = prices[0]
        max_dd = 0

        for price in prices:
            if price > peak:
                peak = price
            else:
                drawdown = (peak - price) / peak
                max_dd = max(max_dd, drawdown)

        return max_dd

    def kelly_criterion(self, win_rate: float, win_loss_ratio: float) -> float:
        """
        Calculate optimal position size using Kelly Criterion

        Kelly % = W - [(1-W) / R]
        Where:
        W = Win probability
        R = Win/Loss ratio

        Returns fraction of capital to risk
        """
        if win_loss_ratio <= 0:
            return 0

        kelly = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Use half-Kelly for safety
        half_kelly = kelly / 2

        # Cap at maximum position size
        return max(0, min(self.max_position_size, half_kelly))

    def calculate_position_size(self, capital: float, risk_per_trade: float,
                                 stop_loss_pct: float, price: float) -> Dict:
        """
        Calculate appropriate position size

        Position Size = (Capital × Risk%) / Stop Loss Distance
        """
        risk_amount = capital * risk_per_trade
        stop_loss_distance = price * stop_loss_pct

        if stop_loss_distance == 0:
            return {"shares": 0, "value": 0, "risk": 0}

        shares = risk_amount / stop_loss_distance
        position_value = shares * price

        # Cap at max position size
        max_value = capital * self.max_position_size
        if position_value > max_value:
            position_value = max_value
            shares = position_value / price

        return {
            "shares": round(shares, 4),
            "value": round(position_value, 2),
            "risk": round(risk_amount, 2),
            "pct_of_portfolio": round(position_value / capital * 100, 1)
        }

    def assess_risk_level(self, volatility: float, var: float, max_dd: float) -> str:
        """Categorize overall risk level"""

        risk_score = 0

        # Volatility contribution
        if volatility > 0.05:
            risk_score += 3
        elif volatility > 0.03:
            risk_score += 2
        elif volatility > 0.02:
            risk_score += 1

        # VaR contribution
        if var > 0.08:
            risk_score += 3
        elif var > 0.05:
            risk_score += 2
        elif var > 0.03:
            risk_score += 1

        # Drawdown contribution
        if max_dd > 0.20:
            risk_score += 3
        elif max_dd > 0.10:
            risk_score += 2
        elif max_dd > 0.05:
            risk_score += 1

        if risk_score >= 7:
            return "EXTREME"
        elif risk_score >= 5:
            return "HIGH"
        elif risk_score >= 3:
            return "MEDIUM"
        else:
            return "LOW"

    def calculate_cvd_divergence(self, prices: List[float], volumes: List[float] = None) -> CVDMetrics:
        """
        Calculate Cumulative Volume Delta (CVD) and detect divergences

        CVD = Running sum of (Buy Volume - Sell Volume)

        Since we don't have actual buy/sell volume, we estimate it from price action:
        - Up candle: volume is considered buying pressure
        - Down candle: volume is considered selling pressure

        Whale Detection (Micro-Check):
        - BULLISH ABSORPTION: Price makes Lower Low BUT CVD makes Higher Low
          → Whales are buying into weakness (smart money accumulation)
        - BEARISH DISTRIBUTION: Price makes Higher High BUT CVD makes Lower High
          → Whales are selling into strength (smart money distribution)

        Entry Condition: whale_trap_detected == True (bullish absorption)
        Exit Condition: distribution_detected == True (bearish distribution)
        """
        if len(prices) < 10:
            return CVDMetrics(
                cvd_value=0.0,
                cvd_trend="NEUTRAL",
                divergence_type="NONE",
                whale_trap_detected=False,
                distribution_detected=False,
                micro_check_passed=False,
                signal_strength=0.0
            )

        # Generate synthetic volume if not provided
        if volumes is None or len(volumes) < len(prices):
            # Estimate volume based on price volatility
            volumes = []
            for i in range(len(prices)):
                if i == 0:
                    volumes.append(1.0)
                else:
                    # Higher price change = higher volume (simplified)
                    change = abs(prices[i] - prices[i-1]) / prices[i-1]
                    volumes.append(1.0 + change * 10)

        # Calculate CVD
        cvd_values = []
        cvd = 0.0

        for i in range(1, len(prices)):
            price_change = prices[i] - prices[i-1]
            volume = volumes[i] if i < len(volumes) else 1.0

            # Positive price change = buying pressure, negative = selling pressure
            if price_change > 0:
                delta = volume  # Buy volume
            elif price_change < 0:
                delta = -volume  # Sell volume
            else:
                delta = 0

            cvd += delta
            cvd_values.append(cvd)

        if not cvd_values:
            return CVDMetrics(
                cvd_value=0.0,
                cvd_trend="NEUTRAL",
                divergence_type="NONE",
                whale_trap_detected=False,
                distribution_detected=False,
                micro_check_passed=False,
                signal_strength=0.0
            )

        current_cvd = cvd_values[-1]

        # Determine CVD trend
        recent_cvd = cvd_values[-5:] if len(cvd_values) >= 5 else cvd_values
        if len(recent_cvd) >= 2:
            cvd_change = recent_cvd[-1] - recent_cvd[0]
            if cvd_change > 0:
                cvd_trend = "ACCUMULATING"
            elif cvd_change < 0:
                cvd_trend = "DISTRIBUTING"
            else:
                cvd_trend = "NEUTRAL"
        else:
            cvd_trend = "NEUTRAL"

        # Find recent lows and highs for divergence detection
        lookback = min(10, len(prices) - 1)
        recent_prices = prices[-lookback:]
        recent_cvd_subset = cvd_values[-lookback:] if len(cvd_values) >= lookback else cvd_values

        # Find price lows and highs
        price_low_idx = recent_prices.index(min(recent_prices))
        price_high_idx = recent_prices.index(max(recent_prices))

        # Find CVD lows and highs
        cvd_low_idx = recent_cvd_subset.index(min(recent_cvd_subset)) if recent_cvd_subset else 0
        cvd_high_idx = recent_cvd_subset.index(max(recent_cvd_subset)) if recent_cvd_subset else 0

        # Detect BULLISH ABSORPTION (Whale Trap)
        # Price making lower low but CVD making higher low
        whale_trap_detected = False
        signal_strength = 0.0

        if len(recent_prices) >= 5 and len(recent_cvd_subset) >= 5:
            # Compare first half to second half
            mid = len(recent_prices) // 2

            first_half_price_low = min(recent_prices[:mid])
            second_half_price_low = min(recent_prices[mid:])

            first_half_cvd_low = min(recent_cvd_subset[:mid]) if len(recent_cvd_subset) >= mid else 0
            second_half_cvd_low = min(recent_cvd_subset[mid:]) if len(recent_cvd_subset) > mid else 0

            # Bullish absorption: price lower low + CVD higher low
            if second_half_price_low < first_half_price_low and second_half_cvd_low > first_half_cvd_low:
                whale_trap_detected = True
                # Signal strength based on divergence magnitude
                price_divergence = (first_half_price_low - second_half_price_low) / first_half_price_low
                cvd_divergence = (second_half_cvd_low - first_half_cvd_low) / abs(first_half_cvd_low) if first_half_cvd_low != 0 else 0
                signal_strength = min(1.0, (price_divergence + abs(cvd_divergence)) * 5)

        # Detect BEARISH DISTRIBUTION
        # Price making higher high but CVD making lower high
        distribution_detected = False

        if len(recent_prices) >= 5 and len(recent_cvd_subset) >= 5:
            mid = len(recent_prices) // 2

            first_half_price_high = max(recent_prices[:mid])
            second_half_price_high = max(recent_prices[mid:])

            first_half_cvd_high = max(recent_cvd_subset[:mid]) if len(recent_cvd_subset) >= mid else 0
            second_half_cvd_high = max(recent_cvd_subset[mid:]) if len(recent_cvd_subset) > mid else 0

            # Bearish distribution: price higher high + CVD lower high
            if second_half_price_high > first_half_price_high and second_half_cvd_high < first_half_cvd_high:
                distribution_detected = True

        # Determine divergence type
        if whale_trap_detected:
            divergence_type = "BULLISH_ABSORPTION"
        elif distribution_detected:
            divergence_type = "BEARISH_DISTRIBUTION"
        else:
            divergence_type = "NONE"

        return CVDMetrics(
            cvd_value=round(current_cvd, 2),
            cvd_trend=cvd_trend,
            divergence_type=divergence_type,
            whale_trap_detected=whale_trap_detected,
            distribution_detected=distribution_detected,
            micro_check_passed=whale_trap_detected,  # Entry condition
            signal_strength=round(signal_strength, 3)
        )

    def analyze(self, asset: str, data: Dict[str, Any]) -> AgentOpinion:
        """Perform comprehensive risk assessment"""

        current_price = data.get('price', 0)
        prices = data.get('price_history', [current_price] * 50)
        capital = data.get('capital', 100)
        current_positions = data.get('positions', [])

        # Calculate risk metrics
        volatility, vol_percentile = self.calculate_volatility(prices)
        var_95 = self.calculate_var(prices)
        max_dd = self.calculate_max_drawdown(prices)

        # Risk level
        risk_level = self.assess_risk_level(volatility, var_95, max_dd)

        # Calculate CVD Divergence (Micro-Check for whale detection)
        volumes = data.get('volume_history', None)
        cvd_metrics = self.calculate_cvd_divergence(prices, volumes)

        # Position sizing
        # Estimate win rate based on other agents (default 55%)
        estimated_win_rate = data.get('estimated_win_rate', 0.55)
        win_loss_ratio = self.default_take_profit / self.default_stop_loss  # 2:1

        kelly = self.kelly_criterion(estimated_win_rate, win_loss_ratio)

        position_sizing = self.calculate_position_size(
            capital=capital,
            risk_per_trade=kelly * 0.5,  # Conservative
            stop_loss_pct=self.default_stop_loss,
            price=current_price
        )

        # Check correlation with existing positions
        correlation_warning = False
        if current_positions:
            crypto_count = sum(1 for p in current_positions if p.get('asset') in ['BTC', 'ETH'])
            stock_count = len(current_positions) - crypto_count

            if asset in ['BTC', 'ETH'] and crypto_count >= 2:
                correlation_warning = True
            if asset in ['SPY', 'QQQ', 'NVDA'] and stock_count >= 2:
                correlation_warning = True

        # Generate action based on risk
        action, confidence = self._generate_recommendation(
            risk_level, volatility, vol_percentile, position_sizing, correlation_warning
        )

        # Key factors
        key_factors = [
            f"Risk Level: {risk_level}",
            f"Daily Volatility: {volatility:.1%} (percentile: {vol_percentile:.0f})",
            f"Value at Risk (95%): {var_95:.1%} - Could lose this much 5% of days",
            f"Max Drawdown Risk: {max_dd:.1%}",
            f"Recommended Position: ${position_sizing['value']:.2f} ({position_sizing['pct_of_portfolio']:.0f}% of portfolio)",
            f"Kelly Optimal Sizing: {kelly:.1%} of portfolio"
        ]

        if correlation_warning:
            key_factors.append("⚠️ Correlation Warning: Similar positions already held")

        # CVD Divergence key factors
        key_factors.append(f"🐋 CVD Trend: {cvd_metrics.cvd_trend}")
        if cvd_metrics.whale_trap_detected:
            key_factors.append("🎯 MICRO-CHECK PASSED: Whale absorption detected (bullish)")
        if cvd_metrics.distribution_detected:
            key_factors.append("⚠️ Distribution detected: Smart money selling into strength")

        # Reasoning
        reasoning = self._build_reasoning(risk_level, volatility, var_95, position_sizing, correlation_warning)

        # Warnings
        warnings = []
        if risk_level == "EXTREME":
            warnings.append("EXTREME RISK: Consider reducing position size by 50%")
        if risk_level == "HIGH":
            warnings.append("HIGH RISK: Use tight stops and smaller positions")
        if vol_percentile > 80:
            warnings.append(f"Volatility is elevated ({vol_percentile:.0f} percentile)")
        if max_dd > 0.15:
            warnings.append(f"Asset has shown {max_dd:.0%} drawdowns historically")
        if correlation_warning:
            warnings.append("Portfolio may be overexposed to this sector")

        # CVD Divergence warnings
        if cvd_metrics.distribution_detected:
            warnings.append("🔴 DISTRIBUTION EXIT: Smart money selling detected - consider taking profits")

        # Hold time based on risk
        if risk_level == "EXTREME":
            hold_time = "1-4 hours max (high risk environment)"
        elif risk_level == "HIGH":
            hold_time = "4-8 hours (monitor closely)"
        elif risk_level == "MEDIUM":
            hold_time = "8-24 hours (standard swing trade)"
        else:
            hold_time = "1-3 days (low risk, can hold longer)"

        # Entry timing
        if action == Action.BUY:
            entry_timing = f"Safe to enter with ${position_sizing['value']:.2f} position"
        elif action == Action.HOLD:
            entry_timing = "Risk is elevated - wait for volatility to decrease"
        else:
            entry_timing = "Risk too high - avoid or use minimal position"

        return AgentOpinion(
            agent_name=self.name,
            asset=asset,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            suggested_hold_time=hold_time,
            entry_timing=entry_timing,
            entry_price=current_price,
            stop_loss_price=current_price * (1 - self.default_stop_loss),
            target_price=current_price * (1 + self.default_take_profit),
            risk_reward_ratio=win_loss_ratio,
            win_probability=estimated_win_rate,
            indicators={
                "volatility": volatility,
                "volatility_percentile": vol_percentile,
                "var_95": var_95,
                "max_drawdown": max_dd,
                "risk_level": risk_level,
                "kelly_optimal": kelly,
                "position_sizing": position_sizing,
                "correlation_warning": correlation_warning,
                "stop_loss_pct": self.default_stop_loss,
                "take_profit_pct": self.default_take_profit,
                # CVD Divergence metrics (Micro-Check)
                "cvd_value": cvd_metrics.cvd_value,
                "cvd_trend": cvd_metrics.cvd_trend,
                "cvd_divergence_type": cvd_metrics.divergence_type,
                "whale_trap_detected": cvd_metrics.whale_trap_detected,
                "distribution_detected": cvd_metrics.distribution_detected,
                "micro_check_passed": cvd_metrics.micro_check_passed,
                "cvd_signal_strength": cvd_metrics.signal_strength
            },
            warnings=warnings
        )

    def _generate_recommendation(self, risk_level: str, volatility: float,
                                  vol_percentile: float, position: Dict,
                                  correlation_warning: bool) -> Tuple[Action, Confidence]:
        """Generate recommendation based on risk"""

        if risk_level == "EXTREME":
            return Action.SELL, Confidence.HIGH
        elif risk_level == "HIGH":
            if correlation_warning:
                return Action.HOLD, Confidence.MEDIUM
            return Action.HOLD, Confidence.LOW
        elif risk_level == "MEDIUM":
            if vol_percentile > 70:
                return Action.HOLD, Confidence.LOW
            return Action.BUY, Confidence.LOW
        else:
            return Action.BUY, Confidence.MEDIUM

    def _build_reasoning(self, risk_level: str, volatility: float, var: float,
                         position: Dict, correlation: bool) -> str:
        """Build risk assessment reasoning"""

        reasoning = f"Risk assessment shows {risk_level} risk environment. "
        reasoning += f"Daily volatility is {volatility:.1%}, meaning typical daily moves of ±{volatility*100:.1f}%. "
        reasoning += f"With 95% confidence, daily loss should not exceed {var:.1%}. "

        if risk_level in ["EXTREME", "HIGH"]:
            reasoning += "Given elevated risk, position sizing should be reduced. "
        elif risk_level == "LOW":
            reasoning += "Favorable risk conditions allow for standard position sizing. "

        reasoning += f"Recommended position size is ${position['value']:.2f} ({position['pct_of_portfolio']:.0f}% of portfolio) with ${position['risk']:.2f} at risk. "

        if correlation:
            reasoning += "⚠️ Note: You already have correlated positions. Consider diversifying. "

        return reasoning

    def get_teaching_content(self) -> Dict[str, Any]:
        """Educational content about risk management"""
        return {
            "name": self.name,
            "specialty": self.specialty,
            "lessons": [
                {
                    "title": "Position Sizing: The Most Important Skill",
                    "content": """
Position sizing determines how much of your capital to risk on each trade.
It's MORE IMPORTANT than your entry strategy.

THE 1-2% RULE:
Never risk more than 1-2% of your portfolio on a single trade.

CALCULATION:
Position Size = (Account Risk) / (Trade Risk)

Example with $100 portfolio:
- Risk 2% = $2 max loss per trade
- Stop loss at 3% below entry
- Position Size = $2 / 0.03 = $66.67 max position

WHY THIS MATTERS:
- 10 consecutive losses at 2% = 18% drawdown (recoverable)
- 10 consecutive losses at 10% = 65% drawdown (devastating)

KELLY CRITERION:
Optimal bet size = Win% - (Loss% / Win-Loss Ratio)
But use HALF-KELLY for safety!
"""
                },
                {
                    "title": "Understanding Volatility",
                    "content": """
Volatility measures how much price moves over time.

HIGH VOLATILITY ASSETS (e.g., BTC, ETH):
- Can move 5-10% in a day
- Larger stop losses needed
- Smaller position sizes required
- Higher profit potential but higher risk

LOW VOLATILITY ASSETS (e.g., SPY):
- Typically move 0.5-2% daily
- Tighter stops possible
- Larger positions acceptable
- Lower risk, lower reward

VOLATILITY INDICATORS:
1. ATR (Average True Range) - Average daily movement
2. Bollinger Band Width - Relative volatility
3. VIX - Market fear gauge

TRADING VOLATILITY:
- High vol = reduce size, widen stops
- Low vol = increase size, tighten stops
- Volatility clusters - high vol follows high vol
"""
                },
                {
                    "title": "Risk/Reward Ratio",
                    "content": """
Risk/Reward ratio compares potential profit to potential loss.

CALCULATION:
R:R = (Target Price - Entry) / (Entry - Stop Loss)

EXAMPLE:
Entry: $100
Stop: $97 (risking $3)
Target: $109 (potential gain $9)
R:R = 9/3 = 3:1

MINIMUM RATIOS:
- Scalping: 1:1 (need 60%+ win rate)
- Swing trading: 2:1 (need 40%+ win rate)
- Position trading: 3:1+ (can profit with 30% wins)

THE MATH:
With 2:1 R:R and 40% win rate:
10 trades: 4 wins × $2 = $8, 6 losses × $1 = $6
Net: +$2 profit despite losing 60% of trades!

RULE: Never take trades with less than 1.5:1 R:R
"""
                },
                {
                    "title": "Stop Losses and Take Profits",
                    "content": """
Stop losses and take profits are your safety nets.

STOP LOSS TYPES:
1. Fixed Percentage (e.g., 3% below entry)
   - Simple, consistent
   - May be too tight in volatile markets

2. ATR-Based (e.g., 2× ATR below entry)
   - Adapts to volatility
   - Gives trades room to breathe

3. Support/Resistance Based
   - Place below key support levels
   - More likely to hold if placed correctly

TAKE PROFIT STRATEGIES:
1. Fixed Multiple (e.g., 2× your risk)
   - Simple, maintains R:R

2. Scaling Out
   - Take 50% at 1:1
   - Take 25% at 2:1
   - Let 25% run with trailing stop

3. Resistance-Based
   - Target known resistance levels

GOLDEN RULES:
✓ Always set stop BEFORE entering trade
✓ Never move stop further away
✓ Let winners run, cut losers short
✓ Use position sizing to control risk
"""
                },
                {
                    "title": "Managing Drawdowns",
                    "content": """
Drawdowns are peak-to-trough declines in your portfolio.

DRAWDOWN MATH:
-10% drawdown needs +11% to recover
-25% drawdown needs +33% to recover
-50% drawdown needs +100% to recover
-75% drawdown needs +300% to recover

This is why AVOIDING large losses is crucial!

MAX DRAWDOWN LIMITS:
- Conservative: 10% max drawdown
- Moderate: 15-20% max drawdown
- Aggressive: 25% max drawdown

DRAWDOWN RULES:
1. Daily loss limit: Stop trading if down 3-5% in one day
2. Weekly loss limit: Reduce size if down 5-10% in week
3. Monthly loss limit: Take break if down 15%+ in month

RECOVERY PROTOCOL:
After significant drawdown:
1. Cut position sizes in half
2. Only take highest-confidence setups
3. Slowly increase size as you recover
4. Never revenge trade!
"""
                }
            ]
        }
