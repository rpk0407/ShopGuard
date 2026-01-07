"""
Funding Rate Scanner
====================
Monitor funding rates across exchanges for arbitrage opportunities.

Funding rate arbitrage is a market-neutral strategy:
- When funding is POSITIVE: Longs pay shorts
  -> Short perp, hold spot/stablecoin as hedge
  -> Collect funding every 8 hours

- When funding is NEGATIVE: Shorts pay longs
  -> Long perp, short spot (if possible)
  -> Collect funding every 8 hours

Expected Returns (2025 data):
- Average: 19.26% annually
- Best case: 115.9% over 6 months (extreme funding)
- Worst case: -1.92% (minimal loss)
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .client import HyperliquidClient

logger = logging.getLogger(__name__)


class FundingSignal(Enum):
    NONE = "none"
    COLLECT_LONG = "collect_long"  # Go long perp to collect funding
    COLLECT_SHORT = "collect_short"  # Go short perp to collect funding
    CLOSE = "close"  # Close position, funding turned against us


@dataclass
class FundingOpportunity:
    """Funding rate arbitrage opportunity"""
    asset: str
    funding_rate: float  # Per 8 hours
    funding_rate_annual: float  # Annualized
    signal: FundingSignal
    price: float
    next_funding_time: int  # Unix timestamp
    timestamp: float = field(default_factory=time.time)

    @property
    def hours_to_funding(self) -> float:
        """Hours until next funding"""
        return max(0, (self.next_funding_time - time.time()) / 3600)


@dataclass
class FundingPosition:
    """Active funding arbitrage position"""
    asset: str
    side: str  # "LONG" or "SHORT"
    size: float
    entry_price: float
    entry_funding_rate: float
    total_funding_collected: float = 0.0
    funding_payments: int = 0
    entry_time: float = field(default_factory=time.time)


@dataclass
class FundingConfig:
    """Funding scanner configuration"""
    # Thresholds
    min_funding_rate: float = 0.0005  # 0.05% per 8h (18.25% annual)
    max_funding_rate: float = 0.01  # 1% per 8h (extreme, might reverse)

    # Position sizing
    position_size_usd: float = 5000
    max_positions: int = 3

    # Assets to monitor
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH", "SOL"])

    # Scan interval (seconds)
    scan_interval: int = 60


class FundingScanner:
    """
    Funding Rate Scanner

    Monitors funding rates and identifies arbitrage opportunities.
    Can work standalone or integrated with the main broker.

    Usage:
        scanner = FundingScanner(client, config)

        # Set callback for opportunities
        scanner.on_opportunity = lambda opp: print(f"Found: {opp.asset} {opp.signal}")

        # Start scanning
        await scanner.start()

        # Get current opportunities
        opportunities = scanner.get_opportunities()
    """

    # Funding times (UTC)
    FUNDING_TIMES = [0, 8, 16]  # 00:00, 08:00, 16:00 UTC

    def __init__(
        self,
        client: HyperliquidClient,
        config: FundingConfig = None
    ):
        self.client = client
        self.config = config or FundingConfig()

        self._running = False
        self._scan_task: Optional[asyncio.Task] = None

        # State
        self.opportunities: Dict[str, FundingOpportunity] = {}
        self.positions: Dict[str, FundingPosition] = {}
        self.funding_history: List[Dict] = []

        # Callbacks
        self.on_opportunity: Optional[Callable[[FundingOpportunity], None]] = None
        self.on_funding_payment: Optional[Callable[[str, float], None]] = None

        logger.info("FundingScanner initialized")

    def _get_next_funding_time(self) -> int:
        """Get timestamp of next funding payment"""
        now = time.time()
        current_hour = time.gmtime(now).tm_hour

        # Find next funding hour
        next_funding_hour = None
        for hour in self.FUNDING_TIMES:
            if hour > current_hour:
                next_funding_hour = hour
                break

        if next_funding_hour is None:
            # Next funding is tomorrow at 00:00
            next_funding_hour = 0
            # Add one day
            tomorrow = now + 86400
            midnight = tomorrow - (tomorrow % 86400)
            return int(midnight)

        # Calculate today's funding time
        today_start = now - (now % 86400)
        return int(today_start + next_funding_hour * 3600)

    def _annualize_rate(self, rate_8h: float) -> float:
        """Convert 8-hour funding rate to annual rate"""
        # 3 funding payments per day * 365 days
        return rate_8h * 3 * 365

    async def scan(self) -> List[FundingOpportunity]:
        """Scan for funding opportunities"""
        opportunities = []

        # Get all funding rates
        rates = self.client.get_all_funding_rates()
        prices = self.client.get_all_mids()
        next_funding = self._get_next_funding_time()

        for asset in self.config.assets:
            rate = rates.get(asset, 0)
            price = prices.get(asset, 0)

            if price == 0:
                continue

            abs_rate = abs(rate)
            annual_rate = self._annualize_rate(abs_rate)

            # Determine signal
            signal = FundingSignal.NONE

            if abs_rate >= self.config.min_funding_rate:
                if abs_rate <= self.config.max_funding_rate:
                    if rate > 0:
                        # Positive funding: longs pay shorts
                        # -> Go SHORT to collect
                        signal = FundingSignal.COLLECT_SHORT
                    else:
                        # Negative funding: shorts pay longs
                        # -> Go LONG to collect
                        signal = FundingSignal.COLLECT_LONG
                else:
                    # Extreme funding, might reverse
                    logger.warning(f"{asset} funding {rate*100:.3f}% is extreme")

            opp = FundingOpportunity(
                asset=asset,
                funding_rate=rate,
                funding_rate_annual=annual_rate,
                signal=signal,
                price=price,
                next_funding_time=next_funding
            )

            opportunities.append(opp)
            self.opportunities[asset] = opp

            # Callback if actionable
            if signal != FundingSignal.NONE and self.on_opportunity:
                self.on_opportunity(opp)

        return opportunities

    async def start(self):
        """Start continuous scanning"""
        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info("FundingScanner started")

    async def stop(self):
        """Stop scanning"""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
        logger.info("FundingScanner stopped")

    async def _scan_loop(self):
        """Main scan loop"""
        while self._running:
            try:
                await self.scan()
                await asyncio.sleep(self.config.scan_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scan error: {e}")
                await asyncio.sleep(5)

    def get_opportunities(
        self,
        min_annual_rate: float = 0.1  # 10% minimum
    ) -> List[FundingOpportunity]:
        """Get current actionable opportunities"""
        return [
            opp for opp in self.opportunities.values()
            if opp.signal != FundingSignal.NONE
            and opp.funding_rate_annual >= min_annual_rate
        ]

    def get_best_opportunity(self) -> Optional[FundingOpportunity]:
        """Get the best current opportunity by annual rate"""
        opportunities = self.get_opportunities()
        if not opportunities:
            return None

        return max(opportunities, key=lambda x: abs(x.funding_rate_annual))

    def record_position(
        self,
        asset: str,
        side: str,
        size: float,
        entry_price: float,
        funding_rate: float
    ):
        """Record a new funding arbitrage position"""
        self.positions[asset] = FundingPosition(
            asset=asset,
            side=side,
            size=size,
            entry_price=entry_price,
            entry_funding_rate=funding_rate
        )

    def record_funding_payment(self, asset: str, amount: float):
        """Record a funding payment received"""
        if asset in self.positions:
            pos = self.positions[asset]
            pos.total_funding_collected += amount
            pos.funding_payments += 1

            self.funding_history.append({
                "asset": asset,
                "amount": amount,
                "timestamp": time.time()
            })

            if self.on_funding_payment:
                self.on_funding_payment(asset, amount)

    def get_total_funding_collected(self) -> float:
        """Get total funding collected across all positions"""
        return sum(pos.total_funding_collected for pos in self.positions.values())

    def get_stats(self) -> Dict:
        """Get scanner statistics"""
        opportunities = self.get_opportunities()

        return {
            "running": self._running,
            "assets_monitored": len(self.config.assets),
            "opportunities_found": len(opportunities),
            "active_positions": len(self.positions),
            "total_funding_collected": self.get_total_funding_collected(),
            "funding_payments": len(self.funding_history),
            "best_opportunity": {
                "asset": self.get_best_opportunity().asset,
                "annual_rate": f"{self.get_best_opportunity().funding_rate_annual*100:.2f}%"
            } if self.get_best_opportunity() else None
        }


# =========================================
# CROSS-EXCHANGE SCANNER (Bonus Alpha)
# =========================================

@dataclass
class CrossExchangeOpportunity:
    """Cross-exchange funding arbitrage opportunity"""
    asset: str
    exchange_a: str
    exchange_b: str
    rate_a: float  # Funding on exchange A
    rate_b: float  # Funding on exchange B
    spread: float  # rate_a - rate_b
    spread_annual: float
    action: str  # "LONG_A_SHORT_B" or "SHORT_A_LONG_B"


class CrossExchangeFundingScanner:
    """
    Cross-Exchange Funding Scanner

    Finds opportunities where funding rates differ between exchanges.
    Example: Hyperliquid +0.02%, Binance +0.01%
    -> Short on Hyperliquid, Long on Binance
    -> Collect 0.01% per 8h = 10.95% annually EXTRA

    Note: Requires API access to multiple exchanges.
    """

    def __init__(self):
        # Would need to integrate multiple exchange APIs
        # Binance, Bybit, OKX, dYdX, etc.
        pass

    async def scan_cross_exchange(
        self,
        asset: str
    ) -> Optional[CrossExchangeOpportunity]:
        """
        Scan for cross-exchange funding opportunities.

        This is a placeholder - full implementation would require:
        1. Binance Futures API client
        2. Bybit API client
        3. OKX API client
        4. dYdX client

        For now, we focus on Hyperliquid-only funding arbitrage.
        """
        # TODO: Implement cross-exchange scanning
        pass


# =========================================
# DEMO / TEST
# =========================================

async def demo_funding_scanner():
    """Demo the funding scanner"""
    print("\n" + "=" * 60)
    print("FUNDING RATE SCANNER DEMO")
    print("=" * 60 + "\n")

    # Create client (no private key needed for read-only)
    client = HyperliquidClient(testnet=True)

    # Create scanner
    config = FundingConfig(
        min_funding_rate=0.0001,  # Lower threshold for demo
        assets=["BTC", "ETH", "SOL", "DOGE", "XRP"]
    )
    scanner = FundingScanner(client, config)

    # Set callback
    def on_opp(opp: FundingOpportunity):
        print(f"\nOPPORTUNITY: {opp.asset}")
        print(f"  Funding: {opp.funding_rate*100:.4f}% per 8h")
        print(f"  Annual: {opp.funding_rate_annual*100:.2f}%")
        print(f"  Signal: {opp.signal.value}")
        print(f"  Hours to funding: {opp.hours_to_funding:.1f}")

    scanner.on_opportunity = on_opp

    # Scan once
    print("Scanning funding rates...\n")
    opportunities = await scanner.scan()

    print("\n" + "-" * 40)
    print("ALL FUNDING RATES:")
    print("-" * 40)

    for opp in sorted(opportunities, key=lambda x: abs(x.funding_rate), reverse=True):
        direction = "+" if opp.funding_rate > 0 else ""
        print(f"{opp.asset:6} | {direction}{opp.funding_rate*100:.4f}% | {opp.funding_rate_annual*100:6.2f}% annual | {opp.signal.value}")

    # Get best
    best = scanner.get_best_opportunity()
    if best:
        print(f"\nBEST OPPORTUNITY: {best.asset}")
        print(f"  Expected annual return: {best.funding_rate_annual*100:.2f}%")
        print(f"  On $5,000 position: ${5000 * best.funding_rate_annual:,.2f}/year passive")

    print("\n" + "=" * 60)
    print("Demo complete!")


if __name__ == "__main__":
    asyncio.run(demo_funding_scanner())
