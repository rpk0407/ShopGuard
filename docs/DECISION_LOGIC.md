# Central Decision Logic - Pseudocode

This document describes the core decision-making logic of the trading system.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     DECISION PIPELINE                            │
│                                                                  │
│  Market Data → Feature Engineering → AI Models → Risk Check →   │
│  → Position Sizing → Execution → Risk Monitoring                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Central Decision Engine Pseudocode

```python
class TradingDecisionEngine:
    """
    Central decision-making logic.

    This is the "brain" that coordinates:
    1. Signal generation (AI models)
    2. Risk management
    3. Position sizing
    4. Execution
    """

    def __init__(self):
        # Core components
        self.feature_engineer = FeatureEngineer()
        self.signal_model = TemporalFusionNetwork()
        self.rl_agent = TradingPPOAgent()
        self.risk_manager = RiskManager()
        self.position_sizer = FractionalKelly(fraction=0.25)
        self.execution_engine = ExecutionEngine()
        self.kill_switch = KillSwitch()

    def on_market_update(self, market_data: MarketData):
        """
        Main decision loop - called on each market update.

        This is the HOT PATH - must be fast.
        """

        # =====================================================================
        # STEP 1: SAFETY CHECKS (Before anything else)
        # =====================================================================

        if self.kill_switch.state != KillSwitchState.ARMED:
            return  # System halted

        if self.risk_manager.current_risk_level == RiskLevel.CRITICAL:
            self.reduce_exposure()
            return

        # =====================================================================
        # STEP 2: FEATURE ENGINEERING
        # =====================================================================

        features = self.feature_engineer.compute_features(
            prices=market_data.prices,
            volumes=market_data.volumes,
            orderbook=market_data.orderbook
        )

        # =====================================================================
        # STEP 3: SIGNAL GENERATION
        # =====================================================================

        # Get predictions from AI model
        predictions = self.signal_model.forward(features)

        # predictions contains:
        # - direction: [-1, 1] (short to long)
        # - magnitude: [0, inf) (expected move size)
        # - confidence: [0, 1] (model confidence)

        # Also get RL agent's action
        rl_action = self.rl_agent.select_action(
            state=self.get_state(),
            deterministic=True  # No exploration in live trading
        )

        # =====================================================================
        # STEP 4: SIGNAL COMBINATION & FILTERING
        # =====================================================================

        # Combine signals (ensemble approach)
        combined_signal = self.combine_signals(
            model_prediction=predictions,
            rl_action=rl_action,
            weights=[0.6, 0.4]  # Weight model more than RL
        )

        # Filter by confidence
        if combined_signal.confidence < MIN_CONFIDENCE_THRESHOLD:
            return  # Not confident enough

        # Filter by signal strength
        if abs(combined_signal.direction) < MIN_SIGNAL_STRENGTH:
            return  # Signal too weak

        # =====================================================================
        # STEP 5: POSITION SIZING (Kelly Criterion)
        # =====================================================================

        # Estimate trade expectation
        expectation = self.estimate_expectation(
            signal=combined_signal,
            historical_accuracy=self.get_model_accuracy()
        )

        # Calculate optimal position size
        kelly_fraction = self.position_sizer.calculate_fraction(expectation)

        # Adjust for current conditions
        adjusted_size = kelly_fraction * self.volatility_adjustment() \
                                       * self.confidence_adjustment(combined_signal.confidence)

        # =====================================================================
        # STEP 6: RISK CHECKS
        # =====================================================================

        target_position = combined_signal.direction * adjusted_size
        position_change = target_position - self.current_position

        # Pre-trade risk check
        allowed, reason = self.risk_manager.check_order(
            symbol=self.symbol,
            side="buy" if position_change > 0 else "sell",
            quantity=abs(position_change),
            price=market_data.last_price
        )

        if not allowed:
            self.log(f"Trade blocked: {reason}")
            return

        # =====================================================================
        # STEP 7: EXECUTION
        # =====================================================================

        if abs(position_change) > MIN_TRADE_SIZE:
            # Choose execution algorithm
            if abs(position_change) > LARGE_ORDER_THRESHOLD:
                order_type = OrderType.TWAP  # Split large orders
            else:
                order_type = OrderType.LIMIT

            # Create and submit order
            order = self.execution_engine.create_order(
                symbol=self.symbol,
                side="buy" if position_change > 0 else "sell",
                quantity=abs(position_change),
                order_type=order_type,
                limit_price=self.calculate_limit_price(
                    direction=position_change,
                    market_data=market_data
                )
            )

            self.execution_engine.submit_order(order)

    def combine_signals(self, model_prediction, rl_action, weights):
        """
        Combine multiple signal sources.

        Ensemble methods reduce variance and improve robustness.
        """
        direction = (
            weights[0] * model_prediction.direction +
            weights[1] * rl_action.target_position
        )

        # Confidence is minimum of sources (conservative)
        confidence = min(
            model_prediction.confidence,
            rl_action.confidence if hasattr(rl_action, 'confidence') else 0.5
        )

        return Signal(direction=direction, confidence=confidence)

    def volatility_adjustment(self) -> float:
        """
        Scale position by inverse volatility.

        Higher vol = smaller position (risk parity concept)
        """
        current_vol = self.get_current_volatility()
        target_vol = 0.15  # Target 15% annualized

        if current_vol > 0:
            return min(1.0, target_vol / current_vol)
        return 1.0

    def confidence_adjustment(self, confidence: float) -> float:
        """
        Scale position by model confidence.

        Low confidence = smaller position
        """
        # Sigmoid-like scaling
        return confidence ** 2  # Aggressive reduction for low confidence

    def calculate_limit_price(self, direction: float, market_data) -> float:
        """
        Calculate limit price with edge.

        We want to be a price maker, not taker.
        """
        spread = market_data.ask - market_data.bid

        if direction > 0:  # Buying
            # Bid + small increment (trying to cross spread minimally)
            return market_data.bid + spread * 0.3
        else:  # Selling
            # Ask - small increment
            return market_data.ask - spread * 0.3

    def reduce_exposure(self):
        """
        Emergency exposure reduction.

        Called when risk level is critical.
        """
        for symbol, position in self.positions.items():
            if abs(position) > 0:
                # Flatten at market
                self.execution_engine.create_order(
                    symbol=symbol,
                    side="sell" if position > 0 else "buy",
                    quantity=abs(position),
                    order_type=OrderType.MARKET
                )


# =============================================================================
# REWARD FUNCTION (The most important design decision)
# =============================================================================

def compute_reward(
    portfolio_return: float,
    position_change: float,
    portfolio_value: float,
    peak_value: float
) -> float:
    """
    Reward function for RL agent.

    THE REWARD FUNCTION IS THE STRATEGY.

    Components:
    1. Risk-adjusted returns (not raw returns)
    2. Transaction cost penalty
    3. Drawdown penalty
    4. Turnover penalty

    This encourages:
    - High Sharpe ratio, not just high returns
    - Low turnover (fewer trades)
    - Controlled drawdowns
    """

    # Component 1: Risk-adjusted return (differential Sharpe)
    sharpe_component = differential_sharpe_ratio(portfolio_return)

    # Component 2: Transaction costs
    cost_component = abs(position_change) * TRANSACTION_COST

    # Component 3: Drawdown penalty (quadratic)
    drawdown = (peak_value - portfolio_value) / peak_value
    drawdown_component = DRAWDOWN_PENALTY * (drawdown ** 2)

    # Component 4: Turnover penalty
    turnover_component = TURNOVER_PENALTY * abs(position_change)

    # Final reward
    reward = sharpe_component - cost_component - drawdown_component - turnover_component

    return reward


# =============================================================================
# GAME THEORY CONSIDERATIONS
# =============================================================================

"""
Game Theory in Trading:

1. ADVERSARIAL ENVIRONMENT
   - Other algorithms are watching for patterns
   - Successful strategies attract competition
   - Your orders reveal information

2. MARKET IMPACT
   - Large orders move prices against you
   - Need to model price impact
   - Slice large orders (TWAP/VWAP)

3. INFORMATION LEAKAGE
   - Order flow reveals intentions
   - Use randomization to obscure
   - Vary timing and sizing

4. NASH EQUILIBRIUM
   - In equilibrium, no edge remains
   - Edges are transient
   - Must constantly adapt

5. COUNTER-STRATEGIES
   - Anticipate how others will react
   - Model common algo behaviors
   - Avoid crowded trades

PRACTICAL IMPLICATIONS:
- Don't trade patterns that are too obvious
- Use multiple uncorrelated signals
- Randomize execution
- Monitor for alpha decay
- Expect edges to disappear
"""
```

## Signal Processing Pipeline

```python
def process_market_signal(prices: np.ndarray) -> Signal:
    """
    Multi-scale signal extraction.
    """

    # STEP 1: Denoise with wavelets
    denoised = wavelet_denoise(prices, levels=4)

    # STEP 2: Extract trend (Kalman filter)
    trend = kalman_filter_trend(denoised)

    # STEP 3: Extract momentum (medium-term wavelets)
    momentum = extract_momentum_component(prices, scales=[8, 16, 32])

    # STEP 4: Extract mean-reversion (short-term)
    mean_reversion = extract_mean_reversion_component(prices, scales=[2, 4])

    # STEP 5: Detect regime
    regime = detect_regime(prices)  # trending vs mean-reverting

    # STEP 6: Combine based on regime
    if regime == "trending":
        signal = 0.7 * momentum + 0.3 * trend
    elif regime == "mean_reverting":
        signal = 0.7 * mean_reversion + 0.3 * (-trend)
    else:
        signal = 0.4 * momentum + 0.3 * mean_reversion + 0.3 * trend

    return Signal(direction=np.sign(signal), strength=abs(signal))
```

## Risk Management Flow

```python
def risk_management_flow(order: Order) -> Tuple[bool, str]:
    """
    Multi-layer risk checks.
    """

    # LAYER 1: Order-level checks
    if order.value > MAX_ORDER_VALUE:
        return False, "Order too large"

    if order.value / portfolio_value > MAX_ORDER_PCT:
        return False, "Order too large relative to portfolio"

    # LAYER 2: Position-level checks
    new_position = current_position + order.quantity
    if abs(new_position) * price > MAX_POSITION_VALUE:
        return False, "Position would exceed limit"

    # LAYER 3: Portfolio-level checks
    new_exposure = calculate_exposure_after_order(order)
    if new_exposure > MAX_GROSS_EXPOSURE:
        return False, "Gross exposure would exceed limit"

    # LAYER 4: Loss checks
    if daily_pnl < -MAX_DAILY_LOSS:
        return False, "Daily loss limit exceeded"

    if current_drawdown > MAX_DRAWDOWN:
        return False, "Drawdown limit exceeded"

    # LAYER 5: Rate limits
    if orders_this_minute >= MAX_ORDERS_PER_MINUTE:
        return False, "Order rate limit"

    # All checks passed
    return True, "Approved"
```
