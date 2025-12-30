"""
TITAN ECOSYSTEM - Unified Trading Organism
============================================
The complete integrated system that combines all components
into a self-evolving, self-healing trading organism.

Data Flow:
    MATRIX → RECEPTORS → TITAN BRAIN → RISK MANAGER → EXECUTOR → JOURNAL
       ↑                      ↑              ↓
       └──────────────────────┴──── DARWIN (evolving) ────→ ALERTS

All components work together, communicating through the Alert System (Nervous System).
"""

import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

# Import all ecosystem components
from .titan_brain import TitanBrain, BrainConfig, TradingSignal, SignalType
from .risk_manager import RiskManager, RiskConfig, RiskState
from .executor import OrderExecutor, ExecutionConfig, Order, OrderSide, OrderType, OrderStatus
from .regime import RegimeDetector, RegimeState, MarketRegime, VolatilityState
from .journal import TradeJournal, TradeRecord, PerformanceMetrics
from .alerts import AlertSystem, Alert, AlertLevel, EventType, get_alert_system

logger = logging.getLogger(__name__)


class EcosystemState(Enum):
    """Ecosystem health states"""
    DORMANT = "dormant"       # Not started
    INITIALIZING = "init"    # Starting up
    HEALTHY = "healthy"       # All systems go
    DEGRADED = "degraded"     # Some issues
    CRITICAL = "critical"     # Major issues
    EVOLVING = "evolving"     # Darwin running
    SHUTDOWN = "shutdown"     # Shutting down


@dataclass
class EcosystemConfig:
    """Master configuration for the entire ecosystem"""
    # Capital
    initial_capital: float = 10000.0

    # Trading
    max_concurrent_positions: int = 3
    max_position_pct: float = 0.25  # Max 25% per position

    # Evolution
    enable_evolution: bool = True
    evolution_interval: int = 300  # Evolve every 5 minutes
    min_ticks_for_evolution: int = 100

    # Risk
    daily_loss_limit_pct: float = 0.05  # 5% daily max loss
    max_drawdown_pct: float = 0.15  # 15% max drawdown

    # System
    enable_paper_trading: bool = True
    log_level: str = "INFO"


@dataclass
class Position:
    """Active trading position"""
    position_id: str
    trade_id: str
    order_id: str
    asset: str
    side: str  # LONG or SHORT
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_time: float
    entry_signal: str
    entry_regime: str

    # Dynamic
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0


class TitanEcosystem:
    """
    THE TITAN ECOSYSTEM
    ===================
    A unified, self-evolving trading organism.

    Components (Biological Metaphor):
    - Nucleus (TitanBrain): Central decision-making
    - DNA (Darwin): Evolutionary optimization
    - Membrane (RiskManager): Protection layer
    - Mitochondria (Executor): Energy/Execution
    - Receptors (RegimeDetector): Market sensing
    - Memory (Journal): Trade history & learning
    - Nervous System (Alerts): Communication
    - Environment (Matrix): Simulation layer
    """

    def __init__(
        self,
        config: EcosystemConfig = None,
        brain_config: BrainConfig = None,
        risk_config: RiskConfig = None,
        execution_config: ExecutionConfig = None
    ):
        self.config = config or EcosystemConfig()

        # ===================================
        # INITIALIZE ALL ORGANS
        # ===================================

        # The Nervous System (Event Bus) - Initialize first
        self.alerts = get_alert_system()

        # The Nucleus (Decision Center)
        self.brain = TitanBrain(brain_config)

        # The Membrane (Protection)
        self.risk_manager = RiskManager(risk_config)

        # The Mitochondria (Execution)
        self.executor = OrderExecutor(execution_config)

        # The Receptors (Market Sensing)
        self.regime_detector = RegimeDetector()

        # The Memory (Trade History)
        self.journal = TradeJournal(initial_capital=self.config.initial_capital)

        # The DNA (Evolution) - Loaded on demand
        self.darwin = None
        self.matrix = None

        # ===================================
        # ECOSYSTEM STATE
        # ===================================

        self.state = EcosystemState.DORMANT
        self.positions: Dict[str, Position] = {}
        self.capital = self.config.initial_capital
        self.daily_pnl = 0.0
        self.daily_start_capital = self.config.initial_capital

        # Tick history for evolution
        self.tick_history: List[Dict] = []
        self.max_tick_history = 1000

        # Threading
        self._running = False
        self._lock = threading.RLock()
        self._evolution_thread = None

        # Wire up callbacks
        self._setup_callbacks()

        logger.info("🌍 TITAN ECOSYSTEM initialized")
        self.alerts.emit(
            EventType.SYSTEM_START,
            "Ecosystem Ready",
            "All organs initialized successfully",
            AlertLevel.INFO,
            source="Ecosystem"
        )

    def _setup_callbacks(self):
        """Wire up inter-component communication"""

        # Brain emits signals -> We handle execution
        def on_brain_signal(signal: TradingSignal):
            if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                self._handle_buy_signal(signal)
            elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL, SignalType.EXIT]:
                self._handle_sell_signal(signal)

        self.brain.on_signal = on_brain_signal

        # Executor emits fills -> We log to journal
        def on_fill(fill):
            logger.debug(f"🔧 Fill received: {fill.fill_id}")

        self.executor.on_fill = on_fill

        # Risk manager can trigger circuit breakers
        def on_risk_alert(message: str, level: AlertLevel):
            self.alerts.emit(
                EventType.DRAWDOWN_WARNING if 'drawdown' in message.lower() else EventType.CIRCUIT_BREAKER,
                "Risk Alert",
                message,
                level,
                source="RiskManager"
            )

        # Subscribe to key events
        self.alerts.subscribe(EventType.CIRCUIT_BREAKER, self._on_circuit_breaker)

    def _on_circuit_breaker(self, alert: Alert):
        """Handle circuit breaker events"""
        logger.warning(f"🚨 Circuit Breaker: {alert.message}")
        # Close all positions
        self._emergency_close_all()

    # =========================================
    # CORE PROCESSING LOOP
    # =========================================

    def process_tick(self, tick: Dict) -> Optional[TradingSignal]:
        """
        MAIN PROCESSING LOOP
        Process a market tick through all organs.

        Flow:
        1. Update regime detector
        2. Process through brain
        3. Check risk limits
        4. Execute if approved
        5. Update positions
        6. Log to journal
        """
        with self._lock:
            if self.state == EcosystemState.SHUTDOWN:
                return None

            asset = tick.get('asset', 'BTC/USDT')
            price = tick.get('price', 0)

            # Store tick for evolution
            self.tick_history.append(tick)
            if len(self.tick_history) > self.max_tick_history:
                self.tick_history.pop(0)

            # 1. UPDATE RECEPTORS (Regime Detection)
            regime_state = self.regime_detector.update(asset, price)
            tick['regime'] = regime_state.regime.value if regime_state else 'unknown'
            tick['volatility_state'] = regime_state.volatility_state.value if regime_state else 'normal'

            # 2. UPDATE EXECUTOR MARKET STATE
            volume = tick.get('volume', 1000000)
            self.executor.update_market(asset, price, volume)

            # 3. PROCESS THROUGH BRAIN (Decision)
            signal = self.brain.process_tick(tick)

            # 4. CHECK RISK LIMITS
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                signal.confidence *= 0.1  # Severely reduce confidence
                logger.debug(f"Trading restricted: {reason}")

            # 5. UPDATE OPEN POSITIONS
            self._update_positions(price)

            # 6. CHECK STOP LOSSES / TAKE PROFITS
            self._check_exit_conditions(asset, price)

            # 7. EMIT ALERT FOR SIGNIFICANT SIGNALS
            if signal.signal_type != SignalType.HOLD and signal.confidence > 0.6:
                self.alerts.signal_alert(
                    signal.signal_type.value,
                    asset,
                    signal.confidence,
                    price,
                    source="TitanBrain"
                )

            return signal

    def _handle_buy_signal(self, signal: TradingSignal):
        """Handle buy signal - check risk, execute, record"""
        with self._lock:
            # Check if we can open new positions
            if len(self.positions) >= self.config.max_concurrent_positions:
                logger.debug("Max positions reached, skipping signal")
                return

            # Check risk limits
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                logger.info(f"Trade blocked by risk manager: {reason}")
                return

            # Calculate position size
            available_capital = self.capital - sum(
                p.quantity * p.entry_price for p in self.positions.values()
            )
            max_position_value = self.capital * self.config.max_position_pct

            position_value = min(
                available_capital * signal.position_size,
                max_position_value
            )

            if position_value < 10:  # Minimum position value
                logger.debug("Position too small, skipping")
                return

            quantity = position_value / signal.price

            # Execute order
            if self.config.enable_paper_trading:
                order = self.executor.execute_signal(
                    asset=signal.asset,
                    side="BUY",
                    quantity=quantity,
                    signal_id=str(int(time.time()))
                )

                if order and order.status == OrderStatus.FILLED:
                    # Create position
                    position_id = f"pos_{order.order_id}"
                    trade_id = f"trade_{order.order_id}"

                    position = Position(
                        position_id=position_id,
                        trade_id=trade_id,
                        order_id=order.order_id,
                        asset=signal.asset,
                        side="LONG",
                        entry_price=order.average_fill_price,
                        quantity=order.filled_quantity,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        entry_time=time.time(),
                        entry_signal=signal.signal_type.value,
                        entry_regime=signal.market_phase,
                        current_price=order.average_fill_price,
                        highest_price=order.average_fill_price,
                        lowest_price=order.average_fill_price
                    )

                    self.positions[position_id] = position

                    # Log to journal
                    self.journal.open_trade(
                        trade_id=trade_id,
                        asset=signal.asset,
                        side="LONG",
                        entry_price=order.average_fill_price,
                        size=order.filled_quantity,
                        stop_loss=signal.stop_loss,
                        entry_signal=signal.signal_type.value,
                        entry_confidence=signal.confidence,
                        entry_regime=signal.market_phase,
                        pillars_aligned=sum([signal.bio_check, signal.physics_check, signal.micro_check, signal.cvd_check])
                    )

                    # Update risk manager
                    self.risk_manager.open_position(
                        signal.asset,
                        "LONG",
                        order.average_fill_price,
                        order.filled_quantity,
                        signal.stop_loss,
                        signal.take_profit
                    )

                    # Alert
                    self.alerts.trade_alert(
                        "OPENED",
                        signal.asset,
                        "LONG",
                        order.average_fill_price
                    )

                    logger.info(f"📈 Position opened: {position_id} - {order.filled_quantity:.4f} @ ${order.average_fill_price:.2f}")

    def _handle_sell_signal(self, signal: TradingSignal):
        """Handle sell/exit signal - close relevant positions"""
        with self._lock:
            # Find positions for this asset
            positions_to_close = [
                p for p in self.positions.values()
                if p.asset == signal.asset
            ]

            for position in positions_to_close:
                self._close_position(position, signal.price, "SIGNAL")

    def _update_positions(self, current_price: float):
        """Update all position metrics"""
        for position in self.positions.values():
            position.current_price = current_price

            # Track high/low
            position.highest_price = max(position.highest_price, current_price)
            position.lowest_price = min(position.lowest_price, current_price)

            # Calculate P&L
            if position.side == "LONG":
                position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * position.quantity

            position.unrealized_pnl_pct = position.unrealized_pnl / (position.entry_price * position.quantity)

    def _check_exit_conditions(self, asset: str, price: float):
        """Check stop loss and take profit for all positions"""
        positions_to_close = []

        for pos_id, position in self.positions.items():
            if position.asset != asset:
                continue

            exit_reason = None

            # Stop Loss
            if position.side == "LONG" and price <= position.stop_loss:
                exit_reason = "STOP_LOSS"
            elif position.side == "SHORT" and price >= position.stop_loss:
                exit_reason = "STOP_LOSS"

            # Take Profit
            if position.side == "LONG" and price >= position.take_profit:
                exit_reason = "TAKE_PROFIT"
            elif position.side == "SHORT" and price <= position.take_profit:
                exit_reason = "TAKE_PROFIT"

            if exit_reason:
                positions_to_close.append((position, price, exit_reason))

        for position, exit_price, reason in positions_to_close:
            self._close_position(position, exit_price, reason)

    def _close_position(self, position: Position, exit_price: float, reason: str):
        """Close a position and log to journal"""
        with self._lock:
            # Execute exit order
            exit_side = "SELL" if position.side == "LONG" else "BUY"

            order = self.executor.execute_signal(
                asset=position.asset,
                side=exit_side,
                quantity=position.quantity,
                signal_id=position.trade_id
            )

            if order and order.status == OrderStatus.FILLED:
                actual_exit_price = order.average_fill_price

                # Calculate P&L
                if position.side == "LONG":
                    pnl = (actual_exit_price - position.entry_price) * position.quantity
                else:
                    pnl = (position.entry_price - actual_exit_price) * position.quantity

                # Update capital
                self.capital += pnl
                self.daily_pnl += pnl

                # Close in journal
                self.journal.close_trade(
                    trade_id=position.trade_id,
                    exit_price=actual_exit_price,
                    exit_reason=reason,
                    exit_fee=order.total_fees
                )

                # Update risk manager
                self.risk_manager.close_position(
                    position.asset,
                    actual_exit_price,
                    pnl
                )

                # Alert
                self.alerts.trade_alert(
                    "CLOSED",
                    position.asset,
                    position.side,
                    actual_exit_price,
                    pnl=pnl
                )

                # Remove position
                if position.position_id in self.positions:
                    del self.positions[position.position_id]

                logger.info(f"📉 Position closed: {position.position_id} - P&L: ${pnl:.2f} ({reason})")

    def _emergency_close_all(self):
        """Emergency close all positions"""
        logger.warning("🚨 EMERGENCY CLOSE ALL POSITIONS")

        for position in list(self.positions.values()):
            self._close_position(position, position.current_price, "EMERGENCY")

    # =========================================
    # EVOLUTION INTEGRATION
    # =========================================

    def attach_darwin(self, darwin):
        """Attach Darwin evolution engine"""
        self.darwin = darwin

        # Wire up evolution callback
        def on_alpha_evolved(genome):
            self.brain.update_from_genome(genome)
            self.alerts.evolution_alert(
                darwin.generation,
                genome.fitness,
                alpha_updated=True
            )

        darwin.on_alpha_evolved = on_alpha_evolved
        logger.info("🧬 Darwin attached to ecosystem")

    def attach_matrix(self, matrix):
        """Attach Matrix simulation"""
        self.matrix = matrix
        logger.info("🔮 Matrix attached to ecosystem")

    def start_evolution(self):
        """Start background evolution"""
        if not self.darwin:
            try:
                from ..evolution.darwin import Darwin
                self.darwin = Darwin()
                self.attach_darwin(self.darwin)
            except ImportError:
                logger.warning("Darwin not available")
                return

        if self.matrix:
            self.darwin.start_evolution(self.matrix)
            self.state = EcosystemState.EVOLVING
            self.alerts.emit(
                EventType.GENERATION_COMPLETE,
                "Evolution Started",
                "Darwin evolution engine activated",
                AlertLevel.INFO,
                source="Darwin"
            )

    def stop_evolution(self):
        """Stop background evolution"""
        if self.darwin:
            self.darwin.stop_evolution()
            self.state = EcosystemState.HEALTHY

    def run_generation(self) -> Dict:
        """Run a single evolution generation"""
        if not self.darwin:
            return {'error': 'Darwin not attached'}

        if len(self.tick_history) < 50:
            return {'error': 'Not enough tick history for evolution'}

        # Run generation with stored ticks
        result = self.darwin.run_generation(self.tick_history)

        return result

    # =========================================
    # LIFECYCLE MANAGEMENT
    # =========================================

    def start(self):
        """Start the ecosystem"""
        with self._lock:
            if self.state != EcosystemState.DORMANT:
                return

            self.state = EcosystemState.INITIALIZING

            # Start alert system
            self.alerts.start()

            # Reset daily tracking
            self.daily_pnl = 0.0
            self.daily_start_capital = self.capital

            self._running = True
            self.state = EcosystemState.HEALTHY

            self.alerts.emit(
                EventType.SYSTEM_START,
                "Ecosystem Started",
                "TITAN ecosystem is now active",
                AlertLevel.INFO,
                source="Ecosystem"
            )

            logger.info("🌍 TITAN ECOSYSTEM started")

    def stop(self):
        """Stop the ecosystem gracefully"""
        with self._lock:
            self.state = EcosystemState.SHUTDOWN

            # Stop evolution
            self.stop_evolution()

            # Close all positions
            for position in list(self.positions.values()):
                self._close_position(position, position.current_price, "SHUTDOWN")

            # Stop alert system
            self.alerts.stop()

            self._running = False

            logger.info("🌍 TITAN ECOSYSTEM stopped")

    def reset(self):
        """Reset ecosystem to initial state"""
        with self._lock:
            # Clear positions
            self.positions.clear()

            # Reset capital
            self.capital = self.config.initial_capital
            self.daily_pnl = 0.0
            self.daily_start_capital = self.config.initial_capital

            # Reset components
            self.brain.reset()
            # Recreate risk manager and journal since they don't have reset methods
            self.risk_manager = RiskManager()
            self.journal = TradeJournal(initial_capital=self.config.initial_capital)

            # Clear history
            self.tick_history.clear()

            logger.info("🌍 Ecosystem reset to initial state")

    # =========================================
    # STATUS & STATISTICS
    # =========================================

    def get_status(self) -> Dict:
        """Get comprehensive ecosystem status"""
        with self._lock:
            # Calculate portfolio value
            positions_value = sum(
                p.quantity * p.current_price for p in self.positions.values()
            )
            unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
            total_equity = self.capital + positions_value

            return {
                'state': self.state.value,
                'portfolio': {
                    'capital': self.capital,
                    'positions_value': positions_value,
                    'unrealized_pnl': unrealized_pnl,
                    'total_equity': total_equity,
                    'total_return_pct': (total_equity - self.config.initial_capital) / self.config.initial_capital * 100
                },
                'positions': {
                    'count': len(self.positions),
                    'details': [
                        {
                            'id': p.position_id,
                            'asset': p.asset,
                            'side': p.side,
                            'entry_price': p.entry_price,
                            'current_price': p.current_price,
                            'quantity': p.quantity,
                            'unrealized_pnl': p.unrealized_pnl,
                            'unrealized_pnl_pct': p.unrealized_pnl_pct * 100
                        }
                        for p in self.positions.values()
                    ]
                },
                'daily': {
                    'pnl': self.daily_pnl,
                    'start_capital': self.daily_start_capital,
                    'return_pct': (self.daily_pnl / self.daily_start_capital * 100) if self.daily_start_capital > 0 else 0
                },
                'brain': self.brain.get_stats(),
                'risk': self.risk_manager.get_stats(),
                'execution': self.executor.get_stats(),
                'journal': self.journal.get_stats(),
                'alerts': self.alerts.get_stats(),
                'darwin': self.darwin.get_stats() if self.darwin else None,
                'tick_history_size': len(self.tick_history)
            }

    def get_performance(self) -> PerformanceMetrics:
        """Get performance metrics from journal"""
        return self.journal.calculate_metrics()

    def get_regime_analysis(self) -> Dict:
        """Get regime analysis from receptors"""
        return self.regime_detector.get_analysis()

    def get_brain_config(self) -> BrainConfig:
        """Get current brain configuration"""
        return self.brain.get_config()

    def export_journal(self, filepath: str):
        """Export trade journal"""
        self.journal.export_trades(filepath)


# =========================================
# FACTORY FUNCTION
# =========================================

_global_ecosystem: Optional[TitanEcosystem] = None


def get_ecosystem() -> TitanEcosystem:
    """Get or create global ecosystem instance"""
    global _global_ecosystem
    if _global_ecosystem is None:
        _global_ecosystem = TitanEcosystem()
    return _global_ecosystem


def create_ecosystem(config: EcosystemConfig = None) -> TitanEcosystem:
    """Create a new ecosystem instance (replaces global)"""
    global _global_ecosystem
    _global_ecosystem = TitanEcosystem(config)
    return _global_ecosystem


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test ecosystem
    ecosystem = TitanEcosystem()
    ecosystem.start()

    # Simulate some ticks
    test_ticks = [
        {'asset': 'BTC/USDT', 'price': 50000, 'entropy': 2.3, 'hurst': 0.65, 'viral_k': 1.3, 'cvd': 150, 'phase': 'accumulation'},
        {'asset': 'BTC/USDT', 'price': 50100, 'entropy': 2.1, 'hurst': 0.68, 'viral_k': 1.4, 'cvd': 200, 'phase': 'recovery'},
        {'asset': 'BTC/USDT', 'price': 50200, 'entropy': 2.0, 'hurst': 0.70, 'viral_k': 1.5, 'cvd': 250, 'phase': 'recovery'},
        {'asset': 'BTC/USDT', 'price': 50500, 'entropy': 1.9, 'hurst': 0.72, 'viral_k': 1.6, 'cvd': 300, 'phase': 'euphoria'},
        {'asset': 'BTC/USDT', 'price': 49800, 'entropy': 3.5, 'hurst': 0.45, 'viral_k': 0.8, 'cvd': -100, 'phase': 'crash'},
    ]

    print("\n" + "="*60)
    print("TITAN ECOSYSTEM TEST")
    print("="*60)

    for tick in test_ticks:
        signal = ecosystem.process_tick(tick)
        print(f"Price: ${tick['price']:.2f} | Phase: {tick['phase']:12} | Signal: {signal.signal_type.value if signal else 'None'}")

    print("\n" + "="*60)
    print("ECOSYSTEM STATUS")
    print("="*60)

    status = ecosystem.get_status()
    print(f"State: {status['state']}")
    print(f"Capital: ${status['portfolio']['capital']:.2f}")
    print(f"Positions: {status['positions']['count']}")
    print(f"Signals Generated: {status['brain']['signals_generated']}")

    ecosystem.stop()
