"""
News & Event Analysis Agent

Monitors and analyzes:
- Breaking news and headlines
- Earnings announcements
- Economic data releases
- Geopolitical events
- Natural disasters and crises
- Technology announcements
- Regulatory changes
- Central bank decisions
- Social media trends

Extracts tradeable signals from real-world events.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum, auto
import re
import numpy as np
from collections import deque

from .base import (
    BaseAgent, Signal, SignalStrength, MarketSnapshot,
    AgentState, generate_unique_id, normalize_confidence
)


class EventCategory(Enum):
    """Categories of market-moving events"""
    EARNINGS = auto()
    ECONOMIC_DATA = auto()
    CENTRAL_BANK = auto()
    GEOPOLITICAL = auto()
    NATURAL_DISASTER = auto()
    TECHNOLOGY = auto()
    REGULATORY = auto()
    MERGER_ACQUISITION = auto()
    LEADERSHIP_CHANGE = auto()
    PRODUCT_LAUNCH = auto()
    SCANDAL = auto()
    LEGAL = auto()
    CRYPTOCURRENCY = auto()
    SOCIAL_TREND = auto()


class EventImpact(Enum):
    """Expected market impact level"""
    MINIMAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    EXTREME = 5


class SentimentScore(Enum):
    """Sentiment classification"""
    VERY_BEARISH = -2
    BEARISH = -1
    NEUTRAL = 0
    BULLISH = 1
    VERY_BULLISH = 2


@dataclass
class NewsEvent:
    """Structured news/event data"""
    event_id: str
    headline: str
    summary: str
    source: str
    timestamp: datetime
    category: EventCategory
    impact: EventImpact
    sentiment: SentimentScore
    affected_symbols: List[str]
    affected_sectors: List[str]
    keywords: List[str]
    reliability_score: float  # 0-1, source reliability
    is_breaking: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventPattern:
    """Historical pattern of how events affect markets"""
    category: EventCategory
    avg_price_impact: float  # Percentage move
    avg_duration_hours: float  # How long impact lasts
    typical_direction: str  # 'bullish', 'bearish', 'mixed'
    sample_size: int


class NewsAnalyzerAgent(BaseAgent):
    """
    Analyzes news and events for trading opportunities.

    Key capabilities:
    - Real-time news processing
    - Sentiment extraction
    - Impact prediction
    - Cross-event correlation
    - Historical pattern matching
    - Crisis detection
    - Opportunity identification
    """

    def __init__(self):
        super().__init__(
            agent_id=generate_unique_id('news_analyzer'),
            name="News & Event Analyzer",
            description="Analyzes news, events, and crises for trading signals"
        )

        # Event storage
        self.recent_events: deque = deque(maxlen=1000)
        self.breaking_events: List[NewsEvent] = []
        self.event_patterns: Dict[EventCategory, EventPattern] = {}

        # Sentiment dictionaries
        self._init_sentiment_dictionaries()

        # Source reliability scores
        self.source_reliability = {
            'reuters': 0.95,
            'bloomberg': 0.95,
            'wsj': 0.90,
            'ft': 0.90,
            'cnbc': 0.80,
            'sec_filing': 1.0,
            'fed': 1.0,
            'ecb': 1.0,
            'company_pr': 0.85,
            'twitter': 0.50,
            'reddit': 0.40,
            'unknown': 0.30
        }

        # Sector mappings
        self.sector_keywords = {
            'technology': ['tech', 'software', 'ai', 'cloud', 'semiconductor', 'chip'],
            'finance': ['bank', 'financial', 'insurance', 'lending', 'credit'],
            'healthcare': ['pharma', 'biotech', 'medical', 'drug', 'fda', 'health'],
            'energy': ['oil', 'gas', 'solar', 'renewable', 'energy', 'opec'],
            'retail': ['retail', 'consumer', 'shopping', 'ecommerce'],
            'automotive': ['auto', 'car', 'ev', 'electric vehicle', 'tesla'],
            'crypto': ['bitcoin', 'crypto', 'blockchain', 'ethereum', 'defi']
        }

        # Crisis keywords
        self.crisis_keywords = [
            'crash', 'crisis', 'collapse', 'bankruptcy', 'default', 'emergency',
            'war', 'invasion', 'attack', 'disaster', 'pandemic', 'outbreak',
            'fraud', 'scandal', 'investigation', 'arrest', 'resign'
        ]

        # Opportunity keywords
        self.opportunity_keywords = [
            'breakthrough', 'record', 'surge', 'soar', 'beat', 'exceed',
            'launch', 'announce', 'partnership', 'acquisition', 'approval',
            'upgrade', 'innovation', 'disrupt'
        ]

    def _init_sentiment_dictionaries(self):
        """Initialize sentiment analysis dictionaries"""
        self.positive_words = {
            'surge', 'soar', 'jump', 'gain', 'rise', 'climb', 'rally', 'boom',
            'beat', 'exceed', 'outperform', 'strong', 'bullish', 'upgrade',
            'growth', 'profit', 'success', 'breakthrough', 'approval', 'launch',
            'partnership', 'deal', 'record', 'best', 'positive', 'optimistic'
        }

        self.negative_words = {
            'crash', 'plunge', 'drop', 'fall', 'decline', 'sink', 'tumble',
            'miss', 'fail', 'weak', 'bearish', 'downgrade', 'loss', 'warning',
            'concern', 'risk', 'crisis', 'default', 'bankruptcy', 'fraud',
            'scandal', 'investigation', 'lawsuit', 'cut', 'layoff', 'worst'
        }

        self.amplifiers = {
            'very', 'extremely', 'significantly', 'sharply', 'dramatically',
            'massive', 'huge', 'major', 'substantial'
        }

        self.negators = {'not', 'no', 'never', 'neither', 'hardly', 'barely'}

    def analyze(self, snapshot: MarketSnapshot) -> Optional[Signal]:
        """Analyze current news/events for signals"""
        self.state = AgentState.ANALYZING
        self.last_active = datetime.now()

        # Process any pending events
        self._process_breaking_events()

        # Find tradeable opportunities from recent events
        signals = []
        for event in list(self.recent_events)[-50:]:  # Check last 50 events
            if event.is_breaking or (datetime.now() - event.timestamp).seconds < 300:
                signal = self._event_to_signal(event, snapshot)
                if signal:
                    signals.append(signal)

        self.state = AgentState.IDLE

        if signals:
            signals.sort(key=lambda s: s.score, reverse=True)
            return signals[0]

        return None

    def process_news(self, headline: str, content: str = "", source: str = "unknown",
                     symbols: List[str] = None) -> NewsEvent:
        """Process a news item and extract structured data"""
        # Analyze sentiment
        sentiment = self._analyze_sentiment(headline + " " + content)

        # Detect category
        category = self._detect_category(headline, content)

        # Estimate impact
        impact = self._estimate_impact(headline, content, category)

        # Extract affected entities
        if symbols is None:
            symbols = self._extract_symbols(headline + " " + content)

        sectors = self._extract_sectors(headline + " " + content)
        keywords = self._extract_keywords(headline + " " + content)

        # Check if breaking news
        is_breaking = self._is_breaking_news(headline, impact)

        event = NewsEvent(
            event_id=generate_unique_id('event'),
            headline=headline,
            summary=content[:500] if content else headline,
            source=source,
            timestamp=datetime.now(),
            category=category,
            impact=impact,
            sentiment=sentiment,
            affected_symbols=symbols,
            affected_sectors=sectors,
            keywords=keywords,
            reliability_score=self.source_reliability.get(source.lower(), 0.5),
            is_breaking=is_breaking
        )

        self.recent_events.append(event)
        if is_breaking:
            self.breaking_events.append(event)

        return event

    def _analyze_sentiment(self, text: str) -> SentimentScore:
        """Analyze text sentiment"""
        text_lower = text.lower()
        words = text_lower.split()

        positive_count = 0
        negative_count = 0
        amplifier_active = False
        negator_active = False

        for i, word in enumerate(words):
            # Check for amplifiers
            if word in self.amplifiers:
                amplifier_active = True
                continue

            # Check for negators
            if word in self.negators:
                negator_active = True
                continue

            # Score words
            multiplier = 2 if amplifier_active else 1

            if word in self.positive_words:
                if negator_active:
                    negative_count += multiplier
                else:
                    positive_count += multiplier
            elif word in self.negative_words:
                if negator_active:
                    positive_count += multiplier
                else:
                    negative_count += multiplier

            # Reset modifiers
            amplifier_active = False
            negator_active = False

        # Calculate score
        total = positive_count + negative_count
        if total == 0:
            return SentimentScore.NEUTRAL

        net_score = (positive_count - negative_count) / total

        if net_score > 0.5:
            return SentimentScore.VERY_BULLISH
        elif net_score > 0.2:
            return SentimentScore.BULLISH
        elif net_score < -0.5:
            return SentimentScore.VERY_BEARISH
        elif net_score < -0.2:
            return SentimentScore.BEARISH
        else:
            return SentimentScore.NEUTRAL

    def _detect_category(self, headline: str, content: str) -> EventCategory:
        """Detect event category from text"""
        text = (headline + " " + content).lower()

        # Check for specific patterns
        if any(word in text for word in ['earnings', 'quarter', 'revenue', 'eps', 'profit']):
            return EventCategory.EARNINGS

        if any(word in text for word in ['fed', 'rate', 'fomc', 'central bank', 'ecb', 'boj']):
            return EventCategory.CENTRAL_BANK

        if any(word in text for word in ['gdp', 'inflation', 'cpi', 'jobs', 'employment', 'pmi']):
            return EventCategory.ECONOMIC_DATA

        if any(word in text for word in ['war', 'military', 'sanction', 'tariff', 'diplomatic']):
            return EventCategory.GEOPOLITICAL

        if any(word in text for word in ['earthquake', 'hurricane', 'flood', 'disaster', 'storm']):
            return EventCategory.NATURAL_DISASTER

        if any(word in text for word in ['merge', 'acquisition', 'acquire', 'takeover', 'buyout']):
            return EventCategory.MERGER_ACQUISITION

        if any(word in text for word in ['sec', 'regulation', 'law', 'compliance', 'ban']):
            return EventCategory.REGULATORY

        if any(word in text for word in ['ceo', 'resign', 'appoint', 'executive', 'board']):
            return EventCategory.LEADERSHIP_CHANGE

        if any(word in text for word in ['bitcoin', 'crypto', 'ethereum', 'blockchain']):
            return EventCategory.CRYPTOCURRENCY

        if any(word in text for word in ['launch', 'release', 'unveil', 'product', 'innovation']):
            return EventCategory.PRODUCT_LAUNCH

        if any(word in text for word in ['scandal', 'fraud', 'lawsuit', 'investigation']):
            return EventCategory.SCANDAL

        return EventCategory.TECHNOLOGY  # Default

    def _estimate_impact(self, headline: str, content: str, category: EventCategory) -> EventImpact:
        """Estimate market impact level"""
        text = (headline + " " + content).lower()

        # Crisis keywords indicate high impact
        crisis_count = sum(1 for word in self.crisis_keywords if word in text)
        if crisis_count >= 3:
            return EventImpact.EXTREME
        elif crisis_count >= 2:
            return EventImpact.HIGH

        # Category-based base impact
        category_impact = {
            EventCategory.CENTRAL_BANK: EventImpact.HIGH,
            EventCategory.GEOPOLITICAL: EventImpact.HIGH,
            EventCategory.NATURAL_DISASTER: EventImpact.HIGH,
            EventCategory.MERGER_ACQUISITION: EventImpact.HIGH,
            EventCategory.SCANDAL: EventImpact.HIGH,
            EventCategory.ECONOMIC_DATA: EventImpact.MEDIUM,
            EventCategory.EARNINGS: EventImpact.MEDIUM,
            EventCategory.REGULATORY: EventImpact.MEDIUM,
            EventCategory.LEADERSHIP_CHANGE: EventImpact.MEDIUM,
            EventCategory.CRYPTOCURRENCY: EventImpact.MEDIUM,
            EventCategory.PRODUCT_LAUNCH: EventImpact.LOW,
            EventCategory.TECHNOLOGY: EventImpact.LOW
        }

        base_impact = category_impact.get(category, EventImpact.LOW)

        # Amplifier words increase impact
        if any(word in text for word in self.amplifiers):
            if base_impact.value < EventImpact.EXTREME.value:
                return EventImpact(base_impact.value + 1)

        return base_impact

    def _extract_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from text"""
        # Look for $SYMBOL pattern
        dollar_symbols = re.findall(r'\$([A-Z]{1,5})', text.upper())

        # Look for common patterns like "AAPL stock" or "Apple (AAPL)"
        paren_symbols = re.findall(r'\(([A-Z]{1,5})\)', text.upper())

        # Combine and deduplicate
        symbols = list(set(dollar_symbols + paren_symbols))

        return symbols[:10]  # Limit to 10

    def _extract_sectors(self, text: str) -> List[str]:
        """Extract affected sectors"""
        text_lower = text.lower()
        affected = []

        for sector, keywords in self.sector_keywords.items():
            if any(kw in text_lower for kw in keywords):
                affected.append(sector)

        return affected

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords"""
        text_lower = text.lower()
        keywords = []

        # Check all keyword lists
        for word in self.crisis_keywords + self.opportunity_keywords:
            if word in text_lower:
                keywords.append(word)

        return keywords[:20]

    def _is_breaking_news(self, headline: str, impact: EventImpact) -> bool:
        """Determine if news is breaking/urgent"""
        headline_lower = headline.lower()

        # Breaking indicators
        breaking_words = ['breaking', 'just in', 'alert', 'urgent', 'developing']
        if any(word in headline_lower for word in breaking_words):
            return True

        # High/extreme impact is considered breaking
        if impact.value >= EventImpact.HIGH.value:
            return True

        return False

    def _process_breaking_events(self):
        """Process and clean up breaking events"""
        # Remove events older than 1 hour
        cutoff = datetime.now() - timedelta(hours=1)
        self.breaking_events = [e for e in self.breaking_events if e.timestamp > cutoff]

    def _event_to_signal(self, event: NewsEvent, snapshot: MarketSnapshot) -> Optional[Signal]:
        """Convert event to trading signal"""
        if not event.affected_symbols:
            return None

        # Calculate confidence based on multiple factors
        confidence = 0.3  # Base confidence

        # Impact factor
        confidence += event.impact.value * 0.1

        # Reliability factor
        confidence += event.reliability_score * 0.2

        # Recency factor (more recent = higher confidence)
        age_minutes = (datetime.now() - event.timestamp).seconds / 60
        if age_minutes < 5:
            confidence += 0.2
        elif age_minutes < 15:
            confidence += 0.1

        # Breaking news bonus
        if event.is_breaking:
            confidence += 0.1

        # Determine direction
        if event.sentiment in [SentimentScore.BULLISH, SentimentScore.VERY_BULLISH]:
            direction = 'long'
        elif event.sentiment in [SentimentScore.BEARISH, SentimentScore.VERY_BEARISH]:
            direction = 'short'
        else:
            return None  # No clear direction

        # Signal strength from sentiment intensity
        sentiment_strength = abs(event.sentiment.value)
        if sentiment_strength == 2:
            strength = SignalStrength.STRONG
        elif sentiment_strength == 1:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Boost for high impact
        if event.impact == EventImpact.EXTREME:
            if strength.value < 5:
                strength = SignalStrength(strength.value + 1)

        # Only generate if confidence is high enough
        if confidence < 0.4:
            return None

        self.signals_generated += 1

        return Signal(
            agent_id=self.agent_id,
            symbol=event.affected_symbols[0],  # Primary symbol
            direction=direction,
            strength=strength,
            confidence=normalize_confidence(confidence),
            reasoning=f"{event.category.name}: {event.headline[:100]}",
            timestamp=datetime.now(),
            expiry=datetime.now() + timedelta(minutes=30),
            metadata={
                'event_id': event.event_id,
                'category': event.category.name,
                'impact': event.impact.name,
                'sentiment': event.sentiment.name,
                'source': event.source,
                'all_symbols': event.affected_symbols,
                'sectors': event.affected_sectors
            }
        )

    def get_crisis_alerts(self) -> List[NewsEvent]:
        """Get current crisis-level events"""
        return [e for e in self.breaking_events
                if e.impact.value >= EventImpact.HIGH.value]

    def get_opportunities(self) -> List[NewsEvent]:
        """Get current opportunity events"""
        opportunities = []
        for event in list(self.recent_events)[-100:]:
            if event.sentiment in [SentimentScore.BULLISH, SentimentScore.VERY_BULLISH]:
                if any(kw in event.keywords for kw in self.opportunity_keywords):
                    opportunities.append(event)
        return opportunities

    def learn(self, feedback: Dict[str, Any]):
        """Learn from trade outcomes"""
        event_id = feedback.get('event_id')
        outcome = feedback.get('outcome', 0)

        # Find the event
        for event in self.recent_events:
            if event.event_id == event_id:
                # Update pattern statistics
                category = event.category
                if category not in self.event_patterns:
                    self.event_patterns[category] = EventPattern(
                        category=category,
                        avg_price_impact=outcome,
                        avg_duration_hours=1,
                        typical_direction='mixed',
                        sample_size=1
                    )
                else:
                    pattern = self.event_patterns[category]
                    n = pattern.sample_size
                    # Running average
                    pattern.avg_price_impact = (pattern.avg_price_impact * n + outcome) / (n + 1)
                    pattern.sample_size += 1

                if outcome > 0:
                    self.correct_signals += 1

                break

        self.memory.record_trade(feedback, outcome)

    def get_event_summary(self) -> Dict:
        """Get summary of recent events"""
        hour_ago = datetime.now() - timedelta(hours=1)
        recent = [e for e in self.recent_events if e.timestamp > hour_ago]

        by_category = {}
        for event in recent:
            cat = event.category.name
            if cat not in by_category:
                by_category[cat] = 0
            by_category[cat] += 1

        sentiment_counts = {s.name: 0 for s in SentimentScore}
        for event in recent:
            sentiment_counts[event.sentiment.name] += 1

        return {
            'total_events_1h': len(recent),
            'breaking_count': len(self.breaking_events),
            'by_category': by_category,
            'sentiment_distribution': sentiment_counts,
            'high_impact_events': [e.headline for e in recent if e.impact.value >= 4]
        }
