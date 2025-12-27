#!/usr/bin/env python3
"""
🤖 ShopGuard Live Trading Bot - Quick Start

This runs a REAL trading bot with:
- Real-time stock prices from Yahoo Finance
- Real-time crypto prices from CoinGecko
- Trading signals based on technical analysis
- Paper trading portfolio (no real money)

Usage:
    python run_live_bot.py              # Start web dashboard
    python run_live_bot.py --cli        # Run in terminal mode
    python run_live_bot.py --test       # Test price fetching
"""

import sys
import os
import argparse

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_prices():
    """Test that price fetching works"""
    print("\n🧪 Testing Price Fetching...")
    print("=" * 50)

    from live_trading_bot.price_fetcher import PriceFetcher

    fetcher = PriceFetcher()

    print("\n📊 Fetching REAL crypto prices from CoinGecko...")
    crypto = fetcher.get_crypto_prices(["bitcoin", "ethereum", "solana"])

    if crypto:
        print("\n✅ Crypto prices (REAL DATA):")
        for coin_id, price in crypto.items():
            arrow = "🟢" if price.change_24h > 0 else "🔴"
            print(f"   {arrow} {price.symbol}: ${price.price:,.2f} ({price.change_24h:+.2f}%)")
    else:
        print("❌ Failed to fetch crypto prices")

    print("\n📈 Fetching REAL stock prices from Yahoo Finance...")
    stocks = fetcher.get_stock_prices(["AAPL", "GOOGL", "NVDA"])

    if stocks:
        print("\n✅ Stock prices (REAL DATA):")
        for symbol, price in stocks.items():
            arrow = "🟢" if price.change_24h > 0 else "🔴"
            print(f"   {arrow} {symbol}: ${price.price:,.2f} ({price.change_24h:+.2f}%)")
    else:
        print("❌ Failed to fetch stock prices")

    print("\n✅ Price fetching test complete!")
    return bool(crypto or stocks)


def run_cli():
    """Run bot in CLI mode"""
    print("\n🤖 Starting Trading Bot (CLI Mode)...")
    print("=" * 50)

    from live_trading_bot.bot import TradingBot
    from live_trading_bot.config import TradingConfig

    bot = TradingBot(TradingConfig())

    print("\nRunning one cycle...")
    bot.run_once()

    print("\nWould you like to continue monitoring? (y/n)")
    try:
        if input().lower() == 'y':
            bot.run(interval_seconds=60, auto_trade=False)
    except KeyboardInterrupt:
        print("\nGoodbye!")


def run_dashboard():
    """Run web dashboard"""
    print("\n🌐 Starting Web Dashboard...")

    # Check Flask
    try:
        import flask
    except ImportError:
        print("\n❌ Flask not installed. Installing...")
        os.system(f"{sys.executable} -m pip install flask")

    from live_trading_bot.dashboard import main
    main()


def main():
    parser = argparse.ArgumentParser(
        description='🤖 ShopGuard Live Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_live_bot.py          # Start web dashboard
  python run_live_bot.py --cli    # Terminal mode
  python run_live_bot.py --test   # Test price APIs
        """
    )
    parser.add_argument('--cli', action='store_true', help='Run in CLI/terminal mode')
    parser.add_argument('--test', action='store_true', help='Test price fetching')

    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🤖  SHOPGUARD LIVE TRADING BOT                             ║
║                                                              ║
║   Real prices • Real signals • Paper trading                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    if args.test:
        success = test_prices()
        sys.exit(0 if success else 1)
    elif args.cli:
        run_cli()
    else:
        run_dashboard()


if __name__ == '__main__':
    main()
