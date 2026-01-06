#!/usr/bin/env python3
"""
TQO MVP - Main Entry Point

Titan Quantitative Opportunities
A 2-factor systematic trading system based on:
1. CVD Divergence (Order Flow)
2. Entropy Filter (Regime Detection)

Usage:
    python main.py --mode backtest --asset BTC
    python main.py --mode paper --asset ETH
    python main.py --mode live --asset BTC (DANGEROUS)
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('titan_mvp')


def run_backtest(asset: str, days: int = 30):
    """Run backtest with synthetic data."""
    from titan_mvp.data.candles import Candle, CandleAggregator
    from titan_mvp.signals.signal_combiner import SignalCombiner
    from titan_mvp.risk.risk_manager import RiskManager
    from titan_mvp.backtest.engine import BacktestEngine, BacktestConfig
    import random
    import math

    logger.info("=" * 60)
    logger.info("TQO MVP BACKTEST")
    logger.info("=" * 60)
    logger.info(f"Asset: {asset}")
    logger.info(f"Period: {days} days")

    # Generate synthetic candles for testing
    logger.info("Generating synthetic market data...")
    candles = generate_synthetic_candles(
        base_price=50000 if asset == "BTC" else 3000,
        num_candles=days * 24 * 60,  # 1-minute candles
        volatility=0.001
    )
    logger.info(f"Generated {len(candles)} candles")

    # Setup backtest
    config = BacktestConfig(
        initial_capital=10000.0,
        maker_fee_bps=2,
        slippage_bps=5
    )

    engine = BacktestEngine(config=config)

    # Run backtest
    logger.info("Running backtest...")
    result = engine.run(candles, warmup_period=100)

    # Print results
    print("\n" + result.metrics.summary())

    # Verdict
    passes, failures = result.metrics.passes_minimum()
    if passes:
        logger.info("VERDICT: Strategy PASSES minimum thresholds")
        logger.info("Proceed to paper trading phase")
    else:
        logger.warning("VERDICT: Strategy FAILS minimum thresholds")
        for failure in failures:
            logger.warning(f"  - {failure}")

    return result


def generate_synthetic_candles(
    base_price: float,
    num_candles: int,
    volatility: float = 0.001
) -> list:
    """
    Generate synthetic candles with realistic patterns.

    Includes:
    - Trending periods (for CVD divergence)
    - Low/high entropy regimes
    - Volume patterns
    """
    from titan_mvp.data.candles import Candle
    from titan_mvp.data.trades import TradeSide
    import random
    import math

    candles = []
    price = base_price
    timestamp = int(datetime.now().timestamp() * 1000) - (num_candles * 60 * 1000)

    # Market phases
    phase = "neutral"
    phase_duration = 0
    phase_length = random.randint(50, 200)

    for i in range(num_candles):
        # Change phase periodically
        phase_duration += 1
        if phase_duration >= phase_length:
            phase = random.choice(["trending_up", "trending_down", "ranging", "volatile", "neutral"])
            phase_duration = 0
            phase_length = random.randint(50, 200)

        # Generate OHLC based on phase
        if phase == "trending_up":
            drift = volatility * 0.3
            vol = volatility * 0.8
        elif phase == "trending_down":
            drift = -volatility * 0.3
            vol = volatility * 0.8
        elif phase == "ranging":
            drift = 0
            vol = volatility * 0.5
        elif phase == "volatile":
            drift = random.gauss(0, volatility * 0.2)
            vol = volatility * 2
        else:
            drift = random.gauss(0, volatility * 0.1)
            vol = volatility

        # Generate candle
        open_price = price
        change = random.gauss(drift, vol)
        close_price = price * (1 + change)

        # High and low
        high_wick = abs(random.gauss(0, vol * 0.5))
        low_wick = abs(random.gauss(0, vol * 0.5))
        high_price = max(open_price, close_price) * (1 + high_wick)
        low_price = min(open_price, close_price) * (1 - low_wick)

        # Volume (correlated with volatility)
        base_volume = 100
        volume = base_volume * (1 + abs(change) * 100) * random.uniform(0.5, 1.5)

        # Buy/sell volume (for CVD)
        if close_price > open_price:
            buy_ratio = 0.5 + random.uniform(0, 0.3)
        else:
            buy_ratio = 0.5 - random.uniform(0, 0.3)

        buy_volume = volume * buy_ratio
        sell_volume = volume * (1 - buy_ratio)

        candle = Candle(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            trade_count=int(volume / 10),
            timeframe="1m",
            is_complete=True
        )
        candles.append(candle)

        # Update for next candle
        price = close_price
        timestamp += 60 * 1000  # 1 minute

    return candles


def run_demo():
    """Run a quick demo of all components."""
    logger.info("=" * 60)
    logger.info("TQO MVP COMPONENT DEMO")
    logger.info("=" * 60)

    # 1. Data Layer
    logger.info("\n1. DATA LAYER")
    from titan_mvp.data.trades import Trade, TradeAggregator, TradeSide
    from titan_mvp.data.candles import Candle, CandleAggregator

    aggregator = TradeAggregator()
    for i in range(100):
        trade = Trade(
            timestamp=i * 1000,
            price=50000 + i * 10,
            size=0.1,
            side=TradeSide.BUY if i % 3 != 0 else TradeSide.SELL
        )
        aggregator.add_trade(trade)

    logger.info(f"  CVD: {aggregator.cvd:.2f}")
    logger.info(f"  Imbalance: {aggregator.get_imbalance():.2%}")
    logger.info(f"  Z-score: {aggregator.get_cvd_zscore():.2f}")

    # 2. CVD Engine
    logger.info("\n2. CVD ENGINE")
    from titan_mvp.signals.cvd_engine import CVDEngine

    candles = generate_synthetic_candles(50000, 100)
    cvd_engine = CVDEngine()
    signal = cvd_engine.analyze(candles)

    logger.info(f"  Divergence: {signal.divergence_type.value}")
    logger.info(f"  Strength: {signal.strength:.2f}")
    logger.info(f"  Z-score: {signal.zscore:.2f}")
    logger.info(f"  Valid: {signal.is_valid}")

    # 3. Entropy Filter
    logger.info("\n3. ENTROPY FILTER")
    from titan_mvp.signals.entropy_filter import EntropyFilter

    entropy_filter = EntropyFilter()
    for candle in candles:
        entropy_filter.update(candle.close)
    entropy_signal = entropy_filter.get_signal()

    logger.info(f"  Regime: {entropy_signal.regime.value}")
    logger.info(f"  Entropy: {entropy_signal.entropy:.4f}")
    logger.info(f"  Hurst: {entropy_signal.hurst:.4f} ({entropy_signal.hurst_signal})")
    logger.info(f"  Can Trade: {entropy_signal.can_trade}")

    # 4. Signal Combiner
    logger.info("\n4. SIGNAL COMBINER")
    from titan_mvp.signals.signal_combiner import SignalCombiner

    combiner = SignalCombiner()
    combined = combiner.analyze(candles, asset="BTC")

    logger.info(f"  Direction: {combined.direction.value}")
    logger.info(f"  Should Trade: {combined.should_trade}")
    logger.info(f"  Confidence: {combined.confidence:.2f}")
    logger.info(f"  Reason: {combined.reason}")

    # 5. Risk Manager
    logger.info("\n5. RISK MANAGER")
    from titan_mvp.risk.risk_manager import RiskManager
    from titan_mvp.risk.atr_calculator import ATRCalculator

    atr = ATRCalculator()
    for candle in candles:
        atr.update(candle)

    risk = RiskManager(initial_capital=10000, atr_calculator=atr)
    can_trade, reason = risk.can_trade()

    logger.info(f"  Can Trade: {can_trade} ({reason})")
    state = risk.get_state()
    logger.info(f"  Status: {state.status.value}")
    logger.info(f"  Equity: ${state.current_equity:.2f}")

    if can_trade:
        position = risk.calculate_position(
            entry_price=candles[-1].close,
            direction='long',
            confidence=0.8
        )
        if position:
            logger.info(f"  Position Size: ${position.size_usd:.2f}")
            logger.info(f"  Stop: ${position.stop_price:.2f}")
            logger.info(f"  Target: ${position.target_price:.2f}")

    logger.info("\n" + "=" * 60)
    logger.info("DEMO COMPLETE")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="TQO MVP - Titan Quantitative Opportunities"
    )
    parser.add_argument(
        "--mode",
        choices=["demo", "backtest", "paper", "live"],
        default="demo",
        help="Operating mode"
    )
    parser.add_argument(
        "--asset",
        default="BTC",
        help="Asset to trade (default: BTC)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days of data for backtest"
    )

    args = parser.parse_args()

    if args.mode == "demo":
        run_demo()
    elif args.mode == "backtest":
        run_backtest(args.asset, args.days)
    elif args.mode == "paper":
        logger.info("Paper trading mode not yet implemented")
        logger.info("Coming in Week 3 of MVP development")
    elif args.mode == "live":
        logger.error("LIVE TRADING IS DANGEROUS")
        logger.error("Requires extensive paper trading validation first")
        logger.error("Not implemented in MVP")
        sys.exit(1)


if __name__ == "__main__":
    main()
