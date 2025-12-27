"""
Market Making Strategies

Market makers provide liquidity by continuously quoting bid and ask prices.
They profit from the spread but face risks:
1. Inventory risk (accumulating unwanted positions)
2. Adverse selection (trading with informed traders)
3. Volatility risk (prices moving against inventory)

This module implements:
- Avellaneda-Stoikov optimal market making
- Inventory management
- Dynamic spread adjustment
- Quote optimization
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import heapq


class InventoryState(Enum):
    """Inventory position state."""
    LONG_EXTREME = "long_extreme"
    LONG = "long"
    NEUTRAL = "neutral"
    SHORT = "short"
    SHORT_EXTREME = "short_extreme"


@dataclass
class Quote:
    """A two-sided quote."""
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    timestamp: datetime

    @property
    def mid_price(self) -> float:
        return (self.bid_price + self.ask_price) / 2

    @property
    def spread(self) -> float:
        return self.ask_price - self.bid_price

    @property
    def spread_bps(self) -> float:
        return (self.spread / self.mid_price) * 10000


@dataclass
class MarketMakerParams:
    """Parameters for market making strategy."""
    # Risk parameters
    gamma: float = 0.1              # Risk aversion (higher = more conservative)
    max_inventory: float = 100      # Maximum position (units)
    inventory_target: float = 0     # Target inventory level

    # Quote parameters
    min_spread_bps: float = 5       # Minimum spread in bps
    max_spread_bps: float = 50      # Maximum spread in bps
    quote_size: float = 10          # Default quote size

    # Time parameters
    time_horizon: float = 1.0       # Trading horizon (days)
    quote_lifetime_ms: float = 100  # How long quotes live

    # Fee structure
    maker_rebate: float = 0.0002    # Maker rebate (earn for providing)
    taker_fee: float = 0.0003       # Taker fee (pay for taking)


@dataclass
class InventoryStats:
    """Inventory position statistics."""
    current_position: float
    average_cost: float
    unrealized_pnl: float
    realized_pnl: float
    position_age: timedelta
    state: InventoryState


class InventoryManager:
    """
    Manage market maker inventory.

    Key responsibilities:
    - Track position and P&L
    - Signal when to reduce exposure
    - Compute inventory risk metrics
    """

    def __init__(self, params: MarketMakerParams):
        self.params = params
        self.position = 0.0
        self.average_cost = 0.0
        self.realized_pnl = 0.0
        self.position_opened_at: Optional[datetime] = None
        self.position_history: List[Tuple[datetime, float]] = []

    def update_position(
        self,
        quantity_change: float,
        price: float,
        timestamp: datetime
    ):
        """Update inventory after a fill."""
        if quantity_change == 0:
            return

        old_position = self.position

        if self.position == 0:
            # Opening new position
            self.position = quantity_change
            self.average_cost = price
            self.position_opened_at = timestamp
        elif np.sign(self.position + quantity_change) == np.sign(self.position):
            # Adding to position
            total_cost = self.position * self.average_cost + quantity_change * price
            self.position += quantity_change
            self.average_cost = total_cost / self.position if self.position != 0 else 0
        else:
            # Reducing or flipping position
            close_qty = min(abs(quantity_change), abs(self.position))
            pnl = close_qty * (price - self.average_cost) * np.sign(self.position)
            self.realized_pnl += pnl

            remaining = abs(quantity_change) - close_qty
            if remaining > 0:
                # Flipping position
                self.position = remaining * np.sign(quantity_change)
                self.average_cost = price
                self.position_opened_at = timestamp
            else:
                self.position += quantity_change
                if abs(self.position) < 1e-10:
                    self.position = 0
                    self.average_cost = 0
                    self.position_opened_at = None

        self.position_history.append((timestamp, self.position))

    def get_unrealized_pnl(self, current_price: float) -> float:
        """Compute unrealized P&L at current price."""
        if self.position == 0:
            return 0
        return self.position * (current_price - self.average_cost)

    def get_state(self, current_price: float = None) -> InventoryStats:
        """Get current inventory state."""
        max_inv = self.params.max_inventory

        if abs(self.position) < max_inv * 0.2:
            state = InventoryState.NEUTRAL
        elif abs(self.position) < max_inv * 0.6:
            state = InventoryState.LONG if self.position > 0 else InventoryState.SHORT
        else:
            state = InventoryState.LONG_EXTREME if self.position > 0 else InventoryState.SHORT_EXTREME

        position_age = timedelta(0)
        if self.position_opened_at:
            position_age = datetime.now() - self.position_opened_at

        unrealized = self.get_unrealized_pnl(current_price) if current_price else 0

        return InventoryStats(
            current_position=self.position,
            average_cost=self.average_cost,
            unrealized_pnl=unrealized,
            realized_pnl=self.realized_pnl,
            position_age=position_age,
            state=state
        )

    def inventory_penalty(self) -> float:
        """
        Compute inventory penalty for quote adjustment.

        Higher penalty = wider spread on the side we don't want to trade.
        """
        q = self.position
        max_q = self.params.max_inventory

        # Normalized inventory [-1, 1]
        normalized = np.clip(q / max_q, -1, 1)

        # Quadratic penalty
        return normalized ** 2


class QuoteGenerator:
    """
    Generate optimal quotes using Avellaneda-Stoikov framework.

    The optimal quotes depend on:
    1. Current inventory (skew quotes to reduce risk)
    2. Volatility (wider spreads in volatile markets)
    3. Time horizon (tighter spreads near market close)
    4. Market conditions (toxicity, competition)
    """

    def __init__(
        self,
        params: MarketMakerParams,
        inventory_manager: InventoryManager
    ):
        self.params = params
        self.inventory = inventory_manager

        # Volatility estimation
        self.price_history: List[float] = []
        self.volatility = 0.02  # Initial estimate (2% daily)

    def update_volatility(self, price: float):
        """Update volatility estimate."""
        self.price_history.append(price)

        if len(self.price_history) > 100:
            self.price_history.pop(0)

        if len(self.price_history) > 20:
            returns = np.diff(self.price_history) / np.array(self.price_history[:-1])
            self.volatility = np.std(returns) * np.sqrt(252 * 24 * 60)  # Annualized

    def generate_quote(
        self,
        mid_price: float,
        time_remaining: float = None,
        toxicity: float = 0.5
    ) -> Quote:
        """
        Generate optimal two-sided quote.

        Uses Avellaneda-Stoikov reservation price and optimal spread.

        Reservation price: r = s - q * γ * σ² * (T - t)
        Optimal spread: δ = γ * σ² * (T - t) + 2/γ * ln(1 + γ/k)

        Where:
        - s: mid price
        - q: inventory
        - γ: risk aversion
        - σ: volatility
        - T - t: time remaining
        - k: order arrival rate parameter
        """
        if time_remaining is None:
            time_remaining = self.params.time_horizon

        gamma = self.params.gamma
        sigma = self.volatility
        q = self.inventory.position

        # Reservation price (mid adjusted for inventory)
        reservation_price = mid_price - q * gamma * sigma**2 * time_remaining

        # Optimal spread
        k = 1.5  # Order arrival rate parameter
        base_spread = gamma * sigma**2 * time_remaining + (2/gamma) * np.log(1 + gamma/k)

        # Convert to price units
        spread_price = base_spread * mid_price

        # Adjust for toxicity (wider spread in toxic conditions)
        toxicity_adjustment = 1 + toxicity * 0.5
        spread_price *= toxicity_adjustment

        # Enforce min/max spread
        min_spread = mid_price * self.params.min_spread_bps / 10000
        max_spread = mid_price * self.params.max_spread_bps / 10000
        spread_price = np.clip(spread_price, min_spread, max_spread)

        # Inventory skew (shift quotes to reduce inventory)
        inventory_skew = q / self.params.max_inventory * spread_price * 0.5

        bid_price = reservation_price - spread_price / 2 + inventory_skew
        ask_price = reservation_price + spread_price / 2 + inventory_skew

        # Quote sizes (reduce size on risky side)
        base_size = self.params.quote_size
        inventory_ratio = abs(q) / self.params.max_inventory

        if q > 0:  # Long inventory, want to sell more
            bid_size = base_size * (1 - inventory_ratio * 0.5)
            ask_size = base_size
        elif q < 0:  # Short inventory, want to buy more
            bid_size = base_size
            ask_size = base_size * (1 - inventory_ratio * 0.5)
        else:
            bid_size = base_size
            ask_size = base_size

        return Quote(
            bid_price=bid_price,
            bid_size=bid_size,
            ask_price=ask_price,
            ask_size=ask_size,
            timestamp=datetime.now()
        )

    def should_pause_quoting(self) -> Tuple[bool, str]:
        """
        Determine if we should pause quoting.

        Reasons to pause:
        - Inventory too extreme
        - Volatility too high
        - Large price gap detected
        """
        inv_state = self.inventory.get_state()

        if inv_state.state in [InventoryState.LONG_EXTREME, InventoryState.SHORT_EXTREME]:
            return True, "Inventory extreme"

        if self.volatility > 0.5:  # 50% annualized = very high
            return True, "Volatility too high"

        return False, ""


class MarketMaker:
    """
    Complete market making system.

    Coordinates:
    - Inventory management
    - Quote generation
    - Risk controls
    - Performance tracking
    """

    def __init__(self, params: MarketMakerParams = None):
        self.params = params or MarketMakerParams()
        self.inventory = InventoryManager(self.params)
        self.quote_gen = QuoteGenerator(self.params, self.inventory)

        # Performance tracking
        self.trades: List[Dict] = []
        self.quotes_sent = 0
        self.quotes_filled = 0

        # State
        self.active_quote: Optional[Quote] = None
        self.paused = False
        self.pause_reason = ""

    def on_market_update(
        self,
        mid_price: float,
        toxicity: float = 0.5,
        time_remaining: float = None
    ) -> Optional[Quote]:
        """
        Process market update and generate new quote if needed.

        Args:
            mid_price: Current mid price
            toxicity: Order flow toxicity estimate
            time_remaining: Time remaining in trading session

        Returns:
            New quote, or None if paused
        """
        # Update volatility estimate
        self.quote_gen.update_volatility(mid_price)

        # Check if should pause
        should_pause, reason = self.quote_gen.should_pause_quoting()
        if should_pause:
            self.paused = True
            self.pause_reason = reason
            return None

        self.paused = False
        self.pause_reason = ""

        # Generate new quote
        quote = self.quote_gen.generate_quote(mid_price, time_remaining, toxicity)
        self.active_quote = quote
        self.quotes_sent += 1

        return quote

    def on_fill(
        self,
        side: str,
        quantity: float,
        price: float,
        timestamp: datetime = None
    ):
        """Process a fill (our quote was hit)."""
        if timestamp is None:
            timestamp = datetime.now()

        # Update inventory
        quantity_change = quantity if side == 'buy' else -quantity
        self.inventory.update_position(quantity_change, price, timestamp)

        # Record trade
        self.trades.append({
            'side': side,
            'quantity': quantity,
            'price': price,
            'timestamp': timestamp,
            'inventory_after': self.inventory.position
        })

        self.quotes_filled += 1

    def get_performance_metrics(self, current_price: float) -> Dict:
        """Get market making performance metrics."""
        inv_stats = self.inventory.get_state(current_price)

        total_pnl = inv_stats.realized_pnl + inv_stats.unrealized_pnl

        # Trading metrics
        n_trades = len(self.trades)
        buy_trades = [t for t in self.trades if t['side'] == 'buy']
        sell_trades = [t for t in self.trades if t['side'] == 'sell']

        avg_spread_earned = 0
        if buy_trades and sell_trades:
            avg_buy = np.mean([t['price'] for t in buy_trades])
            avg_sell = np.mean([t['price'] for t in sell_trades])
            avg_spread_earned = (avg_sell - avg_buy) / current_price * 10000

        fill_rate = self.quotes_filled / self.quotes_sent if self.quotes_sent > 0 else 0

        return {
            'total_pnl': total_pnl,
            'realized_pnl': inv_stats.realized_pnl,
            'unrealized_pnl': inv_stats.unrealized_pnl,
            'current_inventory': inv_stats.current_position,
            'inventory_state': inv_stats.state.value,
            'n_trades': n_trades,
            'avg_spread_earned_bps': avg_spread_earned,
            'fill_rate': fill_rate,
            'quotes_sent': self.quotes_sent,
            'is_paused': self.paused,
            'pause_reason': self.pause_reason
        }


class AdaptiveMarketMaker(MarketMaker):
    """
    Adaptive market maker that adjusts to market conditions.

    Enhancements:
    - Regime detection (adjust for trending vs mean-reverting)
    - Competition awareness (adjust for other MMs)
    - Event detection (widen around news)
    """

    def __init__(self, params: MarketMakerParams = None):
        super().__init__(params)
        self.regime = "normal"
        self.competition_level = 0.5
        self.event_mode = False

    def detect_regime(self, prices: List[float]) -> str:
        """Detect market regime for strategy adjustment."""
        if len(prices) < 50:
            return "normal"

        returns = np.diff(prices) / np.array(prices[:-1])

        # Check for trending (autocorrelation)
        autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]

        # Check for mean-reversion
        if autocorr < -0.3:
            return "mean_reverting"
        elif autocorr > 0.3:
            return "trending"
        else:
            return "normal"

    def adjust_for_regime(self, quote: Quote) -> Quote:
        """Adjust quote for detected regime."""
        if self.regime == "trending":
            # Wider spreads, skew against trend
            spread_mult = 1.5
        elif self.regime == "mean_reverting":
            # Tighter spreads, more aggressive inventory reduction
            spread_mult = 0.8
        else:
            spread_mult = 1.0

        new_spread = quote.spread * spread_mult
        mid = quote.mid_price

        return Quote(
            bid_price=mid - new_spread / 2,
            bid_size=quote.bid_size,
            ask_price=mid + new_spread / 2,
            ask_size=quote.ask_size,
            timestamp=quote.timestamp
        )

    def on_market_update(
        self,
        mid_price: float,
        toxicity: float = 0.5,
        time_remaining: float = None,
        prices: List[float] = None
    ) -> Optional[Quote]:
        """Enhanced market update with regime detection."""
        if prices:
            self.regime = self.detect_regime(prices)

        quote = super().on_market_update(mid_price, toxicity, time_remaining)

        if quote:
            quote = self.adjust_for_regime(quote)

        return quote
