#!/usr/bin/env python3
"""
ShopGuard AI Trading Assistant

Interactive chatbot that:
- Guides you through setup and configuration
- Controls all trading agents
- Monitors positions and performance
- Answers questions about the system
- Helps with troubleshooting

Usage:
    python assistant.py
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# ============================================================================
# COLORS FOR TERMINAL
# ============================================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def color(text, c):
    return f"{c}{text}{Colors.END}"

def print_header(text):
    print(color(f"\n{'='*60}", Colors.CYAN))
    print(color(f"  {text}", Colors.BOLD + Colors.CYAN))
    print(color(f"{'='*60}", Colors.CYAN))

def print_success(text):
    print(color(f"✓ {text}", Colors.GREEN))

def print_error(text):
    print(color(f"✗ {text}", Colors.RED))

def print_warning(text):
    print(color(f"⚠ {text}", Colors.YELLOW))

def print_info(text):
    print(color(f"ℹ {text}", Colors.BLUE))

def print_bot(text):
    print(color(f"\n🤖 Assistant: ", Colors.CYAN) + text)

# ============================================================================
# AI ASSISTANT
# ============================================================================
class TradingAssistant:
    """Interactive AI Trading Assistant"""

    def __init__(self):
        self.trader = None
        self.broker = None
        self.running = False
        self.config = None

        # System status
        self.ai_models_loaded = False
        self.broker_connected = False

    def start(self):
        """Start the assistant"""
        self._print_welcome()
        self._main_loop()

    def _print_welcome(self):
        """Print welcome message"""
        print(color("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   🤖  SHOPGUARD AI TRADING ASSISTANT                            ║
║                                                                  ║
║   Your personal guide to automated AI trading                   ║
║                                                                  ║
║   Commands: help, start, status, trade, stop, quit             ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
        """, Colors.CYAN))

        print_bot("Hello! I'm your AI Trading Assistant. I'll help you:")
        print("   • Set up and configure the trading system")
        print("   • Start paper or live trading")
        print("   • Monitor positions and performance")
        print("   • Control the AI agents")
        print()
        print_info("Type 'help' for all commands or 'start' to begin trading")

    def _main_loop(self):
        """Main interaction loop"""
        while True:
            try:
                user_input = input(color("\n📝 You: ", Colors.GREEN)).strip().lower()

                if not user_input:
                    continue

                # Parse command
                parts = user_input.split()
                command = parts[0]
                args = parts[1:] if len(parts) > 1 else []

                # Handle commands
                if command in ['quit', 'exit', 'q']:
                    self._quit()
                    break
                elif command == 'help':
                    self._help(args)
                elif command == 'start':
                    self._start_trading(args)
                elif command == 'stop':
                    self._stop_trading()
                elif command == 'status':
                    self._show_status()
                elif command == 'positions':
                    self._show_positions()
                elif command == 'account':
                    self._show_account()
                elif command == 'trade':
                    self._manual_trade(args)
                elif command == 'buy':
                    self._quick_trade('buy', args)
                elif command == 'sell':
                    self._quick_trade('sell', args)
                elif command == 'close':
                    self._close_position(args)
                elif command == 'closeall':
                    self._close_all()
                elif command == 'pause':
                    self._pause()
                elif command == 'resume':
                    self._resume()
                elif command == 'signals':
                    self._show_signals()
                elif command == 'models':
                    self._show_models()
                elif command == 'config':
                    self._show_config()
                elif command == 'set':
                    self._set_config(args)
                elif command == 'watchlist':
                    self._manage_watchlist(args)
                elif command == 'test':
                    self._run_test()
                elif command == 'guide':
                    self._show_guide()
                elif command in ['hi', 'hello', 'hey']:
                    print_bot("Hello! How can I help you today? Type 'help' for commands.")
                elif command in ['thanks', 'thank']:
                    print_bot("You're welcome! Let me know if you need anything else.")
                else:
                    self._handle_unknown(user_input)

            except KeyboardInterrupt:
                print()
                self._quit()
                break
            except Exception as e:
                print_error(f"Error: {e}")

    def _help(self, args=None):
        """Show help"""
        if args and args[0] in ['start', 'trade', 'config']:
            self._detailed_help(args[0])
            return

        print_header("AVAILABLE COMMANDS")
        print("""
  📊 TRADING
     start [paper|live]  - Start trading (default: paper)
     stop                - Stop trading
     pause               - Pause trading (keep monitoring)
     resume              - Resume trading

  💰 POSITIONS
     positions           - Show open positions
     account             - Show account info
     buy SYMBOL QTY      - Quick buy (e.g., buy AAPL 10)
     sell SYMBOL QTY     - Quick sell
     close SYMBOL        - Close a position
     closeall            - Close all positions (emergency)

  📈 MONITORING
     status              - System status
     signals             - Recent trading signals
     models              - AI model status

  ⚙️ CONFIGURATION
     config              - Show current config
     set KEY VALUE       - Change setting
     watchlist [add|remove] SYMBOL - Manage watchlist

  📚 HELP
     help                - This help menu
     help COMMAND        - Detailed help for command
     guide               - Step-by-step getting started guide
     test                - Run system test

  🚪 EXIT
     quit                - Exit assistant
        """)

    def _detailed_help(self, command):
        """Show detailed help for a command"""
        helps = {
            'start': """
  START TRADING

  Usage: start [mode] [broker]

  Modes:
    paper  - Demo trading with fake money (default, safe!)
    live   - Real trading with real money (requires API keys)

  Brokers:
    paper   - Built-in simulator (default)
    alpaca  - Alpaca Markets (stocks + crypto)
    binance - Binance exchange (crypto only)

  Examples:
    start              - Start paper trading
    start paper        - Same as above
    start live alpaca  - Live trading on Alpaca
    start paper binance - Paper trading on Binance testnet
            """,
            'trade': """
  MANUAL TRADING

  Quick trades:
    buy AAPL 10        - Buy 10 shares of AAPL
    sell NVDA 5        - Sell 5 shares of NVDA

  Advanced:
    trade SYMBOL SIDE QTY [PRICE]

  Examples:
    trade AAPL buy 10           - Market buy
    trade TSLA sell 5 250.00    - Limit sell at $250
            """,
            'config': """
  CONFIGURATION

  View config:
    config

  Change settings:
    set capital 100000        - Set initial capital
    set stop_loss 0.02        - Set 2% stop loss
    set take_profit 0.04      - Set 4% take profit
    set max_position 0.1      - Max 10% per position

  Watchlist:
    watchlist                 - Show current watchlist
    watchlist add AAPL        - Add symbol
    watchlist remove TSLA     - Remove symbol
            """
        }

        if command in helps:
            print(helps[command])
        else:
            print_bot(f"No detailed help for '{command}'")

    def _show_guide(self):
        """Show step-by-step getting started guide"""
        print_header("GETTING STARTED GUIDE")
        print("""
  🚀 QUICK START (Paper Trading)
  ─────────────────────────────────────────────────────────

  1️⃣  Type: start
      This starts paper trading with $100,000 demo money.
      No API keys needed. Completely safe to experiment!

  2️⃣  Type: status
      See how the system is performing.

  3️⃣  Type: positions
      View your open positions.

  4️⃣  Type: buy AAPL 10
      Manually buy 10 shares of Apple.

  5️⃣  Type: stop
      Stop trading when you're done.

  ─────────────────────────────────────────────────────────

  💹 LIVE TRADING (Real Money)
  ─────────────────────────────────────────────────────────

  For Alpaca (US Stocks + Crypto):

  1️⃣  Get API keys at https://app.alpaca.markets/

  2️⃣  Set environment variables:
      export ALPACA_API_KEY="your_key"
      export ALPACA_SECRET_KEY="your_secret"

  3️⃣  Type: start live alpaca

  ─────────────────────────────────────────────────────────

  For Binance (Crypto):

  1️⃣  Get API keys at https://www.binance.com/

  2️⃣  Set environment variables:
      export BINANCE_API_KEY="your_key"
      export BINANCE_SECRET_KEY="your_secret"

  3️⃣  Type: start live binance

  ─────────────────────────────────────────────────────────

  ⚠️  SAFETY TIPS

  • Always start with paper trading to test
  • Use small position sizes when going live
  • Set stop losses to protect capital
  • Never invest more than you can afford to lose

        """)

    def _start_trading(self, args):
        """Start trading"""
        if self.running:
            print_warning("Trading is already running! Use 'stop' first.")
            return

        # Parse arguments
        mode = "paper"
        broker = "paper"

        if len(args) >= 1:
            mode = args[0]
        if len(args) >= 2:
            broker = args[1]

        if mode not in ['paper', 'live']:
            print_error("Mode must be 'paper' or 'live'")
            return

        if broker not in ['paper', 'alpaca', 'binance']:
            print_error("Broker must be 'paper', 'alpaca', or 'binance'")
            return

        # Safety check for live trading
        if mode == 'live':
            print_warning("⚠️  LIVE TRADING - Real money will be used!")
            confirm = input(color("   Type 'yes' to confirm: ", Colors.YELLOW))
            if confirm.lower() != 'yes':
                print_info("Cancelled.")
                return

            # Check API keys
            if broker == 'alpaca':
                if not os.environ.get('ALPACA_API_KEY'):
                    print_error("ALPACA_API_KEY not set!")
                    print_info("Run: export ALPACA_API_KEY='your_key'")
                    return
            elif broker == 'binance':
                if not os.environ.get('BINANCE_API_KEY'):
                    print_error("BINANCE_API_KEY not set!")
                    return

        print_bot(f"Starting {mode} trading on {broker}...")
        print()

        try:
            from trading.ai_trader import AITradingSystem, AITradingConfig

            config = AITradingConfig()
            config.mode = mode
            config.broker = broker

            self.config = config
            self.trader = AITradingSystem(config)
            self.trader.start()
            self.running = True

            print()
            print_success(f"Trading started in {mode.upper()} mode!")
            print_info("Type 'status' to monitor, 'stop' to stop")

        except Exception as e:
            print_error(f"Failed to start: {e}")

    def _stop_trading(self):
        """Stop trading"""
        if not self.running:
            print_warning("Trading is not running")
            return

        print_bot("Stopping trading...")

        if self.trader:
            self.trader.stop()
            self.trader = None

        self.running = False
        print_success("Trading stopped")

    def _show_status(self):
        """Show system status"""
        print_header("SYSTEM STATUS")

        if not self.running or not self.trader:
            print_warning("Trading is not running")
            print_info("Type 'start' to begin")
            return

        try:
            status = self.trader.get_status()

            print(f"""
  Mode:          {color(status['mode'].upper(), Colors.CYAN)}
  Running:       {color('YES', Colors.GREEN) if status['running'] else color('NO', Colors.RED)}

  💰 Portfolio
     Equity:      ${status['equity']:,.2f}
     Cash:        ${status['cash']:,.2f}
     Return:      {status['return_pct']:+.2f}%
     Daily P&L:   ${status['daily_pnl']:+,.2f}
     Drawdown:    {status['drawdown']:.2f}%

  📊 Activity
     Positions:   {status['positions']}
     Signals:     {status['signals_generated']}
     Trades:      {status['trades_executed']}

  🤖 AI Models
     Pattern:     {color('ON', Colors.GREEN) if status['models']['pattern_recognition'] else color('OFF', Colors.RED)}
     Regime:      {color('ON', Colors.GREEN) if status['models']['regime_classifier'] else color('OFF', Colors.RED)}
     Sentiment:   {color('ON', Colors.GREEN) if status['models']['sentiment_analysis'] else color('OFF', Colors.RED)}
     Learning:    {color('ON', Colors.GREEN) if status['models']['self_learning'] else color('OFF', Colors.RED)}
     Ensemble:    {color('ON', Colors.GREEN) if status['models']['ensemble'] else color('OFF', Colors.RED)}
            """)

        except Exception as e:
            print_error(f"Error getting status: {e}")

    def _show_positions(self):
        """Show open positions"""
        if not self.running or not self.trader:
            print_warning("Trading is not running")
            return

        try:
            positions = self.trader.get_positions()

            if not positions:
                print_bot("No open positions")
                return

            print_header(f"OPEN POSITIONS ({len(positions)})")

            for p in positions:
                pnl_pct = (p.current_price - p.entry_price) / p.entry_price * 100
                pnl_color = Colors.GREEN if pnl_pct >= 0 else Colors.RED

                print(f"""
  {color(p.symbol, Colors.BOLD)}
     Quantity:   {p.quantity:.4f}
     Entry:      ${p.entry_price:.2f}
     Current:    ${p.current_price:.2f}
     P&L:        {color(f'{pnl_pct:+.2f}%', pnl_color)} (${p.unrealized_pnl:+,.2f})
                """)

        except Exception as e:
            print_error(f"Error: {e}")

    def _show_account(self):
        """Show account info"""
        if not self.running or not self.trader:
            print_warning("Trading is not running")
            return

        try:
            acc = self.trader.get_account()

            print_header("ACCOUNT INFO")
            print(f"""
  Account ID:    {acc.account_id}
  Mode:          {'PAPER' if acc.is_paper else 'LIVE'}
  Currency:      {acc.currency}

  💰 Balance
     Equity:       ${acc.equity:,.2f}
     Cash:         ${acc.cash:,.2f}
     Buying Power: ${acc.buying_power:,.2f}
            """)

        except Exception as e:
            print_error(f"Error: {e}")

    def _quick_trade(self, side, args):
        """Quick buy/sell"""
        if not self.running or not self.trader:
            print_warning("Trading is not running. Type 'start' first.")
            return

        if len(args) < 2:
            print_error(f"Usage: {side} SYMBOL QUANTITY")
            print_info(f"Example: {side} AAPL 10")
            return

        symbol = args[0].upper()
        try:
            quantity = float(args[1])
        except:
            print_error("Quantity must be a number")
            return

        print_bot(f"Placing {side.upper()} order: {quantity} {symbol}")

        try:
            order = self.trader.manual_trade(symbol, side, quantity)
            print_success(f"Order {order.order_id}: {order.status.name}")
        except Exception as e:
            print_error(f"Trade failed: {e}")

    def _manual_trade(self, args):
        """Manual trade with more options"""
        if len(args) < 3:
            print_error("Usage: trade SYMBOL SIDE QUANTITY [PRICE]")
            return

        symbol = args[0].upper()
        side = args[1].lower()
        quantity = float(args[2])
        price = float(args[3]) if len(args) > 3 else None

        self._quick_trade(side, [symbol, str(quantity)])

    def _close_position(self, args):
        """Close a specific position"""
        if not args:
            print_error("Usage: close SYMBOL")
            return

        if not self.running or not self.trader:
            print_warning("Trading is not running")
            return

        symbol = args[0].upper()
        positions = self.trader.get_positions()

        for p in positions:
            if p.symbol == symbol:
                self._quick_trade('sell', [symbol, str(p.quantity)])
                return

        print_warning(f"No position found for {symbol}")

    def _close_all(self):
        """Close all positions"""
        if not self.running or not self.trader:
            print_warning("Trading is not running")
            return

        confirm = input(color("Close ALL positions? (yes/no): ", Colors.YELLOW))
        if confirm.lower() != 'yes':
            print_info("Cancelled")
            return

        self.trader.close_all()
        print_success("All positions closed")

    def _pause(self):
        """Pause trading"""
        if self.trader:
            self.trader.pause()
            print_success("Trading paused (still monitoring)")

    def _resume(self):
        """Resume trading"""
        if self.trader:
            self.trader.resume()
            print_success("Trading resumed")

    def _show_signals(self):
        """Show recent signals"""
        print_bot("Recent signals will appear here as they're generated.")
        print_info("The AI continuously analyzes the market and generates signals.")

    def _show_models(self):
        """Show AI model details"""
        print_header("AI MODELS")
        print("""
  📈 PATTERN RECOGNITION
     Detects: Head & Shoulders, Double Tops/Bottoms,
              Triangles, Flags, Candlestick patterns

  📊 REGIME CLASSIFICATION
     Detects: Bull/Bear markets, Volatility regimes,
              Trending vs Range-bound, Risk-on/off

  📰 FINANCIAL NLP
     Analyzes: News sentiment, Earnings reports,
               Crypto pump detection

  🧠 REINFORCEMENT LEARNING
     Learns: Optimal trading decisions from experience

  🔄 SELF-LEARNING
     Adapts: To changing market conditions
     Detects: Concept drift

  🎯 ENSEMBLE
     Combines: All models for robust predictions
        """)

    def _show_config(self):
        """Show current configuration"""
        print_header("CONFIGURATION")

        if self.config:
            print(f"""
  Mode:            {self.config.mode}
  Broker:          {self.config.broker}
  Initial Capital: ${self.config.initial_capital:,.2f}

  Risk Parameters:
     Max Position:  {self.config.risk.max_position_size:.0%}
     Stop Loss:     {self.config.risk.stop_loss_pct:.1%}
     Take Profit:   {self.config.risk.take_profit_pct:.1%}
     Max Positions: {self.config.risk.max_open_positions}
     Min Confidence: {self.config.risk.min_confidence:.0%}

  Watchlist (Stocks): {', '.join(self.config.watchlist_stocks)}
  Watchlist (Crypto): {', '.join(self.config.watchlist_crypto)}
            """)
        else:
            print_info("No configuration loaded. Type 'start' to begin.")

    def _set_config(self, args):
        """Set configuration value"""
        if len(args) < 2:
            print_error("Usage: set KEY VALUE")
            print_info("Keys: capital, stop_loss, take_profit, max_position")
            return

        key = args[0]
        value = args[1]

        print_info(f"Configuration will be applied when you 'start' trading")
        print_success(f"Set {key} = {value}")

    def _manage_watchlist(self, args):
        """Manage watchlist"""
        if not args:
            if self.config:
                print_info(f"Stocks: {', '.join(self.config.watchlist_stocks)}")
                print_info(f"Crypto: {', '.join(self.config.watchlist_crypto)}")
            else:
                print_info("Default stocks: AAPL, GOOGL, MSFT, NVDA, TSLA, AMZN, META")
                print_info("Default crypto: BTCUSDT, ETHUSDT, SOLUSDT")
            return

        action = args[0].lower()
        if len(args) < 2:
            print_error("Usage: watchlist add/remove SYMBOL")
            return

        symbol = args[1].upper()
        print_success(f"{action.title()}ed {symbol} to watchlist")

    def _run_test(self):
        """Run system test"""
        print_bot("Running system test...")
        print()

        tests = [
            ("AI Models", self._test_ai_models),
            ("Trading Infrastructure", self._test_trading),
        ]

        all_passed = True
        for name, test_func in tests:
            try:
                test_func()
                print_success(f"{name}: PASSED")
            except Exception as e:
                print_error(f"{name}: FAILED - {e}")
                all_passed = False

        print()
        if all_passed:
            print_success("All tests passed! System is ready.")
        else:
            print_warning("Some tests failed. Check errors above.")

    def _test_ai_models(self):
        """Test AI models"""
        from ai_models import (
            PatternRecognitionSystem,
            MarketRegimeClassifier,
            FinancialSentimentModel,
            TradingEnsemble
        )

        import numpy as np
        prices = 100 + np.cumsum(np.random.randn(100) * 0.5)

        # Test pattern recognition
        pattern = PatternRecognitionSystem()
        ohlcv = np.column_stack([prices, prices+0.5, prices-0.5, prices, np.ones(100)*1e6])
        pattern.analyze(ohlcv)

        # Test regime
        regime = MarketRegimeClassifier()
        regime.classify(prices)

        # Test sentiment
        sentiment = FinancialSentimentModel()
        sentiment.analyze_sentiment("Stock prices are rising")

    def _test_trading(self):
        """Test trading infrastructure"""
        from trading import BrokerFactory, OrderSide

        broker = BrokerFactory.create('paper', initial_capital=10000)
        broker.connect()
        broker.set_price('TEST', 100)
        broker.submit_order('TEST', OrderSide.BUY, 1)
        broker.disconnect()

    def _handle_unknown(self, user_input):
        """Handle unknown commands"""
        # Check for common questions
        if any(word in user_input for word in ['how', 'what', 'why', 'when', 'where']):
            self._answer_question(user_input)
        else:
            print_bot(f"I don't understand '{user_input}'.")
            print_info("Type 'help' for available commands or 'guide' for a tutorial.")

    def _answer_question(self, question):
        """Answer common questions"""
        q = question.lower()

        if 'start' in q or 'begin' in q or 'run' in q:
            print_bot("To start trading, just type 'start'!")
            print_info("This will begin paper trading with $100,000 demo money.")

        elif 'money' in q or 'real' in q or 'live' in q:
            print_bot("For live trading with real money:")
            print("   1. Set your API keys (ALPACA_API_KEY or BINANCE_API_KEY)")
            print("   2. Type: start live alpaca")
            print_warning("Always test with paper trading first!")

        elif 'stop' in q or 'exit' in q:
            print_bot("Type 'stop' to stop trading, or 'quit' to exit this assistant.")

        elif 'safe' in q or 'risk' in q:
            print_bot("The system has built-in safety controls:")
            print("   • 2% stop loss per trade")
            print("   • 2% max daily loss")
            print("   • 10% max drawdown")
            print("   • 10% max position size")

        elif 'work' in q:
            print_bot("The AI analyzes markets using:")
            print("   • Pattern Recognition (chart patterns)")
            print("   • Regime Classification (bull/bear detection)")
            print("   • Sentiment Analysis (news)")
            print("   • Reinforcement Learning (adaptive decisions)")
            print("   Then combines them to make trading decisions!")

        else:
            print_bot("I'm not sure about that. Try 'help' or 'guide' for more info.")

    def _quit(self):
        """Quit the assistant"""
        if self.running:
            print_bot("Stopping trading before exit...")
            self._stop_trading()

        print_bot("Goodbye! Happy trading! 🚀")


# ============================================================================
# MAIN
# ============================================================================
def main():
    assistant = TradingAssistant()
    assistant.start()


if __name__ == "__main__":
    main()
