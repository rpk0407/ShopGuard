"""
Auto Executor - Automatically executes trades based on AI decisions
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from .config import Config, TradingMode
from .brokers import Broker, PaperBroker, AlpacaBroker, OrderSide
from .brain import TradingBrain, TradingDecision, SignalStrength
from .news import NewsAnalyzer
from .sentiment import SocialSentiment


@dataclass
class TradeLog:
    """Log of executed trade"""
    symbol: str
    side: str
    quantity: float
    price: float
    stop_loss: float
    take_profit: float
    reason: str
    timestamp: datetime


class AutoExecutor:
    """
    Automatic trade executor
    Combines all signals and executes trades with proper risk management
    """

    def __init__(self, config: Config = None):
        self.config = config or Config()

        # Initialize broker
        if self.config.alpaca_api_key and self.config.mode == TradingMode.PAPER:
            self.broker = AlpacaBroker(
                api_key=self.config.alpaca_api_key,
                secret_key=self.config.alpaca_secret_key,
                paper=True
            )
        else:
            self.broker = PaperBroker(self.config.initial_capital)

        # Initialize analyzers
        self.brain = TradingBrain(
            technical_weight=self.config.technical_weight,
            news_weight=self.config.news_weight,
            social_weight=self.config.social_weight,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct
        )
        self.news = NewsAnalyzer()
        self.sentiment = SocialSentiment()

        # State
        self.running = False
        self.trade_log: List[TradeLog] = []
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_scan = None

    def connect(self) -> bool:
        """Connect to broker"""
        return self.broker.connect()

    def get_all_signals(self) -> Dict[str, TradingDecision]:
        """
        Analyze all assets and get trading signals
        """
        print(f"\n🔍 Scanning markets... ({datetime.now().strftime('%H:%M:%S')})")

        decisions = {}

        # Get news sentiment for all symbols
        all_symbols = self.config.stocks + ["BTC", "ETH"]
        print("   📰 Fetching news sentiment...")
        news_data = self.news.get_sentiment_summary(all_symbols[:5])

        # Get social sentiment
        print("   🐒 Analyzing social media...")
        social_data = self.sentiment.get_all_sentiment(all_symbols[:5])

        # Analyze each asset
        for symbol in self.config.stocks:
            news_score = news_data.get(symbol, {}).get("sentiment", 0)
            social_score = social_data.get(symbol, {}).get("sentiment", 0)

            decision = self.brain.analyze(
                symbol,
                news_sentiment=news_score,
                social_sentiment=social_score,
                is_crypto=False
            )
            decisions[symbol] = decision

            time.sleep(0.2)  # Rate limiting

        # Analyze crypto
        for crypto in ["BTC", "ETH"]:
            news_score = news_data.get(crypto, {}).get("sentiment", 0)
            social_score = social_data.get(crypto, {}).get("sentiment", 0)

            decision = self.brain.analyze(
                crypto,
                news_sentiment=news_score,
                social_sentiment=social_score,
                is_crypto=True
            )
            decisions[crypto] = decision

            time.sleep(0.2)

        self.last_scan = datetime.now()
        return decisions

    def execute_decision(self, decision: TradingDecision) -> bool:
        """
        Execute a trading decision
        """
        # Check if we should trade
        if decision.signal == SignalStrength.HOLD:
            return False

        if decision.confidence < self.config.min_confidence:
            return False

        # Get current positions
        positions = self.broker.get_positions()
        account = self.broker.get_account()

        # Check max positions
        if len(positions) >= self.config.max_open_positions:
            if decision.signal in [SignalStrength.BUY, SignalStrength.STRONG_BUY]:
                print(f"   ⚠️ Max positions reached ({self.config.max_open_positions})")
                return False

        # Check daily loss limit
        if self.daily_pnl < -self.config.initial_capital * self.config.max_daily_loss_pct:
            print(f"   🛑 Daily loss limit reached!")
            return False

        # Execute BUY signals
        if decision.signal in [SignalStrength.BUY, SignalStrength.STRONG_BUY]:
            if decision.symbol in positions:
                print(f"   Already in {decision.symbol}")
                return False

            # Calculate position size
            position_value = account.equity * decision.position_size_pct
            quantity = position_value / decision.price

            # For fractional shares/crypto
            if decision.symbol in ["BTC", "ETH"]:
                quantity = round(quantity, 6)
            else:
                quantity = int(quantity)

            if quantity <= 0:
                return False

            # Update broker price (for paper trading)
            if isinstance(self.broker, PaperBroker):
                self.broker.set_price(decision.symbol, decision.price)

            # Execute
            print(f"\n   🎯 {decision.signal.value} {decision.symbol}")
            print(f"      Price: ${decision.price:,.2f}")
            print(f"      Confidence: {decision.confidence:.0%}")
            print(f"      Reasons: {', '.join(decision.reasons[:2])}")

            order = self.broker.submit_order(
                decision.symbol,
                OrderSide.BUY,
                quantity,
                stop_loss=decision.stop_loss,
                take_profit=decision.take_profit
            )

            if order and order.status.value == "filled":
                self.trade_log.append(TradeLog(
                    symbol=decision.symbol,
                    side="BUY",
                    quantity=quantity,
                    price=decision.price,
                    stop_loss=decision.stop_loss,
                    take_profit=decision.take_profit,
                    reason=decision.reasons[0] if decision.reasons else "",
                    timestamp=datetime.now()
                ))
                self.daily_trades += 1
                return True

        # Execute SELL signals
        elif decision.signal in [SignalStrength.SELL, SignalStrength.STRONG_SELL]:
            if decision.symbol not in positions:
                return False

            if isinstance(self.broker, PaperBroker):
                self.broker.set_price(decision.symbol, decision.price)

            print(f"\n   🔴 {decision.signal.value} {decision.symbol}")
            order = self.broker.close_position(decision.symbol)

            if order:
                self.daily_trades += 1
                return True

        return False

    def check_positions(self):
        """Check all positions for SL/TP"""
        positions = self.broker.get_positions()

        for symbol, position in positions.items():
            # Get current price
            is_crypto = symbol in ["BTC", "ETH"]
            current_price = self.brain.get_price(symbol, is_crypto)

            if isinstance(self.broker, PaperBroker):
                self.broker.set_price(symbol, current_price)

        # Paper broker checks stops internally
        if isinstance(self.broker, PaperBroker):
            self.broker.check_stops()

    def run_cycle(self, auto_execute: bool = True) -> Dict[str, TradingDecision]:
        """
        Run one complete trading cycle
        """
        # Check existing positions first
        self.check_positions()

        # Get all signals
        decisions = self.get_all_signals()

        # Print summary
        self._print_summary(decisions)

        # Auto execute if enabled
        if auto_execute:
            for symbol, decision in decisions.items():
                self.execute_decision(decision)

        return decisions

    def _print_summary(self, decisions: Dict[str, TradingDecision]):
        """Print trading summary"""
        print("\n" + "=" * 60)
        print(f"📊 MARKET ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        # Signals
        buy_signals = [d for d in decisions.values() if d.signal in [SignalStrength.BUY, SignalStrength.STRONG_BUY]]
        sell_signals = [d for d in decisions.values() if d.signal in [SignalStrength.SELL, SignalStrength.STRONG_SELL]]

        if buy_signals:
            print("\n🟢 BUY SIGNALS:")
            for d in sorted(buy_signals, key=lambda x: x.confidence, reverse=True)[:5]:
                print(f"   {d.symbol}: {d.signal.value} ({d.confidence:.0%})")
                print(f"      Tech: {d.technical_score:.2f} | News: {d.news_score:.2f} | Social: {d.social_score:.2f}")
                print(f"      {d.reasons[0] if d.reasons else ''}")

        if sell_signals:
            print("\n🔴 SELL SIGNALS:")
            for d in sorted(sell_signals, key=lambda x: x.confidence, reverse=True)[:5]:
                print(f"   {d.symbol}: {d.signal.value} ({d.confidence:.0%})")

        # Portfolio
        account = self.broker.get_account()
        positions = self.broker.get_positions()

        print("\n💰 PORTFOLIO:")
        print(f"   Cash: ${account.cash:,.2f}")
        print(f"   Equity: ${account.equity:,.2f}")

        if positions:
            print(f"   Positions: {len(positions)}")
            for symbol, pos in positions.items():
                emoji = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
                print(f"      {emoji} {symbol}: {pos.quantity:.4f} @ ${pos.entry_price:.2f}")
                print(f"         Current: ${pos.current_price:.2f} | P&L: ${pos.unrealized_pnl:.2f} ({pos.unrealized_pnl_pct:.1f}%)")

        print(f"\n   Daily Trades: {self.daily_trades}")

    def run(self, auto_execute: bool = True):
        """
        Run continuously
        """
        self.running = True
        interval = self.config.scan_interval_minutes * 60

        print(f"\n🚀 AUTO TRADER STARTED")
        print(f"   Mode: {self.config.mode.value.upper()}")
        print(f"   Scan Interval: {self.config.scan_interval_minutes} min")
        print(f"   Auto Execute: {auto_execute}")
        print(f"   Min Confidence: {self.config.min_confidence:.0%}")
        print("\n   Press Ctrl+C to stop\n")

        try:
            while self.running:
                self.run_cycle(auto_execute)
                print(f"\n⏰ Next scan in {self.config.scan_interval_minutes} minutes...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping auto trader...")
            self.running = False
            if isinstance(self.broker, PaperBroker):
                self.broker._save()
            print("State saved. Goodbye!")

    def stop(self):
        """Stop the executor"""
        self.running = False
