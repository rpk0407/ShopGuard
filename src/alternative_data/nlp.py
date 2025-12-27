"""
Financial NLP Processing

Advanced NLP for financial text:
- Named entity recognition for tickers and companies
- Event extraction (earnings, M&A, lawsuits)
- Relationship extraction
- Temporal parsing

Financial text is domain-specific and requires
specialized models and lexicons.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from enum import Enum


class EventType(Enum):
    """Types of financial events."""
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    DIVIDEND = "dividend"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    SPINOFF = "spinoff"
    LAWSUIT = "lawsuit"
    REGULATORY = "regulatory"
    EXECUTIVE_CHANGE = "executive_change"
    PRODUCT_LAUNCH = "product_launch"
    PARTNERSHIP = "partnership"
    RESTRUCTURING = "restructuring"
    BANKRUPTCY = "bankruptcy"
    IPO = "ipo"
    BUYBACK = "buyback"
    INSIDER_TRADING = "insider_trading"


@dataclass
class FinancialEntity:
    """Extracted financial entity."""
    text: str
    entity_type: str  # COMPANY, TICKER, PERSON, MONEY, PERCENT, DATE
    start_pos: int
    end_pos: int
    normalized: Optional[str] = None  # Normalized form (e.g., ticker symbol)
    confidence: float = 1.0


@dataclass
class FinancialEvent:
    """Detected financial event."""
    event_type: EventType
    entities: List[FinancialEntity]
    description: str
    sentiment_impact: float  # Expected market impact (-1 to 1)
    magnitude: float  # Size of impact (0 to 1)
    timestamp: Optional[datetime] = None
    source_text: str = ""
    confidence: float = 1.0


@dataclass
class Relationship:
    """Relationship between entities."""
    subject: FinancialEntity
    predicate: str  # e.g., "acquires", "partners_with", "sues"
    object: FinancialEntity
    confidence: float = 1.0


class FinancialNLP:
    """
    Core NLP processing for financial text.

    Provides:
    - Tokenization with financial awareness
    - POS tagging optimized for financial text
    - Dependency parsing
    - Semantic similarity
    """

    def __init__(self):
        # Financial abbreviations and terms
        self.financial_abbreviations = {
            'eps': 'earnings per share',
            'p/e': 'price to earnings',
            'yoy': 'year over year',
            'qoq': 'quarter over quarter',
            'mom': 'month over month',
            'cagr': 'compound annual growth rate',
            'ebitda': 'earnings before interest taxes depreciation amortization',
            'roi': 'return on investment',
            'roe': 'return on equity',
            'roa': 'return on assets',
            'm&a': 'mergers and acquisitions',
            'ipo': 'initial public offering',
            'sec': 'securities and exchange commission',
            'fed': 'federal reserve',
            'fomc': 'federal open market committee',
            'gdp': 'gross domestic product',
            'cpi': 'consumer price index',
            'ppi': 'producer price index',
        }

        # Common financial patterns
        self.money_pattern = re.compile(
            r'\$[\d,]+(?:\.\d{1,2})?(?:\s*(?:billion|million|trillion|B|M|T))?',
            re.IGNORECASE
        )
        self.percent_pattern = re.compile(
            r'[-+]?\d+(?:\.\d+)?%'
        )
        self.ticker_pattern = re.compile(
            r'\$[A-Z]{1,5}(?:\.[A-Z])?|\b[A-Z]{1,5}(?:\.[A-Z])?\b'
        )

    def preprocess(self, text: str) -> str:
        """Preprocess financial text."""
        # Normalize whitespace
        text = ' '.join(text.split())

        # Handle cashtags ($AAPL -> AAPL)
        text = re.sub(r'\$([A-Z]{1,5})', r'\1', text)

        return text

    def tokenize(self, text: str) -> List[str]:
        """
        Financial-aware tokenization.

        Keeps financial terms together (e.g., "10-K", "$100M").
        """
        # Preprocess
        text = self.preprocess(text)

        # Basic tokenization preserving financial patterns
        tokens = []

        # Split on whitespace while preserving special patterns
        for word in text.split():
            # Check if it's a money amount
            if self.money_pattern.match(word):
                tokens.append(word)
            # Check if it's a percentage
            elif self.percent_pattern.match(word):
                tokens.append(word)
            # Check if it's a ticker
            elif self.ticker_pattern.match(word):
                tokens.append(word.upper())
            else:
                # Regular tokenization
                tokens.append(word)

        return tokens

    def extract_numbers(self, text: str) -> List[Tuple[str, float, str]]:
        """
        Extract numerical values with context.

        Returns list of (original_text, value, unit).
        """
        numbers = []

        # Money amounts
        for match in self.money_pattern.finditer(text):
            original = match.group()
            # Parse value
            value_str = re.sub(r'[,$]', '', original)

            multiplier = 1
            if 'trillion' in value_str.lower() or value_str.endswith('T'):
                multiplier = 1e12
            elif 'billion' in value_str.lower() or value_str.endswith('B'):
                multiplier = 1e9
            elif 'million' in value_str.lower() or value_str.endswith('M'):
                multiplier = 1e6

            value_str = re.sub(r'[A-Za-z]', '', value_str).strip()
            try:
                value = float(value_str) * multiplier
                numbers.append((original, value, 'USD'))
            except ValueError:
                pass

        # Percentages
        for match in self.percent_pattern.finditer(text):
            original = match.group()
            try:
                value = float(original.replace('%', ''))
                numbers.append((original, value, 'PERCENT'))
            except ValueError:
                pass

        return numbers


class EntityExtractor:
    """
    Named Entity Recognition for financial text.

    Extracts:
    - Company names and ticker symbols
    - People (executives, analysts)
    - Money amounts
    - Dates and times
    - Percentages and metrics
    """

    def __init__(self):
        self.nlp = FinancialNLP()

        # Known company name -> ticker mapping (sample)
        self.company_to_ticker = {
            'apple': 'AAPL',
            'microsoft': 'MSFT',
            'amazon': 'AMZN',
            'google': 'GOOGL',
            'alphabet': 'GOOGL',
            'meta': 'META',
            'facebook': 'META',
            'tesla': 'TSLA',
            'nvidia': 'NVDA',
            'netflix': 'NFLX',
        }

        # Executive title patterns
        self.executive_pattern = re.compile(
            r'\b(CEO|CFO|CTO|COO|President|Chairman|Director|VP|'
            r'Vice President|Chief [A-Za-z]+ Officer)\b',
            re.IGNORECASE
        )

        # Date patterns
        self.date_patterns = [
            re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b', re.IGNORECASE),
            re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'),
            re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
            re.compile(r'\b(?:Q[1-4]|first|second|third|fourth)\s+(?:quarter|Q)\s+\d{4}\b', re.IGNORECASE),
        ]

    def extract_entities(self, text: str) -> List[FinancialEntity]:
        """Extract all financial entities from text."""
        entities = []

        # Extract tickers
        entities.extend(self._extract_tickers(text))

        # Extract companies
        entities.extend(self._extract_companies(text))

        # Extract money
        entities.extend(self._extract_money(text))

        # Extract percentages
        entities.extend(self._extract_percentages(text))

        # Extract dates
        entities.extend(self._extract_dates(text))

        # Extract people
        entities.extend(self._extract_people(text))

        return entities

    def _extract_tickers(self, text: str) -> List[FinancialEntity]:
        """Extract ticker symbols."""
        entities = []
        pattern = re.compile(r'\$([A-Z]{1,5}(?:\.[A-Z])?)')

        for match in pattern.finditer(text):
            entities.append(FinancialEntity(
                text=match.group(),
                entity_type='TICKER',
                start_pos=match.start(),
                end_pos=match.end(),
                normalized=match.group(1)
            ))

        return entities

    def _extract_companies(self, text: str) -> List[FinancialEntity]:
        """Extract company names."""
        entities = []
        text_lower = text.lower()

        for company, ticker in self.company_to_ticker.items():
            start = 0
            while True:
                pos = text_lower.find(company, start)
                if pos == -1:
                    break

                entities.append(FinancialEntity(
                    text=text[pos:pos + len(company)],
                    entity_type='COMPANY',
                    start_pos=pos,
                    end_pos=pos + len(company),
                    normalized=ticker
                ))
                start = pos + 1

        return entities

    def _extract_money(self, text: str) -> List[FinancialEntity]:
        """Extract monetary values."""
        entities = []

        for match in self.nlp.money_pattern.finditer(text):
            entities.append(FinancialEntity(
                text=match.group(),
                entity_type='MONEY',
                start_pos=match.start(),
                end_pos=match.end()
            ))

        return entities

    def _extract_percentages(self, text: str) -> List[FinancialEntity]:
        """Extract percentage values."""
        entities = []

        for match in self.nlp.percent_pattern.finditer(text):
            entities.append(FinancialEntity(
                text=match.group(),
                entity_type='PERCENT',
                start_pos=match.start(),
                end_pos=match.end()
            ))

        return entities

    def _extract_dates(self, text: str) -> List[FinancialEntity]:
        """Extract dates."""
        entities = []

        for pattern in self.date_patterns:
            for match in pattern.finditer(text):
                entities.append(FinancialEntity(
                    text=match.group(),
                    entity_type='DATE',
                    start_pos=match.start(),
                    end_pos=match.end()
                ))

        return entities

    def _extract_people(self, text: str) -> List[FinancialEntity]:
        """Extract person names (especially executives)."""
        entities = []

        # Look for executive titles followed by names
        for match in self.executive_pattern.finditer(text):
            title = match.group()
            # Look for name after title
            after_title = text[match.end():match.end() + 50]
            name_match = re.match(r'\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', after_title)

            if name_match:
                full_text = title + name_match.group()
                entities.append(FinancialEntity(
                    text=full_text,
                    entity_type='PERSON',
                    start_pos=match.start(),
                    end_pos=match.end() + name_match.end(),
                    normalized=name_match.group().strip()
                ))

        return entities

    def get_mentioned_tickers(self, text: str) -> Set[str]:
        """Get set of ticker symbols mentioned in text."""
        entities = self.extract_entities(text)

        tickers = set()
        for entity in entities:
            if entity.entity_type == 'TICKER' and entity.normalized:
                tickers.add(entity.normalized)
            elif entity.entity_type == 'COMPANY' and entity.normalized:
                tickers.add(entity.normalized)

        return tickers


class EventDetector:
    """
    Detect financial events from text.

    Events drive price movements - detecting them early
    provides alpha.
    """

    def __init__(self):
        self.entity_extractor = EntityExtractor()

        # Event patterns
        self.event_patterns = {
            EventType.EARNINGS: [
                r'(?:report|post|announce)[sd]?\s+(?:earnings|results|profit)',
                r'(?:beat|miss|exceed)[sed]?\s+(?:estimates|expectations|consensus)',
                r'EPS\s+(?:of|at)\s+\$[\d.]+',
                r'quarterly\s+(?:earnings|results)',
            ],
            EventType.GUIDANCE: [
                r'(?:raise|lower|maintain|reiterate)[sd]?\s+(?:guidance|outlook|forecast)',
                r'(?:upward|downward)\s+revision',
                r'expect[s]?\s+(?:revenue|earnings|profit)',
                r'full[- ]year\s+(?:guidance|outlook)',
            ],
            EventType.MERGER: [
                r'merg(?:e|er|ing)\s+with',
                r'combine\s+(?:with|into)',
                r'merger\s+agreement',
            ],
            EventType.ACQUISITION: [
                r'acquir(?:e|ed|ing|es)',
                r'(?:buy|purchase)[sd]?\s+(?:out|\$)',
                r'takeover\s+(?:bid|offer)',
                r'acquisition\s+of',
            ],
            EventType.DIVIDEND: [
                r'(?:declare|announce)[sd]?\s+(?:a\s+)?dividend',
                r'dividend\s+(?:increase|cut|suspend)',
                r'special\s+dividend',
            ],
            EventType.BUYBACK: [
                r'(?:share|stock)\s+(?:buyback|repurchase)',
                r'repurchase\s+(?:program|plan)',
                r'buy\s+back\s+(?:shares|stock)',
            ],
            EventType.LAWSUIT: [
                r'(?:file|face)[sd]?\s+(?:lawsuit|litigation|legal action)',
                r'(?:sue|sued|suing)',
                r'class[- ]action',
                r'settlement\s+(?:of|for)',
            ],
            EventType.REGULATORY: [
                r'(?:SEC|FTC|DOJ|FDA)\s+(?:investigation|probe|approval|rejection)',
                r'regulatory\s+(?:approval|clearance|scrutiny)',
                r'antitrust',
            ],
            EventType.EXECUTIVE_CHANGE: [
                r'(?:CEO|CFO|CTO|COO)\s+(?:resign|step down|retire|appointed|named)',
                r'(?:new|incoming)\s+(?:CEO|CFO|chief)',
                r'executive\s+(?:departure|transition)',
            ],
            EventType.PRODUCT_LAUNCH: [
                r'(?:launch|unveil|introduce|announce)[sed]?\s+(?:new|its)',
                r'product\s+(?:launch|announcement)',
                r'new\s+(?:product|service|platform)',
            ],
            EventType.BANKRUPTCY: [
                r'(?:file|filed)\s+(?:for\s+)?(?:bankruptcy|Chapter\s+\d+)',
                r'(?:bankruptcy|insolvency)\s+(?:protection|proceedings)',
            ],
            EventType.IPO: [
                r'(?:IPO|initial public offering)',
                r'(?:go|going)\s+public',
                r'(?:list|listed|listing)\s+on\s+(?:NYSE|NASDAQ)',
            ],
        }

        # Compile patterns
        self.compiled_patterns = {}
        for event_type, patterns in self.event_patterns.items():
            self.compiled_patterns[event_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        # Event sentiment impact (default expected direction)
        self.event_sentiment = {
            EventType.EARNINGS: 0.0,  # Depends on beat/miss
            EventType.GUIDANCE: 0.0,  # Depends on direction
            EventType.DIVIDEND: 0.3,
            EventType.MERGER: 0.1,
            EventType.ACQUISITION: 0.2,  # For acquirer
            EventType.SPINOFF: 0.1,
            EventType.LAWSUIT: -0.3,
            EventType.REGULATORY: 0.0,  # Depends on outcome
            EventType.EXECUTIVE_CHANGE: -0.1,
            EventType.PRODUCT_LAUNCH: 0.2,
            EventType.PARTNERSHIP: 0.2,
            EventType.RESTRUCTURING: -0.2,
            EventType.BANKRUPTCY: -0.8,
            EventType.IPO: 0.0,
            EventType.BUYBACK: 0.3,
            EventType.INSIDER_TRADING: 0.0,
        }

    def detect_events(self, text: str) -> List[FinancialEvent]:
        """Detect all financial events in text."""
        events = []
        entities = self.entity_extractor.extract_entities(text)

        for event_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    # Get context around match
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]

                    # Find related entities
                    related_entities = [
                        e for e in entities
                        if start <= e.start_pos <= end or start <= e.end_pos <= end
                    ]

                    # Calculate sentiment
                    sentiment = self._calculate_event_sentiment(
                        event_type, context
                    )

                    events.append(FinancialEvent(
                        event_type=event_type,
                        entities=related_entities,
                        description=match.group(),
                        sentiment_impact=sentiment,
                        magnitude=0.5,  # Default magnitude
                        source_text=context,
                        confidence=0.8
                    ))

        return self._deduplicate_events(events)

    def _calculate_event_sentiment(
        self,
        event_type: EventType,
        context: str
    ) -> float:
        """Calculate sentiment impact of an event."""
        base_sentiment = self.event_sentiment.get(event_type, 0.0)

        context_lower = context.lower()

        # Adjust for positive/negative context
        positive_modifiers = ['beat', 'exceed', 'raise', 'increase', 'approve', 'win']
        negative_modifiers = ['miss', 'below', 'lower', 'cut', 'reject', 'lose', 'fail']

        modifier = 0.0
        for word in positive_modifiers:
            if word in context_lower:
                modifier += 0.3
        for word in negative_modifiers:
            if word in context_lower:
                modifier -= 0.3

        return max(-1, min(1, base_sentiment + modifier))

    def _deduplicate_events(
        self,
        events: List[FinancialEvent]
    ) -> List[FinancialEvent]:
        """Remove duplicate event detections."""
        if not events:
            return events

        # Sort by confidence
        events.sort(key=lambda e: e.confidence, reverse=True)

        # Keep highest confidence for each event type
        seen_types = set()
        unique_events = []

        for event in events:
            if event.event_type not in seen_types:
                unique_events.append(event)
                seen_types.add(event.event_type)

        return unique_events

    def get_event_signal(
        self,
        events: List[FinancialEvent]
    ) -> Tuple[float, float]:
        """
        Convert events to a trading signal.

        Returns (signal, confidence).
        """
        if not events:
            return 0.0, 0.0

        total_signal = 0.0
        total_weight = 0.0

        for event in events:
            weight = event.magnitude * event.confidence
            total_signal += event.sentiment_impact * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0, 0.0

        signal = total_signal / total_weight
        confidence = min(1.0, total_weight)

        return signal, confidence
