"""
Market Microstructure Signals

Microstructure = The study of how trading actually happens.

Key concepts:
- Information asymmetry (informed vs uninformed traders)
- Adverse selection (trading with those who know more)
- Inventory risk (market makers holding positions)
- Price discovery (how information gets into prices)

This module implements signals derived from microstructure theory.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import deque
from datetime import datetime, timedelta
from scipy import stats


@dataclass
class TradeData:
    """Individual trade record."""
    price: float
    quantity: float
    timestamp: datetime
    side: str           # 'buy' or 'sell'
    is_aggressive: bool # Did this trade cross the spread?


@dataclass
class ToxicityMetrics:
    """
    Metrics measuring order flow toxicity.

    Toxic flow = informed traders trading against market makers.
    """
    vpin: float                 # Volume-synchronized PIN
    kyle_lambda: float          # Price impact coefficient
    spread_toxicity: float      # Spread widening indicator
    volume_imbalance: float     # Buy vs sell volume ratio
    informed_ratio: float       # Estimated ratio of informed trading


class MicrostructureSignals:
    """
    Generate trading signals from microstructure analysis.

    These signals are particularly useful for:
    - Short-term price prediction
    - Execution timing
    - Risk management (avoiding toxic times)
    """

    def __init__(self, lookback_periods: int = 1000):
        self.trades: deque = deque(maxlen=lookback_periods)
        self.quotes: deque = deque(maxlen=lookback_periods)

    def add_trade(self, trade: TradeData):
        """Add a trade to history."""
        self.trades.append(trade)

    def add_quote(self, bid: float, ask: float, timestamp: datetime):
        """Add a quote to history."""
        self.quotes.append({
            'bid': bid, 'ask': ask, 'mid': (bid + ask) / 2,
            'spread': ask - bid, 'timestamp': timestamp
        })

    def compute_vpin(self, bucket_size: float = 10000) -> float:
        """
        Volume-Synchronized Probability of Informed Trading (VPIN).

        VPIN estimates the probability that the counterparty is informed.

        High VPIN = High probability of informed trading = Higher risk

        Method:
        1. Divide trades into volume buckets
        2. Classify each trade as buy/sell (Lee-Ready or similar)
        3. Compute imbalance |V_B - V_S| / V per bucket
        4. Average over recent buckets

        VPIN was developed by Easley, López de Prado, and O'Hara (2012).
        """
        if len(self.trades) < 100:
            return 0.5

        trades = list(self.trades)

        # Create volume buckets
        buckets = []
        current_bucket_buy = 0
        current_bucket_sell = 0
        current_volume = 0

        for trade in trades:
            if trade.side == 'buy':
                current_bucket_buy += trade.quantity
            else:
                current_bucket_sell += trade.quantity

            current_volume += trade.quantity

            if current_volume >= bucket_size:
                total = current_bucket_buy + current_bucket_sell
                if total > 0:
                    imbalance = abs(current_bucket_buy - current_bucket_sell) / total
                    buckets.append(imbalance)

                current_bucket_buy = 0
                current_bucket_sell = 0
                current_volume = 0

        if not buckets:
            return 0.5

        # VPIN = average imbalance
        vpin = np.mean(buckets)

        return vpin

    def compute_kyle_lambda(self, window: int = 50) -> float:
        """
        Estimate Kyle's lambda (price impact coefficient).

        From Kyle (1985): ΔP = λ * OFI

        Where:
        - ΔP: Price change
        - λ: Permanent price impact (Kyle's lambda)
        - OFI: Order flow imbalance (buy volume - sell volume)

        Higher λ = Less liquid, more price impact
        """
        if len(self.trades) < window or len(self.quotes) < window:
            return 0

        trades = list(self.trades)[-window:]
        quotes = list(self.quotes)[-window:]

        # Compute signed volume
        signed_volume = np.array([
            t.quantity if t.side == 'buy' else -t.quantity
            for t in trades
        ])

        # Compute price changes
        price_changes = np.diff([q['mid'] for q in quotes[:len(signed_volume)+1]])

        if len(price_changes) != len(signed_volume):
            min_len = min(len(price_changes), len(signed_volume))
            price_changes = price_changes[:min_len]
            signed_volume = signed_volume[:min_len]

        # Regression: ΔP = λ * OFI
        var_ofi = np.var(signed_volume)
        if var_ofi > 0:
            kyle_lambda = np.cov(price_changes, signed_volume)[0, 1] / var_ofi
        else:
            kyle_lambda = 0

        return max(0, kyle_lambda)  # Lambda should be positive

    def compute_roll_spread(self, window: int = 100) -> float:
        """
        Roll's implicit spread estimator.

        Based on serial covariance of price changes.
        Spread = 2 * sqrt(-Cov(ΔP_t, ΔP_{t-1}))

        Assumes bid-ask bounce is the main source of negative autocorrelation.
        """
        if len(self.trades) < window:
            return 0

        prices = [t.price for t in list(self.trades)[-window:]]
        price_changes = np.diff(prices)

        if len(price_changes) < 2:
            return 0

        # Autocovariance at lag 1
        autocov = np.cov(price_changes[:-1], price_changes[1:])[0, 1]

        if autocov < 0:
            roll_spread = 2 * np.sqrt(-autocov)
        else:
            roll_spread = 0

        return roll_spread

    def compute_hasbrouck_info_share(
        self,
        venue_prices: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """
        Hasbrouck Information Share.

        When an asset trades on multiple venues, which venue leads price discovery?

        Higher info share = More price discovery happens on that venue.
        """
        # Simplified: based on lead-lag correlation
        venues = list(venue_prices.keys())
        n_venues = len(venues)

        if n_venues < 2:
            return {v: 1.0 / n_venues for v in venues}

        # Compute lead-lag correlations
        lead_lags = {}
        for i, venue_i in enumerate(venues):
            for j, venue_j in enumerate(venues):
                if i != j:
                    returns_i = np.diff(venue_prices[venue_i])
                    returns_j = np.diff(venue_prices[venue_j])

                    min_len = min(len(returns_i), len(returns_j))
                    if min_len > 10:
                        # Lead-lag: correlate returns_i with lagged returns_j
                        lead = np.corrcoef(returns_i[1:min_len], returns_j[:min_len-1])[0, 1]
                        lag = np.corrcoef(returns_i[:min_len-1], returns_j[1:min_len])[0, 1]
                        lead_lags[(venue_i, venue_j)] = lead - lag

        # Convert to info shares (simplified)
        info_shares = {}
        for venue in venues:
            leads = [v for k, v in lead_lags.items() if k[0] == venue]
            info_shares[venue] = np.mean(leads) + 1 if leads else 1

        # Normalize
        total = sum(info_shares.values())
        return {k: v/total for k, v in info_shares.items()}

    def detect_momentum_ignition(
        self,
        window: int = 30,
        threshold: float = 3.0
    ) -> bool:
        """
        Detect potential momentum ignition.

        Momentum ignition = aggressive trading to trigger stops/algos.

        Signs:
        - Sudden spike in one-sided volume
        - Rapid price move
        - Often followed by reversal

        Returns True if momentum ignition is suspected.
        """
        if len(self.trades) < window:
            return False

        recent = list(self.trades)[-window:]

        # Check for one-sided volume
        buy_vol = sum(t.quantity for t in recent if t.side == 'buy')
        sell_vol = sum(t.quantity for t in recent if t.side == 'sell')
        total = buy_vol + sell_vol

        if total == 0:
            return False

        imbalance = abs(buy_vol - sell_vol) / total

        # Check for rapid price move
        prices = [t.price for t in recent]
        price_range = (max(prices) - min(prices)) / np.mean(prices)

        # Check for acceleration in trading
        first_half = recent[:len(recent)//2]
        second_half = recent[len(recent)//2:]
        vol_acceleration = sum(t.quantity for t in second_half) / (sum(t.quantity for t in first_half) + 1e-10)

        # Momentum ignition if high imbalance + large move + acceleration
        return (
            imbalance > 0.8 and
            price_range > 0.005 and  # 0.5% move
            vol_acceleration > 2.0
        )

    def detect_spoofing_pattern(self, book_history: List[Dict]) -> float:
        """
        Detect potential spoofing patterns.

        Spoofing = Placing large orders with intent to cancel before execution.

        Patterns:
        - Large orders appearing then disappearing
        - Orders that never get filled
        - Price moving toward orders that then cancel

        Returns a score 0-1 indicating spoofing likelihood.
        """
        if len(book_history) < 20:
            return 0

        # Look for orders that appear and disappear quickly
        large_order_events = []

        for i in range(1, len(book_history)):
            prev = book_history[i-1]
            curr = book_history[i]

            # Check bid side
            if 'bid_depth' in prev and 'bid_depth' in curr:
                if prev['bid_depth'] > curr['bid_depth'] * 2:
                    # Large order disappeared from bid
                    large_order_events.append({
                        'side': 'bid',
                        'size_ratio': prev['bid_depth'] / curr['bid_depth'],
                        'price_direction': 'down' if curr['mid'] < prev['mid'] else 'up'
                    })

            # Check ask side
            if 'ask_depth' in prev and 'ask_depth' in curr:
                if prev['ask_depth'] > curr['ask_depth'] * 2:
                    large_order_events.append({
                        'side': 'ask',
                        'size_ratio': prev['ask_depth'] / curr['ask_depth'],
                        'price_direction': 'up' if curr['mid'] > prev['mid'] else 'down'
                    })

        if not large_order_events:
            return 0

        # Check if price moved in the direction the spoofer wanted
        spoof_score = 0
        for event in large_order_events:
            if event['side'] == 'bid' and event['price_direction'] == 'down':
                spoof_score += 1  # Bid disappeared and price dropped (sell spoofing)
            elif event['side'] == 'ask' and event['price_direction'] == 'up':
                spoof_score += 1  # Ask disappeared and price rose (buy spoofing)

        return min(1.0, spoof_score / len(book_history) * 10)

    def get_toxicity_metrics(self) -> ToxicityMetrics:
        """Compute all toxicity metrics."""
        return ToxicityMetrics(
            vpin=self.compute_vpin(),
            kyle_lambda=self.compute_kyle_lambda(),
            spread_toxicity=self._compute_spread_toxicity(),
            volume_imbalance=self._compute_volume_imbalance(),
            informed_ratio=self._estimate_informed_ratio()
        )

    def _compute_spread_toxicity(self) -> float:
        """
        Spread toxicity: Does spread widen after trades?

        If spread widens after trades, market makers are being picked off.
        """
        if len(self.quotes) < 50 or len(self.trades) < 50:
            return 0

        quotes = list(self.quotes)[-50:]
        trades = list(self.trades)[-50:]

        # Find spread changes after aggressive trades
        aggressive_indices = [
            i for i, t in enumerate(trades)
            if t.is_aggressive
        ]

        if not aggressive_indices:
            return 0

        spread_changes = []
        for idx in aggressive_indices:
            if idx < len(quotes) - 5:
                before = np.mean([q['spread'] for q in quotes[max(0, idx-5):idx]])
                after = np.mean([q['spread'] for q in quotes[idx:idx+5]])
                if before > 0:
                    spread_changes.append((after - before) / before)

        if spread_changes:
            return np.mean(spread_changes)
        return 0

    def _compute_volume_imbalance(self) -> float:
        """Compute recent buy/sell volume imbalance."""
        if len(self.trades) < 20:
            return 0.5

        recent = list(self.trades)[-100:]
        buy_vol = sum(t.quantity for t in recent if t.side == 'buy')
        sell_vol = sum(t.quantity for t in recent if t.side == 'sell')
        total = buy_vol + sell_vol

        if total > 0:
            return buy_vol / total
        return 0.5

    def _estimate_informed_ratio(self) -> float:
        """
        Estimate ratio of informed trading.

        Uses simplified PIN model intuition.
        """
        vpin = self.compute_vpin()
        roll_spread = self.compute_roll_spread()

        if len(self.quotes) > 0:
            actual_spread = np.mean([q['spread'] for q in list(self.quotes)[-50:]])
        else:
            actual_spread = 0

        # If actual spread >> roll spread, suggests informed trading
        if roll_spread > 0:
            spread_ratio = actual_spread / roll_spread
        else:
            spread_ratio = 1

        # Combine signals
        informed_ratio = 0.5 * vpin + 0.5 * min(1, max(0, (spread_ratio - 1) / 2))

        return np.clip(informed_ratio, 0, 1)


class LeadLagAnalyzer:
    """
    Analyze lead-lag relationships between assets.

    Applications:
    - Pairs trading (lead asset signals lag asset)
    - Cross-asset momentum
    - Information transmission across markets
    """

    def __init__(self, max_lag: int = 10):
        self.max_lag = max_lag
        self.price_history: Dict[str, List[float]] = {}

    def add_price(self, symbol: str, price: float):
        """Add a price observation."""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)

    def compute_lead_lag(
        self,
        leader: str,
        lagger: str
    ) -> Dict[str, float]:
        """
        Compute lead-lag relationship between two assets.

        Returns:
            Dict with 'optimal_lag', 'correlation', 'granger_f_stat'
        """
        if leader not in self.price_history or lagger not in self.price_history:
            return {}

        returns_lead = np.diff(self.price_history[leader])
        returns_lag = np.diff(self.price_history[lagger])

        min_len = min(len(returns_lead), len(returns_lag))
        if min_len < 50:
            return {}

        returns_lead = returns_lead[-min_len:]
        returns_lag = returns_lag[-min_len:]

        # Find optimal lag by cross-correlation
        correlations = []
        for lag in range(self.max_lag + 1):
            if lag == 0:
                corr = np.corrcoef(returns_lead, returns_lag)[0, 1]
            else:
                corr = np.corrcoef(returns_lead[lag:], returns_lag[:-lag])[0, 1]
            correlations.append((lag, corr))

        optimal_lag, best_corr = max(correlations, key=lambda x: abs(x[1]))

        # Simple Granger causality test (F-statistic)
        # H0: Leader does not Granger-cause Lagger
        if optimal_lag > 0:
            X = returns_lead[:-optimal_lag]
            y = returns_lag[optimal_lag:]
            y_lagged = returns_lag[:-optimal_lag]

            # Restricted model: y ~ y_lagged
            rss_r = np.sum((y - np.mean(y))**2)

            # Unrestricted model: y ~ y_lagged + X
            # Simple regression
            X_full = np.column_stack([np.ones(len(X)), y_lagged, X])
            try:
                beta = np.linalg.lstsq(X_full, y, rcond=None)[0]
                y_pred = X_full @ beta
                rss_u = np.sum((y - y_pred)**2)

                n = len(y)
                k = 1  # One restriction
                f_stat = ((rss_r - rss_u) / k) / (rss_u / (n - 3))
            except Exception:
                f_stat = 0
        else:
            f_stat = 0

        return {
            'optimal_lag': optimal_lag,
            'correlation': best_corr,
            'granger_f_stat': f_stat
        }
