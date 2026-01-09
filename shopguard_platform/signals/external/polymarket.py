"""
Polymarket Prediction Market Scanner
====================================
Extracts market-implied probabilities from Polymarket for trading signals.

Key Insight:
- Prediction markets aggregate crowd wisdom efficiently
- Crypto-related markets can signal sentiment shifts before price moves
- ETF approval odds, regulatory events, macro elections affect crypto prices

API: https://docs.polymarket.com/
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def create_retry_session(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """Create a requests session with retry logic"""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class MarketCategory(Enum):
    """Categories of prediction markets relevant to crypto trading"""
    CRYPTO = "crypto"          # Direct crypto markets (ETF approval, etc)
    MACRO = "macro"            # Fed rates, inflation, recession
    POLITICS = "politics"      # Elections, regulations
    TECH = "tech"              # Tech company events affecting sentiment


@dataclass
class PredictionMarket:
    """A single prediction market"""
    market_id: str
    question: str
    category: MarketCategory
    yes_price: float           # Probability of YES outcome (0-1)
    no_price: float            # Probability of NO outcome (0-1)
    volume_24h: float          # 24h trading volume in USD
    liquidity: float           # Total liquidity
    end_date: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def implied_probability(self) -> float:
        """Market-implied probability of YES outcome"""
        return self.yes_price

    @property
    def confidence(self) -> float:
        """Confidence based on liquidity and volume"""
        # Higher liquidity/volume = more reliable signal
        volume_score = min(self.volume_24h / 100000, 1.0)  # Cap at $100k
        liquidity_score = min(self.liquidity / 500000, 1.0)  # Cap at $500k
        return (volume_score + liquidity_score) / 2


@dataclass
class PredictionSignal:
    """Trading signal derived from prediction markets"""
    asset: str                 # Affected asset (BTC, ETH, etc)
    direction: float           # -1 (bearish) to +1 (bullish)
    confidence: float          # 0-1 confidence in signal
    source_markets: List[str]  # Market IDs that contributed
    reasoning: str             # Human-readable explanation
    timestamp: datetime = field(default_factory=datetime.now)


class PolymarketScanner:
    """
    Scans Polymarket for crypto-relevant prediction markets.

    Strategy:
    1. Track crypto-specific markets (ETF approvals, protocol upgrades)
    2. Monitor macro markets (Fed rates, recession odds)
    3. Watch political markets (crypto-friendly candidates, regulations)
    4. Convert market movements to trading signals

    Signal Generation:
    - Rising YES probability on bullish events = bullish signal
    - Rising YES probability on bearish events = bearish signal
    - Confidence weighted by market liquidity and volume
    """

    # Polymarket API endpoints
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"

    # Keywords for finding crypto-relevant markets
    CRYPTO_KEYWORDS = [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "sec", "etf",
        "gensler", "coinbase", "binance", "stablecoin", "defi"
    ]

    MACRO_KEYWORDS = [
        "fed", "interest rate", "inflation", "cpi", "recession",
        "unemployment", "gdp", "treasury", "dollar"
    ]

    BULLISH_EVENTS = [
        "approve", "approval", "pass", "win", "success", "adopt",
        "legalize", "accept", "launch", "bullish"
    ]

    BEARISH_EVENTS = [
        "reject", "ban", "crash", "fail", "default", "recession",
        "bearish", "decline", "shut down"
    ]

    def __init__(
        self,
        refresh_interval: int = 300,  # 5 minutes
        min_liquidity: float = 10000,  # Minimum $10k liquidity
        min_volume: float = 1000,      # Minimum $1k 24h volume
    ):
        self.refresh_interval = refresh_interval
        self.min_liquidity = min_liquidity
        self.min_volume = min_volume

        self.markets: Dict[str, PredictionMarket] = {}
        self.signals: List[PredictionSignal] = []
        self.last_refresh: float = 0

        # Callbacks
        self.on_signal: Optional[Callable[[PredictionSignal], None]] = None

        # Asset mapping: which assets are affected by which market categories
        self.asset_mapping = {
            MarketCategory.CRYPTO: ["BTC", "ETH", "SOL"],
            MarketCategory.MACRO: ["BTC", "ETH"],  # Macro affects major cryptos
            MarketCategory.POLITICS: ["BTC", "ETH"],
            MarketCategory.TECH: ["ETH", "SOL"],  # Tech sentiment
        }

        self._session = create_retry_session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "TITAN-Trading/1.0"
        })

    def _fetch_markets(self) -> List[dict]:
        """Fetch all active markets from Polymarket"""
        # Try multiple endpoints with fallback
        endpoints = [
            (f"{self.GAMMA_URL}/markets", {"active": "true", "closed": "false", "limit": 100}),
            (f"{self.BASE_URL}/markets", {"next_cursor": "", "limit": "100"}),
        ]

        for url, params in endpoints:
            try:
                response = self._session.get(url, params=params, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    # Handle different response formats
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get("data", data.get("markets", []))
                    return []

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout fetching from {url}")
                continue
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error for {url}: {e}")
                continue
            except Exception as e:
                logger.error(f"Failed to fetch markets from {url}: {e}")
                continue

        logger.error("All Polymarket endpoints failed")
        return []

    def _fetch_market_prices(self, token_ids: List[str]) -> Dict[str, dict]:
        """Fetch current prices for markets"""
        try:
            # CLOB API for prices
            response = self._session.get(
                f"{self.BASE_URL}/prices",
                params={"token_ids": ",".join(token_ids)},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch prices: {e}")
            return {}

    def _categorize_market(self, question: str) -> Optional[MarketCategory]:
        """Determine category of a market based on question text"""
        question_lower = question.lower()

        # Check crypto keywords first (most specific)
        if any(kw in question_lower for kw in self.CRYPTO_KEYWORDS):
            return MarketCategory.CRYPTO

        # Then macro
        if any(kw in question_lower for kw in self.MACRO_KEYWORDS):
            return MarketCategory.MACRO

        # Could add more categories here
        return None

    def _is_bullish_event(self, question: str) -> Optional[bool]:
        """Determine if YES outcome is bullish or bearish for crypto"""
        question_lower = question.lower()

        bullish_count = sum(1 for kw in self.BULLISH_EVENTS if kw in question_lower)
        bearish_count = sum(1 for kw in self.BEARISH_EVENTS if kw in question_lower)

        if bullish_count > bearish_count:
            return True
        elif bearish_count > bullish_count:
            return False
        return None  # Ambiguous

    def refresh_markets(self) -> int:
        """Refresh market data from Polymarket"""
        now = time.time()

        if now - self.last_refresh < self.refresh_interval:
            return len(self.markets)

        logger.info("Refreshing Polymarket data...")

        raw_markets = self._fetch_markets()
        new_markets = {}

        for market_data in raw_markets:
            try:
                # Skip if not a dict (API format changed)
                if not isinstance(market_data, dict):
                    continue

                question = market_data.get("question", "")
                category = self._categorize_market(question)

                # Skip irrelevant markets
                if category is None:
                    continue

                # Get outcomes (YES/NO prices)
                outcomes = market_data.get("outcomes", [])
                yes_price = 0.5
                no_price = 0.5

                for outcome in outcomes:
                    if outcome.get("outcome", "").upper() == "YES":
                        yes_price = float(outcome.get("price", 0.5))
                    elif outcome.get("outcome", "").upper() == "NO":
                        no_price = float(outcome.get("price", 0.5))

                # Get volume and liquidity
                volume_24h = float(market_data.get("volume24hr", 0))
                liquidity = float(market_data.get("liquidity", 0))

                # Filter by minimum thresholds
                if liquidity < self.min_liquidity or volume_24h < self.min_volume:
                    continue

                market_id = market_data.get("id", market_data.get("condition_id", ""))

                market = PredictionMarket(
                    market_id=market_id,
                    question=question,
                    category=category,
                    yes_price=yes_price,
                    no_price=no_price,
                    volume_24h=volume_24h,
                    liquidity=liquidity,
                    last_updated=datetime.now()
                )

                new_markets[market_id] = market

            except Exception as e:
                logger.warning(f"Failed to parse market: {e}")
                continue

        # Detect changes and generate signals
        self._detect_changes(new_markets)

        self.markets = new_markets
        self.last_refresh = now

        logger.info(f"Found {len(self.markets)} relevant prediction markets")
        return len(self.markets)

    def _detect_changes(self, new_markets: Dict[str, PredictionMarket]):
        """Detect significant probability changes and generate signals"""
        for market_id, new_market in new_markets.items():
            old_market = self.markets.get(market_id)

            if old_market is None:
                continue  # New market, no change to detect

            # Calculate probability change
            prob_change = new_market.yes_price - old_market.yes_price

            # Significant change threshold: 5% probability shift
            if abs(prob_change) < 0.05:
                continue

            # Determine direction based on event type
            is_bullish_event = self._is_bullish_event(new_market.question)

            if is_bullish_event is None:
                continue  # Can't determine direction

            # Calculate signal direction
            # If bullish event probability increases -> bullish signal
            # If bearish event probability increases -> bearish signal
            if is_bullish_event:
                direction = prob_change  # Positive change = bullish
            else:
                direction = -prob_change  # Positive change in bearish event = bearish signal

            # Normalize to [-1, 1]
            direction = max(-1, min(1, direction * 10))  # Scale up small changes

            # Generate signals for affected assets
            affected_assets = self.asset_mapping.get(new_market.category, ["BTC"])

            for asset in affected_assets:
                signal = PredictionSignal(
                    asset=asset,
                    direction=direction,
                    confidence=new_market.confidence * abs(prob_change) * 2,
                    source_markets=[market_id],
                    reasoning=f"{new_market.question} - probability {'increased' if prob_change > 0 else 'decreased'} by {abs(prob_change)*100:.1f}%"
                )

                self.signals.append(signal)

                if self.on_signal:
                    self.on_signal(signal)

                logger.info(f"Prediction signal: {asset} {'BULLISH' if direction > 0 else 'BEARISH'} ({signal.confidence:.2f}) - {new_market.question[:50]}...")

    def get_current_signal(self, asset: str) -> Optional[PredictionSignal]:
        """Get aggregated current signal for an asset"""
        self.refresh_markets()

        # Get recent signals for this asset (last hour)
        cutoff = datetime.now().timestamp() - 3600
        recent = [
            s for s in self.signals
            if s.asset == asset and s.timestamp.timestamp() > cutoff
        ]

        if not recent:
            return None

        # Weighted average of signals
        total_weight = sum(s.confidence for s in recent)
        if total_weight == 0:
            return None

        weighted_direction = sum(s.direction * s.confidence for s in recent) / total_weight
        avg_confidence = total_weight / len(recent)

        return PredictionSignal(
            asset=asset,
            direction=weighted_direction,
            confidence=avg_confidence,
            source_markets=[m for s in recent for m in s.source_markets],
            reasoning=f"Aggregated from {len(recent)} prediction market signals"
        )

    def get_market_summary(self) -> Dict[str, any]:
        """Get summary of tracked prediction markets"""
        self.refresh_markets()

        summary = {
            "total_markets": len(self.markets),
            "by_category": {},
            "total_volume_24h": 0,
            "total_liquidity": 0,
            "top_markets": []
        }

        for market in self.markets.values():
            cat = market.category.value
            if cat not in summary["by_category"]:
                summary["by_category"][cat] = 0
            summary["by_category"][cat] += 1

            summary["total_volume_24h"] += market.volume_24h
            summary["total_liquidity"] += market.liquidity

        # Top 5 by volume
        sorted_markets = sorted(
            self.markets.values(),
            key=lambda m: m.volume_24h,
            reverse=True
        )[:5]

        for m in sorted_markets:
            summary["top_markets"].append({
                "question": m.question[:80],
                "yes_price": m.yes_price,
                "volume_24h": m.volume_24h
            })

        return summary


# Demo function
async def demo_polymarket():
    """Demo the Polymarket scanner"""
    print("\n=== Polymarket Prediction Market Scanner ===\n")

    scanner = PolymarketScanner(
        min_liquidity=5000,
        min_volume=500
    )

    def on_signal(signal: PredictionSignal):
        direction = "BULLISH" if signal.direction > 0 else "BEARISH"
        print(f"  SIGNAL: {signal.asset} {direction} ({signal.confidence:.2f})")
        print(f"    Reason: {signal.reasoning}")

    scanner.on_signal = on_signal

    # Refresh markets
    count = scanner.refresh_markets()
    print(f"Found {count} crypto-relevant prediction markets\n")

    # Get summary
    summary = scanner.get_market_summary()
    print(f"Categories: {summary['by_category']}")
    print(f"Total 24h Volume: ${summary['total_volume_24h']:,.0f}")
    print(f"Total Liquidity: ${summary['total_liquidity']:,.0f}")

    print("\nTop Markets:")
    for m in summary["top_markets"]:
        print(f"  {m['question']}")
        print(f"    YES: {m['yes_price']*100:.1f}% | Volume: ${m['volume_24h']:,.0f}")

    # Get signal for BTC
    btc_signal = scanner.get_current_signal("BTC")
    if btc_signal:
        direction = "BULLISH" if btc_signal.direction > 0 else "BEARISH"
        print(f"\nBTC Signal: {direction} (confidence: {btc_signal.confidence:.2f})")
        print(f"  {btc_signal.reasoning}")
    else:
        print("\nNo significant BTC signals from prediction markets")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_polymarket())
