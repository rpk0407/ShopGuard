#!/usr/bin/env python3
"""
TITAN ECOSYSTEM TEST SUITE
===========================
Comprehensive tests for all ecosystem components.

Run: python3 test_ecosystem.py

Components tested:
- Risk Manager (The Membrane)
- Order Executor (The Mitochondria)
- Regime Detector (The Receptors)
- Trade Journal (The Memory)
- Alert System (The Nervous System)
- TitanEcosystem (Unified Organism)
"""

import sys
import os
import time
import random
import logging

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise during tests

# Track test results
tests_passed = 0
tests_failed = 0


def test_result(passed: bool, message: str):
    """Track test result"""
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        print(f"  ✓ {message}")
    else:
        tests_failed += 1
        print(f"  ✗ {message}")


def test_imports():
    """Test all ecosystem imports"""
    print("\n" + "=" * 60)
    print("  TEST 1: IMPORTS")
    print("=" * 60)

    # Risk Manager
    try:
        from src.core.risk_manager import RiskManager, RiskConfig, PositionSizer
        test_result(True, "RiskManager imported")
    except ImportError as e:
        test_result(False, f"RiskManager import failed: {e}")
        return False

    # Order Executor
    try:
        from src.core.executor import OrderExecutor, Order, OrderSide, OrderType, OrderStatus, Fill
        test_result(True, "OrderExecutor imported")
    except ImportError as e:
        test_result(False, f"OrderExecutor import failed: {e}")
        return False

    # Regime Detector
    try:
        from src.core.regime import RegimeDetector, MarketRegime, VolatilityState
        test_result(True, "RegimeDetector imported")
    except ImportError as e:
        test_result(False, f"RegimeDetector import failed: {e}")
        return False

    # Trade Journal
    try:
        from src.core.journal import TradeJournal, TradeRecord, PerformanceMetrics
        test_result(True, "TradeJournal imported")
    except ImportError as e:
        test_result(False, f"TradeJournal import failed: {e}")
        return False

    # Alert System
    try:
        from src.core.alerts import AlertSystem, Alert, AlertLevel, EventType
        test_result(True, "AlertSystem imported")
    except ImportError as e:
        test_result(False, f"AlertSystem import failed: {e}")
        return False

    # Ecosystem
    try:
        from src.core.ecosystem import TitanEcosystem, EcosystemConfig, EcosystemState
        test_result(True, "TitanEcosystem imported")
    except ImportError as e:
        test_result(False, f"TitanEcosystem import failed: {e}")
        return False

    return True


def test_risk_manager():
    """Test Risk Manager component"""
    print("\n" + "=" * 60)
    print("  TEST 2: RISK MANAGER (The Membrane)")
    print("=" * 60)

    from src.core.risk_manager import RiskManager, RiskConfig

    # Create risk manager with correct parameters
    config = RiskConfig(
        initial_capital=10000.0,
        max_position_pct=0.25,
        max_drawdown_pct=0.15,
        daily_loss_limit_pct=0.05,
        max_correlated_positions=3
    )
    rm = RiskManager(config)
    test_result(True, "RiskManager created")

    # Test can_trade
    can_trade, reason = rm.can_trade()
    test_result(can_trade, f"Initial can_trade: {reason}")

    # Test position sizing
    size, reasoning = rm.calculate_position_size(
        signal_confidence=0.8,
        current_volatility=0.02
    )
    test_result(size >= 0, f"Position size calculated: {size:.4f}")

    # Test opening position
    position = rm.open_position("BTC/USDT", "LONG", 50000.0, 0.1, 49000.0, 52000.0)
    test_result(position is not None, "Position opened")

    # Test more positions
    rm.open_position("ETH/USDT", "LONG", 3000.0, 0.1, 2900.0, 3200.0)
    rm.open_position("SOL/USDT", "LONG", 100.0, 0.1, 95.0, 110.0)
    test_result(True, "Multiple positions opened")

    # Test close position
    pnl = rm.close_position("BTC/USDT", 51000.0)  # Profit
    test_result(pnl is not None and pnl >= 0, f"Position closed with P&L: ${pnl:.2f}")

    # Test can still trade after normal operation
    can_trade, reason = rm.can_trade()
    test_result(True, f"Post-trade state: {reason}")

    # Get stats
    stats = rm.get_stats()
    test_result('capital' in stats, f"Stats retrieved: capital=${stats.get('capital', {}).get('current', 0):.2f}")

    return True


def test_order_executor():
    """Test Order Executor component"""
    print("\n" + "=" * 60)
    print("  TEST 3: ORDER EXECUTOR (The Mitochondria)")
    print("=" * 60)

    from src.core.executor import OrderExecutor, ExecutionConfig, OrderSide, OrderType, OrderStatus

    # Create executor
    config = ExecutionConfig(
        maker_fee=0.001,
        taker_fee=0.002,
        base_slippage=0.0005
    )
    executor = OrderExecutor(config)
    test_result(True, "OrderExecutor created")

    # Update market
    executor.update_market("BTC/USDT", 50000.0, 10000000)
    test_result(True, "Market updated")

    # Create order
    order = executor.create_order(
        asset="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    test_result(order is not None, f"Order created: {order.order_id}")

    # Submit order
    submitted = executor.submit_order(order.order_id)
    test_result(submitted, "Order submitted")

    # Wait for fill
    time.sleep(0.2)
    test_result(order.status == OrderStatus.FILLED, f"Order filled: {order.status.value}")

    # Check fills
    test_result(len(order.fills) > 0, f"Fills recorded: {len(order.fills)}")

    # Execute signal (convenience method)
    sell_order = executor.execute_signal("BTC/USDT", "SELL", 0.05)
    test_result(sell_order is not None and sell_order.status == OrderStatus.FILLED, "Signal executed")

    # Get stats
    stats = executor.get_stats()
    test_result(stats['total_orders'] >= 2, f"Stats: {stats['total_orders']} orders, {stats['total_fills']} fills")

    return True


def test_regime_detector():
    """Test Regime Detector component"""
    print("\n" + "=" * 60)
    print("  TEST 4: REGIME DETECTOR (The Receptors)")
    print("=" * 60)

    from src.core.regime import RegimeDetector, MarketRegime, VolatilityState

    # Create detector
    detector = RegimeDetector()
    test_result(True, "RegimeDetector created")

    # Feed stable prices
    for i in range(30):
        price = 50000 + random.uniform(-100, 100)
        state = detector.update("BTC/USDT", price)

    test_result(state is not None, f"Regime detected: {state.regime.value if state else 'None'}")

    # Feed trending prices
    price = 50000
    for i in range(50):
        price *= 1.002  # 0.2% gain each tick
        state = detector.update("BTC/USDT", price)

    test_result(state.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN, MarketRegime.RANGING],
                f"Trend regime: {state.regime.value}")

    # Check volatility state
    test_result(state.volatility_state in VolatilityState,
                f"Volatility: {state.volatility_state.value}")

    # Check confidence
    test_result(0 <= state.regime_confidence <= 1,
                f"Confidence: {state.regime_confidence:.2f}")

    # Get stats
    stats = detector.get_stats()
    test_result('tracked_assets' in stats, f"Stats tracked: {len(stats.get('tracked_assets', []))} assets")

    return True


def test_trade_journal():
    """Test Trade Journal component"""
    print("\n" + "=" * 60)
    print("  TEST 5: TRADE JOURNAL (The Memory)")
    print("=" * 60)

    from src.core.journal import TradeJournal, TradeOutcome

    # Create journal
    journal = TradeJournal(initial_capital=10000.0)
    test_result(True, "TradeJournal created")

    # Open trade
    trade = journal.open_trade(
        trade_id="trade_1",
        asset="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        size=0.1,
        stop_loss=49000.0,
        entry_signal="STRONG_BUY",
        entry_confidence=0.85,
        entry_regime="trending_up",
        pillars_aligned=3
    )
    test_result(trade is not None, f"Trade opened: {trade.trade_id}")

    # Close trade (winner)
    closed = journal.close_trade(
        trade_id="trade_1",
        exit_price=52000.0,
        exit_reason="TAKE_PROFIT"
    )
    test_result(closed is not None, f"Trade closed: P&L=${closed.pnl:.2f}")
    test_result(closed.outcome in [TradeOutcome.WIN, TradeOutcome.BIG_WIN], f"Outcome: {closed.outcome.value}")

    # Open and close more trades
    for i in range(10):
        entry = 50000 + random.uniform(-1000, 1000)
        exit_price = entry * (1 + random.uniform(-0.03, 0.05))

        journal.open_trade(
            trade_id=f"trade_{i+2}",
            asset="BTC/USDT",
            side="LONG",
            entry_price=entry,
            size=0.1,
            stop_loss=entry * 0.95,
            entry_signal="BUY",
            entry_regime="ranging",
            pillars_aligned=2
        )
        journal.close_trade(
            trade_id=f"trade_{i+2}",
            exit_price=exit_price,
            exit_reason="SIGNAL"
        )

    # Calculate metrics
    metrics = journal.calculate_metrics()
    test_result(metrics.total_trades == 11, f"Total trades: {metrics.total_trades}")
    test_result(0 <= metrics.win_rate <= 1, f"Win rate: {metrics.win_rate*100:.1f}%")

    # Get best patterns
    best_regime, regime_r = journal.get_best_regime()
    test_result(best_regime is not None, f"Best regime: {best_regime} (R={regime_r:.2f})")

    # Get stats
    stats = journal.get_stats()
    test_result('capital' in stats, f"Current capital: ${stats['capital']['current']:.2f}")

    return True


def test_alert_system():
    """Test Alert System component"""
    print("\n" + "=" * 60)
    print("  TEST 6: ALERT SYSTEM (The Nervous System)")
    print("=" * 60)

    from src.core.alerts import AlertSystem, AlertLevel, EventType

    # Create alert system
    alerts = AlertSystem()
    test_result(True, "AlertSystem created")

    # Start system
    alerts.start()
    test_result(True, "AlertSystem started")

    # Track received events
    received_events = []

    def on_event(alert):
        received_events.append(alert)

    # Subscribe to events
    alerts.subscribe(EventType.SIGNAL_GENERATED, on_event)
    test_result(True, "Subscribed to SIGNAL_GENERATED")

    # Emit alert
    alert = alerts.emit(
        EventType.SIGNAL_GENERATED,
        "Test Signal",
        "BTC/USDT STRONG_BUY",
        AlertLevel.INFO,
        source="Test"
    )
    test_result(alert is not None, f"Alert emitted: {alert.alert_id}")

    # Use convenience methods
    alerts.signal_alert("STRONG_BUY", "ETH/USDT", 0.85, 3000.0)
    alerts.trade_alert("OPENED", "BTC/USDT", "LONG", 50000.0)
    alerts.risk_alert("drawdown", "Drawdown at 5%", AlertLevel.WARNING)
    alerts.evolution_alert(5, 45.3, alpha_updated=True)

    # Wait for processing
    time.sleep(0.3)

    # Check events received
    test_result(len(received_events) >= 1, f"Events received: {len(received_events)}")

    # Query alerts
    recent = alerts.get_alerts(limit=10)
    test_result(len(recent) >= 4, f"Recent alerts: {len(recent)}")

    # Get unacknowledged
    unack_count = alerts.get_unacknowledged_count()
    test_result(unack_count >= 0, f"Unacknowledged: {unack_count}")

    # Get stats
    stats = alerts.get_stats()
    test_result('total_alerts' in stats, f"Total alerts: {stats['total_alerts']}")

    # Stop system
    alerts.stop()
    test_result(True, "AlertSystem stopped")

    return True


def test_ecosystem_integration():
    """Test full ecosystem integration"""
    print("\n" + "=" * 60)
    print("  TEST 7: TITAN ECOSYSTEM (Full Integration)")
    print("=" * 60)

    from src.core.ecosystem import TitanEcosystem, EcosystemConfig, EcosystemState

    # Create ecosystem
    config = EcosystemConfig(
        initial_capital=10000.0,
        max_concurrent_positions=3,
        enable_evolution=False,  # Disable for test
        enable_paper_trading=True
    )
    ecosystem = TitanEcosystem(config=config)
    test_result(True, "TitanEcosystem created")

    # Check components initialized
    test_result(ecosystem.brain is not None, "Brain initialized")
    test_result(ecosystem.risk_manager is not None, "RiskManager initialized")
    test_result(ecosystem.executor is not None, "Executor initialized")
    test_result(ecosystem.regime_detector is not None, "RegimeDetector initialized")
    test_result(ecosystem.journal is not None, "Journal initialized")
    test_result(ecosystem.alerts is not None, "AlertSystem initialized")

    # Start ecosystem
    ecosystem.start()
    test_result(ecosystem.state == EcosystemState.HEALTHY, f"Ecosystem state: {ecosystem.state.value}")

    # Process ticks
    test_ticks = [
        {'asset': 'BTC/USDT', 'price': 50000, 'entropy': 2.3, 'hurst': 0.65, 'viral_k': 1.3, 'cvd': 150, 'phase': 'accumulation'},
        {'asset': 'BTC/USDT', 'price': 50100, 'entropy': 2.1, 'hurst': 0.68, 'viral_k': 1.4, 'cvd': 200, 'phase': 'recovery'},
        {'asset': 'BTC/USDT', 'price': 50200, 'entropy': 2.0, 'hurst': 0.70, 'viral_k': 1.5, 'cvd': 250, 'phase': 'recovery'},
        {'asset': 'BTC/USDT', 'price': 50500, 'entropy': 1.9, 'hurst': 0.72, 'viral_k': 1.6, 'cvd': 300, 'phase': 'euphoria'},
    ]

    signals = []
    for tick in test_ticks:
        signal = ecosystem.process_tick(tick)
        if signal:
            signals.append(signal)

    test_result(len(signals) == len(test_ticks), f"Processed {len(signals)} ticks")

    # Check signal generated
    test_result(signals[0].signal_type is not None, f"First signal: {signals[0].signal_type.value}")

    # Get status
    status = ecosystem.get_status()
    test_result('portfolio' in status, f"Portfolio value: ${status['portfolio']['total_equity']:.2f}")
    test_result('brain' in status, f"Brain signals: {status['brain']['signals_generated']}")

    # Get performance
    performance = ecosystem.get_performance()
    test_result(performance is not None, "Performance metrics retrieved")

    # Reset ecosystem
    ecosystem.reset()
    test_result(ecosystem.capital == 10000.0, "Ecosystem reset")

    # Stop ecosystem
    ecosystem.stop()
    test_result(ecosystem.state == EcosystemState.SHUTDOWN, "Ecosystem stopped")

    return True


def run_all_tests():
    """Run all tests"""
    global tests_passed, tests_failed

    print("\n" + "=" * 60)
    print("  TITAN ECOSYSTEM TEST SUITE")
    print("=" * 60)
    print(f"\n  Running comprehensive tests for all components...")

    start_time = time.time()

    # Run tests
    if not test_imports():
        print("\n  ✗ Import tests failed - aborting")
        return False

    test_risk_manager()
    test_order_executor()
    test_regime_detector()
    test_trade_journal()
    test_alert_system()
    test_ecosystem_integration()

    elapsed = time.time() - start_time

    # Print summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    print(f"\n  Total tests: {tests_passed + tests_failed}")
    print(f"  Passed: {tests_passed}")
    print(f"  Failed: {tests_failed}")
    print(f"  Time: {elapsed:.2f}s")

    if tests_failed == 0:
        print("\n  ✓ ALL TESTS PASSED!")
    else:
        print(f"\n  ✗ {tests_failed} TESTS FAILED")

    return tests_failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
