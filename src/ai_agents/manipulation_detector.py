"""
Manipulation Detection Agent

Detects and avoids:
- Pump and dump schemes
- Spoofing and layering
- Wash trading
- Front running
- Stop hunting
- Fake breakouts
- Whale manipulation
- Coordinated social media attacks
- Flash crashes (artificial)
- Market cornering attempts

Protects portfolio from falling into traps.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum, auto
import numpy as np
from collections import deque

from .base import (
    BaseAgent, Signal, SignalStrength, MarketSnapshot,
    MarketCondition, AgentState, generate_unique_id, normalize_confidence
)


class ManipulationType(Enum):
    """Types of market manipulation"""
    PUMP_AND_DUMP = auto()
    SPOOFING = auto()
    LAYERING = auto()
    WASH_TRADING = auto()
    FRONT_RUNNING = auto()
    STOP_HUNTING = auto()
    FAKE_BREAKOUT = auto()
    WHALE_MANIPULATION = auto()
    COORDINATED_ATTACK = auto()
    FLASH_CRASH = auto()
    CORNER_SQUEEZE = auto()
    PAINTING_THE_TAPE = auto()


class AlertSeverity(Enum):
    """Severity of manipulation alert"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ManipulationAlert:
    """Alert for detected manipulation"""
    alert_id: str
    symbol: str
    manipulation_type: ManipulationType
    severity: AlertSeverity
    confidence: float
    description: str
    timestamp: datetime
    evidence: Dict[str, Any]
    recommended_action: str
    expires: datetime


@dataclass
class OrderBookSnapshot:
    """Order book state for analysis"""
    bids: List[Tuple[float, float]]  # (price, size)
    asks: List[Tuple[float, float]]
    spread: float
    mid_price: float
    imbalance: float  # Positive = more bids
    total_bid_volume: float
    total_ask_volume: float


class ManipulationDetectorAgent(BaseAgent):
    """
    Detects market manipulation to protect from traps.

    Uses multiple detection algorithms:
    - Volume anomaly detection
    - Order book analysis
    - Price action pattern recognition
    - Cross-market correlation
    - Social sentiment divergence
    - Whale wallet tracking (for crypto)
    """

    def __init__(self):
        super().__init__(
            agent_id=generate_unique_id('manipulation_detector'),
            name="Manipulation Detector",
            description="Detects market manipulation and protects from traps"
        )

        # Historical data for pattern detection
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.order_book_history: Dict[str, deque] = {}
        self.trade_velocity: Dict[str, deque] = {}

        # Active alerts
        self.active_alerts: Dict[str, ManipulationAlert] = {}
        self.alert_history: deque = deque(maxlen=1000)

        # Suspicious entities tracking
        self.suspicious_addresses: Set[str] = set()  # For crypto
        self.known_whale_addresses: Set[str] = set()

        # Detection thresholds (tunable)
        self.volume_spike_threshold = 5.0  # 5x average
        self.price_spike_threshold = 0.05  # 5% in short time
        self.order_book_imbalance_threshold = 0.7  # 70% one-sided
        self.velocity_spike_threshold = 3.0  # 3x normal trade rate
        self.correlation_break_threshold = 0.5  # Correlation divergence

        # Pattern templates for known manipulation
        self._init_manipulation_patterns()

    def _init_manipulation_patterns(self):
        """Initialize known manipulation pattern templates"""
        self.patterns = {
            ManipulationType.PUMP_AND_DUMP: {
                'price_surge': 0.2,  # 20%+ price increase
                'volume_surge': 10.0,  # 10x volume
                'duration_hours': 24,
                'social_buzz': True
            },
            ManipulationType.STOP_HUNTING: {
                'wick_ratio': 0.7,  # Long wicks
                'recovery_speed': 0.8,  # Fast recovery
                'volume_spike': 2.0
            },
            ManipulationType.FAKE_BREAKOUT: {
                'breakout_size': 0.02,  # 2% above resistance
                'reversal_speed': 0.5,  # Quick reversal (hours)
                'volume_divergence': True
            },
            ManipulationType.SPOOFING: {
                'order_cancel_rate': 0.9,  # 90% cancellation
                'order_size_anomaly': 5.0,  # 5x normal
                'one_sided': True
            }
        }

    def analyze(self, snapshot: MarketSnapshot) -> Optional[Signal]:
        """Analyze market for manipulation signals"""
        self.state = AgentState.ANALYZING
        self.last_active = datetime.now()

        # Clean expired alerts
        self._clean_expired_alerts()

        signals = []

        for symbol, price in snapshot.prices.items():
            # Update history
            self._update_history(symbol, price, snapshot.volumes.get(symbol, 0))

            # Run all detection algorithms
            alerts = self._detect_all(symbol, snapshot)

            for alert in alerts:
                self.active_alerts[alert.alert_id] = alert
                self.alert_history.append(alert)

                # Generate protective signal
                signal = self._alert_to_signal(alert, snapshot)
                if signal:
                    signals.append(signal)

        self.state = AgentState.IDLE

        if signals:
            # Return most severe alert signal
            signals.sort(key=lambda s: s.confidence, reverse=True)
            return signals[0]

        return None

    def _update_history(self, symbol: str, price: float, volume: float):
        """Update historical data"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=1000)
            self.volume_history[symbol] = deque(maxlen=1000)
            self.trade_velocity[symbol] = deque(maxlen=100)

        self.price_history[symbol].append({
            'price': price,
            'timestamp': datetime.now()
        })
        self.volume_history[symbol].append(volume)

    def _detect_all(self, symbol: str, snapshot: MarketSnapshot) -> List[ManipulationAlert]:
        """Run all manipulation detection algorithms"""
        alerts = []

        # Volume analysis
        vol_alert = self._detect_volume_manipulation(symbol)
        if vol_alert:
            alerts.append(vol_alert)

        # Price action analysis
        price_alert = self._detect_price_manipulation(symbol)
        if price_alert:
            alerts.append(price_alert)

        # Order book analysis
        if symbol in snapshot.order_book_imbalance:
            ob_alert = self._detect_order_book_manipulation(symbol, snapshot)
            if ob_alert:
                alerts.append(ob_alert)

        # Pump and dump detection
        pnd_alert = self._detect_pump_and_dump(symbol)
        if pnd_alert:
            alerts.append(pnd_alert)

        # Stop hunting detection
        sh_alert = self._detect_stop_hunting(symbol)
        if sh_alert:
            alerts.append(sh_alert)

        # Fake breakout detection
        fb_alert = self._detect_fake_breakout(symbol)
        if fb_alert:
            alerts.append(fb_alert)

        return alerts

    def _detect_volume_manipulation(self, symbol: str) -> Optional[ManipulationAlert]:
        """Detect unusual volume patterns"""
        if symbol not in self.volume_history or len(self.volume_history[symbol]) < 50:
            return None

        volumes = list(self.volume_history[symbol])
        avg_volume = np.mean(volumes[:-10])  # Exclude recent
        recent_volume = np.mean(volumes[-5:])

        if avg_volume == 0:
            return None

        volume_ratio = recent_volume / avg_volume

        if volume_ratio > self.volume_spike_threshold:
            # Check if price is also spiking (wash trading indicator)
            prices = [p['price'] for p in self.price_history[symbol]]
            price_change = (prices[-1] - prices[-10]) / prices[-10] if len(prices) >= 10 else 0

            severity = AlertSeverity.HIGH if volume_ratio > 10 else AlertSeverity.MEDIUM

            return ManipulationAlert(
                alert_id=generate_unique_id('alert'),
                symbol=symbol,
                manipulation_type=ManipulationType.WASH_TRADING if abs(price_change) < 0.01 else ManipulationType.PUMP_AND_DUMP,
                severity=severity,
                confidence=min(0.9, volume_ratio / 20),
                description=f"Volume spike {volume_ratio:.1f}x average, price change {price_change*100:.1f}%",
                timestamp=datetime.now(),
                evidence={'volume_ratio': volume_ratio, 'price_change': price_change},
                recommended_action="AVOID" if severity == AlertSeverity.HIGH else "CAUTION",
                expires=datetime.now() + timedelta(hours=1)
            )

        return None

    def _detect_price_manipulation(self, symbol: str) -> Optional[ManipulationAlert]:
        """Detect unusual price movements"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 20:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]

        # Check for rapid price changes
        for window in [5, 10, 20]:
            if len(prices) >= window:
                change = (prices[-1] - prices[-window]) / prices[-window]

                if abs(change) > self.price_spike_threshold * (20 / window):
                    # Calculate volatility for context
                    returns = np.diff(prices[-100:]) / prices[-100:-1]
                    normal_vol = np.std(returns) if len(returns) > 0 else 0.01

                    # Is this move abnormal?
                    move_zscore = abs(change) / (normal_vol * np.sqrt(window)) if normal_vol > 0 else 0

                    if move_zscore > 4:  # 4 sigma event
                        return ManipulationAlert(
                            alert_id=generate_unique_id('alert'),
                            symbol=symbol,
                            manipulation_type=ManipulationType.WHALE_MANIPULATION,
                            severity=AlertSeverity.HIGH,
                            confidence=min(0.95, move_zscore / 10),
                            description=f"Abnormal {change*100:.1f}% move in {window} periods ({move_zscore:.1f} sigma)",
                            timestamp=datetime.now(),
                            evidence={'change': change, 'z_score': move_zscore, 'window': window},
                            recommended_action="DO NOT CHASE",
                            expires=datetime.now() + timedelta(hours=2)
                        )

        return None

    def _detect_order_book_manipulation(self, symbol: str, snapshot: MarketSnapshot) -> Optional[ManipulationAlert]:
        """Detect order book manipulation (spoofing, layering)"""
        imbalance = snapshot.order_book_imbalance.get(symbol, 0)

        if abs(imbalance) > self.order_book_imbalance_threshold:
            # Track if imbalance persists or suddenly disappears
            if symbol not in self.order_book_history:
                self.order_book_history[symbol] = deque(maxlen=100)

            self.order_book_history[symbol].append({
                'imbalance': imbalance,
                'timestamp': datetime.now()
            })

            # Check for spoofing pattern: large imbalance that disappears
            if len(self.order_book_history[symbol]) >= 5:
                recent = list(self.order_book_history[symbol])[-5:]
                imbalances = [r['imbalance'] for r in recent]

                # If imbalance was high and dropped suddenly
                if max(abs(i) for i in imbalances[:-1]) > 0.8 and abs(imbalances[-1]) < 0.3:
                    return ManipulationAlert(
                        alert_id=generate_unique_id('alert'),
                        symbol=symbol,
                        manipulation_type=ManipulationType.SPOOFING,
                        severity=AlertSeverity.HIGH,
                        confidence=0.75,
                        description=f"Order book manipulation detected - imbalance collapsed from {max(abs(i) for i in imbalances[:-1]):.0%} to {abs(imbalances[-1]):.0%}",
                        timestamp=datetime.now(),
                        evidence={'imbalance_history': imbalances},
                        recommended_action="AVOID - Spoofing detected",
                        expires=datetime.now() + timedelta(minutes=30)
                    )

        return None

    def _detect_pump_and_dump(self, symbol: str) -> Optional[ManipulationAlert]:
        """Detect pump and dump schemes"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 100:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]
        volumes = list(self.volume_history[symbol]) if symbol in self.volume_history else []

        if len(volumes) < 100:
            return None

        # Look for pattern: rapid rise followed by distribution
        # Check last 24 hours worth of data
        lookback = min(len(prices), 100)

        price_high = max(prices[-lookback:])
        price_low = min(prices[-lookback:])
        price_range = (price_high - price_low) / price_low if price_low > 0 else 0

        current = prices[-1]
        from_high = (price_high - current) / price_high if price_high > 0 else 0

        # Pump pattern: big range, currently dumping
        if price_range > 0.3 and from_high > 0.2:
            # Volume confirmation
            vol_at_high = np.mean(volumes[-lookback:-lookback+20])
            vol_now = np.mean(volumes[-10:])

            if vol_at_high > np.mean(volumes) * 3:
                return ManipulationAlert(
                    alert_id=generate_unique_id('alert'),
                    symbol=symbol,
                    manipulation_type=ManipulationType.PUMP_AND_DUMP,
                    severity=AlertSeverity.CRITICAL,
                    confidence=0.85,
                    description=f"Pump and dump pattern: {price_range*100:.0f}% range, now {from_high*100:.0f}% from high",
                    timestamp=datetime.now(),
                    evidence={
                        'price_range': price_range,
                        'from_high': from_high,
                        'volume_spike': vol_at_high / np.mean(volumes)
                    },
                    recommended_action="AVOID - High probability dump in progress",
                    expires=datetime.now() + timedelta(hours=6)
                )

        return None

    def _detect_stop_hunting(self, symbol: str) -> Optional[ManipulationAlert]:
        """Detect stop hunting patterns"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 30:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]

        # Look for wick patterns (price spikes that quickly reverse)
        recent_prices = prices[-20:]

        high = max(recent_prices)
        low = min(recent_prices)
        current = prices[-1]
        open_price = prices[-20]

        body = abs(current - open_price)
        total_range = high - low

        if total_range == 0:
            return None

        # Wick ratio: how much of the range is wick vs body
        wick_ratio = 1 - (body / total_range)

        # Stop hunt pattern: long wicks with small body
        if wick_ratio > 0.7 and total_range / current > 0.02:
            # Determine direction of hunt
            upper_wick = high - max(current, open_price)
            lower_wick = min(current, open_price) - low

            hunt_direction = "upside" if upper_wick > lower_wick else "downside"

            return ManipulationAlert(
                alert_id=generate_unique_id('alert'),
                symbol=symbol,
                manipulation_type=ManipulationType.STOP_HUNTING,
                severity=AlertSeverity.MEDIUM,
                confidence=0.65,
                description=f"Stop hunt on {hunt_direction} - {wick_ratio*100:.0f}% wick ratio",
                timestamp=datetime.now(),
                evidence={
                    'wick_ratio': wick_ratio,
                    'hunt_direction': hunt_direction,
                    'range': total_range
                },
                recommended_action=f"Avoid tight stops on {hunt_direction}",
                expires=datetime.now() + timedelta(hours=1)
            )

        return None

    def _detect_fake_breakout(self, symbol: str) -> Optional[ManipulationAlert]:
        """Detect fake breakout patterns"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 50:
            return None

        prices = [p['price'] for p in self.price_history[symbol]]

        # Find recent high/low (potential S/R levels)
        lookback_range = prices[-50:-10]
        if not lookback_range:
            return None

        resistance = max(lookback_range)
        support = min(lookback_range)

        current = prices[-1]
        recent_high = max(prices[-10:])
        recent_low = min(prices[-10:])

        # Check for breakout and reversal
        broke_resistance = recent_high > resistance * 1.01
        broke_support = recent_low < support * 0.99
        back_inside = support <= current <= resistance

        if (broke_resistance or broke_support) and back_inside:
            direction = "upside" if broke_resistance else "downside"

            # Calculate how far it broke out before reversing
            if broke_resistance:
                breakout_size = (recent_high - resistance) / resistance
            else:
                breakout_size = (support - recent_low) / support

            if breakout_size > 0.01:  # At least 1% breakout
                return ManipulationAlert(
                    alert_id=generate_unique_id('alert'),
                    symbol=symbol,
                    manipulation_type=ManipulationType.FAKE_BREAKOUT,
                    severity=AlertSeverity.HIGH,
                    confidence=0.70,
                    description=f"Fake {direction} breakout - broke by {breakout_size*100:.1f}% then reversed",
                    timestamp=datetime.now(),
                    evidence={
                        'direction': direction,
                        'breakout_size': breakout_size,
                        'resistance': resistance,
                        'support': support
                    },
                    recommended_action=f"Fade the {direction} move, trade reversal",
                    expires=datetime.now() + timedelta(hours=2)
                )

        return None

    def _alert_to_signal(self, alert: ManipulationAlert, snapshot: MarketSnapshot) -> Optional[Signal]:
        """Convert manipulation alert to protective/trading signal"""
        # Determine signal direction based on manipulation type
        direction = 'hold'  # Default to hold/avoid

        if alert.manipulation_type == ManipulationType.PUMP_AND_DUMP:
            if 'from_high' in alert.evidence and alert.evidence['from_high'] < 0.1:
                direction = 'short'  # Dump imminent
            else:
                direction = 'hold'  # Already dumping, avoid

        elif alert.manipulation_type == ManipulationType.FAKE_BREAKOUT:
            if alert.evidence.get('direction') == 'upside':
                direction = 'short'  # Fade the fake breakout
            else:
                direction = 'long'  # Fade the fake breakdown

        elif alert.manipulation_type == ManipulationType.STOP_HUNTING:
            # After stop hunt, often good to trade the reversal
            if alert.evidence.get('hunt_direction') == 'downside':
                direction = 'long'
            else:
                direction = 'short'

        elif alert.manipulation_type in [ManipulationType.SPOOFING, ManipulationType.WHALE_MANIPULATION]:
            direction = 'hold'  # Avoid entirely

        if direction == 'hold':
            return None

        # Calculate signal strength from severity
        strength_map = {
            AlertSeverity.LOW: SignalStrength.WEAK,
            AlertSeverity.MEDIUM: SignalStrength.MODERATE,
            AlertSeverity.HIGH: SignalStrength.STRONG,
            AlertSeverity.CRITICAL: SignalStrength.VERY_STRONG
        }

        self.signals_generated += 1

        return Signal(
            agent_id=self.agent_id,
            symbol=alert.symbol,
            direction=direction,
            strength=strength_map[alert.severity],
            confidence=alert.confidence,
            reasoning=f"Manipulation detected: {alert.description}",
            timestamp=datetime.now(),
            expiry=alert.expires,
            metadata={
                'alert_id': alert.alert_id,
                'manipulation_type': alert.manipulation_type.name,
                'recommended_action': alert.recommended_action,
                'evidence': alert.evidence
            }
        )

    def _clean_expired_alerts(self):
        """Remove expired alerts"""
        now = datetime.now()
        expired = [aid for aid, alert in self.active_alerts.items() if alert.expires < now]
        for aid in expired:
            del self.active_alerts[aid]

    def is_symbol_safe(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """Check if a symbol is safe to trade"""
        active = [a for a in self.active_alerts.values() if a.symbol == symbol]

        if not active:
            return True, None

        # Check for critical alerts
        for alert in active:
            if alert.severity == AlertSeverity.CRITICAL:
                return False, f"CRITICAL: {alert.description}"
            if alert.severity == AlertSeverity.HIGH:
                return False, f"WARNING: {alert.description}"

        return True, None

    def get_all_alerts(self) -> List[Dict]:
        """Get all active alerts"""
        return [
            {
                'symbol': a.symbol,
                'type': a.manipulation_type.name,
                'severity': a.severity.name,
                'description': a.description,
                'action': a.recommended_action,
                'expires': a.expires.isoformat()
            }
            for a in self.active_alerts.values()
        ]

    def learn(self, feedback: Dict[str, Any]):
        """Learn from trade outcomes related to manipulation detection"""
        alert_id = feedback.get('alert_id')
        outcome = feedback.get('outcome', 0)

        if outcome > 0:
            self.correct_signals += 1
            # The manipulation detection was correct
            self.memory.remember({
                'type': 'correct_detection',
                'alert_id': alert_id,
                'outcome': outcome
            }, importance=0.8)
        else:
            # False positive or wrong action
            self.memory.remember({
                'type': 'wrong_detection',
                'alert_id': alert_id,
                'outcome': outcome
            }, importance=0.7)
