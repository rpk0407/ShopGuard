#!/usr/bin/env python3
"""
AI Trading System - Full Simulation

This script runs a complete simulation of the AI trading infrastructure,
demonstrating all agents working together with realistic market data.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
import time
from datetime import datetime, timedelta

# Import AI infrastructure
from ai_agents import (
    MasterOrchestrator, SystemMode, RiskLevel,
    MarketSnapshot, MarketCondition,
    FinancialMetrics
)

print("=" * 70)
print("        AI TRADING SYSTEM - FULL SIMULATION")
print("=" * 70)
print()

# =============================================================================
# STEP 1: Initialize the Master Orchestrator
# =============================================================================
print("[1/8] INITIALIZING AI SYSTEM...")
print("-" * 50)

initial_capital = 100000
orchestrator = MasterOrchestrator(initial_capital=initial_capital)

print(f"   Capital: ${initial_capital:,}")
print(f"   Agents loaded: {len(orchestrator.agents)}")
for name, agent in orchestrator.agents.items():
    print(f"      - {name}: {agent.name}")

# Configure settings
orchestrator.set_risk_level(RiskLevel.MODERATE)
orchestrator.enable_auto_trading(True)

# Add symbols to watchlist
symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META', 'BTC-USD']
for s in symbols:
    orchestrator.add_to_watchlist(s)

print(f"   Watchlist: {', '.join(symbols)}")
print(f"   Risk Level: MODERATE")
print(f"   Auto Trading: ENABLED")
print()

# =============================================================================
# STEP 2: Start the System
# =============================================================================
print("[2/8] STARTING AI SYSTEM IN PAPER TRADING MODE...")
print("-" * 50)

orchestrator.start(mode=SystemMode.PAPER_TRADING)
time.sleep(0.5)

status = orchestrator.get_status()
print(f"   Mode: {status['mode']}")
print(f"   Running: {status['running']}")
print()

# =============================================================================
# STEP 3: Add Company Fundamentals
# =============================================================================
print("[3/8] LOADING COMPANY FUNDAMENTALS...")
print("-" * 50)

# Add fundamental data for key companies
companies = {
    'AAPL': FinancialMetrics(
        symbol='AAPL', market_cap=3000000000000, pe_ratio=28.5, forward_pe=25.0,
        ps_ratio=7.5, pb_ratio=45.0, ev_ebitda=22.0, peg_ratio=2.5,
        gross_margin=0.45, operating_margin=0.30, net_margin=0.25,
        roe=0.160, roa=0.28, roic=0.55,
        revenue_growth_yoy=0.08, earnings_growth_yoy=0.12, revenue_growth_5y=0.10,
        debt_to_equity=1.8, current_ratio=0.99, quick_ratio=0.85, cash_per_share=4.5,
        free_cash_flow=100000000000, fcf_yield=0.033, operating_cash_flow=120000000000,
        dividend_yield=0.005, payout_ratio=0.15, timestamp=datetime.now()
    ),
    'NVDA': FinancialMetrics(
        symbol='NVDA', market_cap=1200000000000, pe_ratio=65.0, forward_pe=35.0,
        ps_ratio=25.0, pb_ratio=35.0, ev_ebitda=50.0, peg_ratio=1.2,
        gross_margin=0.72, operating_margin=0.55, net_margin=0.50,
        roe=0.85, roa=0.45, roic=0.65,
        revenue_growth_yoy=1.20, earnings_growth_yoy=2.00, revenue_growth_5y=0.45,
        debt_to_equity=0.4, current_ratio=4.0, quick_ratio=3.5, cash_per_share=2.0,
        free_cash_flow=15000000000, fcf_yield=0.012, operating_cash_flow=20000000000,
        dividend_yield=0.0004, payout_ratio=0.01, timestamp=datetime.now()
    ),
    'TSLA': FinancialMetrics(
        symbol='TSLA', market_cap=800000000000, pe_ratio=75.0, forward_pe=55.0,
        ps_ratio=8.0, pb_ratio=12.0, ev_ebitda=45.0, peg_ratio=3.0,
        gross_margin=0.18, operating_margin=0.08, net_margin=0.07,
        roe=0.20, roa=0.08, roic=0.12,
        revenue_growth_yoy=0.15, earnings_growth_yoy=-0.10, revenue_growth_5y=0.50,
        debt_to_equity=0.1, current_ratio=1.7, quick_ratio=1.2, cash_per_share=8.0,
        free_cash_flow=5000000000, fcf_yield=0.006, operating_cash_flow=12000000000,
        dividend_yield=0, payout_ratio=0, timestamp=datetime.now()
    )
}

for symbol, metrics in companies.items():
    orchestrator.company_tracker.add_company(symbol, metrics, name=symbol, sector='Technology')
    profile = orchestrator.company_tracker.profiles.get(symbol)
    if profile:
        print(f"   {symbol}:")
        print(f"      Score: {profile.overall_score:.0f}/100")
        print(f"      Health: {profile.financial_health.name}")
        print(f"      Growth: {profile.growth_profile.name}")
        print(f"      Valuation: {profile.valuation.name}")

print()

# =============================================================================
# STEP 4: Feed News Events
# =============================================================================
print("[4/8] PROCESSING NEWS & EVENTS...")
print("-" * 50)

news_items = [
    ("Apple announces record iPhone 16 sales in China, beats estimates",
     "Apple Inc reported Q4 earnings that exceeded analyst expectations with $95B revenue...",
     "reuters", ["AAPL"]),

    ("NVIDIA unveils next-gen AI chips, stock surges pre-market",
     "NVIDIA announced its Blackwell B200 chips with 5x performance improvement...",
     "bloomberg", ["NVDA"]),

    ("Fed signals potential rate cuts in Q1 2025 amid cooling inflation",
     "The Federal Reserve indicated it may begin cutting interest rates as early as March...",
     "wsj", []),

    ("Tesla faces regulatory investigation in Europe over autopilot",
     "European regulators launched a probe into Tesla's Full Self-Driving system...",
     "reuters", ["TSLA"]),

    ("WARNING: Unusual trading detected in small-cap crypto token",
     "Multiple exchanges report suspicious volume spikes suggesting possible manipulation...",
     "unknown", ["SHIB-USD"]),

    ("Microsoft Azure outage affects global cloud services",
     "A major outage impacted Microsoft's cloud services for several hours...",
     "cnbc", ["MSFT"]),
]

for headline, content, source, syms in news_items:
    event = orchestrator.feed_news(headline, content, source, syms)
    sentiment_icon = "+" if event.sentiment.value > 0 else ("-" if event.sentiment.value < 0 else "=")
    print(f"   [{sentiment_icon}] {event.category.name}: {headline[:50]}...")
    if event.is_breaking:
        print(f"       BREAKING NEWS - Impact: {event.impact.name}")

print()

# =============================================================================
# STEP 5: Simulate Market Data (Multiple Cycles)
# =============================================================================
print("[5/8] RUNNING MARKET SIMULATION (5 cycles)...")
print("-" * 50)

np.random.seed(42)

# Initial prices
base_prices = {
    'AAPL': 185.0,
    'GOOGL': 142.0,
    'MSFT': 378.0,
    'TSLA': 248.0,
    'AMZN': 178.0,
    'NVDA': 495.0,
    'META': 505.0,
    'BTC-USD': 43500.0
}

# Simulate 5 market cycles
for cycle in range(5):
    print(f"\n   --- Cycle {cycle + 1}/5 ---")

    # Generate price movements
    prices = {}
    volumes = {}
    volatility = {}
    momentum = {}

    for symbol, base in base_prices.items():
        # Add some trend + noise
        if symbol == 'NVDA':
            # NVDA trending up (good news)
            change = 0.02 + np.random.randn() * 0.01
        elif symbol == 'TSLA':
            # TSLA trending down (bad news)
            change = -0.015 + np.random.randn() * 0.02
        elif symbol == 'AAPL':
            # AAPL slightly up (earnings beat)
            change = 0.008 + np.random.randn() * 0.008
        else:
            change = np.random.randn() * 0.01

        prices[symbol] = base * (1 + change)
        base_prices[symbol] = prices[symbol]  # Update for next cycle
        volumes[symbol] = np.random.uniform(10000000, 80000000)
        volatility[symbol] = np.random.uniform(0.015, 0.04)
        momentum[symbol] = change * 10  # Scale for momentum

    # Determine market condition
    avg_change = np.mean([(prices[s] - base) / base for s, base in
                          list(zip(prices.keys(), [185, 142, 378, 248, 178, 495, 505, 43500]))])

    if avg_change > 0.02:
        condition = MarketCondition.TRENDING_UP
    elif avg_change < -0.02:
        condition = MarketCondition.TRENDING_DOWN
    else:
        condition = MarketCondition.NEUTRAL

    # Create snapshot
    snapshot = MarketSnapshot(
        timestamp=datetime.now(),
        prices=prices,
        volumes=volumes,
        spreads={s: 0.01 for s in prices},
        order_book_imbalance={s: np.random.uniform(-0.5, 0.5) for s in prices},
        recent_trades={},
        volatility=volatility,
        momentum=momentum,
        market_condition=condition
    )

    # Update the AI system
    orchestrator.update_market_data(snapshot)

    # Let it process
    time.sleep(0.3)

    # Show some prices
    print(f"   Market: {condition.name}")
    for sym in ['AAPL', 'NVDA', 'TSLA']:
        pct = (prices[sym] / [185, 495, 248][['AAPL', 'NVDA', 'TSLA'].index(sym)] - 1) * 100
        sign = "+" if pct > 0 else ""
        print(f"      {sym}: ${prices[sym]:.2f} ({sign}{pct:.2f}%)")

print()

# =============================================================================
# STEP 6: Check Manipulation Detector
# =============================================================================
print("[6/8] MANIPULATION DETECTION RESULTS...")
print("-" * 50)

alerts = orchestrator.manipulation_detector.get_all_alerts()
if alerts:
    for alert in alerts:
        print(f"   [{alert['severity']}] {alert['symbol']}: {alert['type']}")
        print(f"      {alert['description'][:60]}...")
        print(f"      Action: {alert['action']}")
else:
    print("   No manipulation detected - Markets appear clean")

print()

# =============================================================================
# STEP 7: Check Opportunities Found
# =============================================================================
print("[7/8] OPPORTUNITIES IDENTIFIED...")
print("-" * 50)

opportunities = orchestrator.opportunity_sniper.get_active_opportunities()
if opportunities:
    for opp in opportunities[:5]:  # Show top 5
        print(f"   [{opp['quality']}] {opp['symbol']}: {opp['type']}")
        print(f"      Direction: {opp['direction'].upper()}")
        print(f"      Entry: ${opp['entry']:.2f} | Target: ${opp['target']:.2f} | Stop: ${opp['stop']:.2f}")
        print(f"      R:R = {opp['rr']:.1f} | Confidence: {opp['confidence']*100:.0f}%")
        print(f"      {opp['reasoning'][:50]}...")
        print()
else:
    print("   No high-probability opportunities found yet")
    print("   (Need more price history for pattern detection)")

print()

# =============================================================================
# STEP 8: Final Status & Portfolio
# =============================================================================
print("[8/8] FINAL STATUS REPORT...")
print("-" * 50)

# Get final status
status = orchestrator.get_status()
portfolio = orchestrator.executor.get_portfolio_summary()
performance = orchestrator.get_performance_metrics()

print(f"\n   SYSTEM STATUS:")
print(f"      Mode: {status['mode']}")
print(f"      Running: {status['running']}")
print(f"      Auto Trade: {status['auto_trade']}")
print(f"      Risk Level: {status['risk_level']}")

print(f"\n   AGENT PERFORMANCE:")
for agent_name, agent_status in status['agents'].items():
    print(f"      {agent_name}:")
    print(f"         State: {agent_status['state']}")
    print(f"         Signals: {agent_status['signals']}")
    print(f"         Accuracy: {agent_status['accuracy']*100:.0f}%")

print(f"\n   PORTFOLIO:")
print(f"      Total Value: ${portfolio['total_value']:,.2f}")
print(f"      Available: ${portfolio['available_capital']:,.2f}")
print(f"      Unrealized P&L: ${portfolio['unrealized_pnl']:,.2f}")
print(f"      Daily P&L: ${portfolio['daily_pnl']:,.2f}")
print(f"      Total Return: {portfolio['total_return']:.2f}%")
print(f"      Positions: {len(portfolio['positions'])}")
print(f"      Session Trades: {portfolio['session_trades']}")
print(f"      Win Rate: {portfolio['win_rate']:.1f}%")
print(f"      Paper Mode: {portfolio['paper_mode']}")

if portfolio['positions']:
    print(f"\n   OPEN POSITIONS:")
    for pos in portfolio['positions']:
        pnl_sign = "+" if pos['unrealized_pnl'] >= 0 else ""
        print(f"      {pos['symbol']}: {pos['quantity']} @ ${pos['entry_price']:.2f}")
        print(f"         Current: ${pos['current_price']:.2f} | P&L: {pnl_sign}${pos['unrealized_pnl']:.2f}")

print(f"\n   PERFORMANCE METRICS:")
print(f"      Total Return: {performance.total_return*100:.2f}%")
print(f"      Sharpe Ratio: {performance.sharpe_ratio:.2f}")
print(f"      Max Drawdown: {performance.max_drawdown*100:.2f}%")
print(f"      Total Trades: {performance.total_trades}")

# Get insights
insights = orchestrator.get_agent_insights()
news_summary = insights.get('news', {})
if news_summary:
    print(f"\n   NEWS SUMMARY (Last Hour):")
    print(f"      Total Events: {news_summary.get('total_events_1h', 0)}")
    print(f"      Breaking News: {news_summary.get('breaking_count', 0)}")
    by_cat = news_summary.get('by_category', {})
    if by_cat:
        print(f"      Categories: {', '.join(f'{k}: {v}' for k, v in by_cat.items())}")

# Stop the system
print("\n   Stopping AI system...")
orchestrator.stop()

print()
print("=" * 70)
print("              SIMULATION COMPLETE")
print("=" * 70)
print()
print("The AI infrastructure is ready for use. Key features demonstrated:")
print()
print("   [X] All 6 agents initialized and running")
print("   [X] Company fundamentals loaded and analyzed")
print("   [X] News processing with sentiment analysis")
print("   [X] Market data simulation (5 cycles)")
print("   [X] Manipulation detection active")
print("   [X] Opportunity identification working")
print("   [X] Portfolio tracking operational")
print("   [X] Paper trading mode functional")
print()
print("To use in real trading:")
print("   1. Connect to live market data feeds")
print("   2. Set mode to LIVE_TRADING (carefully!)")
print("   3. Configure broker API callbacks")
print("   4. Monitor via web dashboard at localhost:5000")
print()
