"""
News Analysis Agent
====================
Deep news research and sentiment analysis for market-moving events.

Sources:
- Google News RSS (financial, crypto, stock news)
- Multiple news categories for comprehensive coverage

Analysis:
- Sentiment scoring (positive/negative/neutral)
- Impact assessment (high/medium/low)
- Event categorization
- Trend detection in news flow
"""
import re
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from .base_agent import BaseAgent, AgentOpinion, Action, Confidence


@dataclass
class NewsItem:
    """Single news item with analysis"""
    title: str
    source: str
    published: datetime
    url: str
    sentiment: float  # -1 to 1
    impact: str  # high, medium, low
    category: str
    relevance: float  # 0 to 1
    key_entities: List[str] = field(default_factory=list)


@dataclass
class NewsAnalysis:
    """Comprehensive news analysis for an asset"""
    asset: str
    total_articles: int
    sentiment_score: float  # -1 to 1
    sentiment_trend: str  # improving, declining, stable
    bullish_count: int
    bearish_count: int
    neutral_count: int
    high_impact_events: List[NewsItem]
    recent_headlines: List[str]
    key_themes: List[str]
    risk_events: List[str]
    opportunity_events: List[str]


class NewsAgent(BaseAgent):
    """
    News Analysis Agent
    Performs deep research on market-moving news and events
    """

    def __init__(self):
        super().__init__(
            name="News Research Agent",
            specialty="Deep news analysis, sentiment detection, and event impact assessment"
        )

        # Sentiment word dictionaries
        self.bullish_words = {
            # Strong positive
            'surge', 'soar', 'skyrocket', 'moon', 'breakout', 'rally', 'boom',
            'bullish', 'breakthrough', 'milestone', 'record', 'all-time high',
            'ath', 'explode', 'parabolic', 'massive gains',

            # Moderate positive
            'rise', 'gain', 'up', 'climb', 'advance', 'growth', 'increase',
            'higher', 'positive', 'optimistic', 'strong', 'recovery', 'rebound',
            'outperform', 'beat', 'exceed', 'profit', 'bullrun',

            # Crypto specific
            'adoption', 'institutional', 'etf approved', 'halving', 'accumulation',
            'whale buying', 'spot etf', 'regulation clarity',

            # Market specific
            'fed cut', 'rate cut', 'dovish', 'stimulus', 'liquidity',
            'earnings beat', 'upgrade', 'buy rating', 'target raised'
        }

        self.bearish_words = {
            # Strong negative
            'crash', 'plunge', 'collapse', 'tank', 'dump', 'bearish', 'crisis',
            'disaster', 'panic', 'selloff', 'capitulation', 'bloodbath', 'rekt',
            'meltdown', 'freefall',

            # Moderate negative
            'fall', 'drop', 'decline', 'down', 'lower', 'weak', 'loss',
            'negative', 'concern', 'worry', 'risk', 'uncertainty', 'volatile',
            'correction', 'pullback', 'underperform', 'miss',

            # Crypto specific
            'hack', 'exploit', 'rug pull', 'scam', 'ban', 'crackdown',
            'regulation', 'sec lawsuit', 'delisting', 'whale selling',

            # Market specific
            'fed hike', 'rate hike', 'hawkish', 'inflation', 'recession',
            'layoffs', 'bankruptcy', 'downgrade', 'sell rating', 'target cut'
        }

        self.high_impact_keywords = {
            'breaking', 'urgent', 'just in', 'alert', 'major', 'significant',
            'historic', 'unprecedented', 'emergency', 'sec', 'fed', 'regulation',
            'hack', 'exploit', 'billion', 'trillion', 'etf', 'approval'
        }

        # Asset-specific search terms
        self.asset_terms = {
            'BTC': ['bitcoin', 'btc', 'crypto', 'cryptocurrency'],
            'ETH': ['ethereum', 'eth', 'crypto', 'defi', 'smart contract'],
            'SPY': ['s&p 500', 'sp500', 'spy etf', 'stock market', 'wall street'],
            'QQQ': ['nasdaq', 'qqq', 'tech stocks', 'technology sector'],
            'NVDA': ['nvidia', 'nvda', 'ai chips', 'gpu', 'artificial intelligence']
        }

    def fetch_news(self, asset: str) -> List[NewsItem]:
        """
        Fetch news from multiple sources for comprehensive coverage
        """
        news_items = []

        search_terms = self.asset_terms.get(asset, [asset.lower()])

        for term in search_terms[:2]:  # Limit to avoid rate limiting
            try:
                # Google News RSS
                url = f"https://news.google.com/rss/search?q={term}+stock+OR+crypto+OR+price&hl=en-US&gl=US&ceid=US:en"
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    root = ET.fromstring(response.content)

                    for item in root.findall('.//item')[:10]:
                        title = item.find('title').text if item.find('title') is not None else ""
                        link = item.find('link').text if item.find('link') is not None else ""
                        source = item.find('source').text if item.find('source') is not None else "Unknown"
                        pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""

                        # Parse date
                        try:
                            published = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                        except:
                            published = datetime.now()

                        # Analyze the headline
                        sentiment = self._analyze_sentiment(title)
                        impact = self._assess_impact(title)
                        category = self._categorize_news(title)
                        relevance = self._calculate_relevance(title, asset)

                        news_items.append(NewsItem(
                            title=title,
                            source=source,
                            published=published,
                            url=link,
                            sentiment=sentiment,
                            impact=impact,
                            category=category,
                            relevance=relevance,
                            key_entities=self._extract_entities(title)
                        ))

            except Exception as e:
                continue

        # Sort by relevance and recency
        news_items.sort(key=lambda x: (x.relevance, x.published), reverse=True)

        return news_items[:20]  # Return top 20 most relevant

    def _analyze_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of text on scale of -1 to 1

        Uses weighted keyword matching with context awareness
        """
        text_lower = text.lower()
        score = 0.0
        word_count = 0

        # Check bullish words
        for word in self.bullish_words:
            if word in text_lower:
                # Strong words get higher weight
                if word in ['surge', 'soar', 'skyrocket', 'breakout', 'bullish', 'etf approved']:
                    score += 0.3
                else:
                    score += 0.15
                word_count += 1

        # Check bearish words
        for word in self.bearish_words:
            if word in text_lower:
                if word in ['crash', 'collapse', 'crisis', 'hack', 'ban', 'panic']:
                    score -= 0.3
                else:
                    score -= 0.15
                word_count += 1

        # Normalize
        if word_count > 0:
            score = max(-1, min(1, score))

        return score

    def _assess_impact(self, text: str) -> str:
        """Assess potential market impact of news"""
        text_lower = text.lower()

        high_impact_count = sum(1 for word in self.high_impact_keywords if word in text_lower)

        if high_impact_count >= 2:
            return "high"
        elif high_impact_count == 1:
            return "medium"
        else:
            return "low"

    def _categorize_news(self, text: str) -> str:
        """Categorize news into types"""
        text_lower = text.lower()

        categories = {
            'regulation': ['sec', 'regulation', 'law', 'legal', 'court', 'lawsuit', 'ban', 'approve'],
            'adoption': ['adopt', 'accept', 'payment', 'integration', 'partnership', 'institutional'],
            'technology': ['upgrade', 'update', 'launch', 'release', 'development', 'fork', 'network'],
            'market': ['price', 'trading', 'volume', 'market', 'rally', 'crash', 'surge', 'drop'],
            'earnings': ['earnings', 'revenue', 'profit', 'quarterly', 'report', 'beat', 'miss'],
            'macro': ['fed', 'inflation', 'interest rate', 'economy', 'gdp', 'jobs', 'unemployment']
        }

        for category, keywords in categories.items():
            if any(kw in text_lower for kw in keywords):
                return category

        return 'general'

    def _calculate_relevance(self, text: str, asset: str) -> float:
        """Calculate how relevant news is to the specific asset"""
        text_lower = text.lower()
        relevance = 0.3  # Base relevance

        search_terms = self.asset_terms.get(asset, [asset.lower()])

        for term in search_terms:
            if term in text_lower:
                relevance += 0.2

        # Boost for direct mentions
        if asset.lower() in text_lower:
            relevance += 0.3

        return min(1.0, relevance)

    def _extract_entities(self, text: str) -> List[str]:
        """Extract key entities from text"""
        entities = []

        # Common entities to look for
        entity_patterns = [
            r'\$[A-Z]{2,5}',  # Ticker symbols
            r'[A-Z][a-z]+ (?:Inc|Corp|Ltd|LLC)',  # Company names
            r'(?:SEC|Fed|FBI|DOJ|CFTC)',  # Regulatory bodies
            r'(?:Bitcoin|Ethereum|Solana|Cardano)',  # Crypto names
        ]

        for pattern in entity_patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)

        return list(set(entities))[:5]

    def _identify_themes(self, news_items: List[NewsItem]) -> List[str]:
        """Identify recurring themes in news"""
        theme_counts = {}

        for item in news_items:
            # Count categories
            theme_counts[item.category] = theme_counts.get(item.category, 0) + 1

            # Extract common words
            words = item.title.lower().split()
            for word in words:
                if len(word) > 5 and word not in ['about', 'their', 'would', 'could', 'should']:
                    theme_counts[word] = theme_counts.get(word, 0) + 1

        # Return top themes
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        return [theme for theme, count in sorted_themes[:5] if count >= 2]

    def analyze(self, asset: str, data: Dict[str, Any]) -> AgentOpinion:
        """
        Perform deep news research and analysis
        """
        # Fetch news
        news_items = self.fetch_news(asset)

        if not news_items:
            return AgentOpinion(
                agent_name=self.name,
                asset=asset,
                action=Action.HOLD,
                confidence=Confidence.LOW,
                reasoning="Unable to fetch news data. Recommending caution.",
                key_factors=["No news data available"],
                suggested_hold_time="N/A",
                entry_timing="Wait for news data",
                warnings=["News analysis unavailable"]
            )

        # Calculate overall sentiment
        sentiments = [item.sentiment for item in news_items]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        # Count sentiment distribution
        bullish_count = sum(1 for s in sentiments if s > 0.1)
        bearish_count = sum(1 for s in sentiments if s < -0.1)
        neutral_count = len(sentiments) - bullish_count - bearish_count

        # Identify high impact events
        high_impact = [item for item in news_items if item.impact == "high"]

        # Extract themes
        themes = self._identify_themes(news_items)

        # Identify risks and opportunities
        risks = []
        opportunities = []

        for item in news_items:
            if item.impact in ["high", "medium"]:
                if item.sentiment < -0.2:
                    risks.append(item.title)
                elif item.sentiment > 0.2:
                    opportunities.append(item.title)

        # Determine sentiment trend (compare recent vs older)
        if len(news_items) >= 6:
            recent_sentiment = sum(item.sentiment for item in news_items[:3]) / 3
            older_sentiment = sum(item.sentiment for item in news_items[3:6]) / 3

            if recent_sentiment > older_sentiment + 0.1:
                sentiment_trend = "IMPROVING"
            elif recent_sentiment < older_sentiment - 0.1:
                sentiment_trend = "DECLINING"
            else:
                sentiment_trend = "STABLE"
        else:
            sentiment_trend = "STABLE"

        # Generate recommendation
        action, confidence = self._generate_recommendation(
            avg_sentiment, sentiment_trend, bullish_count, bearish_count, high_impact
        )

        # Build key factors
        key_factors = []

        key_factors.append(f"Overall sentiment: {avg_sentiment:+.2f} ({self._sentiment_label(avg_sentiment)})")
        key_factors.append(f"News distribution: {bullish_count} bullish, {bearish_count} bearish, {neutral_count} neutral")
        key_factors.append(f"Sentiment trend: {sentiment_trend}")

        if high_impact:
            key_factors.append(f"⚠️ {len(high_impact)} high-impact events detected")

        if themes:
            key_factors.append(f"Key themes: {', '.join(themes[:3])}")

        # Reasoning
        reasoning = self._build_reasoning(avg_sentiment, sentiment_trend, high_impact, risks, opportunities)

        # Warnings
        warnings = []
        if risks:
            warnings.append(f"Potential risks: {risks[0][:80]}...")
        if len(high_impact) >= 3:
            warnings.append("Multiple high-impact news events - expect volatility")
        if abs(avg_sentiment) > 0.5:
            warnings.append("Extreme sentiment - potential for reversal")

        # Hold time based on news cycle
        if high_impact:
            hold_time = "2-6 hours (volatile news environment)"
        elif sentiment_trend == "IMPROVING":
            hold_time = "8-16 hours (positive momentum)"
        elif sentiment_trend == "DECLINING":
            hold_time = "Monitor closely, exit on further deterioration"
        else:
            hold_time = "12-24 hours (stable conditions)"

        # Entry timing
        if action in [Action.BUY, Action.STRONG_BUY]:
            if opportunities:
                entry_timing = f"Enter on positive momentum - {opportunities[0][:50]}..."
            else:
                entry_timing = "Sentiment supportive - can enter on minor pullback"
        elif action in [Action.SELL, Action.STRONG_SELL]:
            if risks:
                entry_timing = f"Consider exiting - Risk: {risks[0][:50]}..."
            else:
                entry_timing = "Sentiment deteriorating - reduce exposure"
        else:
            entry_timing = "Wait for clearer news direction"

        return AgentOpinion(
            agent_name=self.name,
            asset=asset,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            suggested_hold_time=hold_time,
            entry_timing=entry_timing,
            indicators={
                "overall_sentiment": avg_sentiment,
                "sentiment_trend": sentiment_trend,
                "bullish_articles": bullish_count,
                "bearish_articles": bearish_count,
                "high_impact_count": len(high_impact),
                "key_themes": themes,
                "recent_headlines": [item.title for item in news_items[:5]],
                "risks": risks[:3],
                "opportunities": opportunities[:3]
            },
            warnings=warnings
        )

    def _sentiment_label(self, score: float) -> str:
        """Convert sentiment score to label"""
        if score > 0.3:
            return "Very Bullish"
        elif score > 0.1:
            return "Bullish"
        elif score < -0.3:
            return "Very Bearish"
        elif score < -0.1:
            return "Bearish"
        else:
            return "Neutral"

    def _generate_recommendation(self, sentiment: float, trend: str, bullish: int, bearish: int, high_impact: List) -> Tuple[Action, Confidence]:
        """Generate trading recommendation from news analysis"""

        score = sentiment  # Base score from sentiment

        # Adjust for trend
        if trend == "IMPROVING":
            score += 0.15
        elif trend == "DECLINING":
            score -= 0.15

        # Adjust for distribution
        if bullish > bearish * 2:
            score += 0.1
        elif bearish > bullish * 2:
            score -= 0.1

        # High impact events
        if high_impact:
            # Average sentiment of high impact news
            hi_sentiment = sum(item.sentiment for item in high_impact) / len(high_impact)
            score = (score + hi_sentiment) / 2  # Weight high impact heavily

        # Determine action
        if score > 0.35:
            return Action.STRONG_BUY, Confidence.HIGH
        elif score > 0.15:
            return Action.BUY, Confidence.MEDIUM
        elif score < -0.35:
            return Action.STRONG_SELL, Confidence.HIGH
        elif score < -0.15:
            return Action.SELL, Confidence.MEDIUM
        else:
            return Action.HOLD, Confidence.LOW

    def _build_reasoning(self, sentiment: float, trend: str, high_impact: List, risks: List, opportunities: List) -> str:
        """Build detailed reasoning for the recommendation"""

        reasoning = f"News sentiment analysis shows {self._sentiment_label(sentiment)} conditions "
        reasoning += f"with a {trend.lower()} trend. "

        if high_impact:
            reasoning += f"There are {len(high_impact)} high-impact news events that could significantly move price. "

        if opportunities:
            reasoning += f"Key opportunity: {opportunities[0][:100]}. "
        elif risks:
            reasoning += f"Key risk to monitor: {risks[0][:100]}. "

        if sentiment > 0.2 and trend == "IMPROVING":
            reasoning += "The combination of positive sentiment and improving trend suggests bullish momentum."
        elif sentiment < -0.2 and trend == "DECLINING":
            reasoning += "Negative sentiment combined with declining trend indicates bearish pressure."
        else:
            reasoning += "Mixed signals suggest waiting for clearer direction."

        return reasoning

    def get_teaching_content(self) -> Dict[str, Any]:
        """Educational content about news analysis"""
        return {
            "name": self.name,
            "specialty": self.specialty,
            "lessons": [
                {
                    "title": "Reading Market News Like a Pro",
                    "content": """
News moves markets. Here's how to interpret financial news effectively:

1. IDENTIFY THE SOURCE
   - Tier 1: Bloomberg, Reuters, WSJ (highly reliable)
   - Tier 2: CNBC, Financial Times (reliable with some sensationalism)
   - Tier 3: Social media, blogs (verify before acting)

2. ASSESS IMPACT
   - HIGH IMPACT: Regulatory decisions, major hacks, earnings misses, Fed announcements
   - MEDIUM IMPACT: Partnership announcements, product launches
   - LOW IMPACT: Opinion pieces, minor updates

3. CHECK TIMING
   - Breaking news = immediate reaction
   - Scheduled news (earnings, Fed) = priced in partially
   - Old news repackaged = minimal impact

4. WATCH FOR MANIPULATION
   - "Pump and dump" schemes use fake news
   - Verify across multiple sources
   - Be suspicious of overly hyped headlines
"""
                },
                {
                    "title": "Sentiment Analysis Fundamentals",
                    "content": """
Understanding market sentiment from news:

BULLISH KEYWORDS (Price likely to rise):
• Strong: surge, soar, breakout, milestone, approved
• Moderate: growth, gain, bullish, adoption, upgrade

BEARISH KEYWORDS (Price likely to fall):
• Strong: crash, collapse, hack, ban, lawsuit
• Moderate: decline, concern, risk, selloff, downgrade

NEUTRAL/UNCERTAIN:
• volatile, uncertain, mixed, consolidating

CRYPTO-SPECIFIC SIGNALS:
📈 Bullish: ETF approval, halving, institutional buying
📉 Bearish: Exchange hack, regulatory crackdown, whale selling

PRO TIP: It's not just WHAT the news says, but HOW the market reacts.
If bullish news doesn't push price up, that's bearish signal!
"""
                },
                {
                    "title": "Trading the News Cycle",
                    "content": """
The news cycle has predictable patterns:

1. BREAKING NEWS (0-15 minutes)
   - Fastest traders react
   - High volatility, wide spreads
   - DANGER ZONE for retail traders

2. DIGESTION PHASE (15-60 minutes)
   - Market processes implications
   - Initial move may reverse or extend
   - Good time to assess, not act

3. TREND ESTABLISHMENT (1-4 hours)
   - True direction becomes clear
   - Volume confirms move
   - BEST ENTRY for swing traders

4. NEWS FADES (4-24 hours)
   - Move exhausts
   - Profit-taking begins
   - Look for next catalyst

STRATEGY: Wait for the dust to settle before trading news.
The second move is often more reliable than the first.
"""
                },
                {
                    "title": "News Categories That Move Markets",
                    "content": """
Different news types have different impacts:

🏛️ REGULATORY NEWS (Highest Impact)
- SEC decisions, government policies
- Can cause 20%+ moves in crypto
- Example: ETF approval = massive rally

💰 MACRO ECONOMIC (High Impact)
- Fed rate decisions
- Inflation data (CPI)
- Jobs reports
- Affects ALL markets

📊 EARNINGS (High Impact for Stocks)
- Beat = usually bullish
- Miss = usually bearish
- Guidance matters more than past results

🔧 TECHNOLOGY (Medium Impact)
- Network upgrades (ETH merge)
- Security vulnerabilities
- New feature launches

🤝 PARTNERSHIPS (Medium Impact)
- Institutional adoption
- Integration announcements
- Often front-run by insiders

💭 OPINION/ANALYSIS (Low Impact)
- Price predictions
- Analyst ratings
- Usually noise, not signal
"""
                }
            ]
        }
