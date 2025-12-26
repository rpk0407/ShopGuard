"""
Monte Carlo Simulation Engine

For scenario analysis, risk estimation, and strategy validation.

KEY PRINCIPLE: Monte Carlo doesn't predict the future. It maps the
DISTRIBUTION of possible outcomes given model assumptions.

The value is in understanding:
1. What can go wrong (tail risk)
2. How strategies perform across regimes
3. The sensitivity of results to parameter changes
"""

import numpy as np
from dataclasses import dataclass
from typing import Callable, List, Dict, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor
import multiprocessing


@dataclass
class SimulationConfig:
    """Configuration for Monte Carlo simulation."""
    n_simulations: int = 10000      # Number of paths to simulate
    n_steps: int = 252              # Steps per path (252 = 1 year of daily)
    seed: Optional[int] = None      # Random seed for reproducibility
    n_workers: int = None           # Parallel workers (None = CPU count)

    def __post_init__(self):
        if self.n_workers is None:
            self.n_workers = max(1, multiprocessing.cpu_count() - 1)


@dataclass
class SimulationResult:
    """Results from Monte Carlo simulation."""
    paths: np.ndarray                      # Simulated paths
    final_values: np.ndarray               # Terminal values
    statistics: Dict[str, float]           # Summary statistics
    percentiles: Dict[int, float]          # Key percentiles
    var_95: float                          # 95% Value at Risk
    cvar_95: float                         # 95% Conditional VaR (Expected Shortfall)


class MonteCarloEngine:
    """
    Core Monte Carlo simulation engine.

    This engine is agnostic to the underlying model - it takes a
    path generator function and runs simulations.
    """

    def __init__(self, config: SimulationConfig = None):
        self.config = config or SimulationConfig()
        if self.config.seed is not None:
            np.random.seed(self.config.seed)

    def simulate(
        self,
        path_generator: Callable[[int], np.ndarray],
        initial_value: float = 1.0
    ) -> SimulationResult:
        """
        Run Monte Carlo simulation.

        Args:
            path_generator: Function that takes n_steps and returns a price path
            initial_value: Starting value (for calculating returns)

        Returns:
            SimulationResult with all analysis
        """
        n_sims = self.config.n_simulations
        n_steps = self.config.n_steps

        # Generate paths
        paths = np.zeros((n_sims, n_steps + 1))
        for i in range(n_sims):
            paths[i] = path_generator(n_steps)

        final_values = paths[:, -1]
        returns = (final_values - initial_value) / initial_value

        # Calculate statistics
        statistics = {
            "mean_return": np.mean(returns),
            "median_return": np.median(returns),
            "std_return": np.std(returns),
            "skewness": self._skewness(returns),
            "kurtosis": self._kurtosis(returns),
            "sharpe_ratio": np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0,
            "max_return": np.max(returns),
            "min_return": np.min(returns),
            "positive_prob": np.mean(returns > 0),
        }

        # Percentiles
        percentiles = {
            1: np.percentile(returns, 1),
            5: np.percentile(returns, 5),
            10: np.percentile(returns, 10),
            25: np.percentile(returns, 25),
            50: np.percentile(returns, 50),
            75: np.percentile(returns, 75),
            90: np.percentile(returns, 90),
            95: np.percentile(returns, 95),
            99: np.percentile(returns, 99),
        }

        # Value at Risk and Conditional VaR
        var_95 = -np.percentile(returns, 5)  # 5th percentile loss
        cvar_95 = -np.mean(returns[returns <= np.percentile(returns, 5)])

        return SimulationResult(
            paths=paths,
            final_values=final_values,
            statistics=statistics,
            percentiles=percentiles,
            var_95=var_95,
            cvar_95=cvar_95
        )

    def _skewness(self, x: np.ndarray) -> float:
        """Calculate skewness (third standardized moment)."""
        n = len(x)
        mean = np.mean(x)
        std = np.std(x)
        if std == 0:
            return 0.0
        return np.sum(((x - mean) / std) ** 3) / n

    def _kurtosis(self, x: np.ndarray) -> float:
        """Calculate excess kurtosis (fourth standardized moment - 3)."""
        n = len(x)
        mean = np.mean(x)
        std = np.std(x)
        if std == 0:
            return 0.0
        return np.sum(((x - mean) / std) ** 4) / n - 3


class ScenarioAnalyzer:
    """
    Scenario analysis for stress testing strategies.

    This goes beyond simple Monte Carlo by testing specific scenarios:
    - Market crashes (2008, 2020)
    - Volatility spikes (VIX > 40)
    - Correlation breakdowns
    - Liquidity crises
    """

    @dataclass
    class Scenario:
        """Definition of a market scenario."""
        name: str
        description: str
        drift_modifier: float     # Multiply normal drift by this
        vol_modifier: float       # Multiply normal vol by this
        correlation_shock: float  # Add to correlation matrix diagonal
        jump_probability: float   # Probability of large moves
        duration_days: int        # How long scenario lasts

    # Pre-defined scenarios based on historical events
    SCENARIOS = {
        "normal": Scenario(
            name="Normal",
            description="Business as usual",
            drift_modifier=1.0,
            vol_modifier=1.0,
            correlation_shock=0.0,
            jump_probability=0.01,
            duration_days=252
        ),
        "2008_crisis": Scenario(
            name="2008 Financial Crisis",
            description="Lehman collapse, credit freeze, correlation spike",
            drift_modifier=-2.0,
            vol_modifier=4.0,
            correlation_shock=0.3,
            jump_probability=0.15,
            duration_days=120
        ),
        "2020_covid": Scenario(
            name="COVID-19 Crash",
            description="Fast crash, V-shaped recovery potential",
            drift_modifier=-5.0,
            vol_modifier=5.0,
            correlation_shock=0.4,
            jump_probability=0.25,
            duration_days=30
        ),
        "flash_crash": Scenario(
            name="Flash Crash",
            description="Intraday liquidity evaporation",
            drift_modifier=-10.0,
            vol_modifier=8.0,
            correlation_shock=0.5,
            jump_probability=0.50,
            duration_days=1
        ),
        "low_vol_grind": Scenario(
            name="Low Vol Grind",
            description="Complacency, slow grind higher (2017-like)",
            drift_modifier=1.5,
            vol_modifier=0.5,
            correlation_shock=-0.1,
            jump_probability=0.005,
            duration_days=252
        ),
        "stagflation": Scenario(
            name="Stagflation",
            description="Rising rates, inflation, slow growth",
            drift_modifier=-0.5,
            vol_modifier=1.5,
            correlation_shock=0.1,
            jump_probability=0.03,
            duration_days=252
        ),
    }

    def __init__(self, base_drift: float, base_vol: float):
        """
        Initialize with baseline market parameters.

        Args:
            base_drift: Baseline annualized drift (e.g., 0.07 for 7%)
            base_vol: Baseline annualized volatility (e.g., 0.15 for 15%)
        """
        self.base_drift = base_drift
        self.base_vol = base_vol

    def run_scenario(
        self,
        scenario_name: str,
        strategy_returns_func: Callable[[np.ndarray], float],
        n_simulations: int = 1000
    ) -> Dict[str, float]:
        """
        Run strategy through a specific scenario.

        Args:
            scenario_name: Key from SCENARIOS dict
            strategy_returns_func: Function that takes price path, returns strategy PnL
            n_simulations: Number of simulations

        Returns:
            Dictionary with performance metrics under scenario
        """
        scenario = self.SCENARIOS.get(scenario_name)
        if scenario is None:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        # Modified parameters for scenario
        scenario_drift = self.base_drift * scenario.drift_modifier
        scenario_vol = self.base_vol * scenario.vol_modifier
        n_steps = scenario.duration_days

        results = []
        for _ in range(n_simulations):
            # Generate scenario-specific path
            path = self._generate_scenario_path(
                scenario_drift,
                scenario_vol,
                scenario.jump_probability,
                n_steps
            )
            # Run strategy on this path
            pnl = strategy_returns_func(path)
            results.append(pnl)

        results = np.array(results)

        return {
            "scenario": scenario_name,
            "mean_pnl": np.mean(results),
            "median_pnl": np.median(results),
            "std_pnl": np.std(results),
            "worst_case": np.percentile(results, 1),
            "best_case": np.percentile(results, 99),
            "prob_loss": np.mean(results < 0),
            "max_loss": np.min(results),
        }

    def stress_test_all(
        self,
        strategy_returns_func: Callable[[np.ndarray], float],
        n_simulations: int = 1000
    ) -> Dict[str, Dict[str, float]]:
        """Run strategy through all predefined scenarios."""
        return {
            name: self.run_scenario(name, strategy_returns_func, n_simulations)
            for name in self.SCENARIOS.keys()
        }

    def _generate_scenario_path(
        self,
        drift: float,
        vol: float,
        jump_prob: float,
        n_steps: int
    ) -> np.ndarray:
        """Generate a price path with scenario parameters."""
        dt = 1 / 252
        path = np.zeros(n_steps + 1)
        path[0] = 100.0  # Arbitrary starting price

        for t in range(n_steps):
            # Normal diffusion
            dW = np.random.normal(0, np.sqrt(dt))
            ret = (drift - 0.5 * vol**2) * dt + vol * dW

            # Potential jump
            if np.random.random() < jump_prob:
                # Large negative jump (crisis-like)
                ret += np.random.normal(-0.05, 0.03)

            path[t + 1] = path[t] * np.exp(ret)

        return path


def bootstrap_confidence_interval(
    data: np.ndarray,
    statistic_func: Callable[[np.ndarray], float],
    n_bootstrap: int = 10000,
    confidence: float = 0.95
) -> Tuple[float, float, float]:
    """
    Bootstrap confidence interval for any statistic.

    CRITICAL FOR TRADING: Use this to quantify uncertainty in your
    backtest results. A strategy with "50% annual return" but a
    95% CI of [-10%, 110%] is NOT the same as one with CI [40%, 60%].

    Args:
        data: Original data sample
        statistic_func: Function to compute statistic of interest
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level (e.g., 0.95 for 95%)

    Returns:
        Tuple of (point_estimate, lower_bound, upper_bound)
    """
    n = len(data)
    bootstrap_stats = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        # Resample with replacement
        resample = data[np.random.randint(0, n, n)]
        bootstrap_stats[i] = statistic_func(resample)

    point_estimate = statistic_func(data)
    alpha = 1 - confidence
    lower = np.percentile(bootstrap_stats, 100 * alpha / 2)
    upper = np.percentile(bootstrap_stats, 100 * (1 - alpha / 2))

    return point_estimate, lower, upper
