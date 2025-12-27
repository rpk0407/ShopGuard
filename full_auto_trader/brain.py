"""
Trading Brain - AI that combines all signals to make trading decisions
"""
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import requests


class SignalStrength(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class TradingDecision:
    """Final trading decision from the AI brain"""
    symbol: str
    signal: SignalStrength
    confidence: float  # 0 to 1
    price: float

    # Components
    technical_score: float
    news_score: float
    social_score: float

    # Trade parameters
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_pct: float

    # Reasoning
    reasons: List[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signal": self.signal.value,
            "confidence": round(self.confidence * 100, 1),
            "price": self.price,
            "technical": round(self.technical_score, 2),
            "news": round(self.news_score, 2),
            "social": round(self.social_score, 2),
            "stop_loss": round(self.stop_loss, 2),
            "take_profit": round(self.take_profit, 2),
            "reasons": self.reasons
        }


class TradingBrain:
    """
    AI Trading Brain - Combines multiple data sources:
    1. Technical Analysis (price action, indicators)
    2. News Sentiment (financial news)
    3. Social Sentiment (Reddit, Twitter)

    Weights can be configured.
    """

    def __init__(self,
                 technical_weight: float = 0.40,
                 news_weight: float = 0.30,
                 social_weight: float = 0.30,
                 stop_loss_pct: float = 0.03,
                 take_profit_pct: float = 0.06):

        self.technical_weight = technical_weight
        self.news_weight = news_weight
        self.social_weight = social_weight
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        # Price fetcher
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

        self._price_cache: Dict[str, Tuple[float, datetime]] = {}

    # =========================================================================
    # PRICE FETCHING
    # =========================================================================

    def get_price(self, symbol: str, is_crypto: bool = False) -> float:
        """Get current price"""
        cache_key = symbol
        if cache_key in self._price_cache:
            price, cached_at = self._price_cache[cache_key]
            if datetime.now() - cached_at < timedelta(seconds=30):
                return price

        try:
            if is_crypto:
                coin_id = {"BTC": "bitcoin", "ETH": "ethereum"}.get(symbol, symbol.lower())
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
                resp = self.session.get(url, timeout=10)
                price = resp.json()[coin_id]["usd"]
            else:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                resp = self.session.get(url, timeout=10)
                price = resp.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]

            self._price_cache[cache_key] = (price, datetime.now())
            return price
        except:
            return self._price_cache.get(cache_key, (0, datetime.now()))[0]

    def get_price_history(self, symbol: str, is_crypto: bool = False) -> List[float]:
        """Get price history"""
        try:
            if is_crypto:
                coin_id = {"BTC": "bitcoin", "ETH": "ethereum"}.get(symbol, symbol.lower())
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=7"
                resp = self.session.get(url, timeout=10)
                return [candle[4] for candle in resp.json()]
            else:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=7d"
                resp = self.session.get(url, timeout=10)
                closes = resp.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                return [c for c in closes if c is not None]
        except:
            return []

    # =========================================================================
    # TECHNICAL ANALYSIS
    # =========================================================================

    def _rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50
        deltas = np.diff(prices[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100
        return 100 - (100 / (1 + avg_gain / avg_loss))

    def _sma(self, prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0
        return np.mean(prices[-period:])

    def _ema(self, prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema

    def _bollinger_position(self, prices: List[float]) -> float:
        if len(prices) < 20:
            return 0.5
        sma = np.mean(prices[-20:])
        std = np.std(prices[-20:])
        if std == 0:
            return 0.5
        upper = sma + 2 * std
        lower = sma - 2 * std
        return (prices[-1] - lower) / (upper - lower)

    def analyze_technical(self, symbol: str, is_crypto: bool = False) -> Tuple[float, List[str]]:
        """
        Analyze technical indicators
        Returns score (-1 to 1) and list of reasons
        """
        prices = self.get_price_history(symbol, is_crypto)
        if len(prices) < 20:
            return 0, ["Insufficient price data"]

        current = prices[-1]
        reasons = []
        score = 0

        # RSI
        rsi = self._rsi(prices)
        if rsi < 30:
            score += 0.3
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi < 40:
            score += 0.15
            reasons.append(f"RSI low ({rsi:.0f})")
        elif rsi > 70:
            score -= 0.3
            reasons.append(f"RSI overbought ({rsi:.0f})")
        elif rsi > 60:
            score -= 0.15
            reasons.append(f"RSI high ({rsi:.0f})")

        # Moving averages
        sma_short = self._sma(prices, 10)
        sma_long = self._sma(prices, 30)
        ema_fast = self._ema(prices, 8)
        ema_slow = self._ema(prices, 21)

        if ema_fast > ema_slow and sma_short > sma_long:
            score += 0.25
            reasons.append("Bullish MA crossover")
        elif ema_fast < ema_slow and sma_short < sma_long:
            score -= 0.25
            reasons.append("Bearish MA crossover")

        # Price vs MAs
        if current > sma_short > sma_long:
            score += 0.15
            reasons.append("Uptrend (price > MAs)")
        elif current < sma_short < sma_long:
            score -= 0.15
            reasons.append("Downtrend (price < MAs)")

        # Bollinger position
        bb_pos = self._bollinger_position(prices)
        if bb_pos < 0.2:
            score += 0.2
            reasons.append("Near lower Bollinger Band")
        elif bb_pos > 0.8:
            score -= 0.2
            reasons.append("Near upper Bollinger Band")

        # Momentum
        if len(prices) >= 10:
            momentum = (current - prices[-10]) / prices[-10]
            if momentum > 0.05:
                score += 0.1
                reasons.append(f"Strong momentum (+{momentum*100:.1f}%)")
            elif momentum < -0.05:
                score -= 0.1
                reasons.append(f"Weak momentum ({momentum*100:.1f}%)")

        return max(-1, min(1, score)), reasons

    # =========================================================================
    # COMBINE ALL SIGNALS
    # =========================================================================

    def analyze(self, symbol: str,
                news_sentiment: float = 0,
                social_sentiment: float = 0,
                is_crypto: bool = False) -> TradingDecision:
        """
        Analyze all signals and make a trading decision

        Args:
            symbol: Asset symbol
            news_sentiment: -1 to 1 from news analysis
            social_sentiment: -1 to 1 from social media
            is_crypto: Whether this is a crypto asset

        Returns:
            TradingDecision with signal, confidence, and trade params
        """
        price = self.get_price(symbol, is_crypto)

        # Get technical score
        technical_score, tech_reasons = self.analyze_technical(symbol, is_crypto)

        # Combine scores with weights
        combined_score = (
            technical_score * self.technical_weight +
            news_sentiment * self.news_weight +
            social_sentiment * self.social_weight
        )

        # Build reasons list
        reasons = tech_reasons.copy()
        if news_sentiment > 0.2:
            reasons.append(f"Positive news sentiment ({news_sentiment:.2f})")
        elif news_sentiment < -0.2:
            reasons.append(f"Negative news sentiment ({news_sentiment:.2f})")

        if social_sentiment > 0.2:
            reasons.append(f"Bullish social buzz ({social_sentiment:.2f})")
        elif social_sentiment < -0.2:
            reasons.append(f"Bearish social buzz ({social_sentiment:.2f})")

        # Determine signal strength
        if combined_score > 0.5:
            signal = SignalStrength.STRONG_BUY
            confidence = min(0.95, 0.7 + combined_score * 0.3)
        elif combined_score > 0.2:
            signal = SignalStrength.BUY
            confidence = min(0.85, 0.5 + combined_score * 0.4)
        elif combined_score < -0.5:
            signal = SignalStrength.STRONG_SELL
            confidence = min(0.95, 0.7 + abs(combined_score) * 0.3)
        elif combined_score < -0.2:
            signal = SignalStrength.SELL
            confidence = min(0.85, 0.5 + abs(combined_score) * 0.4)
        else:
            signal = SignalStrength.HOLD
            confidence = 0.5

        # Calculate SL/TP
        stop_loss = price * (1 - self.stop_loss_pct)
        take_profit = price * (1 + self.take_profit_pct)

        # Position size based on confidence
        position_size_pct = confidence * 0.20  # Max 20% at 100% confidence

        return TradingDecision(
            symbol=symbol,
            signal=signal,
            confidence=confidence,
            price=price,
            technical_score=technical_score,
            news_score=news_sentiment,
            social_score=social_sentiment,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_pct=position_size_pct,
            reasons=reasons
        )


# Quick test
if __name__ == "__main__":
    brain = TradingBrain()

    print("\n🧠 AI TRADING BRAIN TEST")
    print("=" * 60)

    symbols = [("NVDA", False), ("BTC", True), ("SPY", False)]

    for symbol, is_crypto in symbols:
        decision = brain.analyze(
            symbol,
            news_sentiment=0.2,  # Simulated
            social_sentiment=0.3,  # Simulated
            is_crypto=is_crypto
        )

        emoji = "🟢" if "BUY" in decision.signal.value else "🔴" if "SELL" in decision.signal.value else "⚪"
        print(f"\n{emoji} {symbol}: {decision.signal.value}")
        print(f"   Price: ${decision.price:,.2f}")
        print(f"   Confidence: {decision.confidence:.0%}")
        print(f"   Technical: {decision.technical_score:.2f} | News: {decision.news_score:.2f} | Social: {decision.social_score:.2f}")
        print(f"   SL: ${decision.stop_loss:,.2f} | TP: ${decision.take_profit:,.2f}")
        print(f"   Reasons: {', '.join(decision.reasons[:3])}")
