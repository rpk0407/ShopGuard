"""
Fundamental Analysis Agent
==========================
Analyzes fundamental factors and on-chain metrics for assets.

For Crypto:
- Market cap analysis
- Volume analysis
- Network activity (simplified)
- Supply dynamics

For Stocks:
- Market cap & sector analysis
- Earnings context
- Industry trends
"""
import requests
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from .base_agent import BaseAgent, AgentOpinion, Action, Confidence


@dataclass
class FundamentalData:
    """Fundamental metrics for an asset"""
    market_cap: float
    market_cap_rank: int
    volume_24h: float
    volume_to_mcap: float  # Healthy if > 0.05
    circulating_supply: float
    total_supply: float
    supply_ratio: float  # % of total in circulation
    ath: float
    ath_change_pct: float
    atl: float
    price_change_24h: float
    price_change_7d: float
    price_change_30d: float


class FundamentalAgent(BaseAgent):
    """
    Fundamental Analysis Agent
    Analyzes underlying value and metrics
    """

    def __init__(self):
        super().__init__(
            name="Fundamental Analysis Agent",
            specialty="Market fundamentals, valuation metrics, and supply/demand dynamics"
        )

        # Market cap tiers
        self.mcap_tiers = {
            'mega': 100_000_000_000,   # $100B+
            'large': 10_000_000_000,    # $10B+
            'mid': 1_000_000_000,       # $1B+
            'small': 100_000_000,       # $100M+
            'micro': 0
        }

        # Sector info
        self.sector_info = {
            'BTC': {
                'sector': 'Digital Gold / Store of Value',
                'competitors': ['ETH', 'Gold'],
                'key_metrics': ['hash_rate', 'active_addresses', 'halving_cycle']
            },
            'ETH': {
                'sector': 'Smart Contract Platform / DeFi',
                'competitors': ['SOL', 'AVAX', 'ADA'],
                'key_metrics': ['gas_fees', 'tvl', 'staking_ratio']
            },
            'SPY': {
                'sector': 'S&P 500 Index ETF',
                'tracks': 'Top 500 US companies',
                'key_metrics': ['earnings_growth', 'pe_ratio', 'dividend_yield']
            },
            'QQQ': {
                'sector': 'NASDAQ 100 Tech ETF',
                'tracks': 'Top 100 tech-heavy companies',
                'key_metrics': ['tech_earnings', 'growth_rates', 'innovation']
            },
            'NVDA': {
                'sector': 'Semiconductors / AI',
                'industry': 'GPU and AI chips',
                'key_metrics': ['data_center_revenue', 'ai_adoption', 'earnings_growth']
            }
        }

    def fetch_crypto_fundamentals(self, asset: str) -> Dict[str, Any]:
        """Fetch fundamental data for crypto assets"""
        coin_ids = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum'
        }

        coin_id = coin_ids.get(asset)
        if not coin_id:
            return {}

        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                market_data = data.get('market_data', {})

                return {
                    'market_cap': market_data.get('market_cap', {}).get('usd', 0),
                    'market_cap_rank': data.get('market_cap_rank', 0),
                    'volume_24h': market_data.get('total_volume', {}).get('usd', 0),
                    'circulating_supply': market_data.get('circulating_supply', 0),
                    'total_supply': market_data.get('total_supply', 0),
                    'ath': market_data.get('ath', {}).get('usd', 0),
                    'ath_change_percentage': market_data.get('ath_change_percentage', {}).get('usd', 0),
                    'atl': market_data.get('atl', {}).get('usd', 0),
                    'price_change_24h': market_data.get('price_change_percentage_24h', 0),
                    'price_change_7d': market_data.get('price_change_percentage_7d', 0),
                    'price_change_30d': market_data.get('price_change_percentage_30d', 0),
                    'sentiment_up': data.get('sentiment_votes_up_percentage', 50),
                    'sentiment_down': data.get('sentiment_votes_down_percentage', 50),
                    'developer_score': data.get('developer_score', 0),
                    'community_score': data.get('community_score', 0)
                }
        except:
            pass

        return {}

    def analyze_volume(self, volume: float, market_cap: float) -> Tuple[str, str]:
        """Analyze volume relative to market cap"""
        if market_cap == 0:
            return "unknown", "Unable to calculate volume ratio"

        ratio = volume / market_cap

        if ratio > 0.3:
            return "very_high", f"Very high volume ({ratio:.1%} of market cap) - Extreme interest/activity"
        elif ratio > 0.15:
            return "high", f"High volume ({ratio:.1%} of market cap) - Strong trading interest"
        elif ratio > 0.05:
            return "healthy", f"Healthy volume ({ratio:.1%} of market cap) - Normal market activity"
        elif ratio > 0.02:
            return "low", f"Low volume ({ratio:.1%} of market cap) - Limited trading interest"
        else:
            return "very_low", f"Very low volume ({ratio:.1%} of market cap) - Illiquid, caution advised"

    def analyze_supply(self, circulating: float, total: float) -> Tuple[str, str]:
        """Analyze supply dynamics"""
        if total == 0 or circulating == 0:
            return "unknown", "Supply data unavailable"

        ratio = circulating / total

        if ratio > 0.9:
            return "fully_diluted", f"{ratio:.0%} of supply in circulation - Limited future dilution"
        elif ratio > 0.7:
            return "mostly_circulating", f"{ratio:.0%} of supply circulating - Moderate future unlocks"
        elif ratio > 0.5:
            return "moderate", f"{ratio:.0%} circulating - Significant supply yet to enter market"
        else:
            return "low_circulation", f"Only {ratio:.0%} circulating - Heavy future dilution risk"

    def analyze_price_position(self, current: float, ath: float, atl: float) -> Tuple[str, str]:
        """Analyze current price relative to ATH/ATL"""
        if ath == 0:
            return "unknown", "ATH data unavailable"

        from_ath = ((current - ath) / ath) * 100 if ath > 0 else 0
        from_atl = ((current - atl) / atl) * 100 if atl > 0 else 0

        if from_ath > -10:
            return "near_ath", f"Only {abs(from_ath):.0f}% from ATH - Consider taking profits"
        elif from_ath > -30:
            return "strong", f"{abs(from_ath):.0f}% from ATH - In strong territory"
        elif from_ath > -50:
            return "mid_range", f"{abs(from_ath):.0f}% from ATH - Middle of historical range"
        elif from_ath > -70:
            return "discounted", f"{abs(from_ath):.0f}% from ATH - Significantly discounted"
        else:
            return "deep_discount", f"{abs(from_ath):.0f}% from ATH - Deep discount (caution: may be for good reason)"

    def get_market_cap_tier(self, market_cap: float) -> str:
        """Categorize by market cap"""
        for tier, threshold in self.mcap_tiers.items():
            if market_cap >= threshold:
                return tier
        return 'micro'

    def analyze(self, asset: str, data: Dict[str, Any]) -> AgentOpinion:
        """Perform fundamental analysis"""

        current_price = data.get('price', 0)

        # Fetch fundamental data
        if asset in ['BTC', 'ETH']:
            fundamentals = self.fetch_crypto_fundamentals(asset)
        else:
            # For stocks, use basic data from input
            fundamentals = {
                'market_cap': data.get('market_cap', 0),
                'volume_24h': data.get('volume', 0),
                'price_change_24h': data.get('change_24h', 0)
            }

        # If no fundamentals available, provide limited analysis
        if not fundamentals or fundamentals.get('market_cap', 0) == 0:
            return self._limited_analysis(asset, data)

        # Analyze components
        market_cap = fundamentals.get('market_cap', 0)
        volume = fundamentals.get('volume_24h', 0)
        circulating = fundamentals.get('circulating_supply', 0)
        total = fundamentals.get('total_supply', circulating)
        ath = fundamentals.get('ath', current_price)
        atl = fundamentals.get('atl', current_price * 0.1)

        volume_status, volume_analysis = self.analyze_volume(volume, market_cap)
        supply_status, supply_analysis = self.analyze_supply(circulating, total)
        price_status, price_analysis = self.analyze_price_position(current_price, ath, atl)
        mcap_tier = self.get_market_cap_tier(market_cap)

        # Get sector info
        sector_data = self.sector_info.get(asset, {})

        # Price changes
        change_24h = fundamentals.get('price_change_24h', 0)
        change_7d = fundamentals.get('price_change_7d', 0)
        change_30d = fundamentals.get('price_change_30d', 0)

        # Generate recommendation
        action, confidence = self._generate_recommendation(
            volume_status, supply_status, price_status, mcap_tier,
            change_24h, change_7d, change_30d
        )

        # Key factors
        key_factors = [
            f"Market Cap: ${market_cap:,.0f} ({mcap_tier.upper()} cap)",
            volume_analysis,
            supply_analysis,
            price_analysis,
            f"Sector: {sector_data.get('sector', 'Unknown')}"
        ]

        if change_24h:
            key_factors.append(f"Price change: 24h: {change_24h:+.1f}%, 7d: {change_7d:+.1f}%, 30d: {change_30d:+.1f}%")

        # Build reasoning
        reasoning = self._build_reasoning(
            asset, mcap_tier, volume_status, supply_status, price_status,
            change_24h, change_7d, sector_data
        )

        # Warnings
        warnings = []
        if volume_status in ['low', 'very_low']:
            warnings.append("Low liquidity - may have difficulty exiting large positions")
        if supply_status == 'low_circulation':
            warnings.append("High future dilution risk from unlocking tokens")
        if price_status == 'near_ath':
            warnings.append("Near all-time highs - elevated risk of pullback")
        if price_status == 'deep_discount':
            warnings.append("Deep discount may indicate fundamental issues - research carefully")
        if mcap_tier == 'micro':
            warnings.append("Micro-cap asset - extremely high risk")

        # Hold time based on fundamentals
        if mcap_tier in ['mega', 'large']:
            hold_time = "1-7 days (large cap, can hold longer)"
        elif mcap_tier == 'mid':
            hold_time = "12-48 hours (mid cap)"
        else:
            hold_time = "4-12 hours (smaller cap, higher volatility)"

        # Entry timing
        if action in [Action.BUY, Action.STRONG_BUY]:
            if price_status in ['discounted', 'deep_discount']:
                entry_timing = "Fundamentally undervalued - can accumulate"
            else:
                entry_timing = "Fundamentals supportive - enter on technical confirmation"
        elif action == Action.HOLD:
            entry_timing = "Wait for better fundamental setup"
        else:
            entry_timing = "Fundamentals suggest caution - reduce exposure"

        return AgentOpinion(
            agent_name=self.name,
            asset=asset,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            suggested_hold_time=hold_time,
            entry_timing=entry_timing,
            entry_price=current_price,
            indicators={
                "market_cap": market_cap,
                "market_cap_tier": mcap_tier,
                "volume_24h": volume,
                "volume_status": volume_status,
                "supply_ratio": circulating / total if total > 0 else 1,
                "supply_status": supply_status,
                "ath": ath,
                "ath_change_pct": ((current_price - ath) / ath * 100) if ath > 0 else 0,
                "price_status": price_status,
                "change_24h": change_24h,
                "change_7d": change_7d,
                "change_30d": change_30d,
                "sector": sector_data.get('sector', 'Unknown')
            },
            warnings=warnings
        )

    def _limited_analysis(self, asset: str, data: Dict[str, Any]) -> AgentOpinion:
        """Provide limited analysis when fundamental data unavailable"""
        sector_data = self.sector_info.get(asset, {})

        return AgentOpinion(
            agent_name=self.name,
            asset=asset,
            action=Action.HOLD,
            confidence=Confidence.LOW,
            reasoning=f"Limited fundamental data available for {asset}. Using sector context only.",
            key_factors=[
                f"Sector: {sector_data.get('sector', 'Unknown')}",
                "Detailed fundamental data unavailable",
                "Rely on technical and sentiment analysis"
            ],
            suggested_hold_time="Defer to technical analysis",
            entry_timing="Wait for more data",
            indicators={"sector": sector_data.get('sector', 'Unknown')},
            warnings=["Fundamental analysis limited - use caution"]
        )

    def _generate_recommendation(self, volume: str, supply: str, price: str,
                                   mcap: str, c24h: float, c7d: float, c30d: float) -> Tuple[Action, Confidence]:
        """Generate recommendation from fundamentals"""

        score = 0

        # Volume analysis
        if volume in ['high', 'very_high']:
            score += 0.2
        elif volume in ['low', 'very_low']:
            score -= 0.1

        # Supply analysis
        if supply == 'fully_diluted':
            score += 0.15
        elif supply == 'low_circulation':
            score -= 0.2

        # Price position
        if price in ['discounted', 'deep_discount']:
            score += 0.25
        elif price == 'near_ath':
            score -= 0.15

        # Momentum (price changes)
        if c30d > 20 and c7d > 5:
            score += 0.2  # Strong momentum
        elif c30d < -20 and c7d < -5:
            score -= 0.2  # Weak momentum
        elif c30d > 0 and c7d > 0:
            score += 0.1

        # Market cap safety
        if mcap in ['mega', 'large']:
            confidence_base = Confidence.MEDIUM
        else:
            confidence_base = Confidence.LOW

        if score > 0.35:
            return Action.STRONG_BUY, Confidence.HIGH
        elif score > 0.15:
            return Action.BUY, confidence_base
        elif score < -0.35:
            return Action.STRONG_SELL, Confidence.HIGH
        elif score < -0.15:
            return Action.SELL, confidence_base
        else:
            return Action.HOLD, Confidence.LOW

    def _build_reasoning(self, asset: str, mcap: str, volume: str, supply: str,
                         price: str, c24h: float, c7d: float, sector: Dict) -> str:
        """Build fundamental reasoning"""

        reasoning = f"{asset} is a {mcap}-cap asset in the {sector.get('sector', 'Unknown')} sector. "

        if volume in ['high', 'very_high']:
            reasoning += "Trading volume is strong, indicating healthy market interest. "
        elif volume in ['low', 'very_low']:
            reasoning += "Trading volume is concerning low, which may affect liquidity. "

        if supply == 'fully_diluted':
            reasoning += "Most of the supply is already circulating, limiting dilution risk. "
        elif supply == 'low_circulation':
            reasoning += "Significant supply is yet to unlock, creating dilution risk. "

        if price == 'discounted':
            reasoning += "Currently trading at a discount to historical highs, offering value opportunity. "
        elif price == 'near_ath':
            reasoning += "Trading near all-time highs suggests limited upside and higher risk. "

        if c7d > 10:
            reasoning += f"Strong recent momentum (+{c7d:.1f}% this week). "
        elif c7d < -10:
            reasoning += f"Weak recent performance ({c7d:.1f}% this week). "

        return reasoning

    def get_teaching_content(self) -> Dict[str, Any]:
        """Educational content about fundamental analysis"""
        return {
            "name": self.name,
            "specialty": self.specialty,
            "lessons": [
                {
                    "title": "Market Cap and Why It Matters",
                    "content": """
Market Cap = Price × Circulating Supply

It represents the total value of all coins/shares in circulation.

MARKET CAP TIERS:
• Mega Cap ($100B+): BTC, ETH, Apple, Microsoft
  - Most stable, lower risk, lower reward
  - Suitable for larger positions

• Large Cap ($10B-$100B): Major altcoins, blue chips
  - Relatively stable with growth potential
  - Good balance of risk/reward

• Mid Cap ($1B-$10B): Emerging projects
  - Higher volatility, higher potential
  - Moderate position sizes

• Small Cap ($100M-$1B): Newer projects
  - Very volatile, speculative
  - Small positions only

• Micro Cap (<$100M): High risk
  - Extreme volatility, illiquid
  - Only money you can afford to lose

WHY IT MATTERS:
A $1M buy in a $100B asset = 0.001% impact
A $1M buy in a $100M asset = 1% impact!
Smaller caps move faster but are riskier.
"""
                },
                {
                    "title": "Volume Analysis",
                    "content": """
Volume shows how much of an asset is being traded.

VOLUME TO MARKET CAP RATIO:
• >15%: Very high (unusual activity, potential big move)
• 5-15%: Healthy (active trading, good liquidity)
• 2-5%: Low (limited interest, harder to trade)
• <2%: Very low (illiquid, difficult to exit)

VOLUME SIGNALS:
1. Rising price + Rising volume = STRONG move (trend confirmation)
2. Rising price + Falling volume = WEAK move (potential reversal)
3. Falling price + Rising volume = DISTRIBUTION (selling pressure)
4. Falling price + Falling volume = EXHAUSTION (selling may be ending)

VOLUME SPIKES:
• Sudden volume increase often precedes price moves
• Watch for volume breakouts from normal range
• High volume at support/resistance = significant level

PRO TIP: Always check volume before entering a trade.
Low volume = harder to exit at your target price.
"""
                },
                {
                    "title": "Supply Dynamics (Crypto)",
                    "content": """
Understanding supply is crucial for crypto investing.

KEY METRICS:
• Circulating Supply: Coins currently tradeable
• Total Supply: All coins that exist
• Max Supply: Maximum coins that will ever exist

SUPPLY RATIO = Circulating / Total
• >90%: Fully diluted - limited future selling pressure
• 50-90%: Moderate - some unlocks coming
• <50%: High dilution risk - many tokens yet to enter market

TOKENOMICS FACTORS:
1. Vesting schedules (when team/investors can sell)
2. Inflation rate (new coins entering supply)
3. Burn mechanisms (coins being destroyed)
4. Staking lockups (coins removed from circulation)

BITCOIN EXAMPLE:
• Max supply: 21 million (hard cap)
• Circulating: ~19.5 million (93%)
• New supply: ~6.25 BTC per block (halves every 4 years)
• Deflationary model = bullish long-term

WARNING SIGNS:
• Large upcoming token unlocks
• Team holds >20% of supply
• High inflation with no burns
"""
                },
                {
                    "title": "Price Position Analysis",
                    "content": """
Where is the current price relative to historical range?

ATH (All-Time High):
The highest price ever reached.
• Near ATH (<10% away): Be cautious, profit-taking zone
• Moderate discount (30-50%): Often good value zone
• Deep discount (>70%): Either great opportunity or dying asset

ATL (All-Time Low):
The lowest price ever reached.
• Near ATL: Maximum fear, potential capitulation
• Could be bottom, could go lower
• Requires strong conviction to buy

PRICE CHANGE ANALYSIS:
Look at multiple timeframes:
• 24h: Short-term momentum
• 7d: Weekly trend
• 30d: Monthly trend
• 1y: Long-term trajectory

IDEAL SETUP:
• 30d change positive (long-term up)
• 7d change small (consolidation)
• 24h change negative (pullback to enter)
= Buying the dip in an uptrend!

WARNING:
"Cheap" doesn't mean "good value"
Always ask: WHY is it at this price?
"""
                },
                {
                    "title": "Sector and Narrative Analysis",
                    "content": """
Understanding what sector an asset is in and current narratives.

CRYPTO SECTORS:
• Store of Value (BTC) - Digital gold
• Smart Contracts (ETH, SOL) - DeFi, NFTs, dApps
• DeFi - Decentralized finance protocols
• Layer 2 - Scaling solutions
• AI & Data - AI-crypto intersection
• Gaming/Metaverse - Virtual worlds

STOCK SECTORS:
• Technology (NVDA, AAPL) - Growth stocks
• Finance - Banks, fintech
• Healthcare - Pharma, biotech
• Consumer - Retail, brands
• Energy - Oil, renewables

NARRATIVE INVESTING:
Markets move on narratives (stories).
Current examples:
• "AI is the future" → NVDA pumps
• "Bitcoin is digital gold" → BTC in macro uncertainty
• "DeFi replaces banks" → DeFi tokens rise

HOW TO USE:
1. Identify the current hot narrative
2. Find assets that benefit from it
3. Enter early in the narrative cycle
4. Exit when narrative becomes mainstream (priced in)

Remember: Narratives can change quickly!
"""
                }
            ]
        }
