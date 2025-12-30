"""
The Matrix - Reality Simulation Engine
=======================================
Generates synthetic market data to drive the ShopGuard infrastructure
without requiring real API keys.

Features:
- Geometric Brownian Motion (GBM) for realistic price movement
- Periodic "Perfect Storm" events (crashes + whale absorption)
- Viral K-Factor dynamics that respond to market conditions
- CVD (Cumulative Volume Delta) simulation with whale traps
- Entropy and Hurst exponent modeling

This allows demonstration of "God Mode" capabilities immediately.
"""
import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List, Optional
from enum import Enum

# Import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from utils.logging_config import get_logger
    logger = get_logger("shopguard.matrix")
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class MarketPhase(Enum):
    """Market cycle phases"""
    STABLE = "stable"
    CRASH = "crash"
    ACCUMULATION = "accumulation"
    RECOVERY = "recovery"
    EUPHORIA = "euphoria"


@dataclass
class MarketState:
    """Current simulated market state"""
    price: float
    price_history: List[float] = field(default_factory=list)
    volume: float = 0.0

    # Three-pillar metrics
    entropy: float = 0.5
    hurst: float = 0.5
    viral_k: float = 1.0
    viral_acceleration: float = 0.0
    cvd: float = 0.0
    cvd_trend: str = "NEUTRAL"

    # Detection flags
    whale_trap: bool = False
    distribution: bool = False

    # Market phase
    phase: MarketPhase = MarketPhase.STABLE
    phase_tick: int = 0

    # Volatility
    volatility: float = 0.02


class Matrix:
    """
    The Reality Simulation Engine.

    Generates continuous synthetic market data that mimics real markets
    with periodic anomalies to trigger the convergence strategy.
    """

    def __init__(
        self,
        base_price: float = 100.0,
        volatility: float = 0.02,
        drift: float = 0.0001,
        crash_interval: int = 60,  # seconds between "perfect storm" events
        tick_interval: float = 1.0  # seconds between ticks
    ):
        self.base_price = base_price
        self.volatility = volatility
        self.drift = drift
        self.crash_interval = crash_interval
        self.tick_interval = tick_interval

        # State per asset
        self.states: Dict[str, MarketState] = {}

        # Timing
        self.start_time = time.time()
        self.last_crash_time: Dict[str, float] = {}

        # Random seed for reproducibility (optional)
        self.rng = random.Random()

        logger.info(f"Matrix initialized: base_price={base_price}, volatility={volatility}, crash_interval={crash_interval}s")

    def _init_asset(self, asset: str) -> MarketState:
        """Initialize state for a new asset"""
        # Different base prices for different assets
        base_prices = {
            'BTC': 42000.0,
            'ETH': 2200.0,
            'SPY': 480.0,
            'QQQ': 420.0,
            'NVDA': 500.0
        }

        price = base_prices.get(asset, self.base_price)
        history = [price * (1 + self.rng.gauss(0, 0.01)) for _ in range(30)]
        history.append(price)

        state = MarketState(
            price=price,
            price_history=history,
            volume=self.rng.uniform(1e9, 5e9),
            entropy=self.rng.uniform(0.4, 0.6),
            hurst=self.rng.uniform(0.45, 0.55),
            viral_k=1.0,
            viral_acceleration=0.0,
            cvd=0.0
        )

        self.states[asset] = state
        self.last_crash_time[asset] = time.time()

        return state

    def _gbm_step(self, price: float, dt: float = 1.0) -> float:
        """
        Geometric Brownian Motion price step.

        dS = μ*S*dt + σ*S*dW

        Where:
        - μ = drift (expected return)
        - σ = volatility
        - dW = Wiener process increment
        """
        # Random component (Wiener process)
        dW = self.rng.gauss(0, math.sqrt(dt))

        # Price change
        dS = self.drift * price * dt + self.volatility * price * dW

        return price + dS

    def _calculate_entropy(self, price_history: List[float]) -> float:
        """
        Calculate Shannon entropy from price returns.

        Low entropy = ordered, predictable market (good for entry)
        High entropy = chaotic, unpredictable market (exit signal)
        """
        if len(price_history) < 10:
            return 0.5

        # Calculate returns
        returns = []
        for i in range(1, len(price_history)):
            if price_history[i-1] != 0:
                ret = (price_history[i] - price_history[i-1]) / price_history[i-1]
                returns.append(ret)

        if not returns:
            return 0.5

        # Bin returns into categories
        bins = 10
        min_ret, max_ret = min(returns), max(returns)
        if min_ret == max_ret:
            return 0.0

        bin_width = (max_ret - min_ret) / bins
        counts = [0] * bins

        for ret in returns:
            bin_idx = min(int((ret - min_ret) / bin_width), bins - 1)
            counts[bin_idx] += 1

        # Calculate entropy
        total = len(returns)
        entropy = 0.0
        for count in counts:
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)

        # Normalize to 0-1
        max_entropy = math.log2(bins)
        return min(1.0, entropy / max_entropy)

    def _calculate_hurst(self, price_history: List[float]) -> float:
        """
        Estimate Hurst exponent using R/S analysis.

        H > 0.5 = trending (persistent)
        H = 0.5 = random walk
        H < 0.5 = mean-reverting
        """
        if len(price_history) < 20:
            return 0.5

        # Simplified R/S calculation
        returns = []
        for i in range(1, len(price_history)):
            if price_history[i-1] != 0:
                ret = math.log(price_history[i] / price_history[i-1])
                returns.append(ret)

        if len(returns) < 10:
            return 0.5

        n = len(returns)
        mean = sum(returns) / n

        # Calculate cumulative deviation from mean
        cum_dev = []
        running = 0
        for ret in returns:
            running += ret - mean
            cum_dev.append(running)

        # Range
        R = max(cum_dev) - min(cum_dev)

        # Standard deviation
        S = (sum((r - mean) ** 2 for r in returns) / n) ** 0.5

        if S == 0:
            return 0.5

        # R/S ratio
        RS = R / S

        # Estimate H from log(R/S) / log(n)
        if RS > 0 and n > 1:
            H = math.log(RS) / math.log(n)
            return max(0.0, min(1.0, H + 0.5))  # Normalize around 0.5

        return 0.5

    def _should_trigger_crash(self, asset: str) -> bool:
        """Check if it's time for a "Perfect Storm" event"""
        elapsed = time.time() - self.last_crash_time.get(asset, time.time())
        return elapsed >= self.crash_interval

    def _execute_crash_phase(self, state: MarketState) -> None:
        """Execute the crash phase of the Perfect Storm"""
        # Price drops 2-5%
        crash_pct = self.rng.uniform(0.02, 0.05)
        state.price *= (1 - crash_pct)

        # Entropy spikes (chaos)
        state.entropy = min(0.95, state.entropy + 0.3)

        # Volatility increases
        state.volatility = self.volatility * 2

        # Viral panic (K drops initially)
        state.viral_k = max(0.5, state.viral_k - 0.3)
        state.viral_acceleration = -0.5

        # CVD drops (selling pressure)
        state.cvd -= self.rng.uniform(500, 1000)
        state.cvd_trend = "DISTRIBUTION"

        state.phase = MarketPhase.CRASH
        state.phase_tick = 0

        logger.info(f"💥 CRASH: Price dropped {crash_pct*100:.1f}% to ${state.price:.2f}")

    def _execute_accumulation_phase(self, state: MarketState) -> None:
        """Execute the accumulation phase - whales absorbing"""
        # Price stabilizes with small movements
        state.price *= (1 + self.rng.gauss(0, 0.005))

        # Entropy starts dropping (order returning)
        state.entropy = max(0.3, state.entropy - 0.05)

        # CVD reverses - WHALE TRAP forming
        state.cvd += self.rng.uniform(200, 500)
        state.cvd_trend = "ACCUMULATION"
        state.whale_trap = True

        # Viral K starts recovering
        state.viral_k = min(1.5, state.viral_k + 0.1)
        state.viral_acceleration = 0.2

        state.phase = MarketPhase.ACCUMULATION

        logger.info(f"🐋 ACCUMULATION: Whale trap forming, CVD reversing")

    def _execute_recovery_phase(self, state: MarketState) -> None:
        """Execute the recovery phase - price starts rising"""
        # Price recovers
        state.price *= (1 + self.rng.uniform(0.005, 0.02))

        # Entropy continues dropping (trend emerging)
        state.entropy = max(0.2, state.entropy - 0.1)

        # Hurst increases (trending)
        state.hurst = min(0.8, state.hurst + 0.05)

        # Viral K spikes - EXPLOSIVE GROWTH
        state.viral_k = min(2.0, state.viral_k + 0.2)
        state.viral_acceleration = 0.5

        # CVD strongly positive
        state.cvd += self.rng.uniform(300, 600)

        state.phase = MarketPhase.RECOVERY

        logger.info(f"📈 RECOVERY: Viral K={state.viral_k:.2f}, Entropy={state.entropy:.2f}")

    def _execute_stable_phase(self, state: MarketState) -> None:
        """Execute stable phase - normal market"""
        # Normal GBM movement
        state.price = self._gbm_step(state.price)

        # Entropy wanders
        state.entropy += self.rng.gauss(0, 0.02)
        state.entropy = max(0.3, min(0.7, state.entropy))

        # Hurst wanders
        state.hurst += self.rng.gauss(0, 0.01)
        state.hurst = max(0.4, min(0.6, state.hurst))

        # Viral K normal
        state.viral_k += self.rng.gauss(0, 0.05)
        state.viral_k = max(0.8, min(1.3, state.viral_k))
        state.viral_acceleration = self.rng.gauss(0, 0.1)

        # CVD wanders
        state.cvd += self.rng.gauss(0, 100)
        state.cvd_trend = "NEUTRAL"
        state.whale_trap = False
        state.distribution = False

        # Reset volatility
        state.volatility = self.volatility

        state.phase = MarketPhase.STABLE

    def tick(self, asset: str) -> Dict[str, Any]:
        """
        Generate a single market tick for an asset.

        Returns a dict with all data needed by the coordinator.
        """
        # Initialize if needed
        if asset not in self.states:
            self._init_asset(asset)

        state = self.states[asset]
        state.phase_tick += 1

        # Check for Perfect Storm trigger
        if state.phase == MarketPhase.STABLE and self._should_trigger_crash(asset):
            self._execute_crash_phase(state)
            self.last_crash_time[asset] = time.time()

        # Phase transitions
        elif state.phase == MarketPhase.CRASH and state.phase_tick >= 5:
            self._execute_accumulation_phase(state)

        elif state.phase == MarketPhase.ACCUMULATION and state.phase_tick >= 8:
            self._execute_recovery_phase(state)

        elif state.phase == MarketPhase.RECOVERY and state.phase_tick >= 10:
            state.phase = MarketPhase.EUPHORIA
            state.whale_trap = False

        elif state.phase == MarketPhase.EUPHORIA and state.phase_tick >= 15:
            state.phase = MarketPhase.STABLE
            state.phase_tick = 0

        elif state.phase == MarketPhase.STABLE:
            self._execute_stable_phase(state)

        else:
            # Continue current phase with minor updates
            state.price = self._gbm_step(state.price)
            state.price = max(state.price, 1.0)  # Floor

        # Update price history
        state.price_history.append(state.price)
        if len(state.price_history) > 100:
            state.price_history = state.price_history[-100:]

        # Recalculate derived metrics
        state.entropy = self._calculate_entropy(state.price_history)
        state.hurst = self._calculate_hurst(state.price_history)

        # Build output dict
        return self._build_tick_data(asset, state)

    def _build_tick_data(self, asset: str, state: MarketState) -> Dict[str, Any]:
        """Build the market data dict for consumption by coordinator"""

        # Determine entropy signal
        if state.entropy < 0.4:
            entropy_signal = "LOW_ENTROPY"
        elif state.entropy < 0.6:
            entropy_signal = "TRANSITIONAL"
        elif state.entropy < 0.8:
            entropy_signal = "HIGH_ENTROPY"
        else:
            entropy_signal = "CHAOS"

        # Determine hurst signal
        if state.hurst > 0.65:
            hurst_signal = "TRENDING"
        elif state.hurst > 0.5:
            hurst_signal = "NEUTRAL"
        else:
            hurst_signal = "MEAN_REVERTING"

        # Determine market regime
        if state.entropy < 0.6 and state.hurst > 0.65:
            market_regime = "SNIPE"  # Entry conditions
        elif state.entropy > 0.8:
            market_regime = "CHAOS"  # Exit
        elif state.hurst < 0.4:
            market_regime = "REVERSAL"
        else:
            market_regime = "CAUTION"

        # Determine viral signal
        if state.viral_k > 1.5 and state.viral_acceleration > 0.3:
            viral_signal = "EXPLOSIVE"
        elif state.viral_k > 1.2 and state.viral_acceleration > 0:
            viral_signal = "GROWING"
        elif state.viral_k > 0.8:
            viral_signal = "STABLE"
        else:
            viral_signal = "DECLINING"

        # Physics check (entropy < 0.6 AND hurst > 0.65)
        physics_check_passed = state.entropy < 0.6 and state.hurst > 0.65

        # Bio check (viral K > 1.2 AND acceleration > 0)
        bio_check_passed = state.viral_k > 1.2 and state.viral_acceleration > 0

        # Micro check (whale trap detected)
        micro_check_passed = state.whale_trap

        return {
            "asset": asset,
            "timestamp": datetime.now().isoformat(),
            "source": "matrix",

            # Price data
            "price": state.price,
            "price_history": list(state.price_history),
            "volume": state.volume + self.rng.uniform(-1e8, 1e8),
            "change_24h": ((state.price / state.price_history[0]) - 1) * 100 if state.price_history else 0,

            # Physics metrics (Technical Agent)
            "entropy": round(state.entropy, 4),
            "entropy_signal": entropy_signal,
            "hurst": round(state.hurst, 4),
            "hurst_signal": hurst_signal,
            "market_regime": market_regime,
            "volatility": state.volatility,
            "physics_check_passed": physics_check_passed,

            # Bio metrics (Social Agent)
            "viral_k_factor": round(state.viral_k, 3),
            "viral_acceleration": round(state.viral_acceleration, 3),
            "viral_signal": viral_signal,
            "bio_check_passed": bio_check_passed,

            # Micro metrics (Risk Agent)
            "cvd": round(state.cvd, 2),
            "cvd_trend": state.cvd_trend,
            "whale_trap_detected": state.whale_trap,
            "distribution_detected": state.distribution,
            "micro_check_passed": micro_check_passed,

            # Phase info (for debugging)
            "market_phase": state.phase.value,
            "phase_tick": state.phase_tick,

            # Convergence summary
            "convergence": {
                "bio_passed": bio_check_passed,
                "physics_passed": physics_check_passed,
                "micro_passed": micro_check_passed,
                "entry_signal": bio_check_passed and physics_check_passed and micro_check_passed,
                "exit_signal": state.entropy > 0.9 or state.viral_k < 0.8 or state.distribution,
                "signal_strength": sum([bio_check_passed, physics_check_passed, micro_check_passed]) / 3
            }
        }

    async def stream(
        self,
        assets: List[str] = None,
        interval: float = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async generator that yields market ticks continuously.

        Args:
            assets: List of assets to stream (default: ["BTC", "ETH"])
            interval: Seconds between ticks (default: self.tick_interval)

        Yields:
            Dict with market data for each asset
        """
        if assets is None:
            assets = ["BTC", "ETH"]
        if interval is None:
            interval = self.tick_interval

        logger.info(f"Matrix stream started: assets={assets}, interval={interval}s")

        asset_idx = 0

        while True:
            try:
                # Round-robin through assets
                asset = assets[asset_idx]
                asset_idx = (asset_idx + 1) % len(assets)

                # Generate tick
                tick_data = self.tick(asset)

                yield tick_data

                # Wait for next tick
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                logger.info("Matrix stream cancelled")
                break
            except Exception as e:
                logger.error(f"Matrix stream error: {e}")
                await asyncio.sleep(1)


# Singleton instance
matrix = Matrix()


# Convenience function
async def stream_market_data(
    assets: List[str] = None,
    interval: float = 1.0,
    crash_interval: int = 60
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream synthetic market data.

    Args:
        assets: List of assets to stream
        interval: Seconds between ticks
        crash_interval: Seconds between "Perfect Storm" events

    Yields:
        Market data dict for each tick
    """
    m = Matrix(crash_interval=crash_interval, tick_interval=interval)
    async for tick in m.stream(assets, interval):
        yield tick


# Test function
async def test_matrix():
    """Test the matrix with a few ticks"""
    print("\n" + "=" * 60)
    print("THE MATRIX - Reality Simulation Engine Test")
    print("=" * 60 + "\n")

    m = Matrix(crash_interval=10)  # Crash every 10 seconds for testing

    tick_count = 0
    async for tick in m.stream(["BTC"], interval=0.5):
        tick_count += 1

        phase = tick["market_phase"]
        price = tick["price"]
        entropy = tick["entropy"]
        viral_k = tick["viral_k_factor"]
        cvd_trend = tick["cvd_trend"]
        convergence = tick["convergence"]

        # Color-coded output
        if convergence["entry_signal"]:
            signal = "🔥 ENTRY SIGNAL"
        elif convergence["exit_signal"]:
            signal = "🔴 EXIT SIGNAL"
        else:
            checks = sum([
                convergence["bio_passed"],
                convergence["physics_passed"],
                convergence["micro_passed"]
            ])
            signal = f"⏳ {checks}/3 checks"

        print(f"[{tick_count:03d}] {phase:12s} | ${price:,.2f} | E:{entropy:.2f} K:{viral_k:.2f} CVD:{cvd_trend:12s} | {signal}")

        if tick_count >= 40:
            break

    print("\n" + "=" * 60)
    print("Matrix test complete!")


if __name__ == "__main__":
    asyncio.run(test_matrix())
