"""
Macroeconomic Indicators and Cross-Asset Signals

Macro factors drive long-term market trends:
- Interest rates (Fed policy)
- Inflation (CPI, PCE)
- Growth (GDP, employment)
- Global factors (currencies, commodities)

Cross-asset signals provide context that single-asset
analysis misses.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import deque


class MacroIndicatorType(Enum):
    """Types of macroeconomic indicators."""
    # Monetary Policy
    FED_FUNDS_RATE = "fed_funds_rate"
    FED_BALANCE_SHEET = "fed_balance_sheet"
    YIELD_CURVE = "yield_curve"

    # Inflation
    CPI = "cpi"
    CORE_CPI = "core_cpi"
    PCE = "pce"
    PPI = "ppi"

    # Growth
    GDP = "gdp"
    INDUSTRIAL_PRODUCTION = "industrial_production"
    RETAIL_SALES = "retail_sales"

    # Employment
    NONFARM_PAYROLLS = "nonfarm_payrolls"
    UNEMPLOYMENT_RATE = "unemployment_rate"
    JOBLESS_CLAIMS = "jobless_claims"

    # Sentiment
    CONSUMER_CONFIDENCE = "consumer_confidence"
    ISM_MANUFACTURING = "ism_manufacturing"
    ISM_SERVICES = "ism_services"

    # Housing
    HOUSING_STARTS = "housing_starts"
    EXISTING_HOME_SALES = "existing_home_sales"

    # Trade
    TRADE_BALANCE = "trade_balance"


@dataclass
class MacroDataPoint:
    """Single macroeconomic data release."""
    indicator: MacroIndicatorType
    value: float
    previous: float
    consensus: float
    timestamp: datetime
    revision: Optional[float] = None

    @property
    def surprise(self) -> float:
        """Surprise vs consensus (standardized)."""
        if self.consensus == 0:
            return 0.0
        return (self.value - self.consensus) / abs(self.consensus)

    @property
    def change(self) -> float:
        """Change from previous."""
        return self.value - self.previous

    @property
    def change_pct(self) -> float:
        """Percentage change from previous."""
        if self.previous == 0:
            return 0.0
        return (self.value - self.previous) / abs(self.previous) * 100


@dataclass
class EconomicEvent:
    """Scheduled economic event."""
    name: str
    indicator: MacroIndicatorType
    datetime: datetime
    previous: float
    consensus: Optional[float]
    importance: int  # 1-3, 3 = high
    actual: Optional[float] = None


class MacroIndicators:
    """
    Macroeconomic indicator processing.

    Tracks and analyzes macro data for:
    - Market regime identification
    - Risk-on/risk-off signals
    - Sector rotation signals
    """

    # Indicator characteristics
    INDICATOR_INFO = {
        MacroIndicatorType.FED_FUNDS_RATE: {
            'higher_is_bearish': True,
            'stocks_sensitivity': -0.5,
            'bonds_sensitivity': -0.8,
        },
        MacroIndicatorType.CPI: {
            'higher_is_bearish': True,
            'stocks_sensitivity': -0.3,
            'bonds_sensitivity': -0.6,
        },
        MacroIndicatorType.GDP: {
            'higher_is_bearish': False,
            'stocks_sensitivity': 0.4,
            'bonds_sensitivity': -0.2,
        },
        MacroIndicatorType.UNEMPLOYMENT_RATE: {
            'higher_is_bearish': True,
            'stocks_sensitivity': -0.4,
            'bonds_sensitivity': 0.3,
        },
        MacroIndicatorType.ISM_MANUFACTURING: {
            'higher_is_bearish': False,
            'stocks_sensitivity': 0.5,
            'bonds_sensitivity': -0.2,
        },
    }

    def __init__(self, history_months: int = 24):
        """Initialize macro indicators tracker."""
        self.history_months = history_months

        # Data history by indicator
        self.data: Dict[MacroIndicatorType, deque] = {}

        # Initialize deques
        for indicator in MacroIndicatorType:
            # Assume monthly data, keep 2 years
            self.data[indicator] = deque(maxlen=history_months)

    def add_data(self, data_point: MacroDataPoint):
        """Add a new macro data point."""
        self.data[data_point.indicator].append(data_point)

    def get_latest(
        self,
        indicator: MacroIndicatorType
    ) -> Optional[MacroDataPoint]:
        """Get latest reading for an indicator."""
        if self.data[indicator]:
            return self.data[indicator][-1]
        return None

    def get_trend(
        self,
        indicator: MacroIndicatorType,
        periods: int = 3
    ) -> Optional[float]:
        """
        Get trend direction for an indicator.

        Returns slope of linear regression.
        """
        data = list(self.data[indicator])
        if len(data) < periods:
            return None

        values = [d.value for d in data[-periods:]]
        x = np.arange(len(values))

        # Linear regression
        slope = np.polyfit(x, values, 1)[0]

        return slope

    def get_surprise_score(
        self,
        indicator: MacroIndicatorType,
        lookback: int = 6
    ) -> float:
        """
        Get average surprise score over recent releases.

        Persistent surprises indicate trend.
        """
        data = list(self.data[indicator])
        if not data:
            return 0.0

        recent = data[-lookback:]
        surprises = [d.surprise for d in recent]

        return np.mean(surprises)

    def get_market_impact(
        self,
        data_point: MacroDataPoint,
        asset_class: str = 'stocks'
    ) -> float:
        """
        Estimate market impact of a data release.

        Returns expected return impact.
        """
        info = self.INDICATOR_INFO.get(data_point.indicator, {})

        if asset_class == 'stocks':
            sensitivity = info.get('stocks_sensitivity', 0.2)
        else:
            sensitivity = info.get('bonds_sensitivity', 0.2)

        # Impact = sensitivity * surprise
        impact = sensitivity * data_point.surprise

        return impact

    def get_macro_regime(self) -> Dict:
        """
        Determine current macro regime.

        Regimes:
        - Growth: Expansion, low inflation
        - Inflation: Rising inflation, Fed hawkish
        - Recession: Declining growth, rising unemployment
        - Recovery: Improving data from recession lows
        """
        # Get key indicators
        gdp = self.get_latest(MacroIndicatorType.GDP)
        cpi = self.get_latest(MacroIndicatorType.CPI)
        unemployment = self.get_latest(MacroIndicatorType.UNEMPLOYMENT_RATE)
        ism = self.get_latest(MacroIndicatorType.ISM_MANUFACTURING)

        # Get trends
        gdp_trend = self.get_trend(MacroIndicatorType.GDP)
        cpi_trend = self.get_trend(MacroIndicatorType.CPI)

        # Determine regime
        regime = {
            'growth': 'neutral',
            'inflation': 'neutral',
            'employment': 'neutral',
            'overall': 'neutral',
        }

        if gdp:
            if gdp.value > 2.0 and (gdp_trend or 0) > 0:
                regime['growth'] = 'expanding'
            elif gdp.value < 0:
                regime['growth'] = 'contracting'

        if cpi:
            if cpi.value > 3.0:
                regime['inflation'] = 'high'
            elif cpi.value < 2.0:
                regime['inflation'] = 'low'

        if unemployment:
            if unemployment.value < 4.0:
                regime['employment'] = 'strong'
            elif unemployment.value > 6.0:
                regime['employment'] = 'weak'

        # Overall regime
        if regime['growth'] == 'expanding' and regime['inflation'] == 'low':
            regime['overall'] = 'goldilocks'
        elif regime['inflation'] == 'high':
            regime['overall'] = 'stagflation' if regime['growth'] == 'contracting' else 'overheating'
        elif regime['growth'] == 'contracting':
            regime['overall'] = 'recession'

        return regime

    def get_fed_expectation(self) -> Dict:
        """
        Infer Fed policy expectations from data.

        Returns hawkish/dovish score and expected rate path.
        """
        cpi = self.get_latest(MacroIndicatorType.CPI)
        unemployment = self.get_latest(MacroIndicatorType.UNEMPLOYMENT_RATE)
        gdp = self.get_latest(MacroIndicatorType.GDP)

        hawkish_score = 0.0

        # High inflation = hawkish
        if cpi and cpi.value > 2.0:
            hawkish_score += (cpi.value - 2.0) * 0.3

        # Low unemployment = hawkish
        if unemployment and unemployment.value < 4.5:
            hawkish_score += (4.5 - unemployment.value) * 0.2

        # Strong growth = hawkish
        if gdp and gdp.value > 2.0:
            hawkish_score += (gdp.value - 2.0) * 0.1

        return {
            'hawkish_score': np.clip(hawkish_score, -1, 1),
            'expected_direction': 'hike' if hawkish_score > 0.3 else ('cut' if hawkish_score < -0.3 else 'hold'),
            'confidence': min(1.0, abs(hawkish_score))
        }


class EconomicCalendar:
    """
    Economic event calendar and scheduling.

    Tracks upcoming releases and their expected impact.
    """

    def __init__(self):
        self.events: List[EconomicEvent] = []

    def add_event(self, event: EconomicEvent):
        """Add an event to the calendar."""
        self.events.append(event)
        # Keep sorted by datetime
        self.events.sort(key=lambda e: e.datetime)

    def get_upcoming_events(
        self,
        hours_ahead: float = 24.0,
        min_importance: int = 1
    ) -> List[EconomicEvent]:
        """Get events in the next N hours."""
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)

        return [
            e for e in self.events
            if now <= e.datetime <= cutoff and e.importance >= min_importance
        ]

    def get_high_impact_events(
        self,
        hours_ahead: float = 24.0
    ) -> List[EconomicEvent]:
        """Get high-impact events only."""
        return self.get_upcoming_events(hours_ahead, min_importance=3)

    def should_reduce_risk(self, hours_ahead: float = 1.0) -> bool:
        """
        Check if risk should be reduced due to upcoming events.

        Major data releases cause volatility - reduce exposure before.
        """
        high_impact = self.get_high_impact_events(hours_ahead)
        return len(high_impact) > 0

    def get_event_risk_score(self, hours_ahead: float = 24.0) -> float:
        """
        Calculate aggregate event risk score.

        Higher score = more event risk.
        """
        events = self.get_upcoming_events(hours_ahead)

        if not events:
            return 0.0

        now = datetime.now()
        total_risk = 0.0

        for event in events:
            hours_until = (event.datetime - now).total_seconds() / 3600

            # Closer events have higher risk
            time_weight = np.exp(-hours_until / 6)  # 6 hour decay

            # Importance weight
            importance_weight = event.importance / 3.0

            total_risk += time_weight * importance_weight

        return min(1.0, total_risk)


class CrossAssetSignals:
    """
    Cross-asset analysis for market signals.

    Different asset classes provide information about each other:
    - Bonds predict equity volatility
    - Commodities predict inflation
    - Currencies reflect rate differentials
    - VIX reflects fear
    """

    def __init__(self):
        # Price history for cross-asset analysis
        self.prices: Dict[str, deque] = {}

        # Standard cross-asset relationships
        self.relationships = {
            'risk_on': ['SPY', 'HYG', 'EEM', 'AUD/USD'],
            'risk_off': ['TLT', 'GLD', 'JPY/USD', 'VIX'],
            'inflation': ['TIP', 'GLD', 'USO', 'DBC'],
            'growth': ['XLI', 'XLF', 'COPPER', 'AUD/USD'],
        }

    def update_price(self, symbol: str, price: float, timestamp: datetime):
        """Update price for a symbol."""
        if symbol not in self.prices:
            self.prices[symbol] = deque(maxlen=252 * 5)  # 5 years daily

        self.prices[symbol].append({
            'price': price,
            'timestamp': timestamp
        })

    def get_returns(self, symbol: str, periods: int = 20) -> Optional[np.ndarray]:
        """Get returns for a symbol."""
        if symbol not in self.prices or len(self.prices[symbol]) < periods + 1:
            return None

        prices = [p['price'] for p in list(self.prices[symbol])[-(periods + 1):]]
        returns = np.diff(np.log(prices))

        return returns

    def get_risk_appetite(self) -> Tuple[float, float]:
        """
        Calculate risk appetite score.

        Compares risk-on vs risk-off asset performance.
        Returns (score, confidence) where score in [-1, 1].
        """
        risk_on_returns = []
        risk_off_returns = []

        for symbol in self.relationships['risk_on']:
            returns = self.get_returns(symbol, 20)
            if returns is not None:
                risk_on_returns.append(np.sum(returns))

        for symbol in self.relationships['risk_off']:
            returns = self.get_returns(symbol, 20)
            if returns is not None:
                risk_off_returns.append(np.sum(returns))

        if not risk_on_returns or not risk_off_returns:
            return 0.0, 0.0

        risk_on_avg = np.mean(risk_on_returns)
        risk_off_avg = np.mean(risk_off_returns)

        # Difference indicates risk appetite
        diff = risk_on_avg - risk_off_avg

        # Normalize
        score = np.tanh(diff * 10)  # Scale and bound

        # Confidence based on agreement
        risk_on_std = np.std(risk_on_returns) if len(risk_on_returns) > 1 else 1
        risk_off_std = np.std(risk_off_returns) if len(risk_off_returns) > 1 else 1
        confidence = 1 / (1 + risk_on_std + risk_off_std)

        return score, confidence

    def get_yield_curve_signal(self) -> Dict:
        """
        Analyze yield curve for signals.

        Inverted yield curve predicts recessions.
        """
        # Would need bond yields at different maturities
        # Using proxy: TLT/SHY ratio
        tlt_returns = self.get_returns('TLT', 60)
        shy_returns = self.get_returns('SHY', 60)

        if tlt_returns is None or shy_returns is None:
            return {'signal': 0, 'inverted': False}

        # Long bonds underperforming short = flattening/inverting
        spread_change = np.sum(tlt_returns) - np.sum(shy_returns)

        return {
            'signal': spread_change,
            'flattening': spread_change < 0,
            'steepening': spread_change > 0,
            'recession_warning': spread_change < -0.1
        }

    def get_inflation_expectation(self) -> Tuple[float, float]:
        """
        Estimate inflation expectations from markets.

        Uses TIPS, gold, and commodities.
        """
        signals = []

        for symbol in self.relationships['inflation']:
            returns = self.get_returns(symbol, 60)
            if returns is not None:
                signals.append(np.sum(returns))

        if not signals:
            return 0.0, 0.0

        avg_signal = np.mean(signals)

        # Positive returns in inflation assets = higher inflation expectations
        inflation_score = np.tanh(avg_signal * 5)
        confidence = 1 / (1 + np.std(signals)) if len(signals) > 1 else 0.5

        return inflation_score, confidence

    def get_dollar_signal(self) -> float:
        """
        Get USD strength signal.

        Strong dollar = headwind for commodities and EM.
        """
        # Would use DXY or currency pairs
        # Using inverse of risk-on currencies
        usd_strength = 0.0
        count = 0

        for symbol in ['AUD/USD', 'EUR/USD']:
            returns = self.get_returns(symbol, 20)
            if returns is not None:
                # Negative returns = USD strength
                usd_strength -= np.sum(returns)
                count += 1

        if count == 0:
            return 0.0

        return np.tanh(usd_strength / count * 10)

    def get_vix_signal(self) -> Dict:
        """
        Analyze VIX for volatility signals.

        VIX levels and changes predict equity returns.
        """
        vix_data = list(self.prices.get('VIX', []))

        if len(vix_data) < 20:
            return {'level': 'unknown', 'signal': 0}

        current_vix = vix_data[-1]['price']
        vix_20d_avg = np.mean([d['price'] for d in vix_data[-20:]])

        # VIX levels
        if current_vix < 15:
            level = 'low'
            signal = 0.2  # Bullish
        elif current_vix > 30:
            level = 'high'
            signal = -0.3  # Bearish near term
        else:
            level = 'normal'
            signal = 0

        # VIX trend
        vix_change = (current_vix - vix_20d_avg) / vix_20d_avg

        # Falling VIX = bullish
        signal -= vix_change * 2

        return {
            'level': level,
            'current': current_vix,
            'average_20d': vix_20d_avg,
            'signal': np.clip(signal, -1, 1),
            'elevated': current_vix > vix_20d_avg * 1.2
        }

    def get_sector_rotation_signal(self) -> Dict[str, float]:
        """
        Identify sector rotation trends.

        Different sectors lead in different market phases.
        """
        sector_signals = {}

        # Cyclical vs Defensive
        cyclicals = ['XLI', 'XLF', 'XLY', 'XLB']
        defensives = ['XLU', 'XLP', 'XLV', 'XLRE']

        cyc_returns = []
        def_returns = []

        for symbol in cyclicals:
            returns = self.get_returns(symbol, 20)
            if returns is not None:
                cyc_returns.append(np.sum(returns))

        for symbol in defensives:
            returns = self.get_returns(symbol, 20)
            if returns is not None:
                def_returns.append(np.sum(returns))

        if cyc_returns and def_returns:
            rotation = np.mean(cyc_returns) - np.mean(def_returns)
            sector_signals['cyclical_vs_defensive'] = np.tanh(rotation * 10)

        return sector_signals

    def get_composite_signal(self) -> Dict:
        """
        Get composite cross-asset signal.

        Combines all cross-asset indicators.
        """
        risk_appetite, risk_conf = self.get_risk_appetite()
        inflation, inflation_conf = self.get_inflation_expectation()
        vix_data = self.get_vix_signal()
        dollar = self.get_dollar_signal()

        # Weight signals
        composite = (
            0.4 * risk_appetite +
            0.2 * (-inflation) +  # High inflation = bearish for stocks
            0.2 * vix_data.get('signal', 0) +
            0.2 * (-dollar)  # Strong dollar = headwind
        )

        return {
            'composite_signal': composite,
            'risk_appetite': risk_appetite,
            'inflation_expectation': inflation,
            'vix_signal': vix_data.get('signal', 0),
            'dollar_signal': dollar,
            'interpretation': 'bullish' if composite > 0.2 else ('bearish' if composite < -0.2 else 'neutral')
        }
