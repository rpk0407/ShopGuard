"""
Smart Money Tracker
===================
Tracks whale and institutional activity vs retail sentiment.

Core Principle:
    "Be fearful when others are greedy, and greedy when others are fearful."
    - Warren Buffett

The Problem with Following Retail:
- Retail panic sells at bottoms (becomes exit liquidity for whales)
- Retail FOMO buys at tops (provides liquidity for whale distributions)
- 90% of retail traders lose money - why follow them?

Smart Money Indicators:
1. Whale wallet movements (on-chain)
2. Exchange inflows/outflows (selling vs accumulating)
3. Open Interest + Funding divergence (professional positioning)
4. Large transaction analysis (whales accumulating during fear)

Data Sources:
- Whale Alert API (large transactions)
- Glassnode / CryptoQuant style metrics
- Exchange flow analysis
- Liquidation data (who's getting rekt)
"""

import logging
import time
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Tuple
import requests

logger = logging.getLogger(__name__)


class MoneyType(Enum):
    """Classification of market participant"""
    WHALE = "whale"           # >$1M transactions
    SHARK = "shark"           # $100k-$1M transactions
    DOLPHIN = "dolphin"       # $10k-$100k
    FISH = "fish"             # <$10k (retail)
    EXCHANGE = "exchange"     # Exchange cold/hot wallets
    INSTITUTION = "institution"  # Known institutional wallets


class FlowDirection(Enum):
    """Direction of capital flow"""
    ACCUMULATION = "accumulation"  # Smart money buying
    DISTRIBUTION = "distribution"   # Smart money selling
    NEUTRAL = "neutral"


@dataclass
class WhaleTransaction:
    """A large transaction detected on-chain"""
    tx_hash: str
    asset: str
    amount_usd: float
    from_type: MoneyType
    to_type: MoneyType
    direction: FlowDirection  # To exchange = selling, from exchange = accumulating
    timestamp: datetime
    blockchain: str = "ethereum"


@dataclass
class SmartMoneySignal:
    """Signal derived from smart money analysis"""
    asset: str
    direction: float           # -1 (smart money selling) to +1 (accumulating)
    confidence: float          # 0-1
    whale_flow: float          # Net whale flow (positive = accumulation)
    exchange_flow: float       # Net exchange flow (negative = accumulation)
    retail_sentiment: float    # What retail thinks (-1 to +1)
    divergence: float          # Whale vs retail divergence (high = contrarian opportunity)
    signal_type: str           # "follow_whales", "contrarian", "neutral"
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)


class SmartMoneyTracker:
    """
    Tracks smart money (whale/institutional) activity vs retail sentiment.

    Key Insight:
    When whales are accumulating while retail is panic selling = BUY signal
    When whales are distributing while retail is FOMO buying = SELL signal

    The divergence between smart money and retail is the alpha, not following either blindly.

    Signals:
    - STRONG_ACCUMULATION: Whales buying heavily, exchange outflows high
    - ACCUMULATION: Whales buying, retail fearful
    - DISTRIBUTION: Whales selling, retail greedy
    - STRONG_DISTRIBUTION: Whales dumping, exchange inflows high
    - DIVERGENCE_BUY: Retail panic selling but whales accumulating
    - DIVERGENCE_SELL: Retail FOMO but whales distributing
    """

    # Whale Alert style transaction thresholds
    WHALE_THRESHOLD = 1_000_000      # $1M+
    SHARK_THRESHOLD = 100_000        # $100k+
    SIGNIFICANT_THRESHOLD = 10_000   # Track $10k+

    # Known exchange wallets (simplified - would use full database)
    EXCHANGE_PATTERNS = [
        "binance", "coinbase", "kraken", "bitfinex", "okx", "bybit",
        "ftx", "huobi", "kucoin", "gate.io", "crypto.com"
    ]

    def __init__(
        self,
        whale_alert_api_key: Optional[str] = None,
        glassnode_api_key: Optional[str] = None,
        refresh_interval: int = 300,
    ):
        self.whale_alert_api_key = whale_alert_api_key
        self.glassnode_api_key = glassnode_api_key
        self.refresh_interval = refresh_interval

        # Data storage
        self.transactions: Dict[str, List[WhaleTransaction]] = {}  # asset -> transactions
        self.signals: Dict[str, SmartMoneySignal] = {}
        self.whale_flow_24h: Dict[str, float] = {}  # Net whale flow
        self.exchange_flow_24h: Dict[str, float] = {}  # Net exchange flow

        self.last_refresh: float = 0

        # Callbacks
        self.on_whale_alert: Optional[Callable[[WhaleTransaction], None]] = None
        self.on_signal: Optional[Callable[[SmartMoneySignal], None]] = None

        self._session = requests.Session()

    def _fetch_whale_alerts(self) -> List[dict]:
        """Fetch recent whale transactions from Whale Alert API"""
        if not self.whale_alert_api_key:
            # Return simulated data for demo
            return self._simulate_whale_data()

        try:
            response = self._session.get(
                "https://api.whale-alert.io/v1/transactions",
                params={
                    "api_key": self.whale_alert_api_key,
                    "min_value": self.SIGNIFICANT_THRESHOLD,
                    "start": int((datetime.now() - timedelta(hours=24)).timestamp()),
                    "limit": 100
                },
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            return data.get("transactions", [])
        except Exception as e:
            logger.warning(f"Whale Alert API error: {e}")
            return []

    def _simulate_whale_data(self) -> List[dict]:
        """Simulate whale data when no API key available"""
        # This would normally come from on-chain analysis
        # For demo, we return empty and rely on other signals
        return []

    def _fetch_exchange_flows(self, asset: str) -> Tuple[float, float]:
        """
        Fetch exchange inflow/outflow data.

        Returns: (inflow, outflow) in USD
        - High inflow = selling pressure (coins moving to exchanges to sell)
        - High outflow = accumulation (coins leaving exchanges to cold storage)
        """
        if not self.glassnode_api_key:
            # Without API, estimate from other signals
            return 0, 0

        try:
            # Glassnode API for exchange flows
            inflow_response = self._session.get(
                f"https://api.glassnode.com/v1/metrics/transactions/transfers_volume_to_exchanges_sum",
                params={
                    "api_key": self.glassnode_api_key,
                    "a": asset.lower(),
                    "i": "24h"
                },
                timeout=15
            )

            outflow_response = self._session.get(
                f"https://api.glassnode.com/v1/metrics/transactions/transfers_volume_from_exchanges_sum",
                params={
                    "api_key": self.glassnode_api_key,
                    "a": asset.lower(),
                    "i": "24h"
                },
                timeout=15
            )

            inflow = 0
            outflow = 0

            if inflow_response.status_code == 200:
                data = inflow_response.json()
                if data:
                    inflow = float(data[-1].get("v", 0))

            if outflow_response.status_code == 200:
                data = outflow_response.json()
                if data:
                    outflow = float(data[-1].get("v", 0))

            return inflow, outflow

        except Exception as e:
            logger.warning(f"Exchange flow API error: {e}")
            return 0, 0

    def _classify_transaction(self, tx: dict) -> Optional[WhaleTransaction]:
        """Classify a whale transaction"""
        try:
            amount_usd = float(tx.get("amount_usd", 0))
            if amount_usd < self.SIGNIFICANT_THRESHOLD:
                return None

            # Determine money type based on amount
            if amount_usd >= self.WHALE_THRESHOLD:
                money_type = MoneyType.WHALE
            elif amount_usd >= self.SHARK_THRESHOLD:
                money_type = MoneyType.SHARK
            else:
                money_type = MoneyType.DOLPHIN

            # Check if from/to is an exchange
            from_owner = tx.get("from", {}).get("owner", "").lower()
            to_owner = tx.get("to", {}).get("owner", "").lower()

            from_is_exchange = any(ex in from_owner for ex in self.EXCHANGE_PATTERNS)
            to_is_exchange = any(ex in to_owner for ex in self.EXCHANGE_PATTERNS)

            # Determine direction
            if to_is_exchange and not from_is_exchange:
                # Moving TO exchange = preparing to sell = distribution
                direction = FlowDirection.DISTRIBUTION
                from_type = money_type
                to_type = MoneyType.EXCHANGE
            elif from_is_exchange and not to_is_exchange:
                # Moving FROM exchange = accumulating = bullish
                direction = FlowDirection.ACCUMULATION
                from_type = MoneyType.EXCHANGE
                to_type = money_type
            else:
                # Wallet to wallet transfer
                direction = FlowDirection.NEUTRAL
                from_type = money_type
                to_type = money_type

            return WhaleTransaction(
                tx_hash=tx.get("hash", ""),
                asset=tx.get("symbol", "BTC").upper(),
                amount_usd=amount_usd,
                from_type=from_type,
                to_type=to_type,
                direction=direction,
                timestamp=datetime.fromtimestamp(tx.get("timestamp", time.time())),
                blockchain=tx.get("blockchain", "bitcoin")
            )

        except Exception as e:
            logger.debug(f"Failed to classify transaction: {e}")
            return None

    def refresh_data(self, assets: List[str]) -> Dict[str, int]:
        """Refresh whale and exchange flow data"""
        now = time.time()

        if now - self.last_refresh < self.refresh_interval:
            return {a: len(self.transactions.get(a, [])) for a in assets}

        logger.info("Refreshing smart money data...")

        # Fetch whale transactions
        raw_txs = self._fetch_whale_alerts()
        new_txs_count = {}

        for asset in assets:
            if asset not in self.transactions:
                self.transactions[asset] = []

            # Filter and classify transactions for this asset
            asset_txs = []
            for raw_tx in raw_txs:
                if raw_tx.get("symbol", "").upper() == asset:
                    tx = self._classify_transaction(raw_tx)
                    if tx:
                        asset_txs.append(tx)
                        if self.on_whale_alert and tx.amount_usd >= self.WHALE_THRESHOLD:
                            self.on_whale_alert(tx)

            self.transactions[asset] = asset_txs
            new_txs_count[asset] = len(asset_txs)

            # Fetch exchange flows
            inflow, outflow = self._fetch_exchange_flows(asset)
            self.exchange_flow_24h[asset] = outflow - inflow  # Positive = accumulation

            # Calculate whale flow
            whale_accumulation = sum(
                tx.amount_usd for tx in asset_txs
                if tx.direction == FlowDirection.ACCUMULATION
            )
            whale_distribution = sum(
                tx.amount_usd for tx in asset_txs
                if tx.direction == FlowDirection.DISTRIBUTION
            )
            self.whale_flow_24h[asset] = whale_accumulation - whale_distribution

            # Generate signal
            self._generate_signal(asset)

        self.last_refresh = now
        return new_txs_count

    def _generate_signal(
        self,
        asset: str,
        retail_sentiment: float = 0
    ):
        """Generate smart money signal for an asset"""
        whale_flow = self.whale_flow_24h.get(asset, 0)
        exchange_flow = self.exchange_flow_24h.get(asset, 0)

        # Normalize flows to -1 to 1 range
        # These thresholds would be calibrated from historical data
        whale_signal = max(-1, min(1, whale_flow / 10_000_000))  # $10M as max
        exchange_signal = max(-1, min(1, exchange_flow / 50_000_000))  # $50M as max

        # Combined smart money direction
        # Exchange flow is weighted higher as it's more reliable
        smart_money_direction = (whale_signal * 0.4 + exchange_signal * 0.6)

        # Calculate divergence between smart money and retail
        # High divergence = contrarian opportunity
        divergence = abs(smart_money_direction - retail_sentiment)

        # Determine signal type
        if divergence > 0.5:
            # Strong divergence - contrarian signal
            if smart_money_direction > 0 and retail_sentiment < -0.3:
                signal_type = "contrarian_buy"
                direction = smart_money_direction  # Follow whales, not retail
                reasoning = "Whales accumulating while retail panic selling - BUY opportunity"
            elif smart_money_direction < 0 and retail_sentiment > 0.3:
                signal_type = "contrarian_sell"
                direction = smart_money_direction  # Follow whales, not retail
                reasoning = "Whales distributing while retail FOMO - Exit/SHORT opportunity"
            else:
                signal_type = "follow_whales"
                direction = smart_money_direction
                reasoning = f"Following smart money flow"
        else:
            # Low divergence - follow smart money if clear direction
            if abs(smart_money_direction) > 0.3:
                signal_type = "follow_whales"
                direction = smart_money_direction
                reasoning = "Smart money and retail aligned"
            else:
                signal_type = "neutral"
                direction = 0
                reasoning = "No clear smart money direction"

        # Confidence based on volume and clarity
        confidence = min(1.0, abs(smart_money_direction) + divergence * 0.5)

        signal = SmartMoneySignal(
            asset=asset,
            direction=direction,
            confidence=confidence,
            whale_flow=whale_flow,
            exchange_flow=exchange_flow,
            retail_sentiment=retail_sentiment,
            divergence=divergence,
            signal_type=signal_type,
            reasoning=reasoning
        )

        self.signals[asset] = signal

        if self.on_signal and abs(direction) > 0.2:
            self.on_signal(signal)

    def get_signal(self, asset: str, retail_sentiment: float = 0) -> Optional[SmartMoneySignal]:
        """
        Get smart money signal for an asset.

        Args:
            asset: The asset symbol
            retail_sentiment: Current retail sentiment (-1 to 1) from social/news

        Returns:
            SmartMoneySignal with direction, confidence, and reasoning
        """
        self.refresh_data([asset])

        # Regenerate signal with updated retail sentiment
        self._generate_signal(asset, retail_sentiment)

        return self.signals.get(asset)

    def get_whale_retail_divergence(self, asset: str, retail_sentiment: float) -> Dict:
        """
        Analyze the divergence between whale activity and retail sentiment.

        High divergence = potential contrarian opportunity
        """
        signal = self.get_signal(asset, retail_sentiment)

        if not signal:
            return {
                "divergence": 0,
                "recommendation": "NEUTRAL",
                "reasoning": "Insufficient data"
            }

        if signal.divergence > 0.6:
            if signal.direction > 0:
                recommendation = "STRONG_CONTRARIAN_BUY"
                reasoning = "Extreme divergence: Whales heavily accumulating while retail panics"
            else:
                recommendation = "STRONG_CONTRARIAN_SELL"
                reasoning = "Extreme divergence: Whales heavily distributing while retail FOMOs"
        elif signal.divergence > 0.3:
            if signal.direction > 0:
                recommendation = "CONTRARIAN_BUY"
                reasoning = "Divergence detected: Smart money accumulating"
            else:
                recommendation = "CONTRARIAN_SELL"
                reasoning = "Divergence detected: Smart money distributing"
        else:
            recommendation = "FOLLOW_TREND" if abs(signal.direction) > 0.3 else "NEUTRAL"
            reasoning = "No significant whale-retail divergence"

        return {
            "divergence": signal.divergence,
            "whale_direction": signal.direction,
            "retail_sentiment": retail_sentiment,
            "recommendation": recommendation,
            "reasoning": reasoning,
            "whale_flow_24h": signal.whale_flow,
            "exchange_flow_24h": signal.exchange_flow
        }


# Demo function
async def demo_smart_money():
    """Demo the smart money tracker"""
    print("\n=== Smart Money Tracker Demo ===\n")
    print("Core Principle: Follow the whales, not the sheep.\n")

    tracker = SmartMoneyTracker()

    def on_whale(tx: WhaleTransaction):
        direction = "📈 ACCUMULATING" if tx.direction == FlowDirection.ACCUMULATION else "📉 DISTRIBUTING"
        print(f"  🐋 WHALE ALERT: ${tx.amount_usd:,.0f} {tx.asset} {direction}")

    def on_signal(signal: SmartMoneySignal):
        print(f"\n  SMART MONEY SIGNAL: {signal.asset}")
        print(f"    Type: {signal.signal_type}")
        print(f"    Direction: {signal.direction:.2f}")
        print(f"    Whale Flow: ${signal.whale_flow:,.0f}")
        print(f"    Divergence: {signal.divergence:.2f}")
        print(f"    Reasoning: {signal.reasoning}")

    tracker.on_whale_alert = on_whale
    tracker.on_signal = on_signal

    # Simulate scenario: Retail is panic selling but whales are accumulating
    print("Scenario: Market dump, retail panicking...")
    print("         But what are the whales doing?\n")

    assets = ["BTC", "ETH"]
    tracker.refresh_data(assets)

    for asset in assets:
        # Simulate retail panic (-0.8 = very bearish sentiment)
        divergence = tracker.get_whale_retail_divergence(asset, retail_sentiment=-0.7)

        print(f"\n{asset} Analysis:")
        print(f"  Retail Sentiment: {divergence['retail_sentiment']:.2f} (PANIC)")
        print(f"  Whale Direction: {divergence['whale_direction']:.2f}")
        print(f"  Divergence: {divergence['divergence']:.2f}")
        print(f"  Recommendation: {divergence['recommendation']}")
        print(f"  Reasoning: {divergence['reasoning']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_smart_money())
