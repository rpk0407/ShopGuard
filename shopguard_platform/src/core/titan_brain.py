"""
TITAN BRAIN - Dynamic Trading Intelligence
==========================================
The central decision-making unit that processes market data through
the three-pillar convergence strategy. Parameters are DYNAMIC and
can be hot-swapped by the Darwinian Engine.

Architecture:
    - Receives ticks from Matrix or live feeds
    - Applies three-pillar convergence detection
    - Parameters updated in real-time by Darwin
    - Emits trading signals with confidence scores
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    EXIT = "EXIT"


@dataclass
class BrainConfig:
    """
    Dynamic configuration for TitanBrain.
    All parameters can be hot-swapped by Darwin.
    """
    # Bio-Check: Entropy thresholds
    entropy_threshold_low: float = 2.0    # Below = strong order
    entropy_threshold_high: float = 2.5   # Below = moderate order
    entropy_weight: float = 1.0

    # Physics-Check: Hurst thresholds
    hurst_threshold_low: float = 0.55     # Above = weak trend
    hurst_threshold_high: float = 0.65    # Above = strong trend
    hurst_weight: float = 1.0

    # Micro-Check: Viral K thresholds
    k_threshold_low: float = 1.1          # Above = weak viral
    k_threshold_high: float = 1.3         # Above = strong viral
    k_weight: float = 1.0

    # CVD thresholds
    cvd_accumulation_threshold: float = 100
    cvd_distribution_threshold: float = -100
    cvd_weight: float = 0.8

    # Convergence requirements
    min_pillars_for_entry: int = 2        # Minimum pillars aligned
    min_conviction_for_entry: float = 0.5 # Minimum conviction score

    # Position sizing
    position_size_base: float = 0.1
    position_size_per_conviction: float = 0.05
    max_position_size: float = 0.3

    # Risk management
    stop_loss_pct: float = 0.03           # 3% stop loss
    take_profit_pct: float = 0.06         # 6% take profit
    trailing_stop_pct: float = 0.02       # 2% trailing stop
    max_drawdown_pct: float = 0.15        # 15% max drawdown

    # Meta
    version: int = 1
    last_updated: float = field(default_factory=time.time)
    source: str = "default"               # "default", "darwin", "manual"


@dataclass
class TradingSignal:
    """Output signal from TitanBrain"""
    signal_type: SignalType
    confidence: float                      # 0.0 - 1.0
    conviction: float                      # Raw conviction score
    asset: str
    price: float
    timestamp: float

    # Pillar states
    bio_check: bool                        # Entropy aligned
    physics_check: bool                    # Hurst aligned
    micro_check: bool                      # Viral K aligned
    cvd_check: bool                        # CVD aligned

    # Metrics
    entropy: float
    hurst: float
    viral_k: float
    cvd: float
    market_phase: str

    # Recommendations
    position_size: float
    stop_loss: float
    take_profit: float

    def to_dict(self) -> Dict:
        return {
            'signal': self.signal_type.value,
            'confidence': self.confidence,
            'conviction': self.conviction,
            'asset': self.asset,
            'price': self.price,
            'timestamp': self.timestamp,
            'pillars': {
                'bio': self.bio_check,
                'physics': self.physics_check,
                'micro': self.micro_check,
                'cvd': self.cvd_check
            },
            'metrics': {
                'entropy': self.entropy,
                'hurst': self.hurst,
                'viral_k': self.viral_k,
                'cvd': self.cvd
            },
            'phase': self.market_phase,
            'recommendations': {
                'position_size': self.position_size,
                'stop_loss': self.stop_loss,
                'take_profit': self.take_profit
            }
        }


class TitanBrain:
    """
    THE TITAN BRAIN
    ===============
    Central intelligence for trading decisions.
    Parameters evolve through Darwinian selection.
    """

    def __init__(self, config: BrainConfig = None):
        self.config = config or BrainConfig()
        self._lock = threading.RLock()

        # State
        self.is_active = True
        self.current_position = 0.0
        self.entry_price = 0.0
        self.peak_equity = 0.0

        # History
        self.signal_history: deque = deque(maxlen=1000)
        self.config_history: List[BrainConfig] = []
        self.evolution_count = 0

        # Callbacks
        self.on_signal: Optional[Callable[[TradingSignal], None]] = None
        self.on_config_update: Optional[Callable[[BrainConfig], None]] = None

        # Stats
        self.stats = {
            'signals_generated': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'config_updates': 0,
            'last_signal_time': None
        }

        logger.info("🧠 TitanBrain initialized with dynamic config")

    async def update_config(self, new_config: BrainConfig):
        """
        HOT-SWAP configuration from Darwin.
        This is the evolution entry point.
        """
        with self._lock:
            old_config = self.config
            self.config = new_config
            self.config.last_updated = time.time()
            self.config.source = "darwin"
            self.config.version = old_config.version + 1

            self.config_history.append(old_config)
            self.evolution_count += 1
            self.stats['config_updates'] += 1

            logger.info(
                f"🧬 BRAIN EVOLVED (v{self.config.version}): "
                f"K-Threshold={self.config.k_threshold_high:.3f}, "
                f"Entropy-Threshold={self.config.entropy_threshold_high:.3f}, "
                f"Hurst-Threshold={self.config.hurst_threshold_high:.3f}"
            )

            if self.on_config_update:
                self.on_config_update(self.config)

    def update_config_sync(self, new_config: BrainConfig):
        """Synchronous version of update_config"""
        with self._lock:
            old_config = self.config
            self.config = new_config
            self.config.last_updated = time.time()
            self.config.source = "darwin"
            self.config.version = old_config.version + 1

            self.config_history.append(old_config)
            self.evolution_count += 1
            self.stats['config_updates'] += 1

            logger.info(
                f"🧬 BRAIN EVOLVED (v{self.config.version}): "
                f"K={self.config.k_threshold_high:.3f}, "
                f"Entropy={self.config.entropy_threshold_high:.3f}, "
                f"Hurst={self.config.hurst_threshold_high:.3f}"
            )

    def update_from_genome(self, genome: 'Genome'):
        """Update config directly from a Darwin Genome"""
        new_config = BrainConfig(
            entropy_threshold_high=genome.entropy_threshold,
            entropy_weight=genome.entropy_weight,
            hurst_threshold_high=genome.hurst_threshold,
            hurst_weight=genome.hurst_weight,
            k_threshold_high=genome.k_threshold,
            k_weight=genome.k_weight,
            cvd_weight=genome.cvd_sensitivity,
            position_size_base=genome.position_size_base,
            position_size_per_conviction=genome.position_size_conviction,
            stop_loss_pct=genome.stop_loss_atr_mult * 0.01,
            take_profit_pct=genome.take_profit_atr_mult * 0.01,
            max_drawdown_pct=genome.max_drawdown_pct,
            source="darwin"
        )
        self.update_config_sync(new_config)

    def process_tick(self, tick: Dict) -> TradingSignal:
        """
        Process market tick and generate trading signal.
        This is the main decision loop.
        """
        with self._lock:
            config = self.config

            # Extract tick data
            asset = tick.get('asset', 'BTC/USDT')
            price = tick.get('price', 0)
            entropy = tick.get('entropy', 3.0)
            hurst = tick.get('hurst', 0.5)
            viral_k = tick.get('viral_k', 1.0)
            cvd = tick.get('cvd', 0)
            phase = tick.get('phase', 'stable')

            # =================================
            # THREE-PILLAR CONVERGENCE CHECK
            # =================================

            # Pillar 1: Bio-Check (Entropy)
            bio_check = entropy < config.entropy_threshold_high
            bio_strong = entropy < config.entropy_threshold_low
            bio_score = 0
            if bio_strong:
                bio_score = config.entropy_weight
            elif bio_check:
                bio_score = config.entropy_weight * 0.5

            # Pillar 2: Physics-Check (Hurst)
            physics_check = hurst > config.hurst_threshold_low
            physics_strong = hurst > config.hurst_threshold_high
            physics_score = 0
            if physics_strong:
                physics_score = config.hurst_weight
            elif physics_check:
                physics_score = config.hurst_weight * 0.5

            # Pillar 3: Micro-Check (Viral K)
            micro_check = viral_k > config.k_threshold_low
            micro_strong = viral_k > config.k_threshold_high
            micro_score = 0
            if micro_strong:
                micro_score = config.k_weight
            elif micro_check:
                micro_score = config.k_weight * 0.5

            # Bonus: CVD Check
            cvd_bullish = cvd > config.cvd_accumulation_threshold
            cvd_bearish = cvd < config.cvd_distribution_threshold
            cvd_check = cvd_bullish
            cvd_score = config.cvd_weight if cvd_bullish else 0

            # =================================
            # CONVICTION CALCULATION
            # =================================

            total_score = bio_score + physics_score + micro_score + cvd_score
            max_score = config.entropy_weight + config.hurst_weight + config.k_weight + config.cvd_weight
            conviction = total_score / max(max_score, 1)

            pillars_aligned = sum([bio_check, physics_check, micro_check, cvd_check])

            # =================================
            # SIGNAL GENERATION
            # =================================

            signal_type = SignalType.HOLD
            confidence = 0.0

            # Exit conditions
            if phase == 'crash' or cvd_bearish:
                if self.current_position > 0:
                    signal_type = SignalType.EXIT
                    confidence = 0.9
                else:
                    signal_type = SignalType.HOLD
                    confidence = 0.3

            # Strong buy: All pillars aligned in favorable phase
            elif (pillars_aligned >= 3 and
                  conviction >= 0.7 and
                  phase in ['accumulation', 'recovery']):
                signal_type = SignalType.STRONG_BUY
                confidence = min(0.95, conviction)

            # Buy: Minimum pillars with good conviction
            elif (pillars_aligned >= config.min_pillars_for_entry and
                  conviction >= config.min_conviction_for_entry and
                  phase in ['accumulation', 'recovery', 'stable']):
                signal_type = SignalType.BUY
                confidence = min(0.8, conviction)

            # Weak sell signal in euphoria with declining metrics
            elif phase == 'euphoria' and viral_k < 0.9:
                signal_type = SignalType.SELL
                confidence = 0.6

            else:
                signal_type = SignalType.HOLD
                confidence = 0.5

            # =================================
            # POSITION SIZING
            # =================================

            if signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                position_size = min(
                    config.position_size_base + (conviction * config.position_size_per_conviction),
                    config.max_position_size
                )
            else:
                position_size = 0

            stop_loss = price * (1 - config.stop_loss_pct)
            take_profit = price * (1 + config.take_profit_pct)

            # =================================
            # CREATE SIGNAL
            # =================================

            signal = TradingSignal(
                signal_type=signal_type,
                confidence=confidence,
                conviction=conviction,
                asset=asset,
                price=price,
                timestamp=time.time(),
                bio_check=bio_check,
                physics_check=physics_check,
                micro_check=micro_check,
                cvd_check=cvd_check,
                entropy=entropy,
                hurst=hurst,
                viral_k=viral_k,
                cvd=cvd,
                market_phase=phase,
                position_size=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            # Update stats
            self.signal_history.append(signal)
            self.stats['signals_generated'] += 1
            self.stats['last_signal_time'] = time.time()

            if signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                self.stats['buy_signals'] += 1
            elif signal_type in [SignalType.SELL, SignalType.STRONG_SELL, SignalType.EXIT]:
                self.stats['sell_signals'] += 1

            # Callback
            if self.on_signal and signal_type != SignalType.HOLD:
                self.on_signal(signal)

            return signal

    def get_config(self) -> BrainConfig:
        """Get current configuration"""
        with self._lock:
            return self.config

    def get_stats(self) -> Dict:
        """Get brain statistics"""
        with self._lock:
            return {
                **self.stats,
                'evolution_count': self.evolution_count,
                'config_version': self.config.version,
                'config_source': self.config.source,
                'is_active': self.is_active
            }

    def get_last_signals(self, n: int = 10) -> List[TradingSignal]:
        """Get last N signals"""
        with self._lock:
            return list(self.signal_history)[-n:]

    def reset(self):
        """Reset brain state"""
        with self._lock:
            self.current_position = 0.0
            self.entry_price = 0.0
            self.peak_equity = 0.0
            self.signal_history.clear()
            self.stats = {
                'signals_generated': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'config_updates': self.stats.get('config_updates', 0),
                'last_signal_time': None
            }
            logger.info("🧠 TitanBrain reset")


# =============================================================================
# BRAIN + DARWIN INTEGRATION
# =============================================================================

class EvolvingBrain(TitanBrain):
    """
    TitanBrain with integrated Darwin evolution.
    Automatically evolves based on simulated performance.
    """

    def __init__(self, config: BrainConfig = None):
        super().__init__(config)
        self.darwin = None
        self._evolution_thread = None
        self._is_evolving = False

    def attach_darwin(self, darwin: 'Darwin'):
        """Attach Darwin engine for evolution"""
        self.darwin = darwin

        # Set callback for alpha evolution
        def on_alpha_evolved(genome):
            self.update_from_genome(genome)

        darwin.on_alpha_evolved = on_alpha_evolved
        logger.info("🧬 Darwin attached to TitanBrain")

    def start_evolution(self, matrix):
        """Start background evolution"""
        if not self.darwin:
            from ..evolution.darwin import Darwin
            self.darwin = Darwin()

        self.darwin.start_evolution(matrix)
        self._is_evolving = True
        logger.info("🧬 Brain evolution STARTED")

    def stop_evolution(self):
        """Stop background evolution"""
        if self.darwin:
            self.darwin.stop_evolution()
        self._is_evolving = False
        logger.info("🧬 Brain evolution STOPPED")

    def get_evolution_stats(self) -> Dict:
        """Get evolution statistics"""
        stats = self.get_stats()
        if self.darwin:
            stats['darwin'] = self.darwin.get_stats()
        stats['is_evolving'] = self._is_evolving
        return stats


if __name__ == "__main__":
    # Test TitanBrain
    logging.basicConfig(level=logging.INFO)

    brain = TitanBrain()

    # Simulate some ticks
    test_ticks = [
        {'price': 100, 'entropy': 2.3, 'hurst': 0.65, 'viral_k': 1.3, 'cvd': 150, 'phase': 'accumulation'},
        {'price': 101, 'entropy': 2.1, 'hurst': 0.68, 'viral_k': 1.4, 'cvd': 200, 'phase': 'recovery'},
        {'price': 99, 'entropy': 3.5, 'hurst': 0.45, 'viral_k': 0.8, 'cvd': -100, 'phase': 'crash'},
        {'price': 98, 'entropy': 2.8, 'hurst': 0.55, 'viral_k': 1.1, 'cvd': 50, 'phase': 'stable'},
    ]

    for tick in test_ticks:
        signal = brain.process_tick(tick)
        print(f"Phase: {tick['phase']:12} -> Signal: {signal.signal_type.value:12} "
              f"(Confidence: {signal.confidence:.2f}, Conviction: {signal.conviction:.2f})")

    print(f"\nStats: {brain.get_stats()}")
