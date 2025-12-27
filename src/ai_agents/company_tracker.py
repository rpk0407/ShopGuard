"""
Company Tracker Agent

Tracks and analyzes company fundamentals:
- Earnings and revenue trends
- Profit margins and efficiency
- Balance sheet health
- Cash flow analysis
- Valuation metrics (P/E, P/S, P/B, EV/EBITDA)
- Growth rates
- Competitive positioning
- Management quality signals
- Insider trading patterns
- Institutional ownership changes
- Sector comparison
- Economic moat assessment

Estimates how company performance could impact stock price.
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


class FinancialHealth(Enum):
    """Company financial health rating"""
    EXCELLENT = 5
    GOOD = 4
    FAIR = 3
    POOR = 2
    CRITICAL = 1


class GrowthProfile(Enum):
    """Company growth profile"""
    HYPER_GROWTH = auto()  # >50% growth
    HIGH_GROWTH = auto()   # 25-50%
    GROWTH = auto()        # 10-25%
    STABLE = auto()        # 0-10%
    DECLINING = auto()     # Negative growth


class ValuationLevel(Enum):
    """Valuation assessment"""
    EXTREMELY_UNDERVALUED = auto()
    UNDERVALUED = auto()
    FAIR_VALUE = auto()
    OVERVALUED = auto()
    EXTREMELY_OVERVALUED = auto()


class MoatStrength(Enum):
    """Economic moat strength"""
    WIDE = auto()      # Strong competitive advantages
    NARROW = auto()    # Some advantages
    NONE = auto()      # No sustainable advantage


@dataclass
class FinancialMetrics:
    """Key financial metrics for a company"""
    symbol: str
    # Valuation
    market_cap: float
    pe_ratio: float
    forward_pe: float
    ps_ratio: float
    pb_ratio: float
    ev_ebitda: float
    peg_ratio: float

    # Profitability
    gross_margin: float
    operating_margin: float
    net_margin: float
    roe: float  # Return on equity
    roa: float  # Return on assets
    roic: float  # Return on invested capital

    # Growth
    revenue_growth_yoy: float
    earnings_growth_yoy: float
    revenue_growth_5y: float

    # Balance Sheet
    debt_to_equity: float
    current_ratio: float
    quick_ratio: float
    cash_per_share: float

    # Cash Flow
    free_cash_flow: float
    fcf_yield: float
    operating_cash_flow: float

    # Dividends
    dividend_yield: float
    payout_ratio: float

    timestamp: datetime


@dataclass
class CompanyProfile:
    """Complete company analysis profile"""
    symbol: str
    name: str
    sector: str
    industry: str
    metrics: FinancialMetrics
    financial_health: FinancialHealth
    growth_profile: GrowthProfile
    valuation: ValuationLevel
    moat: MoatStrength
    insider_sentiment: str  # 'buying', 'selling', 'neutral'
    institutional_trend: str  # 'accumulating', 'distributing', 'stable'
    overall_score: float  # 0-100
    key_strengths: List[str]
    key_risks: List[str]
    price_target: float
    upside_potential: float
    last_updated: datetime


@dataclass
class EarningsEvent:
    """Upcoming or past earnings event"""
    symbol: str
    report_date: datetime
    fiscal_quarter: str
    eps_estimate: float
    eps_actual: Optional[float]
    revenue_estimate: float
    revenue_actual: Optional[float]
    surprise_pct: Optional[float]
    guidance: Optional[str]  # 'raised', 'maintained', 'lowered'


class CompanyTrackerAgent(BaseAgent):
    """
    Tracks company fundamentals and estimates market impact.

    Key capabilities:
    - Fundamental analysis
    - Earnings analysis
    - Valuation assessment
    - Growth trajectory
    - Competitive analysis
    - Price target estimation
    """

    def __init__(self):
        super().__init__(
            agent_id=generate_unique_id('company_tracker'),
            name="Company Tracker",
            description="Fundamental analysis and company tracking"
        )

        # Company profiles
        self.profiles: Dict[str, CompanyProfile] = {}

        # Earnings calendar
        self.upcoming_earnings: List[EarningsEvent] = []
        self.past_earnings: deque = deque(maxlen=500)

        # Sector data
        self.sector_metrics: Dict[str, Dict] = {}

        # Watchlists
        self.value_opportunities: Set[str] = set()
        self.growth_stocks: Set[str] = set()
        self.dividend_plays: Set[str] = set()
        self.turnaround_candidates: Set[str] = set()

        # Configuration
        self.value_pe_threshold = 15
        self.growth_threshold = 0.20  # 20% growth
        self.dividend_yield_threshold = 0.03  # 3% yield

    def analyze(self, snapshot: MarketSnapshot) -> Optional[Signal]:
        """Analyze companies and generate signals"""
        self.state = AgentState.ANALYZING
        self.last_active = datetime.now()

        signals = []

        for symbol in self.profiles:
            if symbol in snapshot.prices:
                signal = self._analyze_company(symbol, snapshot.prices[symbol])
                if signal:
                    signals.append(signal)

        # Check for earnings-based signals
        earnings_signals = self._check_earnings_opportunities()
        signals.extend(earnings_signals)

        self.state = AgentState.IDLE

        if signals:
            signals.sort(key=lambda s: s.score, reverse=True)
            return signals[0]

        return None

    def add_company(self, symbol: str, metrics: FinancialMetrics, name: str = "",
                    sector: str = "", industry: str = ""):
        """Add or update a company profile"""
        # Calculate derived metrics
        financial_health = self._assess_financial_health(metrics)
        growth_profile = self._assess_growth(metrics)
        valuation = self._assess_valuation(metrics)
        moat = self._assess_moat(metrics)

        # Calculate overall score
        overall_score = self._calculate_overall_score(
            financial_health, growth_profile, valuation, moat, metrics
        )

        # Identify strengths and risks
        strengths, risks = self._identify_strengths_risks(metrics)

        # Estimate price target
        price_target = self._estimate_price_target(metrics)

        profile = CompanyProfile(
            symbol=symbol,
            name=name or symbol,
            sector=sector,
            industry=industry,
            metrics=metrics,
            financial_health=financial_health,
            growth_profile=growth_profile,
            valuation=valuation,
            moat=moat,
            insider_sentiment='neutral',
            institutional_trend='stable',
            overall_score=overall_score,
            key_strengths=strengths,
            key_risks=risks,
            price_target=price_target,
            upside_potential=0,  # Will be calculated when price is known
            last_updated=datetime.now()
        )

        self.profiles[symbol] = profile

        # Add to appropriate watchlists
        self._update_watchlists(profile)

    def _assess_financial_health(self, m: FinancialMetrics) -> FinancialHealth:
        """Assess company's financial health"""
        score = 0

        # Liquidity
        if m.current_ratio > 2:
            score += 2
        elif m.current_ratio > 1.5:
            score += 1
        elif m.current_ratio < 1:
            score -= 2

        # Leverage
        if m.debt_to_equity < 0.5:
            score += 2
        elif m.debt_to_equity < 1:
            score += 1
        elif m.debt_to_equity > 2:
            score -= 2

        # Profitability
        if m.net_margin > 0.15:
            score += 2
        elif m.net_margin > 0.05:
            score += 1
        elif m.net_margin < 0:
            score -= 2

        # Cash flow
        if m.free_cash_flow > 0 and m.fcf_yield > 0.05:
            score += 2
        elif m.free_cash_flow > 0:
            score += 1
        elif m.free_cash_flow < 0:
            score -= 1

        # Map score to health rating
        if score >= 6:
            return FinancialHealth.EXCELLENT
        elif score >= 3:
            return FinancialHealth.GOOD
        elif score >= 0:
            return FinancialHealth.FAIR
        elif score >= -3:
            return FinancialHealth.POOR
        else:
            return FinancialHealth.CRITICAL

    def _assess_growth(self, m: FinancialMetrics) -> GrowthProfile:
        """Assess company's growth profile"""
        avg_growth = (m.revenue_growth_yoy + m.earnings_growth_yoy) / 2

        if avg_growth > 0.50:
            return GrowthProfile.HYPER_GROWTH
        elif avg_growth > 0.25:
            return GrowthProfile.HIGH_GROWTH
        elif avg_growth > 0.10:
            return GrowthProfile.GROWTH
        elif avg_growth > 0:
            return GrowthProfile.STABLE
        else:
            return GrowthProfile.DECLINING

    def _assess_valuation(self, m: FinancialMetrics) -> ValuationLevel:
        """Assess company's valuation"""
        # Composite valuation score
        score = 0

        # P/E analysis
        if m.pe_ratio > 0:  # Profitable
            if m.pe_ratio < 10:
                score += 2
            elif m.pe_ratio < 15:
                score += 1
            elif m.pe_ratio > 30:
                score -= 1
            elif m.pe_ratio > 50:
                score -= 2

        # PEG ratio (growth-adjusted)
        if m.peg_ratio > 0:
            if m.peg_ratio < 1:
                score += 2
            elif m.peg_ratio < 1.5:
                score += 1
            elif m.peg_ratio > 2:
                score -= 1
            elif m.peg_ratio > 3:
                score -= 2

        # FCF yield
        if m.fcf_yield > 0.08:
            score += 2
        elif m.fcf_yield > 0.05:
            score += 1
        elif m.fcf_yield < 0.02:
            score -= 1

        # P/S ratio
        if m.ps_ratio < 1:
            score += 1
        elif m.ps_ratio > 10:
            score -= 1

        # Map to valuation level
        if score >= 5:
            return ValuationLevel.EXTREMELY_UNDERVALUED
        elif score >= 2:
            return ValuationLevel.UNDERVALUED
        elif score >= -2:
            return ValuationLevel.FAIR_VALUE
        elif score >= -5:
            return ValuationLevel.OVERVALUED
        else:
            return ValuationLevel.EXTREMELY_OVERVALUED

    def _assess_moat(self, m: FinancialMetrics) -> MoatStrength:
        """Assess economic moat strength"""
        moat_indicators = 0

        # High margins suggest pricing power
        if m.gross_margin > 0.50:
            moat_indicators += 1
        if m.operating_margin > 0.20:
            moat_indicators += 1

        # High ROIC suggests competitive advantage
        if m.roic > 0.15:
            moat_indicators += 1
        if m.roic > 0.25:
            moat_indicators += 1

        # Consistent growth
        if m.revenue_growth_5y > 0.10:
            moat_indicators += 1

        if moat_indicators >= 4:
            return MoatStrength.WIDE
        elif moat_indicators >= 2:
            return MoatStrength.NARROW
        else:
            return MoatStrength.NONE

    def _calculate_overall_score(self, health: FinancialHealth, growth: GrowthProfile,
                                  valuation: ValuationLevel, moat: MoatStrength,
                                  metrics: FinancialMetrics) -> float:
        """Calculate overall company score (0-100)"""
        score = 50  # Start at neutral

        # Health contribution (max ±15)
        score += (health.value - 3) * 5

        # Growth contribution (max ±15)
        growth_scores = {
            GrowthProfile.HYPER_GROWTH: 15,
            GrowthProfile.HIGH_GROWTH: 10,
            GrowthProfile.GROWTH: 5,
            GrowthProfile.STABLE: 0,
            GrowthProfile.DECLINING: -10
        }
        score += growth_scores[growth]

        # Valuation contribution (max ±15)
        valuation_scores = {
            ValuationLevel.EXTREMELY_UNDERVALUED: 15,
            ValuationLevel.UNDERVALUED: 10,
            ValuationLevel.FAIR_VALUE: 0,
            ValuationLevel.OVERVALUED: -10,
            ValuationLevel.EXTREMELY_OVERVALUED: -15
        }
        score += valuation_scores[valuation]

        # Moat contribution (max +10)
        moat_scores = {
            MoatStrength.WIDE: 10,
            MoatStrength.NARROW: 5,
            MoatStrength.NONE: 0
        }
        score += moat_scores[moat]

        # Quality adjustments
        if metrics.roe > 0.20:
            score += 3
        if metrics.fcf_yield > 0.05:
            score += 2
        if metrics.debt_to_equity > 2:
            score -= 5

        return max(0, min(100, score))

    def _identify_strengths_risks(self, m: FinancialMetrics) -> Tuple[List[str], List[str]]:
        """Identify key strengths and risks"""
        strengths = []
        risks = []

        # Strengths
        if m.gross_margin > 0.50:
            strengths.append("High gross margin (pricing power)")
        if m.roe > 0.20:
            strengths.append("Strong return on equity")
        if m.revenue_growth_yoy > 0.20:
            strengths.append("Rapid revenue growth")
        if m.free_cash_flow > 0 and m.fcf_yield > 0.05:
            strengths.append("Strong free cash flow generation")
        if m.current_ratio > 2:
            strengths.append("Excellent liquidity")
        if m.debt_to_equity < 0.3:
            strengths.append("Low leverage/debt")
        if m.pe_ratio < 15 and m.pe_ratio > 0:
            strengths.append("Attractive valuation")

        # Risks
        if m.debt_to_equity > 2:
            risks.append("High debt levels")
        if m.current_ratio < 1:
            risks.append("Liquidity concerns")
        if m.net_margin < 0:
            risks.append("Unprofitable")
        if m.revenue_growth_yoy < -0.10:
            risks.append("Declining revenue")
        if m.pe_ratio > 50:
            risks.append("Very high valuation")
        if m.peg_ratio > 2:
            risks.append("Growth not justifying valuation")
        if m.free_cash_flow < 0:
            risks.append("Negative free cash flow")

        return strengths[:5], risks[:5]

    def _estimate_price_target(self, m: FinancialMetrics) -> float:
        """Estimate fair value price target"""
        # Use multiple valuation methods and average

        # Method 1: P/E based
        if m.pe_ratio > 0:
            fair_pe = 15  # Assume market average
            if m.revenue_growth_yoy > 0.20:
                fair_pe = 25
            elif m.revenue_growth_yoy > 0.10:
                fair_pe = 20
            pe_target = (fair_pe / m.pe_ratio) if m.pe_ratio > 0 else 1.0
        else:
            pe_target = 1.0

        # Method 2: FCF yield based
        if m.fcf_yield > 0:
            target_yield = 0.05  # 5% target FCF yield
            fcf_target = m.fcf_yield / target_yield
        else:
            fcf_target = 1.0

        # Method 3: PEG based
        if m.peg_ratio > 0:
            peg_target = 1.5 / m.peg_ratio  # Target PEG of 1.5
        else:
            peg_target = 1.0

        # Average the methods (as multipliers of current price)
        avg_multiplier = (pe_target + fcf_target + peg_target) / 3

        # This would need current price to calculate actual target
        return avg_multiplier  # Returns as multiplier

    def _update_watchlists(self, profile: CompanyProfile):
        """Update watchlists based on profile"""
        symbol = profile.symbol

        # Value opportunities
        if profile.valuation in [ValuationLevel.UNDERVALUED, ValuationLevel.EXTREMELY_UNDERVALUED]:
            if profile.financial_health in [FinancialHealth.GOOD, FinancialHealth.EXCELLENT]:
                self.value_opportunities.add(symbol)
        else:
            self.value_opportunities.discard(symbol)

        # Growth stocks
        if profile.growth_profile in [GrowthProfile.HIGH_GROWTH, GrowthProfile.HYPER_GROWTH]:
            self.growth_stocks.add(symbol)
        else:
            self.growth_stocks.discard(symbol)

        # Dividend plays
        if profile.metrics.dividend_yield > self.dividend_yield_threshold:
            if profile.metrics.payout_ratio < 0.8:  # Sustainable dividend
                self.dividend_plays.add(symbol)
        else:
            self.dividend_plays.discard(symbol)

        # Turnaround candidates
        if profile.financial_health == FinancialHealth.POOR:
            if profile.metrics.free_cash_flow > 0:  # Has cash flow
                self.turnaround_candidates.add(symbol)
        else:
            self.turnaround_candidates.discard(symbol)

    def _analyze_company(self, symbol: str, current_price: float) -> Optional[Signal]:
        """Analyze a company and potentially generate signal"""
        profile = self.profiles.get(symbol)
        if not profile:
            return None

        # Update upside potential
        if profile.price_target > 0:
            # price_target is a multiplier, calculate actual upside
            upside = (profile.price_target - 1) * 100  # as percentage

            profile.upside_potential = upside

            # Generate signal for significant opportunities
            if upside > 20 and profile.overall_score > 70:
                self.signals_generated += 1

                return Signal(
                    agent_id=self.agent_id,
                    symbol=symbol,
                    direction='long',
                    strength=SignalStrength.STRONG if upside > 30 else SignalStrength.MODERATE,
                    confidence=profile.overall_score / 100,
                    reasoning=f"Undervalued: {upside:.0f}% upside, score {profile.overall_score:.0f}/100",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(days=30),  # Fundamental signals last longer
                    metadata={
                        'valuation': profile.valuation.name,
                        'health': profile.financial_health.name,
                        'growth': profile.growth_profile.name,
                        'moat': profile.moat.name,
                        'strengths': profile.key_strengths,
                        'risks': profile.key_risks
                    }
                )

            elif upside < -20 and profile.overall_score < 30:
                self.signals_generated += 1

                return Signal(
                    agent_id=self.agent_id,
                    symbol=symbol,
                    direction='short',
                    strength=SignalStrength.MODERATE,
                    confidence=(100 - profile.overall_score) / 100,
                    reasoning=f"Overvalued: {-upside:.0f}% downside risk, score {profile.overall_score:.0f}/100",
                    timestamp=datetime.now(),
                    expiry=datetime.now() + timedelta(days=30),
                    metadata={
                        'valuation': profile.valuation.name,
                        'health': profile.financial_health.name,
                        'risks': profile.key_risks
                    }
                )

        return None

    def add_earnings_event(self, event: EarningsEvent):
        """Add earnings event to calendar"""
        if event.report_date > datetime.now():
            self.upcoming_earnings.append(event)
            # Sort by date
            self.upcoming_earnings.sort(key=lambda e: e.report_date)
        else:
            self.past_earnings.append(event)

    def _check_earnings_opportunities(self) -> List[Signal]:
        """Check for earnings-based trading opportunities"""
        signals = []

        for event in self.upcoming_earnings:
            # Check if earnings is imminent (within 7 days)
            days_until = (event.report_date - datetime.now()).days

            if 0 < days_until <= 7:
                profile = self.profiles.get(event.symbol)
                if not profile:
                    continue

                # Look at historical earnings performance
                past_for_symbol = [e for e in self.past_earnings if e.symbol == event.symbol]

                if len(past_for_symbol) >= 4:
                    # Calculate beat rate
                    beats = sum(1 for e in past_for_symbol if e.surprise_pct and e.surprise_pct > 0)
                    beat_rate = beats / len(past_for_symbol)

                    # Generate signal if consistently beats
                    if beat_rate >= 0.75:
                        self.signals_generated += 1
                        signals.append(Signal(
                            agent_id=self.agent_id,
                            symbol=event.symbol,
                            direction='long',
                            strength=SignalStrength.MODERATE,
                            confidence=beat_rate,
                            reasoning=f"Earnings in {days_until} days, {beat_rate*100:.0f}% beat rate",
                            timestamp=datetime.now(),
                            expiry=event.report_date,
                            metadata={
                                'event_type': 'pre_earnings',
                                'beat_rate': beat_rate,
                                'eps_estimate': event.eps_estimate
                            }
                        ))

        return signals

    def get_company_summary(self, symbol: str) -> Optional[Dict]:
        """Get company summary for display"""
        profile = self.profiles.get(symbol)
        if not profile:
            return None

        return {
            'symbol': profile.symbol,
            'name': profile.name,
            'sector': profile.sector,
            'overall_score': round(profile.overall_score, 1),
            'financial_health': profile.financial_health.name,
            'growth_profile': profile.growth_profile.name,
            'valuation': profile.valuation.name,
            'moat': profile.moat.name,
            'strengths': profile.key_strengths,
            'risks': profile.key_risks,
            'upside_potential': round(profile.upside_potential, 1),
            'key_metrics': {
                'pe_ratio': profile.metrics.pe_ratio,
                'revenue_growth': f"{profile.metrics.revenue_growth_yoy*100:.1f}%",
                'net_margin': f"{profile.metrics.net_margin*100:.1f}%",
                'roe': f"{profile.metrics.roe*100:.1f}%",
                'debt_to_equity': profile.metrics.debt_to_equity,
                'fcf_yield': f"{profile.metrics.fcf_yield*100:.1f}%"
            }
        }

    def get_watchlist_summary(self) -> Dict:
        """Get summary of all watchlists"""
        return {
            'value_opportunities': list(self.value_opportunities),
            'growth_stocks': list(self.growth_stocks),
            'dividend_plays': list(self.dividend_plays),
            'turnaround_candidates': list(self.turnaround_candidates),
            'upcoming_earnings': [
                {
                    'symbol': e.symbol,
                    'date': e.report_date.isoformat(),
                    'eps_estimate': e.eps_estimate
                }
                for e in self.upcoming_earnings[:10]
            ]
        }

    def learn(self, feedback: Dict[str, Any]):
        """Learn from fundamental-based trade outcomes"""
        outcome = feedback.get('outcome', 0)
        symbol = feedback.get('symbol')

        if outcome > 0:
            self.correct_signals += 1

        # Adjust confidence in fundamental models based on outcomes
        self.memory.record_trade(feedback, outcome)
