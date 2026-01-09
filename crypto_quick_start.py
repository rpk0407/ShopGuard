#!/usr/bin/env python3
"""
ShopGuard Crypto Trading - Quick Start

Hyperliquid DEX Integration for Perpetual Futures Trading

Setup:
1. Install dependencies: pip install -r requirements.txt
2. Set up .env file with your Hyperliquid credentials
3. Run: python crypto_quick_start.py

Features:
- Connect to Hyperliquid (testnet/mainnet)
- View account balances and positions
- Get real-time market data
- Place orders (limit/market)
- Manage positions
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Load environment variables
load_dotenv()


def print_banner():
    """Print welcome banner"""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🚀  SHOPGUARD CRYPTO TRADING                              ║
    ║                                                              ║
    ║   Hyperliquid DEX - Perpetual Futures                        ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)


def check_environment():
    """Check if environment is properly configured"""
    print("\n[1/4] Checking environment configuration...")

    # Check for Hyperliquid credentials
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
    wallet_address = os.getenv('HYPERLIQUID_WALLET_ADDRESS')

    if not private_key and not wallet_address:
        print("⚠️  No Hyperliquid credentials found")
        print("\n  To trade, you need to set one of:")
        print("  - HYPERLIQUID_PRIVATE_KEY (for full access)")
        print("  - HYPERLIQUID_WALLET_ADDRESS (for read-only)")
        print("\n  Add to .env file or set as environment variables")
        print("\n  For read-only mode (market data only), continuing...\n")
    elif private_key:
        print("✓ Private key configured (full trading access)")
    else:
        print("✓ Wallet address configured (read-only mode)")

    # Check if we're using testnet or mainnet
    use_testnet = os.getenv('HYPERLIQUID_TESTNET', 'true').lower() == 'true'
    env_name = "TESTNET" if use_testnet else "MAINNET ⚠️"
    print(f"✓ Environment: {env_name}")

    return use_testnet


def check_dependencies():
    """Check if required packages are installed"""
    print("\n[2/4] Checking dependencies...")

    required = {
        'hyperliquid': 'hyperliquid-python-sdk',
        'web3': 'web3',
        'requests': 'requests',
        'dotenv': 'python-dotenv'
    }

    missing = []
    for package, pip_name in required.items():
        try:
            __import__(package)
            print(f"  ✓ {pip_name}")
        except ImportError:
            print(f"  ✗ {pip_name} (missing)")
            missing.append(pip_name)

    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print(f"\n  Install with: pip install {' '.join(missing)}")
        return False

    print("\n✓ All dependencies installed")
    return True


def test_hyperliquid_connection(use_testnet=True):
    """Test connection to Hyperliquid"""
    print("\n[3/4] Testing Hyperliquid connection...")

    try:
        from trading.hyperliquid_adapter import HyperliquidAdapter

        # Create adapter
        hl = HyperliquidAdapter(testnet=use_testnet)

        # Connect
        if hl.connect():
            print("✓ Connected to Hyperliquid")

            # Get available markets
            assets = hl.get_all_assets()
            print(f"✓ Found {len(assets)} tradable markets")

            # Get BTC price
            btc_price = hl.get_market_price("BTC")
            if btc_price:
                print(f"✓ BTC Price: ${btc_price:,.2f}")

            # Get ETH price
            eth_price = hl.get_market_price("ETH")
            if eth_price:
                print(f"✓ ETH Price: ${eth_price:,.2f}")

            # If we have wallet access, show account info
            if hl.wallet_address:
                balances = hl.get_balances()
                if balances:
                    print(f"\n  Account Value: ${balances.get('account_value', 0):,.2f}")
                    print(f"  Available: ${balances.get('USDC', 0):,.2f} USDC")
                    print(f"  Margin Used: ${balances.get('margin_used', 0):,.2f}")

                # Check positions
                positions = hl.get_positions()
                if positions:
                    print(f"\n  Open Positions: {len(positions)}")
                    for pos in positions:
                        pnl_symbol = "📈" if pos.unrealized_pnl > 0 else "📉"
                        print(f"    {pnl_symbol} {pos.coin} {pos.side.upper()}: {pos.size} @ ${pos.entry_price:,.2f}")
                        print(f"       PnL: ${pos.unrealized_pnl:,.2f} | Leverage: {pos.leverage:.1f}x")
                else:
                    print("  No open positions")

            return True
        else:
            print("✗ Failed to connect to Hyperliquid")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_market_overview():
    """Show market overview"""
    print("\n[4/4] Market Overview...")

    try:
        from trading.hyperliquid_adapter import HyperliquidAdapter

        hl = HyperliquidAdapter(testnet=os.getenv('HYPERLIQUID_TESTNET', 'true').lower() == 'true')
        hl.connect()

        # Top markets by volume
        print("\n  Top Markets:")
        markets = hl.get_all_assets()

        # Show top 10
        for i, asset in enumerate(markets[:10], 1):
            price = hl.get_market_price(asset['name'])
            funding = hl.get_funding_rate(asset['name'])

            if price:
                print(f"    {i:2d}. {asset['name']:8s} ${price:>10,.2f}  Funding: {funding*100:>6.4f}% APR")

        print("\n✓ Market data refreshed")

    except Exception as e:
        print(f"✗ Error getting market overview: {e}")


def show_trading_examples():
    """Show trading examples"""
    print("""
    ═══════════════════════════════════════════════════════════════

    📚 TRADING EXAMPLES

    ═══════════════════════════════════════════════════════════════

    1. PLACE A LIMIT ORDER

       from trading.hyperliquid_adapter import HyperliquidAdapter

       hl = HyperliquidAdapter(testnet=True)
       hl.connect()

       # Buy 0.01 BTC at $40,000
       hl.place_order(
           coin="BTC",
           is_buy=True,
           size=0.01,
           limit_price=40000,
           order_type="limit"
       )

    ───────────────────────────────────────────────────────────────

    2. PLACE A MARKET ORDER

       # Buy 0.01 BTC at market price
       hl.place_market_order(
           coin="BTC",
           is_buy=True,
           size=0.01,
           slippage_tolerance=0.01  # 1% slippage
       )

    ───────────────────────────────────────────────────────────────

    3. SET LEVERAGE

       # Set 5x leverage for BTC (cross margin)
       hl.update_leverage(
           coin="BTC",
           leverage=5,
           is_cross=True
       )

    ───────────────────────────────────────────────────────────────

    4. CLOSE POSITION

       # Close entire BTC position at market
       hl.close_position(coin="BTC")

       # Or close at specific price
       hl.close_position(coin="BTC", close_price=41000)

    ───────────────────────────────────────────────────────────────

    5. CHECK ACCOUNT & POSITIONS

       # Get balances
       balances = hl.get_balances()
       print(f"Account Value: ${balances['account_value']:,.2f}")

       # Get positions
       positions = hl.get_positions()
       for pos in positions:
           print(f"{pos.coin}: {pos.side} {pos.size} @ ${pos.entry_price}")

    ───────────────────────────────────────────────────────────────

    6. USE WITH STRATEGIES

       from strategies import MomentumStrategy
       from api.strategy import StrategyConfig

       # Configure strategy for crypto
       config = StrategyConfig(
           name="CryptoMomentum",
           symbols=['BTC', 'ETH', 'SOL', 'AVAX'],
           max_position_pct=0.2
       )

       strategy = MomentumStrategy(config)
       strategy.start()

    ═══════════════════════════════════════════════════════════════

    ⚠️  IMPORTANT REMINDERS:

    • Start with TESTNET before using real funds
    • Set appropriate leverage (lower is safer)
    • Use stop losses for risk management
    • Monitor funding rates for perpetuals
    • Never risk more than you can afford to lose

    ═══════════════════════════════════════════════════════════════
    """)


def main():
    """Main function"""
    print_banner()

    # Check environment
    use_testnet = check_environment()

    # Check dependencies
    if not check_dependencies():
        print("\n⚠️  Please install missing dependencies first")
        return

    # Test connection
    if not test_hyperliquid_connection(use_testnet):
        print("\n⚠️  Connection test failed")
        return

    # Show market overview
    show_market_overview()

    # Show examples
    show_trading_examples()

    print("\n✨ Setup complete! Ready for crypto trading on Hyperliquid\n")


if __name__ == "__main__":
    main()
