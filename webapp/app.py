#!/usr/bin/env python3
"""
Quantitative Trading Dashboard - Secure Web Interface
Run: python webapp/app.py
Access: http://localhost:5000
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import numpy as np
from datetime import datetime, timedelta
import hashlib
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# =============================================================================
# SECURITY - Only you can access this
# =============================================================================
# Change these credentials to your own!
USERS = {
    "admin": hashlib.sha256("quanttrader2024".encode()).hexdigest()
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        if username in USERS and USERS[username] == password_hash:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid credentials"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =============================================================================
# MAIN DASHBOARD
# =============================================================================
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

# =============================================================================
# API ENDPOINTS FOR EACH COMPONENT
# =============================================================================

@app.route('/api/garch', methods=['POST'])
@login_required
def api_garch():
    """GARCH Volatility Forecasting"""
    try:
        from core.models.garch import GARCH11

        data = request.json or {}
        n_samples = data.get('samples', 500)
        seed = data.get('seed', 42)

        np.random.seed(seed)
        returns = np.random.normal(0.0005, 0.02, n_samples)

        garch = GARCH11()
        result = garch.fit(returns)
        forecast = garch.forecast(horizon=5)

        return jsonify({
            'success': True,
            'params': {
                'omega': float(result.params.omega),
                'alpha': float(result.params.alpha),
                'beta': float(result.params.beta),
                'persistence': float(result.params.persistence),
                'unconditional_vol': float(np.sqrt(result.params.unconditional_variance) * 100),
                'half_life': float(result.params.half_life)
            },
            'forecast': [float(f * 100) for f in forecast],
            'explanation': 'GARCH(1,1) models how volatility changes over time. High persistence means volatility shocks last longer.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/router', methods=['POST'])
@login_required
def api_router():
    """Smart Order Routing"""
    try:
        from execution.smart_router import SmartOrderRouter, Venue, VenueType, VenueLiquidity, RoutingStrategy

        data = request.json or {}
        symbol = data.get('symbol', 'AAPL')
        side = data.get('side', 'buy')
        quantity = data.get('quantity', 5000)

        venues = {
            'NYSE': Venue('NYSE', 'New York Stock Exchange', VenueType.PRIMARY_EXCHANGE, -0.0002, 0.0003, 500, 0.95, 1.0),
            'NASDAQ': Venue('NASDAQ', 'NASDAQ', VenueType.PRIMARY_EXCHANGE, -0.0002, 0.0003, 400, 0.93, 1.2),
            'DARK': Venue('DARK', 'Dark Pool', VenueType.DARK_POOL, 0, 0.0001, 1000, 0.40, 0),
        }

        router = SmartOrderRouter(venues)
        router.update_liquidity(symbol, 'NYSE', VenueLiquidity('NYSE', 149.95, 5000, 150.00, 4000, datetime.now()))
        router.update_liquidity(symbol, 'NASDAQ', VenueLiquidity('NASDAQ', 149.94, 3000, 150.01, 3500, datetime.now()))
        router.update_liquidity(symbol, 'DARK', VenueLiquidity('DARK', 149.97, 10000, 149.98, 8000, datetime.now()))

        decision = router.route_order(symbol, side, quantity, RoutingStrategy.MINIMIZE_COST)

        orders = []
        for order in decision.orders:
            orders.append({
                'venue': order.venue_id,
                'quantity': order.quantity,
                'price': float(order.limit_price)
            })

        return jsonify({
            'success': True,
            'symbol': symbol,
            'side': side,
            'total_quantity': quantity,
            'orders': orders,
            'expected_fill_rate': float(decision.expected_fill_rate),
            'expected_cost_bps': float(decision.expected_cost_bps),
            'explanation': 'Smart Order Router finds the best venues to execute your order, minimizing costs and maximizing fill probability.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/algorithms', methods=['POST'])
@login_required
def api_algorithms():
    """Execution Algorithms"""
    try:
        from execution.algorithms import TWAPExecutor, VWAPExecutor, ImplementationShortfall

        data = request.json or {}
        quantity = data.get('quantity', 10000)
        duration_hours = data.get('duration', 2)

        start = datetime.now()
        end = start + timedelta(hours=duration_hours)

        # TWAP
        twap = TWAPExecutor('AAPL', 'buy', quantity, start, end, num_slices=24)
        twap.generate_schedule()

        # VWAP
        vwap = VWAPExecutor('AAPL', 'buy', quantity, start, end)
        vwap.generate_schedule()

        # Implementation Shortfall
        isf = ImplementationShortfall('AAPL', 'buy', quantity, start, end, decision_price=150.0, risk_aversion=0.5)
        isf.generate_schedule()

        return jsonify({
            'success': True,
            'twap': {
                'slices': len(twap.schedule.times),
                'quantities': [int(q) for q in twap.schedule.quantities[:10]],
                'description': 'Time-Weighted Average Price - splits order evenly across time'
            },
            'vwap': {
                'slices': len(vwap.schedule.times),
                'peak': int(max(vwap.schedule.quantities)),
                'min': int(min(vwap.schedule.quantities)),
                'description': 'Volume-Weighted Average Price - trades more when volume is high'
            },
            'implementation_shortfall': {
                'slices': len(isf.schedule.times),
                'first_5': [int(q) for q in isf.schedule.quantities[:5]],
                'last_5': [int(q) for q in isf.schedule.quantities[-5:]],
                'description': 'Minimizes difference between decision price and execution price'
            },
            'explanation': 'Execution algorithms break large orders into smaller pieces to minimize market impact.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/impact', methods=['POST'])
@login_required
def api_impact():
    """Market Impact Estimation"""
    try:
        from execution.market_impact import AlmgrenChriss, ImpactParams

        data = request.json or {}
        sizes = data.get('sizes', [10000, 50000, 100000])
        daily_volume = data.get('daily_volume', 5000000)
        volatility = data.get('volatility', 0.25)

        params = ImpactParams(
            temporary_coeff=0.1,
            permanent_coeff=0.1,
            decay_rate=0.5,
            daily_volume=daily_volume,
            volatility=volatility,
            spread=0.01
        )

        ac = AlmgrenChriss()

        results = []
        for size in sizes:
            cost = ac.estimate_impact(size, 1, 0.5, params)
            results.append({
                'size': size,
                'pct_adv': round(size / daily_volume * 100, 2),
                'total_cost': round(cost.total_cost, 2),
                'temporary_cost': round(cost.temporary_cost, 2),
                'permanent_cost': round(cost.permanent_cost, 2)
            })

        return jsonify({
            'success': True,
            'results': results,
            'explanation': 'Market Impact estimates how much your trade will move the price. Larger orders have more impact.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/portfolio', methods=['POST'])
@login_required
def api_portfolio():
    """Portfolio Optimization"""
    try:
        from portfolio.optimization import MeanVarianceOptimizer, RiskParityOptimizer

        data = request.json or {}
        symbols = data.get('symbols', ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN'])
        expected_returns = np.array(data.get('returns', [0.12, 0.10, 0.08, 0.15, 0.09]))
        volatilities = np.array(data.get('volatilities', [0.20, 0.18, 0.12, 0.25, 0.15]))
        risk_aversion = data.get('risk_aversion', 1.0)

        # Build covariance matrix
        n = len(symbols)
        corr = np.array([
            [1.0, 0.5, 0.3, 0.2, 0.4],
            [0.5, 1.0, 0.4, 0.3, 0.5],
            [0.3, 0.4, 1.0, 0.2, 0.3],
            [0.2, 0.3, 0.2, 1.0, 0.4],
            [0.4, 0.5, 0.3, 0.4, 1.0]
        ])[:n, :n]
        cov = np.outer(volatilities, volatilities) * corr

        # Mean-Variance
        mv = MeanVarianceOptimizer(risk_aversion=risk_aversion)
        mv_result = mv.optimize(expected_returns, cov, symbols)

        # Risk Parity
        rp = RiskParityOptimizer()
        rp_result = rp.optimize(cov, symbols)

        return jsonify({
            'success': True,
            'mean_variance': {
                'weights': {s: round(float(w), 4) for s, w in zip(symbols, mv_result.weights)},
                'expected_return': round(float(mv_result.expected_return) * 100, 2),
                'volatility': round(float(mv_result.expected_volatility) * 100, 2),
                'sharpe_ratio': round(float(mv_result.sharpe_ratio), 2),
                'description': 'Maximizes return for a given level of risk'
            },
            'risk_parity': {
                'weights': {s: round(float(w), 4) for s, w in zip(symbols, rp_result.weights)},
                'description': 'Each asset contributes equally to portfolio risk'
            },
            'explanation': 'Portfolio optimization finds the best mix of assets to maximize returns and minimize risk.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/monitoring', methods=['POST'])
@login_required
def api_monitoring():
    """Trading Dashboard Monitoring"""
    try:
        from monitoring.dashboard import TradingDashboard

        data = request.json or {}

        dash = TradingDashboard()

        # Simulate some data
        dash.update_pnl(
            data.get('total_pnl', 25000),
            data.get('realized', 18000),
            data.get('unrealized', 7000)
        )
        dash.update_position('AAPL', 500, 148.50, 152.00)
        dash.update_position('GOOGL', 100, 2750.0, 2820.0)
        dash.update_position('MSFT', 200, 375.0, 380.0)
        dash.record_trade('AAPL', 'buy', 100, 151.50, 'ord001')
        dash.update_system_metrics(350, 25, 2048, 5.2)

        pnl = dash.get_pnl_summary()
        pos = dash.get_position_summary()

        return jsonify({
            'success': True,
            'pnl': {
                'total': pnl['total'],
                'realized': pnl['realized'],
                'unrealized': pnl['unrealized'],
                'peak': pnl['peak'],
                'drawdown': round(pnl['drawdown'] * 100, 2)
            },
            'positions': {
                'count': pos['num_positions'],
                'total_exposure': round(pos['total_exposure'], 2),
                'details': pos['positions']
            },
            'explanation': 'Real-time monitoring of your trading performance, positions, and risk metrics.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/alerts', methods=['POST'])
@login_required
def api_alerts():
    """Alert System"""
    try:
        from monitoring.alerts import AlertManager, AlertRule, AlertLevel

        data = request.json or {}
        pnl_threshold = data.get('pnl_threshold', -50000)
        drawdown_threshold = data.get('drawdown_threshold', 0.05)
        current_pnl = data.get('current_pnl', -65000)
        current_drawdown = data.get('current_drawdown', 0.08)

        alerts = AlertManager()

        alerts.add_rule(AlertRule(
            name="pnl_warning",
            condition=lambda: current_pnl < pnl_threshold,
            level=AlertLevel.WARNING,
            message_template=f"P&L below ${pnl_threshold:,} threshold"
        ))

        alerts.add_rule(AlertRule(
            name="drawdown_critical",
            condition=lambda: current_drawdown > drawdown_threshold,
            level=AlertLevel.CRITICAL if current_drawdown > 0.10 else AlertLevel.WARNING,
            message_template=f"Drawdown exceeds {drawdown_threshold*100:.0f}%"
        ))

        fired = alerts.check_rules()

        triggered = []
        for a in fired:
            triggered.append({
                'level': a.level.name,
                'message': a.message,
                'timestamp': a.timestamp.isoformat()
            })

        return jsonify({
            'success': True,
            'rules_count': len(alerts.rules),
            'triggered_count': len(fired),
            'alerts': triggered,
            'explanation': 'Alerts notify you when important thresholds are breached (P&L limits, drawdown, etc.)'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/sentiment', methods=['POST'])
@login_required
def api_sentiment():
    """Sentiment Analysis"""
    try:
        from alternative_data.sentiment import SentimentAnalyzer, SentimentSource

        data = request.json or {}
        headlines = data.get('headlines', [
            "Apple reports record quarterly earnings, beats estimates",
            "Tesla shares plunge amid regulatory concerns",
            "Microsoft announces $10B AI investment partnership",
            "Fed signals potential rate cuts in 2024"
        ])

        analyzer = SentimentAnalyzer()

        results = []
        for headline in headlines:
            result = analyzer.analyze_text(headline, SentimentSource.NEWS)
            sentiment = "Positive" if result.score > 0.1 else ("Negative" if result.score < -0.1 else "Neutral")
            results.append({
                'headline': headline,
                'score': round(float(result.score), 2),
                'sentiment': sentiment
            })

        return jsonify({
            'success': True,
            'results': results,
            'explanation': 'Sentiment Analysis extracts market sentiment from news, social media, and other text sources.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/engine', methods=['POST'])
@login_required
def api_engine():
    """Trading Engine"""
    try:
        from api.engine import TradingEngine, EngineConfig
        from api.strategy import Strategy, StrategyConfig

        data = request.json or {}
        engine_name = data.get('name', 'MyTradingEngine')
        paper_trading = data.get('paper_trading', True)
        initial_equity = data.get('equity', 1000000)
        symbols = data.get('symbols', ['AAPL', 'GOOGL', 'MSFT'])

        class DemoStrategy(Strategy):
            def on_data(self, context):
                return []

        config = EngineConfig(name=engine_name, paper_trading=paper_trading)
        engine = TradingEngine(config)
        engine.add_strategy(DemoStrategy(StrategyConfig(name="DemoStrategy", symbols=symbols)))
        engine._equity = initial_equity
        engine._prices = {s: 100.0 for s in symbols}

        status = engine.get_status()

        return jsonify({
            'success': True,
            'engine': {
                'name': status['name'],
                'state': status['state'],
                'paper_trading': status['paper_trading'],
                'num_strategies': status['num_strategies'],
                'equity': status['equity']
            },
            'explanation': 'The Trading Engine orchestrates strategies, execution, and risk management in real-time.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/historical', methods=['POST'])
@login_required
def api_historical():
    """Historical Data Analysis"""
    try:
        from datastore.historical import HistoricalDataLoader, TechnicalIndicators, DataAnalyzer

        data = request.json or {}
        symbol = data.get('symbol', 'AAPL')
        initial_price = data.get('initial_price', 150.0)
        volatility = data.get('volatility', 0.02)
        n_days = data.get('n_days', 252)
        indicators = data.get('indicators', ['sma', 'rsi', 'bollinger'])

        # Generate synthetic data
        loader = HistoricalDataLoader()
        hist_data = loader.generate_synthetic(
            symbol=symbol,
            initial_price=initial_price,
            volatility=volatility,
            n_days=n_days
        )

        # Get summary statistics
        stats = DataAnalyzer.summary_stats(hist_data)

        # Calculate requested indicators
        closes = hist_data.closes
        indicator_results = {}

        if 'sma' in indicators:
            sma_20 = TechnicalIndicators.sma(closes, 20)
            sma_50 = TechnicalIndicators.sma(closes, 50)
            indicator_results['sma'] = {
                'sma_20_latest': round(float(sma_20[-1]), 2) if not np.isnan(sma_20[-1]) else None,
                'sma_50_latest': round(float(sma_50[-1]), 2) if not np.isnan(sma_50[-1]) else None,
                'description': 'Simple Moving Average smooths price data to identify trend direction'
            }

        if 'ema' in indicators:
            ema_12 = TechnicalIndicators.ema(closes, 12)
            ema_26 = TechnicalIndicators.ema(closes, 26)
            indicator_results['ema'] = {
                'ema_12_latest': round(float(ema_12[-1]), 2) if not np.isnan(ema_12[-1]) else None,
                'ema_26_latest': round(float(ema_26[-1]), 2) if not np.isnan(ema_26[-1]) else None,
                'description': 'Exponential Moving Average gives more weight to recent prices'
            }

        if 'rsi' in indicators:
            rsi = TechnicalIndicators.rsi(closes, 14)
            latest_rsi = float(rsi[-1]) if not np.isnan(rsi[-1]) else 50
            signal = "Overbought (>70)" if latest_rsi > 70 else ("Oversold (<30)" if latest_rsi < 30 else "Neutral")
            indicator_results['rsi'] = {
                'value': round(latest_rsi, 2),
                'signal': signal,
                'description': 'RSI measures momentum - above 70 is overbought, below 30 is oversold'
            }

        if 'bollinger' in indicators:
            upper, middle, lower = TechnicalIndicators.bollinger_bands(closes, 20, 2.0)
            indicator_results['bollinger'] = {
                'upper': round(float(upper[-1]), 2) if not np.isnan(upper[-1]) else None,
                'middle': round(float(middle[-1]), 2) if not np.isnan(middle[-1]) else None,
                'lower': round(float(lower[-1]), 2) if not np.isnan(lower[-1]) else None,
                'description': 'Bollinger Bands show volatility - price touching bands may signal reversal'
            }

        if 'macd' in indicators:
            macd_line, signal_line, histogram = TechnicalIndicators.macd(closes)
            indicator_results['macd'] = {
                'macd': round(float(macd_line[-1]), 4) if not np.isnan(macd_line[-1]) else None,
                'signal': round(float(signal_line[-1]), 4) if not np.isnan(signal_line[-1]) else None,
                'histogram': round(float(histogram[-1]), 4) if not np.isnan(histogram[-1]) else None,
                'description': 'MACD shows trend changes - bullish when MACD crosses above signal'
            }

        # Get last 10 price data points for chart
        recent_prices = [
            {
                'date': hist_data.bars[i].timestamp.strftime('%Y-%m-%d'),
                'open': round(hist_data.bars[i].open, 2),
                'high': round(hist_data.bars[i].high, 2),
                'low': round(hist_data.bars[i].low, 2),
                'close': round(hist_data.bars[i].close, 2),
                'volume': int(hist_data.bars[i].volume)
            }
            for i in range(-10, 0)
        ]

        return jsonify({
            'success': True,
            'symbol': symbol,
            'summary': stats,
            'indicators': indicator_results,
            'recent_prices': recent_prices,
            'explanation': 'Historical data analysis with technical indicators helps identify trends, momentum, and potential entry/exit points.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  QUANTITATIVE TRADING DASHBOARD")
    print("="*60)
    print("\n  URL: http://localhost:5000")
    print("  Username: admin")
    print("  Password: quanttrader2024")
    print("\n  (Change credentials in webapp/app.py for security)")
    print("="*60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
