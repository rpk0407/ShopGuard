"""
Main Trading Bot - Orchestrates everything
"""
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from .config import TradingConfig, STOCK_WATCHLIST, CRYPTO_WATCHLIST, CRYPTO_SYMBOLS
from .price_fetcher import PriceFetcher, PriceData
from .portfolio import Portfolio
from .strategies import Strategy, MomentumStrategy, RSIStrategy, MeanReversionStrategy, CombinedStrategy
from .signals import Signal, SignalType


@dataclass
class MarketOverview:
    """Market overview data"""
    stocks: Dict[str, PriceData]
    crypto: Dict[str, PriceData]
    signals: List[Signal]
    timestamp: datetime


class TradingBot:
    """Main trading bot"""

    def __init__(self, config: TradingConfig = None):
        self.config = config or TradingConfig()
        self.fetcher = PriceFetcher()
        self.portfolio = Portfolio(self.config.paper_capital)
        self.strategies: Dict[str, Strategy] = {
            "momentum": MomentumStrategy(),
            "rsi": RSIStrategy(),
            "mean_reversion": MeanReversionStrategy(),
            "combined": CombinedStrategy()
        }
        self.active_strategy = self.strategies.get(self.config.default_strategy, self.strategies["combined"])
        self.running = False
        self.last_signals: Dict[str, Signal] = {}

    def set_strategy(self, name: str):
        """Set active strategy"""
        if name in self.strategies:
            self.active_strategy = self.strategies[name]
            print(f"Strategy set to: {name}")
        else:
            print(f"Unknown strategy: {name}. Available: {list(self.strategies.keys())}")

    def get_market_overview(self) -> MarketOverview:
        """Get current market overview with prices and signals"""
        # Fetch real prices
        stocks = self.fetcher.get_stock_prices(STOCK_WATCHLIST)
        crypto = self.fetcher.get_crypto_prices(CRYPTO_WATCHLIST)

        # Generate signals
        signals = []
        all_assets = list(stocks.keys()) + [CRYPTO_SYMBOLS.get(c, c) for c in crypto.keys()]

        for symbol in stocks:
            signal = self._analyze_asset(symbol, stocks[symbol].price, is_crypto=False)
            if signal:
                signals.append(signal)
                self.last_signals[symbol] = signal

        for coin_id, price_data in crypto.items():
            symbol = CRYPTO_SYMBOLS.get(coin_id, price_data.symbol)
            signal = self._analyze_asset(coin_id, price_data.price, is_crypto=True)
            if signal:
                signal.symbol = symbol  # Use readable symbol
                signals.append(signal)
                self.last_signals[symbol] = signal

        # Sort signals by strength
        signals.sort(key=lambda s: (
            2 if s.signal_type == SignalType.STRONG_BUY else
            1 if s.signal_type == SignalType.BUY else
            -1 if s.signal_type == SignalType.SELL else
            -2 if s.signal_type == SignalType.STRONG_SELL else 0,
            s.confidence
        ), reverse=True)

        return MarketOverview(
            stocks=stocks,
            crypto={CRYPTO_SYMBOLS.get(k, v.symbol): v for k, v in crypto.items()},
            signals=signals,
            timestamp=datetime.now()
        )

    def _analyze_asset(self, identifier: str, current_price: float, is_crypto: bool = False) -> Optional[Signal]:
        """Analyze a single asset and generate signal"""
        try:
            if is_crypto:
                bars = self.fetcher.get_crypto_history(identifier, days=30)
            else:
                bars = self.fetcher.get_stock_history(identifier, days=30)

            if len(bars) < 10:
                return None

            return self.active_strategy.analyze(identifier, bars, current_price)
        except Exception as e:
            print(f"Error analyzing {identifier}: {e}")
            return None

    def execute_signal(self, signal: Signal, position_size: float = None) -> bool:
        """
        Execute a trading signal

        Args:
            signal: The signal to execute
            position_size: Dollar amount to trade (default: 10% of portfolio)

        Returns:
            True if trade executed
        """
        if position_size is None:
            position_size = self.portfolio.total_value * self.config.max_position_pct

        quantity = position_size / signal.price

        if signal.is_buy:
            return self.portfolio.buy(signal.symbol, quantity, signal.price)
        elif signal.is_sell and signal.symbol in self.portfolio.positions:
            return self.portfolio.sell(signal.symbol, -1, signal.price)  # Sell all

        return False

    def auto_trade(self, min_confidence: float = 0.7):
        """
        Automatically execute high-confidence signals

        Args:
            min_confidence: Minimum confidence to execute (0.0 - 1.0)
        """
        overview = self.get_market_overview()

        for signal in overview.signals:
            if signal.confidence < min_confidence:
                continue

            if signal.is_buy:
                # Check if we already have a position
                if signal.symbol in self.portfolio.positions:
                    print(f"Already have position in {signal.symbol}, skipping")
                    continue

                # Check risk limits
                position_value = self.portfolio.total_value * self.config.max_position_pct
                if position_value > self.portfolio.cash:
                    print(f"Insufficient cash for {signal.symbol}")
                    continue

                print(f"\n🎯 EXECUTING: {signal.signal_type.value} {signal.symbol}")
                print(f"   Reason: {signal.reason}")
                print(f"   Confidence: {signal.confidence:.0%}")
                self.execute_signal(signal)

            elif signal.is_sell:
                if signal.symbol in self.portfolio.positions:
                    print(f"\n🎯 EXECUTING: {signal.signal_type.value} {signal.symbol}")
                    print(f"   Reason: {signal.reason}")
                    self.execute_signal(signal)

    def run_once(self):
        """Run one trading cycle"""
        print("\n" + "=" * 60)
        print(f"🤖 TRADING BOT CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        overview = self.get_market_overview()

        # Print market summary
        print("\n📊 MARKET SUMMARY")
        print("-" * 40)

        print("\nStocks:")
        for symbol, price in list(overview.stocks.items())[:5]:
            arrow = "🟢" if price.change_24h > 0 else "🔴"
            print(f"  {arrow} {symbol}: ${price.price:,.2f} ({price.change_24h:+.2f}%)")

        print("\nCrypto:")
        for symbol, price in list(overview.crypto.items())[:5]:
            arrow = "🟢" if price.change_24h > 0 else "🔴"
            print(f"  {arrow} {symbol}: ${price.price:,.2f} ({price.change_24h:+.2f}%)")

        # Print signals
        print("\n📡 TRADING SIGNALS")
        print("-" * 40)

        buy_signals = [s for s in overview.signals if s.is_buy]
        sell_signals = [s for s in overview.signals if s.is_sell]

        if buy_signals:
            print("\n🟢 BUY SIGNALS:")
            for signal in buy_signals[:5]:
                print(f"  {signal.symbol}: {signal.signal_type.value} ({signal.confidence:.0%})")
                print(f"    → {signal.reason}")

        if sell_signals:
            print("\n🔴 SELL SIGNALS:")
            for signal in sell_signals[:5]:
                print(f"  {signal.symbol}: {signal.signal_type.value} ({signal.confidence:.0%})")
                print(f"    → {signal.reason}")

        # Print portfolio
        summary = self.portfolio.get_summary()
        print("\n💰 PORTFOLIO")
        print("-" * 40)
        print(f"  Cash: ${summary['cash']:,.2f}")
        print(f"  Positions: ${summary['positions_value']:,.2f}")
        print(f"  Total: ${summary['total_value']:,.2f}")
        pnl_emoji = "📈" if summary['total_pnl'] > 0 else "📉"
        print(f"  P&L: ${summary['total_pnl']:,.2f} ({summary['total_return_pct']:+.2f}%) {pnl_emoji}")

        if summary['positions']:
            print("\n  Open Positions:")
            for pos in summary['positions']:
                pos_emoji = "🟢" if pos['unrealized_pnl'] > 0 else "🔴"
                print(f"    {pos_emoji} {pos['symbol']}: {pos['quantity']:.4f} @ ${pos['entry_price']:.2f}")
                print(f"       Current: ${pos['current_price']:.2f} | P&L: ${pos['unrealized_pnl']:.2f}")

        return overview

    def run(self, interval_seconds: int = 60, auto_trade: bool = False):
        """
        Run the trading bot continuously

        Args:
            interval_seconds: Seconds between cycles
            auto_trade: Whether to automatically execute signals
        """
        self.running = True
        print(f"\n🚀 Starting trading bot (interval: {interval_seconds}s, auto_trade: {auto_trade})")
        print("Press Ctrl+C to stop\n")

        try:
            while self.running:
                self.run_once()

                if auto_trade:
                    self.auto_trade()

                print(f"\n⏰ Next cycle in {interval_seconds} seconds...")
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n\n🛑 Stopping trading bot...")
            self.running = False
            self.portfolio.save("portfolio_state.json")
            print("Portfolio saved. Goodbye!")

    def stop(self):
        """Stop the trading bot"""
        self.running = False


# Quick test
if __name__ == "__main__":
    bot = TradingBot()
    bot.run_once()
