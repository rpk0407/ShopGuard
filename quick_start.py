#!/usr/bin/env python3
"""
ShopGuard AI Trading System - Quick Start

Run this script after cloning from GitHub to set up and start the system.
No configuration needed - just run and go!

Usage:
    python quick_start.py           # Full setup + launch assistant
    python quick_start.py --check   # Check dependencies only
    python quick_start.py --test    # Run all tests
    python quick_start.py --start   # Start trading assistant
"""

import sys
import os
import subprocess
import argparse

# Colors
class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def color(text, c):
    return f"{c}{text}{C.END}"

def print_banner():
    print(color("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🤖  SHOPGUARD AI TRADING SYSTEM                           ║
    ║                                                              ║
    ║   Quick Start Setup                                          ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """, C.CYAN))

def check_python():
    """Check Python version"""
    print(color("\n[1/4] Checking Python...", C.BOLD))

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(color(f"  ✗ Python 3.8+ required (you have {version.major}.{version.minor})", C.RED))
        return False

    print(color(f"  ✓ Python {version.major}.{version.minor}.{version.micro}", C.GREEN))
    return True

def check_dependencies():
    """Check and install dependencies"""
    print(color("\n[2/4] Checking dependencies...", C.BOLD))

    required = ['numpy', 'scipy']
    missing = []

    for pkg in required:
        try:
            __import__(pkg)
            print(color(f"  ✓ {pkg} installed", C.GREEN))
        except ImportError:
            print(color(f"  ✗ {pkg} missing", C.YELLOW))
            missing.append(pkg)

    if missing:
        print(color(f"\n  Installing missing packages...", C.YELLOW))
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing,
                         check=True, capture_output=True)
            print(color(f"  ✓ Installed: {', '.join(missing)}", C.GREEN))
        except subprocess.CalledProcessError as e:
            print(color(f"  ✗ Failed to install: {e}", C.RED))
            print(color(f"  Run: pip install {' '.join(missing)}", C.YELLOW))
            return False

    return True

def check_modules():
    """Check that all trading modules load"""
    print(color("\n[3/4] Checking trading modules...", C.BOLD))

    # Add src to path
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    modules = [
        ('AI Models - Deep Learning', 'ai_models.deep_learning'),
        ('AI Models - Pattern Recognition', 'ai_models.pattern_recognition'),
        ('AI Models - Regime Classifier', 'ai_models.regime_classifier'),
        ('AI Models - Financial NLP', 'ai_models.financial_nlp'),
        ('AI Models - Reinforcement Learning', 'ai_models.reinforcement_learning'),
        ('AI Models - Self Learning', 'ai_models.self_learning'),
        ('AI Models - Ensemble', 'ai_models.ensemble'),
        ('Trading - Broker Adapters', 'trading.broker_adapters'),
        ('Trading - Live Controller', 'trading.live_controller'),
        ('Trading - AI Trader', 'trading.ai_trader'),
    ]

    all_ok = True
    for name, module in modules:
        try:
            __import__(module)
            print(color(f"  ✓ {name}", C.GREEN))
        except Exception as e:
            print(color(f"  ✗ {name}: {e}", C.RED))
            all_ok = False

    return all_ok

def run_tests():
    """Run system tests"""
    print(color("\n[4/4] Running tests...", C.BOLD))

    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    tests = [
        ("Paper Trading", test_paper_trading),
        ("AI Pattern Recognition", test_pattern_recognition),
        ("AI Regime Classifier", test_regime_classifier),
        ("AI Ensemble", test_ensemble),
    ]

    all_passed = True
    for name, test_func in tests:
        try:
            test_func()
            print(color(f"  ✓ {name}", C.GREEN))
        except Exception as e:
            print(color(f"  ✗ {name}: {e}", C.RED))
            all_passed = False

    return all_passed

def test_paper_trading():
    from trading import BrokerFactory, OrderSide
    broker = BrokerFactory.create('paper', initial_capital=10000)
    broker.connect()
    broker.set_price('TEST', 100)
    broker.submit_order('TEST', OrderSide.BUY, 1)
    account = broker.get_account()
    assert account.equity > 0
    broker.disconnect()

def test_pattern_recognition():
    import numpy as np
    from ai_models import PatternRecognitionSystem
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    ohlcv = np.column_stack([prices, prices+0.5, prices-0.5, prices, np.ones(100)*1e6])
    system = PatternRecognitionSystem()
    result = system.analyze(ohlcv)
    assert 'patterns' in result

def test_regime_classifier():
    import numpy as np
    from ai_models import MarketRegimeClassifier
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    classifier = MarketRegimeClassifier()
    regime = classifier.classify(prices)
    assert regime is not None

def test_ensemble():
    import numpy as np
    from ai_models import TradingEnsemble
    ensemble = TradingEnsemble()
    market_data = {
        'prices': 100 + np.cumsum(np.random.randn(100) * 0.5),
        'returns': np.random.randn(100) * 0.01,
        'volume': np.ones(100) * 1e6
    }
    result = ensemble.get_prediction(market_data)
    assert hasattr(result, 'final_signal')  # EnsemblePrediction object

def start_assistant():
    """Start the trading assistant"""
    print(color("\n" + "="*60, C.CYAN))
    print(color("  Starting Trading Assistant...", C.BOLD + C.CYAN))
    print(color("="*60 + "\n", C.CYAN))

    from assistant import TradingAssistant
    assistant = TradingAssistant()
    assistant.start()

def main():
    parser = argparse.ArgumentParser(description='ShopGuard AI Trading System - Quick Start')
    parser.add_argument('--check', action='store_true', help='Check dependencies only')
    parser.add_argument('--test', action='store_true', help='Run all tests')
    parser.add_argument('--start', action='store_true', help='Start trading assistant directly')
    args = parser.parse_args()

    print_banner()

    # Start directly if requested
    if args.start:
        src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
        sys.path.insert(0, src_path)
        start_assistant()
        return

    # Check Python
    if not check_python():
        print(color("\n✗ Setup failed. Please install Python 3.8+", C.RED))
        sys.exit(1)

    # Check dependencies
    if not check_dependencies():
        print(color("\n✗ Setup failed. Please install dependencies.", C.RED))
        sys.exit(1)

    # Check modules
    if not check_modules():
        print(color("\n✗ Some modules failed to load.", C.RED))
        sys.exit(1)

    # Run tests
    if not run_tests():
        print(color("\n⚠ Some tests failed, but you can still try running the system.", C.YELLOW))

    if args.check or args.test:
        print(color("\n✓ All checks complete!", C.GREEN))
        return

    # Success - offer to start
    print(color("\n" + "="*60, C.GREEN))
    print(color("  ✓ SETUP COMPLETE!", C.BOLD + C.GREEN))
    print(color("="*60, C.GREEN))
    print("""
  Your AI Trading System is ready!

  NEXT STEPS:

  1. Start the assistant:
     python assistant.py

  2. In the assistant, type:
     start          - Begin paper trading ($100k demo)
     help           - See all commands
     guide          - Step-by-step tutorial

  3. For live trading:
     Set your API keys first:
     export ALPACA_API_KEY="your_key"
     export ALPACA_SECRET_KEY="your_secret"
     Then: start live alpaca
    """)

    # Ask to start
    try:
        response = input(color("\n  Start trading assistant now? (y/n): ", C.CYAN))
        if response.lower() in ['y', 'yes', '']:
            start_assistant()
    except KeyboardInterrupt:
        print("\n  Goodbye!")

if __name__ == "__main__":
    main()
