"""
THE ON-CHAIN TRACKER - Smart Money Wallet Analysis
===================================================
Integration Target: Physics-Cortex

Track specific "Smart Money" wallets - the traders with proven track records.
When they accumulate in low-entropy conditions, confidence goes to the moon.

The INSIDER_ACCUMULATION Signal:
- Smart Money buying + Low Entropy = High conviction setup
- Smart Money selling + High Entropy = Exit immediately
- Smart Money idle = Wait for clarity

Tracked Entities:
- Known fund wallets (Alameda survivors, Jump, etc.)
- High-win-rate DEX traders
- Protocol treasury wallets
- Exchange cold wallets (for flow analysis)
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


class SmartMoneySignal(Enum):
    """Smart money activity signals"""
    HEAVY_ACCUMULATION = "heavy_accumulation"     # Major buying
    ACCUMULATION = "accumulation"                 # Moderate buying
    IDLE = "idle"                                 # No significant activity
    DISTRIBUTION = "distribution"                 # Moderate selling
    HEAVY_DISTRIBUTION = "heavy_distribution"     # Major selling
    MIXED = "mixed"                               # Conflicting signals


class WalletType(Enum):
    """Types of tracked wallets"""
    FUND = "fund"                    # Investment fund
    DEX_TRADER = "dex_trader"        # High-win-rate trader
    PROTOCOL = "protocol"            # Protocol treasury
    EXCHANGE = "exchange"            # Exchange wallet
    WHALE = "whale"                  # Unknown whale
    INSIDER = "insider"              # Suspected insider


@dataclass
class WalletProfile:
    """Profile of a tracked wallet"""
    address: str
    label: str
    wallet_type: WalletType
    win_rate: float           # Historical win rate
    avg_trade_size_usd: float
    total_volume_usd: float
    last_active: datetime
    is_active: bool = True

    def to_dict(self) -> Dict:
        return {
            'address': self.address[:10] + '...',
            'label': self.label,
            'type': self.wallet_type.value,
            'win_rate': round(self.win_rate, 3),
            'avg_trade_usd': round(self.avg_trade_size_usd, 2),
            'total_volume': round(self.total_volume_usd, 2),
            'last_active': self.last_active.isoformat(),
            'is_active': self.is_active
        }


@dataclass
class WalletActivity:
    """Recent activity from a tracked wallet"""
    wallet: WalletProfile
    action: str               # "BUY", "SELL", "TRANSFER"
    asset: str                # e.g., "BTC/USDT"
    amount_usd: float
    tx_hash: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'wallet': self.wallet.label,
            'action': self.action,
            'asset': self.asset,
            'amount_usd': round(self.amount_usd, 2),
            'tx_hash': self.tx_hash[:16] + '...',
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class SmartMoneySnapshot:
    """Current smart money flow analysis"""
    asset: str
    signal: SmartMoneySignal

    # Aggregate flows
    total_buy_usd: float
    total_sell_usd: float
    net_flow_usd: float

    # Wallet breakdown
    active_wallets: int
    buying_wallets: int
    selling_wallets: int

    # Top movers
    top_buyer: Optional[str]
    top_seller: Optional[str]

    # Confidence
    confidence: float
    reasoning: str

    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'asset': self.asset,
            'signal': self.signal.value,
            'total_buy_usd': round(self.total_buy_usd, 2),
            'total_sell_usd': round(self.total_sell_usd, 2),
            'net_flow_usd': round(self.net_flow_usd, 2),
            'active_wallets': self.active_wallets,
            'buying_wallets': self.buying_wallets,
            'selling_wallets': self.selling_wallets,
            'top_buyer': self.top_buyer,
            'top_seller': self.top_seller,
            'confidence': round(self.confidence, 3),
            'reasoning': self.reasoning,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class InsiderConfidence:
    """Insider accumulation confidence boost"""
    signal: SmartMoneySignal
    smart_money_buying: bool
    entropy: float
    base_confidence: float
    boosted_confidence: float
    boost_reason: str

    def to_dict(self) -> Dict:
        return {
            'signal': self.signal.value,
            'smart_money_buying': self.smart_money_buying,
            'entropy': round(self.entropy, 4),
            'base_confidence': round(self.base_confidence, 3),
            'boosted_confidence': round(self.boosted_confidence, 3),
            'boost_reason': self.boost_reason
        }


class OnChainTracker:
    """
    THE INSIDER'S EYE
    ==================
    Tracks smart money wallets on-chain.

    In production, connects to:
    - Etherscan API
    - Solscan API
    - Arkham Intelligence
    - Nansen labels

    For now, simulates realistic smart money behavior.
    """

    def __init__(
        self,
        simulation_mode: bool = True,
        significant_flow_usd: float = 100000.0  # $100k = significant
    ):
        self.simulation_mode = simulation_mode
        self.significant_flow_usd = significant_flow_usd

        # Simulation state (must be before _init_tracked_wallets)
        self._rng = random.Random()

        # Tracked wallets
        self._wallets: Dict[str, WalletProfile] = {}
        self._init_tracked_wallets()

        # Recent activity per asset
        self._activity: Dict[str, List[WalletActivity]] = {}
        self._snapshots: Dict[str, deque] = {}

        # Thresholds
        self.heavy_flow_threshold = 1000000  # $1M
        self.moderate_flow_threshold = 250000  # $250k

        # Callbacks
        self.on_smart_money_move: Optional[Callable[[WalletActivity], None]] = None
        self.on_signal_change: Optional[Callable[[SmartMoneySnapshot], None]] = None

        logger.info("🎯 On-Chain Tracker initialized (tracking %d wallets)", len(self._wallets))

    def _generate_address(self) -> str:
        """Generate fake address"""
        return '0x' + ''.join([self._rng.choice('0123456789abcdef') for _ in range(40)])

    def _init_tracked_wallets(self):
        """Initialize tracked smart money wallets (simulation)"""
        wallets = [
            # Funds
            ('Alpha Fund', WalletType.FUND, 0.72, 500000),
            ('Beta Capital', WalletType.FUND, 0.68, 750000),
            ('Gamma Ventures', WalletType.FUND, 0.75, 1000000),
            ('Delta Investments', WalletType.FUND, 0.65, 350000),

            # High-win-rate traders
            ('Trader X', WalletType.DEX_TRADER, 0.78, 150000),
            ('The Oracle', WalletType.DEX_TRADER, 0.82, 200000),
            ('Silent Whale', WalletType.DEX_TRADER, 0.71, 500000),
            ('Sniper Bot', WalletType.DEX_TRADER, 0.69, 100000),

            # Protocol treasuries
            ('Uniswap Treasury', WalletType.PROTOCOL, 0.60, 2000000),
            ('Aave Treasury', WalletType.PROTOCOL, 0.58, 1500000),

            # Exchanges (for flow analysis)
            ('Binance Hot', WalletType.EXCHANGE, 0.50, 10000000),
            ('Coinbase Cold', WalletType.EXCHANGE, 0.50, 5000000),

            # Known whales
            ('Genesis Whale', WalletType.WHALE, 0.65, 3000000),
            ('Early Adopter', WalletType.WHALE, 0.70, 800000),

            # Suspected insiders
            ('Insider A', WalletType.INSIDER, 0.85, 400000),
            ('Insider B', WalletType.INSIDER, 0.88, 300000),
        ]

        for label, wallet_type, win_rate, avg_size in wallets:
            address = self._generate_address()
            self._wallets[address] = WalletProfile(
                address=address,
                label=label,
                wallet_type=wallet_type,
                win_rate=win_rate,
                avg_trade_size_usd=avg_size,
                total_volume_usd=avg_size * self._rng.randint(50, 200),
                last_active=datetime.now() - timedelta(hours=self._rng.randint(1, 72))
            )

    def get_wallet_by_label(self, label: str) -> Optional[WalletProfile]:
        """Get wallet by label"""
        for wallet in self._wallets.values():
            if wallet.label == label:
                return wallet
        return None

    def get_high_win_rate_wallets(self, min_win_rate: float = 0.70) -> List[WalletProfile]:
        """Get wallets with high win rate"""
        return [w for w in self._wallets.values() if w.win_rate >= min_win_rate]

    def simulate_tick(
        self,
        asset: str = 'BTC/USDT',
        market_phase: str = 'stable',
        entropy: float = 0.5
    ) -> SmartMoneySnapshot:
        """
        Simulate smart money activity for one tick.
        Smart money tends to buy low entropy and sell high entropy.
        """
        if not self.simulation_mode:
            raise ValueError("simulate_tick only available in simulation mode")

        # Initialize if needed
        if asset not in self._activity:
            self._activity[asset] = []
            self._snapshots[asset] = deque(maxlen=100)

        # Clear old activity (keep last 20)
        if len(self._activity[asset]) > 20:
            self._activity[asset] = self._activity[asset][-20:]

        # Determine smart money behavior based on conditions
        # Low entropy = smart money buys
        # High entropy = smart money sells
        # Phase also influences

        if entropy < 0.4:  # Low entropy - smart money accumulates
            buy_prob = 0.8
            activity_level = 'high'
        elif entropy < 0.6:  # Moderate - normal activity
            buy_prob = 0.55
            activity_level = 'normal'
        else:  # High entropy - smart money exits
            buy_prob = 0.2
            activity_level = 'high'  # High activity but selling

        # Phase modifiers
        if market_phase == 'accumulation':
            buy_prob += 0.15
        elif market_phase == 'crash':
            buy_prob -= 0.2
        elif market_phase == 'euphoria':
            buy_prob -= 0.1  # Smart money sells into euphoria

        buy_prob = max(0.1, min(0.9, buy_prob))

        # How many wallets are active this tick
        if activity_level == 'high':
            active_count = self._rng.randint(4, 8)
        else:
            active_count = self._rng.randint(1, 4)

        # Generate activity
        active_wallets = self._rng.sample(list(self._wallets.values()), min(active_count, len(self._wallets)))

        for wallet in active_wallets:
            is_buy = self._rng.random() < buy_prob

            # Trade size based on wallet profile
            size_mult = self._rng.uniform(0.5, 2.0)
            amount = wallet.avg_trade_size_usd * size_mult

            activity = WalletActivity(
                wallet=wallet,
                action='BUY' if is_buy else 'SELL',
                asset=asset,
                amount_usd=amount,
                tx_hash='0x' + ''.join([self._rng.choice('0123456789abcdef') for _ in range(64)])
            )

            self._activity[asset].append(activity)
            wallet.last_active = datetime.now()

            # Callback for significant moves
            if amount >= self.significant_flow_usd and self.on_smart_money_move:
                self.on_smart_money_move(activity)

        # Calculate snapshot
        snapshot = self._calculate_snapshot(asset)
        self._snapshots[asset].append(snapshot)

        if self.on_signal_change:
            self.on_signal_change(snapshot)

        return snapshot

    def _calculate_snapshot(self, asset: str) -> SmartMoneySnapshot:
        """Calculate current smart money flow"""
        activities = self._activity.get(asset, [])

        # Recent activity only (last 10 minutes simulated)
        recent = activities[-20:]  # Last 20 activities

        buy_activities = [a for a in recent if a.action == 'BUY']
        sell_activities = [a for a in recent if a.action == 'SELL']

        total_buy = sum(a.amount_usd for a in buy_activities)
        total_sell = sum(a.amount_usd for a in sell_activities)
        net_flow = total_buy - total_sell

        buying_wallets = len(set(a.wallet.address for a in buy_activities))
        selling_wallets = len(set(a.wallet.address for a in sell_activities))
        active_wallets = len(set(a.wallet.address for a in recent))

        # Top movers
        top_buyer = max(buy_activities, key=lambda a: a.amount_usd).wallet.label if buy_activities else None
        top_seller = max(sell_activities, key=lambda a: a.amount_usd).wallet.label if sell_activities else None

        # Determine signal
        if net_flow > self.heavy_flow_threshold:
            signal = SmartMoneySignal.HEAVY_ACCUMULATION
            confidence = 0.9
            reasoning = f"Smart money accumulating heavily (${net_flow:,.0f} net inflow)"
        elif net_flow > self.moderate_flow_threshold:
            signal = SmartMoneySignal.ACCUMULATION
            confidence = 0.75
            reasoning = f"Smart money accumulating (${net_flow:,.0f} net inflow)"
        elif net_flow < -self.heavy_flow_threshold:
            signal = SmartMoneySignal.HEAVY_DISTRIBUTION
            confidence = 0.9
            reasoning = f"Smart money distributing heavily (${abs(net_flow):,.0f} net outflow)"
        elif net_flow < -self.moderate_flow_threshold:
            signal = SmartMoneySignal.DISTRIBUTION
            confidence = 0.75
            reasoning = f"Smart money distributing (${abs(net_flow):,.0f} net outflow)"
        elif buying_wallets > 0 and selling_wallets > 0 and abs(net_flow) < self.moderate_flow_threshold:
            signal = SmartMoneySignal.MIXED
            confidence = 0.5
            reasoning = "Mixed signals from smart money"
        else:
            signal = SmartMoneySignal.IDLE
            confidence = 0.5
            reasoning = "Smart money relatively quiet"

        return SmartMoneySnapshot(
            asset=asset,
            signal=signal,
            total_buy_usd=total_buy,
            total_sell_usd=total_sell,
            net_flow_usd=net_flow,
            active_wallets=active_wallets,
            buying_wallets=buying_wallets,
            selling_wallets=selling_wallets,
            top_buyer=top_buyer,
            top_seller=top_seller,
            confidence=confidence,
            reasoning=reasoning
        )

    def calculate_insider_confidence(
        self,
        asset: str,
        entropy: float,
        base_confidence: float
    ) -> InsiderConfidence:
        """
        THE INSIDER ACCUMULATION BOOST
        ================================
        When smart money is buying AND entropy is low (structure),
        we boost confidence significantly.

        Rules:
        - Smart Money Buying + Entropy < 0.5 = 99% confidence
        - Smart Money Buying + Entropy > 0.7 = Suspicious, no boost
        - Smart Money Selling = Reduce confidence
        """
        snapshot = self._calculate_snapshot(asset)
        smart_money_buying = snapshot.signal in [
            SmartMoneySignal.ACCUMULATION,
            SmartMoneySignal.HEAVY_ACCUMULATION
        ]
        smart_money_selling = snapshot.signal in [
            SmartMoneySignal.DISTRIBUTION,
            SmartMoneySignal.HEAVY_DISTRIBUTION
        ]

        if smart_money_buying and entropy < 0.5:
            # GOLDEN SETUP: Smart money + clean structure
            boost = min(0.99, base_confidence + 0.25)
            reason = "INSIDER ACCUMULATION: Smart money buying in low-entropy structure. Max conviction!"

        elif smart_money_buying and entropy < 0.7:
            # Good but not perfect
            boost = min(0.90, base_confidence + 0.15)
            reason = "Smart money accumulating, moderate structure. Good setup."

        elif smart_money_buying and entropy >= 0.7:
            # Suspicious - why buy in chaos?
            boost = base_confidence
            reason = "Smart money buying in chaos - suspicious, no confidence boost."

        elif smart_money_selling and entropy > 0.6:
            # Smart money exiting in chaos - DANGER
            boost = max(0.3, base_confidence - 0.20)
            reason = "WARNING: Smart money distributing in chaotic conditions. Exit recommended."

        elif smart_money_selling:
            # Smart money exiting
            boost = max(0.4, base_confidence - 0.15)
            reason = "Smart money distributing. Reduce exposure."

        else:
            # Neutral
            boost = base_confidence
            reason = "Smart money neutral. No confidence adjustment."

        return InsiderConfidence(
            signal=snapshot.signal,
            smart_money_buying=smart_money_buying,
            entropy=entropy,
            base_confidence=base_confidence,
            boosted_confidence=boost,
            boost_reason=reason
        )

    def get_snapshot(self, asset: str) -> Optional[SmartMoneySnapshot]:
        """Get current smart money snapshot for asset"""
        if asset in self._activity:
            return self._calculate_snapshot(asset)
        return None

    def is_accumulating(self, asset: str) -> bool:
        """Quick check if smart money is accumulating"""
        snapshot = self.get_snapshot(asset)
        return snapshot and snapshot.signal in [
            SmartMoneySignal.ACCUMULATION,
            SmartMoneySignal.HEAVY_ACCUMULATION
        ]

    def is_distributing(self, asset: str) -> bool:
        """Quick check if smart money is distributing"""
        snapshot = self.get_snapshot(asset)
        return snapshot and snapshot.signal in [
            SmartMoneySignal.DISTRIBUTION,
            SmartMoneySignal.HEAVY_DISTRIBUTION
        ]

    def get_stats(self) -> Dict:
        """Get tracker statistics"""
        return {
            'simulation_mode': self.simulation_mode,
            'tracked_wallets': len(self._wallets),
            'high_win_rate_wallets': len(self.get_high_win_rate_wallets()),
            'significant_flow_threshold': self.significant_flow_usd,
            'wallet_types': {
                wtype.value: len([w for w in self._wallets.values() if w.wallet_type == wtype])
                for wtype in WalletType
            }
        }


# Singleton instance
_onchain_tracker: Optional[OnChainTracker] = None


def get_onchain_tracker() -> OnChainTracker:
    """Get or create global on-chain tracker instance"""
    global _onchain_tracker
    if _onchain_tracker is None:
        _onchain_tracker = OnChainTracker(simulation_mode=True)
    return _onchain_tracker


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("  THE ON-CHAIN TRACKER - Smart Money Analysis")
    print("="*70 + "\n")

    tracker = OnChainTracker(simulation_mode=True)

    # Smart money move callback
    def on_move(activity):
        print(f"  💰 {activity.wallet.label}: {activity.action} ${activity.amount_usd:,.0f}")

    tracker.on_smart_money_move = on_move

    # Test scenarios
    scenarios = [
        {'entropy': 0.3, 'phase': 'accumulation', 'desc': 'Low Entropy + Accumulation'},
        {'entropy': 0.5, 'phase': 'stable', 'desc': 'Normal Conditions'},
        {'entropy': 0.8, 'phase': 'crash', 'desc': 'High Entropy + Crash'},
        {'entropy': 0.4, 'phase': 'recovery', 'desc': 'Low Entropy + Recovery'},
    ]

    for scenario in scenarios:
        print(f"\n{'─'*70}")
        print(f"  SCENARIO: {scenario['desc']}")
        print(f"{'─'*70}")

        # Run a few ticks
        for _ in range(3):
            snapshot = tracker.simulate_tick(
                asset='BTC/USDT',
                market_phase=scenario['phase'],
                entropy=scenario['entropy']
            )

        print(f"\n  Net Flow: ${snapshot.net_flow_usd:,.0f}")
        print(f"  Active Wallets: {snapshot.active_wallets}")
        print(f"  Buying: {snapshot.buying_wallets} | Selling: {snapshot.selling_wallets}")
        if snapshot.top_buyer:
            print(f"  Top Buyer: {snapshot.top_buyer}")
        if snapshot.top_seller:
            print(f"  Top Seller: {snapshot.top_seller}")

        print(f"\n  SIGNAL: {snapshot.signal.value.upper()}")
        print(f"  {snapshot.reasoning}")

        # Test insider confidence boost
        insider = tracker.calculate_insider_confidence(
            'BTC/USDT',
            entropy=scenario['entropy'],
            base_confidence=0.7
        )
        print(f"\n  Confidence: {insider.base_confidence:.0%} → {insider.boosted_confidence:.0%}")
        print(f"  Reason: {insider.boost_reason}")

    print(f"\n{'='*70}\n")
