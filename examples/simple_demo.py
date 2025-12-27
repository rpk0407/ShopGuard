#!/usr/bin/env python3
"""
Simple Working Demo - Shows infrastructure components
Run: python examples/simple_demo.py
"""
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from datetime import datetime, timedelta

print("\n" + "="*70)
print("  QUANTITATIVE TRADING INFRASTRUCTURE DEMO")
print("="*70)

# ============================================================
# 1. GARCH VOLATILITY MODEL
# ============================================================
print("\n" + "="*60 + "\n  1. GARCH VOLATILITY MODEL\n" + "="*60)

from core.models.garch import GARCH11

np.random.seed(42)
returns = np.random.normal(0.0005, 0.02, 500)

garch = GARCH11()
result = garch.fit(returns)

print(f"  GARCH(1,1) Estimation:")
print(f"    omega = {result.params.omega:.8f}")
print(f"    alpha = {result.params.alpha:.4f}")
print(f"    beta  = {result.params.beta:.4f}")
print(f"    persistence = {result.params.persistence:.4f}")
print(f"    unconditional vol = {np.sqrt(result.params.unconditional_variance)*100:.2f}%")
print(f"    half-life = {result.params.half_life:.1f} days")

forecast = garch.forecast(horizon=5)
print(f"  5-day volatility forecast: {forecast[-1]*100:.2f}%")

# ============================================================
# 2. SMART ORDER ROUTING
# ============================================================
print("\n" + "="*60 + "\n  2. SMART ORDER ROUTING\n" + "="*60)

from execution.smart_router import SmartOrderRouter, Venue, VenueType, VenueLiquidity, RoutingStrategy

venues = {
    'NYSE': Venue('NYSE', 'NYSE', VenueType.PRIMARY_EXCHANGE, -0.0002, 0.0003, 500, 0.95, 1.0),
    'NASDAQ': Venue('NASDAQ', 'NASDAQ', VenueType.PRIMARY_EXCHANGE, -0.0002, 0.0003, 400, 0.93, 1.2),
    'DARK': Venue('DARK', 'Dark Pool', VenueType.DARK_POOL, 0, 0.0001, 1000, 0.40, 0),
}

router = SmartOrderRouter(venues)
router.update_liquidity('AAPL', 'NYSE', VenueLiquidity('NYSE', 149.95, 5000, 150.00, 4000, datetime.now()))
router.update_liquidity('AAPL', 'NASDAQ', VenueLiquidity('NASDAQ', 149.94, 3000, 150.01, 3500, datetime.now()))
router.update_liquidity('AAPL', 'DARK', VenueLiquidity('DARK', 149.97, 10000, 149.98, 8000, datetime.now()))

decision = router.route_order('AAPL', 'buy', 5000, RoutingStrategy.MINIMIZE_COST)

print(f"  Order: BUY 5,000 AAPL")
print(f"  Strategy: Minimize Cost")
print(f"  Routing:")
for order in decision.orders:
    print(f"    → {order.venue_id}: {order.quantity} shares @ ${order.limit_price:.2f}")
print(f"  Expected Fill: {decision.expected_fill_rate:.0%}")
print(f"  Expected Cost: {decision.expected_cost_bps:.2f} bps")

# ============================================================
# 3. EXECUTION ALGORITHMS
# ============================================================
print("\n" + "="*60 + "\n  3. EXECUTION ALGORITHMS\n" + "="*60)

from execution.algorithms import TWAPExecutor, VWAPExecutor, ImplementationShortfall

start = datetime.now()
end = start + timedelta(hours=2)

# TWAP
twap = TWAPExecutor('AAPL', 'buy', 10000, start, end, num_slices=24)
twap.generate_schedule()
print(f"  TWAP (10,000 shares / 2 hours):")
print(f"    Slices: {len(twap.schedule.times)}")
print(f"    Per slice: ~{sum(twap.schedule.quantities)//len(twap.schedule.quantities)} shares")

# VWAP
vwap = VWAPExecutor('AAPL', 'buy', 10000, start, end)
vwap.generate_schedule()
print(f"\n  VWAP (volume-weighted):")
print(f"    Peak slice: {max(vwap.schedule.quantities)} shares")
print(f"    Min slice: {min(vwap.schedule.quantities)} shares")

# Implementation Shortfall
isf = ImplementationShortfall('AAPL', 'buy', 10000, start, end, decision_price=150.0, risk_aversion=0.5)
isf.generate_schedule()
print(f"\n  Implementation Shortfall (aggressive start):")
print(f"    First 5 slices: {isf.schedule.quantities[:5]}")
print(f"    Last 5 slices: {isf.schedule.quantities[-5:]}")

# ============================================================
# 4. MARKET IMPACT
# ============================================================
print("\n" + "="*60 + "\n  4. MARKET IMPACT ESTIMATION\n" + "="*60)

from execution.market_impact import AlmgrenChriss, ImpactParams

params = ImpactParams(
    temporary_coeff=0.1,
    permanent_coeff=0.1,
    decay_rate=0.5,
    daily_volume=5_000_000,
    volatility=0.25,
    spread=0.01
)

ac = AlmgrenChriss()

# Estimate for different order sizes
for size in [10000, 50000, 100000]:
    cost = ac.estimate_impact(size, 1, 0.5, params)
    pct_adv = size / params.daily_volume * 100
    print(f"  {size:,} shares ({pct_adv:.1f}% ADV):")
    print(f"    Total cost: ${cost.total_cost:,.0f}")

# ============================================================
# 5. PORTFOLIO OPTIMIZATION
# ============================================================
print("\n" + "="*60 + "\n  5. PORTFOLIO OPTIMIZATION\n" + "="*60)

from portfolio.optimization import MeanVarianceOptimizer, RiskParityOptimizer

symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
exp_ret = np.array([0.12, 0.10, 0.08, 0.15, 0.09])

corr = np.array([
    [1.0, 0.5, 0.3, 0.2, 0.4],
    [0.5, 1.0, 0.4, 0.3, 0.5],
    [0.3, 0.4, 1.0, 0.2, 0.3],
    [0.2, 0.3, 0.2, 1.0, 0.4],
    [0.4, 0.5, 0.3, 0.4, 1.0]
])
vols = np.array([0.20, 0.18, 0.12, 0.25, 0.15])
cov = np.outer(vols, vols) * corr

# Mean-Variance
mv = MeanVarianceOptimizer(risk_aversion=1.0)
result = mv.optimize(exp_ret, cov, symbols)
weights = result.weights

print("  Mean-Variance Portfolio:")
for s, w in zip(symbols, weights):
    if w > 0.01:
        print(f"    {s}: {w:.1%}")

print(f"  Expected Return: {result.expected_return:.1%}")
print(f"  Volatility: {result.expected_volatility:.1%}")
print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")

# Risk Parity
rp = RiskParityOptimizer()
rp_result = rp.optimize(cov, symbols)
print("\n  Risk Parity Portfolio:")
for s, w in zip(symbols, rp_result.weights):
    print(f"    {s}: {w:.1%}")

# ============================================================
# 6. MONITORING DASHBOARD
# ============================================================
print("\n" + "="*60 + "\n  6. MONITORING DASHBOARD\n" + "="*60)

from monitoring.dashboard import TradingDashboard

dash = TradingDashboard()
dash.update_pnl(25000, 18000, 7000)
dash.update_position('AAPL', 500, 148.50, 152.00)
dash.update_position('GOOGL', 100, 2750.0, 2820.0)
dash.record_trade('AAPL', 'buy', 100, 151.50, 'ord001')
dash.update_system_metrics(350, 25, 2048, 5.2)

pnl = dash.get_pnl_summary()
pos = dash.get_position_summary()

print(f"  P&L Summary:")
print(f"    Total: ${pnl['total']:,}")
print(f"    Realized: ${pnl['realized']:,}")
print(f"    Unrealized: ${pnl['unrealized']:,}")
print(f"    Peak: ${pnl['peak']:,}")
print(f"\n  Positions: {pos['num_positions']}")
print(f"  Total Exposure: ${pos['total_exposure']:,.0f}")

# ============================================================
# 7. ALERT SYSTEM
# ============================================================
print("\n" + "="*60 + "\n  7. ALERT SYSTEM\n" + "="*60)

from monitoring.alerts import AlertManager, AlertRule, AlertLevel

alerts = AlertManager()

# Add alert rules
current_pnl = -65000
drawdown = 0.08

alerts.add_rule(AlertRule(
    name="pnl_warning",
    condition=lambda: current_pnl < -50000,
    level=AlertLevel.WARNING,
    message_template="P&L below -$50K threshold"
))

alerts.add_rule(AlertRule(
    name="drawdown_warning",
    condition=lambda: drawdown > 0.05,
    level=AlertLevel.WARNING,
    message_template="Drawdown exceeds 5%"
))

fired = alerts.check_rules()
print(f"  Active Rules: {len(alerts.rules)}")
print(f"  Alerts Triggered: {len(fired)}")
for a in fired:
    print(f"    [{a.level.name}] {a.message}")

# ============================================================
# 8. SENTIMENT ANALYSIS
# ============================================================
print("\n" + "="*60 + "\n  8. SENTIMENT ANALYSIS\n" + "="*60)

from alternative_data.sentiment import SentimentAnalyzer, SentimentSource

analyzer = SentimentAnalyzer()

headlines = [
    "Apple reports record quarterly earnings, beats estimates",
    "Tesla shares plunge amid regulatory concerns",
    "Microsoft announces $10B AI investment partnership",
    "Fed signals potential rate cuts in 2024",
]

print("  News Sentiment:")
for headline in headlines:
    result = analyzer.analyze_text(headline, SentimentSource.NEWS)
    icon = "+" if result.score > 0.1 else ("-" if result.score < -0.1 else "=")
    print(f"    [{icon}{result.score:+.2f}] {headline[:50]}...")

# ============================================================
# 9. TRADING ENGINE
# ============================================================
print("\n" + "="*60 + "\n  9. TRADING ENGINE\n" + "="*60)

from api.engine import TradingEngine, EngineConfig
from api.strategy import Strategy, StrategyConfig, Signal

class DemoStrategy(Strategy):
    def on_data(self, context):
        return []

config = EngineConfig(name="DemoEngine", paper_trading=True)
engine = TradingEngine(config)
engine.add_strategy(DemoStrategy(StrategyConfig(name="Demo", symbols=['AAPL', 'GOOGL', 'MSFT'])))
engine._prices = {'AAPL': 150.0, 'GOOGL': 2800.0, 'MSFT': 380.0}
engine._equity = 1_000_000

status = engine.get_status()
print(f"  Engine: {status['name']}")
print(f"  State: {status['state']}")
print(f"  Paper Trading: {status['paper_trading']}")
print(f"  Strategies: {status['num_strategies']}")
print(f"  Equity: ${status['equity']:,}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "="*70)
print("  DEMO COMPLETE - ALL COMPONENTS FUNCTIONAL")
print("="*70)
print("""
  Components Demonstrated:
  1. GARCH Volatility Forecasting
  2. Smart Order Routing (multi-venue)
  3. Execution Algorithms (TWAP, VWAP, IS)
  4. Market Impact Models (Almgren-Chriss)
  5. Portfolio Optimization (Mean-Variance, Risk Parity)
  6. Real-time Monitoring Dashboard
  7. Alert Management System
  8. Sentiment Analysis (NLP)
  9. Trading Engine Framework

  Next Steps:
  - Connect to real market data feeds
  - Implement custom strategies
  - Run backtests with historical data
  - Paper trade before going live

  WARNING: This is research software.
  Past performance does not guarantee future results.
""")
