#!/usr/bin/env python3
"""
AI Trading System - Live/Paper Trading Runner

This script starts the complete AI trading system with:
- All specialized AI models (Pattern Recognition, Regime, NLP, etc.)
- Real broker integration (Paper, Alpaca, Binance)
- Automated order execution
- Risk management

USAGE:
    # Paper Trading (Demo) - Safe to test!
    python run_live_trading.py --mode paper --capital 100000

    # Alpaca Paper Trading
    python run_live_trading.py --mode paper --broker alpaca

    # Binance Testnet
    python run_live_trading.py --mode paper --broker binance

    # LIVE TRADING (Be careful!)
    python run_live_trading.py --mode live --broker alpaca

ENVIRONMENT VARIABLES (for real brokers):
    ALPACA_API_KEY      - Alpaca API Key
    ALPACA_SECRET_KEY   - Alpaca Secret Key
    BINANCE_API_KEY     - Binance API Key
    BINANCE_SECRET_KEY  - Binance Secret Key
"""

import sys
import os
import argparse
import signal

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from trading.ai_trader import AITradingSystem, AITradingConfig


def main():
    parser = argparse.ArgumentParser(
        description='AI Trading System - Automated Trading with AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Paper trading with $100,000:
    python run_live_trading.py --mode paper --capital 100000

  Paper trading specific stocks:
    python run_live_trading.py --symbols AAPL NVDA TSLA

  Alpaca paper trading:
    python run_live_trading.py --broker alpaca --mode paper

  Live trading (CAUTION!):
    python run_live_trading.py --broker alpaca --mode live
        """
    )

    parser.add_argument('--mode', choices=['paper', 'live'], default='paper',
                        help='Trading mode (default: paper)')
    parser.add_argument('--broker', choices=['paper', 'alpaca', 'binance'], default='paper',
                        help='Broker to use (default: paper)')
    parser.add_argument('--capital', type=float, default=100000,
                        help='Initial capital for paper trading (default: 100000)')
    parser.add_argument('--symbols', nargs='+', default=None,
                        help='Symbols to trade (default: preset list)')
    parser.add_argument('--config', type=str, default=None,
                        help='Path to config JSON file')

    # Risk parameters
    parser.add_argument('--max-position', type=float, default=0.1,
                        help='Max position size as fraction of equity (default: 0.1)')
    parser.add_argument('--stop-loss', type=float, default=0.02,
                        help='Stop loss percentage (default: 0.02)')
    parser.add_argument('--take-profit', type=float, default=0.04,
                        help='Take profit percentage (default: 0.04)')
    parser.add_argument('--max-positions', type=int, default=10,
                        help='Maximum number of open positions (default: 10)')

    args = parser.parse_args()

    # Create config
    if args.config:
        config = AITradingConfig.from_file(args.config)
    else:
        config = AITradingConfig()

    # Override with command line args
    config.mode = args.mode
    config.broker = args.broker
    config.initial_capital = args.capital

    if args.symbols:
        if args.broker == 'binance':
            config.watchlist_crypto = args.symbols
        else:
            config.watchlist_stocks = args.symbols

    config.risk.max_position_size = args.max_position
    config.risk.stop_loss_pct = args.stop_loss
    config.risk.take_profit_pct = args.take_profit
    config.risk.max_open_positions = args.max_positions

    # Safety check for live trading
    if config.mode == 'live':
        print("\n" + "!" * 60)
        print("    WARNING: LIVE TRADING MODE")
        print("    Real money will be used!")
        print("!" * 60)

        confirm = input("\nType 'I UNDERSTAND' to continue: ")
        if confirm != 'I UNDERSTAND':
            print("Aborted.")
            sys.exit(1)

        # Check API keys
        if config.broker == 'alpaca':
            if not config.alpaca_key or not config.alpaca_secret:
                print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
                sys.exit(1)
        elif config.broker == 'binance':
            if not config.binance_key or not config.binance_secret:
                print("ERROR: BINANCE_API_KEY and BINANCE_SECRET_KEY must be set")
                sys.exit(1)

    # Print configuration
    print("\n" + "=" * 60)
    print("          AI TRADING SYSTEM - CONFIGURATION")
    print("=" * 60)
    print(f"   Mode: {config.mode.upper()}")
    print(f"   Broker: {config.broker.upper()}")
    print(f"   Initial Capital: ${config.initial_capital:,.2f}")
    print(f"   Max Position Size: {config.risk.max_position_size:.0%}")
    print(f"   Stop Loss: {config.risk.stop_loss_pct:.1%}")
    print(f"   Take Profit: {config.risk.take_profit_pct:.1%}")
    print(f"   Max Positions: {config.risk.max_open_positions}")

    if config.broker in ['paper', 'alpaca']:
        print(f"   Stocks: {', '.join(config.watchlist_stocks)}")
    if config.broker in ['paper', 'binance']:
        print(f"   Crypto: {', '.join(config.watchlist_crypto)}")

    print("=" * 60 + "\n")

    # Create and start system
    trader = AITradingSystem(config)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n[SYSTEM] Shutting down...")
        trader.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        trader.start()

        # Interactive loop
        print("\nCommands: status, positions, account, pause, resume, close-all, quit")

        while trader.running:
            try:
                cmd = input("> ").strip().lower()

                if cmd == 'status':
                    status = trader.get_status()
                    print(f"\nRunning: {status['running']}")
                    print(f"Mode: {status['mode']}")
                    print(f"Equity: ${status['equity']:,.2f}")
                    print(f"Return: {status['return_pct']:.2f}%")
                    print(f"Positions: {status['positions']}")
                    print(f"Trades: {status['trades_executed']}")
                    print(f"Signals: {status['signals_generated']}\n")

                elif cmd == 'positions':
                    positions = trader.get_positions()
                    if not positions:
                        print("\nNo open positions\n")
                    else:
                        print(f"\n{len(positions)} Position(s):")
                        for p in positions:
                            pnl_pct = (p.current_price - p.entry_price) / p.entry_price * 100
                            print(f"   {p.symbol}: {p.quantity:.4f} @ ${p.entry_price:.2f} "
                                  f"-> ${p.current_price:.2f} ({pnl_pct:+.2f}%)")
                        print()

                elif cmd == 'account':
                    acc = trader.get_account()
                    print(f"\nAccount: {acc.account_id}")
                    print(f"Equity: ${acc.equity:,.2f}")
                    print(f"Cash: ${acc.cash:,.2f}")
                    print(f"Buying Power: ${acc.buying_power:,.2f}")
                    print(f"Paper Mode: {acc.is_paper}\n")

                elif cmd == 'pause':
                    trader.pause()

                elif cmd == 'resume':
                    trader.resume()

                elif cmd == 'close-all':
                    confirm = input("Close all positions? (yes/no): ")
                    if confirm.lower() == 'yes':
                        trader.close_all()

                elif cmd in ['quit', 'exit', 'q']:
                    break

                elif cmd:
                    print("Unknown command. Try: status, positions, account, pause, resume, close-all, quit")

            except EOFError:
                break

    except Exception as e:
        print(f"\n[ERROR] {e}")

    finally:
        trader.stop()


if __name__ == "__main__":
    main()
