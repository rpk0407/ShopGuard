"""
ShopGuard Trading Platform - Complete Web Application
"""
import os
import sys
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

from .database import db
from .engine import engine, SignalType
from .agents.coordinator import coordinator
from .education.teacher import teacher, LessonCategory
from .analysis.opportunity import detector, OpportunityType
from .assistant.brain import TradingAssistant
from .brokers import BrokerManager

# Initialize broker manager for real trading
broker_manager = BrokerManager()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize assistant
assistant = TradingAssistant(engine, coordinator, teacher, db)

# Background scanner
scanner_thread = None
scanner_running = False


# =============================================================================
# CLEAN HTML TEMPLATE - REBUILT FROM SCRATCH
# =============================================================================

MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopGuard Trading</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg: #0f0f15;
            --bg2: #1a1a24;
            --bg3: #24243a;
            --border: #333;
            --text: #fff;
            --text2: #888;
            --accent: #6366f1;
            --green: #22c55e;
            --red: #ef4444;
            --yellow: #eab308;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg);
            color: var(--text);
            display: flex;
            min-height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 200px;
            background: var(--bg2);
            padding: 20px;
            border-right: 1px solid var(--border);
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }

        .logo { font-size: 1.3em; font-weight: bold; color: var(--accent); margin-bottom: 30px; }

        .nav-btn {
            display: block;
            width: 100%;
            padding: 12px;
            margin-bottom: 8px;
            background: transparent;
            border: none;
            color: var(--text2);
            text-align: left;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95em;
        }
        .nav-btn:hover { background: var(--bg3); color: var(--text); }
        .nav-btn.active { background: var(--accent); color: white; }

        /* Main */
        .main {
            flex: 1;
            margin-left: 200px;
            padding: 30px;
        }

        /* Pages */
        .page { display: none; }
        .page.active { display: block; }

        /* Cards */
        .card {
            background: var(--bg2);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .card-title { color: var(--text2); font-size: 0.85em; margin-bottom: 8px; }
        .card-value { font-size: 1.8em; font-weight: bold; }

        /* Grid */
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }

        /* Buttons */
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95em;
        }
        .btn-primary { background: var(--accent); color: white; }
        .btn-success { background: var(--green); color: white; }
        .btn-danger { background: var(--red); color: white; }
        .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text); }
        .btn:hover { opacity: 0.9; }

        /* Tables */
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }
        th { color: var(--text2); font-weight: normal; }

        /* Signals */
        .signal-buy { color: var(--green); }
        .signal-sell { color: var(--red); }
        .signal-hold { color: var(--yellow); }

        /* Input */
        input, textarea, select {
            width: 100%;
            padding: 12px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            margin-bottom: 10px;
        }

        /* Header */
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }
        .page-header h1 { font-size: 1.5em; }

        /* Chat */
        .chat-box {
            height: 400px;
            overflow-y: auto;
            background: var(--bg);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .chat-msg {
            margin-bottom: 15px;
            padding: 12px;
            border-radius: 8px;
        }
        .chat-user { background: var(--bg3); margin-left: 50px; }
        .chat-ai { background: var(--accent); margin-right: 50px; }

        /* Lesson */
        .lesson { background: var(--bg3); padding: 20px; border-radius: 10px; margin-bottom: 15px; }
        .lesson h3 { margin-bottom: 10px; color: var(--accent); }

        /* Loading */
        .loading { color: var(--text2); text-align: center; padding: 40px; }
    </style>
</head>
<body>
    <nav class="sidebar">
        <div class="logo">ShopGuard</div>
        <button class="nav-btn active" onclick="nav('dashboard')">Dashboard</button>
        <button class="nav-btn" onclick="nav('signals')">Signals</button>
        <button class="nav-btn" onclick="nav('portfolio')">Portfolio</button>
        <button class="nav-btn" onclick="nav('trades')">Trades</button>
        <button class="nav-btn" onclick="nav('analysis')">Analysis</button>
        <button class="nav-btn" onclick="nav('opportunities')">Opportunities</button>
        <button class="nav-btn" onclick="nav('learn')">Learn</button>
        <button class="nav-btn" onclick="nav('chat')">AI Chat</button>
        <button class="nav-btn" onclick="nav('settings')">Settings</button>
    </nav>

    <main class="main">
        <!-- DASHBOARD -->
        <div id="page-dashboard" class="page active">
            <div class="page-header">
                <h1>Dashboard</h1>
                <button class="btn btn-primary" onclick="scanMarket()">Scan Market</button>
            </div>
            <div class="grid">
                <div class="card">
                    <div class="card-title">Equity</div>
                    <div class="card-value" id="equity">$100.00</div>
                </div>
                <div class="card">
                    <div class="card-title">P&L</div>
                    <div class="card-value" id="pnl">$0.00</div>
                </div>
                <div class="card">
                    <div class="card-title">Positions</div>
                    <div class="card-value" id="positions">0</div>
                </div>
                <div class="card">
                    <div class="card-title">Win Rate</div>
                    <div class="card-value" id="winrate">0%</div>
                </div>
            </div>
            <div class="card">
                <h3 style="margin-bottom:15px;">Top Signals</h3>
                <div id="top-signals"><p class="loading">Click Scan Market</p></div>
            </div>
        </div>

        <!-- SIGNALS -->
        <div id="page-signals" class="page">
            <div class="page-header">
                <h1>Trading Signals</h1>
                <button class="btn btn-primary" onclick="scanMarket()">Scan All</button>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr><th>Asset</th><th>Price</th><th>Signal</th><th>Confidence</th><th>Action</th></tr>
                    </thead>
                    <tbody id="signals-table">
                        <tr><td colspan="5" class="loading">Click Scan All to analyze markets</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- PORTFOLIO -->
        <div id="page-portfolio" class="page">
            <div class="page-header">
                <h1>Portfolio</h1>
                <button class="btn btn-outline" onclick="loadPortfolio()">Refresh</button>
            </div>
            <div class="grid">
                <div class="card">
                    <div class="card-title">Cash</div>
                    <div class="card-value" id="port-cash">$100.00</div>
                </div>
                <div class="card">
                    <div class="card-title">Positions Value</div>
                    <div class="card-value" id="port-value">$0.00</div>
                </div>
            </div>
            <div class="card">
                <h3 style="margin-bottom:15px;">Open Positions</h3>
                <table>
                    <thead>
                        <tr><th>Asset</th><th>Qty</th><th>Entry</th><th>Current</th><th>P&L</th></tr>
                    </thead>
                    <tbody id="positions-table">
                        <tr><td colspan="5" class="loading">No positions</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TRADES -->
        <div id="page-trades" class="page">
            <div class="page-header">
                <h1>Trade History</h1>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr><th>Date</th><th>Asset</th><th>Type</th><th>Price</th><th>Qty</th><th>P&L</th></tr>
                    </thead>
                    <tbody id="trades-table">
                        <tr><td colspan="6" class="loading">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- ANALYSIS -->
        <div id="page-analysis" class="page">
            <div class="page-header">
                <h1>Deep Analysis</h1>
            </div>
            <div class="card">
                <div style="display:flex;gap:10px;margin-bottom:20px;">
                    <select id="analysis-asset">
                        <option value="BTC">Bitcoin (BTC)</option>
                        <option value="ETH">Ethereum (ETH)</option>
                        <option value="SPY">S&P 500 (SPY)</option>
                        <option value="QQQ">NASDAQ (QQQ)</option>
                        <option value="NVDA">NVIDIA (NVDA)</option>
                    </select>
                    <button class="btn btn-primary" onclick="runAnalysis()">Analyze</button>
                </div>
                <div id="analysis-result"><p class="loading">Select asset and click Analyze</p></div>
            </div>
        </div>

        <!-- OPPORTUNITIES -->
        <div id="page-opportunities" class="page">
            <div class="page-header">
                <h1>Opportunities</h1>
                <button class="btn btn-primary" onclick="findOpportunities()">Find Opportunities</button>
            </div>
            <div id="opportunities-list">
                <div class="card"><p class="loading">Click Find Opportunities to scan</p></div>
            </div>
        </div>

        <!-- LEARN -->
        <div id="page-learn" class="page">
            <div class="page-header">
                <h1>Trading Education</h1>
            </div>
            <div class="grid">
                <button class="btn btn-outline" onclick="loadLessons('basics')">Trading Basics</button>
                <button class="btn btn-outline" onclick="loadLessons('technical')">Technical Analysis</button>
                <button class="btn btn-outline" onclick="loadLessons('fundamental')">Fundamental</button>
                <button class="btn btn-outline" onclick="loadLessons('risk')">Risk Management</button>
                <button class="btn btn-outline" onclick="loadLessons('psychology')">Psychology</button>
                <button class="btn btn-outline" onclick="loadLessons('crypto')">Crypto</button>
                <button class="btn btn-outline" onclick="loadLessons('stocks')">Stocks</button>
                <button class="btn btn-outline" onclick="loadLessons('strategies')">Strategies</button>
                <button class="btn btn-outline" onclick="loadLessons('advanced')">Advanced</button>
            </div>
            <div id="lessons-container"></div>
        </div>

        <!-- CHAT -->
        <div id="page-chat" class="page">
            <div class="page-header">
                <h1>AI Trading Assistant</h1>
            </div>
            <div class="card">
                <div class="chat-box" id="chat-messages">
                    <div class="chat-msg chat-ai">Hello! I can help you trade, analyze markets, or learn about trading. Try: "Analyze Bitcoin" or "Buy ETH"</div>
                </div>
                <div style="display:flex;gap:10px;">
                    <input type="text" id="chat-input" placeholder="Ask me anything..." onkeypress="if(event.key==='Enter')sendChat()">
                    <button class="btn btn-primary" onclick="sendChat()">Send</button>
                </div>
            </div>
        </div>

        <!-- SETTINGS -->
        <div id="page-settings" class="page">
            <div class="page-header">
                <h1>Settings</h1>
            </div>
            <div class="card">
                <h3 style="margin-bottom:15px;">Trading Settings</h3>
                <label style="color:var(--text2);display:block;margin-bottom:5px;">Initial Capital ($)</label>
                <input type="number" id="set-capital" value="100">

                <label style="color:var(--text2);display:block;margin-bottom:5px;">Stop Loss (%)</label>
                <input type="number" id="set-stoploss" value="3">

                <label style="color:var(--text2);display:block;margin-bottom:5px;">Take Profit (%)</label>
                <input type="number" id="set-takeprofit" value="6">

                <div style="margin-top:15px;">
                    <label style="color:var(--text2);">
                        <input type="checkbox" id="set-autotrade"> Enable Auto-Trading
                    </label>
                </div>

                <button class="btn btn-primary" style="margin-top:20px;" onclick="saveSettings()">Save Settings</button>
            </div>

            <div class="card">
                <h3 style="margin-bottom:15px;">Broker API Keys (Optional)</h3>
                <label style="color:var(--text2);display:block;margin-bottom:5px;">Alpaca API Key</label>
                <input type="text" id="set-alpaca-key" placeholder="Your Alpaca API key">

                <label style="color:var(--text2);display:block;margin-bottom:5px;">Alpaca Secret</label>
                <input type="password" id="set-alpaca-secret" placeholder="Your Alpaca secret">

                <label style="color:var(--text2);display:block;margin-bottom:5px;">Binance API Key</label>
                <input type="text" id="set-binance-key" placeholder="Your Binance API key">

                <label style="color:var(--text2);display:block;margin-bottom:5px;">Binance Secret</label>
                <input type="password" id="set-binance-secret" placeholder="Your Binance secret">

                <button class="btn btn-outline" style="margin-top:15px;" onclick="saveBrokerKeys()">Save Broker Keys</button>
            </div>
        </div>
    </main>

    <script>
        // =====================
        // NAVIGATION
        // =====================
        function nav(page) {
            // Hide all pages
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            // Show selected
            document.getElementById('page-' + page).classList.add('active');
            // Update nav buttons
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            // Load data
            if (page === 'portfolio') loadPortfolio();
            if (page === 'trades') loadTrades();
            if (page === 'settings') loadSettings();
        }

        // =====================
        // API HELPER
        // =====================
        async function api(endpoint, method = 'GET', data = null) {
            const opts = { method, headers: { 'Content-Type': 'application/json' } };
            if (data) opts.body = JSON.stringify(data);
            const resp = await fetch('/api/' + endpoint, opts);
            return resp.json();
        }

        // =====================
        // DASHBOARD
        // =====================
        async function loadDashboard() {
            const data = await api('dashboard');
            if (data.success) {
                document.getElementById('equity').textContent = '$' + (data.portfolio.equity || 0).toFixed(2);
                document.getElementById('pnl').textContent = '$' + (data.portfolio.total_pnl || 0).toFixed(2);
                document.getElementById('positions').textContent = data.portfolio.positions?.length || 0;
                document.getElementById('winrate').textContent = (data.stats.win_rate || 0).toFixed(0) + '%';
            }
        }

        // =====================
        // SCAN MARKET
        // =====================
        async function scanMarket() {
            document.getElementById('top-signals').innerHTML = '<p class="loading">Scanning...</p>';
            document.getElementById('signals-table').innerHTML = '<tr><td colspan="5" class="loading">Scanning...</td></tr>';

            const data = await api('scan', 'POST');
            if (data.success) {
                const signals = Object.values(data.signals).sort((a, b) => b.confidence - a.confidence);

                // Top signals
                let html = '';
                signals.slice(0, 3).forEach(s => {
                    const cls = s.signal.includes('BUY') ? 'signal-buy' : s.signal.includes('SELL') ? 'signal-sell' : 'signal-hold';
                    html += `<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);">
                        <span><strong>${s.symbol}</strong> - $${s.price.toFixed(2)}</span>
                        <span class="${cls}">${s.signal} (${(s.confidence*100).toFixed(0)}%)</span>
                    </div>`;
                });
                document.getElementById('top-signals').innerHTML = html || '<p>No signals</p>';

                // Signals table
                let rows = '';
                signals.forEach(s => {
                    const cls = s.signal.includes('BUY') ? 'signal-buy' : s.signal.includes('SELL') ? 'signal-sell' : 'signal-hold';
                    rows += `<tr>
                        <td><strong>${s.symbol}</strong></td>
                        <td>$${s.price.toFixed(2)}</td>
                        <td class="${cls}">${s.signal}</td>
                        <td>${(s.confidence*100).toFixed(0)}%</td>
                        <td>
                            <button class="btn btn-success" onclick="trade('${s.symbol}','buy')" style="padding:5px 10px;font-size:0.8em;">Buy</button>
                            <button class="btn btn-danger" onclick="trade('${s.symbol}','sell')" style="padding:5px 10px;font-size:0.8em;">Sell</button>
                        </td>
                    </tr>`;
                });
                document.getElementById('signals-table').innerHTML = rows || '<tr><td colspan="5">No signals</td></tr>';
            }
        }

        // =====================
        // PORTFOLIO
        // =====================
        async function loadPortfolio() {
            const data = await api('portfolio');
            if (data.success) {
                document.getElementById('port-cash').textContent = '$' + (data.cash || 0).toFixed(2);
                document.getElementById('port-value').textContent = '$' + (data.positions_value || 0).toFixed(2);

                let rows = '';
                (data.positions || []).forEach(p => {
                    const pnl = (p.current_price - p.entry_price) * p.quantity;
                    const cls = pnl >= 0 ? 'signal-buy' : 'signal-sell';
                    rows += `<tr>
                        <td>${p.symbol}</td>
                        <td>${p.quantity.toFixed(4)}</td>
                        <td>$${p.entry_price.toFixed(2)}</td>
                        <td>$${p.current_price.toFixed(2)}</td>
                        <td class="${cls}">$${pnl.toFixed(2)}</td>
                    </tr>`;
                });
                document.getElementById('positions-table').innerHTML = rows || '<tr><td colspan="5">No positions</td></tr>';
            }
        }

        // =====================
        // TRADES
        // =====================
        async function loadTrades() {
            const data = await api('trades');
            if (data.success) {
                let rows = '';
                (data.trades || []).forEach(t => {
                    const cls = (t.pnl || 0) >= 0 ? 'signal-buy' : 'signal-sell';
                    rows += `<tr>
                        <td>${t.timestamp}</td>
                        <td>${t.symbol}</td>
                        <td>${t.side}</td>
                        <td>$${t.price.toFixed(2)}</td>
                        <td>${t.quantity.toFixed(4)}</td>
                        <td class="${cls}">$${(t.pnl || 0).toFixed(2)}</td>
                    </tr>`;
                });
                document.getElementById('trades-table').innerHTML = rows || '<tr><td colspan="6">No trades yet</td></tr>';
            }
        }

        // =====================
        // TRADE
        // =====================
        async function trade(symbol, side) {
            const data = await api('trade', 'POST', { symbol, side, amount: 10 });
            alert(data.success ? `${side.toUpperCase()} order placed for ${symbol}` : 'Trade failed: ' + data.error);
            loadPortfolio();
            loadDashboard();
        }

        // =====================
        // ANALYSIS
        // =====================
        async function runAnalysis() {
            const asset = document.getElementById('analysis-asset').value;
            document.getElementById('analysis-result').innerHTML = '<p class="loading">Analyzing ' + asset + '... This may take a moment.</p>';

            const data = await api('deep-analysis/' + asset);
            if (data.success) {
                const a = data.analysis;
                let html = `
                    <div class="lesson">
                        <h3>${a.symbol} - ${a.recommendation}</h3>
                        <p><strong>Confidence:</strong> ${(a.confidence * 100).toFixed(0)}%</p>
                        <p><strong>Entry Zone:</strong> $${a.entry_zone?.join(' - $') || 'N/A'}</p>
                        <p><strong>Targets:</strong> $${a.targets?.join(', $') || 'N/A'}</p>
                        <p><strong>Stop Loss:</strong> $${a.stop_loss || 'N/A'}</p>
                        <p><strong>Hold Time:</strong> ${a.hold_time || 'N/A'}</p>
                    </div>
                    <div class="card" style="margin-top:15px;">
                        <h4>Agent Votes</h4>
                        <p>Technical: ${a.votes?.technical || 'N/A'}</p>
                        <p>News: ${a.votes?.news || 'N/A'}</p>
                        <p>Social: ${a.votes?.social || 'N/A'}</p>
                        <p>Risk: ${a.votes?.risk || 'N/A'}</p>
                        <p>Fundamental: ${a.votes?.fundamental || 'N/A'}</p>
                    </div>
                `;
                document.getElementById('analysis-result').innerHTML = html;
            } else {
                document.getElementById('analysis-result').innerHTML = '<p class="loading">Analysis failed</p>';
            }
        }

        // =====================
        // OPPORTUNITIES
        // =====================
        async function findOpportunities() {
            document.getElementById('opportunities-list').innerHTML = '<div class="card"><p class="loading">Scanning for opportunities...</p></div>';

            const data = await api('opportunities', 'POST');
            if (data.success && data.opportunities?.length > 0) {
                let html = '';
                data.opportunities.forEach(o => {
                    html += `<div class="card">
                        <h3>${o.symbol} - ${o.opportunity_type}</h3>
                        <p><strong>Confidence:</strong> ${(o.confidence * 100).toFixed(0)}%</p>
                        <p>${o.explanation || ''}</p>
                        <button class="btn btn-success" onclick="trade('${o.symbol}','buy')" style="margin-top:10px;">Trade</button>
                    </div>`;
                });
                document.getElementById('opportunities-list').innerHTML = html;
            } else {
                document.getElementById('opportunities-list').innerHTML = '<div class="card"><p>No opportunities found right now</p></div>';
            }
        }

        // =====================
        // EDUCATION
        // =====================
        async function loadLessons(category) {
            document.getElementById('lessons-container').innerHTML = '<div class="card"><p class="loading">Loading...</p></div>';

            const data = await api('education/' + category);
            if (data.success && data.lessons?.length > 0) {
                let html = '';
                data.lessons.forEach((l, i) => {
                    html += `<div class="lesson">
                        <h3>Lesson ${i + 1}: ${l.title}</h3>
                        <p style="color:var(--text2);margin-bottom:10px;">${l.difficulty}</p>
                        <div style="white-space:pre-wrap;">${l.content}</div>
                        ${l.key_takeaways?.length ? '<h4 style="margin-top:15px;">Key Takeaways:</h4><ul>' + l.key_takeaways.map(t => '<li>' + t + '</li>').join('') + '</ul>' : ''}
                    </div>`;
                });
                document.getElementById('lessons-container').innerHTML = html;
            } else {
                document.getElementById('lessons-container').innerHTML = '<div class="card"><p>No lessons in this category</p></div>';
            }
        }

        // =====================
        // CHAT
        // =====================
        async function sendChat() {
            const input = document.getElementById('chat-input');
            const msg = input.value.trim();
            if (!msg) return;

            const box = document.getElementById('chat-messages');
            box.innerHTML += `<div class="chat-msg chat-user">${msg}</div>`;
            input.value = '';

            const data = await api('chat', 'POST', { message: msg });
            if (data.success) {
                box.innerHTML += `<div class="chat-msg chat-ai">${data.response.message}</div>`;
            } else {
                box.innerHTML += `<div class="chat-msg chat-ai">Sorry, something went wrong.</div>`;
            }
            box.scrollTop = box.scrollHeight;
        }

        // =====================
        // SETTINGS
        // =====================
        async function loadSettings() {
            const data = await api('settings');
            if (data.success) {
                document.getElementById('set-capital').value = data.settings.initial_capital || 100;
                document.getElementById('set-stoploss').value = data.settings.stop_loss_pct || 3;
                document.getElementById('set-takeprofit').value = data.settings.take_profit_pct || 6;
                document.getElementById('set-autotrade').checked = data.settings.auto_trade || false;
            }
        }

        async function saveSettings() {
            const settings = {
                initial_capital: parseFloat(document.getElementById('set-capital').value),
                stop_loss_pct: parseFloat(document.getElementById('set-stoploss').value),
                take_profit_pct: parseFloat(document.getElementById('set-takeprofit').value),
                auto_trade: document.getElementById('set-autotrade').checked
            };
            const data = await api('settings', 'POST', settings);
            alert(data.success ? 'Settings saved!' : 'Failed to save');
        }

        async function saveBrokerKeys() {
            alert('Broker keys would be saved (implement as needed)');
        }

        // =====================
        // INIT
        // =====================
        window.addEventListener('DOMContentLoaded', function() {
            loadDashboard();
        });
    </script>
</body>
</html>
'''


# =============================================================================
# API ROUTES
# =============================================================================

@app.route('/')
def index():
    from flask import make_response
    response = make_response(render_template_string(MAIN_TEMPLATE))
    # Prevent browser caching - forces fresh load every time
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/dashboard')
def api_dashboard():
    """Dashboard overview"""
    try:
        portfolio = engine.get_portfolio_value()
        stats = db.get_trade_stats()
        alerts = db.get_alerts(unread_only=True)

        signals = {}
        if engine.last_signals:
            for symbol, sig in engine.last_signals.items():
                signals[symbol] = {
                    "symbol": symbol,
                    "signal": sig.signal.value,
                    "confidence": sig.confidence,
                    "price": sig.price,
                    "technical_score": sig.technical_score,
                    "news_score": sig.news_score,
                    "social_score": sig.social_score,
                    "stop_loss": sig.stop_loss,
                    "take_profit": sig.take_profit
                }

        return jsonify({
            "success": True,
            "portfolio": {
                "cash": portfolio["cash"],
                "positions_value": portfolio["positions_value"],
                "equity": portfolio["equity"],
                "initial_capital": portfolio["initial_capital"],
                "total_pnl": portfolio["total_pnl"],
                "total_pnl_pct": portfolio["total_pnl_pct"],
                "positions": [{"symbol": p.symbol, "quantity": p.quantity, "entry_price": p.entry_price,
                               "current_price": p.current_price} for p in portfolio["positions"]]
            },
            "stats": stats,
            "signals": signals,
            "unread_alerts": len(alerts),
            "last_scan": engine.last_scan.strftime("%H:%M:%S") if engine.last_scan else None
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Scan market for signals"""
    try:
        engine.reload_settings()
        signals = engine.scan_all()

        result = {}
        for symbol, sig in signals.items():
            result[symbol] = {
                "symbol": symbol,
                "signal": sig.signal.value,
                "confidence": sig.confidence,
                "price": sig.price,
                "technical_score": sig.technical_score,
                "news_score": sig.news_score,
                "social_score": sig.social_score,
                "reasons": sig.reasons,
                "stop_loss": sig.stop_loss,
                "take_profit": sig.take_profit
            }

        return jsonify({"success": True, "signals": result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/portfolio')
def api_portfolio():
    """Get portfolio"""
    try:
        portfolio = engine.get_portfolio_value()
        return jsonify({
            "success": True,
            "cash": portfolio["cash"],
            "positions_value": portfolio["positions_value"],
            "equity": portfolio["equity"],
            "positions": [{"symbol": p.symbol, "quantity": p.quantity, "entry_price": p.entry_price,
                           "current_price": p.current_price} for p in portfolio["positions"]]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/trades')
def api_trades():
    """Get trade history"""
    try:
        trades = db.get_trades(limit=50)
        return jsonify({
            "success": True,
            "trades": [{
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "pnl": t.pnl,
                "timestamp": t.timestamp.strftime("%Y-%m-%d %H:%M")
            } for t in trades]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/trade', methods=['POST'])
def api_trade():
    """Execute a trade"""
    try:
        data = request.json
        symbol = data.get('symbol')
        side = data.get('side')
        amount = float(data.get('amount', 10))

        if side == 'buy':
            success = engine.execute_buy(symbol, amount)
        else:
            success = engine.execute_sell(symbol)

        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings"""
    try:
        if request.method == 'POST':
            data = request.json
            db.update_settings(data)
            engine.reload_settings()
            return jsonify({"success": True})
        else:
            settings = db.get_settings()
            return jsonify({"success": True, "settings": settings})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/deep-analysis/<asset>')
def api_deep_analysis(asset):
    """Run deep multi-agent analysis"""
    try:
        print(f"\n🔬 Running deep analysis on {asset}...")
        analysis = coordinator.analyze(asset)

        return jsonify({
            "success": True,
            "analysis": {
                "symbol": asset,
                "recommendation": analysis.get("recommendation", "HOLD"),
                "confidence": analysis.get("confidence", 0),
                "entry_zone": analysis.get("entry_zone", []),
                "targets": analysis.get("targets", []),
                "stop_loss": analysis.get("stop_loss"),
                "hold_time": analysis.get("hold_time"),
                "votes": analysis.get("votes", {}),
                "reasoning": analysis.get("reasoning", [])
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/opportunities', methods=['POST'])
def api_opportunities():
    """Find trading opportunities"""
    try:
        print("\n🔍 Scanning for opportunities...")
        all_opportunities = []

        for symbol in engine.symbols:
            print(f"  Analyzing {symbol}...")
            opps = detector.find_opportunities(symbol, coordinator)
            for opp in opps:
                all_opportunities.append({
                    "symbol": opp.symbol,
                    "opportunity_type": opp.opportunity_type.value,
                    "confidence": opp.confidence,
                    "explanation": opp.explanation,
                    "entry_zone": opp.entry_zone,
                    "targets": opp.targets,
                    "stop_loss": opp.stop_loss
                })

        all_opportunities.sort(key=lambda x: x["confidence"], reverse=True)

        return jsonify({
            "success": True,
            "opportunities": all_opportunities
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/education/<category>')
def api_education(category):
    """Get educational lessons by category"""
    try:
        category_map = {
            'basics': LessonCategory.BASICS,
            'technical': LessonCategory.TECHNICAL,
            'fundamental': LessonCategory.FUNDAMENTAL,
            'risk': LessonCategory.RISK,
            'psychology': LessonCategory.PSYCHOLOGY,
            'crypto': LessonCategory.CRYPTO,
            'stocks': LessonCategory.STOCKS,
            'strategies': LessonCategory.STRATEGIES,
            'advanced': LessonCategory.ADVANCED
        }

        cat_enum = category_map.get(category.lower())
        if not cat_enum:
            return jsonify({"success": False, "error": "Unknown category"})

        lessons = teacher.get_lessons_by_category(cat_enum)

        return jsonify({
            "success": True,
            "category": category,
            "lessons": [{
                "id": l.id,
                "title": l.title,
                "difficulty": l.difficulty,
                "content": l.content,
                "key_takeaways": l.key_takeaways
            } for l in lessons]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Chat with AI assistant"""
    try:
        data = request.json
        message = data.get('message', '')

        response = assistant.chat(message)

        return jsonify({
            "success": True,
            "response": {
                "message": response.get("message", "I didn't understand that."),
                "action_taken": response.get("action_taken", False)
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/alerts')
def api_alerts():
    """Get alerts"""
    try:
        alerts = db.get_alerts(limit=20)
        return jsonify({
            "success": True,
            "alerts": [{
                "id": a.id,
                "type": a.alert_type,
                "message": a.message,
                "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M"),
                "read": a.read
            } for a in alerts]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# BROKER API ROUTES
# =============================================================================

@app.route('/api/brokers/status')
def api_broker_status():
    """Get broker connection status"""
    return jsonify({
        "success": True,
        "alpaca": bool(getattr(broker_manager.alpaca, 'api_key', None)),
        "binance": bool(getattr(broker_manager.binance, 'api_key', None))
    })


@app.route('/api/brokers/alpaca/test', methods=['POST'])
def api_test_alpaca():
    """Test Alpaca connection"""
    try:
        data = request.json
        broker_manager.alpaca.configure(
            data.get('api_key'),
            data.get('api_secret'),
            data.get('paper', True)
        )
        account = broker_manager.alpaca.get_account()
        return jsonify({"success": True, "account": account})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/brokers/binance/test', methods=['POST'])
def api_test_binance():
    """Test Binance connection"""
    try:
        data = request.json
        broker_manager.binance.configure(
            data.get('api_key'),
            data.get('api_secret'),
            data.get('testnet', True)
        )
        account = broker_manager.binance.get_account()
        return jsonify({"success": True, "account": account})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# RUN APP
# =============================================================================

def run_app(host='0.0.0.0', port=5000, debug=False):
    """Run the application"""
    print("\n" + "=" * 60)
    print("  SHOPGUARD TRADING PLATFORM")
    print("=" * 60)
    print(f"\n  URL: http://localhost:{port}")
    print("\n  Features:")
    print("    - Real-time market data")
    print("    - AI trading signals")
    print("    - Multi-agent analysis")
    print("    - Trading education")
    print("    - Auto-trading")
    print("\n" + "=" * 60 + "\n")

    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_app(debug=True)
