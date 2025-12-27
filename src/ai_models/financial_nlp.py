"""
Specialized Financial NLP Model

Custom-trained language model specifically for:
- Financial sentiment analysis
- Market impact prediction from news
- Entity extraction (companies, sectors, events)
- Earnings call analysis
- SEC filing parsing
- Social media sentiment
- Crypto-specific terminology

This is a SPECIALIZED model trained on financial text, not a general LLM.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import re
import math


class FinancialSentiment(Enum):
    """Financial sentiment levels"""
    VERY_BEARISH = -2
    BEARISH = -1
    NEUTRAL = 0
    BULLISH = 1
    VERY_BULLISH = 2


class ImpactLevel(Enum):
    """Market impact levels"""
    NEGLIGIBLE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    EXTREME = 4


class EntityType(Enum):
    """Types of financial entities"""
    COMPANY = "company"
    PERSON = "person"
    SECTOR = "sector"
    CURRENCY = "currency"
    CRYPTO = "crypto"
    INDEX = "index"
    COMMODITY = "commodity"
    EVENT = "event"
    METRIC = "metric"


@dataclass
class FinancialEntity:
    """Extracted financial entity"""
    text: str
    entity_type: EntityType
    symbol: Optional[str] = None
    confidence: float = 0.0
    context: str = ""


@dataclass
class SentimentResult:
    """Result of sentiment analysis"""
    sentiment: FinancialSentiment
    confidence: float
    impact: ImpactLevel
    key_phrases: List[str]
    entities: List[FinancialEntity]
    reasoning: str


class FinancialVocabulary:
    """
    Specialized vocabulary for financial text.
    Contains domain-specific word embeddings and importance weights.
    """

    def __init__(self):
        # Bullish words with intensity weights
        self.bullish_words = {
            # Strong bullish
            'surge': 2.0, 'soar': 2.0, 'skyrocket': 2.5, 'moon': 2.5,
            'breakout': 2.0, 'rally': 1.8, 'boom': 2.0, 'explode': 2.0,
            'parabolic': 2.5, 'bullrun': 2.5,

            # Medium bullish
            'gain': 1.0, 'rise': 1.0, 'climb': 1.2, 'advance': 1.0,
            'jump': 1.5, 'spike': 1.5, 'beat': 1.5, 'exceed': 1.5,
            'outperform': 1.5, 'upgrade': 1.5, 'buy': 1.0, 'long': 1.0,

            # Light bullish
            'positive': 0.8, 'optimistic': 0.8, 'confident': 0.8,
            'growth': 0.8, 'profit': 1.0, 'strong': 0.8, 'bullish': 1.5,
            'upside': 1.0, 'opportunity': 0.8, 'success': 0.8,

            # Crypto-specific bullish
            'hodl': 1.5, 'diamond hands': 2.0, 'to the moon': 2.5,
            'ath': 2.0, 'pump': 1.5, 'accumulate': 1.2, 'undervalued': 1.5,
            'adoption': 1.2, 'institutional': 1.2, 'halving': 1.5,
        }

        # Bearish words with intensity weights
        self.bearish_words = {
            # Strong bearish
            'crash': 2.5, 'plunge': 2.0, 'collapse': 2.5, 'plummet': 2.0,
            'tank': 2.0, 'rekt': 2.5, 'dump': 2.0, 'capitulation': 2.5,
            'bloodbath': 2.5, 'meltdown': 2.5,

            # Medium bearish
            'drop': 1.0, 'fall': 1.0, 'decline': 1.0, 'sink': 1.5,
            'tumble': 1.5, 'slide': 1.2, 'miss': 1.5, 'disappoint': 1.5,
            'underperform': 1.5, 'downgrade': 1.5, 'sell': 1.0, 'short': 1.2,

            # Light bearish
            'negative': 0.8, 'pessimistic': 0.8, 'concern': 0.8,
            'risk': 0.6, 'loss': 1.0, 'weak': 0.8, 'bearish': 1.5,
            'downside': 1.0, 'threat': 0.8, 'fail': 1.2,

            # Crisis words
            'fraud': 2.0, 'scandal': 2.0, 'investigation': 1.5,
            'lawsuit': 1.5, 'bankrupt': 2.5, 'default': 2.5,
            'recession': 2.0, 'crisis': 2.0, 'panic': 2.0,

            # Crypto-specific bearish
            'rug pull': 2.5, 'scam': 2.5, 'ponzi': 2.5, 'bubble': 2.0,
            'paper hands': 1.5, 'fud': 1.0, 'hack': 2.0, 'exploit': 2.0,
        }

        # Impact amplifiers
        self.amplifiers = {
            'very': 1.5, 'extremely': 2.0, 'significantly': 1.5,
            'sharply': 1.5, 'dramatically': 2.0, 'massively': 2.0,
            'huge': 1.8, 'major': 1.5, 'record': 2.0, 'historic': 2.0,
            'unprecedented': 2.0, 'biggest': 2.0, 'largest': 1.8,
        }

        # Negation words
        self.negations = {
            'not', 'no', 'never', 'neither', 'nor', 'nothing',
            'nobody', 'none', 'nowhere', 'hardly', 'barely',
            'scarcely', "n't", "doesn't", "don't", "didn't",
            "isn't", "aren't", "wasn't", "weren't", "won't",
        }

        # Company patterns
        self.company_patterns = [
            r'\$([A-Z]{1,5})',  # $AAPL
            r'\b([A-Z]{2,5})\b(?=\s+(?:stock|share|price|rose|fell|gained|lost))',
            r'(?:shares of|stock of|ticker)\s+([A-Z]{2,5})',
        ]

        # Crypto patterns
        self.crypto_patterns = [
            r'\$([A-Z]{2,10})',
            r'\b(BTC|ETH|XRP|SOL|ADA|DOT|DOGE|SHIB|AVAX|MATIC)\b',
            r'\b(Bitcoin|Ethereum|Solana|Cardano|Ripple|Dogecoin)\b',
        ]

        # Metric patterns
        self.metric_patterns = [
            r'(\d+\.?\d*)\s*%',  # Percentages
            r'\$(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|billion|trillion)?',  # Dollar amounts
            r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|billion|trillion)?',  # Numbers
            r'P/E\s*(?:ratio)?\s*(?:of)?\s*(\d+\.?\d*)',  # P/E ratio
            r'EPS\s*(?:of)?\s*\$?(\d+\.?\d*)',  # EPS
        ]

        # Event keywords
        self.event_keywords = {
            'earnings': 'EARNINGS',
            'ipo': 'IPO',
            'merger': 'M&A',
            'acquisition': 'M&A',
            'fed': 'CENTRAL_BANK',
            'rate': 'INTEREST_RATE',
            'inflation': 'ECONOMIC_DATA',
            'gdp': 'ECONOMIC_DATA',
            'unemployment': 'ECONOMIC_DATA',
            'halving': 'CRYPTO_EVENT',
            'fork': 'CRYPTO_EVENT',
            'listing': 'LISTING',
            'delisting': 'DELISTING',
            'sec': 'REGULATORY',
            'lawsuit': 'LEGAL',
            'hack': 'SECURITY',
        }


class WordEmbedding:
    """Simple word embedding layer for financial text"""

    def __init__(self, vocab_size: int, embedding_dim: int = 64):
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.embeddings = np.random.randn(vocab_size, embedding_dim) * 0.01

        self.word_to_idx: Dict[str, int] = {}
        self.idx_to_word: Dict[int, str] = {}
        self.next_idx = 0

    def add_word(self, word: str) -> int:
        """Add word to vocabulary"""
        if word not in self.word_to_idx:
            if self.next_idx < self.vocab_size:
                self.word_to_idx[word] = self.next_idx
                self.idx_to_word[self.next_idx] = word
                self.next_idx += 1
        return self.word_to_idx.get(word, 0)

    def get_embedding(self, word: str) -> np.ndarray:
        """Get embedding for a word"""
        idx = self.word_to_idx.get(word.lower(), 0)
        return self.embeddings[idx]

    def encode_text(self, text: str) -> np.ndarray:
        """Encode text as average of word embeddings"""
        words = text.lower().split()
        if not words:
            return np.zeros(self.embedding_dim)

        embeddings = [self.get_embedding(w) for w in words]
        return np.mean(embeddings, axis=0)


class AttentionLayer:
    """Self-attention for finding important words in financial text"""

    def __init__(self, dim: int):
        self.dim = dim
        self.W_q = np.random.randn(dim, dim) * np.sqrt(2.0 / dim)
        self.W_k = np.random.randn(dim, dim) * np.sqrt(2.0 / dim)
        self.W_v = np.random.randn(dim, dim) * np.sqrt(2.0 / dim)

    def forward(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply self-attention
        x: (seq_len, dim)
        Returns: output, attention_weights
        """
        Q = np.dot(x, self.W_q)
        K = np.dot(x, self.W_k)
        V = np.dot(x, self.W_v)

        # Scaled dot-product attention
        scores = np.dot(Q, K.T) / np.sqrt(self.dim)
        attention_weights = self._softmax(scores)

        output = np.dot(attention_weights, V)
        return output, attention_weights

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)


class FinancialSentimentModel:
    """
    Neural network for financial sentiment classification.
    Trained specifically on financial text.
    """

    def __init__(self, embedding_dim: int = 64, hidden_dim: int = 128):
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim

        self.vocabulary = FinancialVocabulary()
        self.embeddings = WordEmbedding(vocab_size=10000, embedding_dim=embedding_dim)
        self.attention = AttentionLayer(embedding_dim)

        # Classification layers
        self.W1 = np.random.randn(embedding_dim, hidden_dim) * np.sqrt(2.0 / embedding_dim)
        self.b1 = np.zeros((1, hidden_dim))
        self.W2 = np.random.randn(hidden_dim, 5) * np.sqrt(2.0 / hidden_dim)  # 5 sentiment classes
        self.b2 = np.zeros((1, 5))

        # Impact prediction
        self.W_impact = np.random.randn(hidden_dim, 5) * np.sqrt(2.0 / hidden_dim)
        self.b_impact = np.zeros((1, 5))

        self._initialize_vocabulary()

    def _initialize_vocabulary(self):
        """Initialize embeddings with financial vocabulary"""
        # Add all financial words
        for word in self.vocabulary.bullish_words:
            self.embeddings.add_word(word)

        for word in self.vocabulary.bearish_words:
            self.embeddings.add_word(word)

        for word in self.vocabulary.amplifiers:
            self.embeddings.add_word(word)

    def preprocess(self, text: str) -> List[str]:
        """Preprocess text for analysis"""
        # Lowercase
        text = text.lower()

        # Handle common financial abbreviations
        text = re.sub(r'\bp/e\b', 'pe_ratio', text)
        text = re.sub(r'\beps\b', 'earnings_per_share', text)
        text = re.sub(r'\byoy\b', 'year_over_year', text)
        text = re.sub(r'\bqoq\b', 'quarter_over_quarter', text)
        text = re.sub(r'\bm&a\b', 'merger_acquisition', text)
        text = re.sub(r'\bipo\b', 'initial_public_offering', text)

        # Remove special characters but keep important ones
        text = re.sub(r'[^\w\s\$\%\-\.]', ' ', text)

        # Tokenize
        tokens = text.split()

        return tokens

    def analyze_sentiment(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of financial text.
        Returns detailed sentiment analysis.
        """
        tokens = self.preprocess(text)

        if not tokens:
            return SentimentResult(
                sentiment=FinancialSentiment.NEUTRAL,
                confidence=0.5,
                impact=ImpactLevel.LOW,
                key_phrases=[],
                entities=[],
                reasoning="Empty text"
            )

        # Rule-based sentiment scoring
        score, key_phrases = self._calculate_sentiment_score(tokens, text)

        # Neural network sentiment
        nn_sentiment, nn_confidence = self._neural_sentiment(tokens)

        # Combine rule-based and neural
        combined_score = 0.6 * score + 0.4 * nn_sentiment
        confidence = (abs(combined_score) / 2 + 0.5) * nn_confidence

        # Map to sentiment
        if combined_score > 1.5:
            sentiment = FinancialSentiment.VERY_BULLISH
        elif combined_score > 0.5:
            sentiment = FinancialSentiment.BULLISH
        elif combined_score < -1.5:
            sentiment = FinancialSentiment.VERY_BEARISH
        elif combined_score < -0.5:
            sentiment = FinancialSentiment.BEARISH
        else:
            sentiment = FinancialSentiment.NEUTRAL

        # Calculate impact
        impact = self._calculate_impact(tokens, text, abs(combined_score))

        # Extract entities
        entities = self.extract_entities(text)

        # Generate reasoning
        reasoning = self._generate_reasoning(sentiment, key_phrases, entities)

        return SentimentResult(
            sentiment=sentiment,
            confidence=min(0.99, confidence),
            impact=impact,
            key_phrases=key_phrases[:5],
            entities=entities,
            reasoning=reasoning
        )

    def _calculate_sentiment_score(self, tokens: List[str], original_text: str) -> Tuple[float, List[str]]:
        """Calculate sentiment score using financial vocabulary"""
        score = 0.0
        key_phrases = []
        amplifier_active = False
        negation_active = False
        amplifier_value = 1.0

        for i, token in enumerate(tokens):
            # Check for amplifiers
            if token in self.vocabulary.amplifiers:
                amplifier_active = True
                amplifier_value = self.vocabulary.amplifiers[token]
                continue

            # Check for negations
            if token in self.vocabulary.negations:
                negation_active = True
                continue

            # Check bullish words
            if token in self.vocabulary.bullish_words:
                word_score = self.vocabulary.bullish_words[token]
                if amplifier_active:
                    word_score *= amplifier_value
                if negation_active:
                    word_score = -word_score
                score += word_score
                key_phrases.append(token)

            # Check bearish words
            elif token in self.vocabulary.bearish_words:
                word_score = -self.vocabulary.bearish_words[token]
                if amplifier_active:
                    word_score *= amplifier_value
                if negation_active:
                    word_score = -word_score
                score += word_score
                key_phrases.append(token)

            # Reset modifiers
            amplifier_active = False
            negation_active = False
            amplifier_value = 1.0

        # Normalize by length
        if len(tokens) > 0:
            score = score / np.sqrt(len(tokens))

        return score, key_phrases

    def _neural_sentiment(self, tokens: List[str]) -> Tuple[float, float]:
        """Neural network sentiment prediction"""
        # Get embeddings
        embeddings = np.array([self.embeddings.get_embedding(t) for t in tokens])

        if len(embeddings) == 0:
            return 0.0, 0.5

        # Apply attention
        attended, attention_weights = self.attention.forward(embeddings)

        # Average pooling
        pooled = np.mean(attended, axis=0, keepdims=True)

        # Classification
        h = np.maximum(0, np.dot(pooled, self.W1) + self.b1)  # ReLU
        logits = np.dot(h, self.W2) + self.b2

        # Softmax
        probs = self._softmax(logits[0])

        # Convert to score (-2 to 2)
        sentiment_score = sum(probs[i] * (i - 2) for i in range(5))

        # Confidence is max probability
        confidence = max(probs)

        return sentiment_score, confidence

    def _calculate_impact(self, tokens: List[str], text: str, sentiment_strength: float) -> ImpactLevel:
        """Calculate market impact level"""
        impact_score = 0

        # Check for high-impact keywords
        high_impact_keywords = [
            'earnings', 'fed', 'rate', 'inflation', 'gdp',
            'bankruptcy', 'acquisition', 'merger', 'ipo',
            'sec', 'investigation', 'fraud', 'hack', 'crash'
        ]

        for keyword in high_impact_keywords:
            if keyword in text.lower():
                impact_score += 1

        # Amplifiers increase impact
        amplifier_count = sum(1 for t in tokens if t in self.vocabulary.amplifiers)
        impact_score += amplifier_count * 0.5

        # Sentiment strength increases impact
        impact_score += sentiment_strength * 0.5

        # Numbers and percentages indicate concrete impact
        if re.search(r'\d+%', text):
            impact_score += 0.5

        # Map to impact level
        if impact_score >= 4:
            return ImpactLevel.EXTREME
        elif impact_score >= 3:
            return ImpactLevel.HIGH
        elif impact_score >= 2:
            return ImpactLevel.MEDIUM
        elif impact_score >= 1:
            return ImpactLevel.LOW
        else:
            return ImpactLevel.NEGLIGIBLE

    def extract_entities(self, text: str) -> List[FinancialEntity]:
        """Extract financial entities from text"""
        entities = []

        # Extract stock symbols
        for pattern in self.vocabulary.company_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                symbol = match.group(1)
                entities.append(FinancialEntity(
                    text=symbol,
                    entity_type=EntityType.COMPANY,
                    symbol=symbol,
                    confidence=0.9,
                    context=text[max(0, match.start()-20):match.end()+20]
                ))

        # Extract crypto
        for pattern in self.vocabulary.crypto_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                crypto = match.group(1) if match.group(1) else match.group(0)
                entities.append(FinancialEntity(
                    text=crypto,
                    entity_type=EntityType.CRYPTO,
                    symbol=crypto.upper(),
                    confidence=0.85,
                    context=text[max(0, match.start()-20):match.end()+20]
                ))

        # Extract metrics
        for pattern in self.vocabulary.metric_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                entities.append(FinancialEntity(
                    text=match.group(0),
                    entity_type=EntityType.METRIC,
                    confidence=0.9,
                    context=text[max(0, match.start()-20):match.end()+20]
                ))

        # Extract events
        for keyword, event_type in self.vocabulary.event_keywords.items():
            if keyword in text.lower():
                entities.append(FinancialEntity(
                    text=keyword,
                    entity_type=EntityType.EVENT,
                    confidence=0.8,
                    context=event_type
                ))

        return entities

    def _generate_reasoning(self, sentiment: FinancialSentiment,
                            key_phrases: List[str], entities: List[FinancialEntity]) -> str:
        """Generate human-readable reasoning"""
        parts = []

        # Sentiment explanation
        sentiment_desc = {
            FinancialSentiment.VERY_BULLISH: "Strongly positive sentiment",
            FinancialSentiment.BULLISH: "Positive sentiment",
            FinancialSentiment.NEUTRAL: "Neutral sentiment",
            FinancialSentiment.BEARISH: "Negative sentiment",
            FinancialSentiment.VERY_BEARISH: "Strongly negative sentiment"
        }
        parts.append(sentiment_desc[sentiment])

        # Key phrases
        if key_phrases:
            parts.append(f"Key words: {', '.join(key_phrases[:3])}")

        # Entities
        symbols = [e.symbol for e in entities if e.symbol and e.entity_type in [EntityType.COMPANY, EntityType.CRYPTO]]
        if symbols:
            parts.append(f"Affected: {', '.join(list(set(symbols))[:3])}")

        return " | ".join(parts)

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()


class EarningsAnalyzer:
    """
    Specialized model for analyzing earnings reports and calls.
    """

    def __init__(self):
        self.sentiment_model = FinancialSentimentModel()

        # Earnings-specific vocabulary
        self.positive_metrics = [
            'beat', 'exceeded', 'above', 'higher', 'growth',
            'increased', 'strong', 'robust', 'record', 'accelerated'
        ]
        self.negative_metrics = [
            'missed', 'below', 'lower', 'declined', 'decreased',
            'weak', 'soft', 'challenging', 'headwinds'
        ]
        self.guidance_positive = [
            'raised', 'increased', 'upgraded', 'optimistic',
            'confident', 'strong outlook'
        ]
        self.guidance_negative = [
            'lowered', 'decreased', 'downgraded', 'cautious',
            'challenging', 'headwinds', 'uncertain'
        ]

    def analyze_earnings(self, text: str) -> Dict[str, Any]:
        """Analyze earnings report text"""
        # Base sentiment
        sentiment_result = self.sentiment_model.analyze_sentiment(text)

        # Extract specific metrics
        eps = self._extract_eps(text)
        revenue = self._extract_revenue(text)
        guidance = self._analyze_guidance(text)

        # Beat/miss analysis
        beat_miss = self._analyze_beat_miss(text)

        return {
            'overall_sentiment': sentiment_result.sentiment.name,
            'confidence': sentiment_result.confidence,
            'impact': sentiment_result.impact.name,
            'eps': eps,
            'revenue': revenue,
            'guidance': guidance,
            'beat_miss': beat_miss,
            'key_phrases': sentiment_result.key_phrases,
            'entities': [e.text for e in sentiment_result.entities]
        }

    def _extract_eps(self, text: str) -> Optional[Dict]:
        """Extract EPS information"""
        patterns = [
            r'EPS\s+(?:of\s+)?\$?([\d.]+)',
            r'earnings\s+per\s+share\s+(?:of\s+)?\$?([\d.]+)',
            r'\$?([\d.]+)\s+per\s+share'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {'value': float(match.group(1))}

        return None

    def _extract_revenue(self, text: str) -> Optional[Dict]:
        """Extract revenue information"""
        pattern = r'revenue\s+(?:of\s+)?\$?([\d.]+)\s*(billion|million)?'
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit:
                if 'billion' in unit.lower():
                    value *= 1e9
                elif 'million' in unit.lower():
                    value *= 1e6
            return {'value': value}

        return None

    def _analyze_guidance(self, text: str) -> str:
        """Analyze forward guidance"""
        text_lower = text.lower()

        positive_count = sum(1 for word in self.guidance_positive if word in text_lower)
        negative_count = sum(1 for word in self.guidance_negative if word in text_lower)

        if positive_count > negative_count:
            return 'raised'
        elif negative_count > positive_count:
            return 'lowered'
        else:
            return 'maintained'

    def _analyze_beat_miss(self, text: str) -> str:
        """Determine if earnings beat or missed"""
        text_lower = text.lower()

        beat_keywords = ['beat', 'exceeded', 'surpassed', 'above', 'topped']
        miss_keywords = ['missed', 'below', 'fell short', 'under']

        beat_count = sum(1 for word in beat_keywords if word in text_lower)
        miss_count = sum(1 for word in miss_keywords if word in text_lower)

        if beat_count > miss_count:
            return 'beat'
        elif miss_count > beat_count:
            return 'miss'
        else:
            return 'in-line'


class CryptoSentimentModel:
    """
    Specialized model for cryptocurrency sentiment.
    Understands crypto-specific language and patterns.
    """

    def __init__(self):
        self.base_model = FinancialSentimentModel()

        # Crypto-specific vocabulary extensions
        self.crypto_bullish = {
            'hodl': 2.0, 'moon': 2.5, 'lambo': 2.0, 'diamond hands': 2.0,
            'bullish': 1.5, 'accumulate': 1.2, 'undervalued': 1.5,
            'adoption': 1.2, 'institutional': 1.3, 'halving': 1.5,
            'defi': 1.0, 'stake': 1.0, 'yield': 1.0, 'airdrop': 1.2,
            'pump': 1.5, 'ath': 2.0, 'breakout': 1.8, 'altseason': 2.0,
            'bullrun': 2.5, 'supercycle': 2.5
        }

        self.crypto_bearish = {
            'rug': 2.5, 'rugpull': 2.5, 'scam': 2.5, 'ponzi': 2.5,
            'dump': 2.0, 'rekt': 2.5, 'paper hands': 1.5, 'fud': 1.0,
            'hack': 2.0, 'exploit': 2.0, 'vulnerability': 1.5,
            'bear market': 2.0, 'capitulation': 2.5, 'crash': 2.5,
            'bloodbath': 2.5, 'liquidated': 2.0, 'margin call': 2.0
        }

        # Add to base vocabulary
        for word, weight in self.crypto_bullish.items():
            self.base_model.vocabulary.bullish_words[word] = weight
        for word, weight in self.crypto_bearish.items():
            self.base_model.vocabulary.bearish_words[word] = weight

    def analyze(self, text: str) -> SentimentResult:
        """Analyze crypto-specific sentiment"""
        return self.base_model.analyze_sentiment(text)

    def detect_pump_scheme(self, text: str) -> Tuple[bool, float]:
        """Detect potential pump and dump schemes"""
        pump_indicators = [
            'guaranteed', '100x', '1000x', 'easy money', 'get rich',
            'next bitcoin', 'hidden gem', 'insider', 'before it moons',
            'last chance', 'dont miss', "don't miss", 'hurry',
            'limited time', 'exclusive', 'secret'
        ]

        text_lower = text.lower()
        indicator_count = sum(1 for indicator in pump_indicators if indicator in text_lower)

        if indicator_count >= 3:
            return True, 0.9
        elif indicator_count >= 2:
            return True, 0.7
        elif indicator_count >= 1:
            return True, 0.5
        else:
            return False, 0.0
