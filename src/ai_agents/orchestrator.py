"""
Master AI Orchestrator

The brain of the trading system that:
- Coordinates all AI agents
- Aggregates signals from multiple sources
- Makes final trading decisions
- Manages risk across portfolio
- Learns from outcomes
- Provides user control interface
- Ensures safety and compliance

YOU have full control while the AI handles everything else.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum, auto
import numpy as np
import threading
import time
from collections import deque

from .base import (
    BaseAgent, Signal, SignalStrength, MarketSnapshot, MarketCondition,
    AgentState, AgentOrchestrator, generate_unique_id
)
from .market_intelligence import MarketIntelligenceAgent
from .news_analyzer import NewsAnalyzerAgent
from .manipulation_detector import ManipulationDetectorAgent
from .opportunity_sniper import OpportunitySniperAgent
from .company_tracker import CompanyTrackerAgent
from .trade_executor import AutonomousTradeExecutor


class SystemMode(Enum):
    """System operating modes"""
    STOPPED = auto()
    PAPER_TRADING = auto()
    LIVE_TRADING = auto()
    ANALYSIS_ONLY = auto()


class RiskLevel(Enum):
    """Portfolio risk levels"""
    CONSERVATIVE = auto()
    MODERATE = auto()
    AGGRESSIVE = auto()


@dataclass
class TradingDecision:
    """Final trading decision from orchestrator"""
    decision_id: str
    symbol: str
    action: str  # 'buy', 'sell', 'hold', 'close'
    quantity: Optional[float]
    confidence: float
    contributing_agents: List[str]
    reasoning: str
    timestamp: datetime
    executed: bool = False
    execution_result: Optional[Dict] = None


@dataclass
class PerformanceMetrics:
    """System performance metrics"""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    total_trades: int
    best_trade: float
    worst_trade: float
    avg_hold_time: timedelta


class MasterOrchestrator:
    """
    Master AI Trading System Orchestrator

    This is the main class that coordinates everything.
    It gives YOU full control while automating the trading.
    """

    def __init__(self, initial_capital: float = 100000):
        self.orchestrator_id = generate_unique_id('master')
        self.created_at = datetime.now()

        # System state
        self.mode = SystemMode.STOPPED
        self.risk_level = RiskLevel.MODERATE

        # Initialize all agents
        self.market_intel = MarketIntelligenceAgent()
        self.news_analyzer = NewsAnalyzerAgent()
        self.manipulation_detector = ManipulationDetectorAgent()
        self.opportunity_sniper = OpportunitySniperAgent()
        self.company_tracker = CompanyTrackerAgent()
        self.executor = AutonomousTradeExecutor(capital=initial_capital)

        self.agents = {
            'market_intel': self.market_intel,
            'news_analyzer': self.news_analyzer,
            'manipulation_detector': self.manipulation_detector,
            'opportunity_sniper': self.opportunity_sniper,
            'company_tracker': self.company_tracker,
            'executor': self.executor
        }

        # Decision history
        self.decisions: deque = deque(maxlen=1000)
        self.pending_signals: List[Signal] = []

        # Performance tracking
        self.starting_capital = initial_capital
        self.performance_history: deque = deque(maxlen=10000)

        # User controls
        self.auto_trade_enabled = False
        self.require_confirmation = True
        self.allowed_symbols: Set[str] = set()
        self.blocked_symbols: Set[str] = set()
        self.max_position_size = 0.10  # 10% of capital
        self.max_daily_trades = 20
        self.max_daily_loss = 0.03  # 3%

        # Callbacks for user interface
        self.on_signal: Optional[Callable] = None
        self.on_decision: Optional[Callable] = None
        self.on_trade: Optional[Callable] = None
        self.on_alert: Optional[Callable] = None

        # Running state
        self._running = False
        self._main_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Last market snapshot
        self._last_snapshot: Optional[MarketSnapshot] = None

    def start(self, mode: SystemMode = SystemMode.PAPER_TRADING):
        """Start the trading system"""
        self.mode = mode
        self._running = True

        # Configure executor based on mode
        if mode == SystemMode.PAPER_TRADING:
            self.executor.enable_trading(paper_mode=True)
        elif mode == SystemMode.LIVE_TRADING:
            self.executor.enable_trading(paper_mode=False)
        else:
            self.executor.disable_trading()

        # Start all agents
        for agent in self.agents.values():
            if hasattr(agent, 'start'):
                agent.start()

        # Start main loop
        self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self._main_thread.start()

        print(f"Trading system started in {mode.name} mode")

    def stop(self):
        """Stop the trading system"""
        self._running = False
        self.mode = SystemMode.STOPPED

        # Stop all agents
        for agent in self.agents.values():
            if hasattr(agent, 'stop'):
                agent.stop()

        # Close all positions if in live mode
        if self._last_snapshot:
            self.executor.close_all_positions(self._last_snapshot)

        if self._main_thread:
            self._main_thread.join(timeout=5)

        print("Trading system stopped")

    def _main_loop(self):
        """Main orchestration loop"""
        while self._running:
            try:
                if self._last_snapshot:
                    self._process_cycle(self._last_snapshot)

                # Sleep to prevent busy-waiting
                time.sleep(1)

            except Exception as e:
                if self.on_alert:
                    self.on_alert('error', str(e))
                time.sleep(5)

    def update_market_data(self, snapshot: MarketSnapshot):
        """Update with new market data"""
        self._last_snapshot = snapshot

        # Process immediately in separate thread
        threading.Thread(target=self._process_cycle, args=(snapshot,), daemon=True).start()

    def _process_cycle(self, snapshot: MarketSnapshot):
        """Process one analysis cycle"""
        with self._lock:
            # Step 1: Collect signals from all agents
            signals = self._collect_signals(snapshot)

            # Step 2: Filter unsafe signals (manipulation, blocked symbols)
            safe_signals = self._filter_signals(signals, snapshot)

            # Step 3: Aggregate and rank signals
            ranked_signals = self._rank_signals(safe_signals)

            # Step 4: Make trading decisions
            decisions = self._make_decisions(ranked_signals, snapshot)

            # Step 5: Execute decisions (if auto-trade enabled)
            for decision in decisions:
                self._execute_decision(decision, snapshot)

            # Step 6: Update executor (check stops, manage positions)
            self.executor.analyze(snapshot)

            # Step 7: Record performance
            self._record_performance()

    def _collect_signals(self, snapshot: MarketSnapshot) -> List[Signal]:
        """Collect signals from all agents"""
        signals = []

        # Market Intelligence
        sig = self.market_intel.analyze(snapshot)
        if sig:
            signals.append(sig)

        # News Analyzer (if has events)
        sig = self.news_analyzer.analyze(snapshot)
        if sig:
            signals.append(sig)

        # Manipulation Detector
        sig = self.manipulation_detector.analyze(snapshot)
        if sig:
            signals.append(sig)

        # Opportunity Sniper
        sig = self.opportunity_sniper.analyze(snapshot)
        if sig:
            signals.append(sig)

        # Company Tracker
        sig = self.company_tracker.analyze(snapshot)
        if sig:
            signals.append(sig)

        return signals

    def _filter_signals(self, signals: List[Signal], snapshot: MarketSnapshot) -> List[Signal]:
        """Filter out unsafe or blocked signals"""
        filtered = []

        for signal in signals:
            # Check blocked symbols
            if signal.symbol in self.blocked_symbols:
                continue

            # Check allowed symbols (if whitelist active)
            if self.allowed_symbols and signal.symbol not in self.allowed_symbols:
                continue

            # Check for manipulation alerts
            is_safe, warning = self.manipulation_detector.is_symbol_safe(signal.symbol)
            if not is_safe:
                if self.on_alert:
                    self.on_alert('manipulation', f"{signal.symbol}: {warning}")
                continue

            # Check signal expiry
            if not signal.is_valid:
                continue

            filtered.append(signal)

        return filtered

    def _rank_signals(self, signals: List[Signal]) -> List[Signal]:
        """Rank signals by quality and confidence"""
        if not signals:
            return []

        # Calculate composite score for each signal
        scored = []
        for sig in signals:
            # Base score from signal
            score = sig.score

            # Adjust for agent track record
            agent = self.agents.get(sig.agent_id.split('_')[0])
            if agent and hasattr(agent, 'accuracy'):
                accuracy = agent.accuracy
                if accuracy > 0.6:
                    score *= 1.2
                elif accuracy < 0.4:
                    score *= 0.8

            # Adjust for market conditions
            if hasattr(self._last_snapshot, 'market_condition'):
                condition = self._last_snapshot.market_condition
                if condition == MarketCondition.VOLATILE:
                    score *= 0.8  # More cautious in volatile markets
                elif condition == MarketCondition.MANIPULATION_DETECTED:
                    score *= 0.5  # Very cautious

            scored.append((score, sig))

        # Sort by score
        scored.sort(key=lambda x: x[0], reverse=True)
        return [sig for _, sig in scored]

    def _make_decisions(self, signals: List[Signal], snapshot: MarketSnapshot) -> List[TradingDecision]:
        """Make trading decisions from ranked signals"""
        decisions = []

        # Group signals by symbol
        by_symbol: Dict[str, List[Signal]] = {}
        for sig in signals:
            if sig.symbol not in by_symbol:
                by_symbol[sig.symbol] = []
            by_symbol[sig.symbol].append(sig)

        for symbol, symbol_signals in by_symbol.items():
            # Aggregate direction
            long_score = sum(s.score for s in symbol_signals if s.direction == 'long')
            short_score = sum(s.score for s in symbol_signals if s.direction == 'short')

            if long_score > short_score and long_score > 0:
                direction = 'buy'
                confidence = long_score / (long_score + short_score) if (long_score + short_score) > 0 else 0
            elif short_score > long_score and short_score > 0:
                direction = 'sell'
                confidence = short_score / (long_score + short_score) if (long_score + short_score) > 0 else 0
            else:
                continue  # No clear signal

            # Check if we already have a position
            existing_position = self.executor.positions.get(symbol)

            if existing_position:
                # Position management
                if direction == 'sell' and existing_position.quantity > 0:
                    action = 'close'
                elif direction == 'buy' and existing_position.quantity < 0:
                    action = 'close'
                else:
                    action = 'hold'  # Same direction as position
            else:
                action = direction

            # Only create decision if action is actionable
            if action in ['buy', 'sell', 'close']:
                decision = TradingDecision(
                    decision_id=generate_unique_id('decision'),
                    symbol=symbol,
                    action=action,
                    quantity=None,  # Executor will calculate
                    confidence=confidence,
                    contributing_agents=[s.agent_id for s in symbol_signals],
                    reasoning=" | ".join([s.reasoning[:50] for s in symbol_signals[:3]]),
                    timestamp=datetime.now()
                )
                decisions.append(decision)

        return decisions

    def _execute_decision(self, decision: TradingDecision, snapshot: MarketSnapshot):
        """Execute a trading decision"""
        # Check if auto-trade enabled
        if not self.auto_trade_enabled and self.mode != SystemMode.ANALYSIS_ONLY:
            # Queue for confirmation
            self.decisions.append(decision)
            if self.on_decision:
                self.on_decision(decision)
            return

        # Check daily limits
        if self.executor.session_trades >= self.max_daily_trades:
            return

        # Check daily loss limit
        portfolio = self.executor.get_portfolio_summary()
        if portfolio['daily_pnl'] < -self.starting_capital * self.max_daily_loss:
            if self.on_alert:
                self.on_alert('risk', 'Daily loss limit reached')
            return

        # Execute based on action
        if decision.action == 'close':
            order = self.executor.close_position(decision.symbol, snapshot)
        else:
            # Create signal for executor
            sig = Signal(
                agent_id=self.orchestrator_id,
                symbol=decision.symbol,
                direction='long' if decision.action == 'buy' else 'short',
                strength=SignalStrength.STRONG if decision.confidence > 0.7 else SignalStrength.MODERATE,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
                timestamp=datetime.now(),
                expiry=datetime.now() + timedelta(minutes=30)
            )
            order = self.executor.execute_signal(sig, snapshot)

        if order:
            decision.executed = True
            decision.execution_result = {'order_id': order.order_id}
            if self.on_trade:
                self.on_trade(decision, order)

        self.decisions.append(decision)

    def _record_performance(self):
        """Record performance metrics"""
        portfolio = self.executor.get_portfolio_summary()

        self.performance_history.append({
            'timestamp': datetime.now(),
            'total_value': portfolio['total_value'],
            'daily_pnl': portfolio['daily_pnl'],
            'positions': len(portfolio['positions'])
        })

    # ===== USER CONTROL METHODS =====

    def approve_decision(self, decision_id: str, snapshot: MarketSnapshot) -> bool:
        """Manually approve a pending decision"""
        for decision in self.decisions:
            if decision.decision_id == decision_id and not decision.executed:
                self._execute_decision(decision, snapshot)
                return True
        return False

    def reject_decision(self, decision_id: str) -> bool:
        """Reject a pending decision"""
        for decision in self.decisions:
            if decision.decision_id == decision_id:
                decision.executed = True  # Mark as handled
                decision.execution_result = {'rejected': True}
                return True
        return False

    def manual_trade(self, symbol: str, action: str, quantity: float, snapshot: MarketSnapshot):
        """Execute a manual trade"""
        if action == 'buy':
            sig = Signal(
                agent_id='manual',
                symbol=symbol,
                direction='long',
                strength=SignalStrength.VERY_STRONG,
                confidence=1.0,
                reasoning='Manual trade',
                timestamp=datetime.now(),
                expiry=datetime.now() + timedelta(minutes=5),
                metadata={'quantity': quantity}
            )
            self.executor.execute_signal(sig, snapshot)
        elif action == 'sell':
            sig = Signal(
                agent_id='manual',
                symbol=symbol,
                direction='short',
                strength=SignalStrength.VERY_STRONG,
                confidence=1.0,
                reasoning='Manual trade',
                timestamp=datetime.now(),
                expiry=datetime.now() + timedelta(minutes=5),
                metadata={'quantity': quantity}
            )
            self.executor.execute_signal(sig, snapshot)
        elif action == 'close':
            self.executor.close_position(symbol, snapshot)

    def emergency_close_all(self, snapshot: MarketSnapshot):
        """Emergency: Close all positions immediately"""
        orders = self.executor.close_all_positions(snapshot)
        if self.on_alert:
            self.on_alert('emergency', f'Closed {len(orders)} positions')
        return orders

    def add_to_watchlist(self, symbol: str):
        """Add symbol to allowed list"""
        self.allowed_symbols.add(symbol)
        self.blocked_symbols.discard(symbol)

    def block_symbol(self, symbol: str):
        """Block a symbol from trading"""
        self.blocked_symbols.add(symbol)
        self.allowed_symbols.discard(symbol)

    def set_risk_level(self, level: RiskLevel):
        """Set portfolio risk level"""
        self.risk_level = level

        if level == RiskLevel.CONSERVATIVE:
            self.max_position_size = 0.05
            self.max_daily_loss = 0.02
            self.executor.max_position_size_pct = 0.05
        elif level == RiskLevel.MODERATE:
            self.max_position_size = 0.10
            self.max_daily_loss = 0.03
            self.executor.max_position_size_pct = 0.10
        else:  # AGGRESSIVE
            self.max_position_size = 0.15
            self.max_daily_loss = 0.05
            self.executor.max_position_size_pct = 0.15

    def enable_auto_trading(self, enable: bool = True):
        """Enable or disable automatic trading"""
        self.auto_trade_enabled = enable

    def feed_news(self, headline: str, content: str = "", source: str = "unknown", symbols: List[str] = None):
        """Feed news to the news analyzer"""
        event = self.news_analyzer.process_news(headline, content, source, symbols)
        if event.is_breaking and self.on_alert:
            self.on_alert('news', f"Breaking: {headline}")
        return event

    # ===== STATUS AND REPORTING =====

    def get_status(self) -> Dict:
        """Get complete system status"""
        portfolio = self.executor.get_portfolio_summary()

        return {
            'mode': self.mode.name,
            'risk_level': self.risk_level.name,
            'auto_trade': self.auto_trade_enabled,
            'running': self._running,
            'portfolio': portfolio,
            'agents': {
                name: {
                    'state': agent.state.name if hasattr(agent, 'state') else 'N/A',
                    'signals': agent.signals_generated if hasattr(agent, 'signals_generated') else 0,
                    'accuracy': round(agent.accuracy, 2) if hasattr(agent, 'accuracy') else 0
                }
                for name, agent in self.agents.items()
            },
            'pending_decisions': len([d for d in self.decisions if not d.executed]),
            'manipulation_alerts': len(self.manipulation_detector.active_alerts),
            'active_opportunities': len(self.opportunity_sniper.active_opportunities)
        }

    def get_agent_insights(self) -> Dict:
        """Get insights from all agents"""
        insights = {}

        # Market Intelligence
        for symbol in list(self.market_intel.market_structures.keys())[:5]:
            summary = self.market_intel.get_market_summary(symbol)
            if summary:
                insights[f'market_{symbol}'] = summary

        # News summary
        insights['news'] = self.news_analyzer.get_event_summary()

        # Manipulation alerts
        insights['manipulation_alerts'] = self.manipulation_detector.get_all_alerts()

        # Opportunities
        insights['opportunities'] = self.opportunity_sniper.get_active_opportunities()

        # Company watchlists
        insights['company_watchlists'] = self.company_tracker.get_watchlist_summary()

        return insights

    def get_performance_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics"""
        if not self.performance_history:
            return PerformanceMetrics(
                total_return=0, sharpe_ratio=0, max_drawdown=0, win_rate=0,
                avg_win=0, avg_loss=0, profit_factor=0, total_trades=0,
                best_trade=0, worst_trade=0, avg_hold_time=timedelta(0)
            )

        # Calculate returns
        values = [p['total_value'] for p in self.performance_history]
        returns = np.diff(values) / values[:-1] if len(values) > 1 else [0]

        total_return = (values[-1] - self.starting_capital) / self.starting_capital

        # Sharpe ratio (annualized)
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0

        # Max drawdown
        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd

        # Trade statistics
        closed = list(self.executor.closed_positions)
        if closed:
            wins = [p.realized_pnl for p in closed if p.realized_pnl > 0]
            losses = [p.realized_pnl for p in closed if p.realized_pnl < 0]

            win_rate = len(wins) / len(closed) if closed else 0
            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 0
            profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float('inf')
            best = max(wins) if wins else 0
            worst = min(losses) if losses else 0
        else:
            win_rate = avg_win = avg_loss = profit_factor = best = worst = 0

        return PerformanceMetrics(
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            total_trades=len(closed),
            best_trade=best,
            worst_trade=worst,
            avg_hold_time=timedelta(hours=1)  # Placeholder
        )

    def learn_from_outcome(self, symbol: str, outcome: float, metadata: Dict = None):
        """Provide feedback to agents for learning"""
        feedback = {
            'symbol': symbol,
            'outcome': outcome,
            **(metadata or {})
        }

        # Distribute to all agents
        for agent in self.agents.values():
            if hasattr(agent, 'learn'):
                agent.learn(feedback)
