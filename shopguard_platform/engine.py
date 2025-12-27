"""
Trading Engine - Core trading logic and execution
"""
import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import requests

from .database import db, Trade, Position, Alert


class SignalType(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class MarketData:
    symbol: str
    price: float
    change_1h: float
    change_24h: float
    volume: float
    high_24h: float
    low_24h: float
    market_cap: Optional[float] = None


@dataclass
class TradingSignal:
    symbol: str
    signal: SignalType
    confidence: float
    price: float
    technical_score: float
    news_score: float
    social_score: float
    reasons: List[str]
    stop_loss: float
    take_profit: float
    timestamp: datetime = field(default_factory=datetime.now)


class TradingEngine:
    """
    Complete trading engine with all components integrated
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

        # Cache
        self._price_cache: Dict[str, Tuple[MarketData, datetime]] = {}
        self._history_cache: Dict[str, Tuple[List[float], datetime]] = {}

        # State
        self.running = False
        self.last_scan = None
        self.last_signals: Dict[str, TradingSignal] = {}

        # Load settings
        self._load_settings()

    def _load_settings(self):
        """Load settings from database"""
        settings = db.get_all_settings()
        self.initial_capital = float(settings.get("initial_capital", 100))
        self.stop_loss_pct = float(settings.get("stop_loss_pct", 0.03))
        self.take_profit_pct = float(settings.get("take_profit_pct", 0.06))
        self.max_position_pct = float(settings.get("max_position_pct", 0.20))
        self.min_confidence = float(settings.get("min_confidence", 0.65))
        self.stocks = json.loads(settings.get("stocks", '["NVDA", "SPY", "QQQ"]'))
        self.crypto = json.loads(settings.get("crypto", '["bitcoin", "ethereum"]'))

    def reload_settings(self):
        """Reload settings from database"""
        self._load_settings()

    # =========================================================================
    # MARKET DATA
    # =========================================================================

    def get_crypto_prices(self, coins: List[str] = None) -> Dict[str, MarketData]:
        """Get crypto prices from CoinGecko"""
        if coins is None:
            coins = self.crypto

        cache_key = ",".join(sorted(coins))
        if cache_key in self._price_cache:
            data, cached_at = self._price_cache[cache_key]
            if datetime.now() - cached_at < timedelta(seconds=30):
                return {cache_key: data}

        try:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                "vs_currency": "usd",
                "ids": ",".join(coins),
                "price_change_percentage": "1h,24h"
            }
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()

            result = {}
            for coin in resp.json():
                symbol = coin["symbol"].upper()
                data = MarketData(
                    symbol=symbol,
                    price=coin["current_price"] or 0,
                    change_1h=coin.get("price_change_percentage_1h_in_currency", 0) or 0,
                    change_24h=coin.get("price_change_percentage_24h", 0) or 0,
                    volume=coin.get("total_volume", 0) or 0,
                    high_24h=coin.get("high_24h", coin["current_price"]) or 0,
                    low_24h=coin.get("low_24h", coin["current_price"]) or 0,
                    market_cap=coin.get("market_cap")
                )
                result[coin["id"]] = data
                self._price_cache[coin["id"]] = (data, datetime.now())

            return result
        except Exception as e:
            print(f"Crypto price error: {e}")
            return {}

    def get_stock_price(self, symbol: str) -> Optional[MarketData]:
        """Get stock price from Yahoo Finance"""
        if symbol in self._price_cache:
            data, cached_at = self._price_cache[symbol]
            if datetime.now() - cached_at < timedelta(seconds=30):
                return data

        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"interval": "1h", "range": "2d"}
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()

            result = resp.json()["chart"]["result"][0]
            meta = result["meta"]
            quotes = result["indicators"]["quote"][0]

            current = meta["regularMarketPrice"]
            prev_close = meta.get("previousClose", current)
            closes = [c for c in quotes["close"] if c is not None]

            change_1h = 0
            if len(closes) >= 2:
                change_1h = ((closes[-1] - closes[-2]) / closes[-2]) * 100

            change_24h = ((current - prev_close) / prev_close) * 100 if prev_close else 0

            data = MarketData(
                symbol=symbol,
                price=current,
                change_1h=change_1h,
                change_24h=change_24h,
                volume=meta.get("regularMarketVolume", 0),
                high_24h=meta.get("regularMarketDayHigh", current),
                low_24h=meta.get("regularMarketDayLow", current)
            )

            self._price_cache[symbol] = (data, datetime.now())
            return data
        except Exception as e:
            print(f"Stock price error ({symbol}): {e}")
            return None

    def get_all_prices(self) -> Dict[str, MarketData]:
        """Get all market prices"""
        result = {}

        # Crypto
        crypto = self.get_crypto_prices()
        result.update(crypto)

        # Stocks
        for symbol in self.stocks:
            data = self.get_stock_price(symbol)
            if data:
                result[symbol] = data
            time.sleep(0.1)

        return result

    def get_price_history(self, symbol: str, is_crypto: bool = False) -> List[float]:
        """Get price history for technical analysis"""
        cache_key = f"hist_{symbol}"
        if cache_key in self._history_cache:
            data, cached_at = self._history_cache[cache_key]
            if datetime.now() - cached_at < timedelta(minutes=5):
                return data

        try:
            if is_crypto:
                coin_id = {"BTC": "bitcoin", "ETH": "ethereum"}.get(symbol, symbol.lower())
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
                params = {"vs_currency": "usd", "days": 7}
                resp = self.session.get(url, params=params, timeout=10)
                prices = [c[4] for c in resp.json()]
            else:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                params = {"interval": "1h", "range": "7d"}
                resp = self.session.get(url, params=params, timeout=10)
                closes = resp.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                prices = [c for c in closes if c is not None]

            self._history_cache[cache_key] = (prices, datetime.now())
            return prices
        except:
            return []

    # =========================================================================
    # NEWS ANALYSIS
    # =========================================================================

    POSITIVE_WORDS = {"surge", "soar", "jump", "rally", "gain", "beat", "profit", "growth", "bullish", "upgrade", "boom", "breakthrough"}
    NEGATIVE_WORDS = {"crash", "plunge", "drop", "fall", "decline", "miss", "loss", "bearish", "downgrade", "warning", "crisis", "fraud"}

    def get_news_sentiment(self, symbol: str) -> Tuple[float, List[str]]:
        """Get news sentiment for a symbol"""
        try:
            query = f"{symbol} stock" if symbol not in ["BTC", "ETH"] else f"{symbol} crypto"
            url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            resp = self.session.get(url, timeout=10)

            from xml.etree import ElementTree
            root = ElementTree.fromstring(resp.content)

            headlines = []
            sentiment_sum = 0

            for item in root.findall(".//item")[:10]:
                title = item.find("title").text or ""
                headlines.append(title)

                words = set(title.lower().split())
                pos = len(words & self.POSITIVE_WORDS)
                neg = len(words & self.NEGATIVE_WORDS)

                if pos + neg > 0:
                    sentiment_sum += (pos - neg) / (pos + neg)

            avg_sentiment = sentiment_sum / len(headlines) if headlines else 0
            return avg_sentiment, headlines[:5]
        except:
            return 0, []

    # =========================================================================
    # SOCIAL SENTIMENT
    # =========================================================================

    BULLISH_WORDS = {"moon", "rocket", "buy", "calls", "bull", "long", "diamond", "tendies", "gains", "pump"}
    BEARISH_WORDS = {"puts", "bear", "short", "sell", "crash", "dump", "bag", "loss", "rip"}

    def get_social_sentiment(self, symbol: str) -> Tuple[float, int]:
        """Get Reddit sentiment for a symbol"""
        try:
            subreddits = ["wallstreetbets", "stocks"] if symbol not in ["BTC", "ETH"] else ["cryptocurrency", "Bitcoin"]

            total_sentiment = 0
            total_mentions = 0

            for sub in subreddits:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
                resp = self.session.get(url, timeout=10)

                for post in resp.json()["data"]["children"]:
                    title = post["data"]["title"].upper()
                    if symbol in title or symbol.replace(".", "") in title:
                        total_mentions += 1
                        words = set(title.lower().split())
                        bull = len(words & self.BULLISH_WORDS)
                        bear = len(words & self.BEARISH_WORDS)
                        if bull + bear > 0:
                            total_sentiment += (bull - bear) / (bull + bear)

                time.sleep(0.3)

            avg_sentiment = total_sentiment / total_mentions if total_mentions > 0 else 0
            return avg_sentiment, total_mentions
        except:
            return 0, 0

    # =========================================================================
    # TECHNICAL ANALYSIS
    # =========================================================================

    def _rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50
        import numpy as np
        deltas = np.diff(prices[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain, avg_loss = np.mean(gains), np.mean(losses)
        if avg_loss == 0:
            return 100
        return 100 - (100 / (1 + avg_gain / avg_loss))

    def _sma(self, prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0
        import numpy as np
        return float(np.mean(prices[-period:]))

    def _bollinger_position(self, prices: List[float]) -> float:
        if len(prices) < 20:
            return 0.5
        import numpy as np
        sma = np.mean(prices[-20:])
        std = np.std(prices[-20:])
        if std == 0:
            return 0.5
        upper, lower = sma + 2 * std, sma - 2 * std
        return (prices[-1] - lower) / (upper - lower)

    def analyze_technical(self, prices: List[float]) -> Tuple[float, List[str]]:
        """Analyze technical indicators"""
        if len(prices) < 20:
            return 0, ["Insufficient data"]

        score = 0
        reasons = []

        # RSI
        rsi = self._rsi(prices)
        if rsi < 30:
            score += 0.3
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi > 70:
            score -= 0.3
            reasons.append(f"RSI overbought ({rsi:.0f})")

        # Moving averages
        sma_short = self._sma(prices, 10)
        sma_long = self._sma(prices, 30)
        if sma_short > sma_long:
            score += 0.2
            reasons.append("Bullish MA crossover")
        else:
            score -= 0.2
            reasons.append("Bearish MA crossover")

        # Bollinger
        bb_pos = self._bollinger_position(prices)
        if bb_pos < 0.2:
            score += 0.2
            reasons.append("Near lower BB")
        elif bb_pos > 0.8:
            score -= 0.2
            reasons.append("Near upper BB")

        # Momentum
        if len(prices) >= 10:
            momentum = (prices[-1] - prices[-10]) / prices[-10]
            if momentum > 0.05:
                score += 0.15
                reasons.append(f"Strong momentum (+{momentum*100:.1f}%)")
            elif momentum < -0.05:
                score -= 0.15

        return max(-1, min(1, score)), reasons

    # =========================================================================
    # SIGNAL GENERATION
    # =========================================================================

    def generate_signal(self, symbol: str, is_crypto: bool = False) -> Optional[TradingSignal]:
        """Generate complete trading signal for a symbol"""
        # Get current price
        if is_crypto:
            coin_id = {"BTC": "bitcoin", "ETH": "ethereum"}.get(symbol, symbol.lower())
            prices = self.get_crypto_prices([coin_id])
            if coin_id not in prices:
                return None
            current_price = prices[coin_id].price
        else:
            data = self.get_stock_price(symbol)
            if not data:
                return None
            current_price = data.price

        # Get price history
        history = self.get_price_history(symbol, is_crypto)
        if len(history) < 10:
            return None

        # Technical analysis
        tech_score, tech_reasons = self.analyze_technical(history)

        # News sentiment
        news_score, _ = self.get_news_sentiment(symbol)

        # Social sentiment
        social_score, mentions = self.get_social_sentiment(symbol)

        # Combined score (weighted)
        combined = tech_score * 0.4 + news_score * 0.3 + social_score * 0.3

        # Build reasons
        reasons = tech_reasons.copy()
        if news_score > 0.2:
            reasons.append(f"Positive news ({news_score:.2f})")
        elif news_score < -0.2:
            reasons.append(f"Negative news ({news_score:.2f})")
        if mentions > 5:
            reasons.append(f"High social buzz ({mentions} mentions)")

        # Determine signal
        if combined > 0.5:
            signal = SignalType.STRONG_BUY
            confidence = min(0.95, 0.7 + combined * 0.3)
        elif combined > 0.2:
            signal = SignalType.BUY
            confidence = min(0.85, 0.5 + combined * 0.4)
        elif combined < -0.5:
            signal = SignalType.STRONG_SELL
            confidence = min(0.95, 0.7 + abs(combined) * 0.3)
        elif combined < -0.2:
            signal = SignalType.SELL
            confidence = min(0.85, 0.5 + abs(combined) * 0.4)
        else:
            signal = SignalType.HOLD
            confidence = 0.5

        return TradingSignal(
            symbol=symbol,
            signal=signal,
            confidence=confidence,
            price=current_price,
            technical_score=tech_score,
            news_score=news_score,
            social_score=social_score,
            reasons=reasons,
            stop_loss=current_price * (1 - self.stop_loss_pct),
            take_profit=current_price * (1 + self.take_profit_pct)
        )

    def scan_all(self) -> Dict[str, TradingSignal]:
        """Scan all assets and generate signals"""
        signals = {}

        # Scan stocks
        for symbol in self.stocks:
            signal = self.generate_signal(symbol, is_crypto=False)
            if signal:
                signals[symbol] = signal
            time.sleep(0.2)

        # Scan crypto
        for coin in self.crypto:
            symbol = {"bitcoin": "BTC", "ethereum": "ETH"}.get(coin, coin.upper())
            signal = self.generate_signal(symbol, is_crypto=True)
            if signal:
                signals[symbol] = signal
            time.sleep(0.2)

        self.last_signals = signals
        self.last_scan = datetime.now()
        return signals

    # =========================================================================
    # PORTFOLIO MANAGEMENT
    # =========================================================================

    def get_portfolio_value(self) -> Dict:
        """Get current portfolio value"""
        portfolio = db.get_portfolio()
        positions = db.get_positions()

        # Update position prices
        prices = self.get_all_prices()
        positions_value = 0

        for pos in positions:
            if pos.symbol in prices:
                db.update_position_price(pos.symbol, prices[pos.symbol].price)
                pos.current_price = prices[pos.symbol].price

            pnl = (pos.current_price - pos.entry_price) * pos.quantity
            positions_value += pos.current_price * pos.quantity

        cash = portfolio["cash"] if portfolio else self.initial_capital
        equity = cash + positions_value
        total_pnl = equity - self.initial_capital

        return {
            "cash": cash,
            "positions_value": positions_value,
            "equity": equity,
            "initial_capital": self.initial_capital,
            "total_pnl": total_pnl,
            "total_pnl_pct": (total_pnl / self.initial_capital) * 100,
            "positions": positions
        }

    def execute_buy(self, symbol: str, signal: TradingSignal) -> bool:
        """Execute a buy order"""
        portfolio = self.get_portfolio_value()

        # Check if already in position
        existing = db.get_position(symbol)
        if existing:
            return False

        # Calculate position size
        position_value = portfolio["equity"] * self.max_position_pct
        if position_value > portfolio["cash"]:
            position_value = portfolio["cash"] * 0.95

        quantity = position_value / signal.price

        if quantity <= 0 or position_value < 1:
            return False

        # Update cash
        new_cash = portfolio["cash"] - position_value
        db.update_cash(new_cash)

        # Create position
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=signal.price,
            current_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            entry_time=datetime.now().isoformat(),
            strategy=f"{signal.signal.value} ({signal.confidence:.0%})"
        )
        db.save_position(position)

        # Record trade
        trade = Trade(
            id=0,
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=signal.price,
            total=position_value,
            pnl=0,
            strategy=signal.signal.value,
            confidence=signal.confidence,
            timestamp=datetime.now().isoformat(),
            notes="; ".join(signal.reasons[:2])
        )
        db.add_trade(trade)

        # Add alert
        db.add_alert("trade", symbol, f"BOUGHT {quantity:.4f} {symbol} @ ${signal.price:.2f}", "info")

        return True

    def execute_sell(self, symbol: str, price: float = None) -> bool:
        """Execute a sell order"""
        position = db.get_position(symbol)
        if not position:
            return False

        if price is None:
            # Get current price
            is_crypto = symbol in ["BTC", "ETH"]
            if is_crypto:
                prices = self.get_crypto_prices()
                coin_id = {"BTC": "bitcoin", "ETH": "ethereum"}.get(symbol)
                if coin_id in prices:
                    price = prices[coin_id].price
            else:
                data = self.get_stock_price(symbol)
                if data:
                    price = data.price

        if not price:
            price = position.current_price

        # Calculate P&L
        proceeds = position.quantity * price
        pnl = (price - position.entry_price) * position.quantity

        # Update cash
        portfolio = db.get_portfolio()
        new_cash = portfolio["cash"] + proceeds
        db.update_cash(new_cash)

        # Record trade
        trade = Trade(
            id=0,
            symbol=symbol,
            side="SELL",
            quantity=position.quantity,
            price=price,
            total=proceeds,
            pnl=pnl,
            strategy="CLOSE",
            confidence=0,
            timestamp=datetime.now().isoformat(),
            notes=f"Entry: ${position.entry_price:.2f}"
        )
        db.add_trade(trade)

        # Delete position
        db.delete_position(symbol)

        # Add alert
        pnl_emoji = "📈" if pnl > 0 else "📉"
        db.add_alert("trade", symbol, f"SOLD {symbol} | P&L: ${pnl:.2f} {pnl_emoji}", "info")

        return True

    def check_stops(self):
        """Check stop loss and take profit for all positions"""
        positions = db.get_positions()
        prices = self.get_all_prices()

        for pos in positions:
            current_price = None

            # Get current price
            if pos.symbol in prices:
                current_price = prices[pos.symbol].price
            elif pos.symbol == "BTC" and "bitcoin" in prices:
                current_price = prices["bitcoin"].price
            elif pos.symbol == "ETH" and "ethereum" in prices:
                current_price = prices["ethereum"].price

            if not current_price:
                continue

            # Update price
            db.update_position_price(pos.symbol, current_price)

            # Check stop loss
            if pos.stop_loss and current_price <= pos.stop_loss:
                db.add_alert("signal", pos.symbol, f"STOP LOSS triggered at ${current_price:.2f}", "warning")
                self.execute_sell(pos.symbol, current_price)

            # Check take profit
            elif pos.take_profit and current_price >= pos.take_profit:
                db.add_alert("signal", pos.symbol, f"TAKE PROFIT triggered at ${current_price:.2f}", "info")
                self.execute_sell(pos.symbol, current_price)


# Global engine instance
engine = TradingEngine()
