#!/usr/bin/env python3
"""
Full System Demonstration

This script demonstrates all major components of the trading infrastructure:
1. Mathematical Models (GARCH, Regime Switching, Copulas)
2. Signal Processing (Fourier, Wavelets, Kalman)
3. AI/ML Models (LSTM, Transformers, RL)
4. HFT Components (Order Book, Market Making)
5. Portfolio Optimization (Mean-Variance, Risk Parity, Black-Litterman)
6. Execution (Smart Order Router, TWAP/VWAP)
7. Backtesting Engine
8. Monitoring & Alerts
9. Full Trading Engine

Run with: python examples/demo_full_system.py
"""

import numpy as np
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime, timedelta


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_mathematical_models():
    """Demonstrate mathematical models."""
    print_header("1. MATHEMATICAL MODELS")

    # Generate sample price data
    np.random.seed(42)
    n = 500
    returns = np.random.normal(0.0005, 0.02, n)
    prices = 100 * np.exp(np.cumsum(returns))

    # --- GARCH Models ---
    print("📊 GARCH Volatility Models")
    print("-" * 40)

    from core.models.garch import GARCH, EGARCH, ComponentGARCH

    # Fit GARCH(1,1)
    garch = GARCH(p=1, q=1)
    garch.fit(returns)
    vol_forecast = garch.forecast(horizon=5)
    print(f"  GARCH(1,1) Parameters: ω={garch.omega:.6f}, α={garch.alpha[0]:.4f}, β={garch.beta[0]:.4f}")
    print(f"  5-day volatility forecast: {vol_forecast[-1]*100:.2f}%")

    # Fit EGARCH
    egarch = EGARCH(p=1, q=1)
    egarch.fit(returns)
    print(f"  EGARCH leverage effect (γ): {egarch.gamma:.4f}")

    # --- Regime Switching ---
    print("\n🔄 Regime Switching Model")
    print("-" * 40)

    from core.models.regime_switching import MarkovRegimeSwitching

    regime_model = MarkovRegimeSwitching(n_regimes=2)
    regime_model.fit(returns)
    current_probs = regime_model.get_regime_probabilities(returns)
    print(f"  Regime 1 (Low Vol) mean: {regime_model.means[0]*100:.3f}%")
    print(f"  Regime 2 (High Vol) mean: {regime_model.means[1]*100:.3f}%")
    print(f"  Current regime probabilities: {current_probs}")

    # --- Copulas ---
    print("\n🔗 Copula Dependency Models")
    print("-" * 40)

    from core.models.copulas import GaussianCopula, StudentTCopula

    # Generate correlated returns
    returns2 = 0.6 * returns + 0.4 * np.random.normal(0, 0.02, n)

    gaussian_cop = GaussianCopula()
    gaussian_cop.fit(returns, returns2)
    print(f"  Gaussian Copula correlation: {gaussian_cop.rho:.4f}")

    t_cop = StudentTCopula()
    t_cop.fit(returns, returns2)
    print(f"  Student-t Copula correlation: {t_cop.rho:.4f}, df: {t_cop.df:.1f}")
    print(f"  Tail dependence (lower): {t_cop.lower_tail_dependence():.4f}")


def demo_signal_processing():
    """Demonstrate signal processing."""
    print_header("2. SIGNAL PROCESSING")

    np.random.seed(42)
    n = 256
    t = np.linspace(0, 1, n)
    # Signal with trend + cycles + noise
    signal = 0.5 * t + 0.3 * np.sin(2 * np.pi * 10 * t) + 0.1 * np.sin(2 * np.pi * 30 * t) + 0.05 * np.random.randn(n)

    # --- Fourier Analysis ---
    print("📈 Fourier Transform")
    print("-" * 40)

    from core.signals.fourier import FourierAnalyzer

    fourier = FourierAnalyzer(sample_rate=n)
    spectrum = fourier.compute_spectrum(signal)
    dominant = fourier.find_dominant_frequencies(signal, n_frequencies=3)
    print(f"  Dominant frequencies: {[f'{f:.1f} Hz' for f in dominant]}")

    # --- Wavelet Analysis ---
    print("\n🌊 Wavelet Transform")
    print("-" * 40)

    from core.signals.wavelets import WaveletAnalyzer

    wavelet = WaveletAnalyzer(wavelet='db4')
    coeffs = wavelet.decompose(signal, level=3)
    print(f"  Decomposition levels: {len(coeffs)}")
    denoised = wavelet.denoise(signal)
    noise_reduction = 1 - np.std(denoised - signal) / np.std(signal)
    print(f"  Noise reduction: {noise_reduction*100:.1f}%")

    # --- Kalman Filter ---
    print("\n🎯 Kalman Filter")
    print("-" * 40)

    from core.signals.kalman import KalmanFilter

    kf = KalmanFilter(
        transition_matrix=np.array([[1, 1], [0, 1]]),
        observation_matrix=np.array([[1, 0]]),
        process_noise=np.eye(2) * 0.01,
        observation_noise=np.array([[0.1]])
    )

    filtered_states = []
    state = np.array([signal[0], 0])
    cov = np.eye(2)

    for obs in signal[:50]:
        state, cov = kf.update(state, cov, np.array([obs]))
        state, cov = kf.predict(state, cov)
        filtered_states.append(state[0])

    print(f"  Filtered {len(filtered_states)} observations")
    print(f"  Final state estimate: {state[0]:.4f}, velocity: {state[1]:.4f}")


def demo_ai_models():
    """Demonstrate AI/ML models."""
    print_header("3. AI/ML MODELS")

    # --- Neural Networks ---
    print("🧠 Neural Network Architectures")
    print("-" * 40)

    from ai.networks.temporal import LSTMEncoder, TransformerEncoder

    # LSTM
    lstm = LSTMEncoder(input_size=5, hidden_size=64, num_layers=2)
    print(f"  LSTM Encoder: input=5, hidden=64, layers=2")
    print(f"  Parameters: ~{sum(p.numel() for p in lstm.parameters()):,}")

    # Transformer
    transformer = TransformerEncoder(d_model=64, nhead=4, num_layers=2)
    print(f"  Transformer: d_model=64, heads=4, layers=2")
    print(f"  Parameters: ~{sum(p.numel() for p in transformer.parameters()):,}")

    # --- Ensemble Methods ---
    print("\n🎭 Ensemble Methods")
    print("-" * 40)

    from ai.networks.ensemble import MixtureOfExperts, StackingEnsemble

    moe = MixtureOfExperts(input_dim=10, output_dim=1, num_experts=4, hidden_dim=32)
    print(f"  Mixture of Experts: 4 experts, hidden=32")

    # --- RL Agent ---
    print("\n🎮 Reinforcement Learning")
    print("-" * 40)

    from ai.agents.ppo_agent import PPOAgent

    ppo = PPOAgent(
        state_dim=20,
        action_dim=3,
        hidden_dim=64
    )
    print(f"  PPO Agent: state=20, actions=3")
    print(f"  Policy network parameters: ~{sum(p.numel() for p in ppo.actor.parameters()):,}")


def demo_hft_components():
    """Demonstrate HFT components."""
    print_header("4. HIGH-FREQUENCY TRADING")

    # --- Order Book ---
    print("📚 Order Book Analysis")
    print("-" * 40)

    from hft.orderbook import OrderBook, OrderBookAnalyzer

    book = OrderBook("AAPL")
    # Add some orders
    book.add_order('b1', 'bid', 149.95, 1000)
    book.add_order('b2', 'bid', 149.90, 2000)
    book.add_order('b3', 'bid', 149.85, 1500)
    book.add_order('a1', 'ask', 150.00, 800)
    book.add_order('a2', 'ask', 150.05, 1200)
    book.add_order('a3', 'ask', 150.10, 2000)

    print(f"  Best Bid: ${book.best_bid:.2f} x {book.best_bid_size}")
    print(f"  Best Ask: ${book.best_ask:.2f} x {book.best_ask_size}")
    print(f"  Spread: ${book.spread:.2f} ({book.spread_bps:.1f} bps)")
    print(f"  Mid Price: ${book.mid_price:.2f}")

    analyzer = OrderBookAnalyzer()
    imbalance = analyzer.calculate_imbalance(book)
    print(f"  Order Imbalance: {imbalance:.2%}")

    # --- Market Making ---
    print("\n💹 Market Making (Avellaneda-Stoikov)")
    print("-" * 40)

    from hft.market_making import AvellanedaStoikov

    mm = AvellanedaStoikov(
        gamma=0.1,      # Risk aversion
        sigma=0.02,     # Volatility
        k=1.5,          # Order arrival intensity
        dt=1/252/6.5/60 # 1 minute
    )

    bid_offset, ask_offset = mm.optimal_quotes(
        mid_price=150.0,
        inventory=100,
        time_remaining=0.5
    )

    print(f"  Mid Price: $150.00, Inventory: 100 shares")
    print(f"  Optimal Bid: ${150.0 - bid_offset:.2f} (offset: ${bid_offset:.3f})")
    print(f"  Optimal Ask: ${150.0 + ask_offset:.2f} (offset: ${ask_offset:.3f})")

    # --- Latency ---
    print("\n⚡ Latency Monitoring")
    print("-" * 40)

    from hft.latency import LatencyMonitor

    monitor = LatencyMonitor()
    # Simulate some latencies
    for _ in range(100):
        monitor.record('order_submission', np.random.exponential(500))  # microseconds
        monitor.record('market_data', np.random.exponential(100))

    order_stats = monitor.get_statistics('order_submission')
    print(f"  Order Submission: mean={order_stats['mean']:.0f}μs, p99={order_stats['p99']:.0f}μs")

    data_stats = monitor.get_statistics('market_data')
    print(f"  Market Data: mean={data_stats['mean']:.0f}μs, p99={data_stats['p99']:.0f}μs")


def demo_portfolio_optimization():
    """Demonstrate portfolio optimization."""
    print_header("5. PORTFOLIO OPTIMIZATION")

    np.random.seed(42)

    # Generate sample data for 5 assets
    n_assets = 5
    n_days = 252

    # Expected returns and covariance
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15, 0.09])

    # Correlation matrix
    corr = np.array([
        [1.0, 0.5, 0.3, 0.2, 0.4],
        [0.5, 1.0, 0.4, 0.3, 0.5],
        [0.3, 0.4, 1.0, 0.2, 0.3],
        [0.2, 0.3, 0.2, 1.0, 0.4],
        [0.4, 0.5, 0.3, 0.4, 1.0]
    ])
    vols = np.array([0.20, 0.18, 0.12, 0.25, 0.15])
    cov = np.outer(vols, vols) * corr

    symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']

    # --- Mean-Variance ---
    print("📊 Mean-Variance Optimization")
    print("-" * 40)

    from portfolio.optimization import MeanVarianceOptimizer

    mv = MeanVarianceOptimizer(expected_returns, cov, symbols)

    # Minimum variance portfolio
    min_var = mv.minimum_variance()
    print(f"  Minimum Variance Portfolio:")
    for sym, w in zip(symbols, min_var):
        if w > 0.01:
            print(f"    {sym}: {w:.1%}")
    print(f"    Expected Return: {np.dot(min_var, expected_returns):.1%}")
    print(f"    Volatility: {np.sqrt(min_var @ cov @ min_var):.1%}")

    # Maximum Sharpe
    max_sharpe = mv.maximum_sharpe(risk_free_rate=0.03)
    print(f"\n  Maximum Sharpe Portfolio:")
    for sym, w in zip(symbols, max_sharpe):
        if w > 0.01:
            print(f"    {sym}: {w:.1%}")
    ret = np.dot(max_sharpe, expected_returns)
    vol = np.sqrt(max_sharpe @ cov @ max_sharpe)
    print(f"    Expected Return: {ret:.1%}")
    print(f"    Volatility: {vol:.1%}")
    print(f"    Sharpe Ratio: {(ret - 0.03) / vol:.2f}")

    # --- Risk Parity ---
    print("\n⚖️ Risk Parity")
    print("-" * 40)

    from portfolio.optimization import RiskParityOptimizer

    rp = RiskParityOptimizer(cov, symbols)
    rp_weights = rp.optimize()

    print(f"  Risk Parity Weights:")
    for sym, w in zip(symbols, rp_weights):
        print(f"    {sym}: {w:.1%}")

    # --- Black-Litterman ---
    print("\n🔮 Black-Litterman Model")
    print("-" * 40)

    from portfolio.optimization import BlackLittermanModel

    market_weights = np.array([0.25, 0.20, 0.20, 0.15, 0.20])

    bl = BlackLittermanModel(cov, market_weights, risk_aversion=2.5)

    # Add views
    bl.add_absolute_view(0, 0.15, 0.02)  # AAPL will return 15%
    bl.add_relative_view(3, 1, 0.05, 0.02)  # TSLA will outperform GOOGL by 5%

    bl_returns, bl_cov = bl.posterior()
    bl_weights = bl.optimal_weights()

    print(f"  Views incorporated:")
    print(f"    - AAPL absolute return: 15%")
    print(f"    - TSLA outperforms GOOGL by 5%")
    print(f"\n  Black-Litterman Weights:")
    for sym, w in zip(symbols, bl_weights):
        print(f"    {sym}: {w:.1%}")


def demo_execution():
    """Demonstrate execution algorithms."""
    print_header("6. EXECUTION ALGORITHMS")

    # --- Smart Order Router ---
    print("🛣️ Smart Order Router")
    print("-" * 40)

    from execution.smart_router import SmartOrderRouter, Venue, VenueType, VenueLiquidity

    # Create venues
    venues = {
        'NYSE': Venue('NYSE', 'New York Stock Exchange', VenueType.PRIMARY_EXCHANGE,
                     maker_fee=-0.0002, taker_fee=0.0003, latency_us=500, fill_rate=0.95, avg_spread=1.0),
        'NASDAQ': Venue('NASDAQ', 'NASDAQ', VenueType.PRIMARY_EXCHANGE,
                       maker_fee=-0.0002, taker_fee=0.0003, latency_us=400, fill_rate=0.93, avg_spread=1.2),
        'DARKPOOL': Venue('DARKPOOL', 'Dark Pool', VenueType.DARK_POOL,
                         maker_fee=0, taker_fee=0.0001, latency_us=1000, fill_rate=0.40, avg_spread=0),
    }

    router = SmartOrderRouter(venues)

    # Add liquidity
    router.update_liquidity('AAPL', 'NYSE', VenueLiquidity('NYSE', 149.95, 5000, 150.00, 4000, datetime.now()))
    router.update_liquidity('AAPL', 'NASDAQ', VenueLiquidity('NASDAQ', 149.94, 3000, 150.01, 3500, datetime.now()))
    router.update_liquidity('AAPL', 'DARKPOOL', VenueLiquidity('DARKPOOL', 149.97, 10000, 149.98, 8000, datetime.now()))

    # Route order
    from execution.smart_router import RoutingStrategy
    decision = router.route_order('AAPL', 'buy', 5000, RoutingStrategy.MINIMIZE_COST)

    print(f"  Order: BUY 5000 AAPL")
    print(f"  Strategy: Minimize Cost")
    print(f"  Routing Decision:")
    for order in decision.orders:
        print(f"    → {order.venue_id}: {order.quantity} shares @ ${order.limit_price:.2f}")
    print(f"  Expected Fill Rate: {decision.expected_fill_rate:.1%}")
    print(f"  Expected Cost: {decision.expected_cost_bps:.2f} bps")

    # --- Execution Algorithms ---
    print("\n📈 Execution Algorithms")
    print("-" * 40)

    from execution.algorithms import TWAPExecutor, VWAPExecutor, ImplementationShortfall

    start = datetime.now()
    end = start + timedelta(hours=1)

    # TWAP
    twap = TWAPExecutor('AAPL', 'buy', 10000, start, end, num_slices=12)
    twap.generate_schedule()
    print(f"  TWAP: 10,000 shares over 1 hour")
    print(f"    Slices: {len(twap.schedule.times)}")
    print(f"    Avg slice size: {sum(twap.schedule.quantities)//len(twap.schedule.quantities)}")

    # VWAP
    vwap = VWAPExecutor('AAPL', 'buy', 10000, start, end)
    vwap.generate_schedule()
    print(f"  VWAP: Following volume profile")
    print(f"    Peak slice: {max(vwap.schedule.quantities)}")
    print(f"    Min slice: {min(vwap.schedule.quantities)}")

    # Implementation Shortfall
    isf = ImplementationShortfall('AAPL', 'buy', 10000, start, end, decision_price=150.0)
    isf.generate_schedule()
    print(f"  Implementation Shortfall: Aggressive start")
    print(f"    First 3 slices: {isf.schedule.quantities[:3]}")
    print(f"    Last 3 slices: {isf.schedule.quantities[-3:]}")

    # --- Market Impact ---
    print("\n💥 Market Impact Models")
    print("-" * 40)

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
    cost = ac.estimate_impact(50000, 1, 0.5, params)  # 50K shares over half day

    print(f"  Order: 50,000 shares (1% of ADV)")
    print(f"  Execution: Half trading day")
    print(f"  Estimated Costs:")
    print(f"    Temporary Impact: ${cost.temporary_impact_cost:,.0f}")
    print(f"    Permanent Impact: ${cost.permanent_impact_cost:,.0f}")
    print(f"    Spread Cost: ${cost.spread_cost:,.0f}")
    print(f"    Total: ${cost.total_cost:,.0f}")


def demo_backtesting():
    """Demonstrate backtesting engine."""
    print_header("7. BACKTESTING ENGINE")

    from research.backtesting.engine import BacktestEngine, BacktestConfig

    # Generate sample data
    np.random.seed(42)
    n_days = 252
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(n_days)]

    prices = {'AAPL': 150 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, n_days)))}
    volumes = {'AAPL': np.random.randint(1000000, 5000000, n_days)}

    config = BacktestConfig(
        start_date=dates[0],
        end_date=dates[-1],
        initial_capital=1_000_000,
        commission_rate=0.001,
        slippage_rate=0.0005
    )

    engine = BacktestEngine(config)
    engine.load_data(dates, prices, volumes)

    # Simple momentum strategy
    def momentum_strategy(engine, date_idx):
        if date_idx < 20:
            return {}

        prices_arr = np.array([engine.prices['AAPL'][i] for i in range(date_idx-20, date_idx)])
        returns = (prices_arr[-1] - prices_arr[0]) / prices_arr[0]

        current_pos = engine.positions.get('AAPL', 0)

        if returns > 0.05 and current_pos == 0:
            # Buy signal
            price = engine.prices['AAPL'][date_idx]
            shares = int(engine.cash * 0.5 / price)
            return {'AAPL': shares}
        elif returns < -0.03 and current_pos > 0:
            # Sell signal
            return {'AAPL': -current_pos}

        return {}

    # Run backtest
    results = engine.run(momentum_strategy)

    print("📊 Backtest Results")
    print("-" * 40)
    print(f"  Period: {config.start_date.date()} to {config.end_date.date()}")
    print(f"  Initial Capital: ${config.initial_capital:,.0f}")
    print(f"  Final Equity: ${results['final_equity']:,.0f}")
    print(f"  Total Return: {results['total_return']:.1%}")
    print(f"  Annualized Return: {results['annualized_return']:.1%}")
    print(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown: {results['max_drawdown']:.1%}")
    print(f"  Win Rate: {results['win_rate']:.1%}")
    print(f"  Total Trades: {results['total_trades']}")

    # Walk-Forward Optimization
    print("\n🔄 Walk-Forward Optimization")
    print("-" * 40)

    from research.backtesting.engine import WalkForwardOptimizer

    wfo = WalkForwardOptimizer(
        n_splits=5,
        train_ratio=0.7
    )

    print(f"  Splits: {wfo.n_splits}")
    print(f"  Train/Test Ratio: {wfo.train_ratio:.0%}/{1-wfo.train_ratio:.0%}")
    print(f"  Method: Rolling window with purging")


def demo_monitoring():
    """Demonstrate monitoring and alerts."""
    print_header("8. MONITORING & ALERTS")

    # --- Dashboard ---
    print("📊 Trading Dashboard")
    print("-" * 40)

    from monitoring.dashboard import TradingDashboard

    dashboard = TradingDashboard()

    # Simulate some updates
    dashboard.update_pnl(15000, 12000, 3000)
    dashboard.update_position('AAPL', 500, 148.50, 150.25)
    dashboard.update_position('GOOGL', 100, 2750.00, 2780.00)
    dashboard.record_trade('AAPL', 'buy', 100, 150.00, 'order_001')
    dashboard.update_risk_metrics(var=25000, cvar=35000, beta=1.1, correlation=0.75)
    dashboard.update_system_metrics(latency_us=450, cpu_percent=35, memory_mb=2048, order_rate=5.2)

    # Get summary
    pnl = dashboard.get_pnl_summary()
    print(f"  P&L: ${pnl['total']:,.0f} (Realized: ${pnl['realized']:,.0f}, Unrealized: ${pnl['unrealized']:,.0f})")
    print(f"  Drawdown: {pnl['drawdown']:.2%}")

    pos = dashboard.get_position_summary()
    print(f"  Positions: {pos['num_positions']}, Exposure: ${pos['total_exposure']:,.0f}")

    # --- Alerts ---
    print("\n🚨 Alert System")
    print("-" * 40)

    from monitoring.alerts import AlertManager, AlertRule, AlertLevel

    alert_manager = AlertManager()

    # Add rules
    pnl_value = -75000  # Simulated loss

    alert_manager.add_rule(AlertRule(
        name="large_loss",
        condition=lambda: pnl_value < -50000,
        level=AlertLevel.WARNING,
        message_template="P&L below threshold: ${pnl:,.0f}",
        metadata_fn=lambda: {'pnl': pnl_value}
    ))

    alert_manager.add_rule(AlertRule(
        name="critical_loss",
        condition=lambda: pnl_value < -100000,
        level=AlertLevel.CRITICAL,
        message_template="CRITICAL: P&L at ${pnl:,.0f}"
    ))

    # Check rules
    alerts = alert_manager.check_rules()
    print(f"  Active Rules: {len(alert_manager.rules)}")
    print(f"  Alerts Fired: {len(alerts)}")
    for alert in alerts:
        print(f"    [{alert.level.name}] {alert.message}")

    # --- Health Check ---
    print("\n💚 System Health")
    print("-" * 40)

    from monitoring.health import SystemHealth, HealthCheck

    health = SystemHealth()

    health.register_check('trading', HealthCheck(
        name='database',
        check_fn=lambda: True,
        critical=True,
        description='Database connectivity'
    ))

    health.register_check('trading', HealthCheck(
        name='exchange',
        check_fn=lambda: True,
        critical=True,
        description='Exchange connectivity'
    ))

    health.register_check('trading', HealthCheck(
        name='risk_engine',
        check_fn=lambda: True,
        critical=True,
        description='Risk engine status'
    ))

    results = health.run_checks()
    print(f"  Overall Status: {health.get_status().value.upper()}")
    for comp, result in results.items():
        print(f"  {comp}: {result.status.value}")
        for check in result.checks:
            status_icon = '✓' if check.status.value == 'healthy' else '✗'
            print(f"    {status_icon} {check.name}: {check.message} ({check.latency_ms:.1f}ms)")


def demo_trading_engine():
    """Demonstrate the full trading engine."""
    print_header("9. TRADING ENGINE")

    from api.engine import TradingEngine, EngineConfig
    from api.strategy import Strategy, StrategyConfig, StrategyContext, Signal

    # Create a simple strategy
    class SimpleStrategy(Strategy):
        def on_initialize(self, context):
            self.threshold = self.get_parameter('threshold', 0.02)
            self.last_price = {}

        def on_data(self, context: StrategyContext):
            signals = []
            for symbol in self.symbols:
                price = context.get_price(symbol)
                if price is None:
                    continue

                if symbol in self.last_price:
                    ret = (price - self.last_price[symbol]) / self.last_price[symbol]
                    if abs(ret) > self.threshold:
                        signals.append(Signal(
                            symbol=symbol,
                            direction=1.0 if ret > 0 else -1.0,
                            strength=min(1.0, abs(ret) / self.threshold),
                            confidence=0.7
                        ))

                self.last_price[symbol] = price

            return signals

    # Configure engine
    config = EngineConfig(
        name="DemoEngine",
        tick_interval_ms=1000,
        enable_trading=True,
        paper_trading=True
    )

    engine = TradingEngine(config)

    # Add strategy
    strategy = SimpleStrategy(StrategyConfig(
        name="MomentumDemo",
        symbols=['AAPL', 'GOOGL', 'MSFT'],
        parameters={'threshold': 0.01}
    ))
    engine.add_strategy(strategy)

    # Simulate some price updates
    engine._prices = {'AAPL': 150.0, 'GOOGL': 2800.0, 'MSFT': 380.0}
    engine._equity = 1_000_000

    print("🚀 Trading Engine Status")
    print("-" * 40)

    status = engine.get_status()
    print(f"  Name: {status['name']}")
    print(f"  State: {status['state']}")
    print(f"  Trading Enabled: {status['trading_enabled']}")
    print(f"  Paper Trading: {status['paper_trading']}")
    print(f"  Equity: ${status['equity']:,.0f}")
    print(f"  Strategies: {status['num_strategies']}")

    print("\n📋 Engine Components")
    print("-" * 40)
    print(f"  Event Bus: Configured (async mode)")
    print(f"  Signal Generator: {len(engine.signal_generator.strategies)} strategies")
    print(f"  Symbols: {strategy.symbols}")

    print("\n⚙️ Configuration")
    print("-" * 40)
    print(f"  Tick Interval: {config.tick_interval_ms}ms")
    print(f"  Max Positions: {config.max_positions}")
    print(f"  Max Order Rate: {config.max_order_rate}/sec")


def demo_alternative_data():
    """Demonstrate alternative data processing."""
    print_header("10. ALTERNATIVE DATA")

    # --- Sentiment Analysis ---
    print("💬 Sentiment Analysis")
    print("-" * 40)

    from alternative_data.sentiment import SentimentAnalyzer, SentimentSource

    analyzer = SentimentAnalyzer()

    # Analyze some sample texts
    texts = [
        ("Apple beats earnings expectations, stock surges 5%", "positive"),
        ("Tesla faces regulatory investigation, shares tumble", "negative"),
        ("Microsoft announces partnership with OpenAI", "positive"),
        ("Market volatility increases amid economic uncertainty", "neutral"),
    ]

    for text, expected in texts:
        result = analyzer.analyze_text(text, SentimentSource.NEWS)
        sentiment = "positive" if result.score > 0.1 else ("negative" if result.score < -0.1 else "neutral")
        print(f"  \"{text[:50]}...\"")
        print(f"    Score: {result.score:+.2f}, Magnitude: {result.magnitude:.2f}, Detected: {sentiment}")

    # --- NLP ---
    print("\n📝 Financial NLP")
    print("-" * 40)

    from alternative_data.nlp import EntityExtractor, EventDetector

    extractor = EntityExtractor()
    detector = EventDetector()

    text = "Apple Inc. (AAPL) reported Q4 earnings of $1.29 per share, beating estimates by 5%. CEO Tim Cook announced a $100 billion buyback program."

    entities = extractor.extract_entities(text)
    events = detector.detect_events(text)

    print(f"  Sample Text: \"{text[:60]}...\"")
    print(f"\n  Entities Found:")
    for entity in entities[:5]:
        print(f"    {entity.entity_type}: {entity.text}")

    print(f"\n  Events Detected:")
    for event in events:
        print(f"    {event.event_type.value}: {event.description}")

    # --- Macro Indicators ---
    print("\n🌍 Macro Indicators")
    print("-" * 40)

    from alternative_data.macro import MacroIndicators, CrossAssetSignals

    macro = MacroIndicators()
    cross_asset = CrossAssetSignals()

    print("  Key Indicators Tracked:")
    print("    - Fed Funds Rate, Balance Sheet")
    print("    - CPI, Core CPI, PCE, PPI")
    print("    - GDP, Industrial Production")
    print("    - NFP, Unemployment, Jobless Claims")
    print("    - Consumer Confidence, ISM")

    print("\n  Cross-Asset Signals:")
    print("    - Risk On/Off (SPY vs TLT)")
    print("    - Yield Curve (2s10s spread)")
    print("    - Dollar Strength (DXY)")
    print("    - VIX/Volatility regime")


def main():
    """Run all demonstrations."""
    print("\n" + "🚀" * 35)
    print("\n  QUANTITATIVE TRADING INFRASTRUCTURE DEMONSTRATION")
    print("  " + "=" * 55)
    print("\n" + "🚀" * 35 + "\n")

    try:
        demo_mathematical_models()
        demo_signal_processing()
        demo_ai_models()
        demo_hft_components()
        demo_portfolio_optimization()
        demo_execution()
        demo_backtesting()
        demo_monitoring()
        demo_trading_engine()
        demo_alternative_data()

        print_header("✅ DEMONSTRATION COMPLETE")
        print("All components are functional and ready for use!")
        print("\nNext steps:")
        print("  1. Review individual module documentation")
        print("  2. Run unit tests: pytest tests/")
        print("  3. Try the interactive examples in examples/")
        print("  4. Connect to real market data feeds")
        print("  5. Start with paper trading before going live")
        print("\n⚠️  IMPORTANT: Always backtest thoroughly before live trading!")
        print("    Past performance does not guarantee future results.")

    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("\nMake sure you have installed all dependencies:")
        print("  pip install -r requirements.txt")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
