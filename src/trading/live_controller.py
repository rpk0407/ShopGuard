"""
Live Trading Controller

Connects the specialized AI models to real brokers for automated trading.
Supports both paper trading (demo) and live trading.

Features:
- Real-time market data processing
- AI signal generation
- Automated order execution
- Position management
- Risk controls
- Performance tracking
"""

import threading
import time
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

from .broker_adapters import (
    BrokerAdapter, BrokerFactory, MultiBrokerManager,
    OrderSide, OrderType, OrderStatus, Order, Position, Quote, AccountInfo
)


class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"
    PAUSED = "paused"
    STOPPED = "stopped"


class SignalAction(Enum):
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class TradingSignal:
    symbol: str
    action: SignalAction
    strength: float  # 0 to 1
    confidence: float  # 0 to 1
    source: str  # Which model generated it
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeExecution:
    signal: TradingSignal
    order: Order
    entry_price: float
    position_size: float
    risk_amount: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RiskParameters:
    max_position_size: float = 0.1  # 10% of portfolio per position
    max_daily_loss: float = 0.02  # 2% max daily loss
    max_drawdown: float = 0.1  # 10% max drawdown
    max_open_positions: int = 10
    min_confidence: float = 0.6  # Minimum signal confidence
    stop_loss_pct: float = 0.02  # 2% default stop loss
    take_profit_pct: float = 0.04  # 4% default take profit
    max_correlation: float = 0.7  # Max correlation between positions
    cool_down_minutes: int = 5  # Minutes between trades on same symbol


class RiskManager:
    """Manages trading risk and position sizing"""

    def __init__(self, params: RiskParameters = None):
        self.params = params or RiskParameters()
        self.daily_pnl = 0.0
        self.peak_equity = 0.0
        self.current_drawdown = 0.0
        self.last_trade_time: Dict[str, datetime] = {}
        self.trade_count_today = 0
        self.losses_today = 0

    def check_signal(self, signal: TradingSignal, account: AccountInfo) -> tuple[bool, str]:
        """Check if a signal passes risk checks"""

        # Confidence check
        if signal.confidence < self.params.min_confidence:
            return False, f"Confidence {signal.confidence:.0%} < {self.params.min_confidence:.0%}"

        # Daily loss check
        if self.daily_pnl < -self.params.max_daily_loss * account.equity:
            return False, "Daily loss limit reached"

        # Drawdown check
        if self.current_drawdown > self.params.max_drawdown:
            return False, "Max drawdown reached"

        # Position count check
        if len(account.positions) >= self.params.max_open_positions:
            if signal.action in [SignalAction.BUY, SignalAction.STRONG_BUY]:
                return False, "Max positions reached"

        # Cool down check
        if signal.symbol in self.last_trade_time:
            time_since = (datetime.now() - self.last_trade_time[signal.symbol]).seconds / 60
            if time_since < self.params.cool_down_minutes:
                return False, f"Cool down: {self.params.cool_down_minutes - time_since:.1f}min left"

        return True, "OK"

    def calculate_position_size(self, signal: TradingSignal, account: AccountInfo,
                                current_price: float) -> float:
        """Calculate appropriate position size"""
        max_position_value = account.equity * self.params.max_position_size

        # Adjust by signal strength
        adjusted_value = max_position_value * signal.strength * signal.confidence

        # Calculate shares/units
        position_size = adjusted_value / current_price

        return position_size

    def calculate_stop_loss(self, signal: TradingSignal, entry_price: float) -> float:
        """Calculate stop loss price"""
        if signal.stop_loss:
            return signal.stop_loss

        if signal.action in [SignalAction.BUY, SignalAction.STRONG_BUY]:
            return entry_price * (1 - self.params.stop_loss_pct)
        else:
            return entry_price * (1 + self.params.stop_loss_pct)

    def calculate_take_profit(self, signal: TradingSignal, entry_price: float) -> float:
        """Calculate take profit price"""
        if signal.take_profit:
            return signal.take_profit

        if signal.target_price:
            return signal.target_price

        if signal.action in [SignalAction.BUY, SignalAction.STRONG_BUY]:
            return entry_price * (1 + self.params.take_profit_pct)
        else:
            return entry_price * (1 - self.params.take_profit_pct)

    def update_stats(self, pnl: float, equity: float):
        """Update daily stats"""
        self.daily_pnl += pnl

        if equity > self.peak_equity:
            self.peak_equity = equity

        self.current_drawdown = (self.peak_equity - equity) / self.peak_equity

    def record_trade(self, symbol: str):
        """Record trade for cool down"""
        self.last_trade_time[symbol] = datetime.now()
        self.trade_count_today += 1

    def reset_daily(self):
        """Reset daily stats"""
        self.daily_pnl = 0.0
        self.trade_count_today = 0
        self.losses_today = 0


class MarketDataManager:
    """Manages real-time and historical market data"""

    def __init__(self, broker: BrokerAdapter):
        self.broker = broker
        self.quotes: Dict[str, Quote] = {}
        self.bars: Dict[str, List[Dict]] = {}
        self.subscribers: Dict[str, List[Callable]] = {}
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def subscribe(self, symbol: str, callback: Callable):
        """Subscribe to real-time quotes"""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = []
        self.subscribers[symbol].append(callback)

    def get_quote(self, symbol: str) -> Quote:
        """Get latest quote"""
        if symbol not in self.quotes:
            self.quotes[symbol] = self.broker.get_quote(symbol)
        return self.quotes[symbol]

    def get_price(self, symbol: str) -> float:
        """Get current price"""
        return self.get_quote(symbol).last

    def get_ohlcv(self, symbol: str, periods: int = 100) -> np.ndarray:
        """Get OHLCV data for a symbol"""
        if symbol not in self.bars or len(self.bars[symbol]) < periods:
            end = datetime.now()
            start = end - timedelta(days=7)
            self.bars[symbol] = self.broker.get_historical_bars(symbol, '1h', start, end)

        bars = self.bars[symbol][-periods:]

        if not bars:
            # Return simulated data if no real data
            return np.random.randn(periods, 5) * 0.01 + 100

        ohlcv = np.array([
            [float(b.get('o', b.get('open', 0))),
             float(b.get('h', b.get('high', 0))),
             float(b.get('l', b.get('low', 0))),
             float(b.get('c', b.get('close', 0))),
             float(b.get('v', b.get('volume', 0)))]
            for b in bars
        ])

        return ohlcv

    def start_streaming(self):
        """Start streaming quotes"""
        self.running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()

    def stop_streaming(self):
        """Stop streaming"""
        self.running = False

    def _stream_loop(self):
        """Background thread for quote updates"""
        while self.running:
            for symbol in list(self.subscribers.keys()):
                try:
                    quote = self.broker.get_quote(symbol)
                    self.quotes[symbol] = quote

                    for callback in self.subscribers.get(symbol, []):
                        callback(quote)
                except Exception as e:
                    print(f"[DATA] Error fetching {symbol}: {e}")

            time.sleep(1)  # Update every second


class LiveTradingController:
    """
    Main controller for live/paper trading.
    Connects AI models to real execution.
    """

    def __init__(self, broker: BrokerAdapter = None, risk_params: RiskParameters = None):
        self.broker = broker or BrokerFactory.create('paper', initial_capital=100000)
        self.risk_manager = RiskManager(risk_params)
        self.data_manager = MarketDataManager(self.broker)

        self.mode = TradingMode.STOPPED
        self.watchlist: List[str] = []
        self.signals_queue = queue.Queue()
        self.executions: List[TradeExecution] = []

        # AI Models (to be set)
        self.ensemble = None
        self.pattern_system = None
        self.regime_classifier = None
        self.sentiment_model = None

        # Threading
        self._running = False
        self._main_thread: Optional[threading.Thread] = None
        self._signal_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_signal: Optional[Callable] = None
        self.on_trade: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # Performance tracking
        self.start_equity = 0.0
        self.trade_history: List[Dict] = []

    def set_ai_models(self, ensemble=None, pattern_system=None,
                      regime_classifier=None, sentiment_model=None):
        """Set AI models for signal generation"""
        self.ensemble = ensemble
        self.pattern_system = pattern_system
        self.regime_classifier = regime_classifier
        self.sentiment_model = sentiment_model

    def add_to_watchlist(self, symbols: List[str]):
        """Add symbols to watchlist"""
        for symbol in symbols:
            if symbol not in self.watchlist:
                self.watchlist.append(symbol)
                self.data_manager.subscribe(symbol, self._on_quote_update)

    def start(self, mode: TradingMode = TradingMode.PAPER):
        """Start the trading controller"""
        if self._running:
            print("[CONTROLLER] Already running")
            return

        print(f"[CONTROLLER] Starting in {mode.value} mode...")

        # Connect to broker
        if not self.broker.connect():
            raise Exception("Failed to connect to broker")

        # Get initial account state
        account = self.broker.get_account()
        self.start_equity = account.equity
        self.risk_manager.peak_equity = account.equity

        print(f"[CONTROLLER] Account equity: ${account.equity:,.2f}")
        print(f"[CONTROLLER] Paper mode: {account.is_paper}")

        self.mode = mode
        self._running = True

        # Start data streaming
        self.data_manager.start_streaming()

        # Start main loop
        self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self._main_thread.start()

        # Start signal processing
        self._signal_thread = threading.Thread(target=self._signal_loop, daemon=True)
        self._signal_thread.start()

        print(f"[CONTROLLER] Running with {len(self.watchlist)} symbols")

    def stop(self):
        """Stop the trading controller"""
        print("[CONTROLLER] Stopping...")
        self._running = False
        self.mode = TradingMode.STOPPED

        self.data_manager.stop_streaming()
        self.broker.disconnect()

        # Wait for threads
        if self._main_thread:
            self._main_thread.join(timeout=5)
        if self._signal_thread:
            self._signal_thread.join(timeout=5)

        print("[CONTROLLER] Stopped")

    def pause(self):
        """Pause trading (still monitor, no execution)"""
        self.mode = TradingMode.PAUSED
        print("[CONTROLLER] Paused")

    def resume(self):
        """Resume trading"""
        if self.mode == TradingMode.PAUSED:
            self.mode = TradingMode.PAPER if self.broker.paper else TradingMode.LIVE
            print(f"[CONTROLLER] Resumed in {self.mode.value} mode")

    def _main_loop(self):
        """Main trading loop"""
        last_analysis = {}

        while self._running:
            try:
                if self.mode == TradingMode.STOPPED:
                    break

                # Analyze each symbol
                for symbol in self.watchlist:
                    # Don't analyze too frequently
                    if symbol in last_analysis:
                        if (datetime.now() - last_analysis[symbol]).seconds < 60:
                            continue

                    signal = self._analyze_symbol(symbol)
                    if signal:
                        self.signals_queue.put(signal)
                        if self.on_signal:
                            self.on_signal(signal)

                    last_analysis[symbol] = datetime.now()

                # Check existing positions
                self._check_positions()

                time.sleep(5)  # Main loop interval

            except Exception as e:
                print(f"[CONTROLLER] Error in main loop: {e}")
                if self.on_error:
                    self.on_error(e)

    def _analyze_symbol(self, symbol: str) -> Optional[TradingSignal]:
        """Analyze a symbol and generate signal"""
        try:
            # Get market data
            price = self.data_manager.get_price(symbol)
            ohlcv = self.data_manager.get_ohlcv(symbol)

            if len(ohlcv) < 20:
                return None

            prices = ohlcv[:, 3]  # Close prices

            # Use ensemble if available
            if self.ensemble:
                market_data = {'prices': prices, 'ohlcv': ohlcv}
                prediction = self.ensemble.get_prediction(market_data)

                action = SignalAction(prediction.final_signal.value)
                return TradingSignal(
                    symbol=symbol,
                    action=action,
                    strength=prediction.signal_strength,
                    confidence=prediction.confidence,
                    source="ensemble",
                    target_price=prediction.target_price,
                    metadata={'reasoning': prediction.reasoning}
                )

            # Fallback to individual models
            signals = []

            # Pattern recognition
            if self.pattern_system:
                result = self.pattern_system.analyze(ohlcv)
                if result['patterns']:
                    direction = result['direction']
                    if direction == 'bullish':
                        signals.append((1, result['confidence']))
                    elif direction == 'bearish':
                        signals.append((-1, result['confidence']))

            # Regime classification
            if self.regime_classifier:
                regime = self.regime_classifier.classify(prices)
                bias = self.regime_classifier.get_trading_bias()
                if bias['bias'] == 'long':
                    signals.append((1, regime.confidence))
                elif bias['bias'] == 'short':
                    signals.append((-1, regime.confidence))

            if not signals:
                return None

            # Aggregate signals
            total_weight = sum(s[1] for s in signals)
            weighted_signal = sum(s[0] * s[1] for s in signals) / total_weight
            avg_confidence = total_weight / len(signals)

            # Determine action
            if weighted_signal > 0.5:
                action = SignalAction.STRONG_BUY if weighted_signal > 0.8 else SignalAction.BUY
            elif weighted_signal < -0.5:
                action = SignalAction.STRONG_SELL if weighted_signal < -0.8 else SignalAction.SELL
            else:
                action = SignalAction.HOLD

            if action == SignalAction.HOLD:
                return None

            return TradingSignal(
                symbol=symbol,
                action=action,
                strength=abs(weighted_signal),
                confidence=avg_confidence,
                source="models"
            )

        except Exception as e:
            print(f"[CONTROLLER] Error analyzing {symbol}: {e}")
            return None

    def _signal_loop(self):
        """Process trading signals"""
        while self._running:
            try:
                signal = self.signals_queue.get(timeout=1)
                self._process_signal(signal)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[CONTROLLER] Error processing signal: {e}")

    def _process_signal(self, signal: TradingSignal):
        """Process a trading signal"""
        if self.mode == TradingMode.PAUSED:
            print(f"[SIGNAL] {signal.symbol} {signal.action.name} (paused)")
            return

        if self.mode == TradingMode.STOPPED:
            return

        # Get account info
        account = self.broker.get_account()

        # Risk check
        passed, reason = self.risk_manager.check_signal(signal, account)
        if not passed:
            print(f"[SIGNAL] {signal.symbol} rejected: {reason}")
            return

        # Get current price
        price = self.data_manager.get_price(signal.symbol)

        # Calculate position size
        position_size = self.risk_manager.calculate_position_size(signal, account, price)

        if position_size <= 0:
            return

        # Determine order side
        if signal.action in [SignalAction.BUY, SignalAction.STRONG_BUY]:
            side = OrderSide.BUY
        else:
            side = OrderSide.SELL

            # Check if we have position to sell
            position = self.broker.get_position(signal.symbol)
            if not position:
                return
            position_size = min(position_size, position.quantity)

        # Submit order
        print(f"[TRADE] {side.value.upper()} {position_size:.4f} {signal.symbol} @ ${price:.2f}")

        try:
            order = self.broker.submit_order(
                symbol=signal.symbol,
                side=side,
                quantity=position_size,
                order_type=OrderType.MARKET
            )

            execution = TradeExecution(
                signal=signal,
                order=order,
                entry_price=price,
                position_size=position_size,
                risk_amount=position_size * price * self.risk_manager.params.stop_loss_pct
            )

            self.executions.append(execution)
            self.risk_manager.record_trade(signal.symbol)

            if self.on_trade:
                self.on_trade(execution)

            # Record trade
            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': signal.symbol,
                'side': side.value,
                'quantity': position_size,
                'price': price,
                'signal': signal.action.name,
                'confidence': signal.confidence
            })

        except Exception as e:
            print(f"[TRADE] Error: {e}")
            if self.on_error:
                self.on_error(e)

    def _check_positions(self):
        """Check and manage existing positions"""
        positions = self.broker.get_positions()

        for position in positions:
            try:
                # Check stop loss / take profit
                self._check_exit_conditions(position)
            except Exception as e:
                print(f"[POSITION] Error checking {position.symbol}: {e}")

    def _check_exit_conditions(self, position: Position):
        """Check if position should be closed"""
        # Find original execution
        original = None
        for exec in self.executions:
            if exec.signal.symbol == position.symbol:
                original = exec
                break

        if not original:
            return

        entry = original.entry_price
        current = position.current_price
        pnl_pct = (current - entry) / entry

        # Check stop loss
        if position.side == "long" and pnl_pct < -self.risk_manager.params.stop_loss_pct:
            print(f"[EXIT] {position.symbol} STOP LOSS at {pnl_pct:.1%}")
            self._close_position(position, "stop_loss")

        # Check take profit
        elif position.side == "long" and pnl_pct > self.risk_manager.params.take_profit_pct:
            print(f"[EXIT] {position.symbol} TAKE PROFIT at {pnl_pct:.1%}")
            self._close_position(position, "take_profit")

    def _close_position(self, position: Position, reason: str):
        """Close a position"""
        side = OrderSide.SELL if position.side == "long" else OrderSide.BUY

        order = self.broker.submit_order(
            symbol=position.symbol,
            side=side,
            quantity=position.quantity,
            order_type=OrderType.MARKET
        )

        print(f"[EXIT] Closed {position.symbol}: {reason}")

    def _on_quote_update(self, quote: Quote):
        """Handle quote updates"""
        # Update paper trading prices
        if hasattr(self.broker, 'set_price'):
            self.broker.set_price(quote.symbol, quote.last)

    def get_status(self) -> Dict[str, Any]:
        """Get controller status"""
        account = self.broker.get_account() if self.broker.connected else None

        return {
            'mode': self.mode.value,
            'running': self._running,
            'watchlist': self.watchlist,
            'positions': len(account.positions) if account else 0,
            'equity': account.equity if account else 0,
            'cash': account.cash if account else 0,
            'start_equity': self.start_equity,
            'return_pct': ((account.equity / self.start_equity - 1) * 100) if account and self.start_equity else 0,
            'trades_today': self.risk_manager.trade_count_today,
            'daily_pnl': self.risk_manager.daily_pnl,
            'drawdown': self.risk_manager.current_drawdown * 100,
            'signals_pending': self.signals_queue.qsize()
        }

    def get_positions(self) -> List[Position]:
        """Get current positions"""
        return self.broker.get_positions()

    def get_account(self) -> AccountInfo:
        """Get account info"""
        return self.broker.get_account()

    def manual_trade(self, symbol: str, side: str, quantity: float,
                     order_type: str = "market", price: Optional[float] = None) -> Order:
        """Execute a manual trade"""
        return self.broker.submit_order(
            symbol=symbol,
            side=OrderSide(side),
            quantity=quantity,
            order_type=OrderType(order_type),
            price=price
        )

    def close_all_positions(self):
        """Emergency close all positions"""
        print("[CONTROLLER] CLOSING ALL POSITIONS")
        positions = self.broker.get_positions()

        for position in positions:
            self._close_position(position, "manual_close")

        print(f"[CONTROLLER] Closed {len(positions)} positions")
