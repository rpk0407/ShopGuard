"""
AI Agent Framework - Core Architecture

Base classes for all AI trading agents. Provides:
- Agent lifecycle management
- Inter-agent communication
- Decision making framework
- Learning and adaptation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable, Set
import numpy as np
import threading
import queue
import time
import hashlib
import random
from collections import deque


class AgentState(Enum):
    """Agent operational states"""
    INITIALIZING = auto()
    IDLE = auto()
    ANALYZING = auto()
    DECIDING = auto()
    EXECUTING = auto()
    LEARNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()


class SignalStrength(Enum):
    """Trading signal strength levels"""
    VERY_WEAK = 1
    WEAK = 2
    MODERATE = 3
    STRONG = 4
    VERY_STRONG = 5


class MarketCondition(Enum):
    """Current market conditions"""
    EXTREME_FEAR = auto()
    FEAR = auto()
    NEUTRAL = auto()
    GREED = auto()
    EXTREME_GREED = auto()
    VOLATILE = auto()
    TRENDING_UP = auto()
    TRENDING_DOWN = auto()
    RANGING = auto()
    MANIPULATION_DETECTED = auto()


@dataclass
class Signal:
    """Trading signal from an agent"""
    agent_id: str
    symbol: str
    direction: str  # 'long', 'short', 'close', 'hold'
    strength: SignalStrength
    confidence: float  # 0-1
    reasoning: str
    timestamp: datetime
    expiry: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return datetime.now() < self.expiry

    @property
    def score(self) -> float:
        """Combined score for ranking signals"""
        return self.strength.value * self.confidence


@dataclass
class MarketSnapshot:
    """Point-in-time market state"""
    timestamp: datetime
    prices: Dict[str, float]
    volumes: Dict[str, float]
    spreads: Dict[str, float]
    order_book_imbalance: Dict[str, float]
    recent_trades: Dict[str, List[Dict]]
    volatility: Dict[str, float]
    momentum: Dict[str, float]
    correlation_matrix: Optional[np.ndarray] = None
    market_condition: MarketCondition = MarketCondition.NEUTRAL


@dataclass
class AgentMessage:
    """Inter-agent communication message"""
    sender_id: str
    recipient_id: str  # or 'broadcast' for all agents
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime
    priority: int = 5  # 1=highest, 10=lowest
    requires_ack: bool = False


class Memory:
    """Agent memory system for learning and pattern recognition"""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.short_term: deque = deque(maxlen=100)  # Recent observations
        self.long_term: List[Dict] = []  # Important patterns
        self.trade_history: List[Dict] = []
        self.pattern_cache: Dict[str, Any] = {}
        self.success_patterns: List[Dict] = []
        self.failure_patterns: List[Dict] = []

    def remember(self, observation: Dict, importance: float = 0.5):
        """Store an observation"""
        entry = {
            'timestamp': datetime.now(),
            'observation': observation,
            'importance': importance
        }
        self.short_term.append(entry)

        # Promote important observations to long-term memory
        if importance > 0.7:
            self.long_term.append(entry)
            if len(self.long_term) > self.max_size:
                # Remove least important memories
                self.long_term.sort(key=lambda x: x['importance'])
                self.long_term = self.long_term[len(self.long_term)//10:]

    def recall_similar(self, query: Dict, n: int = 5) -> List[Dict]:
        """Find similar past observations"""
        # Simple similarity based on shared keys and values
        scored = []
        for mem in self.long_term:
            score = self._similarity(query, mem['observation'])
            scored.append((score, mem))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [m for _, m in scored[:n]]

    def _similarity(self, a: Dict, b: Dict) -> float:
        """Calculate similarity between two observations"""
        if not a or not b:
            return 0.0

        shared_keys = set(a.keys()) & set(b.keys())
        if not shared_keys:
            return 0.0

        matches = sum(1 for k in shared_keys if a[k] == b[k])
        return matches / len(shared_keys)

    def record_trade(self, trade: Dict, outcome: float):
        """Record a trade and its outcome for learning"""
        trade['outcome'] = outcome
        trade['recorded_at'] = datetime.now()
        self.trade_history.append(trade)

        # Categorize as success or failure pattern
        if outcome > 0:
            self.success_patterns.append(trade)
        else:
            self.failure_patterns.append(trade)

    def get_win_rate(self, lookback: int = 100) -> float:
        """Calculate recent win rate"""
        recent = self.trade_history[-lookback:] if self.trade_history else []
        if not recent:
            return 0.5
        wins = sum(1 for t in recent if t.get('outcome', 0) > 0)
        return wins / len(recent)


class BaseAgent(ABC):
    """
    Base class for all AI trading agents.

    Provides:
    - Lifecycle management (start, stop, pause)
    - Message passing between agents
    - Memory and learning capabilities
    - Human-like behavior simulation
    """

    def __init__(self, agent_id: str, name: str, description: str):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.state = AgentState.INITIALIZING
        self.memory = Memory()

        # Communication
        self.inbox: queue.PriorityQueue = queue.PriorityQueue()
        self.subscribers: Set[str] = set()
        self.message_handlers: Dict[str, Callable] = {}

        # Performance tracking
        self.signals_generated = 0
        self.correct_signals = 0
        self.created_at = datetime.now()
        self.last_active = datetime.now()

        # Human-like behavior parameters
        self.reaction_delay_range = (0.1, 2.0)  # seconds
        self.decision_noise = 0.05  # Small random factor
        self.fatigue_factor = 0.0  # Increases over time, affects performance

        # Thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @abstractmethod
    def analyze(self, snapshot: MarketSnapshot) -> Optional[Signal]:
        """Analyze market and generate signal if warranted"""
        pass

    @abstractmethod
    def learn(self, feedback: Dict[str, Any]):
        """Learn from outcomes and feedback"""
        pass

    def start(self):
        """Start the agent"""
        self._running = True
        self.state = AgentState.IDLE
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the agent"""
        self._running = False
        self.state = AgentState.STOPPED
        if self._thread:
            self._thread.join(timeout=5)

    def pause(self):
        """Pause the agent"""
        self.state = AgentState.PAUSED

    def resume(self):
        """Resume the agent"""
        if self.state == AgentState.PAUSED:
            self.state = AgentState.IDLE

    def _run_loop(self):
        """Main agent loop"""
        while self._running:
            try:
                if self.state == AgentState.PAUSED:
                    time.sleep(0.5)
                    continue

                # Process messages
                self._process_messages()

                # Update fatigue (resets periodically)
                self._update_fatigue()

                # Small delay to prevent busy-waiting
                time.sleep(0.1)

            except Exception as e:
                self.state = AgentState.ERROR
                self.memory.remember({'error': str(e), 'type': 'runtime'}, 0.9)

    def _process_messages(self):
        """Process incoming messages"""
        while not self.inbox.empty():
            try:
                _, msg = self.inbox.get_nowait()
                handler = self.message_handlers.get(msg.message_type)
                if handler:
                    handler(msg)
            except queue.Empty:
                break

    def send_message(self, recipient: 'BaseAgent', msg_type: str, payload: Dict):
        """Send message to another agent"""
        msg = AgentMessage(
            sender_id=self.agent_id,
            recipient_id=recipient.agent_id,
            message_type=msg_type,
            payload=payload,
            timestamp=datetime.now()
        )
        recipient.inbox.put((msg.priority, msg))

    def broadcast(self, orchestrator: 'AgentOrchestrator', msg_type: str, payload: Dict):
        """Broadcast message to all agents"""
        for agent in orchestrator.agents.values():
            if agent.agent_id != self.agent_id:
                self.send_message(agent, msg_type, payload)

    def _update_fatigue(self):
        """Simulate human-like fatigue"""
        hours_active = (datetime.now() - self.created_at).total_seconds() / 3600
        self.fatigue_factor = min(0.3, hours_active * 0.01)  # Max 30% reduction

    def add_human_delay(self):
        """Add realistic delay to seem human"""
        base_delay = random.uniform(*self.reaction_delay_range)
        fatigue_delay = base_delay * (1 + self.fatigue_factor)
        time.sleep(fatigue_delay)

    def add_decision_noise(self, value: float) -> float:
        """Add small noise to decisions for human-like behavior"""
        noise = random.gauss(0, self.decision_noise)
        return value * (1 + noise)

    @property
    def accuracy(self) -> float:
        """Signal accuracy rate"""
        if self.signals_generated == 0:
            return 0.0
        return self.correct_signals / self.signals_generated

    def get_status(self) -> Dict:
        """Get agent status"""
        return {
            'agent_id': self.agent_id,
            'name': self.name,
            'state': self.state.name,
            'signals_generated': self.signals_generated,
            'accuracy': round(self.accuracy, 4),
            'last_active': self.last_active.isoformat(),
            'fatigue_factor': round(self.fatigue_factor, 4),
            'memory_size': len(self.memory.long_term)
        }


class AgentOrchestrator:
    """
    Master controller that coordinates all AI agents.

    Responsibilities:
    - Agent lifecycle management
    - Signal aggregation and conflict resolution
    - Risk management coordination
    - User control interface
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.agents: Dict[str, BaseAgent] = {}
        self.signal_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.active_positions: Dict[str, Dict] = {}
        self.capital = 0.0
        self.max_risk_per_trade = 0.02  # 2% max risk
        self.max_total_exposure = 0.5  # 50% max exposure
        self.is_running = False

        # User controls
        self.user_override = False
        self.allowed_symbols: Set[str] = set()
        self.blocked_symbols: Set[str] = set()
        self.max_position_size: Dict[str, float] = {}

        # Performance tracking
        self.total_pnl = 0.0
        self.trade_count = 0
        self.win_count = 0

    def register_agent(self, agent: BaseAgent):
        """Register an agent with the orchestrator"""
        self.agents[agent.agent_id] = agent

    def start_all(self):
        """Start all registered agents"""
        self.is_running = True
        for agent in self.agents.values():
            agent.start()

    def stop_all(self):
        """Stop all agents"""
        self.is_running = False
        for agent in self.agents.values():
            agent.stop()

    def set_capital(self, amount: float):
        """Set available trading capital"""
        self.capital = amount

    def aggregate_signals(self, signals: List[Signal]) -> Optional[Signal]:
        """
        Aggregate signals from multiple agents.
        Uses weighted voting based on agent accuracy and signal strength.
        """
        if not signals:
            return None

        # Group by symbol and direction
        grouped: Dict[tuple, List[Signal]] = {}
        for sig in signals:
            key = (sig.symbol, sig.direction)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(sig)

        # Find strongest consensus
        best_score = 0
        best_signal = None

        for (symbol, direction), sigs in grouped.items():
            # Calculate weighted score
            total_score = sum(s.score for s in sigs)
            avg_confidence = np.mean([s.confidence for s in sigs])

            # Bonus for agent consensus
            consensus_bonus = len(sigs) / len(self.agents) if self.agents else 0
            final_score = total_score * (1 + consensus_bonus) * avg_confidence

            if final_score > best_score:
                best_score = final_score
                # Create merged signal
                best_signal = Signal(
                    agent_id='orchestrator',
                    symbol=symbol,
                    direction=direction,
                    strength=SignalStrength(min(5, int(final_score / 2) + 1)),
                    confidence=avg_confidence,
                    reasoning=f"Consensus from {len(sigs)} agents",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(minutes=5),
                    metadata={'source_signals': len(sigs), 'score': final_score}
                )

        return best_signal

    def check_risk_limits(self, signal: Signal, position_size: float) -> bool:
        """Check if trade passes risk limits"""
        # Check symbol restrictions
        if signal.symbol in self.blocked_symbols:
            return False

        if self.allowed_symbols and signal.symbol not in self.allowed_symbols:
            return False

        # Check position size limit
        max_size = self.max_position_size.get(signal.symbol, float('inf'))
        if position_size > max_size:
            return False

        # Check total exposure
        current_exposure = sum(p.get('value', 0) for p in self.active_positions.values())
        if (current_exposure + position_size) / self.capital > self.max_total_exposure:
            return False

        # Check per-trade risk
        if position_size / self.capital > self.max_risk_per_trade:
            return False

        return True

    def get_dashboard_data(self) -> Dict:
        """Get data for user dashboard"""
        return {
            'agents': {aid: a.get_status() for aid, a in self.agents.items()},
            'capital': self.capital,
            'total_pnl': self.total_pnl,
            'trade_count': self.trade_count,
            'win_rate': self.win_count / self.trade_count if self.trade_count > 0 else 0,
            'active_positions': len(self.active_positions),
            'is_running': self.is_running
        }


# Utility functions for agent behavior

def generate_unique_id(prefix: str = 'agent') -> str:
    """Generate unique agent ID"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_part = hashlib.md5(str(random.random()).encode()).hexdigest()[:6]
    return f"{prefix}_{timestamp}_{random_part}"


def calculate_position_size(
    capital: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss_price: float
) -> float:
    """Calculate position size based on risk"""
    risk_amount = capital * risk_per_trade
    price_risk = abs(entry_price - stop_loss_price)
    if price_risk == 0:
        return 0
    return risk_amount / price_risk


def normalize_confidence(raw_score: float, min_val: float = 0, max_val: float = 1) -> float:
    """Normalize a score to 0-1 confidence range"""
    return max(min_val, min(max_val, raw_score))
