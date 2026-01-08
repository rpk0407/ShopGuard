"""
TITAN Trading Engine
=====================
Unified trading engine connecting TitanBrain signals with Hyperliquid execution.

This is the core loop that:
1. Receives real-time CVD from Hyperliquid WebSocket
2. Integrates external alpha (prediction markets, social sentiment, news)
3. Feeds data to TitanBrain for signal generation
4. Executes signals through Hyperliquid broker
5. Manages positions with ATR-based stops

Architecture:
    External Alpha ────────────────────────────┐
    (Polymarket, Twitter, Reddit, News)        │
                                               ▼
    Hyperliquid WS → CVD Engine → TitanBrain → Risk Manager → Hyperliquid Execution
                         ↓              ↓
                    Funding Scanner  Position Monitor
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

# Import TitanBrain components
try:
    from ..src.core.titan_brain import TitanBrain, BrainConfig, TradingSignal, SignalType
    BRAIN_AVAILABLE = True
except ImportError:
    BRAIN_AVAILABLE = False

# Import Hyperliquid broker
from .hyperliquid import HyperliquidBroker, BrokerConfig
from .hyperliquid.websocket import HyperliquidWebSocket, CVDState, Trade
from .hyperliquid.client import HyperliquidClient
from .hyperliquid.funding import FundingScanner, FundingConfig, FundingOpportunity

# Import external signals
try:
    from ..signals.external import (
        SignalAggregator, AggregatedSignal, ExternalSignalConfig
    )
    EXTERNAL_SIGNALS_AVAILABLE = True
except ImportError:
    EXTERNAL_SIGNALS_AVAILABLE = False

logger = logging.getLogger(__name__)


class EngineState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class EngineConfig:
    """Trading engine configuration"""
    # Hyperliquid
    private_key: str = ""
    testnet: bool = True

    # Assets
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH"])

    # Signal Generation
    min_confidence: float = 0.6
    cvd_weight: float = 0.5  # Enhanced CVD weighting
    require_cvd_confirmation: bool = True

    # External Signals (Prediction Markets, Social, News)
    enable_external_signals: bool = True
    external_signal_weight: float = 0.25  # Weight of external signals vs technical
    twitter_bearer_token: Optional[str] = None
    newsapi_key: Optional[str] = None
    lunarcrush_api_key: Optional[str] = None

    # Risk
    max_position_pct: float = 0.25
    max_leverage: int = 3
    max_concurrent_positions: int = 3
    atr_stop_multiplier: float = 1.5
    atr_target_multiplier: float = 3.0

    # Funding Arbitrage (Passive Income Layer)
    enable_funding_arbitrage: bool = True
    min_funding_rate: float = 0.0005  # 0.05% per 8h

    # Monitoring
    position_check_interval: int = 5  # seconds
    signal_cooldown: int = 60  # seconds between signals per asset


@dataclass
class EngineStats:
    """Engine statistics"""
    start_time: float = 0.0
    ticks_processed: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    trades_won: int = 0
    trades_lost: int = 0
    total_pnl: float = 0.0
    funding_collected: float = 0.0

    @property
    def win_rate(self) -> float:
        total = self.trades_won + self.trades_lost
        return self.trades_won / total if total > 0 else 0.0

    @property
    def uptime_hours(self) -> float:
        return (time.time() - self.start_time) / 3600 if self.start_time > 0 else 0.0


class TitanTradingEngine:
    """
    TITAN Trading Engine

    The unified trading system that combines:
    - Real-time CVD from Hyperliquid WebSocket
    - TitanBrain 3-pillar signal generation (enhanced with CVD)
    - Hyperliquid execution with ATR-based risk
    - Funding rate arbitrage for passive income

    Usage:
        engine = TitanTradingEngine(config)
        await engine.start()

        # Engine runs autonomously, or you can:
        engine.pause()
        engine.resume()
        await engine.stop()
    """

    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()
        self.state = EngineState.STOPPED
        self.stats = EngineStats()

        # Components
        self.broker: Optional[HyperliquidBroker] = None
        self.brain: Optional['TitanBrain'] = None
        self.funding_scanner: Optional[FundingScanner] = None
        self.external_signals: Optional['SignalAggregator'] = None

        # State tracking
        self._last_signal_time: Dict[str, float] = {}
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Market data cache
        self._prices: Dict[str, float] = {}
        self._cvd_states: Dict[str, CVDState] = {}
        self._atr_values: Dict[str, float] = {}  # ATR for each asset

        # Callbacks
        self.on_signal: Optional[Callable[[TradingSignal], None]] = None
        self.on_trade: Optional[Callable[[Dict], None]] = None
        self.on_funding: Optional[Callable[[FundingOpportunity], None]] = None

        logger.info("TitanTradingEngine initialized")

    async def start(self) -> bool:
        """Start the trading engine"""
        self.state = EngineState.STARTING
        logger.info("Starting TitanTradingEngine...")

        try:
            # Initialize TitanBrain
            if BRAIN_AVAILABLE:
                brain_config = BrainConfig(
                    entropy_threshold=2.5,
                    hurst_threshold=0.55,
                    viral_k_threshold=1.1,
                    cvd_threshold=0.6
                )
                self.brain = TitanBrain(config=brain_config)
                logger.info("TitanBrain initialized")
            else:
                logger.warning("TitanBrain not available, using simplified signals")

            # Initialize Hyperliquid broker
            broker_config = BrokerConfig(
                private_key=self.config.private_key,
                testnet=self.config.testnet,
                assets=self.config.assets,
                max_position_pct=self.config.max_position_pct,
                max_leverage=self.config.max_leverage,
                max_concurrent_positions=self.config.max_concurrent_positions
            )
            self.broker = HyperliquidBroker(broker_config)

            if not await self.broker.connect():
                logger.error("Failed to connect to Hyperliquid")
                self.state = EngineState.ERROR
                return False

            # Set up CVD callback
            self.broker.on_cvd_update = self._on_cvd_update
            self.broker.on_trade = self._on_trade

            # Initialize funding scanner (passive income layer)
            if self.config.enable_funding_arbitrage:
                funding_config = FundingConfig(
                    min_funding_rate=self.config.min_funding_rate,
                    assets=self.config.assets
                )
                self.funding_scanner = FundingScanner(
                    self.broker.client,
                    funding_config
                )
                self.funding_scanner.on_opportunity = self._on_funding_opportunity

            # Initialize external signals (prediction markets, social, news)
            if self.config.enable_external_signals and EXTERNAL_SIGNALS_AVAILABLE:
                external_config = ExternalSignalConfig(
                    enable_polymarket=True,
                    enable_social=True,
                    enable_news=True,
                    twitter_bearer_token=self.config.twitter_bearer_token,
                    newsapi_key=self.config.newsapi_key,
                    lunarcrush_api_key=self.config.lunarcrush_api_key,
                    assets=self.config.assets
                )
                self.external_signals = SignalAggregator(external_config)
                self.external_signals.on_signal = self._on_external_signal
                self.external_signals.on_urgent_signal = self._on_urgent_external_signal
                await self.external_signals.start()
                logger.info("External signals initialized (Polymarket, Social, News)")
            elif self.config.enable_external_signals:
                logger.warning("External signals requested but module not available")

            # Start background tasks
            self._running = True
            self._tasks = [
                asyncio.create_task(self._signal_loop()),
                asyncio.create_task(self._position_monitor_loop()),
            ]

            if self.funding_scanner:
                self._tasks.append(
                    asyncio.create_task(self._funding_loop())
                )

            self.state = EngineState.RUNNING
            self.stats.start_time = time.time()
            logger.info("TitanTradingEngine started")
            return True

        except Exception as e:
            logger.error(f"Failed to start engine: {e}")
            self.state = EngineState.ERROR
            return False

    async def stop(self):
        """Stop the trading engine"""
        logger.info("Stopping TitanTradingEngine...")
        self._running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        # Stop external signals
        if self.external_signals:
            await self.external_signals.stop()

        # Disconnect broker
        if self.broker:
            await self.broker.disconnect()

        self.state = EngineState.STOPPED
        logger.info("TitanTradingEngine stopped")

    def pause(self):
        """Pause signal generation (keeps monitoring)"""
        self.state = EngineState.PAUSED
        logger.info("Engine paused")

    def resume(self):
        """Resume signal generation"""
        self.state = EngineState.RUNNING
        logger.info("Engine resumed")

    # =========================================
    # CORE LOOPS
    # =========================================

    async def _signal_loop(self):
        """Main signal generation loop"""
        while self._running:
            try:
                if self.state != EngineState.RUNNING:
                    await asyncio.sleep(1)
                    continue

                # Process each asset
                for asset in self.config.assets:
                    await self._process_asset(asset)

                await asyncio.sleep(1)  # Check every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Signal loop error: {e}")
                await asyncio.sleep(5)

    async def _position_monitor_loop(self):
        """Monitor positions for stop loss / take profit"""
        while self._running:
            try:
                if self.broker:
                    await self.broker.check_stop_loss_take_profit()

                await asyncio.sleep(self.config.position_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(5)

    async def _funding_loop(self):
        """Monitor funding rates for arbitrage"""
        while self._running:
            try:
                if self.funding_scanner:
                    await self.funding_scanner.scan()

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Funding loop error: {e}")
                await asyncio.sleep(30)

    # =========================================
    # SIGNAL GENERATION
    # =========================================

    async def _process_asset(self, asset: str):
        """Process an asset for signal generation"""
        # Check cooldown
        last_signal = self._last_signal_time.get(asset, 0)
        if time.time() - last_signal < self.config.signal_cooldown:
            return

        # Get market data
        price = self.broker.get_price(asset) if self.broker else 0
        cvd_state = self._cvd_states.get(asset)

        if price == 0:
            return

        self._prices[asset] = price
        self.stats.ticks_processed += 1

        # Generate signal
        signal = await self._generate_signal(asset, price, cvd_state)

        if signal and signal.signal_type != SignalType.HOLD:
            self.stats.signals_generated += 1
            self._last_signal_time[asset] = time.time()

            # Callback
            if self.on_signal:
                self.on_signal(signal)

            # Execute if confidence meets threshold
            if signal.confidence >= self.config.min_confidence:
                await self._execute_signal(signal)

    async def _generate_signal(
        self,
        asset: str,
        price: float,
        cvd_state: Optional[CVDState]
    ) -> Optional['TradingSignal']:
        """Generate trading signal using TitanBrain + CVD + External Signals"""

        # Calculate ATR (simplified - would use proper candle data)
        atr = self._calculate_atr(asset, price)
        self._atr_values[asset] = atr

        # Get external signals (prediction markets, social, news)
        external_data = None
        if self.external_signals:
            external_data = self.external_signals.get_signal_for_titan(asset)

        # Build tick data for TitanBrain
        tick_data = {
            'asset': asset,
            'price': price,
            'timestamp': time.time(),
            # CVD data
            'cvd': cvd_state.cvd if cvd_state else 0,
            'cvd_buy_volume': cvd_state.buy_volume if cvd_state else 0,
            'cvd_sell_volume': cvd_state.sell_volume if cvd_state else 0,
            # Will be filled by TitanBrain or estimated
            'entropy': 2.0,  # Placeholder
            'hurst': 0.5,    # Placeholder
            'viral_k': 1.0,  # Placeholder
            # External signals
            'external_direction': external_data.get('external_direction', 0) if external_data else 0,
            'external_confidence': external_data.get('external_confidence', 0) if external_data else 0,
        }

        # Get CVD divergence signal
        cvd_divergence = None
        if cvd_state:
            cvd_divergence = cvd_state.get_divergence()

        # Use TitanBrain if available
        if self.brain:
            signal = self.brain.process_tick(tick_data)

            # Enhance with CVD divergence
            if cvd_divergence:
                signal = self._enhance_signal_with_cvd(signal, cvd_divergence)

            # Enhance with external signals
            if external_data:
                signal = self._enhance_signal_with_external(signal, external_data)

            # Add ATR-based stops
            signal.atr = atr
            signal.stop_loss = self._calculate_stop_loss(
                signal.signal_type, price, atr
            )
            signal.take_profit = self._calculate_take_profit(
                signal.signal_type, price, atr
            )

            return signal

        # Simplified signal generation without TitanBrain
        return self._generate_simple_signal(asset, price, cvd_state, cvd_divergence, atr, external_data)

    def _enhance_signal_with_cvd(
        self,
        signal: 'TradingSignal',
        cvd_divergence: str
    ) -> 'TradingSignal':
        """Enhance TitanBrain signal with CVD divergence"""

        # CVD divergence can boost or reduce confidence
        if cvd_divergence == "BULLISH":
            if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                # CVD confirms bullish signal
                signal.confidence = min(1.0, signal.confidence + 0.15)
                signal.cvd_check = True
            elif signal.signal_type in [SignalType.SELL, SignalType.EXIT]:
                # CVD contradicts bearish signal
                signal.confidence = max(0.0, signal.confidence - 0.1)

        elif cvd_divergence == "BEARISH":
            if signal.signal_type in [SignalType.SELL, SignalType.EXIT]:
                # CVD confirms bearish signal
                signal.confidence = min(1.0, signal.confidence + 0.15)
                signal.cvd_check = True
            elif signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                # CVD contradicts bullish signal
                signal.confidence = max(0.0, signal.confidence - 0.1)

        return signal

    def _enhance_signal_with_external(
        self,
        signal: 'TradingSignal',
        external_data: Dict
    ) -> 'TradingSignal':
        """Enhance TitanBrain signal with external signals (prediction markets, social, news)"""

        external_direction = external_data.get('external_direction', 0)
        external_confidence = external_data.get('external_confidence', 0)
        external_urgency = external_data.get('external_urgency', 0)

        # Skip if external signal is weak
        if abs(external_direction) < 0.2 or external_confidence < 0.3:
            return signal

        weight = self.config.external_signal_weight

        # Check if external signals confirm or contradict the technical signal
        sig_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else signal.signal_type

        if sig_type in ["BUY", "STRONG_BUY"]:
            if external_direction > 0:
                # External confirms bullish signal
                boost = weight * external_confidence * external_direction
                signal.confidence = min(1.0, signal.confidence + boost)
                signal.external_confirmed = True
            else:
                # External contradicts bullish signal
                penalty = weight * external_confidence * abs(external_direction) * 0.5
                signal.confidence = max(0.0, signal.confidence - penalty)

        elif sig_type in ["SELL", "EXIT"]:
            if external_direction < 0:
                # External confirms bearish signal
                boost = weight * external_confidence * abs(external_direction)
                signal.confidence = min(1.0, signal.confidence + boost)
                signal.external_confirmed = True
            else:
                # External contradicts bearish signal
                penalty = weight * external_confidence * external_direction * 0.5
                signal.confidence = max(0.0, signal.confidence - penalty)

        # Urgent external signals get extra weight
        if external_urgency > 0.5:
            if (external_direction > 0 and sig_type in ["BUY", "STRONG_BUY"]) or \
               (external_direction < 0 and sig_type in ["SELL", "EXIT"]):
                signal.confidence = min(1.0, signal.confidence + 0.1)

        return signal

    def _generate_simple_signal(
        self,
        asset: str,
        price: float,
        cvd_state: Optional[CVDState],
        cvd_divergence: Optional[str],
        atr: float,
        external_data: Optional[Dict] = None
    ) -> Optional['TradingSignal']:
        """Simple signal generation without TitanBrain"""

        # This is a simplified fallback
        # Real implementation should use proper indicators

        signal = None
        reasons = []

        # CVD-based signal
        if cvd_divergence == "BULLISH":
            signal = self._create_signal(
                asset=asset,
                signal_type="BUY",
                confidence=0.65,
                price=price,
                atr=atr,
                reason="CVD Bullish Divergence"
            )
            reasons.append("CVD Bullish")
        elif cvd_divergence == "BEARISH":
            signal = self._create_signal(
                asset=asset,
                signal_type="SELL",
                confidence=0.65,
                price=price,
                atr=atr,
                reason="CVD Bearish Divergence"
            )
            reasons.append("CVD Bearish")

        # Enhance with external signals if available
        if external_data and signal:
            ext_dir = external_data.get('external_direction', 0)
            ext_conf = external_data.get('external_confidence', 0)
            ext_urg = external_data.get('external_urgency', 0)

            if abs(ext_dir) > 0.2 and ext_conf > 0.3:
                sig_type = signal.signal_type

                # Check alignment
                if (sig_type == "BUY" and ext_dir > 0) or (sig_type == "SELL" and ext_dir < 0):
                    # External confirms
                    boost = self.config.external_signal_weight * ext_conf * abs(ext_dir)
                    signal.confidence = min(1.0, signal.confidence + boost)
                    reasons.append("External Confirmed")

                    # Add source details
                    if external_data.get('prediction_signal', 0) != 0:
                        reasons.append("Polymarket")
                    if external_data.get('social_signal', 0) != 0:
                        reasons.append("Social")
                    if external_data.get('news_signal', 0) != 0:
                        reasons.append("News")
                else:
                    # External contradicts
                    penalty = self.config.external_signal_weight * ext_conf * abs(ext_dir) * 0.5
                    signal.confidence = max(0.0, signal.confidence - penalty)

            signal.story = f"{signal.signal_type} signal for {asset} based on: {', '.join(reasons)}"

        # If no CVD signal, check if external signals are strong enough on their own
        elif external_data and not signal:
            ext_dir = external_data.get('external_direction', 0)
            ext_conf = external_data.get('external_confidence', 0)
            ext_urg = external_data.get('external_urgency', 0)

            # Strong external signal can trigger on its own (with high urgency)
            if abs(ext_dir) > 0.5 and ext_conf > 0.6 and ext_urg > 0.5:
                if ext_dir > 0:
                    signal = self._create_signal(
                        asset=asset,
                        signal_type="BUY",
                        confidence=ext_conf * 0.8,  # Slightly reduced without CVD confirmation
                        price=price,
                        atr=atr,
                        reason="Strong External Bullish Signal (Prediction/Social/News)"
                    )
                else:
                    signal = self._create_signal(
                        asset=asset,
                        signal_type="SELL",
                        confidence=ext_conf * 0.8,
                        price=price,
                        atr=atr,
                        reason="Strong External Bearish Signal (Prediction/Social/News)"
                    )

        return signal

    def _create_signal(
        self,
        asset: str,
        signal_type: str,
        confidence: float,
        price: float,
        atr: float,
        reason: str
    ) -> 'TradingSignal':
        """Create a trading signal (when TitanBrain not available)"""

        # Simple dataclass-like object
        class SimpleSignal:
            pass

        signal = SimpleSignal()
        signal.asset = asset
        signal.signal_type = signal_type
        signal.confidence = confidence
        signal.price = price
        signal.atr = atr
        signal.timestamp = time.time()
        signal.stop_loss = self._calculate_stop_loss(signal_type, price, atr)
        signal.take_profit = self._calculate_take_profit(signal_type, price, atr)
        signal.headline = reason
        signal.story = f"{signal_type} signal for {asset} based on {reason}"

        return signal

    def _calculate_atr(self, asset: str, current_price: float) -> float:
        """Calculate ATR (simplified)"""
        # In production, use proper candle data
        # For now, estimate as 2% of price
        return current_price * 0.02

    def _calculate_stop_loss(
        self,
        signal_type,
        price: float,
        atr: float
    ) -> float:
        """Calculate stop loss based on ATR"""
        stop_distance = atr * self.config.atr_stop_multiplier

        # Handle both enum and string signal types
        sig = signal_type.value if hasattr(signal_type, 'value') else signal_type

        if sig in ["BUY", "STRONG_BUY"]:
            return price - stop_distance
        elif sig in ["SELL", "EXIT"]:
            return price + stop_distance
        return price

    def _calculate_take_profit(
        self,
        signal_type,
        price: float,
        atr: float
    ) -> float:
        """Calculate take profit based on ATR"""
        target_distance = atr * self.config.atr_target_multiplier

        sig = signal_type.value if hasattr(signal_type, 'value') else signal_type

        if sig in ["BUY", "STRONG_BUY"]:
            return price + target_distance
        elif sig in ["SELL", "EXIT"]:
            return price - target_distance
        return price

    # =========================================
    # EXECUTION
    # =========================================

    async def _execute_signal(self, signal):
        """Execute a trading signal"""
        if not self.broker:
            return

        # Convert to TradeSignal format expected by broker
        from .hyperliquid.broker import TradeSignal

        sig_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else signal.signal_type

        if sig_type in ["BUY", "STRONG_BUY"]:
            side = "BUY"
        elif sig_type in ["SELL", "EXIT"]:
            side = "SELL"
        else:
            return  # HOLD - no action

        trade_signal = TradeSignal(
            asset=signal.asset,
            side=side,
            size_pct=1.0,  # Use full allocation per signal
            confidence=signal.confidence,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            signal_type=sig_type
        )

        result = await self.broker.execute_signal(trade_signal)

        if result:
            self.stats.trades_executed += 1
            logger.info(f"Trade executed: {side} {signal.asset} @ ${signal.price:,.2f}")

            if self.on_trade:
                self.on_trade({
                    'asset': signal.asset,
                    'side': side,
                    'price': signal.price,
                    'confidence': signal.confidence,
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.take_profit
                })

    # =========================================
    # CALLBACKS
    # =========================================

    def _on_cvd_update(self, cvd: CVDState):
        """Handle CVD update from WebSocket"""
        self._cvd_states[cvd.asset] = cvd

    def _on_trade(self, trade: Trade):
        """Handle trade from WebSocket"""
        # Update price cache
        self._prices[trade.asset] = trade.price

    def _on_funding_opportunity(self, opp: FundingOpportunity):
        """Handle funding opportunity"""
        logger.info(
            f"Funding opportunity: {opp.asset} "
            f"{opp.funding_rate*100:.4f}% ({opp.funding_rate_annual*100:.2f}% annual)"
        )

        if self.on_funding:
            self.on_funding(opp)

    def _on_external_signal(self, signal: 'AggregatedSignal'):
        """Handle external signal from aggregator"""
        direction = "BULLISH" if signal.direction > 0 else "BEARISH" if signal.direction < 0 else "NEUTRAL"
        logger.info(
            f"External signal: {signal.asset} {direction} "
            f"(conf: {signal.confidence:.2f}, sources: {signal.source_count})"
        )

    def _on_urgent_external_signal(self, signal: 'AggregatedSignal'):
        """Handle urgent external signal (e.g., breaking news)"""
        direction = "BULLISH" if signal.direction > 0 else "BEARISH" if signal.direction < 0 else "NEUTRAL"
        logger.warning(
            f"URGENT External signal: {signal.asset} {direction} "
            f"(urgency: {signal.urgency:.2f}) - {signal.reasoning}"
        )
        # Urgent signals bypass normal cooldown
        self._last_signal_time[signal.asset] = 0

    # =========================================
    # STATUS
    # =========================================

    def get_status(self) -> Dict:
        """Get engine status"""
        status = {
            'state': self.state.value,
            'uptime_hours': self.stats.uptime_hours,
            'assets': self.config.assets,
            'testnet': self.config.testnet,
            'broker': self.broker.get_status() if self.broker else None,
            'brain_available': BRAIN_AVAILABLE,
            'external_signals_enabled': self.config.enable_external_signals and EXTERNAL_SIGNALS_AVAILABLE,
            'funding_enabled': self.config.enable_funding_arbitrage,
            'prices': self._prices,
            'cvd': {
                asset: {
                    'cvd': state.cvd,
                    'divergence': state.get_divergence()
                }
                for asset, state in self._cvd_states.items()
            }
        }

        # Add external signal summary
        if self.external_signals:
            ext_summary = self.external_signals.get_summary()
            status['external_signals'] = {
                'overall_sentiment': ext_summary.get('overall_sentiment', 0),
                'urgent_count': ext_summary.get('urgent_count', 0),
                'assets': ext_summary.get('assets', {})
            }

        return status

    def get_stats(self) -> Dict:
        """Get engine statistics"""
        return {
            'uptime_hours': round(self.stats.uptime_hours, 2),
            'ticks_processed': self.stats.ticks_processed,
            'signals_generated': self.stats.signals_generated,
            'trades_executed': self.stats.trades_executed,
            'win_rate': f"{self.stats.win_rate*100:.1f}%",
            'total_pnl': self.stats.total_pnl,
            'funding_collected': self.stats.funding_collected
        }


# =========================================
# DEMO
# =========================================

async def demo_engine():
    """Demo the trading engine (read-only, no private key)"""
    print("\n" + "=" * 60)
    print("TITAN TRADING ENGINE DEMO")
    print("=" * 60 + "\n")

    config = EngineConfig(
        testnet=True,
        assets=["BTC", "ETH"],
        enable_funding_arbitrage=True,
        enable_external_signals=True  # Enable prediction markets, social, news
    )

    engine = TitanTradingEngine(config)

    # Set up callbacks
    def on_signal(signal):
        sig_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else signal.signal_type
        print(f"\nSIGNAL: {signal.asset} {sig_type}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Stop Loss: ${signal.stop_loss:,.2f}")
        print(f"  Take Profit: ${signal.take_profit:,.2f}")

    engine.on_signal = on_signal

    print("Starting engine (read-only mode)...")
    print("  - CVD from Hyperliquid WebSocket")
    print("  - External signals (Polymarket, Social, News)")
    print("  - Funding rate monitoring")

    if not await engine.start():
        print("Failed to start engine")
        return

    print("\nEngine running. Collecting data...")
    print("Press Ctrl+C to stop\n")

    try:
        # Run for a while, printing status
        for i in range(60):  # Run for 60 seconds
            await asyncio.sleep(10)

            status = engine.get_status()
            stats = engine.get_stats()

            print(f"\n[{i*10}s] Status Update:")
            print(f"  State: {status['state']}")
            print(f"  Ticks: {stats['ticks_processed']}")
            print(f"  Signals: {stats['signals_generated']}")

            # Show CVD
            for asset, cvd in status.get('cvd', {}).items():
                print(f"  {asset} CVD: {cvd['cvd']:,.2f} | Divergence: {cvd['divergence']}")

            # Show external signals
            ext_signals = status.get('external_signals', {})
            if ext_signals:
                print(f"  External Sentiment: {ext_signals.get('overall_sentiment', 0):.2f}")
                for asset, data in ext_signals.get('assets', {}).items():
                    direction = "BULL" if data.get('direction', 0) > 0 else "BEAR" if data.get('direction', 0) < 0 else "NEUT"
                    print(f"    {asset}: {direction} (conf: {data.get('confidence', 0):.2f})")

    except KeyboardInterrupt:
        print("\n\nStopping...")

    await engine.stop()

    print("\n" + "=" * 60)
    print("Final Stats:")
    print(engine.get_stats())
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo_engine())
