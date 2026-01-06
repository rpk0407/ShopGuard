"""
THE MEMPOOL SCANNER - Pre-Cognition from Pending Transactions
==============================================================
Integration Target: Micro-Cortex

The mempool is where transactions wait before being mined into blocks.
By watching it, we can see whale moves BEFORE they hit the blockchain.

The PRE_COGNITION Signal:
- Large pending buys = Whales loading up (precognitive buy signal)
- Large pending sells = Distribution incoming (precognitive exit signal)
- Sandwich attacks detected = Someone's about to get rekt

This gives us a ~12 second edge on Ethereum, ~0.4 second on Solana.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Set
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class MempoolPressure(Enum):
    """Mempool pressure levels"""
    EXTREME_BUY = "extreme_buy"       # Whale buy incoming
    HIGH_BUY = "high_buy"             # Strong buy pressure
    MODERATE_BUY = "moderate_buy"     # Some buy pressure
    NEUTRAL = "neutral"               # Balanced
    MODERATE_SELL = "moderate_sell"   # Some sell pressure
    HIGH_SELL = "high_sell"           # Strong sell pressure
    EXTREME_SELL = "extreme_sell"     # Whale dump incoming


class TransactionType(Enum):
    """Types of transactions detected"""
    SWAP = "swap"
    TRANSFER = "transfer"
    LIQUIDITY_ADD = "liquidity_add"
    LIQUIDITY_REMOVE = "liquidity_remove"
    SANDWICH_FRONT = "sandwich_front"
    SANDWICH_BACK = "sandwich_back"
    ARBITRAGE = "arbitrage"
    UNKNOWN = "unknown"


@dataclass
class PendingTransaction:
    """A pending transaction in the mempool"""
    tx_hash: str
    from_address: str
    to_address: str
    value_eth: float          # Value in ETH/SOL
    value_usd: float          # Estimated USD value
    gas_price_gwei: float     # Gas price (indicates urgency)
    tx_type: TransactionType
    asset_involved: str       # e.g., "BTC/USDT", "ETH/USDT"
    direction: str            # "BUY", "SELL", "NEUTRAL"
    is_whale: bool            # True if > threshold
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'tx_hash': self.tx_hash[:16] + '...',
            'from': self.from_address[:10] + '...',
            'value_eth': round(self.value_eth, 4),
            'value_usd': round(self.value_usd, 2),
            'gas_price': round(self.gas_price_gwei, 2),
            'type': self.tx_type.value,
            'asset': self.asset_involved,
            'direction': self.direction,
            'is_whale': self.is_whale,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class MempoolSnapshot:
    """Current state of the mempool for an asset"""
    asset: str
    pending_buy_volume: float      # ETH/SOL pending to buy
    pending_sell_volume: float     # ETH/SOL pending to sell
    pending_buy_usd: float         # USD value
    pending_sell_usd: float        # USD value
    whale_txs_buy: int             # Number of whale buy txs
    whale_txs_sell: int            # Number of whale sell txs
    avg_gas_price: float           # Average gas (urgency indicator)
    pressure: MempoolPressure
    precognition_signal: str       # "BUY", "SELL", "NEUTRAL"
    confidence: float              # Signal confidence
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'asset': self.asset,
            'pending_buy_volume': round(self.pending_buy_volume, 4),
            'pending_sell_volume': round(self.pending_sell_volume, 4),
            'pending_buy_usd': round(self.pending_buy_usd, 2),
            'pending_sell_usd': round(self.pending_sell_usd, 2),
            'whale_buys': self.whale_txs_buy,
            'whale_sells': self.whale_txs_sell,
            'avg_gas': round(self.avg_gas_price, 2),
            'pressure': self.pressure.value,
            'signal': self.precognition_signal,
            'confidence': round(self.confidence, 3),
            'timestamp': self.timestamp.isoformat()
        }


class MempoolScanner:
    """
    THE PRE-COGNITIVE EYE
    ======================
    Scans the mempool for pending whale transactions.

    In production, connects to:
    - Ethereum mempool via Flashbots/Alchemy
    - Solana Geyser plugin
    - BSC mempool

    For now, simulates realistic mempool behavior.
    """

    def __init__(
        self,
        simulation_mode: bool = True,
        whale_threshold_eth: float = 100.0,    # 100 ETH = whale
        whale_threshold_usd: float = 250000.0  # $250k = whale
    ):
        self.simulation_mode = simulation_mode
        self.whale_threshold_eth = whale_threshold_eth
        self.whale_threshold_usd = whale_threshold_usd

        # Pending transactions per asset
        self._pending: Dict[str, List[PendingTransaction]] = {}
        self._snapshots: Dict[str, deque] = {}

        # Simulation state (must be before _init_known_whales)
        self._rng = random.Random()
        self._base_pressure: Dict[str, float] = {}  # -1 to 1

        # Known whale addresses (simulation)
        self._known_whales: Set[str] = set()
        self._init_known_whales()

        # Price references for USD conversion
        self._price_refs = {
            'ETH': 3400.0,
            'SOL': 190.0,
            'BTC': 95000.0
        }

        # Thresholds
        self.high_pressure_threshold = 500   # ETH pending
        self.extreme_pressure_threshold = 1000

        # Callbacks
        self.on_whale_detected: Optional[Callable[[PendingTransaction], None]] = None
        self.on_pressure_change: Optional[Callable[[MempoolSnapshot], None]] = None

        logger.info("🔬 Mempool Scanner initialized (whale_threshold=%.1f ETH)", whale_threshold_eth)

    def _init_known_whales(self):
        """Initialize known whale addresses (simulation)"""
        # Generate fake whale addresses
        prefixes = ['0x1234', '0xdead', '0xbeef', '0xcafe', '0xbabe']
        for prefix in prefixes:
            for i in range(5):
                addr = f"{prefix}{''.join([self._rng.choice('0123456789abcdef') for _ in range(36)])}"
                self._known_whales.add(addr)

    def _generate_tx_hash(self) -> str:
        """Generate fake tx hash"""
        return '0x' + ''.join([self._rng.choice('0123456789abcdef') for _ in range(64)])

    def _generate_address(self, is_whale: bool = False) -> str:
        """Generate fake address"""
        if is_whale and self._known_whales:
            return self._rng.choice(list(self._known_whales))
        return '0x' + ''.join([self._rng.choice('0123456789abcdef') for _ in range(40)])

    def simulate_tick(
        self,
        asset: str = 'BTC/USDT',
        market_phase: str = 'stable',
        cvd: float = 0.0
    ) -> MempoolSnapshot:
        """
        Simulate mempool activity for one tick.
        Generates pending transactions based on market conditions.
        """
        if not self.simulation_mode:
            raise ValueError("simulate_tick only available in simulation mode")

        # Initialize if needed
        if asset not in self._pending:
            self._pending[asset] = []
            self._snapshots[asset] = deque(maxlen=100)
            self._base_pressure[asset] = 0.0

        # Clear old pending txs (simulating they got mined)
        # Keep only ~20% of pending txs between ticks
        if self._pending[asset]:
            keep_count = max(1, len(self._pending[asset]) // 5)
            self._pending[asset] = self._rng.sample(
                self._pending[asset],
                min(keep_count, len(self._pending[asset]))
            )

        # Determine base bias based on phase
        if market_phase == 'accumulation':
            buy_bias = 0.7
            whale_prob = 0.15
        elif market_phase == 'recovery':
            buy_bias = 0.65
            whale_prob = 0.10
        elif market_phase == 'euphoria':
            buy_bias = 0.8
            whale_prob = 0.20
        elif market_phase == 'crash':
            buy_bias = 0.2
            whale_prob = 0.25  # Whales exit during crashes
        else:  # stable
            buy_bias = 0.5
            whale_prob = 0.05

        # CVD influence
        if cvd > 100:
            buy_bias += 0.1
        elif cvd < -100:
            buy_bias -= 0.1
        buy_bias = max(0.1, min(0.9, buy_bias))

        # Generate new pending transactions
        num_new_txs = self._rng.randint(5, 20)

        for _ in range(num_new_txs):
            is_buy = self._rng.random() < buy_bias
            is_whale = self._rng.random() < whale_prob

            # Whale transactions are larger
            if is_whale:
                value_eth = self._rng.uniform(100, 1000)
            else:
                value_eth = self._rng.uniform(0.5, 50)

            # Determine asset type for USD conversion
            base_asset = asset.split('/')[0].upper()
            eth_price = self._price_refs.get('ETH', 3400)
            value_usd = value_eth * eth_price

            # Gas price (higher = more urgent)
            if is_whale or market_phase in ['crash', 'euphoria']:
                gas_price = self._rng.uniform(50, 200)  # Priority fee
            else:
                gas_price = self._rng.uniform(20, 50)   # Normal

            tx = PendingTransaction(
                tx_hash=self._generate_tx_hash(),
                from_address=self._generate_address(is_whale),
                to_address=self._generate_address(False),
                value_eth=value_eth,
                value_usd=value_usd,
                gas_price_gwei=gas_price,
                tx_type=TransactionType.SWAP,
                asset_involved=asset,
                direction='BUY' if is_buy else 'SELL',
                is_whale=is_whale or value_usd > self.whale_threshold_usd
            )

            self._pending[asset].append(tx)

            # Whale detection callback
            if tx.is_whale and self.on_whale_detected:
                self.on_whale_detected(tx)

        # Calculate snapshot
        snapshot = self._calculate_snapshot(asset)
        self._snapshots[asset].append(snapshot)

        # Pressure change callback
        if self.on_pressure_change:
            self.on_pressure_change(snapshot)

        return snapshot

    def _calculate_snapshot(self, asset: str) -> MempoolSnapshot:
        """Calculate current mempool state for an asset"""
        pending = self._pending.get(asset, [])

        buy_txs = [tx for tx in pending if tx.direction == 'BUY']
        sell_txs = [tx for tx in pending if tx.direction == 'SELL']

        pending_buy_vol = sum(tx.value_eth for tx in buy_txs)
        pending_sell_vol = sum(tx.value_eth for tx in sell_txs)
        pending_buy_usd = sum(tx.value_usd for tx in buy_txs)
        pending_sell_usd = sum(tx.value_usd for tx in sell_txs)

        whale_buys = len([tx for tx in buy_txs if tx.is_whale])
        whale_sells = len([tx for tx in sell_txs if tx.is_whale])

        avg_gas = sum(tx.gas_price_gwei for tx in pending) / len(pending) if pending else 30

        # Determine pressure
        net_volume = pending_buy_vol - pending_sell_vol
        net_whale = whale_buys - whale_sells

        if net_volume > self.extreme_pressure_threshold and net_whale > 0:
            pressure = MempoolPressure.EXTREME_BUY
            signal = 'PRECOGNITIVE_BUY'
            confidence = 0.9
        elif net_volume > self.high_pressure_threshold:
            pressure = MempoolPressure.HIGH_BUY
            signal = 'PRECOGNITIVE_BUY'
            confidence = 0.75
        elif net_volume > 100:
            pressure = MempoolPressure.MODERATE_BUY
            signal = 'LEAN_BUY'
            confidence = 0.6
        elif net_volume < -self.extreme_pressure_threshold and net_whale < 0:
            pressure = MempoolPressure.EXTREME_SELL
            signal = 'PRECOGNITIVE_SELL'
            confidence = 0.9
        elif net_volume < -self.high_pressure_threshold:
            pressure = MempoolPressure.HIGH_SELL
            signal = 'PRECOGNITIVE_SELL'
            confidence = 0.75
        elif net_volume < -100:
            pressure = MempoolPressure.MODERATE_SELL
            signal = 'LEAN_SELL'
            confidence = 0.6
        else:
            pressure = MempoolPressure.NEUTRAL
            signal = 'NEUTRAL'
            confidence = 0.5

        return MempoolSnapshot(
            asset=asset,
            pending_buy_volume=pending_buy_vol,
            pending_sell_volume=pending_sell_vol,
            pending_buy_usd=pending_buy_usd,
            pending_sell_usd=pending_sell_usd,
            whale_txs_buy=whale_buys,
            whale_txs_sell=whale_sells,
            avg_gas_price=avg_gas,
            pressure=pressure,
            precognition_signal=signal,
            confidence=confidence
        )

    def get_snapshot(self, asset: str) -> Optional[MempoolSnapshot]:
        """Get current mempool snapshot for asset"""
        if asset in self._pending:
            return self._calculate_snapshot(asset)
        return None

    def is_precognitive_buy(self, asset: str) -> bool:
        """Quick check if precognitive buy signal active"""
        snapshot = self.get_snapshot(asset)
        return snapshot and snapshot.precognition_signal in ['PRECOGNITIVE_BUY', 'LEAN_BUY']

    def is_precognitive_sell(self, asset: str) -> bool:
        """Quick check if precognitive sell signal active"""
        snapshot = self.get_snapshot(asset)
        return snapshot and snapshot.precognition_signal in ['PRECOGNITIVE_SELL', 'LEAN_SELL']

    def get_pressure_score(self, asset: str) -> float:
        """Get pressure as a score from -1 (extreme sell) to +1 (extreme buy)"""
        snapshot = self.get_snapshot(asset)
        if not snapshot:
            return 0.0

        pressure_scores = {
            MempoolPressure.EXTREME_BUY: 1.0,
            MempoolPressure.HIGH_BUY: 0.7,
            MempoolPressure.MODERATE_BUY: 0.4,
            MempoolPressure.NEUTRAL: 0.0,
            MempoolPressure.MODERATE_SELL: -0.4,
            MempoolPressure.HIGH_SELL: -0.7,
            MempoolPressure.EXTREME_SELL: -1.0,
        }
        return pressure_scores.get(snapshot.pressure, 0.0)

    def get_stats(self) -> Dict:
        """Get scanner statistics"""
        return {
            'simulation_mode': self.simulation_mode,
            'tracked_assets': list(self._pending.keys()),
            'whale_threshold_eth': self.whale_threshold_eth,
            'whale_threshold_usd': self.whale_threshold_usd,
            'known_whales': len(self._known_whales),
            'snapshots': {
                asset: self._calculate_snapshot(asset).to_dict()
                for asset in self._pending.keys()
            }
        }


# Singleton instance
_mempool_scanner: Optional[MempoolScanner] = None


def get_mempool_scanner() -> MempoolScanner:
    """Get or create global mempool scanner instance"""
    global _mempool_scanner
    if _mempool_scanner is None:
        _mempool_scanner = MempoolScanner(simulation_mode=True)
    return _mempool_scanner


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("  THE MEMPOOL SCANNER - Pre-Cognition")
    print("="*70 + "\n")

    scanner = MempoolScanner(simulation_mode=True)

    # Whale detection callback
    def on_whale(tx):
        print(f"  🐋 WHALE DETECTED: {tx.direction} {tx.value_eth:.1f} ETH (${tx.value_usd:,.0f})")

    scanner.on_whale_detected = on_whale

    # Simulate different phases
    phases = ['accumulation', 'recovery', 'euphoria', 'crash', 'stable']

    for phase in phases:
        print(f"\n{'─'*70}")
        print(f"  PHASE: {phase.upper()}")
        print(f"{'─'*70}")

        # Run a few ticks
        for i in range(3):
            snapshot = scanner.simulate_tick(
                asset='BTC/USDT',
                market_phase=phase,
                cvd=100 if phase in ['accumulation', 'recovery'] else -100 if phase == 'crash' else 0
            )

        print(f"\n  Pending Buy:  {snapshot.pending_buy_volume:.1f} ETH (${snapshot.pending_buy_usd:,.0f})")
        print(f"  Pending Sell: {snapshot.pending_sell_volume:.1f} ETH (${snapshot.pending_sell_usd:,.0f})")
        print(f"  Whale Buys:   {snapshot.whale_txs_buy}")
        print(f"  Whale Sells:  {snapshot.whale_txs_sell}")
        print(f"  Avg Gas:      {snapshot.avg_gas_price:.1f} gwei")
        print(f"\n  PRESSURE: {snapshot.pressure.value.upper()}")
        print(f"  SIGNAL:   {snapshot.precognition_signal}")
        print(f"  Confidence: {snapshot.confidence:.0%}")

    print(f"\n{'='*70}\n")
