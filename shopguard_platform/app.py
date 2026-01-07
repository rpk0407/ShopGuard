"""
ShopGuard Trading Platform - Professional Web Application
"""
import os
import sys
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, Response
import queue

from .database import db
from .engine import engine, SignalType
from .agents.coordinator import coordinator
from .education.teacher import teacher, LessonCategory
from .analysis.opportunity import detector, OpportunityType
from .assistant.brain import TradingAssistant
from .brokers import BrokerManager

# Initialize broker manager
broker_manager = BrokerManager()

# Initialize Matrix Simulation Engine
try:
    from .src.simulation.matrix import Matrix, MarketPhase
    matrix = Matrix(crash_interval=60, tick_interval=2.0)
    MATRIX_AVAILABLE = True
    print("  ✓ Matrix Simulation Engine initialized")
except ImportError:
    matrix = None
    MATRIX_AVAILABLE = False
    print("  ⚠ Matrix not available - using live data only")

# Initialize TITAN Core Components
try:
    from .src.core.titan_brain import TitanBrain, BrainConfig
    from .src.core.fast_math import FastMath
    from .src.core.ecosystem import TitanEcosystem, EcosystemConfig

    titan_brain = TitanBrain()
    fast_math = FastMath()
    fast_math.warmup()  # Pre-compile JIT functions

    # Initialize TITAN ECOSYSTEM (unified trading organism)
    ecosystem_config = EcosystemConfig(
        initial_capital=10000.0,
        max_concurrent_positions=3,
        enable_paper_trading=True
    )
    ecosystem = TitanEcosystem(config=ecosystem_config)
    if matrix:
        ecosystem.attach_matrix(matrix)
    ecosystem.start()

    ECOSYSTEM_AVAILABLE = True
    print("  TitanBrain (3-pillar convergence) ready")
    print("  FastMath JIT acceleration enabled")
    print("  TITAN Ecosystem initialized")
except ImportError as e:
    titan_brain = None
    fast_math = None
    ecosystem = None
    ECOSYSTEM_AVAILABLE = False
    print(f"  Ecosystem not available: {e}")

# Darwin evolution removed per TQO analysis (prove edge first before optimization)
DARWIN_AVAILABLE = False
darwin = None

# SSE clients for Matrix streaming
matrix_clients = []

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize assistant
assistant = TradingAssistant(engine, coordinator, teacher, db)

# =============================================================================
# PROFESSIONAL UI TEMPLATE
# =============================================================================

MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopGuard | AI Trading Platform</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg-dark: #0a0b0e;
            --bg-card: #12141a;
            --bg-hover: #1a1d24;
            --bg-input: #0d0e12;
            --border: #1e2028;
            --border-light: #2a2d38;
            --text: #ffffff;
            --text-dim: #6b7280;
            --text-muted: #4b5563;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --success: #10b981;
            --success-bg: rgba(16, 185, 129, 0.1);
            --danger: #ef4444;
            --danger-bg: rgba(239, 68, 68, 0.1);
            --warning: #f59e0b;
            --warning-bg: rgba(245, 158, 11, 0.1);
            --purple: #8b5cf6;
            --purple-bg: rgba(139, 92, 246, 0.1);
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            line-height: 1.6;
        }

        /* Layout */
        .app { display: flex; min-height: 100vh; }

        .sidebar {
            width: 240px;
            background: var(--bg-card);
            border-right: 1px solid var(--border);
            padding: 24px 16px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }

        .main {
            flex: 1;
            margin-left: 240px;
            padding: 32px;
            max-width: 1400px;
        }

        /* Logo */
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 0 12px;
            margin-bottom: 32px;
        }
        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent), var(--purple));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        .logo-text {
            font-size: 1.25rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text), var(--text-dim));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* Navigation */
        .nav-section {
            margin-bottom: 24px;
        }
        .nav-label {
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            padding: 0 12px;
            margin-bottom: 8px;
        }
        .nav-btn {
            display: flex;
            align-items: center;
            gap: 12px;
            width: 100%;
            padding: 12px;
            background: transparent;
            border: none;
            border-radius: 8px;
            color: var(--text-dim);
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.15s;
            text-align: left;
        }
        .nav-btn:hover { background: var(--bg-hover); color: var(--text); }
        .nav-btn.active { background: var(--accent); color: white; }
        .nav-btn .icon { font-size: 1.1rem; width: 24px; text-align: center; }

        /* Status indicator */
        .status-bar {
            margin-top: auto;
            padding: 16px;
            background: var(--bg-hover);
            border-radius: 12px;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            font-size: 0.85rem;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Pages */
        .page { display: none; }
        .page.active { display: block; animation: fadeIn 0.2s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

        /* Page Header */
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
        }
        .page-title {
            font-size: 1.75rem;
            font-weight: 700;
        }
        .page-subtitle {
            color: var(--text-dim);
            font-size: 0.9rem;
            margin-top: 4px;
        }

        /* Cards */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .card-title {
            font-size: 1rem;
            font-weight: 600;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
        }
        .stat-label {
            font-size: 0.8rem;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }
        .stat-value {
            font-size: 1.75rem;
            font-weight: 700;
        }
        .stat-change {
            font-size: 0.85rem;
            margin-top: 8px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .stat-change.positive { color: var(--success); }
        .stat-change.negative { color: var(--danger); }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }
        .btn-primary { background: var(--accent); color: white; }
        .btn-primary:hover { background: var(--accent-hover); }
        .btn-success { background: var(--success); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-outline {
            background: transparent;
            border: 1px solid var(--border-light);
            color: var(--text);
        }
        .btn-outline:hover { background: var(--bg-hover); border-color: var(--text-dim); }
        .btn-sm { padding: 6px 12px; font-size: 0.8rem; }
        .btn-lg { padding: 14px 28px; font-size: 1rem; }

        /* Tables */
        .table-container { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th {
            text-align: left;
            padding: 12px 16px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-dim);
            border-bottom: 1px solid var(--border);
        }
        td {
            padding: 16px;
            border-bottom: 1px solid var(--border);
            font-size: 0.9rem;
        }
        tr:hover { background: var(--bg-hover); }

        /* Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-success { background: var(--success-bg); color: var(--success); }
        .badge-danger { background: var(--danger-bg); color: var(--danger); }
        .badge-warning { background: var(--warning-bg); color: var(--warning); }
        .badge-purple { background: var(--purple-bg); color: var(--purple); }

        /* Inputs */
        input, select, textarea {
            width: 100%;
            padding: 12px 16px;
            background: var(--bg-input);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 0.9rem;
            transition: border-color 0.15s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--accent);
        }
        .form-group { margin-bottom: 20px; }
        .form-label {
            display: block;
            font-size: 0.85rem;
            font-weight: 500;
            margin-bottom: 8px;
            color: var(--text-dim);
        }

        /* Grid layouts */
        .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }
        .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
        .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }

        /* Signal styles */
        .signal-buy { color: var(--success); }
        .signal-sell { color: var(--danger); }
        .signal-hold { color: var(--warning); }

        /* Progress bar */
        .progress-bar {
            height: 8px;
            background: var(--bg-hover);
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }

        /* Chat */
        .chat-container {
            display: flex;
            flex-direction: column;
            height: calc(100vh - 200px);
            max-height: 700px;
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: var(--bg-input);
            border-radius: 12px;
            margin-bottom: 16px;
        }
        .chat-msg {
            max-width: 80%;
            padding: 14px 18px;
            border-radius: 16px;
            margin-bottom: 12px;
            font-size: 0.95rem;
            line-height: 1.5;
        }
        .chat-user {
            background: var(--accent);
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 4px;
        }
        .chat-ai {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-bottom-left-radius: 4px;
        }
        .chat-input-area {
            display: flex;
            gap: 12px;
        }
        .chat-input-area input {
            flex: 1;
        }

        /* Agent voting */
        .agent-votes {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
            margin-top: 20px;
        }
        .agent-vote {
            text-align: center;
            padding: 16px;
            background: var(--bg-hover);
            border-radius: 12px;
        }
        .agent-name {
            font-size: 0.75rem;
            color: var(--text-dim);
            margin-bottom: 8px;
        }
        .agent-decision {
            font-size: 0.9rem;
            font-weight: 600;
        }

        /* Lesson cards */
        .lesson-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 16px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .lesson-card:hover {
            border-color: var(--accent);
            transform: translateY(-2px);
        }
        .lesson-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .lesson-meta {
            font-size: 0.8rem;
            color: var(--text-dim);
        }
        .lesson-content {
            background: var(--bg-hover);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 16px;
            line-height: 1.8;
        }
        .lesson-content h2 { margin: 24px 0 12px; color: var(--accent); }
        .lesson-content h3 { margin: 20px 0 10px; }
        .lesson-content ul, .lesson-content ol { margin: 12px 0; padding-left: 24px; }
        .lesson-content li { margin: 8px 0; }

        /* Opportunity card */
        .opp-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
        }
        .opp-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }
        .opp-symbol {
            font-size: 1.25rem;
            font-weight: 700;
        }
        .opp-type {
            font-size: 0.85rem;
            color: var(--text-dim);
        }
        .opp-explanation {
            color: var(--text-dim);
            font-size: 0.9rem;
            line-height: 1.6;
            margin-bottom: 16px;
        }

        /* Loading */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 60px;
            color: var(--text-dim);
        }
        .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 12px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Quick actions */
        .quick-actions {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }

        /* Analysis result */
        .analysis-result {
            background: var(--bg-hover);
            border-radius: 12px;
            padding: 24px;
        }
        .analysis-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }
        .analysis-recommendation {
            font-size: 1.5rem;
            font-weight: 700;
        }
        .analysis-metrics {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .analysis-metric {
            background: var(--bg-card);
            padding: 16px;
            border-radius: 8px;
        }
        .metric-label {
            font-size: 0.75rem;
            color: var(--text-dim);
            margin-bottom: 4px;
        }
        .metric-value {
            font-size: 1.1rem;
            font-weight: 600;
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-dim);
        }
        .empty-icon {
            font-size: 3rem;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        /* Responsive */
        @media (max-width: 1200px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .agent-votes { grid-template-columns: repeat(3, 1fr); }
        }
        @media (max-width: 768px) {
            .sidebar { display: none; }
            .main { margin-left: 0; padding: 20px; }
            .stats-grid { grid-template-columns: 1fr; }
            .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="app">
        <!-- Sidebar -->
        <nav class="sidebar">
            <div class="logo">
                <div class="logo-icon">📊</div>
                <div class="logo-text">ShopGuard</div>
            </div>

            <div class="nav-section">
                <div class="nav-label">Main</div>
                <button class="nav-btn active" onclick="nav('dashboard')">
                    <span class="icon">📈</span> Dashboard
                </button>
                <button class="nav-btn" onclick="nav('signals')">
                    <span class="icon">🎯</span> Trading Signals
                </button>
                <button class="nav-btn" onclick="nav('portfolio')">
                    <span class="icon">💼</span> Portfolio
                </button>
            </div>

            <div class="nav-section">
                <div class="nav-label">AI Analysis</div>
                <button class="nav-btn" onclick="nav('chat')">
                    <span class="icon">🤖</span> AI Assistant
                </button>
                <button class="nav-btn" onclick="nav('analysis')">
                    <span class="icon">🧠</span> Deep Analysis
                </button>
                <button class="nav-btn" onclick="nav('opportunities')">
                    <span class="icon">💡</span> Opportunities
                </button>
                <button class="nav-btn" onclick="nav('matrix')">
                    <span class="icon">🔮</span> Matrix Sim
                </button>
                <button class="nav-btn" onclick="nav('evolution')">
                    <span class="icon">🧬</span> Darwin Lab
                </button>
            </div>

            <div class="nav-section">
                <div class="nav-label">More</div>
                <button class="nav-btn" onclick="nav('trades')">
                    <span class="icon">📜</span> Trade History
                </button>
                <button class="nav-btn" onclick="nav('learn')">
                    <span class="icon">📚</span> Education
                </button>
                <button class="nav-btn" onclick="nav('settings')">
                    <span class="icon">⚙️</span> Settings
                </button>
            </div>

            <div class="status-bar">
                <div class="status-item">
                    <span>Market Status</span>
                    <div class="status-dot"></div>
                </div>
                <div class="status-item">
                    <span style="color: var(--text-dim);">Last Scan</span>
                    <span id="lastScanTime" style="font-size: 0.8rem;">--</span>
                </div>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="main">
            <!-- DASHBOARD -->
            <div id="page-dashboard" class="page active">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Dashboard</h1>
                        <p class="page-subtitle">Your trading overview at a glance</p>
                    </div>
                    <div class="quick-actions">
                        <button class="btn btn-primary" onclick="scanMarket()">
                            🔍 Scan Market
                        </button>
                        <button class="btn btn-outline" onclick="loadDashboard()">
                            ↻ Refresh
                        </button>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Total Equity</div>
                        <div class="stat-value" id="stat-equity">$100.00</div>
                        <div class="stat-change positive" id="stat-equity-change">
                            ↑ 0.00%
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Unrealized P&L</div>
                        <div class="stat-value" id="stat-pnl">$0.00</div>
                        <div class="stat-change" id="stat-pnl-pct">0.00%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Open Positions</div>
                        <div class="stat-value" id="stat-positions">0</div>
                        <div class="stat-change" style="color: var(--text-dim)">Active trades</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Win Rate</div>
                        <div class="stat-value" id="stat-winrate">0%</div>
                        <div class="stat-change" id="stat-trades" style="color: var(--text-dim)">0 trades</div>
                    </div>
                </div>

                <div class="grid-2">
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Top Signals</h3>
                            <button class="btn btn-sm btn-outline" onclick="nav('signals')">View All</button>
                        </div>
                        <div id="dashboard-signals">
                            <div class="empty-state">
                                <div class="empty-icon">📡</div>
                                <p>Click "Scan Market" to analyze assets</p>
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title">Quick Actions</h3>
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 12px;">
                            <button class="btn btn-outline btn-lg" onclick="nav('chat')" style="justify-content: flex-start;">
                                🤖 Talk to AI Assistant
                            </button>
                            <button class="btn btn-outline btn-lg" onclick="nav('analysis')" style="justify-content: flex-start;">
                                🧠 Run Deep Analysis
                            </button>
                            <button class="btn btn-outline btn-lg" onclick="nav('opportunities')" style="justify-content: flex-start;">
                                💡 Find Opportunities
                            </button>
                            <button class="btn btn-outline btn-lg" onclick="nav('learn')" style="justify-content: flex-start;">
                                📚 Learn Trading
                            </button>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Current Positions</h3>
                        <button class="btn btn-sm btn-outline" onclick="nav('portfolio')">Manage</button>
                    </div>
                    <div id="dashboard-positions">
                        <div class="empty-state">
                            <p style="color: var(--text-dim);">No open positions</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- SIGNALS -->
            <div id="page-signals" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Trading Signals</h1>
                        <p class="page-subtitle">AI-powered buy/sell recommendations</p>
                    </div>
                    <button class="btn btn-primary btn-lg" onclick="scanMarket()">
                        🔍 Scan All Assets
                    </button>
                </div>

                <div class="card">
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Asset</th>
                                    <th>Price</th>
                                    <th>Signal</th>
                                    <th>Confidence</th>
                                    <th>Technical</th>
                                    <th>News</th>
                                    <th>Social</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="signals-table">
                                <tr>
                                    <td colspan="8">
                                        <div class="empty-state">
                                            <div class="empty-icon">📡</div>
                                            <p>Click "Scan All Assets" to analyze the market</p>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- PORTFOLIO -->
            <div id="page-portfolio" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Portfolio</h1>
                        <p class="page-subtitle">Manage your positions and track performance</p>
                    </div>
                    <button class="btn btn-outline" onclick="loadPortfolio()">
                        ↻ Refresh
                    </button>
                </div>

                <div class="stats-grid" style="grid-template-columns: repeat(3, 1fr);">
                    <div class="stat-card">
                        <div class="stat-label">Available Cash</div>
                        <div class="stat-value" id="port-cash">$100.00</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Positions Value</div>
                        <div class="stat-value" id="port-value">$0.00</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Total Equity</div>
                        <div class="stat-value" id="port-equity">$100.00</div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Open Positions</h3>
                    </div>
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Asset</th>
                                    <th>Quantity</th>
                                    <th>Entry Price</th>
                                    <th>Current Price</th>
                                    <th>P&L</th>
                                    <th>P&L %</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="portfolio-table">
                                <tr>
                                    <td colspan="7">
                                        <div class="empty-state">
                                            <p>No open positions</p>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- AI CHAT -->
            <div id="page-chat" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">AI Trading Assistant</h1>
                        <p class="page-subtitle">Natural language interface to control everything</p>
                    </div>
                </div>

                <div class="card">
                    <div class="chat-container">
                        <div class="chat-messages" id="chat-messages">
                            <div class="chat-msg chat-ai">
                                <strong>🤖 AI Assistant</strong><br><br>
                                Hello! I'm your AI trading assistant. I can help you:
                                <ul style="margin: 12px 0; padding-left: 20px;">
                                    <li><strong>Trade:</strong> "Buy $20 of Bitcoin" or "Sell all ETH"</li>
                                    <li><strong>Analyze:</strong> "Analyze NVDA" or "What do you think about ETH?"</li>
                                    <li><strong>Learn:</strong> "Explain RSI" or "What is position sizing?"</li>
                                    <li><strong>Monitor:</strong> "Show my portfolio" or "Find opportunities"</li>
                                </ul>
                                Just type naturally - I'll understand!
                            </div>
                        </div>
                        <div class="chat-input-area">
                            <input type="text" id="chat-input" placeholder="Ask me anything about trading..."
                                   onkeypress="if(event.key==='Enter')sendChat()">
                            <button class="btn btn-primary" onclick="sendChat()">Send</button>
                        </div>
                    </div>

                    <div style="margin-top: 20px;">
                        <div class="nav-label">Quick Commands</div>
                        <div class="quick-actions" style="margin-top: 12px;">
                            <button class="btn btn-sm btn-outline" onclick="quickChat('Analyze Bitcoin')">Analyze BTC</button>
                            <button class="btn btn-sm btn-outline" onclick="quickChat('Analyze Ethereum')">Analyze ETH</button>
                            <button class="btn btn-sm btn-outline" onclick="quickChat('Show my portfolio')">My Portfolio</button>
                            <button class="btn btn-sm btn-outline" onclick="quickChat('Find opportunities')">Find Opportunities</button>
                            <button class="btn btn-sm btn-outline" onclick="quickChat('Scan the market')">Scan Market</button>
                            <button class="btn btn-sm btn-outline" onclick="quickChat('Explain RSI indicator')">Explain RSI</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- DEEP ANALYSIS -->
            <div id="page-analysis" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Multi-Agent Deep Analysis</h1>
                        <p class="page-subtitle">5 specialized AI agents analyze every aspect</p>
                    </div>
                </div>

                <div class="card">
                    <div style="display: flex; gap: 16px; margin-bottom: 24px;">
                        <select id="analysis-asset" style="max-width: 300px;">
                            <option value="BTC">Bitcoin (BTC)</option>
                            <option value="ETH">Ethereum (ETH)</option>
                            <option value="SPY">S&P 500 ETF (SPY)</option>
                            <option value="QQQ">NASDAQ 100 ETF (QQQ)</option>
                            <option value="NVDA">NVIDIA (NVDA)</option>
                        </select>
                        <button class="btn btn-primary btn-lg" onclick="runAnalysis()">
                            🧠 Run Deep Analysis
                        </button>
                    </div>

                    <div id="analysis-result">
                        <div class="empty-state">
                            <div class="empty-icon">🧠</div>
                            <p>Select an asset and click "Run Deep Analysis"</p>
                            <p style="font-size: 0.85rem; margin-top: 8px;">
                                5 AI agents will analyze: Technical, News, Social, Risk, Fundamental
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- OPPORTUNITIES -->
            <div id="page-opportunities" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Trading Opportunities</h1>
                        <p class="page-subtitle">AI-detected opportunities with explanations</p>
                    </div>
                    <button class="btn btn-primary btn-lg" onclick="findOpportunities()">
                        💡 Scan for Opportunities
                    </button>
                </div>

                <div id="opportunities-list">
                    <div class="card">
                        <div class="empty-state">
                            <div class="empty-icon">💡</div>
                            <p>Click "Scan for Opportunities" to find trading setups</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TRADE HISTORY -->
            <div id="page-trades" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Trade History</h1>
                        <p class="page-subtitle">All your past trades and performance</p>
                    </div>
                </div>

                <div class="card">
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Date</th>
                                    <th>Asset</th>
                                    <th>Side</th>
                                    <th>Quantity</th>
                                    <th>Price</th>
                                    <th>P&L</th>
                                </tr>
                            </thead>
                            <tbody id="trades-table">
                                <tr>
                                    <td colspan="6">
                                        <div class="loading">Loading trades...</div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- EDUCATION -->
            <div id="page-learn" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Trading Education</h1>
                        <p class="page-subtitle">Learn everything about trading from basics to advanced</p>
                    </div>
                </div>

                <div class="grid-3" id="education-categories">
                    <div class="lesson-card" onclick="loadLessons('basics')">
                        <div class="lesson-title">📖 Trading Basics</div>
                        <div class="lesson-meta">What is trading, order types, getting started</div>
                    </div>
                    <div class="lesson-card" onclick="loadLessons('technical')">
                        <div class="lesson-title">📊 Technical Analysis</div>
                        <div class="lesson-meta">Charts, indicators, patterns</div>
                    </div>
                    <div class="lesson-card" onclick="loadLessons('fundamental')">
                        <div class="lesson-title">📈 Fundamental Analysis</div>
                        <div class="lesson-meta">Value, metrics, financial statements</div>
                    </div>
                    <div class="lesson-card" onclick="loadLessons('risk')">
                        <div class="lesson-title">⚖️ Risk Management</div>
                        <div class="lesson-meta">Position sizing, stop losses, protecting capital</div>
                    </div>
                    <div class="lesson-card" onclick="loadLessons('psychology')">
                        <div class="lesson-title">🧠 Trading Psychology</div>
                        <div class="lesson-meta">Emotions, discipline, mindset</div>
                    </div>
                    <div class="lesson-card" onclick="loadLessons('crypto')">
                        <div class="lesson-title">₿ Crypto Trading</div>
                        <div class="lesson-meta">Crypto-specific knowledge</div>
                    </div>
                    <div class="lesson-card" onclick="loadLessons('stocks')">
                        <div class="lesson-title">🏢 Stock Trading</div>
                        <div class="lesson-meta">Stock market, ETFs, sectors</div>
                    </div>
                    <div class="lesson-card" onclick="loadLessons('strategies')">
                        <div class="lesson-title">🎯 Trading Strategies</div>
                        <div class="lesson-meta">Complete trading systems</div>
                    </div>
                    <div class="lesson-card" onclick="loadLessons('advanced')">
                        <div class="lesson-title">🎓 Advanced Topics</div>
                        <div class="lesson-meta">System building, journaling, optimization</div>
                    </div>
                </div>

                <div id="lessons-content" style="display: none;">
                    <button class="btn btn-outline" onclick="showCategories()" style="margin-bottom: 20px;">
                        ← Back to Categories
                    </button>
                    <div id="lessons-list"></div>
                </div>
            </div>

            <!-- SETTINGS -->
            <div id="page-settings" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">Settings</h1>
                        <p class="page-subtitle">Configure your trading parameters</p>
                    </div>
                </div>

                <div class="grid-2">
                    <div class="card">
                        <h3 class="card-title" style="margin-bottom: 24px;">Trading Configuration</h3>

                        <div class="form-group">
                            <label class="form-label">Initial Capital ($)</label>
                            <input type="number" id="set-capital" value="100">
                        </div>

                        <div class="form-group">
                            <label class="form-label">Stop Loss (%)</label>
                            <input type="number" id="set-stoploss" value="3" step="0.5">
                        </div>

                        <div class="form-group">
                            <label class="form-label">Take Profit (%)</label>
                            <input type="number" id="set-takeprofit" value="6" step="0.5">
                        </div>

                        <div class="form-group">
                            <label style="display: flex; align-items: center; gap: 12px; cursor: pointer;">
                                <input type="checkbox" id="set-autotrade" style="width: auto;">
                                <span>Enable Auto-Trading</span>
                            </label>
                        </div>

                        <button class="btn btn-primary" onclick="saveSettings()">
                            Save Settings
                        </button>
                    </div>

                    <div class="card">
                        <h3 class="card-title" style="margin-bottom: 24px;">Broker API Keys</h3>
                        <p style="color: var(--text-dim); font-size: 0.85rem; margin-bottom: 20px;">
                            Optional: Connect to real brokers for live trading
                        </p>

                        <div class="form-group">
                            <label class="form-label">Alpaca API Key</label>
                            <input type="text" id="set-alpaca-key" placeholder="Your Alpaca API key">
                        </div>

                        <div class="form-group">
                            <label class="form-label">Alpaca Secret</label>
                            <input type="password" id="set-alpaca-secret" placeholder="Your Alpaca secret">
                        </div>

                        <div class="form-group">
                            <label class="form-label">Binance API Key</label>
                            <input type="text" id="set-binance-key" placeholder="Your Binance API key">
                        </div>

                        <div class="form-group">
                            <label class="form-label">Binance Secret</label>
                            <input type="password" id="set-binance-secret" placeholder="Your Binance secret">
                        </div>

                        <button class="btn btn-outline" onclick="saveBrokerKeys()">
                            Save API Keys
                        </button>
                    </div>
                </div>
            </div>

            <!-- MATRIX SIMULATION -->
            <div id="page-matrix" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">🔮 Matrix Simulation</h1>
                        <p class="page-subtitle">Reality Simulation Engine - Perfect Storm every 60 seconds</p>
                    </div>
                    <div id="matrix-status" class="quick-actions">
                        <span class="badge badge-warning">Disconnected</span>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Asset</div>
                        <div class="stat-value" id="matrix-asset">BTC/USDT</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Price</div>
                        <div class="stat-value" id="matrix-price">--</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Market Phase</div>
                        <div class="stat-value" id="matrix-phase">--</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Signal</div>
                        <div class="stat-value" id="matrix-signal">--</div>
                    </div>
                </div>

                <div class="grid-2">
                    <div class="card">
                        <h3 class="card-title" style="margin-bottom: 16px;">Three-Pillar Convergence</h3>
                        <div style="display: grid; gap: 16px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>🧬 Bio-Check (Entropy)</span>
                                <span id="matrix-entropy" class="badge">--</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>⚛️ Physics-Check (Hurst)</span>
                                <span id="matrix-hurst" class="badge">--</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>🦠 Micro-Check (Viral K)</span>
                                <span id="matrix-viral" class="badge">--</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>📊 CVD (Whale Activity)</span>
                                <span id="matrix-cvd" class="badge">--</span>
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <h3 class="card-title" style="margin-bottom: 16px;">Signal History</h3>
                        <div id="matrix-history" style="max-height: 200px; overflow-y: auto;">
                            <p style="color: var(--text-dim);">Waiting for signals...</p>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h3 class="card-title" style="margin-bottom: 16px;">Matrix Control</h3>
                    <div style="display: flex; gap: 12px;">
                        <button class="btn btn-primary" onclick="startMatrix()">▶ Start Simulation</button>
                        <button class="btn btn-danger" onclick="stopMatrix()">⏹ Stop</button>
                        <button class="btn btn-outline" onclick="clearMatrixHistory()">Clear History</button>
                    </div>
                    <p style="margin-top: 16px; color: var(--text-dim); font-size: 0.85rem;">
                        The Matrix generates synthetic market data using Geometric Brownian Motion.
                        Every 60 seconds, a "Perfect Storm" crash event occurs to test the convergence detection.
                    </p>
                </div>
            </div>

            <!-- DARWIN EVOLUTION LAB -->
            <div id="page-evolution" class="page">
                <div class="page-header">
                    <div>
                        <h1 class="page-title">🧬 Darwin Evolution Lab</h1>
                        <p class="page-subtitle">Genetic Algorithm Optimization - The Strong Survive</p>
                    </div>
                    <div id="darwin-status" class="quick-actions">
                        <span class="badge badge-warning">Inactive</span>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Generation</div>
                        <div class="stat-value" id="darwin-generation">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Population</div>
                        <div class="stat-value" id="darwin-population">50</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Best Fitness</div>
                        <div class="stat-value" id="darwin-fitness">--</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Alpha Updates</div>
                        <div class="stat-value" id="darwin-updates">0</div>
                    </div>
                </div>

                <div class="grid-2">
                    <div class="card">
                        <h3 class="card-title" style="margin-bottom: 16px;">🏆 Alpha Genome (Current Best)</h3>
                        <div id="alpha-genome" style="display: grid; gap: 12px;">
                            <div style="display: flex; justify-content: space-between;">
                                <span>K-Factor Threshold</span>
                                <span id="alpha-k" class="badge badge-purple">--</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>Entropy Threshold</span>
                                <span id="alpha-entropy" class="badge badge-purple">--</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>Hurst Threshold</span>
                                <span id="alpha-hurst" class="badge badge-purple">--</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>CVD Sensitivity</span>
                                <span id="alpha-cvd" class="badge badge-purple">--</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>Position Size</span>
                                <span id="alpha-position" class="badge badge-purple">--</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>Stop Loss ATR</span>
                                <span id="alpha-stoploss" class="badge badge-purple">--</span>
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <h3 class="card-title" style="margin-bottom: 16px;">📊 Population Distribution</h3>
                        <div id="population-dist">
                            <div style="margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                    <span>Aggressive</span>
                                    <span id="pop-aggressive">20%</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" id="bar-aggressive" style="width: 20%; background: var(--danger);"></div>
                                </div>
                            </div>
                            <div style="margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                    <span>Conservative</span>
                                    <span id="pop-conservative">20%</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" id="bar-conservative" style="width: 20%; background: var(--success);"></div>
                                </div>
                            </div>
                            <div style="margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                    <span>Balanced</span>
                                    <span id="pop-balanced">30%</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" id="bar-balanced" style="width: 30%; background: var(--accent);"></div>
                                </div>
                            </div>
                            <div style="margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                    <span>Chaotic</span>
                                    <span id="pop-chaotic">30%</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" id="bar-chaotic" style="width: 30%; background: var(--warning);"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h3 class="card-title" style="margin-bottom: 16px;">Evolution Control</h3>
                    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                        <button class="btn btn-success" onclick="startEvolution()">🧬 Start Evolution</button>
                        <button class="btn btn-danger" onclick="stopEvolution()">⏹ Stop</button>
                        <button class="btn btn-primary" onclick="runGeneration()">⚡ Force Generation</button>
                        <button class="btn btn-outline" onclick="loadEvolutionStats()">↻ Refresh Stats</button>
                        <button class="btn btn-outline" onclick="hotSwapAlpha()">🔥 Hot-Swap Alpha</button>
                    </div>
                    <p style="margin-top: 16px; color: var(--text-dim); font-size: 0.85rem;">
                        The Darwinian Engine spawns 50 mutant agents with randomized trading parameters.
                        Every generation, the bottom 50% are culled and the top 50% breed to create the next generation.
                        The Alpha (best performer) is automatically hot-swapped into the live TitanBrain.
                    </p>
                </div>

                <div class="card">
                    <h3 class="card-title" style="margin-bottom: 16px;">🧠 TitanBrain Status</h3>
                    <div class="grid-3">
                        <div>
                            <div class="stat-label">Config Version</div>
                            <div id="brain-version" style="font-size: 1.5rem; font-weight: 700;">v1</div>
                        </div>
                        <div>
                            <div class="stat-label">Config Source</div>
                            <div id="brain-source" style="font-size: 1.5rem; font-weight: 700;">default</div>
                        </div>
                        <div>
                            <div class="stat-label">Signals Generated</div>
                            <div id="brain-signals" style="font-size: 1.5rem; font-weight: 700;">0</div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <script>
        // =========================================
        // NAVIGATION
        // =========================================
        function nav(page) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

            document.getElementById('page-' + page).classList.add('active');
            event.target.closest('.nav-btn').classList.add('active');

            // Load page data
            if (page === 'portfolio') loadPortfolio();
            if (page === 'trades') loadTrades();
            if (page === 'settings') loadSettings();
        }

        // =========================================
        // API HELPER
        // =========================================
        async function api(endpoint, method = 'GET', data = null) {
            try {
                const opts = { method, headers: { 'Content-Type': 'application/json' } };
                if (data) opts.body = JSON.stringify(data);
                const resp = await fetch('/api/' + endpoint, opts);
                return await resp.json();
            } catch (err) {
                console.error('API Error:', err);
                return { success: false, error: err.message };
            }
        }

        // =========================================
        // DASHBOARD
        // =========================================
        async function loadDashboard() {
            const data = await api('dashboard');
            if (!data.success) return;

            const p = data.portfolio;
            document.getElementById('stat-equity').textContent = '$' + (p.equity || 0).toFixed(2);
            document.getElementById('stat-pnl').textContent = '$' + (p.total_pnl || 0).toFixed(2);
            document.getElementById('stat-pnl-pct').textContent = (p.total_pnl_pct || 0).toFixed(2) + '%';
            document.getElementById('stat-positions').textContent = p.positions?.length || 0;
            document.getElementById('stat-winrate').textContent = (data.stats?.win_rate || 0).toFixed(0) + '%';
            document.getElementById('stat-trades').textContent = (data.stats?.total_trades || 0) + ' trades';

            // Update stat change colors
            const pnlEl = document.getElementById('stat-pnl-pct');
            pnlEl.className = 'stat-change ' + ((p.total_pnl || 0) >= 0 ? 'positive' : 'negative');

            const changeEl = document.getElementById('stat-equity-change');
            changeEl.className = 'stat-change ' + ((p.total_pnl_pct || 0) >= 0 ? 'positive' : 'negative');
            changeEl.innerHTML = ((p.total_pnl_pct || 0) >= 0 ? '↑ ' : '↓ ') + Math.abs(p.total_pnl_pct || 0).toFixed(2) + '%';

            // Update last scan time
            if (data.last_scan) {
                document.getElementById('lastScanTime').textContent = data.last_scan;
            }

            // Update positions on dashboard
            if (p.positions && p.positions.length > 0) {
                let html = '<table style="width:100%;"><thead><tr><th>Asset</th><th>P&L</th></tr></thead><tbody>';
                p.positions.forEach(pos => {
                    const pnl = (pos.current_price - pos.entry_price) * pos.quantity;
                    const cls = pnl >= 0 ? 'signal-buy' : 'signal-sell';
                    html += `<tr><td>${pos.symbol}</td><td class="${cls}">$${pnl.toFixed(2)}</td></tr>`;
                });
                html += '</tbody></table>';
                document.getElementById('dashboard-positions').innerHTML = html;
            }

            // Update signals on dashboard
            if (data.signals && Object.keys(data.signals).length > 0) {
                let html = '';
                Object.values(data.signals).slice(0, 3).forEach(s => {
                    const cls = s.signal.includes('BUY') ? 'badge-success' : s.signal.includes('SELL') ? 'badge-danger' : 'badge-warning';
                    html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border);">
                        <div>
                            <strong>${s.symbol}</strong>
                            <span style="color:var(--text-dim);margin-left:8px;">$${s.price.toFixed(2)}</span>
                        </div>
                        <span class="badge ${cls}">${s.signal}</span>
                    </div>`;
                });
                document.getElementById('dashboard-signals').innerHTML = html;
            }
        }

        // =========================================
        // SCAN MARKET
        // =========================================
        async function scanMarket() {
            document.getElementById('dashboard-signals').innerHTML = '<div class="loading"><div class="spinner"></div>Scanning markets...</div>';
            document.getElementById('signals-table').innerHTML = '<tr><td colspan="8"><div class="loading"><div class="spinner"></div>Analyzing all assets...</div></td></tr>';

            const data = await api('scan', 'POST');
            if (!data.success) return;

            const signals = Object.values(data.signals).sort((a, b) => b.confidence - a.confidence);

            // Update signals table
            let rows = '';
            signals.forEach(s => {
                const signalCls = s.signal.includes('BUY') ? 'badge-success' : s.signal.includes('SELL') ? 'badge-danger' : 'badge-warning';
                rows += `<tr>
                    <td><strong>${s.symbol}</strong></td>
                    <td>$${s.price.toFixed(2)}</td>
                    <td><span class="badge ${signalCls}">${s.signal}</span></td>
                    <td>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <div class="progress-bar" style="width:60px;">
                                <div class="progress-fill" style="width:${s.confidence*100}%;background:var(--accent);"></div>
                            </div>
                            ${(s.confidence*100).toFixed(0)}%
                        </div>
                    </td>
                    <td>${(s.technical_score*100).toFixed(0)}%</td>
                    <td>${(s.news_score*100).toFixed(0)}%</td>
                    <td>${(s.social_score*100).toFixed(0)}%</td>
                    <td>
                        <button class="btn btn-sm btn-success" onclick="executeTrade('${s.symbol}','buy')">Buy</button>
                        <button class="btn btn-sm btn-danger" onclick="executeTrade('${s.symbol}','sell')">Sell</button>
                    </td>
                </tr>`;
            });
            document.getElementById('signals-table').innerHTML = rows || '<tr><td colspan="8"><div class="empty-state">No signals found</div></td></tr>';

            // Update dashboard signals
            loadDashboard();
        }

        // =========================================
        // PORTFOLIO
        // =========================================
        async function loadPortfolio() {
            const data = await api('portfolio');
            if (!data.success) return;

            document.getElementById('port-cash').textContent = '$' + (data.cash || 0).toFixed(2);
            document.getElementById('port-value').textContent = '$' + (data.positions_value || 0).toFixed(2);
            document.getElementById('port-equity').textContent = '$' + (data.equity || 0).toFixed(2);

            let rows = '';
            (data.positions || []).forEach(p => {
                const pnl = (p.current_price - p.entry_price) * p.quantity;
                const pnlPct = ((p.current_price - p.entry_price) / p.entry_price * 100);
                const cls = pnl >= 0 ? 'signal-buy' : 'signal-sell';
                rows += `<tr>
                    <td><strong>${p.symbol}</strong></td>
                    <td>${p.quantity.toFixed(4)}</td>
                    <td>$${p.entry_price.toFixed(2)}</td>
                    <td>$${p.current_price.toFixed(2)}</td>
                    <td class="${cls}">$${pnl.toFixed(2)}</td>
                    <td class="${cls}">${pnlPct.toFixed(2)}%</td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="executeTrade('${p.symbol}','sell')">Close</button>
                    </td>
                </tr>`;
            });
            document.getElementById('portfolio-table').innerHTML = rows || '<tr><td colspan="7"><div class="empty-state">No open positions</div></td></tr>';
        }

        // =========================================
        // TRADES
        // =========================================
        async function loadTrades() {
            const data = await api('trades');
            if (!data.success) return;

            let rows = '';
            (data.trades || []).forEach(t => {
                const cls = (t.pnl || 0) >= 0 ? 'signal-buy' : 'signal-sell';
                const sideCls = t.side === 'buy' ? 'badge-success' : 'badge-danger';
                rows += `<tr>
                    <td>${t.timestamp}</td>
                    <td><strong>${t.symbol}</strong></td>
                    <td><span class="badge ${sideCls}">${t.side.toUpperCase()}</span></td>
                    <td>${t.quantity.toFixed(4)}</td>
                    <td>$${t.price.toFixed(2)}</td>
                    <td class="${cls}">$${(t.pnl || 0).toFixed(2)}</td>
                </tr>`;
            });
            document.getElementById('trades-table').innerHTML = rows || '<tr><td colspan="6"><div class="empty-state">No trades yet</div></td></tr>';
        }

        // =========================================
        // TRADE EXECUTION
        // =========================================
        async function executeTrade(symbol, side) {
            const data = await api('trade', 'POST', { symbol, side, amount: 10 });
            if (data.success) {
                alert(`✅ ${side.toUpperCase()} order placed for ${symbol}`);
                loadDashboard();
                loadPortfolio();
            } else {
                alert('❌ Trade failed: ' + (data.error || 'Unknown error'));
            }
        }

        // =========================================
        // AI CHAT
        // =========================================
        async function sendChat() {
            const input = document.getElementById('chat-input');
            const msg = input.value.trim();
            if (!msg) return;

            const box = document.getElementById('chat-messages');
            box.innerHTML += `<div class="chat-msg chat-user">${msg}</div>`;
            input.value = '';
            box.scrollTop = box.scrollHeight;

            // Show typing indicator
            const typingId = 'typing-' + Date.now();
            box.innerHTML += `<div class="chat-msg chat-ai" id="${typingId}"><em>Thinking...</em></div>`;
            box.scrollTop = box.scrollHeight;

            const data = await api('chat', 'POST', { message: msg });
            document.getElementById(typingId).remove();

            if (data.success) {
                box.innerHTML += `<div class="chat-msg chat-ai">${data.response.message}</div>`;
                if (data.response.action_taken) {
                    loadDashboard();
                    loadPortfolio();
                }
            } else {
                box.innerHTML += `<div class="chat-msg chat-ai">Sorry, I encountered an error. Please try again.</div>`;
            }
            box.scrollTop = box.scrollHeight;
        }

        function quickChat(msg) {
            document.getElementById('chat-input').value = msg;
            sendChat();
        }

        // =========================================
        // DEEP ANALYSIS
        // =========================================
        function getVoteClass(action) {
            if (!action) return 'signal-hold';
            if (action.includes('BUY')) return 'signal-buy';
            if (action.includes('SELL')) return 'signal-sell';
            return 'signal-hold';
        }

        async function runAnalysis() {
            const asset = document.getElementById('analysis-asset').value;
            document.getElementById('analysis-result').innerHTML = '<div class="loading"><div class="spinner"></div>Running deep analysis on ' + asset + '... (5 AI agents analyzing)</div>';

            const data = await api('deep-analysis/' + asset);
            if (!data.success) {
                document.getElementById('analysis-result').innerHTML = '<div class="empty-state"><p>Analysis failed: ' + (data.error || 'Unknown error') + '</p></div>';
                return;
            }

            const a = data.analysis;
            const recCls = getVoteClass(a.recommendation);
            const consensusPct = ((a.consensus || 0) * 100).toFixed(0);

            // Build agent votes HTML
            let votesHtml = '';
            const agents = [
                {key: 'technical', name: '📊 Technical', desc: 'Price patterns & indicators'},
                {key: 'news', name: '📰 News', desc: 'Latest news sentiment'},
                {key: 'social', name: '💬 Social', desc: 'Reddit & community mood'},
                {key: 'risk', name: '⚠️ Risk', desc: 'Volatility & position sizing'},
                {key: 'fundamental', name: '📈 Fundamental', desc: 'Market cap & volume'}
            ];

            agents.forEach(agent => {
                const vote = a.votes?.[agent.key];
                const action = vote?.action || 'N/A';
                const conf = vote?.confidence || '';
                votesHtml += `
                    <div class="agent-vote">
                        <div class="agent-name">${agent.name}</div>
                        <div class="agent-desc" style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;">${agent.desc}</div>
                        <div class="agent-decision ${getVoteClass(action)}">${action}</div>
                        <div style="font-size:0.75rem;color:var(--text-dim);margin-top:2px;">${conf}</div>
                    </div>
                `;
            });

            // Build reasoning HTML
            let reasoningHtml = '';
            if (a.reasoning?.length) {
                reasoningHtml = '<div style="margin-top:20px;"><h4>Key Reasons</h4><ul style="margin:8px 0;padding-left:20px;">';
                a.reasoning.forEach(r => { reasoningHtml += '<li style="margin:4px 0;">' + r + '</li>'; });
                reasoningHtml += '</ul></div>';
            }

            // Build learning HTML
            let learningHtml = '';
            if (a.learning?.length) {
                learningHtml = '<div style="margin-top:20px;background:var(--card-bg);padding:16px;border-radius:8px;border-left:3px solid var(--primary);"><h4 style="margin-bottom:8px;">💡 What You Can Learn</h4>';
                a.learning.forEach(l => { learningHtml += '<p style="margin:4px 0;font-size:0.9rem;">' + l + '</p>'; });
                learningHtml += '</div>';
            }

            let html = `
                <div class="analysis-result">
                    <div class="analysis-header">
                        <div>
                            <div style="font-size:0.85rem;color:var(--text-dim);margin-bottom:4px;">${a.symbol}</div>
                            <div class="analysis-recommendation ${recCls}">${a.recommendation}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:0.85rem;color:var(--text-dim);">Confidence</div>
                            <div style="font-size:1.5rem;font-weight:700;">${a.confidence}</div>
                            <div style="font-size:0.8rem;color:var(--text-dim);">${consensusPct}% consensus</div>
                        </div>
                    </div>

                    <div style="background:var(--bg);padding:12px;border-radius:8px;margin-bottom:20px;">
                        <p style="margin:0;line-height:1.5;">${a.summary || ''}</p>
                    </div>

                    <div class="analysis-metrics">
                        <div class="analysis-metric">
                            <div class="metric-label">Entry</div>
                            <div class="metric-value">${a.entry_zone || 'N/A'}</div>
                        </div>
                        <div class="analysis-metric">
                            <div class="metric-label">Take Profit</div>
                            <div class="metric-value" style="color:var(--success);">${a.targets || 'N/A'}</div>
                        </div>
                        <div class="analysis-metric">
                            <div class="metric-label">Stop Loss</div>
                            <div class="metric-value" style="color:var(--danger);">${a.stop_loss || 'N/A'}</div>
                        </div>
                        <div class="analysis-metric">
                            <div class="metric-label">Hold Time</div>
                            <div class="metric-value">${a.hold_time || 'N/A'}</div>
                        </div>
                    </div>

                    <div style="display:flex;gap:16px;margin-bottom:20px;">
                        <div style="flex:1;background:rgba(16,185,129,0.1);padding:12px;border-radius:8px;border-left:3px solid var(--success);">
                            <div style="font-size:0.8rem;color:var(--success);margin-bottom:4px;">Opportunity</div>
                            <div style="font-size:0.9rem;">${a.opportunity || 'N/A'}</div>
                        </div>
                        <div style="flex:1;background:rgba(239,68,68,0.1);padding:12px;border-radius:8px;border-left:3px solid var(--danger);">
                            <div style="font-size:0.8rem;color:var(--danger);margin-bottom:4px;">Risk</div>
                            <div style="font-size:0.9rem;">${a.risk || 'N/A'}</div>
                        </div>
                    </div>

                    <h4 style="margin-bottom:16px;">Agent Votes</h4>
                    <div class="agent-votes">${votesHtml}</div>

                    ${reasoningHtml}
                    ${learningHtml}

                    <div style="margin-top:24px;">
                        <button class="btn btn-success" onclick="executeTrade('${a.symbol}','buy')">Buy ${a.symbol}</button>
                        <button class="btn btn-danger" onclick="executeTrade('${a.symbol}','sell')" style="margin-left:12px;">Sell ${a.symbol}</button>
                    </div>
                </div>
            `;
            document.getElementById('analysis-result').innerHTML = html;
        }

        // =========================================
        // OPPORTUNITIES
        // =========================================
        async function findOpportunities() {
            document.getElementById('opportunities-list').innerHTML = '<div class="card"><div class="loading"><div class="spinner"></div>Scanning for opportunities...</div></div>';

            const data = await api('opportunities', 'POST');
            if (!data.success || !data.opportunities?.length) {
                document.getElementById('opportunities-list').innerHTML = '<div class="card"><div class="empty-state"><div class="empty-icon">💡</div><p>No opportunities found right now. Try again later.</p></div></div>';
                return;
            }

            let html = '';
            data.opportunities.forEach(o => {
                const confCls = o.confidence >= 0.7 ? 'badge-success' : o.confidence >= 0.5 ? 'badge-warning' : 'badge-purple';
                html += `<div class="opp-card">
                    <div class="opp-header">
                        <div>
                            <div class="opp-symbol">${o.symbol}</div>
                            <div class="opp-type">${o.opportunity_type}</div>
                        </div>
                        <span class="badge ${confCls}">${(o.confidence * 100).toFixed(0)}% confidence</span>
                    </div>
                    <div class="opp-explanation">${o.explanation || 'Trading opportunity detected based on multi-agent analysis.'}</div>
                    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
                        ${o.entry_zone?.length ? `<div><span style="color:var(--text-dim);">Entry:</span> $${o.entry_zone.join(' - $')}</div>` : ''}
                        ${o.targets?.length ? `<div><span style="color:var(--text-dim);">Target:</span> $${o.targets[0]}</div>` : ''}
                        ${o.stop_loss ? `<div><span style="color:var(--text-dim);">Stop:</span> $${o.stop_loss}</div>` : ''}
                    </div>
                    <button class="btn btn-success" onclick="executeTrade('${o.symbol}','buy')">Trade ${o.symbol}</button>
                </div>`;
            });
            document.getElementById('opportunities-list').innerHTML = html;
        }

        // =========================================
        // EDUCATION
        // =========================================
        async function loadLessons(category) {
            document.getElementById('education-categories').style.display = 'none';
            document.getElementById('lessons-content').style.display = 'block';
            document.getElementById('lessons-list').innerHTML = '<div class="loading"><div class="spinner"></div>Loading lessons...</div>';

            const data = await api('education/' + category);
            if (!data.success || !data.lessons?.length) {
                document.getElementById('lessons-list').innerHTML = '<div class="empty-state"><p>No lessons available in this category yet.</p></div>';
                return;
            }

            let html = `<h2 style="margin-bottom:24px;">${category.charAt(0).toUpperCase() + category.slice(1)} - ${data.lessons.length} Lessons</h2>`;
            data.lessons.forEach((l, i) => {
                html += `<div class="lesson-content">
                    <h3>Lesson ${i + 1}: ${l.title}</h3>
                    <div class="badge badge-purple" style="margin-bottom:16px;">${l.difficulty}</div>
                    <div style="white-space:pre-wrap;line-height:1.8;">${l.content}</div>
                    ${l.key_takeaways?.length ? `
                        <div style="margin-top:24px;padding:16px;background:var(--bg-card);border-radius:8px;">
                            <strong style="color:var(--success);">📌 Key Takeaways</strong>
                            <ul style="margin-top:12px;">
                                ${l.key_takeaways.map(t => `<li>${t}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>`;
            });
            document.getElementById('lessons-list').innerHTML = html;
        }

        function showCategories() {
            document.getElementById('education-categories').style.display = 'grid';
            document.getElementById('lessons-content').style.display = 'none';
        }

        // =========================================
        // SETTINGS
        // =========================================
        async function loadSettings() {
            const data = await api('settings');
            if (!data.success) return;

            document.getElementById('set-capital').value = data.settings?.initial_capital || 100;
            document.getElementById('set-stoploss').value = data.settings?.stop_loss_pct || 3;
            document.getElementById('set-takeprofit').value = data.settings?.take_profit_pct || 6;
            document.getElementById('set-autotrade').checked = data.settings?.auto_trade || false;
        }

        async function saveSettings() {
            const settings = {
                initial_capital: parseFloat(document.getElementById('set-capital').value),
                stop_loss_pct: parseFloat(document.getElementById('set-stoploss').value),
                take_profit_pct: parseFloat(document.getElementById('set-takeprofit').value),
                auto_trade: document.getElementById('set-autotrade').checked
            };
            const data = await api('settings', 'POST', settings);
            alert(data.success ? '✅ Settings saved!' : '❌ Failed to save settings');
        }

        async function saveBrokerKeys() {
            alert('Broker configuration saved (demo mode)');
        }

        // =========================================
        // MATRIX SIMULATION
        // =========================================
        let matrixEventSource = null;
        let matrixHistory = [];

        function startMatrix() {
            if (matrixEventSource) {
                matrixEventSource.close();
            }

            matrixEventSource = new EventSource('/api/matrix/stream');

            matrixEventSource.onopen = function() {
                document.getElementById('matrix-status').innerHTML =
                    '<span class="badge badge-success">Connected</span>';
            };

            matrixEventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateMatrixDisplay(data);
            };

            matrixEventSource.onerror = function() {
                document.getElementById('matrix-status').innerHTML =
                    '<span class="badge badge-danger">Error</span>';
                matrixEventSource.close();
                matrixEventSource = null;
            };
        }

        function stopMatrix() {
            if (matrixEventSource) {
                matrixEventSource.close();
                matrixEventSource = null;
            }
            document.getElementById('matrix-status').innerHTML =
                '<span class="badge badge-warning">Disconnected</span>';
        }

        function updateMatrixDisplay(data) {
            // Update price and phase
            document.getElementById('matrix-price').textContent =
                '$' + (data.price || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            document.getElementById('matrix-phase').textContent = (data.phase || '--').toUpperCase();

            // Update signal with color and confidence
            const signalEl = document.getElementById('matrix-signal');
            const signal = data.signal || '--';
            const confidence = data.confidence || 0;
            signalEl.textContent = signal + ' (' + (confidence * 100).toFixed(0) + '%)';
            signalEl.className = 'stat-value';
            if (signal === 'STRONG_BUY') signalEl.style.color = 'var(--success)';
            else if (signal === 'BUY') signalEl.style.color = '#22c55e';
            else if (signal === 'EXIT') signalEl.style.color = 'var(--danger)';
            else signalEl.style.color = 'var(--warning)';

            // Update three pillars - USE TITAN BRAIN PILLAR STATES
            const entropy = data.entropy || 0;
            const hurst = data.hurst || 0;
            const viral_k = data.viral_k || 0;
            const cvd = data.cvd || 0;
            const pillars = data.pillars || {};

            // Use TitanBrain pillar states if available, otherwise calculate
            updatePillarBadge('matrix-entropy', entropy, pillars.bio !== undefined ? pillars.bio : entropy < 2.5, entropy.toFixed(2));
            updatePillarBadge('matrix-hurst', hurst, pillars.physics !== undefined ? pillars.physics : hurst > 0.6, hurst.toFixed(2));
            updatePillarBadge('matrix-viral', viral_k, pillars.micro !== undefined ? pillars.micro : viral_k > 1.2, viral_k.toFixed(2));

            const cvdEl = document.getElementById('matrix-cvd');
            cvdEl.textContent = cvd >= 0 ? '+' + cvd.toFixed(0) : cvd.toFixed(0);
            cvdEl.className = 'badge ' + (pillars.cvd !== undefined ? (pillars.cvd ? 'badge-success' : 'badge-danger') : (cvd > 0 ? 'badge-success' : 'badge-danger'));

            // Show brain version if using TitanBrain
            const brainVersion = data.brain_version || 0;
            const brainSource = data.brain_source || 'fallback';
            if (brainVersion > 0) {
                document.getElementById('matrix-status').innerHTML =
                    '<span class="badge badge-success">Connected</span>' +
                    '<span class="badge badge-purple" style="margin-left: 8px;">Brain v' + brainVersion + ' (' + brainSource + ')</span>';
            }

            // Add to history
            if (signal !== 'HOLD') {
                const historyEntry = {
                    time: new Date().toLocaleTimeString(),
                    signal: signal,
                    price: data.price,
                    phase: data.phase,
                    confidence: confidence
                };
                matrixHistory.unshift(historyEntry);
                if (matrixHistory.length > 20) matrixHistory.pop();
                updateMatrixHistory();
            }
        }

        function updatePillarBadge(id, value, isGood, display) {
            const el = document.getElementById(id);
            el.textContent = display;
            el.className = 'badge ' + (isGood ? 'badge-success' : 'badge-warning');
        }

        function updateMatrixHistory() {
            const container = document.getElementById('matrix-history');
            if (matrixHistory.length === 0) {
                container.innerHTML = '<p style="color: var(--text-dim);">Waiting for signals...</p>';
                return;
            }
            container.innerHTML = matrixHistory.map(h =>
                '<div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border);">' +
                    '<span style="color: var(--text-dim); font-size: 0.8rem;">' + h.time + '</span>' +
                    '<span class="' + (h.signal.includes('BUY') ? 'signal-buy' : 'signal-sell') + '" style="font-weight: 600;">' + h.signal + '</span>' +
                    '<span style="font-size: 0.85rem;">' + ((h.confidence || 0) * 100).toFixed(0) + '%</span>' +
                    '<span style="font-size: 0.85rem;">$' + h.price.toFixed(2) + '</span>' +
                '</div>'
            ).join('');
        }

        function clearMatrixHistory() {
            matrixHistory = [];
            updateMatrixHistory();
        }

        // =========================================
        // DARWIN EVOLUTION
        // =========================================
        let evolutionRefreshInterval = null;

        async function startEvolution() {
            const data = await api('darwin/start', 'POST');
            if (data.success) {
                document.getElementById('darwin-status').innerHTML =
                    '<span class="badge badge-success">Evolving</span>';
                // Start auto-refresh
                if (!evolutionRefreshInterval) {
                    evolutionRefreshInterval = setInterval(loadEvolutionStats, 10000);
                }
            } else {
                alert('Failed to start evolution: ' + (data.error || 'Unknown error'));
            }
        }

        async function stopEvolution() {
            const data = await api('darwin/stop', 'POST');
            if (data.success) {
                document.getElementById('darwin-status').innerHTML =
                    '<span class="badge badge-warning">Stopped</span>';
                if (evolutionRefreshInterval) {
                    clearInterval(evolutionRefreshInterval);
                    evolutionRefreshInterval = null;
                }
            }
        }

        async function runGeneration() {
            document.getElementById('darwin-status').innerHTML =
                '<span class="badge badge-purple">Running...</span>';
            const data = await api('darwin/generation', 'POST');
            if (data.success) {
                loadEvolutionStats();
                document.getElementById('darwin-status').innerHTML =
                    '<span class="badge badge-success">Complete</span>';
            } else {
                alert('Failed: ' + (data.error || 'Unknown error'));
                document.getElementById('darwin-status').innerHTML =
                    '<span class="badge badge-danger">Error</span>';
            }
        }

        async function hotSwapAlpha() {
            const data = await api('darwin/hotswap', 'POST');
            if (data.success) {
                alert('🧬 Alpha genome hot-swapped into TitanBrain!');
                loadEvolutionStats();
            } else {
                alert('No alpha genome available yet');
            }
        }

        async function loadEvolutionStats() {
            const data = await api('darwin/stats');
            if (data.success) {
                const stats = data.stats;

                document.getElementById('darwin-generation').textContent = stats.generations || 0;
                document.getElementById('darwin-population').textContent = stats.population_size || 50;
                document.getElementById('darwin-fitness').textContent =
                    stats.best_fitness_ever ? stats.best_fitness_ever.toFixed(2) : '--';
                document.getElementById('darwin-updates').textContent = stats.alpha_updates || 0;

                // Update alpha genome if available
                if (stats.alpha_genome) {
                    const g = stats.alpha_genome;
                    document.getElementById('alpha-k').textContent = g.k_threshold?.toFixed(3) || '--';
                    document.getElementById('alpha-entropy').textContent = g.entropy_threshold?.toFixed(3) || '--';
                    document.getElementById('alpha-hurst').textContent = g.hurst_threshold?.toFixed(3) || '--';
                    document.getElementById('alpha-cvd').textContent = g.cvd_sensitivity?.toFixed(3) || '--';
                    document.getElementById('alpha-position').textContent = (g.position_size_base * 100)?.toFixed(1) + '%' || '--';
                    document.getElementById('alpha-stoploss').textContent = g.stop_loss_atr_mult?.toFixed(2) + 'x' || '--';
                }

                // Update brain stats
                if (data.brain) {
                    document.getElementById('brain-version').textContent = 'v' + (data.brain.config_version || 1);
                    document.getElementById('brain-source').textContent = data.brain.config_source || 'default';
                    document.getElementById('brain-signals').textContent = data.brain.signals_generated || 0;
                }

                // Update status
                if (stats.is_running) {
                    document.getElementById('darwin-status').innerHTML =
                        '<span class="badge badge-success">Evolving</span>';
                }
            }
        }

        // =========================================
        // INIT
        // =========================================
        window.addEventListener('DOMContentLoaded', function() {
            loadDashboard();
            setInterval(loadDashboard, 60000); // Refresh every minute
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
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/dashboard')
def api_dashboard():
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
    try:
        print(f"\n🔬 Running deep analysis on {asset}...")
        analysis = coordinator.analyze(asset)

        # Build votes from agent opinions
        votes = {}
        for agent_name, opinion in analysis.agent_opinions.items():
            votes[agent_name] = {
                "action": opinion.action.value,
                "confidence": opinion.confidence.name,
                "reasoning": opinion.reasoning
            }

        return jsonify({
            "success": True,
            "analysis": {
                "symbol": asset,
                "recommendation": analysis.action.value,
                "confidence": analysis.confidence.name,
                "consensus": analysis.consensus_level,
                "summary": analysis.summary,
                "entry_zone": analysis.recommended_entry,
                "targets": f"+{analysis.take_profit_pct:.0f}%",
                "stop_loss": f"-{analysis.stop_loss_pct:.0f}%",
                "hold_time": analysis.suggested_hold_time,
                "votes": votes,
                "reasoning": analysis.key_reasons,
                "opportunity": analysis.primary_opportunity,
                "risk": analysis.primary_risk,
                "learning": analysis.learning_points,
                "warnings": analysis.warnings
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/opportunities', methods=['POST'])
def api_opportunities():
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
    try:
        data = request.json
        message = data.get('message', '')

        # process_message returns an AssistantResponse object
        response = assistant.process_message(message)

        return jsonify({
            "success": True,
            "response": {
                "message": response.message,
                "action_taken": response.action_taken or False,
                "suggestions": response.suggestions if hasattr(response, 'suggestions') else []
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/alerts')
def api_alerts():
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


@app.route('/api/brokers/status')
def api_broker_status():
    return jsonify({
        "success": True,
        "alpaca": bool(getattr(broker_manager.alpaca, 'api_key', None)),
        "binance": bool(getattr(broker_manager.binance, 'api_key', None))
    })


@app.route('/api/brokers/alpaca/test', methods=['POST'])
def api_test_alpaca():
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
# MATRIX SIMULATION STREAMING
# =============================================================================

def generate_matrix_stream():
    """Generator for Server-Sent Events from Matrix simulation"""
    if not MATRIX_AVAILABLE or matrix is None:
        yield f"data: {json.dumps({'error': 'Matrix not available'})}\n\n"
        return

    while True:
        try:
            tick = matrix.tick("BTC/USDT")

            # Extract metrics
            entropy = tick.get('entropy', 3.0)
            hurst = tick.get('hurst', 0.5)
            viral_k = tick.get('viral_k', 1.0)
            cvd = tick.get('cvd', 0)
            phase = tick.get('phase', 'stable')

            # USE TITAN BRAIN FOR SIGNAL GENERATION (if available)
            if ECOSYSTEM_AVAILABLE and titan_brain:
                # Process tick through TitanBrain with evolved parameters
                brain_tick = {
                    'asset': 'BTC/USDT',
                    'price': tick['price'],
                    'entropy': entropy,
                    'hurst': hurst,
                    'viral_k': viral_k,
                    'cvd': cvd,
                    'phase': phase
                }
                trading_signal = titan_brain.process_tick(brain_tick)
                signal = trading_signal.signal_type.value
                confidence = trading_signal.confidence
                conviction = trading_signal.conviction

                # Include pillar states
                pillars = {
                    'bio': trading_signal.bio_check,
                    'physics': trading_signal.physics_check,
                    'micro': trading_signal.micro_check,
                    'cvd': trading_signal.cvd_check
                }
            else:
                # Fallback to hardcoded logic if TitanBrain not available
                signal = "HOLD"
                confidence = 0.5
                conviction = 0.0
                pillars = {'bio': False, 'physics': False, 'micro': False, 'cvd': False}

                if phase in ['accumulation', 'recovery']:
                    if entropy < 2.5 and hurst > 0.6 and viral_k > 1.2:
                        signal = "STRONG_BUY"
                        confidence = 0.9
                    elif entropy < 3.0 and hurst > 0.55:
                        signal = "BUY"
                        confidence = 0.7
                elif phase == 'crash':
                    signal = "EXIT"
                    confidence = 0.85
                elif phase == 'euphoria' and viral_k < 0.8:
                    signal = "EXIT"
                    confidence = 0.6

            data = {
                'price': tick['price'],
                'phase': phase,
                'signal': signal,
                'confidence': confidence,
                'conviction': conviction if ECOSYSTEM_AVAILABLE else 0,
                'entropy': entropy,
                'hurst': hurst,
                'viral_k': viral_k,
                'cvd': cvd,
                'pillars': pillars,
                'brain_version': titan_brain.config.version if ECOSYSTEM_AVAILABLE and titan_brain else 0,
                'brain_source': titan_brain.config.source if ECOSYSTEM_AVAILABLE and titan_brain else 'fallback',
                'timestamp': tick.get('timestamp', time.time())
            }

            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(2)  # Send update every 2 seconds

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            time.sleep(5)


@app.route('/api/matrix/stream')
def api_matrix_stream():
    """SSE endpoint for Matrix simulation streaming"""
    return Response(
        generate_matrix_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/matrix/status')
def api_matrix_status():
    """Check Matrix availability"""
    return jsonify({
        'available': MATRIX_AVAILABLE,
        'status': 'active' if MATRIX_AVAILABLE else 'unavailable'
    })


# =============================================================================
# DARWIN EVOLUTION API
# =============================================================================

@app.route('/api/darwin/stats')
def api_darwin_stats():
    """Get Darwin evolution statistics"""
    if not DARWIN_AVAILABLE:
        return jsonify({'success': False, 'error': 'Darwin not available'})

    try:
        stats = darwin.get_stats()
        brain_stats = titan_brain.get_stats() if titan_brain else {}

        return jsonify({
            'success': True,
            'stats': stats,
            'brain': brain_stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/darwin/start', methods=['POST'])
def api_darwin_start():
    """Start Darwin evolution"""
    if not DARWIN_AVAILABLE or not MATRIX_AVAILABLE:
        return jsonify({'success': False, 'error': 'Darwin or Matrix not available'})

    try:
        darwin.start_evolution(matrix)
        return jsonify({'success': True, 'message': 'Evolution started'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/darwin/stop', methods=['POST'])
def api_darwin_stop():
    """Stop Darwin evolution"""
    if not DARWIN_AVAILABLE:
        return jsonify({'success': False, 'error': 'Darwin not available'})

    try:
        darwin.stop_evolution()
        return jsonify({'success': True, 'message': 'Evolution stopped'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/darwin/generation', methods=['POST'])
def api_darwin_generation():
    """Run a single generation manually"""
    if not DARWIN_AVAILABLE or not MATRIX_AVAILABLE:
        return jsonify({'success': False, 'error': 'Darwin or Matrix not available'})

    try:
        # Generate ticks from Matrix
        ticks = []
        for _ in range(darwin.config.evaluation_ticks):
            tick = matrix.tick("BTC/USDT")
            ticks.append(tick)

        # Run generation
        alpha = darwin.run_generation(ticks)

        return jsonify({
            'success': True,
            'generation': darwin.generation,
            'alpha': alpha.to_dict() if alpha else None,
            'stats': darwin.get_stats()
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/darwin/hotswap', methods=['POST'])
def api_darwin_hotswap():
    """Hot-swap alpha genome into TitanBrain"""
    if not DARWIN_AVAILABLE:
        return jsonify({'success': False, 'error': 'Darwin not available'})

    try:
        alpha = darwin.get_alpha()
        if not alpha:
            return jsonify({'success': False, 'error': 'No alpha genome available'})

        titan_brain.update_from_genome(alpha)

        return jsonify({
            'success': True,
            'message': 'Alpha genome hot-swapped',
            'genome': alpha.to_dict(),
            'brain_version': titan_brain.config.version
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/darwin/alpha')
def api_darwin_alpha():
    """Get current alpha genome"""
    if not DARWIN_AVAILABLE:
        return jsonify({'success': False, 'error': 'Darwin not available'})

    try:
        alpha = darwin.get_alpha()
        return jsonify({
            'success': True,
            'alpha': alpha.to_dict() if alpha else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/brain/config')
def api_brain_config():
    """Get TitanBrain configuration"""
    if not ECOSYSTEM_AVAILABLE or not titan_brain:
        return jsonify({'success': False, 'error': 'TitanBrain not available'})

    try:
        config = titan_brain.get_config()
        return jsonify({
            'success': True,
            'config': {
                'version': config.version,
                'source': config.source,
                'entropy_threshold': config.entropy_threshold_high,
                'hurst_threshold': config.hurst_threshold_high,
                'k_threshold': config.k_threshold_high,
                'position_size_base': config.position_size_base,
                'stop_loss_pct': config.stop_loss_pct,
                'take_profit_pct': config.take_profit_pct
            },
            'stats': titan_brain.get_stats()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# =============================================================================
# TITAN ECOSYSTEM API
# =============================================================================

@app.route('/api/ecosystem/status')
def api_ecosystem_status():
    """Get comprehensive ecosystem status"""
    if not ECOSYSTEM_AVAILABLE or not ecosystem:
        return jsonify({'success': False, 'error': 'Ecosystem not available'})

    try:
        status = ecosystem.get_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ecosystem/performance')
def api_ecosystem_performance():
    """Get ecosystem performance metrics"""
    if not ECOSYSTEM_AVAILABLE or not ecosystem:
        return jsonify({'success': False, 'error': 'Ecosystem not available'})

    try:
        metrics = ecosystem.get_performance()
        return jsonify({
            'success': True,
            'metrics': {
                'total_return': metrics.total_return,
                'total_return_pct': metrics.total_return_pct,
                'sharpe_ratio': metrics.sharpe_ratio,
                'sortino_ratio': metrics.sortino_ratio,
                'win_rate': metrics.win_rate,
                'profit_factor': metrics.profit_factor,
                'max_drawdown_pct': metrics.max_drawdown_pct,
                'total_trades': metrics.total_trades,
                'expectancy': metrics.expectancy,
                'expectancy_r': metrics.expectancy_r
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ecosystem/positions')
def api_ecosystem_positions():
    """Get open positions"""
    if not ECOSYSTEM_AVAILABLE or not ecosystem:
        return jsonify({'success': False, 'error': 'Ecosystem not available'})

    try:
        status = ecosystem.get_status()
        return jsonify({
            'success': True,
            'positions': status.get('positions', {}),
            'portfolio': status.get('portfolio', {})
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ecosystem/journal')
def api_ecosystem_journal():
    """Get trade journal summary"""
    if not ECOSYSTEM_AVAILABLE or not ecosystem:
        return jsonify({'success': False, 'error': 'Ecosystem not available'})

    try:
        journal_stats = ecosystem.journal.get_stats()
        recent_trades = [t.to_dict() for t in ecosystem.journal.get_recent_trades(20)]
        return jsonify({
            'success': True,
            'stats': journal_stats,
            'recent_trades': recent_trades
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ecosystem/alerts')
def api_ecosystem_alerts():
    """Get recent alerts"""
    if not ECOSYSTEM_AVAILABLE or not ecosystem:
        return jsonify({'success': False, 'error': 'Ecosystem not available'})

    try:
        alerts = ecosystem.alerts.get_alerts(limit=50)
        return jsonify({
            'success': True,
            'alerts': [a.to_dict() for a in alerts],
            'unacknowledged': ecosystem.alerts.get_unacknowledged_count()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ecosystem/regime')
def api_ecosystem_regime():
    """Get regime analysis"""
    if not ECOSYSTEM_AVAILABLE or not ecosystem:
        return jsonify({'success': False, 'error': 'Ecosystem not available'})

    try:
        analysis = ecosystem.get_regime_analysis()
        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ecosystem/reset', methods=['POST'])
def api_ecosystem_reset():
    """Reset ecosystem to initial state"""
    if not ECOSYSTEM_AVAILABLE or not ecosystem:
        return jsonify({'success': False, 'error': 'Ecosystem not available'})

    try:
        ecosystem.reset()
        return jsonify({
            'success': True,
            'message': 'Ecosystem reset to initial state'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ecosystem/evolve', methods=['POST'])
def api_ecosystem_evolve():
    """Run a single evolution generation"""
    if not ECOSYSTEM_AVAILABLE or not ecosystem:
        return jsonify({'success': False, 'error': 'Ecosystem not available'})

    try:
        result = ecosystem.run_generation()
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# =============================================================================
# RUN APP
# =============================================================================

def run_app(host='0.0.0.0', port=5000, debug=False):
    print("\n" + "=" * 60)
    print("  SHOPGUARD AI TRADING PLATFORM")
    print("=" * 60)
    print(f"\n  🌐 Open in browser: http://localhost:{port}")
    print("\n  Features:")
    print("    ✓ Real-time market data (CoinGecko + Yahoo Finance)")
    print("    ✓ AI-powered trading signals")
    print("    ✓ Multi-agent deep analysis (5 AI agents)")
    print("    ✓ Natural language AI assistant")
    print("    ✓ Complete trading education")
    print("    ✓ Paper trading with $100 capital")
    if MATRIX_AVAILABLE:
        print("    Matrix Simulation Engine (Perfect Storm every 60s)")
    if ECOSYSTEM_AVAILABLE:
        print("    TITAN Ecosystem (3-pillar convergence)")
        print("       - TitanBrain (Entropy + Hurst + CVD)")
        print("       - FastMath JIT acceleration")
        print("       - Risk Manager (ATR-based stops)")
        print("       - Order Executor")
        print("       - Regime Detector")
        print("       - Trade Journal")
    print("\n" + "=" * 60 + "\n")

    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_app(debug=True)
