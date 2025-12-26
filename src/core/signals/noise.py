"""
Noise Estimation and Signal-to-Noise Analysis

The fundamental question: Is this price movement SIGNAL or NOISE?

- Signal: Information about future prices (tradeable)
- Noise: Random fluctuations with no predictive value

This module provides tools to:
1. Estimate noise levels in price data
2. Calculate signal-to-noise ratios
3. Determine if a signal is statistically significant
4. Adjust position sizing based on signal quality
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class NoiseProfile:
    """Characterization of noise in a time series."""
    noise_variance: float            # Estimated noise variance
    noise_std: float                 # Noise standard deviation
    signal_variance: float           # Estimated signal variance
    snr: float                       # Signal-to-noise ratio
    snr_db: float                    # SNR in decibels
    autocorrelation_lag1: float      # First-order autocorrelation
    is_dominated_by_noise: bool      # True if SNR < 1


class NoiseEstimator:
    """
    Noise level estimation for financial time series.

    Multiple methods because market noise is complex:
    - Microstructure noise (bid-ask bounce)
    - Sampling noise (discrete observations)
    - Information noise (irrelevant news)
    """

    def estimate_realized_variance_noise(
        self,
        prices: np.ndarray,
        method: str = "two_scale"
    ) -> float:
        """
        Estimate microstructure noise variance.

        High-frequency returns are contaminated by bid-ask bounce
        and other microstructure effects. This biases realized
        variance estimates.

        Methods:
        - "two_scale": Two-scale realized variance (Zhang et al., 2005)
        - "kernel": Kernel-based estimation (Barndorff-Nielsen et al., 2008)
        """
        log_returns = np.diff(np.log(prices))
        n = len(log_returns)

        if method == "two_scale":
            # Two-scale RV: compare fine and coarse sampling
            # The difference reveals microstructure noise
            rv_fine = np.sum(log_returns**2)

            # Coarse sampling (every k observations)
            k = max(2, n // 20)
            coarse_returns = np.log(prices[::k][1:]) - np.log(prices[::k][:-1])
            rv_coarse = np.sum(coarse_returns**2) * k

            # Noise variance = (RV_fine - RV_coarse) / (2n)
            noise_var = max(0, (rv_fine - rv_coarse) / (2 * n))

        elif method == "kernel":
            # Bartlett kernel estimator
            # Downweights autocovariances at higher lags
            max_lag = min(20, n // 5)
            gamma_0 = np.var(log_returns)

            kernel_rv = gamma_0
            for h in range(1, max_lag + 1):
                gamma_h = np.mean(log_returns[h:] * log_returns[:-h])
                weight = 1 - h / (max_lag + 1)  # Bartlett kernel
                kernel_rv += 2 * weight * gamma_h

            # Noise variance from difference
            noise_var = max(0, gamma_0 - kernel_rv)

        else:
            raise ValueError(f"Unknown method: {method}")

        return noise_var

    def estimate_from_residuals(
        self,
        data: np.ndarray,
        filter_type: str = "moving_average"
    ) -> float:
        """
        Estimate noise as residuals from filtered signal.

        Args:
            data: Time series
            filter_type: "moving_average" or "exponential"

        Returns:
            Estimated noise variance
        """
        if filter_type == "moving_average":
            window = min(20, len(data) // 5)
            filtered = np.convolve(data, np.ones(window)/window, mode='valid')
            # Align with original
            offset = window // 2
            residuals = data[offset:offset+len(filtered)] - filtered

        elif filter_type == "exponential":
            alpha = 0.1
            filtered = np.zeros_like(data)
            filtered[0] = data[0]
            for i in range(1, len(data)):
                filtered[i] = alpha * data[i] + (1 - alpha) * filtered[i-1]
            residuals = data - filtered

        else:
            raise ValueError(f"Unknown filter type: {filter_type}")

        return np.var(residuals)

    def estimate_mad_robust(self, data: np.ndarray) -> float:
        """
        Robust noise estimation using Median Absolute Deviation.

        MAD is robust to outliers (unlike variance) and provides
        a consistent estimate of standard deviation:
        σ ≈ MAD / 0.6745

        For differenced data (returns), this estimates noise in changes.
        """
        diff = np.diff(data)
        mad = np.median(np.abs(diff - np.median(diff)))
        sigma = mad / 0.6745

        return sigma**2

    def analyze(self, data: np.ndarray) -> NoiseProfile:
        """
        Complete noise analysis of a time series.

        Returns comprehensive NoiseProfile with multiple estimates.
        """
        returns = np.diff(data) / data[:-1] if np.all(data > 0) else np.diff(data)

        # Noise estimation (conservative: take maximum)
        noise_var_1 = self.estimate_from_residuals(data)
        noise_var_2 = self.estimate_mad_robust(data)
        noise_variance = max(noise_var_1, noise_var_2)

        # Total variance
        total_variance = np.var(returns)

        # Signal variance = total - noise
        signal_variance = max(0, total_variance - noise_variance / np.var(data))

        # SNR
        snr = signal_variance / noise_variance if noise_variance > 0 else np.inf
        snr_db = 10 * np.log10(snr) if snr > 0 else -np.inf

        # Autocorrelation (negative = mean-reverting noise)
        if len(returns) > 1:
            ac_lag1 = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        else:
            ac_lag1 = 0.0

        return NoiseProfile(
            noise_variance=noise_variance,
            noise_std=np.sqrt(noise_variance),
            signal_variance=signal_variance,
            snr=snr,
            snr_db=snr_db,
            autocorrelation_lag1=ac_lag1,
            is_dominated_by_noise=(snr < 1)
        )


class SignalToNoiseAnalyzer:
    """
    Analysis of signal quality for trading decisions.

    Key insight: A signal with SNR < 1 is not tradeable.
    Even with SNR > 1, transaction costs may eliminate the edge.
    """

    def __init__(self, transaction_cost_bps: float = 10.0):
        """
        Initialize analyzer.

        Args:
            transaction_cost_bps: Round-trip transaction cost in basis points
        """
        self.transaction_cost = transaction_cost_bps / 10000

    def calculate_required_snr(
        self,
        holding_period: int,
        target_sharpe: float = 1.0
    ) -> float:
        """
        Calculate minimum SNR needed for profitable trading.

        Given transaction costs and target Sharpe, what signal
        quality do we need?
        """
        # After costs, expected return must exceed threshold
        # SNR = (signal/noise)², Sharpe ∝ sqrt(SNR)
        # Required excess return per trade ≈ 2 * transaction_cost
        # (one round trip)

        min_return_per_trade = 2 * self.transaction_cost
        trades_per_year = 252 / holding_period

        required_annual_return = min_return_per_trade * trades_per_year
        required_snr = (target_sharpe / np.sqrt(trades_per_year))**2

        return max(required_snr, 1.0)  # At minimum, SNR > 1

    def assess_tradability(
        self,
        signal_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        holding_period: int = 5
    ) -> dict:
        """
        Assess whether a signal is tradable after costs.

        Args:
            signal_returns: Returns when following signal
            benchmark_returns: Benchmark returns (e.g., buy-and-hold)
            holding_period: Average holding period in days

        Returns:
            Dictionary with tradability assessment
        """
        excess_returns = signal_returns - benchmark_returns

        # Information ratio
        ir = np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) > 0 else 0
        ir_annualized = ir * np.sqrt(252)

        # Estimate signal and noise
        signal_mean = np.mean(excess_returns)
        noise_std = np.std(excess_returns)
        snr = (signal_mean / noise_std)**2 if noise_std > 0 else 0

        # Required SNR
        required_snr = self.calculate_required_snr(holding_period)

        # Net expected return after costs
        trades_per_year = 252 / holding_period
        annual_costs = 2 * self.transaction_cost * trades_per_year
        net_annual_return = signal_mean * 252 - annual_costs

        return {
            "information_ratio": ir_annualized,
            "snr": snr,
            "required_snr": required_snr,
            "snr_sufficient": snr > required_snr,
            "gross_annual_return": signal_mean * 252,
            "transaction_costs": annual_costs,
            "net_annual_return": net_annual_return,
            "is_tradable": net_annual_return > 0 and snr > required_snr,
            "recommendation": self._get_recommendation(snr, required_snr, net_annual_return)
        }

    def _get_recommendation(self, snr: float, required_snr: float, net_return: float) -> str:
        """Generate human-readable recommendation."""
        if net_return <= 0:
            return "NOT TRADABLE: Transaction costs exceed expected returns"
        elif snr < 0.5:
            return "NOT TRADABLE: Signal dominated by noise"
        elif snr < required_snr:
            return "MARGINAL: SNR below threshold, reduce position size significantly"
        elif snr < required_snr * 2:
            return "CAUTIOUS: SNR adequate but not robust, use conservative sizing"
        else:
            return "TRADABLE: Signal quality sufficient for the strategy"


def calculate_optimal_sampling_frequency(
    prices: np.ndarray,
    timestamps: np.ndarray = None
) -> dict:
    """
    Determine optimal data sampling frequency.

    Higher frequency = more data but more noise.
    Lower frequency = less noise but less data.

    There's an optimal balance that maximizes signal extraction.
    """
    if timestamps is None:
        timestamps = np.arange(len(prices))

    estimator = NoiseEstimator()

    results = {}
    sample_intervals = [1, 2, 5, 10, 20, 50]

    for interval in sample_intervals:
        sampled_prices = prices[::interval]
        if len(sampled_prices) < 20:
            continue

        profile = estimator.analyze(sampled_prices)
        results[interval] = {
            "snr": profile.snr,
            "noise_std": profile.noise_std,
            "effective_observations": len(sampled_prices)
        }

    # Find optimal (highest SNR with reasonable sample size)
    if results:
        optimal = max(results.items(), key=lambda x: x[1]["snr"] * np.log(x[1]["effective_observations"]))
        return {
            "optimal_interval": optimal[0],
            "optimal_snr": optimal[1]["snr"],
            "all_results": results
        }

    return {"optimal_interval": 1, "all_results": {}}
