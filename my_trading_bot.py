#!/usr/bin/env python3
"""
🤖 YOUR PERSONAL TRADING BOT
============================
100% FREE - No API keys needed!

Assets: BTC, ETH, SPY (S&P 500), QQQ (NASDAQ), NVDA
Capital: $100
Strategy: Swing Trading (1-24 hour holds)
Risk: Moderate

Run: python my_trading_bot.py
"""

import os
import sys
import json
import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import requests

# ============================================================================
# CONFIGURATION - YOUR SETTINGS
# ============================================================================

class Config:
    # Your capital
    INITIAL_CAPITAL = 100.0

    # Your assets
    STOCKS = ["NVDA", "SPY", "QQQ"]  # SPY = S&P 500, QQQ = NASDAQ
    CRYPTO = ["bitcoin", "ethereum"]  # CoinGecko IDs

    # Symbol mapping for display
    SYMBOLS = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "SPY": "S&P 500",
        "QQQ": "NASDAQ",
        "NVDA": "NVDA"
    }

    # Risk settings (MODERATE)
    MAX_POSITION_PCT = 0.20  # Max 20% per position ($20)
    MAX_DAILY_LOSS_PCT = 0.05  # Stop if down 5% ($5)
    STOP_LOSS_PCT = 0.03  # 3% stop loss per trade
    TAKE_PROFIT_PCT = 0.06  # 6% take profit

    # Strategy: Swing trading (1-24 hours)
    MIN_HOLD_HOURS = 1
    MAX_HOLD_HOURS = 24

    # Trading schedule (your Mac's local time)
    SCAN_INTERVAL_MINUTES = 15  # Check every 15 minutes

    # Confidence threshold to execute trades
    MIN_CONFIDENCE = 0.65  # 65% confidence minimum


# ============================================================================
# PRICE FETCHER - 100% FREE APIs
# ============================================================================

@dataclass
class Price:
    symbol: str
    price: float
    change_1h: float
    change_24h: float
    volume: float
    high_24h: float
    low_24h: float
    timestamp: datetime = field(default_factory=datetime.now)


class FreePriceFetcher:
    """Fetches REAL prices from FREE APIs - no keys needed!"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        self._cache = {}
        self._cache_time = {}

    def get_crypto(self) -> Dict[str, Price]:
        """Get BTC, ETH from CoinGecko (FREE)"""
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                "vs_currency": "usd",
                "ids": ",".join(Config.CRYPTO),
                "price_change_percentage": "1h,24h"
            }

            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            result = {}
            for coin in data:
                coin_id = coin["id"]
                result[coin_id] = Price(
                    symbol=Config.SYMBOLS.get(coin_id, coin["symbol"].upper()),
                    price=coin["current_price"] or 0,
                    change_1h=coin.get("price_change_percentage_1h_in_currency", 0) or 0,
                    change_24h=coin.get("price_change_percentage_24h", 0) or 0,
                    volume=coin.get("total_volume", 0) or 0,
                    high_24h=coin.get("high_24h", coin["current_price"]) or coin["current_price"],
                    low_24h=coin.get("low_24h", coin["current_price"]) or coin["current_price"]
                )
            return result

        except Exception as e:
            print(f"❌ Crypto fetch error: {e}")
            return {}

    def get_stock(self, symbol: str) -> Optional[Price]:
        """Get stock price from Yahoo Finance (FREE)"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"interval": "1h", "range": "2d"}

            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            result = data["chart"]["result"][0]
            meta = result["meta"]
            quotes = result["indicators"]["quote"][0]

            current = meta["regularMarketPrice"]
            prev_close = meta.get("previousClose", current)

            # Calculate 1h change
            closes = [c for c in quotes["close"] if c is not None]
            change_1h = 0
            if len(closes) >= 2:
                change_1h = ((closes[-1] - closes[-2]) / closes[-2]) * 100

            change_24h = ((current - prev_close) / prev_close) * 100 if prev_close else 0

            return Price(
                symbol=Config.SYMBOLS.get(symbol, symbol),
                price=current,
                change_1h=change_1h,
                change_24h=change_24h,
                volume=meta.get("regularMarketVolume", 0),
                high_24h=meta.get("regularMarketDayHigh", current),
                low_24h=meta.get("regularMarketDayLow", current)
            )

        except Exception as e:
            print(f"❌ Stock fetch error ({symbol}): {e}")
            return None

    def get_stocks(self) -> Dict[str, Price]:
        """Get all stocks"""
        result = {}
        for symbol in Config.STOCKS:
            price = self.get_stock(symbol)
            if price:
                result[symbol] = price
            time.sleep(0.2)  # Rate limiting
        return result

    def get_all_prices(self) -> Dict[str, Price]:
        """Get all prices"""
        prices = {}
        prices.update(self.get_crypto())
        prices.update(self.get_stocks())
        return prices

    def get_history(self, symbol: str, is_crypto: bool = False) -> List[float]:
        """Get price history for analysis"""
        try:
            if is_crypto:
                url = f"https://api.coingecko.com/api/v3/coins/{symbol}/ohlc"
                params = {"vs_currency": "usd", "days": 7}
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                return [candle[4] for candle in data]  # Close prices
            else:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                params = {"interval": "1h", "range": "7d"}
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                return [c for c in closes if c is not None]
        except:
            return []


# ============================================================================
# AI SIGNALS - SWING TRADING STRATEGIES
# ============================================================================

class SignalType(Enum):
    STRONG_BUY = "🟢 STRONG BUY"
    BUY = "🟢 BUY"
    HOLD = "⚪ HOLD"
    SELL = "🔴 SELL"
    STRONG_SELL = "🔴 STRONG SELL"


@dataclass
class Signal:
    symbol: str
    signal_type: SignalType
    confidence: float
    price: float
    reason: str
    entry_price: float = 0
    stop_loss: float = 0
    take_profit: float = 0
    hold_hours: int = 4


class SwingTrader:
    """AI Swing Trading Strategies for 1-24 hour holds"""

    def __init__(self, fetcher: FreePriceFetcher):
        self.fetcher = fetcher

    def _rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _sma(self, prices: List[float], period: int) -> float:
        """Simple Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period

    def _ema(self, prices: List[float], period: int) -> float:
        """Exponential Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema

    def _bollinger_position(self, prices: List[float], period: int = 20) -> float:
        """Where is price in Bollinger Bands? 0 = lower, 1 = upper"""
        if len(prices) < period:
            return 0.5

        recent = prices[-period:]
        sma = sum(recent) / period
        std = (sum((p - sma) ** 2 for p in recent) / period) ** 0.5

        if std == 0:
            return 0.5

        upper = sma + 2 * std
        lower = sma - 2 * std
        current = prices[-1]

        return (current - lower) / (upper - lower)

    def _momentum(self, prices: List[float], period: int = 10) -> float:
        """Price momentum percentage"""
        if len(prices) < period:
            return 0
        return ((prices[-1] - prices[-period]) / prices[-period]) * 100

    def analyze(self, symbol: str, current_price: float, is_crypto: bool) -> Optional[Signal]:
        """Analyze asset and generate swing trading signal"""

        # Get price history
        history = self.fetcher.get_history(symbol, is_crypto)
        if len(history) < 20:
            return None

        # Calculate indicators
        rsi = self._rsi(history)
        sma_short = self._sma(history, 10)
        sma_long = self._sma(history, 30)
        ema_fast = self._ema(history, 8)
        ema_slow = self._ema(history, 21)
        bb_pos = self._bollinger_position(history)
        momentum = self._momentum(history)

        # Scoring system
        score = 0
        reasons = []

        # RSI signals
        if rsi < 30:
            score += 2
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi < 40:
            score += 1
            reasons.append(f"RSI low ({rsi:.0f})")
        elif rsi > 70:
            score -= 2
            reasons.append(f"RSI overbought ({rsi:.0f})")
        elif rsi > 60:
            score -= 1
            reasons.append(f"RSI high ({rsi:.0f})")

        # Moving average crossover
        if ema_fast > ema_slow and sma_short > sma_long:
            score += 2
            reasons.append("Bullish MA crossover")
        elif ema_fast < ema_slow and sma_short < sma_long:
            score -= 2
            reasons.append("Bearish MA crossover")

        # Bollinger position
        if bb_pos < 0.2:
            score += 2
            reasons.append("Near lower Bollinger Band")
        elif bb_pos > 0.8:
            score -= 2
            reasons.append("Near upper Bollinger Band")

        # Momentum
        if momentum > 5:
            score += 1
            reasons.append(f"Strong momentum (+{momentum:.1f}%)")
        elif momentum < -5:
            score -= 1
            reasons.append(f"Weak momentum ({momentum:.1f}%)")

        # Price above/below moving averages
        if current_price > sma_short > sma_long:
            score += 1
            reasons.append("Price above MAs (uptrend)")
        elif current_price < sma_short < sma_long:
            score -= 1
            reasons.append("Price below MAs (downtrend)")

        # Determine signal
        display_symbol = Config.SYMBOLS.get(symbol, symbol)

        if score >= 4:
            signal_type = SignalType.STRONG_BUY
            confidence = min(0.90, 0.70 + score * 0.05)
        elif score >= 2:
            signal_type = SignalType.BUY
            confidence = min(0.80, 0.60 + score * 0.05)
        elif score <= -4:
            signal_type = SignalType.STRONG_SELL
            confidence = min(0.90, 0.70 + abs(score) * 0.05)
        elif score <= -2:
            signal_type = SignalType.SELL
            confidence = min(0.80, 0.60 + abs(score) * 0.05)
        else:
            signal_type = SignalType.HOLD
            confidence = 0.50

        # Calculate entry, stop loss, take profit
        stop_loss = current_price * (1 - Config.STOP_LOSS_PCT)
        take_profit = current_price * (1 + Config.TAKE_PROFIT_PCT)

        # Suggested hold time based on signal strength
        hold_hours = 4 if abs(score) >= 4 else 8 if abs(score) >= 2 else 12

        return Signal(
            symbol=display_symbol,
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            reason=" | ".join(reasons[:3]),
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            hold_hours=hold_hours
        )


# ============================================================================
# PAPER TRADING PORTFOLIO
# ============================================================================

@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float

    @property
    def value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost(self) -> float:
        return self.quantity * self.entry_price

    @property
    def pnl(self) -> float:
        return self.value - self.cost

    @property
    def pnl_pct(self) -> float:
        return (self.pnl / self.cost) * 100 if self.cost > 0 else 0

    @property
    def hold_hours(self) -> float:
        return (datetime.now() - self.entry_time).total_seconds() / 3600


@dataclass
class Trade:
    symbol: str
    side: str
    quantity: float
    price: float
    pnl: float
    timestamp: datetime


class Portfolio:
    """Paper trading portfolio"""

    SAVE_FILE = "my_portfolio.json"

    def __init__(self):
        self.initial_capital = Config.INITIAL_CAPITAL
        self.cash = Config.INITIAL_CAPITAL
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.daily_pnl = 0.0
        self.daily_start = datetime.now().date()
        self._load()

    @property
    def positions_value(self) -> float:
        return sum(p.value for p in self.positions.values())

    @property
    def total_value(self) -> float:
        return self.cash + self.positions_value

    @property
    def total_pnl(self) -> float:
        return self.total_value - self.initial_capital

    @property
    def total_pnl_pct(self) -> float:
        return (self.total_pnl / self.initial_capital) * 100

    def update_prices(self, prices: Dict[str, Price]):
        """Update position prices"""
        for symbol, pos in self.positions.items():
            for price_key, price_data in prices.items():
                if price_data.symbol == symbol or Config.SYMBOLS.get(price_key) == symbol:
                    pos.current_price = price_data.price
                    break

    def can_buy(self, amount: float) -> bool:
        """Check if we can buy"""
        # Check cash
        if amount > self.cash:
            return False

        # Check daily loss limit
        if self.daily_pnl < -Config.INITIAL_CAPITAL * Config.MAX_DAILY_LOSS_PCT:
            print("⚠️ Daily loss limit reached!")
            return False

        return True

    def buy(self, symbol: str, price: float, signal: Signal) -> bool:
        """Buy an asset"""
        # Calculate position size (max 20% of portfolio)
        max_amount = self.total_value * Config.MAX_POSITION_PCT
        amount = min(max_amount, self.cash * 0.9)  # Leave some cash buffer

        if not self.can_buy(amount):
            return False

        quantity = amount / price

        self.cash -= amount
        self.positions[symbol] = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=price,
            current_price=price,
            entry_time=datetime.now(),
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit
        )

        self.trades.append(Trade(
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=price,
            pnl=0,
            timestamp=datetime.now()
        ))

        print(f"✅ BOUGHT {quantity:.6f} {symbol} @ ${price:.2f} (${amount:.2f})")
        self._save()
        return True

    def sell(self, symbol: str, price: float, reason: str = "") -> bool:
        """Sell an asset"""
        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        proceeds = pos.quantity * price
        pnl = proceeds - pos.cost

        self.cash += proceeds
        self.daily_pnl += pnl

        self.trades.append(Trade(
            symbol=symbol,
            side="SELL",
            quantity=pos.quantity,
            price=price,
            pnl=pnl,
            timestamp=datetime.now()
        ))

        emoji = "📈" if pnl > 0 else "📉"
        print(f"✅ SOLD {pos.quantity:.6f} {symbol} @ ${price:.2f} | P&L: ${pnl:.2f} {emoji} {reason}")

        del self.positions[symbol]
        self._save()
        return True

    def check_stops(self, prices: Dict[str, Price]):
        """Check stop loss and take profit"""
        self.update_prices(prices)

        for symbol, pos in list(self.positions.items()):
            if pos.current_price <= pos.stop_loss:
                self.sell(symbol, pos.current_price, "(STOP LOSS)")
            elif pos.current_price >= pos.take_profit:
                self.sell(symbol, pos.current_price, "(TAKE PROFIT 🎯)")
            elif pos.hold_hours > Config.MAX_HOLD_HOURS:
                self.sell(symbol, pos.current_price, "(MAX HOLD TIME)")

    def _save(self):
        """Save portfolio state"""
        data = {
            "cash": self.cash,
            "positions": {
                s: {
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "entry_time": p.entry_time.isoformat(),
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit
                } for s, p in self.positions.items()
            },
            "trades": [
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "pnl": t.pnl,
                    "timestamp": t.timestamp.isoformat()
                } for t in self.trades[-50:]  # Keep last 50 trades
            ]
        }
        with open(self.SAVE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def _load(self):
        """Load portfolio state"""
        try:
            with open(self.SAVE_FILE, 'r') as f:
                data = json.load(f)

            self.cash = data.get("cash", Config.INITIAL_CAPITAL)

            for symbol, pos_data in data.get("positions", {}).items():
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=pos_data["quantity"],
                    entry_price=pos_data["entry_price"],
                    current_price=pos_data["entry_price"],
                    entry_time=datetime.fromisoformat(pos_data["entry_time"]),
                    stop_loss=pos_data["stop_loss"],
                    take_profit=pos_data["take_profit"]
                )

            print(f"📂 Loaded portfolio: ${self.total_value:.2f}")
        except FileNotFoundError:
            print(f"🆕 New portfolio: ${self.initial_capital:.2f}")
        except Exception as e:
            print(f"⚠️ Error loading portfolio: {e}")


# ============================================================================
# TRADING BOT - MAIN ENGINE
# ============================================================================

class TradingBot:
    """Your personal AI trading bot"""

    def __init__(self):
        self.fetcher = FreePriceFetcher()
        self.trader = SwingTrader(self.fetcher)
        self.portfolio = Portfolio()
        self.running = False
        self.last_scan = None

    def scan_market(self) -> Dict[str, Signal]:
        """Scan all assets for trading signals"""
        print(f"\n🔍 Scanning market at {datetime.now().strftime('%H:%M:%S')}...")

        prices = self.fetcher.get_all_prices()
        signals = {}

        # Analyze crypto
        for coin_id in Config.CRYPTO:
            if coin_id in prices:
                signal = self.trader.analyze(coin_id, prices[coin_id].price, is_crypto=True)
                if signal:
                    signals[signal.symbol] = signal

        # Analyze stocks
        for symbol in Config.STOCKS:
            if symbol in prices:
                signal = self.trader.analyze(symbol, prices[symbol].price, is_crypto=False)
                if signal:
                    signals[signal.symbol] = signal

        self.last_scan = datetime.now()
        return signals

    def execute_signals(self, signals: Dict[str, Signal]):
        """Execute trading signals"""
        prices = self.fetcher.get_all_prices()

        # First check stops on existing positions
        self.portfolio.check_stops(prices)

        for symbol, signal in signals.items():
            # Skip if already in position
            if symbol in self.portfolio.positions:
                continue

            # Only execute high confidence BUY signals
            if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                if signal.confidence >= Config.MIN_CONFIDENCE:
                    print(f"\n🎯 SIGNAL: {signal.signal_type.value} {symbol}")
                    print(f"   Price: ${signal.price:.2f}")
                    print(f"   Confidence: {signal.confidence:.0%}")
                    print(f"   Reason: {signal.reason}")
                    print(f"   Stop Loss: ${signal.stop_loss:.2f}")
                    print(f"   Take Profit: ${signal.take_profit:.2f}")
                    print(f"   Hold Time: ~{signal.hold_hours}h")

                    self.portfolio.buy(symbol, signal.price, signal)

    def print_status(self, signals: Dict[str, Signal]):
        """Print current status"""
        prices = self.fetcher.get_all_prices()
        self.portfolio.update_prices(prices)

        print("\n" + "=" * 60)
        print(f"📊 MARKET STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        # Prices
        print("\n💹 CURRENT PRICES")
        print("-" * 40)
        for key, price in prices.items():
            arrow = "🟢" if price.change_24h > 0 else "🔴"
            print(f"  {arrow} {price.symbol:8} ${price.price:>12,.2f}  ({price.change_24h:+.2f}%)")

        # Signals
        print("\n🎯 TRADING SIGNALS")
        print("-" * 40)
        buy_signals = [s for s in signals.values() if s.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]]
        sell_signals = [s for s in signals.values() if s.signal_type in [SignalType.STRONG_SELL, SignalType.SELL]]

        if buy_signals:
            for s in buy_signals:
                print(f"  {s.signal_type.value} {s.symbol} ({s.confidence:.0%})")
                print(f"    └─ {s.reason}")
        if sell_signals:
            for s in sell_signals:
                print(f"  {s.signal_type.value} {s.symbol} ({s.confidence:.0%})")
                print(f"    └─ {s.reason}")
        if not buy_signals and not sell_signals:
            print("  No actionable signals right now")

        # Portfolio
        print("\n💰 YOUR PORTFOLIO")
        print("-" * 40)
        print(f"  Cash:       ${self.portfolio.cash:>10.2f}")
        print(f"  Positions:  ${self.portfolio.positions_value:>10.2f}")
        print(f"  ─────────────────────")
        print(f"  Total:      ${self.portfolio.total_value:>10.2f}")

        pnl_emoji = "📈" if self.portfolio.total_pnl >= 0 else "📉"
        print(f"  P&L:        ${self.portfolio.total_pnl:>+10.2f} ({self.portfolio.total_pnl_pct:+.2f}%) {pnl_emoji}")

        if self.portfolio.positions:
            print("\n  📦 Open Positions:")
            for symbol, pos in self.portfolio.positions.items():
                pos_emoji = "🟢" if pos.pnl >= 0 else "🔴"
                print(f"    {pos_emoji} {symbol}: {pos.quantity:.6f} @ ${pos.entry_price:.2f}")
                print(f"       Now: ${pos.current_price:.2f} | P&L: ${pos.pnl:+.2f} ({pos.pnl_pct:+.1f}%)")
                print(f"       SL: ${pos.stop_loss:.2f} | TP: ${pos.take_profit:.2f} | {pos.hold_hours:.1f}h")

        # Recent trades
        if self.portfolio.trades:
            print("\n  📜 Recent Trades:")
            for trade in self.portfolio.trades[-3:]:
                side_emoji = "🟢" if trade.side == "BUY" else "🔴"
                pnl_str = f" | P&L: ${trade.pnl:+.2f}" if trade.side == "SELL" else ""
                print(f"    {side_emoji} {trade.side} {trade.symbol} @ ${trade.price:.2f}{pnl_str}")

    def run_once(self, auto_trade: bool = True):
        """Run one trading cycle"""
        signals = self.scan_market()
        self.print_status(signals)

        if auto_trade:
            self.execute_signals(signals)

    def run(self, auto_trade: bool = True):
        """Run continuously"""
        self.running = True
        interval = Config.SCAN_INTERVAL_MINUTES * 60

        print(f"\n🚀 Starting trading bot (scanning every {Config.SCAN_INTERVAL_MINUTES} min)")
        print("   Press Ctrl+C to stop\n")

        try:
            while self.running:
                self.run_once(auto_trade)
                print(f"\n⏰ Next scan in {Config.SCAN_INTERVAL_MINUTES} minutes...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping bot...")
            self.portfolio._save()
            print("Portfolio saved. Goodbye!")

    def stop(self):
        self.running = False


# ============================================================================
# WEB DASHBOARD
# ============================================================================

def run_dashboard():
    """Run web dashboard"""
    try:
        from flask import Flask, render_template_string, jsonify
    except ImportError:
        print("Installing Flask...")
        os.system(f"{sys.executable} -m pip install flask")
        from flask import Flask, render_template_string, jsonify

    app = Flask(__name__)
    bot = TradingBot()

    DASHBOARD = '''
<!DOCTYPE html>
<html>
<head>
    <title>🤖 My Trading Bot</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0a0a0a; color: #fff; padding: 20px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 20px; }
        .card {
            background: #1a1a1a; border-radius: 12px;
            padding: 20px; margin-bottom: 20px;
        }
        .card h2 { margin-bottom: 15px; font-size: 1.2em; }
        .price-row {
            display: flex; justify-content: space-between;
            padding: 10px 0; border-bottom: 1px solid #333;
        }
        .positive { color: #00ff88; }
        .negative { color: #ff4444; }
        .signal {
            background: #222; padding: 12px; border-radius: 8px;
            margin-bottom: 10px;
        }
        .portfolio-stat {
            display: inline-block; width: 48%;
            background: #222; padding: 15px; border-radius: 8px;
            text-align: center; margin: 5px 1%;
        }
        .stat-value { font-size: 1.5em; font-weight: bold; }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff; border: none; padding: 12px 24px;
            border-radius: 8px; cursor: pointer; margin: 5px;
        }
        .btn:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 My Trading Bot</h1>
        <p style="text-align:center;color:#888;margin-bottom:20px;">
            $100 Capital | Swing Trading | BTC ETH SPY QQQ NVDA
        </p>

        <div class="card">
            <h2>💰 Portfolio</h2>
            <div id="portfolio"></div>
        </div>

        <div class="card">
            <h2>💹 Prices</h2>
            <div id="prices"></div>
        </div>

        <div class="card">
            <h2>🎯 Signals</h2>
            <div id="signals"></div>
        </div>

        <div style="text-align:center;">
            <button class="btn" onclick="refresh()">🔄 Refresh</button>
            <button class="btn" onclick="autoTrade()">🤖 Auto Trade</button>
        </div>

        <p id="lastUpdate" style="text-align:center;color:#666;margin-top:20px;"></p>
    </div>

    <script>
        function refresh() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    // Portfolio
                    let pnlClass = data.portfolio.total_pnl >= 0 ? 'positive' : 'negative';
                    document.getElementById('portfolio').innerHTML = `
                        <div class="portfolio-stat">
                            <div class="stat-value">$${data.portfolio.total_value.toFixed(2)}</div>
                            <div>Total Value</div>
                        </div>
                        <div class="portfolio-stat">
                            <div class="stat-value ${pnlClass}">
                                ${data.portfolio.total_pnl >= 0 ? '+' : ''}$${data.portfolio.total_pnl.toFixed(2)}
                            </div>
                            <div>P&L (${data.portfolio.total_pnl_pct.toFixed(1)}%)</div>
                        </div>
                    `;

                    // Prices
                    let pricesHtml = '';
                    for (let [sym, p] of Object.entries(data.prices)) {
                        let changeClass = p.change_24h >= 0 ? 'positive' : 'negative';
                        pricesHtml += `
                            <div class="price-row">
                                <span>${p.symbol}</span>
                                <span>$${p.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                                <span class="${changeClass}">${p.change_24h >= 0 ? '+' : ''}${p.change_24h.toFixed(2)}%</span>
                            </div>
                        `;
                    }
                    document.getElementById('prices').innerHTML = pricesHtml;

                    // Signals
                    let sigsHtml = '';
                    let actionable = data.signals.filter(s => !s.signal_type.includes('HOLD'));
                    if (actionable.length === 0) {
                        sigsHtml = '<p style="color:#666;">No actionable signals right now</p>';
                    } else {
                        for (let s of actionable) {
                            sigsHtml += `
                                <div class="signal">
                                    <strong>${s.signal_type} ${s.symbol}</strong> (${(s.confidence*100).toFixed(0)}%)<br>
                                    <small style="color:#888;">${s.reason}</small>
                                </div>
                            `;
                        }
                    }
                    document.getElementById('signals').innerHTML = sigsHtml;

                    document.getElementById('lastUpdate').textContent =
                        'Last updated: ' + new Date().toLocaleTimeString();
                });
        }

        function autoTrade() {
            if (!confirm('Execute high-confidence signals?')) return;
            fetch('/api/trade', {method: 'POST'})
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

    @app.route('/')
    def index():
        return render_template_string(DASHBOARD)

    @app.route('/api/status')
    def status():
        signals = bot.scan_market()
        prices = bot.fetcher.get_all_prices()
        bot.portfolio.update_prices(prices)

        return jsonify({
            'prices': {k: {
                'symbol': v.symbol,
                'price': v.price,
                'change_24h': v.change_24h
            } for k, v in prices.items()},
            'signals': [{
                'symbol': s.symbol,
                'signal_type': s.signal_type.value,
                'confidence': s.confidence,
                'reason': s.reason
            } for s in signals.values()],
            'portfolio': {
                'cash': bot.portfolio.cash,
                'total_value': bot.portfolio.total_value,
                'total_pnl': bot.portfolio.total_pnl,
                'total_pnl_pct': bot.portfolio.total_pnl_pct
            }
        })

    @app.route('/api/trade', methods=['POST'])
    def trade():
        signals = bot.scan_market()
        bot.execute_signals(signals)
        return jsonify({'success': True, 'message': 'Trades executed!'})

    print("\n" + "=" * 50)
    print("  🤖 YOUR TRADING BOT DASHBOARD")
    print("=" * 50)
    print(f"\n  Open: http://localhost:5000")
    print(f"  Capital: $100")
    print(f"  Assets: BTC, ETH, S&P 500, NASDAQ, NVDA")
    print(f"  Strategy: Swing Trading (1-24h)")
    print(f"\n  Press Ctrl+C to stop")
    print("=" * 50 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=False)


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🤖  YOUR PERSONAL TRADING BOT                              ║
║                                                              ║
║   Capital: $100 | Assets: BTC ETH SPY QQQ NVDA              ║
║   Strategy: Swing Trading (1-24h) | Risk: Moderate          ║
║                                                              ║
║   100% FREE - No API keys needed!                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print("Choose mode:")
    print("  1. 🌐 Web Dashboard (recommended)")
    print("  2. 💻 Terminal Mode")
    print("  3. 🧪 Test prices only")
    print("  4. 📊 Single scan")

    try:
        choice = input("\nEnter choice (1-4): ").strip()
    except:
        choice = "1"

    if choice == "1":
        run_dashboard()
    elif choice == "2":
        bot = TradingBot()
        bot.run(auto_trade=True)
    elif choice == "3":
        fetcher = FreePriceFetcher()
        print("\n📊 Fetching real prices...")
        prices = fetcher.get_all_prices()
        for key, price in prices.items():
            print(f"  {price.symbol}: ${price.price:,.2f} ({price.change_24h:+.2f}%)")
    elif choice == "4":
        bot = TradingBot()
        bot.run_once(auto_trade=False)
    else:
        print("Invalid choice, starting web dashboard...")
        run_dashboard()


if __name__ == "__main__":
    main()
