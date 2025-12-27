#!/usr/bin/env python3
"""
🤖 FULL AUTO TRADER
===================
Complete automated trading system with:
- Real broker connection (Alpaca - FREE paper trading)
- News analysis from Google News
- Social media sentiment (Reddit WSB, crypto subs)
- AI-powered decision making
- Automatic execution with SL/TP

Run: python run_full_auto_trader.py
"""

import os
import sys
import time
from datetime import datetime

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from full_auto_trader.config import Config, TradingMode, RiskLevel
from full_auto_trader.executor import AutoExecutor


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🤖  FULL AUTO TRADER                                       ║
║                                                              ║
║   Complete automated trading with AI                         ║
║   News + Social Media + Technical Analysis                   ║
║                                                              ║
║   📰 News from: Google News, Yahoo Finance                   ║
║   🐒 Social from: Reddit (WSB, stocks, crypto)              ║
║   📊 Technical: RSI, MACD, Bollinger, Moving Averages       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def setup_config() -> Config:
    """Interactive config setup"""
    config = Config()

    print("\n⚙️  CONFIGURATION")
    print("=" * 50)

    # Check for Alpaca API keys
    if os.getenv("ALPACA_API_KEY"):
        print("✅ Alpaca API keys found!")
        config.alpaca_api_key = os.getenv("ALPACA_API_KEY")
        config.alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY")
    else:
        print("⚠️  No Alpaca API keys found")
        print("   Using local paper trading simulation")
        print("   For real paper trading, get FREE keys at: https://alpaca.markets")

    # Capital
    print(f"\n💰 Capital: ${config.initial_capital}")
    try:
        capital_input = input("   Change capital? (Enter for $100): ").strip()
        if capital_input:
            config.initial_capital = float(capital_input)
    except:
        pass

    # Risk level
    print(f"\n⚡ Risk Level: {config.risk_level.value}")
    print("   1. Conservative (2% SL, 4% TP)")
    print("   2. Moderate (3% SL, 6% TP)")
    print("   3. Aggressive (5% SL, 10% TP)")
    try:
        risk_input = input("   Choose (1-3, Enter for Moderate): ").strip()
        if risk_input == "1":
            config.risk_level = RiskLevel.CONSERVATIVE
        elif risk_input == "3":
            config.risk_level = RiskLevel.AGGRESSIVE
    except:
        pass

    # Scan interval
    print(f"\n⏰ Scan Interval: {config.scan_interval_minutes} minutes")
    try:
        interval_input = input("   Change interval? (Enter for 5 min): ").strip()
        if interval_input:
            config.scan_interval_minutes = int(interval_input)
    except:
        pass

    # Min confidence
    print(f"\n🎯 Min Confidence: {config.min_confidence:.0%}")
    try:
        conf_input = input("   Change? (Enter for 65%): ").strip()
        if conf_input:
            config.min_confidence = float(conf_input) / 100
    except:
        pass

    return config


def run_dashboard(executor: AutoExecutor):
    """Run web dashboard"""
    try:
        from flask import Flask, render_template_string, jsonify, request
    except ImportError:
        print("Installing Flask...")
        os.system(f"{sys.executable} -m pip install flask")
        from flask import Flask, render_template_string, jsonify, request

    app = Flask(__name__)

    DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Full Auto Trader</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 10px; font-size: 2em; }
        .subtitle { text-align: center; color: #888; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 { font-size: 1.1em; margin-bottom: 15px; color: #aaa; }
        .signal-item {
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .signal-header { display: flex; justify-content: space-between; align-items: center; }
        .signal-type { padding: 4px 10px; border-radius: 10px; font-size: 0.8em; font-weight: 600; }
        .signal-type.buy { background: rgba(0,200,83,0.3); color: #00e676; }
        .signal-type.sell { background: rgba(255,82,82,0.3); color: #ff5252; }
        .signal-type.hold { background: rgba(255,193,7,0.3); color: #ffc107; }
        .signal-details { font-size: 0.85em; color: #888; margin-top: 8px; }
        .score-bar { display: flex; gap: 10px; margin-top: 8px; }
        .score { padding: 2px 8px; border-radius: 4px; font-size: 0.75em; }
        .score.tech { background: rgba(33,150,243,0.3); }
        .score.news { background: rgba(156,39,176,0.3); }
        .score.social { background: rgba(255,152,0,0.3); }
        .portfolio-stat {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .stat-value { font-weight: 600; }
        .positive { color: #00e676; }
        .negative { color: #ff5252; }
        .position-item {
            background: rgba(255,255,255,0.03);
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
        }
        .news-item {
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 0.9em;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            margin: 5px;
        }
        .btn:hover { opacity: 0.9; }
        .btn-danger { background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); }
        .btn-success { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
        .controls { text-align: center; margin: 20px 0; }
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .status-item {
            background: rgba(255,255,255,0.1);
            padding: 8px 15px;
            border-radius: 15px;
            font-size: 0.9em;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .live { color: #00e676; animation: pulse 2s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Full Auto Trader</h1>
        <p class="subtitle">AI-Powered Trading with News & Social Sentiment</p>

        <div class="status-bar">
            <div class="status-item"><span class="live">●</span> LIVE</div>
            <div class="status-item">Mode: <strong>PAPER</strong></div>
            <div class="status-item">Last Scan: <span id="lastScan">-</span></div>
        </div>

        <div class="controls">
            <button class="btn" onclick="refresh()">🔄 Refresh</button>
            <button class="btn btn-success" onclick="runScan()">🔍 Scan Now</button>
            <button class="btn btn-danger" onclick="closeAll()">🛑 Close All</button>
        </div>

        <div class="grid">
            <div class="card">
                <h2>🎯 AI TRADING SIGNALS</h2>
                <div id="signals">Loading...</div>
            </div>

            <div class="card">
                <h2>💰 PORTFOLIO</h2>
                <div id="portfolio">Loading...</div>
            </div>

            <div class="card">
                <h2>📰 NEWS SENTIMENT</h2>
                <div id="news">Loading...</div>
            </div>

            <div class="card">
                <h2>🐒 SOCIAL BUZZ</h2>
                <div id="social">Loading...</div>
            </div>
        </div>
    </div>

    <script>
        function refresh() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    updateSignals(data.signals);
                    updatePortfolio(data.portfolio);
                    updateNews(data.news);
                    updateSocial(data.social);
                    document.getElementById('lastScan').textContent = data.last_scan || 'Never';
                });
        }

        function updateSignals(signals) {
            if (!signals || signals.length === 0) {
                document.getElementById('signals').innerHTML = '<p style="color:#666;">No signals yet. Run a scan.</p>';
                return;
            }
            let html = signals.slice(0, 8).map(s => {
                let typeClass = s.signal.includes('BUY') ? 'buy' : s.signal.includes('SELL') ? 'sell' : 'hold';
                return `
                    <div class="signal-item">
                        <div class="signal-header">
                            <strong>${s.symbol}</strong>
                            <span class="signal-type ${typeClass}">${s.signal} (${s.confidence}%)</span>
                        </div>
                        <div class="score-bar">
                            <span class="score tech">Tech: ${s.technical}</span>
                            <span class="score news">News: ${s.news}</span>
                            <span class="score social">Social: ${s.social}</span>
                        </div>
                        <div class="signal-details">
                            SL: $${s.stop_loss} | TP: $${s.take_profit}<br>
                            ${s.reasons ? s.reasons.slice(0,2).join(' | ') : ''}
                        </div>
                    </div>
                `;
            }).join('');
            document.getElementById('signals').innerHTML = html;
        }

        function updatePortfolio(p) {
            if (!p) return;
            let pnlClass = (p.pnl || 0) >= 0 ? 'positive' : 'negative';
            let html = `
                <div class="portfolio-stat">
                    <span>Cash</span>
                    <span class="stat-value">$${(p.cash || 0).toFixed(2)}</span>
                </div>
                <div class="portfolio-stat">
                    <span>Equity</span>
                    <span class="stat-value">$${(p.equity || 0).toFixed(2)}</span>
                </div>
                <div class="portfolio-stat">
                    <span>P&L</span>
                    <span class="stat-value ${pnlClass}">${(p.pnl || 0) >= 0 ? '+' : ''}$${(p.pnl || 0).toFixed(2)}</span>
                </div>
            `;
            if (p.positions && p.positions.length > 0) {
                html += '<h3 style="margin-top:15px;font-size:0.9em;color:#aaa;">Open Positions</h3>';
                p.positions.forEach(pos => {
                    let posClass = (pos.pnl || 0) >= 0 ? 'positive' : 'negative';
                    html += `
                        <div class="position-item">
                            <strong>${pos.symbol}</strong>: ${pos.quantity} @ $${pos.entry_price}<br>
                            <span class="${posClass}">P&L: $${(pos.pnl || 0).toFixed(2)}</span>
                        </div>
                    `;
                });
            }
            document.getElementById('portfolio').innerHTML = html;
        }

        function updateNews(news) {
            if (!news || Object.keys(news).length === 0) {
                document.getElementById('news').innerHTML = '<p style="color:#666;">No news data</p>';
                return;
            }
            let html = Object.entries(news).slice(0, 5).map(([sym, data]) => {
                let emoji = data.sentiment > 0 ? '🟢' : data.sentiment < 0 ? '🔴' : '⚪';
                return `
                    <div class="news-item">
                        ${emoji} <strong>${sym}</strong>: ${(data.sentiment * 100).toFixed(0)}% sentiment (${data.news_count} articles)
                    </div>
                `;
            }).join('');
            document.getElementById('news').innerHTML = html;
        }

        function updateSocial(social) {
            if (!social || Object.keys(social).length === 0) {
                document.getElementById('social').innerHTML = '<p style="color:#666;">No social data</p>';
                return;
            }
            let html = Object.entries(social).slice(0, 5).map(([sym, data]) => {
                let emoji = data.signal === 'bullish' ? '🟢' : data.signal === 'bearish' ? '🔴' : '⚪';
                return `
                    <div class="news-item">
                        ${emoji} <strong>${sym}</strong>: ${data.signal.toUpperCase()} | ${data.mentions} mentions | Buzz: ${data.buzz}
                    </div>
                `;
            }).join('');
            document.getElementById('social').innerHTML = html;
        }

        function runScan() {
            document.getElementById('signals').innerHTML = '<p>Scanning...</p>';
            fetch('/api/scan', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        refresh();
                    }
                });
        }

        function closeAll() {
            if (!confirm('Close all positions?')) return;
            fetch('/api/close_all', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    alert(data.message);
                    refresh();
                });
        }

        refresh();
        setInterval(refresh, 30000);
    </script>
</body>
</html>
    '''

    # Store last scan results
    last_results = {"signals": [], "news": {}, "social": {}}

    @app.route('/')
    def index():
        return render_template_string(DASHBOARD_HTML)

    @app.route('/api/status')
    def api_status():
        account = executor.broker.get_account()
        positions = executor.broker.get_positions()

        pos_list = []
        for symbol, pos in positions.items():
            pos_list.append({
                "symbol": symbol,
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "pnl": pos.unrealized_pnl
            })

        return jsonify({
            "signals": last_results.get("signals", []),
            "news": last_results.get("news", {}),
            "social": last_results.get("social", {}),
            "portfolio": {
                "cash": account.cash,
                "equity": account.equity,
                "pnl": account.equity - executor.config.initial_capital,
                "positions": pos_list
            },
            "last_scan": executor.last_scan.strftime("%H:%M:%S") if executor.last_scan else None
        })

    @app.route('/api/scan', methods=['POST'])
    def api_scan():
        decisions = executor.run_cycle(auto_execute=True)

        # Convert to JSON-serializable format
        signals = [d.to_dict() for d in decisions.values()]
        signals.sort(key=lambda x: x["confidence"], reverse=True)

        # Get news and social data
        try:
            news_data = executor.news.get_sentiment_summary(list(decisions.keys())[:5])
            social_data = executor.sentiment.get_all_sentiment(list(decisions.keys())[:5])
        except:
            news_data = {}
            social_data = {}

        last_results["signals"] = signals
        last_results["news"] = news_data
        last_results["social"] = social_data

        return jsonify({"success": True})

    @app.route('/api/close_all', methods=['POST'])
    def api_close_all():
        positions = executor.broker.get_positions()
        for symbol in list(positions.keys()):
            executor.broker.close_position(symbol)
        return jsonify({"success": True, "message": f"Closed {len(positions)} positions"})

    print("\n" + "=" * 60)
    print("  🤖 FULL AUTO TRADER DASHBOARD")
    print("=" * 60)
    print(f"\n  URL: http://localhost:5000")
    print(f"  Mode: PAPER TRADING")
    print(f"\n  Features:")
    print(f"    ✓ Real-time AI signals")
    print(f"    ✓ News sentiment analysis")
    print(f"    ✓ Reddit/social sentiment")
    print(f"    ✓ Auto-execution with SL/TP")
    print("\n" + "=" * 60)
    print()

    app.run(host='0.0.0.0', port=5000, debug=False)


def main():
    print_banner()

    # Setup config
    config = setup_config()

    # Create executor
    executor = AutoExecutor(config)

    # Connect to broker
    if not executor.connect():
        print("\n⚠️ Using local paper trading simulation")

    print("\n" + "=" * 50)
    print("Choose mode:")
    print("  1. 🌐 Web Dashboard (recommended)")
    print("  2. 💻 Terminal Auto-Trader")
    print("  3. 🔍 Single Scan (no auto-trade)")
    print("  4. 📊 Test Components")

    try:
        choice = input("\nEnter choice (1-4): ").strip()
    except:
        choice = "1"

    if choice == "1":
        run_dashboard(executor)
    elif choice == "2":
        executor.run(auto_execute=True)
    elif choice == "3":
        executor.run_cycle(auto_execute=False)
    elif choice == "4":
        print("\n🧪 Testing components...")

        print("\n📰 Testing News Analyzer...")
        from full_auto_trader.news import NewsAnalyzer
        news = NewsAnalyzer()
        summary = news.get_sentiment_summary(["NVDA", "BTC"])
        for sym, data in summary.items():
            print(f"   {sym}: {data['sentiment']:.2f} sentiment, {data['news_count']} articles")

        print("\n🐒 Testing Social Sentiment...")
        from full_auto_trader.sentiment import SocialSentiment
        social = SocialSentiment()
        buzz = social.get_all_sentiment(["NVDA", "BTC"])
        for sym, data in buzz.items():
            print(f"   {sym}: {data['signal']} ({data['mentions']} mentions)")

        print("\n🧠 Testing AI Brain...")
        from full_auto_trader.brain import TradingBrain
        brain = TradingBrain()
        decision = brain.analyze("NVDA", news_sentiment=0.2, social_sentiment=0.1)
        print(f"   NVDA: {decision.signal.value} ({decision.confidence:.0%})")

        print("\n✅ All components working!")
    else:
        run_dashboard(executor)


if __name__ == "__main__":
    main()
