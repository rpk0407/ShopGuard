"""
Unified AI Trading System

Combines all specialized AI models with live trading:
- Pattern Recognition
- Regime Classification
- Financial NLP
- Reinforcement Learning
- Deep Learning
- Self-Learning
- Ensemble Prediction

Plus execution via:
- Paper Trading (Demo)
- Alpaca (Stocks/Crypto)
- Binance (Crypto)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import Dict, List, Optional, Any
from datetime import datetime
import threading
import time
import json

# Trading infrastructure
from trading import (
    LiveTradingController, TradingMode, RiskParameters,
    BrokerFactory, BrokerAdapter
)

# AI Models
from ai_models import (
    # Ensemble
    TradingEnsemble,
    # Pattern Recognition
    PatternRecognitionSystem,
    # Regime Classification
    MarketRegimeClassifier,
    # NLP
    FinancialSentimentModel, CryptoSentimentModel,
    # Self-Learning
    SelfLearningSystem, LearningMode
)


class AITradingConfig:
    """Configuration for AI Trading System"""

    def __init__(self):
        # Trading mode
        self.mode = "paper"  # "paper", "live"
        self.broker = "paper"  # "paper", "alpaca", "binance"

        # API Keys (load from environment)
        self.alpaca_key = os.environ.get("ALPACA_API_KEY", "")
        self.alpaca_secret = os.environ.get("ALPACA_SECRET_KEY", "")
        self.binance_key = os.environ.get("BINANCE_API_KEY", "")
        self.binance_secret = os.environ.get("BINANCE_SECRET_KEY", "")

        # Paper trading
        self.initial_capital = 100000.0

        # Watchlist
        self.watchlist_stocks = ["AAPL", "GOOGL", "MSFT", "NVDA", "TSLA", "AMZN", "META"]
        self.watchlist_crypto = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

        # Risk parameters
        self.risk = RiskParameters(
            max_position_size=0.1,      # 10% per position
            max_daily_loss=0.02,        # 2% daily loss limit
            max_drawdown=0.1,           # 10% max drawdown
            max_open_positions=10,
            min_confidence=0.6,         # 60% min confidence
            stop_loss_pct=0.02,         # 2% stop loss
            take_profit_pct=0.04,       # 4% take profit
            cool_down_minutes=5
        )

        # AI settings
        self.use_pattern_recognition = True
        self.use_regime_classification = True
        self.use_sentiment_analysis = True
        self.use_self_learning = True
        self.use_ensemble = True

        # Intervals
        self.analysis_interval = 60     # Analyze every 60 seconds
        self.learning_interval = 300    # Learn every 5 minutes

    def to_dict(self) -> Dict:
        return {
            'mode': self.mode,
            'broker': self.broker,
            'initial_capital': self.initial_capital,
            'watchlist_stocks': self.watchlist_stocks,
            'watchlist_crypto': self.watchlist_crypto,
            'risk': {
                'max_position_size': self.risk.max_position_size,
                'max_daily_loss': self.risk.max_daily_loss,
                'max_drawdown': self.risk.max_drawdown,
                'stop_loss_pct': self.risk.stop_loss_pct,
                'take_profit_pct': self.risk.take_profit_pct
            }
        }

    @classmethod
    def from_file(cls, path: str) -> 'AITradingConfig':
        """Load config from JSON file"""
        config = cls()
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)

            config.mode = data.get('mode', config.mode)
            config.broker = data.get('broker', config.broker)
            config.initial_capital = data.get('initial_capital', config.initial_capital)
            config.watchlist_stocks = data.get('watchlist_stocks', config.watchlist_stocks)
            config.watchlist_crypto = data.get('watchlist_crypto', config.watchlist_crypto)

            if 'risk' in data:
                config.risk.max_position_size = data['risk'].get('max_position_size', 0.1)
                config.risk.max_daily_loss = data['risk'].get('max_daily_loss', 0.02)
                config.risk.stop_loss_pct = data['risk'].get('stop_loss_pct', 0.02)

        return config

    def save(self, path: str):
        """Save config to file"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class AITradingSystem:
    """
    Complete AI Trading System

    Integrates all AI models with live/paper trading execution.
    """

    def __init__(self, config: AITradingConfig = None):
        self.config = config or AITradingConfig()
        self.running = False

        # Initialize components
        self._init_broker()
        self._init_ai_models()
        self._init_controller()

        # Status
        self.start_time: Optional[datetime] = None
        self.trades_executed = 0
        self.signals_generated = 0

    def _init_broker(self):
        """Initialize broker adapter"""
        print(f"[AI-TRADER] Initializing {self.config.broker} broker...")

        if self.config.broker == "paper":
            self.broker = BrokerFactory.create(
                'paper',
                initial_capital=self.config.initial_capital
            )
        elif self.config.broker == "alpaca":
            self.broker = BrokerFactory.create(
                'alpaca',
                api_key=self.config.alpaca_key,
                api_secret=self.config.alpaca_secret,
                paper=(self.config.mode == "paper")
            )
        elif self.config.broker == "binance":
            self.broker = BrokerFactory.create(
                'binance',
                api_key=self.config.binance_key,
                api_secret=self.config.binance_secret,
                paper=(self.config.mode == "paper")
            )
        else:
            raise ValueError(f"Unknown broker: {self.config.broker}")

    def _init_ai_models(self):
        """Initialize AI models"""
        print("[AI-TRADER] Initializing AI models...")

        # Pattern Recognition
        if self.config.use_pattern_recognition:
            self.pattern_system = PatternRecognitionSystem()
            print("   [X] Pattern Recognition")
        else:
            self.pattern_system = None

        # Regime Classifier
        if self.config.use_regime_classification:
            self.regime_classifier = MarketRegimeClassifier()
            print("   [X] Regime Classification")
        else:
            self.regime_classifier = None

        # Sentiment Analysis
        if self.config.use_sentiment_analysis:
            self.sentiment_model = FinancialSentimentModel()
            self.crypto_sentiment = CryptoSentimentModel()
            print("   [X] Sentiment Analysis")
        else:
            self.sentiment_model = None
            self.crypto_sentiment = None

        # Self-Learning
        if self.config.use_self_learning:
            self.learner = SelfLearningSystem(input_size=20, output_size=1)
            self.learner.mode = LearningMode.HYBRID
            print("   [X] Self-Learning System")
        else:
            self.learner = None

        # Ensemble
        if self.config.use_ensemble:
            self.ensemble = TradingEnsemble()
            self.ensemble.set_model('pattern_recognition', self.pattern_system)
            self.ensemble.set_model('regime_classifier', self.regime_classifier)
            print("   [X] Ensemble System")
        else:
            self.ensemble = None

    def _init_controller(self):
        """Initialize trading controller"""
        print("[AI-TRADER] Initializing trading controller...")

        self.controller = LiveTradingController(
            broker=self.broker,
            risk_params=self.config.risk
        )

        # Set AI models
        self.controller.set_ai_models(
            ensemble=self.ensemble,
            pattern_system=self.pattern_system,
            regime_classifier=self.regime_classifier,
            sentiment_model=self.sentiment_model
        )

        # Callbacks
        self.controller.on_signal = self._on_signal
        self.controller.on_trade = self._on_trade
        self.controller.on_error = self._on_error

    def _on_signal(self, signal):
        """Handle new signal"""
        self.signals_generated += 1
        print(f"[SIGNAL] {signal.symbol}: {signal.action.name} "
              f"(confidence: {signal.confidence:.0%})")

    def _on_trade(self, execution):
        """Handle trade execution"""
        self.trades_executed += 1
        print(f"[TRADE] {execution.order.side.value.upper()} "
              f"{execution.position_size:.4f} {execution.signal.symbol} "
              f"@ ${execution.entry_price:.2f}")

    def _on_error(self, error):
        """Handle errors"""
        print(f"[ERROR] {error}")

    def start(self):
        """Start the AI trading system"""
        if self.running:
            print("[AI-TRADER] Already running")
            return

        print("\n" + "=" * 60)
        print("          AI TRADING SYSTEM - STARTING")
        print("=" * 60)

        self.running = True
        self.start_time = datetime.now()

        # Add watchlist
        if self.config.broker in ["paper", "alpaca"]:
            self.controller.add_to_watchlist(self.config.watchlist_stocks)
        if self.config.broker in ["paper", "binance"]:
            self.controller.add_to_watchlist(self.config.watchlist_crypto)

        # Start controller
        mode = TradingMode.PAPER if self.config.mode == "paper" else TradingMode.LIVE
        self.controller.start(mode)

        print(f"\n[AI-TRADER] Running in {mode.value.upper()} mode")
        print(f"[AI-TRADER] Watchlist: {len(self.controller.watchlist)} symbols")
        print(f"[AI-TRADER] Press Ctrl+C to stop\n")

    def stop(self):
        """Stop the AI trading system"""
        if not self.running:
            return

        print("\n[AI-TRADER] Stopping...")
        self.running = False
        self.controller.stop()

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print trading session summary"""
        status = self.controller.get_status()
        duration = (datetime.now() - self.start_time).seconds if self.start_time else 0

        print("\n" + "=" * 60)
        print("          AI TRADING SYSTEM - SESSION SUMMARY")
        print("=" * 60)
        print(f"   Duration: {duration // 60} minutes {duration % 60} seconds")
        print(f"   Signals Generated: {self.signals_generated}")
        print(f"   Trades Executed: {self.trades_executed}")
        print(f"   Starting Equity: ${status['start_equity']:,.2f}")
        print(f"   Current Equity: ${status['equity']:,.2f}")
        print(f"   Return: {status['return_pct']:.2f}%")
        print(f"   Daily P&L: ${status['daily_pnl']:,.2f}")
        print(f"   Max Drawdown: {status['drawdown']:.2f}%")
        print("=" * 60 + "\n")

    def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        controller_status = self.controller.get_status()

        return {
            'running': self.running,
            'mode': self.config.mode,
            'broker': self.config.broker,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            **controller_status,
            'models': {
                'pattern_recognition': self.pattern_system is not None,
                'regime_classifier': self.regime_classifier is not None,
                'sentiment_analysis': self.sentiment_model is not None,
                'self_learning': self.learner is not None,
                'ensemble': self.ensemble is not None
            }
        }

    def get_positions(self):
        """Get current positions"""
        return self.controller.get_positions()

    def get_account(self):
        """Get account info"""
        return self.controller.get_account()

    def manual_trade(self, symbol: str, side: str, quantity: float):
        """Execute manual trade"""
        return self.controller.manual_trade(symbol, side, quantity)

    def close_all(self):
        """Emergency close all positions"""
        self.controller.close_all_positions()

    def pause(self):
        """Pause trading"""
        self.controller.pause()

    def resume(self):
        """Resume trading"""
        self.controller.resume()


def run_ai_trader(mode: str = "paper", broker: str = "paper",
                  capital: float = 100000, symbols: List[str] = None):
    """
    Convenience function to run the AI trader.

    Args:
        mode: "paper" or "live"
        broker: "paper", "alpaca", or "binance"
        capital: Initial capital for paper trading
        symbols: List of symbols to trade
    """
    config = AITradingConfig()
    config.mode = mode
    config.broker = broker
    config.initial_capital = capital

    if symbols:
        if broker == "binance":
            config.watchlist_crypto = symbols
        else:
            config.watchlist_stocks = symbols

    trader = AITradingSystem(config)

    try:
        trader.start()

        # Keep running until interrupted
        while trader.running:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[AI-TRADER] Interrupted by user")
    finally:
        trader.stop()

    return trader


if __name__ == "__main__":
    # Default: Run paper trading
    run_ai_trader(mode="paper", broker="paper", capital=100000)
