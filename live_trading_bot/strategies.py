"""
Trading Strategies - Generates BUY/SELL signals based on technical analysis
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import numpy as np

from .signals import Signal, SignalType
from .price_fetcher import HistoricalBar


@dataclass
class StrategyResult:
    """Result from strategy analysis"""
    signal: Signal
    indicators: dict


class Strategy(ABC):
    """Base class for trading strategies"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def analyze(self, symbol: str, bars: List[HistoricalBar], current_price: float) -> Optional[Signal]:
        """Analyze price data and generate signal"""
        pass

    def _calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return np.mean(prices[-period:])

    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50  # Neutral

        deltas = np.diff(prices[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, prices: List[float]) -> tuple:
        """Calculate MACD (12, 26, 9)"""
        if len(prices) < 26:
            return 0, 0, 0

        ema12 = self._calculate_ema(prices, 12)
        ema26 = self._calculate_ema(prices, 26)
        macd_line = ema12 - ema26

        # For signal line, we'd need historical MACD values
        # Simplified: just return macd_line
        return macd_line, 0, macd_line

    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> tuple:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            price = prices[-1] if prices else 0
            return price, price, price

        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        return upper, sma, lower


class MomentumStrategy(Strategy):
    """
    Momentum Strategy
    - Buy when price breaks above SMA with increasing volume
    - Sell when price breaks below SMA
    """

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        super().__init__("Momentum")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def analyze(self, symbol: str, bars: List[HistoricalBar], current_price: float) -> Optional[Signal]:
        if len(bars) < self.slow_period:
            return None

        closes = [bar.close for bar in bars]

        # Calculate moving averages
        fast_sma = self._calculate_sma(closes, self.fast_period)
        slow_sma = self._calculate_sma(closes, self.slow_period)

        # Calculate momentum
        momentum = (current_price - closes[-self.fast_period]) / closes[-self.fast_period] * 100

        # Determine signal
        if fast_sma > slow_sma and current_price > fast_sma:
            # Bullish crossover
            confidence = min(0.9, 0.5 + abs(momentum) / 20)
            if momentum > 5:
                signal_type = SignalType.STRONG_BUY
                reason = f"Strong upward momentum ({momentum:.1f}%), price above MAs"
            else:
                signal_type = SignalType.BUY
                reason = f"Bullish momentum ({momentum:.1f}%), fast MA above slow MA"

            return Signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                strategy=self.name,
                reason=reason,
                target_price=current_price * 1.05,  # 5% target
                stop_loss=current_price * 0.97  # 3% stop
            )

        elif fast_sma < slow_sma and current_price < fast_sma:
            # Bearish crossover
            confidence = min(0.9, 0.5 + abs(momentum) / 20)
            if momentum < -5:
                signal_type = SignalType.STRONG_SELL
                reason = f"Strong downward momentum ({momentum:.1f}%), price below MAs"
            else:
                signal_type = SignalType.SELL
                reason = f"Bearish momentum ({momentum:.1f}%), fast MA below slow MA"

            return Signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                strategy=self.name,
                reason=reason
            )

        return Signal(
            symbol=symbol,
            signal_type=SignalType.HOLD,
            confidence=0.5,
            price=current_price,
            strategy=self.name,
            reason="No clear momentum signal"
        )


class RSIStrategy(Strategy):
    """
    RSI Strategy
    - Buy when RSI < 30 (oversold)
    - Sell when RSI > 70 (overbought)
    """

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        super().__init__("RSI")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def analyze(self, symbol: str, bars: List[HistoricalBar], current_price: float) -> Optional[Signal]:
        if len(bars) < self.period + 1:
            return None

        closes = [bar.close for bar in bars]
        rsi = self._calculate_rsi(closes, self.period)

        if rsi < self.oversold:
            # Oversold - potential buy
            confidence = min(0.9, 0.5 + (self.oversold - rsi) / 30)
            if rsi < 20:
                signal_type = SignalType.STRONG_BUY
                reason = f"Extremely oversold (RSI: {rsi:.1f})"
            else:
                signal_type = SignalType.BUY
                reason = f"Oversold condition (RSI: {rsi:.1f})"

            return Signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                strategy=self.name,
                reason=reason,
                target_price=current_price * 1.08,  # 8% target on oversold bounce
                stop_loss=current_price * 0.95  # 5% stop
            )

        elif rsi > self.overbought:
            # Overbought - potential sell
            confidence = min(0.9, 0.5 + (rsi - self.overbought) / 30)
            if rsi > 80:
                signal_type = SignalType.STRONG_SELL
                reason = f"Extremely overbought (RSI: {rsi:.1f})"
            else:
                signal_type = SignalType.SELL
                reason = f"Overbought condition (RSI: {rsi:.1f})"

            return Signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                strategy=self.name,
                reason=reason
            )

        return Signal(
            symbol=symbol,
            signal_type=SignalType.HOLD,
            confidence=0.5,
            price=current_price,
            strategy=self.name,
            reason=f"RSI neutral ({rsi:.1f})"
        )


class MeanReversionStrategy(Strategy):
    """
    Mean Reversion Strategy using Bollinger Bands
    - Buy when price touches lower band
    - Sell when price touches upper band
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__("MeanReversion")
        self.period = period
        self.std_dev = std_dev

    def analyze(self, symbol: str, bars: List[HistoricalBar], current_price: float) -> Optional[Signal]:
        if len(bars) < self.period:
            return None

        closes = [bar.close for bar in bars]
        upper, middle, lower = self._calculate_bollinger_bands(closes, self.period, self.std_dev)

        # Calculate position within bands
        band_width = upper - lower
        if band_width == 0:
            return None

        position = (current_price - lower) / band_width  # 0 = at lower, 1 = at upper

        if position < 0.1:
            # Near lower band - buy signal
            confidence = min(0.85, 0.6 + (0.1 - position) * 2)
            signal_type = SignalType.STRONG_BUY if position < 0 else SignalType.BUY
            reason = f"Price at lower Bollinger Band (position: {position:.1%})"

            return Signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                strategy=self.name,
                reason=reason,
                target_price=middle,  # Target the mean
                stop_loss=lower * 0.98  # Stop below lower band
            )

        elif position > 0.9:
            # Near upper band - sell signal
            confidence = min(0.85, 0.6 + (position - 0.9) * 2)
            signal_type = SignalType.STRONG_SELL if position > 1 else SignalType.SELL
            reason = f"Price at upper Bollinger Band (position: {position:.1%})"

            return Signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                strategy=self.name,
                reason=reason
            )

        return Signal(
            symbol=symbol,
            signal_type=SignalType.HOLD,
            confidence=0.5,
            price=current_price,
            strategy=self.name,
            reason=f"Price within Bollinger Bands ({position:.0%})"
        )


class CombinedStrategy(Strategy):
    """
    Combines multiple strategies for stronger signals
    Only triggers when multiple strategies agree
    """

    def __init__(self):
        super().__init__("Combined")
        self.strategies = [
            MomentumStrategy(),
            RSIStrategy(),
            MeanReversionStrategy()
        ]

    def analyze(self, symbol: str, bars: List[HistoricalBar], current_price: float) -> Optional[Signal]:
        signals = []
        for strategy in self.strategies:
            signal = strategy.analyze(symbol, bars, current_price)
            if signal:
                signals.append(signal)

        if not signals:
            return None

        # Count buy/sell votes
        buy_votes = sum(1 for s in signals if s.is_buy)
        sell_votes = sum(1 for s in signals if s.is_sell)
        total = len(signals)

        # Calculate average confidence
        avg_confidence = np.mean([s.confidence for s in signals])

        if buy_votes >= 2:
            # Majority buy
            reasons = [s.reason for s in signals if s.is_buy]
            signal_type = SignalType.STRONG_BUY if buy_votes == total else SignalType.BUY

            return Signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=min(0.95, avg_confidence * 1.2),
                price=current_price,
                strategy=self.name,
                reason=f"{buy_votes}/{total} strategies agree: " + "; ".join(reasons[:2]),
                target_price=current_price * 1.06,
                stop_loss=current_price * 0.96
            )

        elif sell_votes >= 2:
            # Majority sell
            reasons = [s.reason for s in signals if s.is_sell]
            signal_type = SignalType.STRONG_SELL if sell_votes == total else SignalType.SELL

            return Signal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=min(0.95, avg_confidence * 1.2),
                price=current_price,
                strategy=self.name,
                reason=f"{sell_votes}/{total} strategies agree: " + "; ".join(reasons[:2])
            )

        return Signal(
            symbol=symbol,
            signal_type=SignalType.HOLD,
            confidence=0.4,
            price=current_price,
            strategy=self.name,
            reason="No consensus among strategies"
        )
