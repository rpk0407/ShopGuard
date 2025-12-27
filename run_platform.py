#!/usr/bin/env python3
"""
ShopGuard Trading Platform - Complete Launcher
Unified trading system with real market data, AI signals, and automation
"""
import os
import sys
import subprocess
import time

# Colors for terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_banner():
    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ███████╗██╗  ██╗ ██████╗ ██████╗  ██████╗ ██╗   ██╗ █████╗     ║
║   ██╔════╝██║  ██║██╔═══██╗██╔══██╗██╔════╝ ██║   ██║██╔══██╗    ║
║   ███████╗███████║██║   ██║██████╔╝██║  ███╗██║   ██║███████║    ║
║   ╚════██║██╔══██║██║   ██║██╔═══╝ ██║   ██║██║   ██║██╔══██║    ║
║   ███████║██║  ██║╚██████╔╝██║     ╚██████╔╝╚██████╔╝██║  ██║    ║
║   ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝      ╚═════╝  ╚═════╝ ╚═╝  ╚═╝    ║
║                                                                  ║
║              TRADING PLATFORM v2.0 - COMPLETE SYSTEM             ║
╚══════════════════════════════════════════════════════════════════╝
{Colors.END}""")

def check_dependencies():
    """Check and install required packages"""
    required = ['flask', 'requests', 'numpy']
    missing = []

    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"{Colors.YELLOW}Installing missing packages: {', '.join(missing)}{Colors.END}")
        subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing,
                      capture_output=True)
        print(f"{Colors.GREEN}Packages installed!{Colors.END}")

def show_system_info():
    """Display system configuration"""
    print(f"""
{Colors.BOLD}SYSTEM CONFIGURATION:{Colors.END}
{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.END}
  Capital:     $100.00
  Assets:      BTC, ETH, SPY, QQQ, NVDA
  Strategy:    Swing Trading (1-24 hours)
  Risk:        Moderate (3% SL, 6% TP)
  Mode:        Paper Trading
{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.END}

{Colors.BOLD}DATA SOURCES:{Colors.END}
  Prices:      CoinGecko (Crypto) + Yahoo Finance (Stocks)
  News:        Google News RSS (Financial News)
  Social:      Reddit (r/wallstreetbets, r/stocks, r/cryptocurrency)
  Technical:   RSI, Moving Averages, Bollinger Bands, Momentum

{Colors.BOLD}CORE FEATURES:{Colors.END}
  ✓ Real-time market data (no API keys needed)
  ✓ AI-powered trading signals
  ✓ Auto-trading with SL/TP
  ✓ Portfolio management
  ✓ Trade history & analytics

{Colors.BOLD}ADVANCED FEATURES (NEW!):{Colors.END}
  🧠 Multi-Agent Deep Analysis System
     • Technical Agent: RSI, MACD, Bollinger Bands, Fibonacci, Patterns
     • News Agent: Deep research, sentiment scoring, impact assessment
     • Social Agent: Reddit sentiment, FOMO/FUD detection, contrarian signals
     • Risk Agent: Position sizing, volatility analysis, Kelly Criterion
     • Fundamental Agent: Market cap, volume, supply dynamics

  💡 Opportunity Detection
     • Automated opportunity scanning
     • Full explanations of WHY to trade
     • Entry zones, targets, and hold times
     • Risk/reward analysis

  📚 Complete Trading Education
     • Trading basics to advanced strategies
     • Technical analysis lessons
     • Risk management training
     • Trading psychology
     • Crypto-specific education
""")

def run_platform():
    """Start the trading platform"""
    print_banner()
    check_dependencies()
    show_system_info()

    print(f"{Colors.GREEN}{Colors.BOLD}Starting Trading Platform...{Colors.END}")
    print(f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.END}")

    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Add to Python path
    sys.path.insert(0, script_dir)

    try:
        from shopguard_platform.app import app

        print(f"""
{Colors.GREEN}{Colors.BOLD}
  Platform is LIVE!

  Open your browser to: http://127.0.0.1:5000

  Press Ctrl+C to stop
{Colors.END}""")

        # Run Flask app
        app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Shutting down platform...{Colors.END}")
        print(f"{Colors.GREEN}Goodbye!{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_platform()
