#!/usr/bin/env python3
"""
TITAN Trading System - Quick Start
===================================
Run this script to start the TITAN trading engine.

Requirements:
    pip install eth-account requests websockets

Usage:
    # Demo mode (read-only, no trading)
    python run_titan.py --demo

    # Paper trading on testnet
    python run_titan.py --testnet --key YOUR_PRIVATE_KEY

    # Live trading (BE CAREFUL!)
    python run_titan.py --live --key YOUR_PRIVATE_KEY
"""

import asyncio
import argparse
import os
import sys
import logging

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('TITAN')


def print_banner():
    """Print the TITAN banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║   ████████╗██╗████████╗ █████╗ ███╗   ██╗                            ║
║   ╚══██╔══╝██║╚══██╔══╝██╔══██╗████╗  ██║                            ║
║      ██║   ██║   ██║   ███████║██╔██╗ ██║                            ║
║      ██║   ██║   ██║   ██╔══██║██║╚██╗██║                            ║
║      ██║   ██║   ██║   ██║  ██║██║ ╚████║                            ║
║      ╚═╝   ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝                            ║
║                                                                       ║
║              TRADING INFRASTRUCTURE FOR ALPHA NETWORKS                ║
║                                                                       ║
║   3-Pillar Convergence: Entropy + Hurst + CVD                        ║
║   Exchange: Hyperliquid (Zero Gas, Non-Custodial)                    ║
║   Risk: ATR-Based Dynamic Stops (1.5x Stop, 3x Target)               ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


async def run_demo():
    """Run in demo mode (read-only)"""
    from shopguard_platform.brokers.hyperliquid import HyperliquidClient

    print("\n[DEMO MODE] Reading market data from Hyperliquid...\n")

    client = HyperliquidClient(testnet=True)

    # Get prices
    print("Fetching prices...")
    prices = client.get_all_mids()
    print(f"\nTop Assets by Price:")
    for asset in ["BTC", "ETH", "SOL", "DOGE", "XRP"]:
        price = prices.get(asset, 0)
        print(f"  {asset}: ${price:,.2f}")

    # Get funding rates
    print("\nFetching funding rates...")
    rates = client.get_all_funding_rates()
    print(f"\nFunding Rates (Top 5 by absolute value):")

    sorted_rates = sorted(rates.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    for asset, rate in sorted_rates:
        direction = "+" if rate > 0 else ""
        annual = rate * 3 * 365 * 100  # Annualized
        print(f"  {asset}: {direction}{rate*100:.4f}% per 8h ({annual:.1f}% annual)")

    # Stream some trades for CVD
    print("\n\nStreaming trades for CVD calculation...")
    print("(Press Ctrl+C to stop)\n")

    try:
        from shopguard_platform.brokers.hyperliquid.websocket import HyperliquidWebSocket

        ws = HyperliquidWebSocket(testnet=True)

        def on_cvd(cvd):
            divergence = cvd.get_divergence() or "NONE"
            print(
                f"  {cvd.asset} | CVD: {cvd.cvd:>12,.2f} | "
                f"Buy: {cvd.buy_volume:>10,.2f} | Sell: {cvd.sell_volume:>10,.2f} | "
                f"Divergence: {divergence}"
            )

        ws.on_cvd_update = on_cvd

        await ws.connect()
        await ws.subscribe_trades(["BTC", "ETH"])

        # Run for 30 seconds
        await asyncio.wait_for(ws.run_forever(), timeout=30)

    except asyncio.TimeoutError:
        print("\n\nDemo complete!")
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    finally:
        if ws:
            await ws.disconnect()


async def run_engine(private_key: str, testnet: bool = True):
    """Run the full trading engine"""
    from shopguard_platform.brokers.trading_engine import TitanTradingEngine, EngineConfig

    mode = "TESTNET" if testnet else "LIVE"
    print(f"\n[{mode} MODE] Starting TITAN Trading Engine...\n")

    if not testnet:
        print("=" * 60)
        print("WARNING: LIVE TRADING MODE")
        print("Real money is at risk. Proceed with caution.")
        print("=" * 60)
        confirm = input("\nType 'I UNDERSTAND' to continue: ")
        if confirm != "I UNDERSTAND":
            print("Aborted.")
            return

    config = EngineConfig(
        private_key=private_key,
        testnet=testnet,
        assets=["BTC", "ETH"],
        min_confidence=0.65,
        max_leverage=3,
        enable_funding_arbitrage=True
    )

    engine = TitanTradingEngine(config)

    # Set up callbacks
    def on_signal(signal):
        sig_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else signal.signal_type
        logger.info(f"SIGNAL: {signal.asset} {sig_type} @ ${signal.price:,.2f}")
        logger.info(f"  Confidence: {signal.confidence:.2f}")
        logger.info(f"  Stop: ${signal.stop_loss:,.2f} | Target: ${signal.take_profit:,.2f}")

    def on_trade(trade):
        logger.info(f"TRADE EXECUTED: {trade['side']} {trade['asset']}")

    engine.on_signal = on_signal
    engine.on_trade = on_trade

    if not await engine.start():
        print("Failed to start engine!")
        return

    print("\nEngine running. Press Ctrl+C to stop.\n")

    try:
        while True:
            await asyncio.sleep(30)

            # Print status every 30 seconds
            stats = engine.get_stats()
            status = engine.get_status()

            print("\n" + "-" * 40)
            print(f"Uptime: {stats['uptime_hours']:.2f}h")
            print(f"Ticks: {stats['ticks_processed']} | Signals: {stats['signals_generated']} | Trades: {stats['trades_executed']}")

            for asset, cvd in status.get('cvd', {}).items():
                print(f"{asset}: CVD={cvd['cvd']:,.2f} | Divergence={cvd['divergence']}")

    except KeyboardInterrupt:
        print("\n\nShutting down...")

    await engine.stop()

    print("\n" + "=" * 60)
    print("Final Statistics:")
    for key, value in engine.get_stats().items():
        print(f"  {key}: {value}")
    print("=" * 60)


async def run_funding_scan():
    """Just scan funding rates"""
    from shopguard_platform.brokers.hyperliquid.funding import demo_funding_scanner
    await demo_funding_scanner()


def main():
    parser = argparse.ArgumentParser(
        description="TITAN Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_titan.py --demo              # Read-only demo
  python run_titan.py --funding           # Scan funding rates
  python run_titan.py --testnet -k KEY    # Paper trading
  python run_titan.py --live -k KEY       # REAL TRADING
        """
    )

    parser.add_argument('--demo', action='store_true', help='Run in demo mode (read-only)')
    parser.add_argument('--funding', action='store_true', help='Scan funding rates only')
    parser.add_argument('--testnet', action='store_true', help='Run on Hyperliquid testnet')
    parser.add_argument('--live', action='store_true', help='Run on Hyperliquid mainnet (REAL MONEY)')
    parser.add_argument('-k', '--key', help='Ethereum private key (0x...)')

    args = parser.parse_args()

    print_banner()

    # Check dependencies
    try:
        import requests
        import websockets
        from eth_account import Account
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("\nInstall required packages:")
        print("  pip install eth-account requests websockets")
        sys.exit(1)

    # Run appropriate mode
    if args.demo:
        asyncio.run(run_demo())

    elif args.funding:
        asyncio.run(run_funding_scan())

    elif args.testnet:
        key = args.key or os.environ.get('HYPERLIQUID_PRIVATE_KEY')
        if not key:
            print("Error: Private key required for testnet mode")
            print("Use --key YOUR_KEY or set HYPERLIQUID_PRIVATE_KEY env var")
            sys.exit(1)
        asyncio.run(run_engine(key, testnet=True))

    elif args.live:
        key = args.key or os.environ.get('HYPERLIQUID_PRIVATE_KEY')
        if not key:
            print("Error: Private key required for live mode")
            print("Use --key YOUR_KEY or set HYPERLIQUID_PRIVATE_KEY env var")
            sys.exit(1)
        asyncio.run(run_engine(key, testnet=False))

    else:
        # Default to demo
        print("No mode specified, running demo...")
        print("Use --help to see options\n")
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
