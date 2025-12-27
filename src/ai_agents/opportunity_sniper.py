"""
Opportunity Sniper Agent

Identifies and captures high-probability opportunities:
- New cryptocurrency listings
- IPO/SPAC launches
- Trend breakouts
- Sector rotations
- Arbitrage opportunities
- Momentum plays
- Mean reversion setups
- Event-driven plays
- Gap fills
- Oversold/overbought extremes

Moves fast but smart - enters early, exits before the crowd.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum, auto
import numpy as np
from collections import deque

from .base import (
    BaseAgent, Signal, SignalStrength, MarketSnapshot,
    AgentState, generate_unique_id, normalize_confidence
)


class OpportunityType(Enum):
    """Types of trading opportunities"""
    NEW_LISTING = auto()  # New crypto/stock listing
    IPO = auto()
    SPAC = auto()
    TREND_BREAKOUT = auto()
    SECTOR_ROTATION = auto()
    ARBITRAGE = auto()
    MOMENTUM = auto()
    MEAN_REVERSION = auto()
    GAP_FILL = auto()
    OVERSOLD_BOUNCE = auto()
    OVERBOUGHT_SHORT = auto()
    NEWS_CATALYST = auto()
    EARNINGS_PLAY = auto()
    TECHNICAL_SETUP = auto()


class OpportunityQuality(Enum):
    """Quality rating of opportunity"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    EXCEPTIONAL = 4


@dataclass
class Opportunity:
    """Identified trading opportunity"""
    opportunity_id: str
    symbol: str
    opportunity_type: OpportunityType
    quality: OpportunityQuality
    direction: str  # 'long' or 'short'
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward: float
    confidence: float
    reasoning: str
    timestamp: datetime
    expiry: datetime
    urgency: int  # 1=immediate, 5=can wait
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendData:
    """Trend analysis data"""
    symbol: str
    direction: str  # 'up', 'down', 'sideways'
    strength: float  # 0-1
    duration_bars: int
    momentum: float
    acceleration: float


class OpportunitySniperAgent(BaseAgent):
    """
    Snipes high-probability trading opportunities.

    Philosophy:
    - Enter early, before the crowd
    - Exit before the crowd realizes
    - Don't chase - wait for pullbacks
    - Risk-reward must be favorable (>2:1)
    - Quality over quantity
    """

    def __init__(self):
        super().__init__(
            agent_id=generate_unique_id('opportunity_sniper'),
            name="Opportunity Sniper",
            description="Identifies and snipes high-probability opportunities"
        )

        # Price/volume history
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}

        # Opportunity tracking
        self.active_opportunities: Dict[str, Opportunity] = {}
        self.opportunity_history: deque = deque(maxlen=500)

        # Watchlists
        self.new_listings_watchlist: Set[str] = set()
        self.ipo_watchlist: Set[str] = set()
        self.breakout_watchlist: Set[str] = set()

        # Sector tracking
        self.sector_performance: Dict[str, deque] = {}

        # Configuration
        self.min_risk_reward = 2.0
        self.max_opportunities = 10  # Max concurrent opportunities
        self.min_confidence = 0.6

        # Pattern detection parameters
        self.breakout_threshold = 0.03  # 3% for breakout
        self.oversold_rsi = 30
        self.overbought_rsi = 70
        self.volume_confirmation = 1.5  # 1.5x average volume

    def analyze(self, snapshot: MarketSnapshot) -> Optional[Signal]:
        """Scan for opportunities"""
        self.state = AgentState.ANALYZING
        self.last_active = datetime.now()

        # Clean expired opportunities
        self._clean_expired()

        opportunities = []

        for symbol, price in snapshot.prices.items():
            # Update history
            self._update_history(symbol, price, snapshot.volumes.get(symbol, 0))

            # Run opportunity detection
            opps = self._find_opportunities(symbol, snapshot)
            opportunities.extend(opps)

        # Rank and filter opportunities
        opportunities = self._rank_opportunities(opportunities)

        # Store top opportunities
        for opp in opportunities[:self.max_opportunities]:
            self.active_opportunities[opp.opportunity_id] = opp
            self.opportunity_history.append(opp)

        self.state = AgentState.IDLE

        # Return highest quality opportunity as signal
        if opportunities:
            best = opportunities[0]
            return self._opportunity_to_signal(best)

        return None

    def _update_history(self, symbol: str, price: float, volume: float):
        """Update price and volume history"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=500)
            self.volume_history[symbol] = deque(maxlen=500)

        self.price_history[symbol].append({
            'price': price,
            'timestamp': datetime.now()
        })
        self.volume_history[symbol].append(volume)

    def _find_opportunities(self, symbol: str, snapshot: MarketSnapshot) -> List[Opportunity]:
        """Find all opportunities for a symbol"""
        opportunities = []

        # Breakout detection
        breakout = self._detect_breakout(symbol, snapshot)
        if breakout:
            opportunities.append(breakout)

        # Mean reversion
        mean_rev = self._detect_mean_reversion(symbol, snapshot)
        if mean_rev:
            opportunities.append(mean_rev)

        # Momentum play
        momentum = self._detect_momentum(symbol, snapshot)
        if momentum:
            opportunities.append(momentum)

        # Gap fill opportunity
        gap = self._detect_gap_fill(symbol, snapshot)
        if gap:
            opportunities.append(gap)

        # RSI extremes
        rsi_opp = self._detect_rsi_extreme(symbol, snapshot)
        if rsi_opp:
            opportunities.append(rsi_opp)

        # Technical setup (confluence)
        tech_setup = self._detect_technical_setup(symbol, snapshot)
        if tech_setup:
            opportunities.append(tech_setup)

        return opportunities

    def _detect_breakout(self, symbol: str, snapshot: MarketSnapshot) -> Optional[Opportunity]:
        """Detect breakout opportunities"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 50:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]
        volumes = list(self.volume_history[symbol])

        current = prices[-1]

        # Find consolidation range (last 20-50 bars)
        consolidation = prices[-50:-5]
        if not consolidation:
            return None

        high = max(consolidation)
        low = min(consolidation)
        range_size = (high - low) / low if low > 0 else 0

        # Check for tight consolidation
        if range_size > 0.1:  # Too wide, not consolidation
            return None

        # Check for breakout
        avg_volume = np.mean(volumes[:-5]) if volumes else 1
        recent_volume = np.mean(volumes[-5:]) if volumes else 1
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1

        if current > high * (1 + self.breakout_threshold / 2):
            # Upside breakout
            if volume_ratio >= self.volume_confirmation:
                # Calculate targets
                target = current + (high - low)  # Measured move
                stop = low * 0.98  # Below consolidation
                risk_reward = (target - current) / (current - stop) if current > stop else 0

                if risk_reward >= self.min_risk_reward:
                    return Opportunity(
                        opportunity_id=generate_unique_id('opp'),
                        symbol=symbol,
                        opportunity_type=OpportunityType.TREND_BREAKOUT,
                        quality=OpportunityQuality.HIGH if volume_ratio > 2 else OpportunityQuality.MEDIUM,
                        direction='long',
                        entry_price=current,
                        target_price=target,
                        stop_loss=stop,
                        risk_reward=risk_reward,
                        confidence=min(0.85, 0.5 + volume_ratio * 0.1),
                        reasoning=f"Breakout above ${high:.2f} with {volume_ratio:.1f}x volume",
                        timestamp=datetime.now(),
                        expiry=datetime.now() + timedelta(hours=4),
                        urgency=2,
                        metadata={'volume_ratio': volume_ratio, 'breakout_level': high}
                    )

        elif current < low * (1 - self.breakout_threshold / 2):
            # Downside breakout
            if volume_ratio >= self.volume_confirmation:
                target = current - (high - low)
                stop = high * 1.02

                risk_reward = (current - target) / (stop - current) if stop > current else 0

                if risk_reward >= self.min_risk_reward:
                    return Opportunity(
                        opportunity_id=generate_unique_id('opp'),
                        symbol=symbol,
                        opportunity_type=OpportunityType.TREND_BREAKOUT,
                        quality=OpportunityQuality.HIGH if volume_ratio > 2 else OpportunityQuality.MEDIUM,
                        direction='short',
                        entry_price=current,
                        target_price=target,
                        stop_loss=stop,
                        risk_reward=risk_reward,
                        confidence=min(0.85, 0.5 + volume_ratio * 0.1),
                        reasoning=f"Breakdown below ${low:.2f} with {volume_ratio:.1f}x volume",
                        timestamp=datetime.now(),
                        expiry=datetime.now() + timedelta(hours=4),
                        urgency=2,
                        metadata={'volume_ratio': volume_ratio, 'breakdown_level': low}
                    )

        return None

    def _detect_mean_reversion(self, symbol: str, snapshot: MarketSnapshot) -> Optional[Opportunity]:
        """Detect mean reversion opportunities"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 50:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]
        current = prices[-1]

        # Calculate moving averages
        sma_20 = np.mean(prices[-20:])
        sma_50 = np.mean(prices[-50:])

        # Calculate standard deviation
        std_20 = np.std(prices[-20:])

        # Check for extreme deviation from mean
        deviation = (current - sma_20) / std_20 if std_20 > 0 else 0

        if abs(deviation) > 2.5:  # 2.5 sigma move
            direction = 'long' if deviation < 0 else 'short'

            # Target is mean reversion to SMA
            target = sma_20
            if direction == 'long':
                stop = current * 0.95  # 5% stop
                risk_reward = (target - current) / (current - stop) if current > stop else 0
            else:
                stop = current * 1.05
                risk_reward = (current - target) / (stop - current) if stop > current else 0

            if risk_reward >= self.min_risk_reward:
                quality = OpportunityQuality.HIGH if abs(deviation) > 3 else OpportunityQuality.MEDIUM

                return Opportunity(
                    opportunity_id=generate_unique_id('opp'),
                    symbol=symbol,
                    opportunity_type=OpportunityType.MEAN_REVERSION,
                    quality=quality,
                    direction=direction,
                    entry_price=current,
                    target_price=target,
                    stop_loss=stop,
                    risk_reward=risk_reward,
                    confidence=min(0.80, 0.4 + abs(deviation) * 0.1),
                    reasoning=f"Extended {abs(deviation):.1f} sigma from mean, expecting reversion",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(hours=8),
                    urgency=3,
                    metadata={'deviation': deviation, 'sma_20': sma_20}
                )

        return None

    def _detect_momentum(self, symbol: str, snapshot: MarketSnapshot) -> Optional[Opportunity]:
        """Detect momentum opportunities"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 30:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]
        volumes = list(self.volume_history[symbol])

        current = prices[-1]

        # Calculate momentum indicators
        roc_5 = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
        roc_10 = (prices[-1] - prices[-10]) / prices[-10] if len(prices) >= 10 else 0

        # Volume trend
        vol_avg = np.mean(volumes[-20:]) if volumes else 1
        vol_recent = np.mean(volumes[-5:]) if volumes else 1
        vol_trend = vol_recent / vol_avg if vol_avg > 0 else 1

        # Strong momentum with volume
        if roc_5 > 0.05 and roc_10 > 0.08 and vol_trend > 1.3:
            # Bullish momentum
            target = current * 1.15  # 15% target
            stop = current * 0.95  # 5% stop
            risk_reward = (target - current) / (current - stop)

            if risk_reward >= self.min_risk_reward:
                return Opportunity(
                    opportunity_id=generate_unique_id('opp'),
                    symbol=symbol,
                    opportunity_type=OpportunityType.MOMENTUM,
                    quality=OpportunityQuality.HIGH if roc_10 > 0.12 else OpportunityQuality.MEDIUM,
                    direction='long',
                    entry_price=current,
                    target_price=target,
                    stop_loss=stop,
                    risk_reward=risk_reward,
                    confidence=min(0.75, 0.4 + roc_10 + vol_trend * 0.1),
                    reasoning=f"Strong momentum: {roc_10*100:.1f}% in 10 bars with {vol_trend:.1f}x volume",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(hours=6),
                    urgency=2,
                    metadata={'roc_5': roc_5, 'roc_10': roc_10, 'vol_trend': vol_trend}
                )

        elif roc_5 < -0.05 and roc_10 < -0.08 and vol_trend > 1.3:
            # Bearish momentum
            target = current * 0.85
            stop = current * 1.05
            risk_reward = (current - target) / (stop - current)

            if risk_reward >= self.min_risk_reward:
                return Opportunity(
                    opportunity_id=generate_unique_id('opp'),
                    symbol=symbol,
                    opportunity_type=OpportunityType.MOMENTUM,
                    quality=OpportunityQuality.HIGH if roc_10 < -0.12 else OpportunityQuality.MEDIUM,
                    direction='short',
                    entry_price=current,
                    target_price=target,
                    stop_loss=stop,
                    risk_reward=risk_reward,
                    confidence=min(0.75, 0.4 + abs(roc_10) + vol_trend * 0.1),
                    reasoning=f"Strong bearish momentum: {roc_10*100:.1f}% in 10 bars",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(hours=6),
                    urgency=2,
                    metadata={'roc_5': roc_5, 'roc_10': roc_10, 'vol_trend': vol_trend}
                )

        return None

    def _detect_gap_fill(self, symbol: str, snapshot: MarketSnapshot) -> Optional[Opportunity]:
        """Detect gap fill opportunities"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]

        # Find gaps in last 20 bars
        for i in range(len(prices) - 2, max(0, len(prices) - 20), -1):
            prev_close = prices[i - 1]
            gap_open = prices[i]

            gap_size = abs(gap_open - prev_close) / prev_close

            if gap_size > 0.02:  # 2% gap minimum
                current = prices[-1]

                # Check if gap is unfilled
                gap_prices = prices[i:]
                gap_high = max(prev_close, gap_open)
                gap_low = min(prev_close, gap_open)

                if gap_open > prev_close:  # Gap up
                    gap_filled = any(p <= gap_low for p in gap_prices)
                    if not gap_filled and current > gap_low:
                        # Gap up unfilled, potential short for gap fill
                        target = gap_low
                        stop = current * 1.03

                        risk_reward = (current - target) / (stop - current)

                        if risk_reward >= self.min_risk_reward:
                            return Opportunity(
                                opportunity_id=generate_unique_id('opp'),
                                symbol=symbol,
                                opportunity_type=OpportunityType.GAP_FILL,
                                quality=OpportunityQuality.MEDIUM,
                                direction='short',
                                entry_price=current,
                                target_price=target,
                                stop_loss=stop,
                                risk_reward=risk_reward,
                                confidence=0.60,
                                reasoning=f"Gap up at ${gap_open:.2f} unfilled, target ${target:.2f}",
                                timestamp=datetime.now(),
                                expiry=datetime.now() + timedelta(days=1),
                                urgency=4,
                                metadata={'gap_size': gap_size, 'gap_level': gap_low}
                            )

                else:  # Gap down
                    gap_filled = any(p >= gap_high for p in gap_prices)
                    if not gap_filled and current < gap_high:
                        target = gap_high
                        stop = current * 0.97

                        risk_reward = (target - current) / (current - stop)

                        if risk_reward >= self.min_risk_reward:
                            return Opportunity(
                                opportunity_id=generate_unique_id('opp'),
                                symbol=symbol,
                                opportunity_type=OpportunityType.GAP_FILL,
                                quality=OpportunityQuality.MEDIUM,
                                direction='long',
                                entry_price=current,
                                target_price=target,
                                stop_loss=stop,
                                risk_reward=risk_reward,
                                confidence=0.60,
                                reasoning=f"Gap down at ${gap_open:.2f} unfilled, target ${target:.2f}",
                                timestamp=datetime.now(),
                                expiry=datetime.now() + timedelta(days=1),
                                urgency=4,
                                metadata={'gap_size': gap_size, 'gap_level': gap_high}
                            )

                break  # Only check most recent gap

        return None

    def _detect_rsi_extreme(self, symbol: str, snapshot: MarketSnapshot) -> Optional[Opportunity]:
        """Detect oversold/overbought RSI opportunities"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 20:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]
        current = prices[-1]

        # Calculate RSI
        rsi = self._calculate_rsi(prices, 14)

        if rsi is None:
            return None

        if rsi < self.oversold_rsi:
            # Oversold - potential long
            target = current * 1.08
            stop = current * 0.96
            risk_reward = (target - current) / (current - stop)

            quality = OpportunityQuality.HIGH if rsi < 20 else OpportunityQuality.MEDIUM
            confidence = 0.55 + (30 - rsi) / 60  # Lower RSI = higher confidence

            if risk_reward >= self.min_risk_reward:
                return Opportunity(
                    opportunity_id=generate_unique_id('opp'),
                    symbol=symbol,
                    opportunity_type=OpportunityType.OVERSOLD_BOUNCE,
                    quality=quality,
                    direction='long',
                    entry_price=current,
                    target_price=target,
                    stop_loss=stop,
                    risk_reward=risk_reward,
                    confidence=min(0.75, confidence),
                    reasoning=f"RSI oversold at {rsi:.1f}, expecting bounce",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(hours=12),
                    urgency=3,
                    metadata={'rsi': rsi}
                )

        elif rsi > self.overbought_rsi:
            # Overbought - potential short
            target = current * 0.92
            stop = current * 1.04
            risk_reward = (current - target) / (stop - current)

            quality = OpportunityQuality.HIGH if rsi > 80 else OpportunityQuality.MEDIUM
            confidence = 0.55 + (rsi - 70) / 60

            if risk_reward >= self.min_risk_reward:
                return Opportunity(
                    opportunity_id=generate_unique_id('opp'),
                    symbol=symbol,
                    opportunity_type=OpportunityType.OVERBOUGHT_SHORT,
                    quality=quality,
                    direction='short',
                    entry_price=current,
                    target_price=target,
                    stop_loss=stop,
                    risk_reward=risk_reward,
                    confidence=min(0.75, confidence),
                    reasoning=f"RSI overbought at {rsi:.1f}, expecting pullback",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(hours=12),
                    urgency=3,
                    metadata={'rsi': rsi}
                )

        return None

    def _detect_technical_setup(self, symbol: str, snapshot: MarketSnapshot) -> Optional[Opportunity]:
        """Detect confluence of technical signals"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 50:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]
        volumes = list(self.volume_history[symbol])
        current = prices[-1]

        # Collect bullish/bearish signals
        bullish_signals = 0
        bearish_signals = 0

        # Moving average alignment
        sma_10 = np.mean(prices[-10:])
        sma_20 = np.mean(prices[-20:])
        sma_50 = np.mean(prices[-50:])

        if current > sma_10 > sma_20 > sma_50:
            bullish_signals += 2
        elif current < sma_10 < sma_20 < sma_50:
            bearish_signals += 2

        # RSI
        rsi = self._calculate_rsi(prices, 14)
        if rsi:
            if 40 < rsi < 60:  # Neutral - no signal
                pass
            elif rsi < 40:
                bullish_signals += 1  # Room to run
            else:
                bearish_signals += 1

        # Volume trend
        vol_avg = np.mean(volumes[-20:]) if volumes else 1
        vol_recent = np.mean(volumes[-5:]) if volumes else 1
        if vol_recent > vol_avg * 1.5:
            # Volume expanding - confirms direction
            if bullish_signals > bearish_signals:
                bullish_signals += 1
            else:
                bearish_signals += 1

        # Higher highs / lower lows
        if len(prices) >= 30:
            highs = [max(prices[i:i+5]) for i in range(0, 30, 5)]
            lows = [min(prices[i:i+5]) for i in range(0, 30, 5)]

            if all(highs[i] >= highs[i-1] for i in range(1, len(highs))):
                bullish_signals += 1
            if all(lows[i] <= lows[i-1] for i in range(1, len(lows))):
                bearish_signals += 1

        # Generate signal only if strong confluence
        if bullish_signals >= 4 and bearish_signals <= 1:
            target = current * 1.12
            stop = current * 0.95
            risk_reward = (target - current) / (current - stop)

            if risk_reward >= self.min_risk_reward:
                return Opportunity(
                    opportunity_id=generate_unique_id('opp'),
                    symbol=symbol,
                    opportunity_type=OpportunityType.TECHNICAL_SETUP,
                    quality=OpportunityQuality.HIGH,
                    direction='long',
                    entry_price=current,
                    target_price=target,
                    stop_loss=stop,
                    risk_reward=risk_reward,
                    confidence=0.70 + bullish_signals * 0.03,
                    reasoning=f"Bullish confluence: {bullish_signals} aligned signals",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(hours=8),
                    urgency=2,
                    metadata={'bullish_signals': bullish_signals, 'bearish_signals': bearish_signals}
                )

        elif bearish_signals >= 4 and bullish_signals <= 1:
            target = current * 0.88
            stop = current * 1.05
            risk_reward = (current - target) / (stop - current)

            if risk_reward >= self.min_risk_reward:
                return Opportunity(
                    opportunity_id=generate_unique_id('opp'),
                    symbol=symbol,
                    opportunity_type=OpportunityType.TECHNICAL_SETUP,
                    quality=OpportunityQuality.HIGH,
                    direction='short',
                    entry_price=current,
                    target_price=target,
                    stop_loss=stop,
                    risk_reward=risk_reward,
                    confidence=0.70 + bearish_signals * 0.03,
                    reasoning=f"Bearish confluence: {bearish_signals} aligned signals",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(hours=8),
                    urgency=2,
                    metadata={'bullish_signals': bullish_signals, 'bearish_signals': bearish_signals}
                )

        return None

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return None

        deltas = np.diff(prices[-(period+1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _rank_opportunities(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """Rank opportunities by quality and urgency"""
        def score(opp: Opportunity) -> float:
            # Higher is better
            quality_score = opp.quality.value * 10
            rr_score = min(5, opp.risk_reward) * 5
            confidence_score = opp.confidence * 10
            urgency_score = (6 - opp.urgency) * 2  # Lower urgency number = higher score

            return quality_score + rr_score + confidence_score + urgency_score

        opportunities.sort(key=score, reverse=True)
        return opportunities

    def _opportunity_to_signal(self, opp: Opportunity) -> Signal:
        """Convert opportunity to signal"""
        strength_map = {
            OpportunityQuality.LOW: SignalStrength.WEAK,
            OpportunityQuality.MEDIUM: SignalStrength.MODERATE,
            OpportunityQuality.HIGH: SignalStrength.STRONG,
            OpportunityQuality.EXCEPTIONAL: SignalStrength.VERY_STRONG
        }

        self.signals_generated += 1

        return Signal(
            agent_id=self.agent_id,
            symbol=opp.symbol,
            direction=opp.direction,
            strength=strength_map[opp.quality],
            confidence=opp.confidence,
            reasoning=opp.reasoning,
            timestamp=datetime.now(),
            expiry=opp.expiry,
            metadata={
                'opportunity_id': opp.opportunity_id,
                'opportunity_type': opp.opportunity_type.name,
                'entry': opp.entry_price,
                'target': opp.target_price,
                'stop_loss': opp.stop_loss,
                'risk_reward': opp.risk_reward,
                'urgency': opp.urgency
            }
        )

    def _clean_expired(self):
        """Remove expired opportunities"""
        now = datetime.now()
        expired = [oid for oid, opp in self.active_opportunities.items() if opp.expiry < now]
        for oid in expired:
            del self.active_opportunities[oid]

    def add_to_watchlist(self, symbol: str, list_type: str):
        """Add symbol to a watchlist"""
        if list_type == 'new_listing':
            self.new_listings_watchlist.add(symbol)
        elif list_type == 'ipo':
            self.ipo_watchlist.add(symbol)
        elif list_type == 'breakout':
            self.breakout_watchlist.add(symbol)

    def get_active_opportunities(self) -> List[Dict]:
        """Get all active opportunities"""
        return [
            {
                'symbol': o.symbol,
                'type': o.opportunity_type.name,
                'quality': o.quality.name,
                'direction': o.direction,
                'entry': o.entry_price,
                'target': o.target_price,
                'stop': o.stop_loss,
                'rr': round(o.risk_reward, 2),
                'confidence': round(o.confidence, 2),
                'reasoning': o.reasoning,
                'urgency': o.urgency,
                'expires': o.expiry.isoformat()
            }
            for o in self.active_opportunities.values()
        ]

    def learn(self, feedback: Dict[str, Any]):
        """Learn from opportunity outcomes"""
        opportunity_id = feedback.get('opportunity_id')
        outcome = feedback.get('outcome', 0)

        if outcome > 0:
            self.correct_signals += 1
            self.memory.remember({
                'type': 'successful_opportunity',
                'id': opportunity_id,
                'outcome': outcome
            }, importance=0.8)
        else:
            self.memory.remember({
                'type': 'failed_opportunity',
                'id': opportunity_id,
                'outcome': outcome
            }, importance=0.7)
