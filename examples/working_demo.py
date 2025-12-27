#!/usr/bin/env python3
"""
Working Demo - Tests ALL infrastructure components

Run: python examples/working_demo.py
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime, timedelta


def header(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}\n")


def test_garch():
    """Test GARCH volatility models."""
    header("1. GARCH VOLATILITY MODELS")

    from core.models.garch import GARCH11, EGARCH

    # Generate returns
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, 500)

    # GARCH(1,1)
    garch = GARCH11(omega=0.00001, alpha=0.1, beta=0.85)
    variance = garch.filter_variance(returns)
    forecast = garch.forecast_variance(variance[-1], horizon=5)

    print(f"GARCH(1,1) Parameters:")
    print(f"  omega={garch.omega:.6f}, alpha={garch.alpha:.3f}, beta={garch.beta:.3f}")
    print(f"  Current volatility: {np.sqrt(variance[-1])*100:.2f}%")
    print(f"  5-day forecast: {np.sqrt(forecast[-1])*100:.2f}%")

    # EGARCH
    egarch = EGARCH(omega=-0.1, alpha=0.1, gamma=-0.05, beta=0.95)
    print(f"\nEGARCH with leverage effect (gamma={egarch.gamma})")


def test_regime_switching():
    """Test regime switching models."""
    header("2. REGIME SWITCHING")

    from core.models.regime_switching import MarkovRegimeSwitching

    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 300)

    model = MarkovRegimeSwitching(n_regimes=2)
    model.fit(returns)

    print(f"Regime 1 (Low Vol): mean={model.means[0]*100:.3f}%, vol={model.stds[0]*100:.2f}%")
    print(f"Regime 2 (High Vol): mean={model.means[1]*100:.3f}%, vol={model.stds[1]*100:.2f}%")
    print(f"Transition Matrix:")
    print(f"  P(stay in R1) = {model.transition_matrix[0,0]:.2f}")
    print(f"  P(stay in R2) = {model.transition_matrix[1,1]:.2f}")


def test_copulas():
    """Test copula models."""
    header("3. COPULA MODELS")

    from core.models.copulas import GaussianCopula, StudentTCopula

    np.random.seed(42)
    n = 500
    returns1 = np.random.normal(0, 0.02, n)
    returns2 = 0.6 * returns1 + 0.4 * np.random.normal(0, 0.02, n)

    gauss = GaussianCopula()
    gauss.fit(returns1, returns2)
    print(f"Gaussian Copula: rho = {gauss.rho:.4f}")

    t_cop = StudentTCopula()
    t_cop.fit(returns1, returns2)
    print(f"Student-t Copula: rho = {t_cop.rho:.4f}, df = {t_cop.df:.1f}")
    print(f"Lower tail dependence: {t_cop.lower_tail_dependence():.4f}")


def test_orderbook():
    """Test order book analysis."""
    header("4. ORDER BOOK ANALYSIS")

    from hft.orderbook import OrderBookAnalyzer, OrderBookState, OrderBookLevel

    # Create order book state
    bids = [
        OrderBookLevel(149.95, 1000),
        OrderBookLevel(149.90, 2000),
        OrderBookLevel(149.85, 1500),
    ]
    asks = [
        OrderBookLevel(150.00, 800),
        OrderBookLevel(150.05, 1200),
        OrderBookLevel(150.10, 2000),
    ]

    book = OrderBookState(
        symbol="AAPL",
        timestamp=datetime.now(),
        bids=bids,
        asks=asks
    )

    print(f"Symbol: {book.symbol}")
    print(f"Best Bid: ${book.best_bid:.2f} x {book.best_bid_size}")
    print(f"Best Ask: ${book.best_ask:.2f} x {book.best_ask_size}")
    print(f"Spread: ${book.spread:.2f} ({book.spread_bps:.1f} bps)")
    print(f"Mid Price: ${book.mid_price:.2f}")

    analyzer = OrderBookAnalyzer(depth=5)
    imbalance = analyzer.calculate_imbalance(book)
    print(f"Order Imbalance: {imbalance:.2%} (positive=buy pressure)")


def test_market_making():
    """Test market making."""
    header("5. MARKET MAKING (Avellaneda-Stoikov)")

    from hft.market_making import AvellanedaStoikov

    mm = AvellanedaStoikov(
        gamma=0.1,
        sigma=0.02,
        k=1.5,
        dt=1/252/6.5/60
    )

    mid = 150.0
    inventory = 100

    bid_offset, ask_offset = mm.optimal_quotes(mid, inventory, 0.5)

    print(f"Mid Price: ${mid:.2f}, Inventory: {inventory} shares")
    print(f"Time remaining: 50%")
    print(f"Optimal Bid: ${mid - bid_offset:.3f} (offset: ${bid_offset:.4f})")
    print(f"Optimal Ask: ${mid + ask_offset:.3f} (offset: ${ask_offset:.4f})")
    print(f"Spread: ${bid_offset + ask_offset:.4f}")


def test_portfolio():
    """Test portfolio optimization."""
    header("6. PORTFOLIO OPTIMIZATION")

    from portfolio.optimization import MeanVarianceOptimizer, RiskParityOptimizer, BlackLittermanModel

    # 5 assets
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15, 0.09])

    # Covariance
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
    mv = MeanVarianceOptimizer(expected_returns, cov, symbols)
    min_var = mv.minimum_variance()

    print("Mean-Variance (Minimum Variance):")
    for sym, w in zip(symbols, min_var):
        if w > 0.01:
            print(f"  {sym}: {w:.1%}")

    vol = np.sqrt(min_var @ cov @ min_var)
    ret = min_var @ expected_returns
    print(f"  Return: {ret:.1%}, Vol: {vol:.1%}")

    # Risk Parity
    rp = RiskParityOptimizer(cov, symbols)
    rp_weights = rp.optimize()

    print("\nRisk Parity:")
    for sym, w in zip(symbols, rp_weights):
        print(f"  {sym}: {w:.1%}")


def test_execution():
    """Test execution algorithms."""
    header("7. EXECUTION ALGORITHMS")

    from execution.smart_router import SmartOrderRouter, Venue, VenueType, VenueLiquidity, RoutingStrategy
    from execution.algorithms import TWAPExecutor, VWAPExecutor
    from execution.market_impact import AlmgrenChriss, ImpactParams

    # Smart Order Router
    venues = {
        'NYSE': Venue('NYSE', 'NYSE', VenueType.PRIMARY_EXCHANGE,
                     -0.0002, 0.0003, 500, 0.95, 1.0),
        'DARK': Venue('DARK', 'Dark Pool', VenueType.DARK_POOL,
                     0, 0.0001, 1000, 0.40, 0),
    }

    router = SmartOrderRouter(venues)
    router.update_liquidity('AAPL', 'NYSE',
        VenueLiquidity('NYSE', 149.95, 5000, 150.00, 4000, datetime.now()))
    router.update_liquidity('AAPL', 'DARK',
        VenueLiquidity('DARK', 149.97, 10000, 149.98, 8000, datetime.now()))

    decision = router.route_order('AAPL', 'buy', 5000, RoutingStrategy.MINIMIZE_COST)

    print("Smart Order Routing:")
    print(f"  Order: BUY 5000 AAPL")
    for order in decision.orders:
        print(f"  → {order.venue_id}: {order.quantity} @ ${order.limit_price:.2f}")
    print(f"  Cost: {decision.expected_cost_bps:.2f} bps")

    # TWAP/VWAP
    start = datetime.now()
    end = start + timedelta(hours=1)

    twap = TWAPExecutor('AAPL', 'buy', 10000, start, end, num_slices=12)
    twap.generate_schedule()
    print(f"\nTWAP: 10K shares in 12 slices of ~{10000//12} each")

    # Market Impact
    params = ImpactParams(0.1, 0.1, 0.5, 5_000_000, 0.25, 0.01)
    ac = AlmgrenChriss()
    cost = ac.estimate_impact(50000, 1, 0.5, params)

    print(f"\nMarket Impact (50K shares over half day):")
    print(f"  Temporary: ${cost.temporary_impact_cost:,.0f}")
    print(f"  Permanent: ${cost.permanent_impact_cost:,.0f}")
    print(f"  Total: ${cost.total_cost:,.0f}")


def test_monitoring():
    """Test monitoring system."""
    header("8. MONITORING & ALERTS")

    from monitoring.dashboard import TradingDashboard
    from monitoring.alerts import AlertManager, AlertRule, AlertLevel
    from monitoring.health import SystemHealth, HealthCheck

    # Dashboard
    dash = TradingDashboard()
    dash.update_pnl(15000, 12000, 3000)
    dash.update_position('AAPL', 500, 148.50, 150.25)
    dash.record_trade('AAPL', 'buy', 100, 150.00, 'order_001')

    pnl = dash.get_pnl_summary()
    print("Trading Dashboard:")
    print(f"  P&L: ${pnl['total']:,.0f}")
    print(f"  Realized: ${pnl['realized']:,.0f}")
    print(f"  Unrealized: ${pnl['unrealized']:,.0f}")

    pos = dash.get_position_summary()
    print(f"  Positions: {pos['num_positions']}")
    print(f"  Exposure: ${pos['total_exposure']:,.0f}")

    # Alerts
    pnl_value = -75000
    alerts = AlertManager()
    alerts.add_rule(AlertRule(
        name="loss_warning",
        condition=lambda: pnl_value < -50000,
        level=AlertLevel.WARNING,
        message_template="Loss exceeds threshold"
    ))

    fired = alerts.check_rules()
    print(f"\nAlerts: {len(fired)} triggered")
    for a in fired:
        print(f"  [{a.level.name}] {a.message}")

    # Health
    health = SystemHealth()
    health.register_check('core', HealthCheck('database', lambda: True, critical=True))
    health.register_check('core', HealthCheck('exchange', lambda: True, critical=True))

    results = health.run_checks()
    print(f"\nSystem Health: {health.get_status().value.upper()}")


def test_trading_engine():
    """Test trading engine."""
    header("9. TRADING ENGINE")

    from api.engine import TradingEngine, EngineConfig
    from api.strategy import Strategy, StrategyConfig, Signal, StrategyContext

    class TestStrategy(Strategy):
        def on_data(self, context):
            return []  # Simple placeholder

    config = EngineConfig(
        name="TestEngine",
        enable_trading=True,
        paper_trading=True
    )

    engine = TradingEngine(config)
    engine.add_strategy(TestStrategy(StrategyConfig(
        name="Test",
        symbols=['AAPL', 'GOOGL']
    )))

    engine._prices = {'AAPL': 150.0, 'GOOGL': 2800.0}
    engine._equity = 1_000_000

    status = engine.get_status()
    print("Trading Engine Status:")
    print(f"  Name: {status['name']}")
    print(f"  State: {status['state']}")
    print(f"  Paper Trading: {status['paper_trading']}")
    print(f"  Equity: ${status['equity']:,.0f}")
    print(f"  Strategies: {status['num_strategies']}")


def test_sentiment():
    """Test sentiment analysis."""
    header("10. SENTIMENT ANALYSIS")

    from alternative_data.sentiment import SentimentAnalyzer, SentimentSource

    analyzer = SentimentAnalyzer()

    texts = [
        "Apple beats earnings expectations, stock surges 5%",
        "Tesla faces regulatory investigation, shares tumble",
        "Microsoft announces major AI partnership"
    ]

    print("Sentiment Analysis:")
    for text in texts:
        result = analyzer.analyze_text(text, SentimentSource.NEWS)
        sentiment = "+" if result.score > 0.1 else ("-" if result.score < -0.1 else "=")
        print(f"  [{sentiment}] {result.score:+.2f}: \"{text[:40]}...\"")


def main():
    print("\n" + "=" * 60)
    print("  QUANTITATIVE TRADING INFRASTRUCTURE - FULL TEST")
    print("=" * 60)

    tests = [
        ("GARCH Models", test_garch),
        ("Regime Switching", test_regime_switching),
        ("Copulas", test_copulas),
        ("Order Book", test_orderbook),
        ("Market Making", test_market_making),
        ("Portfolio Optimization", test_portfolio),
        ("Execution", test_execution),
        ("Monitoring", test_monitoring),
        ("Trading Engine", test_trading_engine),
        ("Sentiment", test_sentiment),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
