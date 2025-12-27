"""
Opportunity Detector
====================
Identifies and explains trading opportunities with detailed reasoning.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OpportunityType(Enum):
    """Types of trading opportunities"""
    TREND_CONTINUATION = "trend_continuation"
    TREND_REVERSAL = "trend_reversal"
    BREAKOUT = "breakout"
    PULLBACK = "pullback"
    OVERSOLD_BOUNCE = "oversold_bounce"
    OVERBOUGHT_FADE = "overbought_fade"
    NEWS_CATALYST = "news_catalyst"
    SENTIMENT_EXTREME = "sentiment_extreme"


@dataclass
class Opportunity:
    """A detected trading opportunity with full explanation"""
    asset: str
    type: OpportunityType
    direction: str  # LONG or SHORT
    strength: float  # 0-1

    # Detailed explanation
    headline: str
    full_explanation: str
    why_now: str  # Why is this opportunity appearing now?

    # Trade parameters
    entry_zone: str  # Price range to enter
    stop_loss: str
    target_1: str
    target_2: str
    max_hold_time: str

    # Risk assessment
    risk_level: str
    risk_factors: List[str]
    what_could_go_wrong: List[str]

    # Supporting evidence
    technical_evidence: List[str]
    fundamental_evidence: List[str]
    sentiment_evidence: List[str]

    # Educational context
    lesson: str  # What this trade teaches
    similar_historical_setups: str

    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "asset": self.asset,
            "type": self.type.value,
            "direction": self.direction,
            "strength": self.strength,
            "headline": self.headline,
            "full_explanation": self.full_explanation,
            "why_now": self.why_now,
            "entry_zone": self.entry_zone,
            "stop_loss": self.stop_loss,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "max_hold_time": self.max_hold_time,
            "risk_level": self.risk_level,
            "risk_factors": self.risk_factors,
            "what_could_go_wrong": self.what_could_go_wrong,
            "technical_evidence": self.technical_evidence,
            "fundamental_evidence": self.fundamental_evidence,
            "sentiment_evidence": self.sentiment_evidence,
            "lesson": self.lesson,
            "similar_historical_setups": self.similar_historical_setups,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }


class OpportunityDetector:
    """
    Detects and fully explains trading opportunities
    """

    def __init__(self):
        # Opportunity detection thresholds
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.sentiment_extreme = 0.6

    def detect_opportunities(self, analysis) -> List[Opportunity]:
        """
        Analyze unified analysis and detect specific opportunities
        """
        opportunities = []

        asset = analysis.asset
        opinions = analysis.agent_opinions

        tech = opinions.get('technical')
        news = opinions.get('news')
        social = opinions.get('social')
        risk = opinions.get('risk')
        fundamental = opinions.get('fundamental')

        current_price = tech.entry_price if tech else 0

        # Check for RSI Oversold Bounce
        if tech and tech.indicators.get('rsi', 50) < self.rsi_oversold:
            opp = self._build_oversold_opportunity(asset, tech, news, social, risk, current_price)
            opportunities.append(opp)

        # Check for RSI Overbought Fade
        if tech and tech.indicators.get('rsi', 50) > self.rsi_overbought:
            opp = self._build_overbought_opportunity(asset, tech, news, social, risk, current_price)
            opportunities.append(opp)

        # Check for Trend Continuation
        if tech and tech.indicators.get('trend') == 'BULLISH':
            if tech.indicators.get('rsi', 50) < 60:  # Not overbought
                opp = self._build_trend_continuation(asset, tech, news, social, risk, current_price, 'LONG')
                opportunities.append(opp)

        # Check for Sentiment Extreme (Contrarian)
        if social and social.indicators.get('contrarian_signal'):
            opp = self._build_sentiment_extreme_opportunity(asset, tech, news, social, risk, current_price)
            opportunities.append(opp)

        # Check for News Catalyst
        if news and news.indicators.get('high_impact_count', 0) >= 2:
            if news.indicators.get('overall_sentiment', 0) > 0.2:
                opp = self._build_news_catalyst_opportunity(asset, tech, news, social, risk, current_price)
                opportunities.append(opp)

        return opportunities

    def _build_oversold_opportunity(self, asset, tech, news, social, risk, price) -> Opportunity:
        """Build opportunity for oversold bounce"""
        rsi = tech.indicators.get('rsi', 30)
        support = tech.indicators.get('support', price * 0.95)

        return Opportunity(
            asset=asset,
            type=OpportunityType.OVERSOLD_BOUNCE,
            direction="LONG",
            strength=min(1.0, (self.rsi_oversold - rsi) / 20 + 0.5),
            headline=f"{asset} RSI Oversold at {rsi:.0f} - Potential Bounce",
            full_explanation=f"""
{asset} is showing oversold conditions on the RSI indicator, currently at {rsi:.0f}.

When RSI drops below 30, it suggests that selling pressure may be exhausted
and buyers could step in. This creates a potential bounce opportunity.

The current setup shows:
- RSI at {rsi:.0f} (oversold territory below 30)
- Price near support at ${support:,.2f}
- Trend context: {tech.indicators.get('trend', 'Unknown')}

Historically, oversold conditions in {asset} have led to 3-8% bounces
before the next move is determined.
""",
            why_now=f"RSI has dropped to {rsi:.0f}, reaching oversold levels. Selling may be exhausted.",
            entry_zone=f"${price * 0.99:,.2f} - ${price * 1.01:,.2f}",
            stop_loss=f"${price * 0.97:,.2f} (3% below entry)",
            target_1=f"${price * 1.03:,.2f} (3% gain - RSI normalization)",
            target_2=f"${price * 1.06:,.2f} (6% gain - if momentum continues)",
            max_hold_time="4-12 hours for bounce, exit if no bounce within 6 hours",
            risk_level="MEDIUM",
            risk_factors=[
                "Oversold can become more oversold in strong downtrends",
                f"Support at ${support:,.2f} must hold",
                "Requires volume confirmation"
            ],
            what_could_go_wrong=[
                "Price breaks support and continues lower",
                "This is a dead cat bounce in larger downtrend",
                "Negative news catalyst accelerates selling"
            ],
            technical_evidence=[
                f"RSI at {rsi:.0f} (oversold)",
                f"Support level at ${support:,.2f}",
                f"MACD: {tech.indicators.get('macd', 0):.4f}"
            ],
            fundamental_evidence=["Check fundamental agent for context"],
            sentiment_evidence=[
                f"News sentiment: {news.indicators.get('overall_sentiment', 0):+.2f}" if news else "N/A",
                f"Social sentiment: {social.indicators.get('sentiment', 0):+.2f}" if social else "N/A"
            ],
            lesson="""
📚 LESSON: RSI Oversold Bounce

The RSI (Relative Strength Index) measures momentum on a 0-100 scale.
When RSI drops below 30, the asset is considered 'oversold' - meaning
it may have fallen too fast and a bounce is likely.

KEY POINTS:
1. Oversold doesn't mean 'buy immediately' - it means 'watch for bounce'
2. Wait for RSI to start turning up before entry
3. In strong downtrends, oversold can get more oversold
4. Best used in range-bound or uptrending markets

This is a MEAN REVERSION trade - betting price returns to average.
""",
            similar_historical_setups="Oversold bounces in crypto typically yield 3-8% before next direction is clear.",
            confidence=0.6 if tech.indicators.get('trend') != 'BEARISH' else 0.4
        )

    def _build_overbought_opportunity(self, asset, tech, news, social, risk, price) -> Opportunity:
        """Build opportunity for overbought fade"""
        rsi = tech.indicators.get('rsi', 70)
        resistance = tech.indicators.get('resistance', price * 1.05)

        return Opportunity(
            asset=asset,
            type=OpportunityType.OVERBOUGHT_FADE,
            direction="SHORT",
            strength=min(1.0, (rsi - self.rsi_overbought) / 20 + 0.5),
            headline=f"{asset} RSI Overbought at {rsi:.0f} - Potential Pullback",
            full_explanation=f"""
{asset} is showing overbought conditions on the RSI indicator, currently at {rsi:.0f}.

When RSI rises above 70, it suggests buying pressure may be exhausted
and sellers could step in. This creates a potential pullback opportunity.

CAUTION: Overbought conditions in strong uptrends can persist.
This is NOT a signal to immediately short, but to be cautious about new longs.

Consider:
- Taking profits on existing positions
- Waiting for better entry if looking to buy
- Using this as a hedging opportunity
""",
            why_now=f"RSI has risen to {rsi:.0f}, reaching overbought levels. Buyers may be exhausted.",
            entry_zone="Consider reducing long exposure or waiting for pullback",
            stop_loss=f"${price * 1.04:,.2f} above recent high",
            target_1=f"${price * 0.97:,.2f} (3% pullback)",
            target_2=f"${price * 0.94:,.2f} (6% pullback to support)",
            max_hold_time="4-8 hours - quick trade, don't fight strong trends",
            risk_level="MEDIUM-HIGH",
            risk_factors=[
                "Strong trends can stay overbought for extended periods",
                "Fighting momentum is dangerous",
                "News or FOMO can push prices higher"
            ],
            what_could_go_wrong=[
                "Price continues higher despite overbought conditions",
                "FOMO buying creates new momentum",
                "You're fading a strong trend (risky)"
            ],
            technical_evidence=[
                f"RSI at {rsi:.0f} (overbought)",
                f"Resistance at ${resistance:,.2f}",
            ],
            fundamental_evidence=["Check if fundamentals justify the rally"],
            sentiment_evidence=[
                f"FOMO level: {social.indicators.get('fomo_level', 0):.0%}" if social else "N/A"
            ],
            lesson="""
📚 LESSON: Overbought Conditions

When RSI is above 70, an asset is 'overbought' - potentially overextended.

IMPORTANT NUANCES:
1. Overbought ≠ Sell signal (can stay overbought in strong trends)
2. Best used for profit-taking, not aggressive shorting
3. Look for RSI divergence (price higher but RSI lower)
4. Combine with resistance levels for better entries

STRATEGY:
- Take partial profits on longs
- Tighten stop losses
- Wait for confirmation before shorting
""",
            similar_historical_setups="Overbought conditions typically resolve with 2-5% pullbacks before trend continues.",
            confidence=0.5  # Lower confidence - dangerous to fight trends
        )

    def _build_trend_continuation(self, asset, tech, news, social, risk, price, direction) -> Opportunity:
        """Build trend continuation opportunity"""
        trend = tech.indicators.get('trend', 'NEUTRAL')
        sma_20 = tech.indicators.get('sma_20', price)

        return Opportunity(
            asset=asset,
            type=OpportunityType.TREND_CONTINUATION,
            direction=direction,
            strength=0.7 if trend == 'BULLISH' else 0.5,
            headline=f"{asset} in {trend} Trend - Pullback Entry Opportunity",
            full_explanation=f"""
{asset} is in a confirmed {trend} trend based on moving average analysis.

The best way to trade with the trend is to buy pullbacks (in uptrends)
or sell rallies (in downtrends). This reduces risk and improves reward.

Current Structure:
- Price: ${price:,.2f}
- 20 SMA: ${sma_20:,.2f}
- Trend: {trend}

Strategy: Wait for price to pull back to the 20 SMA, then enter
with the trend when price bounces off this dynamic support.
""",
            why_now=f"Asset is trending {trend}. Look for pullback entries rather than chasing.",
            entry_zone=f"Wait for pullback to ${sma_20:,.2f} (20 SMA)",
            stop_loss="Below previous swing low",
            target_1=f"${price * 1.04:,.2f} (4% - conservative)",
            target_2=f"${price * 1.08:,.2f} (8% - trend continuation)",
            max_hold_time="12-24 hours for swing, longer if trend remains intact",
            risk_level="LOW-MEDIUM",
            risk_factors=[
                "Trend could reverse",
                "Pullback could turn into reversal",
                "External catalyst could change direction"
            ],
            what_could_go_wrong=[
                "Trend reverses before entry",
                "No pullback occurs (miss the move)",
                "Pullback is deeper than expected"
            ],
            technical_evidence=[
                f"Trend: {trend}",
                f"Price vs 20 SMA: {'Above' if price > sma_20 else 'Below'}",
                f"RSI: {tech.indicators.get('rsi', 50):.0f}"
            ],
            fundamental_evidence=["Trends often continue when fundamentals are supportive"],
            sentiment_evidence=[
                f"News trend: {news.indicators.get('sentiment_trend', 'N/A')}" if news else "N/A"
            ],
            lesson="""
📚 LESSON: Trend Following

"The trend is your friend" is one of the oldest trading maxims.

KEY PRINCIPLES:
1. Trading WITH the trend has higher success rate
2. Buy pullbacks in uptrends, sell rallies in downtrends
3. Use moving averages to identify and follow trends
4. Don't fight the trend unless you have very strong reasons

ENTRY STRATEGY:
- Wait for pullback to moving average (20/50 EMA)
- Enter when price bounces off the MA
- Stop below the MA or previous swing low
- Target previous highs or higher

Trend trading is the safest and most profitable approach for most traders.
""",
            similar_historical_setups="Trend continuation trades have 55-60% win rate with proper entry timing.",
            confidence=0.65
        )

    def _build_sentiment_extreme_opportunity(self, asset, tech, news, social, risk, price) -> Opportunity:
        """Build contrarian opportunity from extreme sentiment"""
        fomo = social.indicators.get('fomo_level', 0) if social else 0
        fud = social.indicators.get('fud_level', 0) if social else 0

        if fomo > fud:
            direction = "SHORT"
            extreme_type = "FOMO"
            explanation = "Extreme FOMO (fear of missing out) often marks local tops"
        else:
            direction = "LONG"
            extreme_type = "FUD"
            explanation = "Extreme FUD (fear, uncertainty, doubt) often marks local bottoms"

        return Opportunity(
            asset=asset,
            type=OpportunityType.SENTIMENT_EXTREME,
            direction=direction,
            strength=max(fomo, fud),
            headline=f"{asset} Extreme {extreme_type} Detected - Contrarian Opportunity",
            full_explanation=f"""
⚠️ CONTRARIAN SIGNAL DETECTED

{asset} is showing extreme {extreme_type} in social sentiment.

{explanation}.

Sentiment Data:
- FOMO Level: {fomo:.0%}
- FUD Level: {fud:.0%}

Warren Buffett: "Be fearful when others are greedy, and greedy when others are fearful."

This is a CONTRARIAN trade - betting against the crowd.
These trades are higher risk but can be very profitable at turning points.

IMPORTANT: Don't trade this alone. Combine with technical confirmation.
""",
            why_now=f"Social sentiment has reached extreme levels ({extreme_type}: {max(fomo, fud):.0%})",
            entry_zone="Wait for technical confirmation (reversal candle)",
            stop_loss="Tight stop - contrarian trades need quick confirmation",
            target_1="3-5% move as sentiment normalizes",
            target_2="Larger move if trend reversal confirms",
            max_hold_time="2-6 hours initially - extend if reversal confirms",
            risk_level="HIGH",
            risk_factors=[
                "Fighting the crowd is psychologically difficult",
                "Extremes can get more extreme",
                "Requires precise timing"
            ],
            what_could_go_wrong=[
                "Sentiment continues in the same direction",
                "You're early (being early = being wrong)",
                "No technical confirmation"
            ],
            technical_evidence=[
                f"RSI: {tech.indicators.get('rsi', 50):.0f}" if tech else "N/A",
                "Look for reversal candles"
            ],
            fundamental_evidence=["Contrarian trades work best when fundamentals disagree with sentiment"],
            sentiment_evidence=[
                f"FOMO: {fomo:.0%}",
                f"FUD: {fud:.0%}",
                "EXTREME - Contrarian signal active"
            ],
            lesson="""
📚 LESSON: Contrarian Trading

Contrarian trading bets AGAINST the crowd at extremes.

THE LOGIC:
- When everyone is bullish, who's left to buy?
- When everyone is bearish, who's left to sell?
- Extremes create imbalances that resolve with reversals

HOW TO TRADE IT:
1. Identify extreme sentiment (FOMO > 70% or FUD > 70%)
2. Wait for technical confirmation (reversal pattern)
3. Enter with tight stop
4. Be prepared to be wrong - these are lower probability

PSYCHOLOGY:
Going against the crowd is hard. Everyone is saying one thing,
and you're doing the opposite. This requires conviction and discipline.

Remember: You'll often be early. Being early feels like being wrong.
""",
            similar_historical_setups="Sentiment extremes mark reversals ~60% of the time, but timing is difficult.",
            confidence=0.5  # Lower confidence due to difficulty
        )

    def _build_news_catalyst_opportunity(self, asset, tech, news, social, risk, price) -> Opportunity:
        """Build opportunity from positive news catalyst"""
        sentiment = news.indicators.get('overall_sentiment', 0) if news else 0
        headlines = news.indicators.get('recent_headlines', []) if news else []

        return Opportunity(
            asset=asset,
            type=OpportunityType.NEWS_CATALYST,
            direction="LONG" if sentiment > 0 else "SHORT",
            strength=abs(sentiment),
            headline=f"{asset} Positive News Catalyst - Momentum Opportunity",
            full_explanation=f"""
Multiple high-impact news events detected for {asset} with bullish sentiment.

News Sentiment: {sentiment:+.2f}

Recent Headlines:
{chr(10).join(['• ' + h[:80] + '...' for h in headlines[:3]])}

News catalysts can drive sustained moves as information spreads through the market.
Early positioning on news can capture the momentum.

CAUTION: Don't chase if the move has already happened.
The best time to trade news is in the "digestion phase" (15-60 min after).
""",
            why_now="Multiple bullish news events creating momentum",
            entry_zone="Enter on minor pullback, don't chase",
            stop_loss="Below pre-news price level",
            target_1="Initial news reaction target",
            target_2="Extended target if momentum continues",
            max_hold_time="1-4 hours (news fades quickly)",
            risk_level="MEDIUM",
            risk_factors=[
                "News might already be priced in",
                "Fake news or overreaction possible",
                "Reversal after initial spike"
            ],
            what_could_go_wrong=[
                "Buy the rumor, sell the news (already priced in)",
                "Market interprets news differently",
                "Opposing news emerges"
            ],
            technical_evidence=[
                "Check if price broke resistance on news",
                "Volume should confirm the move"
            ],
            fundamental_evidence=[f"News sentiment: {sentiment:+.2f}"],
            sentiment_evidence=[h[:60] + "..." for h in headlines[:3]],
            lesson="""
📚 LESSON: Trading News

News catalysts can create powerful moves. Here's how to trade them:

THE NEWS CYCLE:
1. Breaking (0-15 min): Wild volatility, avoid
2. Digestion (15-60 min): Market figures out impact
3. Trend (1-4 hours): Move in "true" direction
4. Fade (4-24 hours): Move exhausts

BEST PRACTICES:
- Don't trade the first 15 minutes
- Wait for the digestion phase
- Trade in the direction of the digestion
- Have clear stops (pre-news level)
- Quick trades - news fades fast

COMMON TRAP: "Buy the rumor, sell the news"
If price already ran up in anticipation, the news may cause a pullback.
""",
            similar_historical_setups="News-driven moves typically last 2-6 hours before fading.",
            confidence=0.55
        )


# Global detector instance
detector = OpportunityDetector()
