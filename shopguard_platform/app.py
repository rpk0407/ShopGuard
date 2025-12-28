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

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize assistant
assistant = TradingAssistant(engine, coordinator, teacher, db)

# Background scanner
scanner_thread = None
scanner_running = False


# =============================================================================
# COMPLETE HTML TEMPLATE
# =============================================================================

MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏦 ShopGuard Trading Platform</title>
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a25;
            --border: #2a2a3a;
            --text-primary: #ffffff;
            --text-secondary: #8888aa;
            --accent: #6366f1;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            position: fixed;
            left: 0;
            top: 0;
            width: 220px;
            height: 100vh;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            padding: 20px;
            display: flex;
            flex-direction: column;
        }

        .logo {
            font-size: 1.5em;
            font-weight: 700;
            margin-bottom: 30px;
            color: var(--accent);
        }

        .nav-item {
            padding: 12px 15px;
            margin-bottom: 5px;
            border-radius: 8px;
            cursor: pointer;
            color: var(--text-secondary);
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .nav-item:hover, .nav-item.active {
            background: var(--bg-card);
            color: var(--text-primary);
        }

        .nav-item.active {
            border-left: 3px solid var(--accent);
        }

        /* Main Content */
        .main {
            margin-left: 220px;
            padding: 20px;
            min-height: 100vh;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }

        .header h1 { font-size: 1.5em; }

        .header-actions {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        /* Cards */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .card-title {
            font-size: 0.9em;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Stats */
        .stat-value {
            font-size: 2em;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .stat-label {
            color: var(--text-secondary);
            font-size: 0.85em;
        }

        .positive { color: var(--success); }
        .negative { color: var(--danger); }

        /* Tables */
        .table-container {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }

        th {
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.85em;
            text-transform: uppercase;
        }

        /* Buttons */
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.2s;
        }

        .btn-primary {
            background: var(--accent);
            color: white;
        }

        .btn-success {
            background: var(--success);
            color: white;
        }

        .btn-danger {
            background: var(--danger);
            color: white;
        }

        .btn-outline {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-primary);
        }

        .btn:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }

        /* Signals */
        .signal-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
        }

        .signal-buy { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        .signal-sell { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .signal-hold { background: rgba(245, 158, 11, 0.2); color: var(--warning); }

        /* Score bars */
        .score-bar {
            display: flex;
            gap: 5px;
            margin-top: 5px;
        }

        .score {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.7em;
        }

        .score-tech { background: rgba(99, 102, 241, 0.3); }
        .score-news { background: rgba(168, 85, 247, 0.3); }
        .score-social { background: rgba(249, 115, 22, 0.3); }

        /* Positions */
        .position-card {
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
        }

        .position-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }

        /* Alerts */
        .alert-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 8px;
            background: var(--bg-secondary);
        }

        .alert-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .alert-info .alert-dot { background: var(--accent); }
        .alert-warning .alert-dot { background: var(--warning); }
        .alert-critical .alert-dot { background: var(--danger); }

        /* Live indicator */
        .live-dot {
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Tabs */
        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
        }

        .tab {
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            color: var(--text-secondary);
        }

        .tab.active {
            background: var(--accent);
            color: white;
        }

        /* Settings Form */
        .form-group {
            margin-bottom: 15px;
        }

        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: var(--text-secondary);
            font-size: 0.9em;
        }

        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }

        /* Page sections */
        .page { display: none; }
        .page.active { display: block; }

        /* Responsive */
        @media (max-width: 768px) {
            .sidebar { display: none; }
            .main { margin-left: 0; }
        }
    </style>
</head>
<body>
    <!-- Sidebar -->
    <nav class="sidebar">
        <div class="logo">🏦 ShopGuard</div>
        <div class="nav-item" data-page="assistant" onclick="showPage('assistant')" style="background:linear-gradient(135deg, #6366f1, #8b5cf6);color:white;font-weight:bold;">🤖 AI Assistant</div>
        <div class="nav-item" data-page="dashboard" onclick="showPage('dashboard')">📊 Dashboard</div>
        <div class="nav-item active" data-page="signals" onclick="showPage('signals')">🎯 Signals</div>
        <div class="nav-item" data-page="analysis" onclick="showPage('analysis')">🧠 Deep Analysis</div>
        <div class="nav-item" data-page="opportunities" onclick="showPage('opportunities')">💡 Opportunities</div>
        <div class="nav-item" data-page="learn" onclick="showPage('learn')">📚 Learn</div>
        <div class="nav-item" data-page="portfolio" onclick="showPage('portfolio')">💰 Portfolio</div>
        <div class="nav-item" data-page="trades" onclick="showPage('trades')">📜 Trades</div>
        <div class="nav-item" data-page="settings" onclick="showPage('settings')">⚙️ Settings</div>
        <div style="flex:1;"></div>
        <div class="nav-item" data-page="alerts" onclick="showPage('alerts')">🔔 Alerts <span id="alertCount" style="background:var(--danger);padding:2px 8px;border-radius:10px;font-size:0.8em;margin-left:auto;">0</span></div>
    </nav>

    <!-- Main Content -->
    <main class="main">
        <!-- AI Assistant Page -->
        <div id="page-assistant" class="page">
            <div class="header">
                <h1>🤖 AI Trading Assistant</h1>
                <span style="color:var(--text-secondary);">Talk to me to control everything</span>
            </div>

            <div style="display:flex;gap:20px;height:calc(100vh - 150px);">
                <!-- Chat Area -->
                <div class="card" style="flex:2;display:flex;flex-direction:column;">
                    <div id="chatMessages" style="flex:1;overflow-y:auto;padding:15px;background:var(--bg-secondary);border-radius:8px;margin-bottom:15px;">
                        <div class="chat-message assistant">
                            <div class="chat-bubble" style="background:var(--accent);padding:15px;border-radius:12px;max-width:80%;margin-bottom:15px;">
                                <strong>🤖 AI Assistant</strong>
                                <p style="margin-top:10px;">Hey! I'm your AI Trading Assistant. I can help you:</p>
                                <ul style="margin:10px 0;padding-left:20px;">
                                    <li><strong>Trade</strong>: "Buy Bitcoin" or "Sell ETH"</li>
                                    <li><strong>Analyze</strong>: "Analyze NVDA" for deep analysis</li>
                                    <li><strong>Learn</strong>: "Explain RSI" or "Teach me risk management"</li>
                                    <li><strong>Monitor</strong>: "Show my portfolio" or "Find opportunities"</li>
                                </ul>
                                <p>Just type naturally - I'll understand!</p>
                            </div>
                        </div>
                    </div>

                    <div style="display:flex;gap:10px;">
                        <input type="text" id="chatInput" placeholder="Type your message... (e.g., 'Analyze Bitcoin' or 'Show my portfolio')"
                               style="flex:1;padding:15px;border:1px solid var(--border);border-radius:8px;background:var(--bg-secondary);color:white;font-size:1em;"
                               onkeypress="if(event.key==='Enter')sendChat()">
                        <button class="btn btn-primary" onclick="sendChat()" style="padding:15px 25px;">Send 🚀</button>
                    </div>
                </div>

                <!-- Quick Actions Sidebar -->
                <div class="card" style="flex:1;max-width:300px;">
                    <h4 style="margin-bottom:15px;">⚡ Quick Commands</h4>
                    <div style="display:flex;flex-direction:column;gap:8px;">
                        <button class="btn btn-outline" onclick="quickChat('Analyze Bitcoin')" style="text-align:left;">🔬 Analyze Bitcoin</button>
                        <button class="btn btn-outline" onclick="quickChat('Analyze Ethereum')" style="text-align:left;">🔬 Analyze Ethereum</button>
                        <button class="btn btn-outline" onclick="quickChat('Show my portfolio')" style="text-align:left;">💰 Show Portfolio</button>
                        <button class="btn btn-outline" onclick="quickChat('Find opportunities')" style="text-align:left;">💡 Find Opportunities</button>
                        <button class="btn btn-outline" onclick="quickChat('Scan market')" style="text-align:left;">📡 Scan Market</button>
                        <button class="btn btn-outline" onclick="quickChat('How am I performing?')" style="text-align:left;">📈 My Performance</button>
                    </div>

                    <h4 style="margin:20px 0 15px;">📚 Learn</h4>
                    <div style="display:flex;flex-direction:column;gap:8px;">
                        <button class="btn btn-outline" onclick="quickChat('Explain RSI')" style="text-align:left;">📊 Explain RSI</button>
                        <button class="btn btn-outline" onclick="quickChat('Explain position sizing')" style="text-align:left;">📏 Position Sizing</button>
                        <button class="btn btn-outline" onclick="quickChat('Explain stop loss')" style="text-align:left;">⚠️ Stop Loss</button>
                        <button class="btn btn-outline" onclick="quickChat('What is FOMO?')" style="text-align:left;">🧠 FOMO & FUD</button>
                    </div>

                    <h4 style="margin:20px 0 15px;">🔄 Trade</h4>
                    <div style="display:flex;flex-direction:column;gap:8px;">
                        <button class="btn btn-success" onclick="quickChat('Buy Bitcoin')" style="text-align:left;">🟢 Buy Bitcoin</button>
                        <button class="btn btn-success" onclick="quickChat('Buy Ethereum')" style="text-align:left;">🟢 Buy Ethereum</button>
                        <button class="btn btn-danger" onclick="quickChat('Close all positions')" style="text-align:left;">🔴 Close All</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Dashboard Page -->
        <div id="page-dashboard" class="page">
            <div class="header">
                <h1>Dashboard</h1>
                <div class="header-actions">
                    <div class="live-dot"></div>
                    <span style="color:var(--text-secondary);margin-right:15px;">Live</span>
                    <button class="btn btn-primary" onclick="scanMarket()">🔍 Scan Market</button>
                    <button class="btn btn-outline" onclick="refreshAll()">🔄 Refresh</button>
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="card-title">Total Equity</div>
                    <div class="stat-value" id="totalEquity">$0.00</div>
                    <div class="stat-label">Initial: $<span id="initialCapital">100</span></div>
                </div>
                <div class="card">
                    <div class="card-title">Total P&L</div>
                    <div class="stat-value" id="totalPnl">$0.00</div>
                    <div class="stat-label" id="pnlPercent">0.00%</div>
                </div>
                <div class="card">
                    <div class="card-title">Open Positions</div>
                    <div class="stat-value" id="positionsCount">0</div>
                    <div class="stat-label">Active trades</div>
                </div>
                <div class="card">
                    <div class="card-title">Win Rate</div>
                    <div class="stat-value" id="winRate">0%</div>
                    <div class="stat-label"><span id="totalTrades">0</span> total trades</div>
                </div>
            </div>

            <div class="grid">
                <div class="card" style="grid-column: span 2;">
                    <div class="card-header">
                        <div class="card-title">Top Signals</div>
                        <span style="color:var(--text-secondary);font-size:0.85em;">Last scan: <span id="lastScan">Never</span></span>
                    </div>
                    <div id="topSignals">
                        <p style="color:var(--text-secondary);">Click "Scan Market" to analyze</p>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title">Quick Actions</div>
                    <div style="display:flex;flex-direction:column;gap:10px;margin-top:15px;">
                        <button class="btn btn-success" onclick="autoTrade()">🤖 Auto Trade</button>
                        <button class="btn btn-danger" onclick="closeAllPositions()">🛑 Close All</button>
                        <button class="btn btn-outline" onclick="showPage('settings')">⚙️ Settings</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Signals Page -->
        <div id="page-signals" class="page active">
            <div class="header">
                <h1>Trading Signals</h1>
                <button class="btn btn-primary" onclick="scanMarket()">🔍 Scan All Assets</button>
            </div>

            <div class="tabs">
                <div class="tab active" data-filter="all">All</div>
                <div class="tab" data-filter="buy">Buy Signals</div>
                <div class="tab" data-filter="sell">Sell Signals</div>
            </div>

            <div class="card">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Symbol</th>
                                <th>Price</th>
                                <th>Signal</th>
                                <th>Confidence</th>
                                <th>Scores</th>
                                <th>SL / TP</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody id="signalsTable">
                            <tr><td colspan="7" style="text-align:center;color:var(--text-secondary);">No signals yet. Click "Scan All Assets"</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Portfolio Page -->
        <div id="page-portfolio" class="page">
            <div class="header">
                <h1>Portfolio</h1>
                <button class="btn btn-outline" onclick="refreshPortfolio()">🔄 Refresh Prices</button>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="card-title">Cash</div>
                    <div class="stat-value" id="portfolioCash">$0.00</div>
                </div>
                <div class="card">
                    <div class="card-title">Positions Value</div>
                    <div class="stat-value" id="portfolioPositions">$0.00</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Open Positions</div>
                <div id="positionsList" style="margin-top:15px;">
                    <p style="color:var(--text-secondary);">No open positions</p>
                </div>
            </div>
        </div>

        <!-- Trades Page -->
        <div id="page-trades" class="page">
            <div class="header">
                <h1>Trade History</h1>
            </div>

            <div class="card">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Symbol</th>
                                <th>Side</th>
                                <th>Quantity</th>
                                <th>Price</th>
                                <th>P&L</th>
                            </tr>
                        </thead>
                        <tbody id="tradesTable">
                            <tr><td colspan="6" style="text-align:center;color:var(--text-secondary);">No trades yet</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Settings Page -->
        <div id="page-settings" class="page">
            <div class="header">
                <h1>Settings</h1>
                <button class="btn btn-primary" onclick="saveSettings()">💾 Save Settings</button>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="card-title">Trading Settings</div>
                    <div class="form-group">
                        <label>Initial Capital ($)</label>
                        <input type="number" id="settingCapital" value="100">
                    </div>
                    <div class="form-group">
                        <label>Risk Level</label>
                        <select id="settingRisk">
                            <option value="conservative">Conservative (2% SL, 4% TP)</option>
                            <option value="moderate" selected>Moderate (3% SL, 6% TP)</option>
                            <option value="aggressive">Aggressive (5% SL, 10% TP)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Min Confidence (%)</label>
                        <input type="number" id="settingConfidence" value="65" min="0" max="100">
                    </div>
                    <div class="form-group">
                        <label>Scan Interval (minutes)</label>
                        <input type="number" id="settingScanInterval" value="5" min="1">
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Assets</div>
                    <div class="form-group">
                        <label>Stocks (comma-separated)</label>
                        <input type="text" id="settingStocks" value="NVDA, SPY, QQQ, AAPL, TSLA, AMD">
                    </div>
                    <div class="form-group">
                        <label>Crypto (comma-separated)</label>
                        <input type="text" id="settingCrypto" value="bitcoin, ethereum">
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Data Sources</div>
                    <div class="form-group">
                        <label><input type="checkbox" id="settingEnableNews" checked> Enable News Analysis</label>
                    </div>
                    <div class="form-group">
                        <label><input type="checkbox" id="settingEnableSocial" checked> Enable Social Sentiment</label>
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Alpaca API (Optional)</div>
                    <p style="color:var(--text-secondary);font-size:0.85em;margin-bottom:15px;">
                        For real paper trading. Get FREE keys at alpaca.markets
                    </p>
                    <div class="form-group">
                        <label>API Key</label>
                        <input type="text" id="settingAlpacaKey" placeholder="PKXXXXXXXXXX">
                    </div>
                    <div class="form-group">
                        <label>Secret Key</label>
                        <input type="password" id="settingAlpacaSecret" placeholder="••••••••••••">
                    </div>
                    <button class="btn btn-outline" onclick="testAlpaca()">Test Connection</button>
                </div>
            </div>
        </div>

        <!-- Alerts Page -->
        <div id="page-alerts" class="page">
            <div class="header">
                <h1>Alerts</h1>
                <button class="btn btn-outline" onclick="markAllRead()">✓ Mark All Read</button>
            </div>

            <div class="card">
                <div id="alertsList">
                    <p style="color:var(--text-secondary);">No alerts</p>
                </div>
            </div>
        </div>

        <!-- Deep Analysis Page -->
        <div id="page-analysis" class="page">
            <div class="header">
                <h1>🧠 Deep Analysis</h1>
                <div class="header-actions">
                    <select id="analysisAsset" style="padding:10px;background:var(--bg-card);border:1px solid var(--border);color:white;border-radius:6px;">
                        <option value="BTC">Bitcoin (BTC)</option>
                        <option value="ETH">Ethereum (ETH)</option>
                        <option value="SPY">S&P 500 (SPY)</option>
                        <option value="QQQ">NASDAQ (QQQ)</option>
                        <option value="NVDA">NVIDIA (NVDA)</option>
                    </select>
                    <button class="btn btn-primary" onclick="runDeepAnalysis()">🔬 Run Deep Analysis</button>
                </div>
            </div>

            <div id="analysisLoading" style="display:none;text-align:center;padding:40px;">
                <p style="font-size:1.2em;">🔄 Running multi-agent analysis...</p>
                <p style="color:var(--text-secondary);" id="analysisStatus">Initializing agents...</p>
            </div>

            <div id="analysisResults" style="display:none;">
                <!-- Summary Card -->
                <div class="card" style="margin-bottom:20px;border-left:4px solid var(--accent);">
                    <h3 id="analysisTitle" style="margin-bottom:15px;">Analysis Results</h3>
                    <div id="analysisSummary" style="font-size:1.1em;line-height:1.6;"></div>
                    <div style="margin-top:20px;display:flex;gap:20px;flex-wrap:wrap;">
                        <div style="background:var(--bg-secondary);padding:15px;border-radius:8px;min-width:150px;">
                            <div style="color:var(--text-secondary);font-size:0.85em;">Recommendation</div>
                            <div id="analysisAction" style="font-size:1.5em;font-weight:bold;margin-top:5px;">-</div>
                        </div>
                        <div style="background:var(--bg-secondary);padding:15px;border-radius:8px;min-width:150px;">
                            <div style="color:var(--text-secondary);font-size:0.85em;">Confidence</div>
                            <div id="analysisConfidence" style="font-size:1.5em;font-weight:bold;margin-top:5px;">-</div>
                        </div>
                        <div style="background:var(--bg-secondary);padding:15px;border-radius:8px;min-width:150px;">
                            <div style="color:var(--text-secondary);font-size:0.85em;">Consensus</div>
                            <div id="analysisConsensus" style="font-size:1.5em;font-weight:bold;margin-top:5px;">-</div>
                        </div>
                        <div style="background:var(--bg-secondary);padding:15px;border-radius:8px;min-width:150px;">
                            <div style="color:var(--text-secondary);font-size:0.85em;">Hold Time</div>
                            <div id="analysisHoldTime" style="font-size:1em;margin-top:5px;">-</div>
                        </div>
                    </div>
                </div>

                <!-- Key Reasons -->
                <div class="card" style="margin-bottom:20px;">
                    <h4 style="margin-bottom:15px;">📋 Key Reasons</h4>
                    <ul id="analysisReasons" style="list-style:none;padding:0;"></ul>
                </div>

                <!-- Trade Setup -->
                <div class="grid">
                    <div class="card">
                        <h4 style="margin-bottom:15px;">💡 Opportunity</h4>
                        <p id="analysisOpportunity" style="color:var(--success);"></p>
                    </div>
                    <div class="card">
                        <h4 style="margin-bottom:15px;">⚠️ Primary Risk</h4>
                        <p id="analysisRisk" style="color:var(--danger);"></p>
                    </div>
                </div>

                <!-- Agent Opinions -->
                <div class="card" style="margin-top:20px;">
                    <h4 style="margin-bottom:15px;">🤖 Agent Opinions</h4>
                    <div id="agentOpinions" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:15px;"></div>
                </div>

                <!-- Learning Points -->
                <div class="card" style="margin-top:20px;background:linear-gradient(135deg, var(--bg-card), #1e1e35);">
                    <h4 style="margin-bottom:15px;">📚 What You Can Learn From This</h4>
                    <ul id="analysisLearning" style="list-style:none;padding:0;"></ul>
                </div>

                <!-- Warnings -->
                <div class="card" style="margin-top:20px;border-left:4px solid var(--warning);">
                    <h4 style="margin-bottom:15px;">⚠️ Warnings</h4>
                    <ul id="analysisWarnings" style="list-style:none;padding:0;"></ul>
                </div>
            </div>

            <div id="analysisEmpty" class="card" style="text-align:center;padding:40px;">
                <p style="font-size:1.2em;">Select an asset and click "Run Deep Analysis"</p>
                <p style="color:var(--text-secondary);margin-top:10px;">The multi-agent system will analyze technical, fundamental, news, and social data</p>
            </div>
        </div>

        <!-- Opportunities Page -->
        <div id="page-opportunities" class="page">
            <div class="header">
                <h1>💡 Trading Opportunities</h1>
                <button class="btn btn-primary" onclick="scanOpportunities()">🔍 Scan All Assets</button>
            </div>

            <div id="opportunitiesLoading" style="display:none;text-align:center;padding:40px;">
                <p style="font-size:1.2em;">🔄 Scanning for opportunities...</p>
            </div>

            <div id="opportunitiesList"></div>

            <div id="opportunitiesEmpty" class="card" style="text-align:center;padding:40px;">
                <p style="font-size:1.2em;">Click "Scan All Assets" to find opportunities</p>
                <p style="color:var(--text-secondary);margin-top:10px;">The system will analyze all assets and explain each opportunity in detail</p>
            </div>
        </div>

        <!-- Learn Page -->
        <div id="page-learn" class="page">
            <div class="header">
                <h1>📚 Trading Education</h1>
            </div>

            <div class="grid">
                <div class="card" onclick="showLessonCategory('basics')" style="cursor:pointer;">
                    <h3>📖 Trading Basics</h3>
                    <p style="color:var(--text-secondary);margin-top:10px;">What is trading, order types, getting started</p>
                </div>
                <div class="card" onclick="showLessonCategory('technical')" style="cursor:pointer;">
                    <h3>📊 Technical Analysis</h3>
                    <p style="color:var(--text-secondary);margin-top:10px;">Charts, indicators, patterns, and more</p>
                </div>
                <div class="card" onclick="showLessonCategory('fundamental')" style="cursor:pointer;">
                    <h3>📈 Fundamental Analysis</h3>
                    <p style="color:var(--text-secondary);margin-top:10px;">Value, metrics, and what drives prices</p>
                </div>
                <div class="card" onclick="showLessonCategory('risk')" style="cursor:pointer;">
                    <h3>⚖️ Risk Management</h3>
                    <p style="color:var(--text-secondary);margin-top:10px;">Position sizing, stop losses, protecting capital</p>
                </div>
                <div class="card" onclick="showLessonCategory('psychology')" style="cursor:pointer;">
                    <h3>🧠 Trading Psychology</h3>
                    <p style="color:var(--text-secondary);margin-top:10px;">Emotions, discipline, mindset</p>
                </div>
                <div class="card" onclick="showLessonCategory('crypto')" style="cursor:pointer;">
                    <h3>₿ Crypto Trading</h3>
                    <p style="color:var(--text-secondary);margin-top:10px;">Crypto-specific knowledge and strategies</p>
                </div>
                <div class="card" onclick="showLessonCategory('strategies')" style="cursor:pointer;">
                    <h3>🎯 Trading Strategies</h3>
                    <p style="color:var(--text-secondary);margin-top:10px;">Complete strategies you can use</p>
                </div>
            </div>

            <div id="lessonContent" class="card" style="margin-top:20px;display:none;">
                <button class="btn btn-outline" onclick="hideLessonContent()" style="margin-bottom:15px;">← Back to Categories</button>
                <div id="lessonText" style="line-height:1.8;white-space:pre-wrap;"></div>
            </div>
        </div>
    </main>

    <script>
        // State
        let currentSignals = {};
        let autoRefreshInterval = null;

        // ============================================
        // NAVIGATION - Must be first so onclick works
        // ============================================
        function showPage(page) {
            console.log('Showing page:', page);
            try {
                // Remove active from all nav items
                var navItems = document.querySelectorAll('.nav-item');
                for (var i = 0; i < navItems.length; i++) {
                    navItems[i].classList.remove('active');
                }

                // Remove active from all pages
                var pages = document.querySelectorAll('.page');
                for (var j = 0; j < pages.length; j++) {
                    pages[j].classList.remove('active');
                }

                // Add active to clicked nav item
                var navItem = document.querySelector('[data-page="' + page + '"]');
                if (navItem) {
                    navItem.classList.add('active');
                }

                // Show the selected page
                var pageEl = document.getElementById('page-' + page);
                if (pageEl) {
                    pageEl.classList.add('active');
                }

                // Load page-specific data
                if (page === 'portfolio') refreshPortfolio();
                if (page === 'trades') loadTrades();
                if (page === 'settings') loadSettings();
                if (page === 'alerts') loadAlerts();
            } catch (err) {
                console.error('Error showing page:', err);
            }
        }

        // Wait for DOM to be ready for auto-refresh
        document.addEventListener('DOMContentLoaded', function() {
            console.log('ShopGuard Platform Ready');
            refreshAll();
            setInterval(refreshAll, 30000);
        });

        // API Calls with error handling
        async function api(endpoint, method = 'GET', data = null) {
            try {
                const opts = { method, headers: { 'Content-Type': 'application/json' } };
                if (data) opts.body = JSON.stringify(data);
                const resp = await fetch('/api/' + endpoint, opts);
                if (!resp.ok) {
                    console.error('API error:', resp.status, resp.statusText);
                    return { success: false, error: resp.statusText };
                }
                return await resp.json();
            } catch (err) {
                console.error('API call failed:', endpoint, err);
                return { success: false, error: err.message };
            }
        }

        // Dashboard
        async function refreshAll() {
            try {
                const data = await api('dashboard');
                if (!data.success) {
                    console.warn('Dashboard API returned error:', data.error);
                    return;
                }

                // Update equity
                const totalEquityEl = document.getElementById('totalEquity');
                if (totalEquityEl && data.portfolio) {
                    totalEquityEl.textContent = '$' + (data.portfolio.equity || 0).toFixed(2);
                }

                const initialCapitalEl = document.getElementById('initialCapital');
                if (initialCapitalEl && data.portfolio) {
                    initialCapitalEl.textContent = (data.portfolio.initial_capital || 100).toFixed(0);
                }

                // Update PnL
                if (data.portfolio) {
                    const pnl = data.portfolio.total_pnl || 0;
                    const pnlEl = document.getElementById('totalPnl');
                    if (pnlEl) {
                        pnlEl.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
                        pnlEl.className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');
                    }
                    const pnlPctEl = document.getElementById('pnlPercent');
                    if (pnlPctEl) {
                        pnlPctEl.textContent = (data.portfolio.total_pnl_pct || 0).toFixed(2) + '%';
                    }
                }

                // Update positions
                const posCountEl = document.getElementById('positionsCount');
                if (posCountEl && data.portfolio) {
                    posCountEl.textContent = (data.portfolio.positions || []).length;
                }

                // Update stats
                if (data.stats) {
                    const winRateEl = document.getElementById('winRate');
                    if (winRateEl) winRateEl.textContent = (data.stats.win_rate || 0) + '%';
                    const totalTradesEl = document.getElementById('totalTrades');
                    if (totalTradesEl) totalTradesEl.textContent = data.stats.total_trades || 0;
                }

                // Update last scan
                const lastScanEl = document.getElementById('lastScan');
                if (lastScanEl) lastScanEl.textContent = data.last_scan || 'Never';

                // Update alerts
                const alertCountEl = document.getElementById('alertCount');
                if (alertCountEl) alertCountEl.textContent = data.unread_alerts || 0;

                // Update signals
                if (data.signals && Object.keys(data.signals).length > 0) {
                    updateTopSignals(data.signals);
                }
            } catch (err) {
                console.error('Error refreshing dashboard:', err);
            }
        }

        function updateTopSignals(signals) {
            const container = document.getElementById('topSignals');
            const sorted = Object.values(signals)
                .filter(s => s.signal !== 'HOLD')
                .sort((a, b) => b.confidence - a.confidence)
                .slice(0, 5);

            if (sorted.length === 0) {
                container.innerHTML = '<p style="color:var(--text-secondary);">No actionable signals</p>';
                return;
            }

            container.innerHTML = sorted.map(s => {
                const signalClass = s.signal.includes('BUY') ? 'signal-buy' : s.signal.includes('SELL') ? 'signal-sell' : 'signal-hold';
                return `
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:10px;border-bottom:1px solid var(--border);">
                        <div>
                            <strong>${s.symbol}</strong>
                            <span class="signal-badge ${signalClass}">${s.signal}</span>
                            <div class="score-bar">
                                <span class="score score-tech">T:${s.technical_score.toFixed(2)}</span>
                                <span class="score score-news">N:${s.news_score.toFixed(2)}</span>
                                <span class="score score-social">S:${s.social_score.toFixed(2)}</span>
                            </div>
                        </div>
                        <div style="text-align:right;">
                            <div>$${s.price.toFixed(2)}</div>
                            <div style="color:var(--text-secondary);font-size:0.85em;">${(s.confidence*100).toFixed(0)}% conf</div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Scan Market
        async function scanMarket() {
            document.getElementById('topSignals').innerHTML = '<p>Scanning markets...</p>';
            const data = await api('scan', 'POST');
            if (data.success) {
                currentSignals = data.signals;
                updateTopSignals(data.signals);
                updateSignalsTable(data.signals);
            }
        }

        function updateSignalsTable(signals) {
            const tbody = document.getElementById('signalsTable');
            const rows = Object.values(signals).sort((a, b) => b.confidence - a.confidence);

            if (rows.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);">No signals</td></tr>';
                return;
            }

            tbody.innerHTML = rows.map(s => {
                const signalClass = s.signal.includes('BUY') ? 'signal-buy' : s.signal.includes('SELL') ? 'signal-sell' : 'signal-hold';
                return `
                    <tr>
                        <td><strong>${s.symbol}</strong></td>
                        <td>$${s.price.toFixed(2)}</td>
                        <td><span class="signal-badge ${signalClass}">${s.signal}</span></td>
                        <td>${(s.confidence*100).toFixed(0)}%</td>
                        <td>
                            <div class="score-bar">
                                <span class="score score-tech">T:${s.technical_score.toFixed(2)}</span>
                                <span class="score score-news">N:${s.news_score.toFixed(2)}</span>
                                <span class="score score-social">S:${s.social_score.toFixed(2)}</span>
                            </div>
                        </td>
                        <td>$${s.stop_loss.toFixed(2)} / $${s.take_profit.toFixed(2)}</td>
                        <td>
                            ${s.signal.includes('BUY') ? `<button class="btn btn-success" onclick="executeTrade('${s.symbol}', 'buy')">Buy</button>` : ''}
                            ${s.signal.includes('SELL') ? `<button class="btn btn-danger" onclick="executeTrade('${s.symbol}', 'sell')">Sell</button>` : ''}
                        </td>
                    </tr>
                `;
            }).join('');
        }

        // Auto Trade
        async function autoTrade() {
            if (!confirm('Execute all high-confidence signals?')) return;
            const data = await api('auto-trade', 'POST');
            alert(data.message);
            refreshAll();
        }

        // Execute Trade
        async function executeTrade(symbol, side) {
            const data = await api('trade', 'POST', { symbol, side });
            alert(data.message);
            refreshAll();
            refreshPortfolio();
        }

        // Portfolio
        async function refreshPortfolio() {
            try {
                const data = await api('portfolio');
                if (!data.success) {
                    console.warn('Portfolio API error:', data.error);
                    return;
                }

                const cashEl = document.getElementById('portfolioCash');
                if (cashEl) cashEl.textContent = '$' + (data.cash || 0).toFixed(2);

                const posValEl = document.getElementById('portfolioPositions');
                if (posValEl) posValEl.textContent = '$' + (data.positions_value || 0).toFixed(2);

                const list = document.getElementById('positionsList');
                if (!list) return;

                if (!data.positions || data.positions.length === 0) {
                    list.innerHTML = '<p style="color:var(--text-secondary);">No open positions</p>';
                    return;
                }

                list.innerHTML = data.positions.map(p => {
                    const pnl = (p.current_price - p.entry_price) * p.quantity;
                    const pnlPct = ((p.current_price - p.entry_price) / p.entry_price * 100);
                    const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                    return '<div class="position-card">' +
                        '<div class="position-header">' +
                            '<strong>' + p.symbol + '</strong>' +
                            '<span class="' + pnlClass + '">' + (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2) + ' (' + pnlPct.toFixed(1) + '%)</span>' +
                        '</div>' +
                        '<div style="display:flex;justify-content:space-between;color:var(--text-secondary);font-size:0.85em;">' +
                            '<span>Qty: ' + p.quantity.toFixed(4) + '</span>' +
                            '<span>Entry: $' + p.entry_price.toFixed(2) + '</span>' +
                            '<span>Current: $' + p.current_price.toFixed(2) + '</span>' +
                        '</div>' +
                        '<div style="margin-top:10px;">' +
                            '<button class="btn btn-danger" onclick="closePosition(\'' + p.symbol + '\')">Close Position</button>' +
                        '</div>' +
                    '</div>';
                }).join('');
            } catch (err) {
                console.error('Error loading portfolio:', err);
            }
        }

        async function closePosition(symbol) {
            if (!confirm(`Close ${symbol} position?`)) return;
            await api('trade', 'POST', { symbol, side: 'sell' });
            refreshPortfolio();
            refreshAll();
        }

        async function closeAllPositions() {
            if (!confirm('Close ALL positions?')) return;
            await api('close-all', 'POST');
            refreshPortfolio();
            refreshAll();
        }

        // Trades
        async function loadTrades() {
            try {
                const data = await api('trades');
                const tbody = document.getElementById('tradesTable');
                if (!tbody) return;

                if (!data.trades || data.trades.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);">No trades yet</td></tr>';
                    return;
                }

                tbody.innerHTML = data.trades.map(t => {
                    const sideClass = t.side === 'BUY' ? 'positive' : 'negative';
                    const pnlClass = (t.pnl || 0) >= 0 ? 'positive' : 'negative';
                    return '<tr>' +
                        '<td>' + new Date(t.timestamp).toLocaleString() + '</td>' +
                        '<td><strong>' + t.symbol + '</strong></td>' +
                        '<td class="' + sideClass + '">' + t.side + '</td>' +
                        '<td>' + (t.quantity || 0).toFixed(4) + '</td>' +
                        '<td>$' + (t.price || 0).toFixed(2) + '</td>' +
                        '<td class="' + pnlClass + '">' + (t.side === 'SELL' ? ((t.pnl || 0) >= 0 ? '+' : '') + '$' + (t.pnl || 0).toFixed(2) : '-') + '</td>' +
                    '</tr>';
                }).join('');
            } catch (err) {
                console.error('Error loading trades:', err);
            }
        }

        // Settings
        async function loadSettings() {
            try {
                const data = await api('settings');
                if (!data.success) {
                    console.warn('Settings API error:', data.error);
                    return;
                }

                const el = (id, val) => { const e = document.getElementById(id); if (e) e.value = val; };
                const chk = (id, val) => { const e = document.getElementById(id); if (e) e.checked = val; };

                el('settingCapital', data.initial_capital || 100);
                el('settingRisk', data.risk_level || 'moderate');
                el('settingConfidence', (data.min_confidence || 0.65) * 100);
                el('settingScanInterval', data.scan_interval || 5);
                el('settingStocks', (data.stocks || []).join(', '));
                el('settingCrypto', (data.crypto || []).join(', '));
                chk('settingEnableNews', data.enable_news !== false);
                chk('settingEnableSocial', data.enable_social !== false);
            } catch (err) {
                console.error('Error loading settings:', err);
            }
        }

        async function saveSettings() {
            const settings = {
                initial_capital: document.getElementById('settingCapital').value,
                risk_level: document.getElementById('settingRisk').value,
                min_confidence: document.getElementById('settingConfidence').value / 100,
                scan_interval: document.getElementById('settingScanInterval').value,
                stocks: document.getElementById('settingStocks').value.split(',').map(s => s.trim()),
                crypto: document.getElementById('settingCrypto').value.split(',').map(s => s.trim()),
                enable_news: document.getElementById('settingEnableNews').checked,
                enable_social: document.getElementById('settingEnableSocial').checked,
                alpaca_api_key: document.getElementById('settingAlpacaKey').value,
                alpaca_secret_key: document.getElementById('settingAlpacaSecret').value
            };

            const data = await api('settings', 'POST', settings);
            alert(data.message);
        }

        // Alerts
        async function loadAlerts() {
            try {
                const data = await api('alerts');
                const list = document.getElementById('alertsList');
                if (!list) return;

                if (!data.alerts || data.alerts.length === 0) {
                    list.innerHTML = '<p style="color:var(--text-secondary);">No alerts</p>';
                    return;
                }

                list.innerHTML = data.alerts.map(a => {
                    return '<div class="alert-item alert-' + (a.severity || 'info') + '">' +
                        '<div class="alert-dot"></div>' +
                        '<div style="flex:1;">' +
                            '<strong>' + (a.symbol || 'System') + '</strong>: ' + (a.message || '') +
                            '<div style="color:var(--text-secondary);font-size:0.8em;">' + new Date(a.timestamp).toLocaleString() + '</div>' +
                        '</div>' +
                    '</div>';
                }).join('');
            } catch (err) {
                console.error('Error loading alerts:', err);
            }
        }

        async function markAllRead() {
            await api('alerts/read-all', 'POST');
            document.getElementById('alertCount').textContent = '0';
            loadAlerts();
        }

        // Deep Analysis
        async function runDeepAnalysis() {
            const asset = document.getElementById('analysisAsset').value;
            document.getElementById('analysisEmpty').style.display = 'none';
            document.getElementById('analysisResults').style.display = 'none';
            document.getElementById('analysisLoading').style.display = 'block';

            try {
                const data = await api(`deep-analysis/${asset}`, 'POST');
                if (data.success) {
                    displayAnalysis(data.analysis);
                } else {
                    alert('Analysis failed: ' + (data.error || 'Unknown error'));
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }

            document.getElementById('analysisLoading').style.display = 'none';
        }

        function displayAnalysis(a) {
            document.getElementById('analysisResults').style.display = 'block';
            document.getElementById('analysisTitle').textContent = `${a.asset} Deep Analysis`;
            document.getElementById('analysisSummary').textContent = a.summary;

            const actionEl = document.getElementById('analysisAction');
            actionEl.textContent = a.action;
            actionEl.className = a.action.includes('BUY') ? 'positive' : a.action.includes('SELL') ? 'negative' : '';

            document.getElementById('analysisConfidence').textContent = a.confidence;
            document.getElementById('analysisConsensus').textContent = `${(a.consensus_level * 100).toFixed(0)}%`;
            document.getElementById('analysisHoldTime').textContent = a.suggested_hold_time;

            // Reasons
            const reasonsEl = document.getElementById('analysisReasons');
            reasonsEl.innerHTML = a.key_reasons.map(r => `<li style="padding:8px 0;border-bottom:1px solid var(--border);">${r}</li>`).join('');

            // Opportunity and Risk
            document.getElementById('analysisOpportunity').textContent = a.primary_opportunity;
            document.getElementById('analysisRisk').textContent = a.primary_risk;

            // Agent Opinions
            const agentsEl = document.getElementById('agentOpinions');
            agentsEl.innerHTML = '';
            for (const [name, opinion] of Object.entries(a.agent_opinions)) {
                const actionClass = opinion.action.includes('BUY') ? 'positive' : opinion.action.includes('SELL') ? 'negative' : '';
                agentsEl.innerHTML += `
                    <div style="background:var(--bg-secondary);padding:15px;border-radius:8px;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
                            <strong>${opinion.agent}</strong>
                            <span class="${actionClass}">${opinion.action}</span>
                        </div>
                        <p style="color:var(--text-secondary);font-size:0.9em;">${opinion.reasoning.substring(0, 200)}...</p>
                        <div style="margin-top:10px;font-size:0.85em;color:var(--text-secondary);">
                            Confidence: ${opinion.confidence} | Hold: ${opinion.suggested_hold_time}
                        </div>
                    </div>
                `;
            }

            // Learning Points
            const learningEl = document.getElementById('analysisLearning');
            learningEl.innerHTML = a.learning_points.map(l => `<li style="padding:8px 0;border-bottom:1px solid var(--border);">${l}</li>`).join('');

            // Warnings
            const warningsEl = document.getElementById('analysisWarnings');
            warningsEl.innerHTML = a.warnings.map(w => `<li style="padding:8px 0;color:var(--warning);">${w}</li>`).join('');
        }

        // Opportunities
        async function scanOpportunities() {
            document.getElementById('opportunitiesEmpty').style.display = 'none';
            document.getElementById('opportunitiesLoading').style.display = 'block';
            document.getElementById('opportunitiesList').innerHTML = '';

            const data = await api('opportunities', 'POST');

            document.getElementById('opportunitiesLoading').style.display = 'none';

            if (data.success && data.opportunities.length > 0) {
                const list = document.getElementById('opportunitiesList');
                list.innerHTML = data.opportunities.map(o => `
                    <div class="card" style="margin-bottom:20px;border-left:4px solid ${o.direction === 'LONG' ? 'var(--success)' : 'var(--danger)'};">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                            <h3>${o.asset} - ${o.headline}</h3>
                            <span class="signal-badge ${o.direction === 'LONG' ? 'signal-buy' : 'signal-sell'}">${o.direction}</span>
                        </div>
                        <div style="background:var(--bg-secondary);padding:15px;border-radius:8px;margin-bottom:15px;">
                            <strong>Why Now:</strong> ${o.why_now}
                        </div>
                        <p style="margin-bottom:15px;">${o.full_explanation.substring(0, 500)}...</p>
                        <div class="grid" style="margin-bottom:15px;">
                            <div style="background:var(--bg-secondary);padding:10px;border-radius:6px;">
                                <div style="color:var(--text-secondary);font-size:0.8em;">Entry Zone</div>
                                <div>${o.entry_zone}</div>
                            </div>
                            <div style="background:var(--bg-secondary);padding:10px;border-radius:6px;">
                                <div style="color:var(--text-secondary);font-size:0.8em;">Stop Loss</div>
                                <div style="color:var(--danger);">${o.stop_loss}</div>
                            </div>
                            <div style="background:var(--bg-secondary);padding:10px;border-radius:6px;">
                                <div style="color:var(--text-secondary);font-size:0.8em;">Target 1</div>
                                <div style="color:var(--success);">${o.target_1}</div>
                            </div>
                            <div style="background:var(--bg-secondary);padding:10px;border-radius:6px;">
                                <div style="color:var(--text-secondary);font-size:0.8em;">Max Hold</div>
                                <div>${o.max_hold_time}</div>
                            </div>
                        </div>
                        <details>
                            <summary style="cursor:pointer;color:var(--accent);">📚 Learn from this trade</summary>
                            <div style="padding:15px;background:var(--bg-secondary);margin-top:10px;border-radius:6px;white-space:pre-wrap;">${o.lesson}</div>
                        </details>
                    </div>
                `).join('');
            } else {
                document.getElementById('opportunitiesEmpty').style.display = 'block';
                document.getElementById('opportunitiesEmpty').innerHTML = '<p style="color:var(--text-secondary);">No clear opportunities found right now. Market conditions may be mixed.</p>';
            }
        }

        // Education
        async function showLessonCategory(category) {
            const data = await api(`education/${category}`);
            if (data.success && data.lessons.length > 0) {
                document.getElementById('lessonContent').style.display = 'block';
                let html = '<h2>' + category.toUpperCase() + ' LESSONS</h2><br>';
                data.lessons.forEach((lesson, i) => {
                    html += `<div style="margin-bottom:30px;"><h3>${i+1}. ${lesson.title}</h3>${lesson.content}<br><br>`;
                    if (lesson.key_takeaways) {
                        html += '<strong>Key Takeaways:</strong><ul>';
                        lesson.key_takeaways.forEach(t => html += '<li>' + t + '</li>');
                        html += '</ul>';
                    }
                    html += '</div><hr>';
                });
                document.getElementById('lessonText').innerHTML = html;
            }
        }

        function hideLessonContent() {
            document.getElementById('lessonContent').style.display = 'none';
        }

        // AI Assistant Chat
        async function sendChat() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            if (!message) return;

            // Add user message
            addChatMessage('user', message);
            input.value = '';

            // Show typing indicator
            const typingId = addChatMessage('assistant', '🤖 Thinking...');

            try {
                const response = await api('chat', 'POST', { message });

                // Remove typing indicator
                document.getElementById(typingId).remove();

                if (response.success) {
                    addChatMessage('assistant', response.response.message, response.response.suggestions);

                    // If action was taken, refresh relevant data
                    if (response.response.action_taken) {
                        refreshAll();
                    }
                } else {
                    addChatMessage('assistant', 'Sorry, something went wrong. Please try again.');
                }
            } catch (e) {
                document.getElementById(typingId).remove();
                addChatMessage('assistant', 'Error: ' + e.message);
            }
        }

        function quickChat(message) {
            document.getElementById('chatInput').value = message;
            sendChat();
        }

        function addChatMessage(role, message, suggestions = []) {
            const container = document.getElementById('chatMessages');
            const id = 'msg-' + Date.now();

            const isUser = role === 'user';
            const bgColor = isUser ? 'var(--bg-card)' : 'var(--accent)';
            const align = isUser ? 'flex-end' : 'flex-start';

            let html = `
                <div id="${id}" class="chat-message ${role}" style="display:flex;justify-content:${align};margin-bottom:15px;">
                    <div style="background:${bgColor};padding:15px;border-radius:12px;max-width:80%;">
                        ${isUser ? '<strong>You</strong>' : '<strong>🤖 AI Assistant</strong>'}
                        <div style="margin-top:10px;white-space:pre-wrap;">${message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')}</div>
            `;

            if (suggestions && suggestions.length > 0) {
                html += '<div style="margin-top:15px;display:flex;flex-wrap:wrap;gap:8px;">';
                suggestions.forEach(s => {
                    html += `<button class="btn btn-outline" onclick="quickChat('${s}')" style="font-size:0.85em;padding:5px 10px;">${s}</button>`;
                });
                html += '</div>';
            }

            html += '</div></div>';

            container.innerHTML += html;
            container.scrollTop = container.scrollHeight;

            return id;
        }

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
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/auto-trade', methods=['POST'])
def api_auto_trade():
    """Execute all high-confidence signals"""
    try:
        engine.reload_settings()
        signals = engine.scan_all()

        executed = 0
        for symbol, sig in signals.items():
            if sig.confidence >= engine.min_confidence:
                if sig.signal in [SignalType.BUY, SignalType.STRONG_BUY]:
                    if engine.execute_buy(symbol, sig):
                        executed += 1

        return jsonify({"success": True, "message": f"Executed {executed} trades"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/trade', methods=['POST'])
def api_trade():
    """Execute a single trade"""
    try:
        data = request.json
        symbol = data.get('symbol')
        side = data.get('side')

        if side == 'buy':
            sig = engine.last_signals.get(symbol)
            if sig:
                success = engine.execute_buy(symbol, sig)
                return jsonify({"success": success, "message": f"Bought {symbol}" if success else "Buy failed"})
        elif side == 'sell':
            success = engine.execute_sell(symbol)
            return jsonify({"success": success, "message": f"Sold {symbol}" if success else "Sell failed"})

        return jsonify({"success": False, "message": "Invalid request"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/close-all', methods=['POST'])
def api_close_all():
    """Close all positions"""
    try:
        positions = db.get_positions()
        for pos in positions:
            engine.execute_sell(pos.symbol)
        return jsonify({"success": True, "message": f"Closed {len(positions)} positions"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/portfolio')
def api_portfolio():
    """Get portfolio details"""
    try:
        data = engine.get_portfolio_value()
        return jsonify({
            "success": True,
            "cash": data["cash"],
            "positions_value": data["positions_value"],
            "equity": data["equity"],
            "positions": [{
                "symbol": p.symbol,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit
            } for p in data["positions"]]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/trades')
def api_trades():
    """Get trade history"""
    try:
        trades = db.get_trades(50)
        return jsonify({
            "success": True,
            "trades": [{
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "pnl": t.pnl,
                "timestamp": t.timestamp
            } for t in trades]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings"""
    try:
        if request.method == 'POST':
            data = request.json
            for key, value in data.items():
                if key in ['stocks', 'crypto']:
                    db.set_setting(key, json.dumps(value))
                elif key in ['enable_news', 'enable_social']:
                    db.set_setting(key, 'true' if value else 'false')
                else:
                    db.set_setting(key, str(value))

            engine.reload_settings()
            return jsonify({"success": True, "message": "Settings saved!"})
        else:
            settings = db.get_all_settings()
            return jsonify({
                "success": True,
                "initial_capital": float(settings.get("initial_capital", 100)),
                "risk_level": settings.get("risk_level", "moderate"),
                "min_confidence": float(settings.get("min_confidence", 0.65)),
                "scan_interval": int(settings.get("scan_interval", 5)),
                "stocks": json.loads(settings.get("stocks", '["NVDA", "SPY", "QQQ"]')),
                "crypto": json.loads(settings.get("crypto", '["bitcoin", "ethereum"]')),
                "enable_news": settings.get("enable_news", "true") == "true",
                "enable_social": settings.get("enable_social", "true") == "true"
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/alerts')
def api_alerts():
    """Get alerts"""
    try:
        alerts = db.get_alerts()
        return jsonify({
            "success": True,
            "alerts": [{
                "id": a.id,
                "type": a.type,
                "symbol": a.symbol,
                "message": a.message,
                "severity": a.severity,
                "timestamp": a.timestamp,
                "read": a.read
            } for a in alerts]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/alerts/read-all', methods=['POST'])
def api_mark_alerts_read():
    """Mark all alerts as read"""
    try:
        db.mark_all_alerts_read()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# NEW ADVANCED API ROUTES
# =============================================================================

@app.route('/api/deep-analysis/<asset>', methods=['POST'])
def api_deep_analysis(asset):
    """
    Run multi-agent deep analysis on an asset
    Uses all agents: Technical, Fundamental, News, Social, Risk
    """
    try:
        print(f"\n🔬 Running deep analysis for {asset}...")

        # Run the coordinator analysis
        analysis = coordinator.analyze(asset, capital=100)

        # Format agent opinions for response
        agent_opinions = {}
        for name, opinion in analysis.agent_opinions.items():
            agent_opinions[name] = {
                "agent": opinion.agent_name,
                "action": opinion.action.value,
                "confidence": opinion.confidence.name,
                "reasoning": opinion.reasoning,
                "key_factors": opinion.key_factors,
                "suggested_hold_time": opinion.suggested_hold_time,
                "entry_timing": opinion.entry_timing
            }

        return jsonify({
            "success": True,
            "analysis": {
                "asset": analysis.asset,
                "action": analysis.action.value,
                "confidence": analysis.confidence.name,
                "consensus_level": analysis.consensus_level,
                "summary": analysis.summary,
                "key_reasons": analysis.key_reasons,
                "primary_opportunity": analysis.primary_opportunity,
                "primary_risk": analysis.primary_risk,
                "recommended_entry": analysis.recommended_entry,
                "recommended_exit": analysis.recommended_exit,
                "position_size_pct": analysis.position_size_pct,
                "stop_loss_pct": analysis.stop_loss_pct,
                "take_profit_pct": analysis.take_profit_pct,
                "suggested_hold_time": analysis.suggested_hold_time,
                "agent_opinions": agent_opinions,
                "learning_points": analysis.learning_points,
                "what_to_watch": analysis.what_to_watch,
                "warnings": analysis.warnings
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/opportunities', methods=['POST'])
def api_opportunities():
    """
    Scan all assets for trading opportunities with detailed explanations
    """
    try:
        print("\n🔍 Scanning for opportunities...")
        all_opportunities = []

        assets = ['BTC', 'ETH', 'SPY', 'QQQ', 'NVDA']

        for asset in assets:
            print(f"  Analyzing {asset}...")
            try:
                # Run analysis
                analysis = coordinator.analyze(asset, capital=100)

                # Detect opportunities
                opportunities = detector.detect_opportunities(analysis)

                for opp in opportunities:
                    all_opportunities.append(opp.to_dict())
            except Exception as e:
                print(f"  Error analyzing {asset}: {e}")
                continue

        # Sort by strength
        all_opportunities.sort(key=lambda x: x['strength'], reverse=True)

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
    """
    Get educational lessons by category
    """
    try:
        # Map category string to enum
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


@app.route('/api/education/lesson/<lesson_id>')
def api_lesson(lesson_id):
    """
    Get a specific lesson
    """
    try:
        lesson = teacher.get_lesson(lesson_id)
        if not lesson:
            return jsonify({"success": False, "error": "Lesson not found"})

        return jsonify({
            "success": True,
            "lesson": {
                "id": lesson.id,
                "title": lesson.title,
                "category": lesson.category.value,
                "difficulty": lesson.difficulty,
                "content": lesson.content,
                "key_takeaways": lesson.key_takeaways,
                "related_lessons": lesson.related_lessons
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/agent-teachings')
def api_agent_teachings():
    """
    Get educational content from all agents
    """
    try:
        teachings = coordinator.get_all_teaching_content()
        return jsonify({
            "success": True,
            "teachings": teachings
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# AI ASSISTANT CHAT API
# =============================================================================

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    Chat with the AI Trading Assistant
    Natural language interface to control the entire system
    """
    try:
        data = request.json
        message = data.get('message', '')

        if not message:
            return jsonify({"success": False, "error": "No message provided"})

        # Process message through assistant
        response = assistant.process_message(message)

        return jsonify({
            "success": True,
            "response": {
                "message": response.message,
                "action_taken": response.action_taken,
                "data": response.data,
                "suggestions": response.suggestions,
                "follow_up_prompt": response.follow_up_prompt
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


def run_app(host='0.0.0.0', port=5000, debug=False):
    """Run the application"""
    print("\n" + "=" * 60)
    print("  🏦 SHOPGUARD TRADING PLATFORM v2.0")
    print("=" * 60)
    print(f"\n  URL: http://localhost:{port}")
    print("\n  🤖 AI ASSISTANT - Control everything with natural language!")
    print("     Just say: 'Buy Bitcoin', 'Analyze ETH', 'Explain RSI'")
    print("\n  CORE FEATURES:")
    print("    ✓ Real-time market data (CoinGecko + Yahoo Finance)")
    print("    ✓ AI trading signals with confidence scores")
    print("    ✓ Auto-trading with stop loss & take profit")
    print("    ✓ Portfolio management & trade history")
    print("\n  ADVANCED FEATURES:")
    print("    🧠 Multi-Agent Deep Analysis (5 specialized agents)")
    print("    💡 Opportunity Detection with full explanations")
    print("    📚 Complete Trading Education System")
    print("    🎯 Recommended hold times and entry/exit points")
    print("\n" + "=" * 60 + "\n")

    app.run(host=host, port=port, debug=debug)
