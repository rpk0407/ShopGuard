"""
THE PREDICTION ORACLE - Truth from Prediction Markets
======================================================
Integration Target: Bio-Cortex

Prediction markets represent "real money" opinions vs social media hype.
When Twitter is screaming bullish but Polymarket odds are dropping,
that's a FALSE_NARRATIVE signal.

The Truth_Divergence Signal:
- High Viral_K + High Odds = VERIFIED_HYPE (Go!)
- High Viral_K + Low Odds = FAKE_PUMP (Run!)
- Low Viral_K + High Odds = SMART_MONEY_QUIET (Watch)
- Low Viral_K + Low Odds = DEAD_CAT (Avoid)
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class NarrativeSignal(Enum):
    """Truth vs Hype divergence signals"""
    VERIFIED_HYPE = "verified_hype"       # Hype backed by real money
    FAKE_PUMP = "fake_pump"               # Hype without conviction
    SMART_MONEY_QUIET = "smart_money_quiet"  # Truth without hype
    DEAD_CAT = "dead_cat"                 # Neither hype nor conviction
    NEUTRAL = "neutral"                   # No clear signal


@dataclass
class PredictionEvent:
    """A prediction market event (e.g., 'BTC > $100k by EOY')"""
    event_id: str
    title: str
    asset: str
    threshold: float
    deadline: datetime

    # Current market state
    yes_price: float      # 0.0 - 1.0 (probability)
    no_price: float       # 0.0 - 1.0
    volume_24h: float     # USD volume
    liquidity: float      # Total liquidity in market

    # Momentum
    yes_price_1h_ago: float = 0.5
    yes_price_24h_ago: float = 0.5

    # Computed
    momentum_1h: float = 0.0
    momentum_24h: float = 0.0

    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.momentum_1h = self.yes_price - self.yes_price_1h_ago
        self.momentum_24h = self.yes_price - self.yes_price_24h_ago

    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'title': self.title,
            'asset': self.asset,
            'threshold': self.threshold,
            'deadline': self.deadline.isoformat(),
            'yes_price': round(self.yes_price, 4),
            'no_price': round(self.no_price, 4),
            'odds_pct': round(self.yes_price * 100, 2),
            'volume_24h': round(self.volume_24h, 2),
            'liquidity': round(self.liquidity, 2),
            'momentum_1h': round(self.momentum_1h, 4),
            'momentum_24h': round(self.momentum_24h, 4),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TruthDivergence:
    """Analysis of truth vs hype divergence"""
    signal: NarrativeSignal
    prediction_odds: float      # 0.0 - 1.0
    viral_k: float              # From Bio-Cortex
    divergence_score: float     # How much they diverge
    confidence: float           # Signal confidence
    reasoning: str

    def to_dict(self) -> Dict:
        return {
            'signal': self.signal.value,
            'prediction_odds': round(self.prediction_odds, 4),
            'viral_k': round(self.viral_k, 3),
            'divergence_score': round(self.divergence_score, 4),
            'confidence': round(self.confidence, 3),
            'reasoning': self.reasoning
        }


class PredictionOracle:
    """
    THE ORACLE OF TRUTH
    ====================
    Fetches and analyzes prediction market data.

    In production, connects to:
    - Polymarket API
    - Kalshi API
    - Metaculus API

    For now, simulates realistic market behavior.
    """

    def __init__(self, simulation_mode: bool = True):
        self.simulation_mode = simulation_mode
        self._events: Dict[str, PredictionEvent] = {}
        self._history: Dict[str, List[PredictionEvent]] = {}

        # Thresholds for signal generation
        self.high_odds_threshold = 0.60   # Above = bullish prediction
        self.low_odds_threshold = 0.40    # Below = bearish prediction
        self.high_viral_threshold = 1.2   # Above = hype mode
        self.low_viral_threshold = 0.9    # Below = quiet

        # Simulation state
        self._rng = random.Random()
        self._base_odds: Dict[str, float] = {}

        # Initialize default events
        self._init_default_events()

        # Callbacks
        self.on_divergence: Optional[Callable[[TruthDivergence], None]] = None

        logger.info("🔮 Prediction Oracle initialized (simulation_mode=%s)", simulation_mode)

    def _init_default_events(self):
        """Initialize default prediction events for major assets"""
        now = datetime.now()

        default_events = [
            {
                'event_id': 'btc_100k_2025',
                'title': 'Bitcoin above $100,000 by March 2025',
                'asset': 'BTC/USDT',
                'threshold': 100000,
                'deadline': datetime(2025, 3, 31),
                'base_odds': 0.65
            },
            {
                'event_id': 'eth_5k_2025',
                'title': 'Ethereum above $5,000 by June 2025',
                'asset': 'ETH/USDT',
                'threshold': 5000,
                'deadline': datetime(2025, 6, 30),
                'base_odds': 0.45
            },
            {
                'event_id': 'sol_300_2025',
                'title': 'Solana above $300 by March 2025',
                'asset': 'SOL/USDT',
                'threshold': 300,
                'deadline': datetime(2025, 3, 31),
                'base_odds': 0.55
            },
            {
                'event_id': 'btc_150k_2025',
                'title': 'Bitcoin above $150,000 by December 2025',
                'asset': 'BTC/USDT',
                'threshold': 150000,
                'deadline': datetime(2025, 12, 31),
                'base_odds': 0.35
            }
        ]

        for evt in default_events:
            self._base_odds[evt['event_id']] = evt['base_odds']

            event = PredictionEvent(
                event_id=evt['event_id'],
                title=evt['title'],
                asset=evt['asset'],
                threshold=evt['threshold'],
                deadline=evt['deadline'],
                yes_price=evt['base_odds'],
                no_price=1 - evt['base_odds'],
                volume_24h=self._rng.uniform(500000, 5000000),
                liquidity=self._rng.uniform(1000000, 10000000),
                yes_price_1h_ago=evt['base_odds'],
                yes_price_24h_ago=evt['base_odds']
            )
            self._events[evt['event_id']] = event
            self._history[evt['event_id']] = [event]

    def get_event(self, event_id: str) -> Optional[PredictionEvent]:
        """Get a specific prediction event"""
        return self._events.get(event_id)

    def get_events_for_asset(self, asset: str) -> List[PredictionEvent]:
        """Get all prediction events for an asset"""
        return [e for e in self._events.values() if e.asset == asset]

    def get_primary_odds(self, asset: str) -> float:
        """Get the primary prediction odds for an asset (highest liquidity event)"""
        events = self.get_events_for_asset(asset)
        if not events:
            return 0.5  # Neutral if no events

        # Return highest liquidity event
        primary = max(events, key=lambda e: e.liquidity)
        return primary.yes_price

    def simulate_tick(self, market_phase: str = 'stable', price_momentum: float = 0.0) -> Dict[str, PredictionEvent]:
        """
        Simulate prediction market tick.
        Odds move based on market phase and price momentum.
        """
        if not self.simulation_mode:
            raise ValueError("simulate_tick only available in simulation mode")

        for event_id, event in self._events.items():
            # Store previous for momentum calc
            old_price = event.yes_price
            event.yes_price_1h_ago = event.yes_price

            # Base drift based on phase
            if market_phase == 'accumulation':
                drift = 0.002  # Slowly bullish
            elif market_phase == 'recovery':
                drift = 0.005  # Bullish
            elif market_phase == 'euphoria':
                drift = 0.01   # Very bullish
            elif market_phase == 'crash':
                drift = -0.02  # Bearish
            else:
                drift = 0.0    # Stable

            # Add price momentum influence
            drift += price_momentum * 0.1

            # Random walk component
            noise = self._rng.gauss(0, 0.015)

            # Update odds with mean reversion to base
            base = self._base_odds.get(event_id, 0.5)
            mean_reversion = (base - event.yes_price) * 0.05

            new_price = event.yes_price + drift + noise + mean_reversion
            event.yes_price = max(0.05, min(0.95, new_price))
            event.no_price = 1 - event.yes_price

            # Update momentum
            event.momentum_1h = event.yes_price - event.yes_price_1h_ago

            # Update volume (spikes in volatile phases)
            base_volume = 1000000
            if market_phase in ['euphoria', 'crash']:
                volume_mult = 3.0
            elif market_phase in ['accumulation', 'recovery']:
                volume_mult = 1.5
            else:
                volume_mult = 1.0

            event.volume_24h = base_volume * volume_mult * self._rng.uniform(0.5, 2.0)
            event.timestamp = datetime.now()

            # Store history
            self._history[event_id].append(PredictionEvent(**{
                **event.__dict__
            }))
            if len(self._history[event_id]) > 100:
                self._history[event_id] = self._history[event_id][-100:]

        return self._events

    def analyze_truth_divergence(
        self,
        asset: str,
        viral_k: float,
        market_phase: str = 'stable'
    ) -> TruthDivergence:
        """
        THE TRUTH DIVERGENCE SIGNAL
        ============================
        Compare prediction market odds (real money) vs viral sentiment (hype).

        Returns signal indicating whether hype is backed by conviction.
        """
        prediction_odds = self.get_primary_odds(asset)

        # Calculate divergence
        # Normalize viral_k to 0-1 scale (assuming 0.5-2.0 range)
        normalized_viral = (viral_k - 0.5) / 1.5
        normalized_viral = max(0, min(1, normalized_viral))

        # Divergence = difference between hype and truth
        divergence_score = abs(normalized_viral - prediction_odds)

        # Determine signal
        high_viral = viral_k > self.high_viral_threshold
        low_viral = viral_k < self.low_viral_threshold
        high_odds = prediction_odds > self.high_odds_threshold
        low_odds = prediction_odds < self.low_odds_threshold

        if high_viral and high_odds:
            signal = NarrativeSignal.VERIFIED_HYPE
            reasoning = f"Viral K={viral_k:.2f} (HIGH) + Prediction Odds={prediction_odds:.0%} (HIGH) = Real money backs the hype"
            confidence = min(0.95, (viral_k - 1.0) * (prediction_odds - 0.5) * 4)

        elif high_viral and low_odds:
            signal = NarrativeSignal.FAKE_PUMP
            reasoning = f"Viral K={viral_k:.2f} (HIGH) but Prediction Odds={prediction_odds:.0%} (LOW) = Hype without conviction!"
            confidence = min(0.90, divergence_score * 2)

        elif low_viral and high_odds:
            signal = NarrativeSignal.SMART_MONEY_QUIET
            reasoning = f"Viral K={viral_k:.2f} (LOW) but Prediction Odds={prediction_odds:.0%} (HIGH) = Smart money positioning quietly"
            confidence = min(0.85, (prediction_odds - 0.5) * 2)

        elif low_viral and low_odds:
            signal = NarrativeSignal.DEAD_CAT
            reasoning = f"Viral K={viral_k:.2f} (LOW) + Prediction Odds={prediction_odds:.0%} (LOW) = No conviction anywhere"
            confidence = min(0.80, (1 - prediction_odds) * (1.5 - viral_k) * 2)

        else:
            signal = NarrativeSignal.NEUTRAL
            reasoning = f"Viral K={viral_k:.2f} + Prediction Odds={prediction_odds:.0%} = Mixed signals"
            confidence = 0.5

        result = TruthDivergence(
            signal=signal,
            prediction_odds=prediction_odds,
            viral_k=viral_k,
            divergence_score=divergence_score,
            confidence=max(0, min(1, confidence)),
            reasoning=reasoning
        )

        # Callback
        if self.on_divergence and signal not in [NarrativeSignal.NEUTRAL]:
            self.on_divergence(result)

        return result

    def get_stats(self) -> Dict:
        """Get oracle statistics"""
        return {
            'simulation_mode': self.simulation_mode,
            'tracked_events': len(self._events),
            'events': {eid: e.to_dict() for eid, e in self._events.items()}
        }


# Singleton instance
_prediction_oracle: Optional[PredictionOracle] = None


def get_prediction_oracle() -> PredictionOracle:
    """Get or create global prediction oracle instance"""
    global _prediction_oracle
    if _prediction_oracle is None:
        _prediction_oracle = PredictionOracle(simulation_mode=True)
    return _prediction_oracle


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("  THE PREDICTION ORACLE - Truth vs Hype")
    print("="*70 + "\n")

    oracle = PredictionOracle(simulation_mode=True)

    # Simulate different scenarios
    test_cases = [
        {'viral_k': 1.5, 'phase': 'euphoria', 'desc': 'High Hype + Bullish Market'},
        {'viral_k': 1.4, 'phase': 'stable', 'desc': 'High Hype + Stable Market'},
        {'viral_k': 0.7, 'phase': 'accumulation', 'desc': 'Low Hype + Accumulation'},
        {'viral_k': 1.3, 'phase': 'crash', 'desc': 'High Hype + Crash (FAKE PUMP?)'},
    ]

    for tc in test_cases:
        print(f"\n{'─'*70}")
        print(f"  SCENARIO: {tc['desc']}")
        print(f"{'─'*70}")

        # Simulate a few ticks to move odds
        for _ in range(5):
            oracle.simulate_tick(market_phase=tc['phase'])

        # Analyze BTC
        divergence = oracle.analyze_truth_divergence('BTC/USDT', tc['viral_k'], tc['phase'])

        print(f"\n  Signal: {divergence.signal.value.upper()}")
        print(f"  Prediction Odds: {divergence.prediction_odds:.1%}")
        print(f"  Viral K: {divergence.viral_k:.2f}")
        print(f"  Divergence: {divergence.divergence_score:.3f}")
        print(f"  Confidence: {divergence.confidence:.1%}")
        print(f"\n  Reasoning: {divergence.reasoning}")

    print(f"\n{'='*70}\n")
