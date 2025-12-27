#!/usr/bin/env python3
"""
Quick Start Demo - Run this to see the infrastructure in action!

Usage:
    python run_demo.py [component]

Components:
    all        - Run all demos (default)
    math       - Mathematical models (GARCH, Regime Switching)
    hft        - High-frequency trading components
    portfolio  - Portfolio optimization
    execution  - Execution algorithms
    backtest   - Backtesting engine
    monitor    - Monitoring & alerts
    engine     - Trading engine

Examples:
    python run_demo.py           # Run all demos
    python run_demo.py math      # Run math models demo
    python run_demo.py portfolio # Run portfolio optimization demo
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    if len(sys.argv) > 1:
        component = sys.argv[1].lower()
    else:
        component = 'all'

    from examples.demo_full_system import (
        demo_mathematical_models,
        demo_signal_processing,
        demo_ai_models,
        demo_hft_components,
        demo_portfolio_optimization,
        demo_execution,
        demo_backtesting,
        demo_monitoring,
        demo_trading_engine,
        demo_alternative_data,
        print_header
    )

    demos = {
        'math': [demo_mathematical_models, demo_signal_processing],
        'ai': [demo_ai_models],
        'hft': [demo_hft_components],
        'portfolio': [demo_portfolio_optimization],
        'execution': [demo_execution],
        'backtest': [demo_backtesting],
        'monitor': [demo_monitoring],
        'engine': [demo_trading_engine],
        'altdata': [demo_alternative_data],
        'all': [
            demo_mathematical_models,
            demo_signal_processing,
            demo_ai_models,
            demo_hft_components,
            demo_portfolio_optimization,
            demo_execution,
            demo_backtesting,
            demo_monitoring,
            demo_trading_engine,
            demo_alternative_data
        ]
    }

    if component not in demos:
        print(f"Unknown component: {component}")
        print(f"Available: {', '.join(demos.keys())}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("  QUANTITATIVE TRADING INFRASTRUCTURE")
    print("=" * 70)

    for demo_fn in demos[component]:
        try:
            demo_fn()
        except Exception as e:
            print(f"\n❌ Error in {demo_fn.__name__}: {e}")

    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
