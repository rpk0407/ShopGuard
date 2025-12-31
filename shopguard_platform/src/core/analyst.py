"""
THE NARRATIVE ENGINE - Senior Trader Explanations
===================================================
Translates complex math into plain English that sounds like
a senior trader explaining the trade to a junior.

No more cryptic numbers. Every signal comes with a story.

"We're going LONG because social sentiment is heating up while
smart money has been quietly accumulating. The market structure
shows a clean trend forming - this is a high-conviction setup."
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class MarketNarrative(Enum):
    """Types of market stories"""
    ACCUMULATION_BREAKOUT = "accumulation_breakout"
    WHALE_ABSORPTION = "whale_absorption"
    TREND_CONTINUATION = "trend_continuation"
    MEAN_REVERSION = "mean_reversion"
    PANIC_CAPITULATION = "panic_capitulation"
    EUPHORIC_TOP = "euphoric_top"
    QUIET_STRENGTH = "quiet_strength"
    CHAOTIC_AVOID = "chaotic_avoid"


@dataclass
class TradeNarrative:
    """Complete narrative for a trade signal"""
    # Core story
    headline: str           # One-liner summary
    story: str              # Full paragraph explanation
    narrative_type: MarketNarrative

    # Component explanations
    bio_explanation: str    # What social/viral metrics say
    physics_explanation: str  # What market structure says
    micro_explanation: str   # What smart money is doing

    # Confidence
    conviction_level: str   # "High", "Medium", "Low"
    conviction_reason: str

    # Risk context
    risk_warning: str       # What could go wrong
    invalidation: str       # When to exit if wrong

    # Timing
    timestamp: datetime
    time_horizon: str       # "Scalp", "Swing", "Position"

    def to_dict(self) -> Dict:
        return {
            'headline': self.headline,
            'story': self.story,
            'narrative_type': self.narrative_type.value,
            'bio': self.bio_explanation,
            'physics': self.physics_explanation,
            'micro': self.micro_explanation,
            'conviction': self.conviction_level,
            'conviction_reason': self.conviction_reason,
            'risk_warning': self.risk_warning,
            'invalidation': self.invalidation,
            'timestamp': self.timestamp.isoformat(),
            'time_horizon': self.time_horizon
        }

    def format_full_analysis(self) -> str:
        """Format as a professional analysis report"""
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                         TRADE ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 {self.headline}

{self.story}

┌─────────────────────────────────────────────────────────────────┐
│ THREE-PILLAR BREAKDOWN                                          │
├─────────────────────────────────────────────────────────────────┤
│ 🧬 BIO (Social Sentiment):                                      │
│    {self.bio_explanation}
│                                                                 │
│ ⚛️  PHYSICS (Market Structure):                                 │
│    {self.physics_explanation}
│                                                                 │
│ 🔬 MICRO (Smart Money):                                         │
│    {self.micro_explanation}
└─────────────────────────────────────────────────────────────────┘

Conviction: {self.conviction_level} - {self.conviction_reason}
Time Horizon: {self.time_horizon}

⚠️  RISK WARNING: {self.risk_warning}
❌ INVALIDATION: {self.invalidation}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


class NarrativeEngine:
    """
    THE STORYTELLER
    ================
    Converts trading signals into human-readable narratives.

    Every trade needs a story. If you can't explain why you're
    taking a trade in plain English, you shouldn't take it.
    """

    def __init__(self):
        # Bio metric descriptions
        self.viral_descriptions = {
            (1.5, float('inf')): ("exploding", "viral growth is explosive"),
            (1.3, 1.5): ("heating up", "momentum is building rapidly"),
            (1.1, 1.3): ("warming", "interest is picking up"),
            (0.9, 1.1): ("stable", "sentiment is neutral"),
            (0.7, 0.9): ("cooling", "interest is fading"),
            (0.0, 0.7): ("dying", "sentiment has collapsed"),
        }

        # Entropy descriptions (lower = more ordered)
        self.entropy_descriptions = {
            (0.0, 2.0): ("highly ordered", "the market is in a clean, predictable state"),
            (2.0, 2.3): ("ordered", "market structure is clean"),
            (2.3, 2.6): ("moderately ordered", "some noise but readable"),
            (2.6, 2.9): ("transitional", "market is deciding direction"),
            (2.9, 3.2): ("chaotic", "high noise, low predictability"),
            (3.2, float('inf')): ("maximum chaos", "pure noise, no edge"),
        }

        # Hurst descriptions
        self.hurst_descriptions = {
            (0.7, 1.0): ("strong trending", "clear directional momentum"),
            (0.6, 0.7): ("trending", "consistent directional bias"),
            (0.55, 0.6): ("weak trend", "slight directional tendency"),
            (0.45, 0.55): ("random walk", "no predictable direction"),
            (0.3, 0.45): ("mean-reverting", "snapping back to average"),
            (0.0, 0.3): ("strong mean-reversion", "extreme reversion expected"),
        }

        # CVD descriptions
        self.cvd_descriptions = {
            (200, float('inf')): ("heavy accumulation", "whales are loading"),
            (50, 200): ("accumulation", "smart money buying"),
            (-50, 50): ("balanced", "no clear bias"),
            (-200, -50): ("distribution", "smart money selling"),
            (float('-inf'), -200): ("heavy distribution", "whales are dumping"),
        }

        # Phase descriptions
        self.phase_descriptions = {
            'stable': "consolidating in a range",
            'accumulation': "being quietly accumulated by smart money",
            'recovery': "recovering from a pullback",
            'euphoria': "in a euphoric rally - caution advised",
            'crash': "in a sharp correction",
        }

        logger.info("Narrative Engine initialized - ready to tell stories")

    def _get_description(self, value: float, mapping: Dict) -> Tuple[str, str]:
        """Get description from a value range mapping"""
        for (low, high), (short, long) in mapping.items():
            if low <= value < high:
                return short, long
        return "unknown", "unable to classify"

    def _get_cvd_description(self, cvd: float) -> Tuple[str, str]:
        """Get CVD description (handles negative ranges)"""
        if cvd >= 200:
            return "heavy accumulation", "whales are loading aggressively"
        elif cvd >= 50:
            return "accumulation", "smart money is buying"
        elif cvd >= -50:
            return "balanced", "no clear institutional bias"
        elif cvd >= -200:
            return "distribution", "smart money is selling"
        else:
            return "heavy distribution", "institutions are dumping"

    def generate_narrative(
        self,
        signal_type: str,
        confidence: float,
        conviction: float,
        asset: str,
        price: float,
        # Metrics
        entropy: float,
        hurst: float,
        viral_k: float,
        cvd: float,
        phase: str,
        # Pillar states
        bio_check: bool,
        physics_check: bool,
        micro_check: bool,
        cvd_check: bool,
        # Optional context
        stop_loss: float = None,
        take_profit: float = None,
        atr_pct: float = None,
    ) -> TradeNarrative:
        """
        MAIN METHOD: Generate complete trade narrative.

        This is where math becomes meaning.
        """
        # Get descriptions for each metric
        viral_short, viral_long = self._get_description(viral_k, self.viral_descriptions)
        entropy_short, entropy_long = self._get_description(entropy, self.entropy_descriptions)
        hurst_short, hurst_long = self._get_description(hurst, self.hurst_descriptions)
        cvd_short, cvd_long = self._get_cvd_description(cvd)
        phase_desc = self.phase_descriptions.get(phase, f"in {phase} phase")

        # Count aligned pillars
        pillars_aligned = sum([bio_check, physics_check, micro_check, cvd_check])

        # Determine narrative type
        narrative_type = self._classify_narrative(
            signal_type, phase, viral_k, cvd, entropy, hurst, pillars_aligned
        )

        # Generate headline
        headline = self._generate_headline(
            signal_type, asset, narrative_type, confidence
        )

        # Generate the main story
        story = self._generate_story(
            signal_type=signal_type,
            asset=asset,
            price=price,
            phase=phase,
            phase_desc=phase_desc,
            viral_short=viral_short,
            viral_long=viral_long,
            entropy_short=entropy_short,
            entropy_long=entropy_long,
            hurst_short=hurst_short,
            hurst_long=hurst_long,
            cvd_short=cvd_short,
            cvd_long=cvd_long,
            pillars_aligned=pillars_aligned,
            narrative_type=narrative_type
        )

        # Generate component explanations
        bio_explanation = self._explain_bio(viral_k, viral_short, viral_long, bio_check)
        physics_explanation = self._explain_physics(entropy, hurst, entropy_short, hurst_short, physics_check)
        micro_explanation = self._explain_micro(cvd, cvd_short, cvd_long, phase, micro_check)

        # Determine conviction
        conviction_level, conviction_reason = self._assess_conviction(
            confidence, conviction, pillars_aligned, phase
        )

        # Generate risk context
        risk_warning = self._generate_risk_warning(phase, entropy, viral_k, signal_type)
        invalidation = self._generate_invalidation(signal_type, stop_loss, price, entropy)

        # Determine time horizon
        time_horizon = self._determine_time_horizon(hurst, phase, atr_pct)

        return TradeNarrative(
            headline=headline,
            story=story,
            narrative_type=narrative_type,
            bio_explanation=bio_explanation,
            physics_explanation=physics_explanation,
            micro_explanation=micro_explanation,
            conviction_level=conviction_level,
            conviction_reason=conviction_reason,
            risk_warning=risk_warning,
            invalidation=invalidation,
            timestamp=datetime.now(),
            time_horizon=time_horizon
        )

    def _classify_narrative(
        self,
        signal_type: str,
        phase: str,
        viral_k: float,
        cvd: float,
        entropy: float,
        hurst: float,
        pillars: int
    ) -> MarketNarrative:
        """Classify the type of market narrative"""

        if phase == 'crash':
            return MarketNarrative.PANIC_CAPITULATION

        if phase == 'euphoria' and viral_k > 1.5:
            return MarketNarrative.EUPHORIC_TOP

        if entropy > 3.0:
            return MarketNarrative.CHAOTIC_AVOID

        if phase == 'accumulation' and cvd > 100:
            return MarketNarrative.WHALE_ABSORPTION

        if phase == 'recovery' and pillars >= 3:
            return MarketNarrative.ACCUMULATION_BREAKOUT

        if hurst > 0.65 and entropy < 2.5:
            return MarketNarrative.TREND_CONTINUATION

        if hurst < 0.45:
            return MarketNarrative.MEAN_REVERSION

        if entropy < 2.3 and viral_k > 1.1:
            return MarketNarrative.QUIET_STRENGTH

        return MarketNarrative.TREND_CONTINUATION

    def _generate_headline(
        self,
        signal_type: str,
        asset: str,
        narrative_type: MarketNarrative,
        confidence: float
    ) -> str:
        """Generate a punchy headline"""

        headlines = {
            MarketNarrative.ACCUMULATION_BREAKOUT: f"🚀 {asset} BREAKOUT: Smart money accumulation complete",
            MarketNarrative.WHALE_ABSORPTION: f"🐋 {asset}: Whales are absorbing all selling pressure",
            MarketNarrative.TREND_CONTINUATION: f"📈 {asset}: Trend intact, riding the wave",
            MarketNarrative.MEAN_REVERSION: f"↩️ {asset}: Snapping back to mean",
            MarketNarrative.PANIC_CAPITULATION: f"🔴 {asset} CRASH: Capitulation in progress",
            MarketNarrative.EUPHORIC_TOP: f"⚠️ {asset}: Euphoria detected - distribution likely",
            MarketNarrative.QUIET_STRENGTH: f"💪 {asset}: Quiet strength building",
            MarketNarrative.CHAOTIC_AVOID: f"🌪️ {asset}: Chaos mode - no clear edge",
        }

        base = headlines.get(narrative_type, f"{asset}: Signal detected")

        if confidence >= 0.8:
            return base + " [HIGH CONVICTION]"
        elif confidence >= 0.6:
            return base
        else:
            return base + " [LOW CONVICTION]"

    def _generate_story(
        self,
        signal_type: str,
        asset: str,
        price: float,
        phase: str,
        phase_desc: str,
        viral_short: str,
        viral_long: str,
        entropy_short: str,
        entropy_long: str,
        hurst_short: str,
        hurst_long: str,
        cvd_short: str,
        cvd_long: str,
        pillars_aligned: int,
        narrative_type: MarketNarrative
    ) -> str:
        """Generate the main story paragraph"""

        direction = "LONG" if signal_type in ["BUY", "STRONG_BUY"] else "SHORT" if signal_type in ["SELL", "STRONG_SELL"] else "NEUTRAL"

        if narrative_type == MarketNarrative.ACCUMULATION_BREAKOUT:
            return (
                f"We're entering {direction} on {asset} at ${price:,.2f} because the setup is textbook. "
                f"Social sentiment is {viral_short} while smart money shows {cvd_short} - classic accumulation pattern. "
                f"The market structure is {entropy_short} with {hurst_short} behavior, confirming directional bias. "
                f"With {pillars_aligned}/4 pillars aligned, this is a high-probability entry after the accumulation phase completes."
            )

        elif narrative_type == MarketNarrative.WHALE_ABSORPTION:
            return (
                f"This is a whale absorption play on {asset}. Despite the noise, large players are "
                f"quietly accumulating - {cvd_long}. The viral metrics show sentiment is {viral_short}, "
                f"but the real story is in the order flow. Structure is {entropy_short} and {hurst_short}. "
                f"We're positioning with the smart money at ${price:,.2f}."
            )

        elif narrative_type == MarketNarrative.TREND_CONTINUATION:
            return (
                f"The trend on {asset} remains intact. Market structure is {entropy_short} with "
                f"{hurst_short} price action - {hurst_long}. Sentiment is {viral_short} and "
                f"institutions show {cvd_short}. This is a bread-and-butter trend continuation "
                f"entry at ${price:,.2f}. We're riding the wave, not fighting it."
            )

        elif narrative_type == MarketNarrative.PANIC_CAPITULATION:
            return (
                f"🚨 {asset} is in CRASH mode at ${price:,.2f}. This is panic capitulation - "
                f"sentiment has collapsed ({viral_short}), structure is chaotic ({entropy_short}), "
                f"and we're seeing {cvd_short}. DO NOT catch falling knives. "
                f"Wait for accumulation signals before considering entry."
            )

        elif narrative_type == MarketNarrative.EUPHORIC_TOP:
            return (
                f"⚠️ Warning: {asset} is showing signs of euphoric top at ${price:,.2f}. "
                f"Viral metrics are {viral_short} - this is FOMO territory. "
                f"Smart money shows {cvd_short} while retail piles in. "
                f"Structure is {entropy_short}. Consider taking profits, not adding."
            )

        elif narrative_type == MarketNarrative.CHAOTIC_AVOID:
            return (
                f"No clear edge on {asset} at ${price:,.2f}. Market is in chaos mode - "
                f"structure is {entropy_short}, making prediction unreliable. "
                f"Sentiment is {viral_short} and institutional flow is {cvd_short}. "
                f"This is a WAIT situation. Let the noise settle before acting."
            )

        else:
            return (
                f"Analyzing {asset} at ${price:,.2f}. The market is {phase_desc}. "
                f"Viral metrics show sentiment is {viral_short}, while structure is {entropy_short}. "
                f"Smart money flow indicates {cvd_short}. With {pillars_aligned}/4 pillars aligned, "
                f"we're looking at a {'favorable' if pillars_aligned >= 2 else 'marginal'} setup."
            )

    def _explain_bio(self, viral_k: float, short: str, long: str, passed: bool) -> str:
        """Explain the bio/social component"""
        status = "✓ ALIGNED" if passed else "✗ NOT ALIGNED"
        return (
            f"Viral K-Factor: {viral_k:.2f} ({short})\n"
            f"│    Interpretation: {long}\n"
            f"│    Status: {status}"
        )

    def _explain_physics(self, entropy: float, hurst: float, e_short: str, h_short: str, passed: bool) -> str:
        """Explain the physics/structure component"""
        status = "✓ ALIGNED" if passed else "✗ NOT ALIGNED"
        return (
            f"Entropy: {entropy:.2f} ({e_short}) | Hurst: {hurst:.2f} ({h_short})\n"
            f"│    Market structure is {'clean and predictable' if passed else 'noisy or unclear'}\n"
            f"│    Status: {status}"
        )

    def _explain_micro(self, cvd: float, short: str, long: str, phase: str, passed: bool) -> str:
        """Explain the micro/smart money component"""
        status = "✓ ALIGNED" if passed else "✗ NOT ALIGNED"
        return (
            f"CVD: {cvd:+.0f} ({short}) | Phase: {phase}\n"
            f"│    Interpretation: {long}\n"
            f"│    Status: {status}"
        )

    def _assess_conviction(
        self,
        confidence: float,
        conviction: float,
        pillars: int,
        phase: str
    ) -> Tuple[str, str]:
        """Assess conviction level and reason"""

        if confidence >= 0.8 and pillars >= 3:
            return "HIGH", f"Strong signal ({confidence:.0%}) with {pillars}/4 pillars aligned"
        elif confidence >= 0.6 and pillars >= 2:
            return "MEDIUM", f"Decent signal ({confidence:.0%}) with {pillars}/4 pillars aligned"
        elif confidence >= 0.5:
            return "LOW", f"Marginal signal ({confidence:.0%}) - trade small or wait"
        else:
            return "VERY LOW", f"Weak signal ({confidence:.0%}) - consider waiting for better setup"

    def _generate_risk_warning(
        self,
        phase: str,
        entropy: float,
        viral_k: float,
        signal_type: str
    ) -> str:
        """Generate contextual risk warning"""

        warnings = []

        if phase == 'euphoria':
            warnings.append("Late-stage move - watch for distribution")

        if entropy > 2.8:
            warnings.append("High entropy - increased noise and false signals")

        if viral_k > 1.5:
            warnings.append("Overheated sentiment - vulnerable to reversal")

        if viral_k < 0.8:
            warnings.append("Weak momentum - move may lack follow-through")

        if phase == 'crash':
            warnings.append("Active crash - maximum caution required")

        if not warnings:
            return "Standard market conditions - stick to your plan"

        return "; ".join(warnings)

    def _generate_invalidation(
        self,
        signal_type: str,
        stop_loss: float,
        price: float,
        entropy: float
    ) -> str:
        """Generate invalidation criteria"""

        if stop_loss:
            direction = "below" if signal_type in ["BUY", "STRONG_BUY"] else "above"
            return f"Exit if price moves {direction} ${stop_loss:,.2f} (your stop loss)"

        if signal_type in ["BUY", "STRONG_BUY"]:
            invalidation_price = price * 0.97
            return f"Exit if price drops below ${invalidation_price:,.2f} (-3%)"
        elif signal_type in ["SELL", "STRONG_SELL"]:
            invalidation_price = price * 1.03
            return f"Exit if price rises above ${invalidation_price:,.2f} (+3%)"
        else:
            return "No active position - no invalidation criteria"

    def _determine_time_horizon(
        self,
        hurst: float,
        phase: str,
        atr_pct: float = None
    ) -> str:
        """Determine appropriate time horizon for this trade"""

        if phase in ['crash', 'euphoria']:
            return "Scalp (minutes to hours) - volatile conditions"

        if atr_pct and atr_pct > 0.03:
            return "Scalp/Day Trade - high volatility"

        if hurst > 0.7:
            return "Swing (days to weeks) - strong trend"
        elif hurst > 0.6:
            return "Day Trade to Swing - moderate trend"
        elif hurst > 0.5:
            return "Day Trade - low directional bias"
        else:
            return "Scalp/Mean Reversion - quick exits expected"


# Singleton instance
_narrative_engine: Optional[NarrativeEngine] = None


def get_narrative_engine() -> NarrativeEngine:
    """Get or create global narrative engine instance"""
    global _narrative_engine
    if _narrative_engine is None:
        _narrative_engine = NarrativeEngine()
    return _narrative_engine


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test the narrative engine
    engine = NarrativeEngine()

    narrative = engine.generate_narrative(
        signal_type="STRONG_BUY",
        confidence=0.85,
        conviction=0.78,
        asset="BTC/USDT",
        price=95000,
        entropy=2.3,
        hurst=0.68,
        viral_k=1.35,
        cvd=250,
        phase="recovery",
        bio_check=True,
        physics_check=True,
        micro_check=True,
        cvd_check=True,
        stop_loss=92000,
        take_profit=102000
    )

    print(narrative.format_full_analysis())
