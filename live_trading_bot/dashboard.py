#!/usr/bin/env python3
"""
Live Trading Dashboard - Real-time prices and trading signals
Run: python -m live_trading_bot.dashboard
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import threading
import time

from live_trading_bot.bot import TradingBot
from live_trading_bot.config import TradingConfig, STOCK_WATCHLIST, CRYPTO_WATCHLIST

app = Flask(__name__)

# Global bot instance
bot = TradingBot(TradingConfig())

# Dashboard HTML Template
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Live Trading Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 1px solid #333;
            margin-bottom: 30px;
        }
        header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 15px;
        }
        .status-item {
            background: rgba(255,255,255,0.1);
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 0.9em;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 {
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .price-list { list-style: none; }
        .price-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .price-item:last-child { border-bottom: none; }
        .symbol { font-weight: 600; font-size: 1.1em; }
        .price { font-size: 1.2em; }
        .change {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }
        .change.positive { background: rgba(0,200,83,0.2); color: #00c853; }
        .change.negative { background: rgba(255,82,82,0.2); color: #ff5252; }
        .signal-list { list-style: none; }
        .signal-item {
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        .signal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .signal-type {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
        }
        .signal-type.STRONG_BUY, .signal-type.BUY {
            background: rgba(0,200,83,0.3);
            color: #00e676;
        }
        .signal-type.STRONG_SELL, .signal-type.SELL {
            background: rgba(255,82,82,0.3);
            color: #ff5252;
        }
        .signal-type.HOLD {
            background: rgba(255,193,7,0.3);
            color: #ffc107;
        }
        .signal-reason {
            font-size: 0.85em;
            color: rgba(255,255,255,0.7);
            margin-top: 5px;
        }
        .confidence-bar {
            height: 4px;
            background: rgba(255,255,255,0.1);
            border-radius: 2px;
            margin-top: 8px;
            overflow: hidden;
        }
        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #00c853, #69f0ae);
            border-radius: 2px;
        }
        .portfolio-stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }
        .stat {
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.5em;
            font-weight: 600;
            margin-bottom: 5px;
        }
        .stat-label { font-size: 0.85em; color: rgba(255,255,255,0.6); }
        .positive { color: #00e676; }
        .negative { color: #ff5252; }
        .position-item {
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            border: none;
            padding: 12px 25px;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102,126,234,0.4);
        }
        .btn-danger {
            background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%);
        }
        .controls {
            display: flex;
            gap: 15px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        .last-update {
            text-align: center;
            color: rgba(255,255,255,0.5);
            margin-top: 20px;
            font-size: 0.9em;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: rgba(255,255,255,0.5);
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .live-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #00e676;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Live Trading Bot</h1>
            <p>Real-time market analysis with automated trading signals</p>
            <div class="status-bar">
                <div class="status-item"><span class="live-dot"></span>LIVE DATA</div>
                <div class="status-item">Strategy: <strong id="strategy">Combined</strong></div>
                <div class="status-item">Mode: <strong>PAPER</strong></div>
            </div>
        </header>

        <div class="grid">
            <!-- Stocks Card -->
            <div class="card">
                <h2>📈 Stocks</h2>
                <ul class="price-list" id="stocks-list">
                    <li class="loading">Loading...</li>
                </ul>
            </div>

            <!-- Crypto Card -->
            <div class="card">
                <h2>🪙 Crypto</h2>
                <ul class="price-list" id="crypto-list">
                    <li class="loading">Loading...</li>
                </ul>
            </div>

            <!-- Signals Card -->
            <div class="card">
                <h2>🎯 Trading Signals</h2>
                <ul class="signal-list" id="signals-list">
                    <li class="loading">Analyzing...</li>
                </ul>
            </div>

            <!-- Portfolio Card -->
            <div class="card">
                <h2>💰 Portfolio</h2>
                <div class="portfolio-stats" id="portfolio-stats">
                    <div class="stat">
                        <div class="stat-value" id="total-value">$100,000</div>
                        <div class="stat-label">Total Value</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="total-pnl">$0.00</div>
                        <div class="stat-label">Total P&L</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="cash">$100,000</div>
                        <div class="stat-label">Cash</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="positions-count">0</div>
                        <div class="stat-label">Positions</div>
                    </div>
                </div>
                <div id="positions-list" style="margin-top: 15px;"></div>
                <div class="controls">
                    <button class="btn" onclick="refreshData()">🔄 Refresh</button>
                    <button class="btn" onclick="autoTrade()">🤖 Auto Trade</button>
                    <button class="btn btn-danger" onclick="closeAll()">🛑 Close All</button>
                </div>
            </div>
        </div>

        <p class="last-update">Last updated: <span id="last-update">-</span></p>
    </div>

    <script>
        // Refresh data every 30 seconds
        function refreshData() {
            fetch('/api/market')
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        updateStocks(data.stocks);
                        updateCrypto(data.crypto);
                        updateSignals(data.signals);
                        updatePortfolio(data.portfolio);
                        document.getElementById('last-update').textContent =
                            new Date().toLocaleTimeString();
                    }
                })
                .catch(err => console.error('Error:', err));
        }

        function updateStocks(stocks) {
            const list = document.getElementById('stocks-list');
            list.innerHTML = Object.entries(stocks).map(([symbol, data]) => `
                <li class="price-item">
                    <span class="symbol">${symbol}</span>
                    <span class="price">$${data.price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                    <span class="change ${data.change_24h >= 0 ? 'positive' : 'negative'}">
                        ${data.change_24h >= 0 ? '+' : ''}${data.change_24h.toFixed(2)}%
                    </span>
                </li>
            `).join('');
        }

        function updateCrypto(crypto) {
            const list = document.getElementById('crypto-list');
            list.innerHTML = Object.entries(crypto).map(([symbol, data]) => `
                <li class="price-item">
                    <span class="symbol">${symbol}</span>
                    <span class="price">$${data.price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                    <span class="change ${data.change_24h >= 0 ? 'positive' : 'negative'}">
                        ${data.change_24h >= 0 ? '+' : ''}${data.change_24h.toFixed(2)}%
                    </span>
                </li>
            `).join('');
        }

        function updateSignals(signals) {
            const list = document.getElementById('signals-list');
            const actionable = signals.filter(s => s.signal !== 'HOLD');

            if (actionable.length === 0) {
                list.innerHTML = '<li class="signal-item">No actionable signals at the moment</li>';
                return;
            }

            list.innerHTML = actionable.slice(0, 8).map(s => `
                <li class="signal-item">
                    <div class="signal-header">
                        <span class="symbol">${s.symbol} @ $${s.price.toFixed(2)}</span>
                        <span class="signal-type ${s.signal}">${s.signal.replace('_', ' ')}</span>
                    </div>
                    <div class="signal-reason">${s.reason}</div>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${s.confidence}%"></div>
                    </div>
                </li>
            `).join('');
        }

        function updatePortfolio(portfolio) {
            document.getElementById('total-value').textContent =
                '$' + portfolio.total_value.toLocaleString(undefined, {minimumFractionDigits: 2});

            const pnl = portfolio.total_pnl;
            const pnlEl = document.getElementById('total-pnl');
            pnlEl.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toLocaleString(undefined, {minimumFractionDigits: 2});
            pnlEl.className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');

            document.getElementById('cash').textContent =
                '$' + portfolio.cash.toLocaleString(undefined, {minimumFractionDigits: 2});
            document.getElementById('positions-count').textContent = portfolio.num_positions;

            // Positions list
            const posList = document.getElementById('positions-list');
            if (portfolio.positions.length === 0) {
                posList.innerHTML = '<p style="color: rgba(255,255,255,0.5); text-align: center;">No open positions</p>';
            } else {
                posList.innerHTML = portfolio.positions.map(p => `
                    <div class="position-item">
                        <strong>${p.symbol}</strong>: ${p.quantity.toFixed(4)} @ $${p.entry_price.toFixed(2)}
                        <br>
                        <span class="${p.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                            P&L: ${p.unrealized_pnl >= 0 ? '+' : ''}$${p.unrealized_pnl.toFixed(2)}
                            (${p.unrealized_pnl_pct >= 0 ? '+' : ''}${p.unrealized_pnl_pct.toFixed(2)}%)
                        </span>
                    </div>
                `).join('');
            }
        }

        function autoTrade() {
            if (!confirm('Execute high-confidence signals automatically?')) return;

            fetch('/api/auto_trade', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    alert(data.message);
                    refreshData();
                });
        }

        function closeAll() {
            if (!confirm('Close ALL positions? This cannot be undone!')) return;

            fetch('/api/close_all', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    alert(data.message);
                    refreshData();
                });
        }

        // Initial load
        refreshData();

        // Auto-refresh every 30 seconds
        setInterval(refreshData, 30000);
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Main dashboard"""
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/market')
def api_market():
    """Get market overview"""
    try:
        overview = bot.get_market_overview()

        # Update portfolio prices
        all_prices = {}
        for symbol, price_data in overview.stocks.items():
            all_prices[symbol] = price_data.price
        for symbol, price_data in overview.crypto.items():
            all_prices[symbol] = price_data.price
        bot.portfolio.update_prices(all_prices)

        return jsonify({
            'success': True,
            'stocks': {s: {
                'price': p.price,
                'change_24h': p.change_24h,
                'volume_24h': p.volume_24h,
                'high_24h': p.high_24h,
                'low_24h': p.low_24h
            } for s, p in overview.stocks.items()},
            'crypto': {s: {
                'price': p.price,
                'change_24h': p.change_24h,
                'volume_24h': p.volume_24h,
                'market_cap': p.market_cap
            } for s, p in overview.crypto.items()},
            'signals': [s.to_dict() for s in overview.signals],
            'portfolio': bot.portfolio.get_summary(),
            'timestamp': overview.timestamp.isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auto_trade', methods=['POST'])
def api_auto_trade():
    """Execute auto trading"""
    try:
        bot.auto_trade(min_confidence=0.7)
        return jsonify({
            'success': True,
            'message': 'Auto-trade executed! Check portfolio for changes.',
            'portfolio': bot.portfolio.get_summary()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/close_all', methods=['POST'])
def api_close_all():
    """Close all positions"""
    try:
        overview = bot.get_market_overview()
        prices = {s: p.price for s, p in overview.stocks.items()}
        prices.update({s: p.price for s, p in overview.crypto.items()})

        bot.portfolio.close_all(prices)
        return jsonify({
            'success': True,
            'message': 'All positions closed!',
            'portfolio': bot.portfolio.get_summary()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/buy', methods=['POST'])
def api_buy():
    """Manual buy"""
    try:
        data = request.json
        symbol = data.get('symbol')
        amount = float(data.get('amount', 1000))

        # Get current price
        overview = bot.get_market_overview()
        price = None
        if symbol in overview.stocks:
            price = overview.stocks[symbol].price
        elif symbol in overview.crypto:
            price = overview.crypto[symbol].price

        if not price:
            return jsonify({'success': False, 'error': f'Unknown symbol: {symbol}'})

        quantity = amount / price
        success = bot.portfolio.buy(symbol, quantity, price)

        return jsonify({
            'success': success,
            'message': f'Bought {quantity:.4f} {symbol} @ ${price:.2f}' if success else 'Buy failed',
            'portfolio': bot.portfolio.get_summary()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/sell', methods=['POST'])
def api_sell():
    """Manual sell"""
    try:
        data = request.json
        symbol = data.get('symbol')

        # Get current price
        overview = bot.get_market_overview()
        price = None
        if symbol in overview.stocks:
            price = overview.stocks[symbol].price
        elif symbol in overview.crypto:
            price = overview.crypto[symbol].price

        if not price:
            return jsonify({'success': False, 'error': f'Unknown symbol: {symbol}'})

        success = bot.portfolio.sell(symbol, -1, price)

        return jsonify({
            'success': success,
            'message': f'Sold all {symbol}' if success else 'Sell failed',
            'portfolio': bot.portfolio.get_summary()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def main():
    print("\n" + "=" * 60)
    print("  🤖 LIVE TRADING BOT DASHBOARD")
    print("=" * 60)
    print("\n  URL: http://localhost:5000")
    print("  Mode: PAPER TRADING (no real money)")
    print("\n  Features:")
    print("    ✓ Real-time stock prices (Yahoo Finance)")
    print("    ✓ Real-time crypto prices (CoinGecko)")
    print("    ✓ Trading signals (Momentum, RSI, Mean Reversion)")
    print("    ✓ Paper trading portfolio")
    print("    ✓ Auto-trade based on signals")
    print("\n" + "=" * 60)
    print()

    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
