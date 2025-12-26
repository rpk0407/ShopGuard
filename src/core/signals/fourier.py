"""
Fourier Analysis for Financial Time Series

Fourier transforms decompose a signal into constituent frequencies.
For trading, this helps identify:
1. Cyclical patterns (weekly, monthly, quarterly effects)
2. Noise levels at different frequencies
3. Dominant periodicities that might be exploitable

CRITICAL CAVEAT:
Financial markets are NON-STATIONARY. Fourier analysis assumes stationarity.
Use rolling windows and be skeptical of any "stable" patterns.
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Optional
from scipy import fft
from scipy import signal as scipy_signal


@dataclass
class FrequencyComponent:
    """A frequency component from Fourier decomposition."""
    frequency: float      # Cycles per time unit
    period: float         # Time units per cycle
    amplitude: float      # Strength of this frequency
    phase: float          # Phase offset
    power: float          # Power (amplitude squared)
    significance: float   # Ratio to noise floor


class FourierAnalyzer:
    """
    Fourier analysis toolkit for price and returns data.

    The Discrete Fourier Transform (DFT) decomposes a signal x[n] into:
    X[k] = Σₙ x[n] · exp(-2πi·k·n/N)

    Where:
    - X[k]: Complex coefficient for frequency k
    - |X[k]|: Amplitude at frequency k
    - arg(X[k]): Phase at frequency k
    - |X[k]|²: Power at frequency k
    """

    def __init__(self, sampling_rate: float = 1.0):
        """
        Initialize analyzer.

        Args:
            sampling_rate: Samples per time unit (e.g., 1 for daily data)
        """
        self.sampling_rate = sampling_rate

    def analyze(self, data: np.ndarray, detrend: bool = True) -> List[FrequencyComponent]:
        """
        Perform Fourier analysis on time series.

        Args:
            data: Time series data
            detrend: Whether to remove linear trend first (recommended)

        Returns:
            List of FrequencyComponent objects, sorted by power
        """
        n = len(data)

        # Detrend to remove DC and linear components
        if detrend:
            data = scipy_signal.detrend(data)

        # Apply window function to reduce spectral leakage
        window = np.hanning(n)
        windowed_data = data * window

        # Compute FFT
        fft_result = fft.fft(windowed_data)
        frequencies = fft.fftfreq(n, d=1/self.sampling_rate)

        # Only positive frequencies (real signal is symmetric)
        positive_mask = frequencies > 0
        freqs = frequencies[positive_mask]
        coeffs = fft_result[positive_mask]

        # Compute power spectrum
        power = np.abs(coeffs)**2

        # Estimate noise floor (median power level)
        noise_floor = np.median(power)

        components = []
        for i, (freq, coeff, pwr) in enumerate(zip(freqs, coeffs, power)):
            components.append(FrequencyComponent(
                frequency=freq,
                period=1/freq if freq > 0 else np.inf,
                amplitude=np.abs(coeff) * 2 / n,  # Normalize
                phase=np.angle(coeff),
                power=pwr,
                significance=pwr / noise_floor if noise_floor > 0 else 0
            ))

        # Sort by power (strongest first)
        components.sort(key=lambda x: x.power, reverse=True)

        return components

    def get_dominant_cycles(
        self,
        data: np.ndarray,
        min_significance: float = 3.0,
        min_period: float = 2.0,
        max_period: float = None
    ) -> List[FrequencyComponent]:
        """
        Extract statistically significant cyclical patterns.

        Args:
            data: Time series data
            min_significance: Minimum ratio to noise floor (3.0 = 3x noise)
            min_period: Minimum cycle length to consider
            max_period: Maximum cycle length to consider

        Returns:
            List of significant frequency components
        """
        if max_period is None:
            max_period = len(data) / 2

        components = self.analyze(data)

        significant = [
            c for c in components
            if c.significance >= min_significance
            and c.period >= min_period
            and c.period <= max_period
        ]

        return significant

    def reconstruct_signal(
        self,
        data: np.ndarray,
        keep_components: int = 10
    ) -> np.ndarray:
        """
        Reconstruct signal using only the strongest frequency components.

        This is a form of DENOISING - keeping only the strongest patterns.

        Args:
            data: Original time series
            keep_components: Number of strongest frequencies to keep

        Returns:
            Reconstructed (denoised) signal
        """
        n = len(data)

        # Detrend and save trend for later
        trend = np.polyfit(np.arange(n), data, 1)
        detrended = data - np.polyval(trend, np.arange(n))

        # FFT
        fft_result = fft.fft(detrended)

        # Keep only strongest components
        power = np.abs(fft_result)**2
        threshold_idx = np.argsort(power)[-keep_components*2:]  # *2 for symmetry

        filtered_fft = np.zeros_like(fft_result)
        filtered_fft[threshold_idx] = fft_result[threshold_idx]

        # Inverse FFT
        reconstructed = np.real(fft.ifft(filtered_fft))

        # Add trend back
        reconstructed += np.polyval(trend, np.arange(n))

        return reconstructed


class SpectralDensity:
    """
    Power Spectral Density estimation for understanding signal structure.

    PSD tells us how power is distributed across frequencies.
    For financial data:
    - White noise: flat PSD (random walk)
    - Pink noise (1/f): PSD ~ 1/f (long memory)
    - Brownian motion: PSD ~ 1/f² (integrated white noise)
    """

    def __init__(self, method: str = "welch"):
        """
        Initialize PSD estimator.

        Args:
            method: 'periodogram', 'welch', or 'multitaper'
        """
        self.method = method

    def estimate(
        self,
        data: np.ndarray,
        sampling_rate: float = 1.0,
        nperseg: int = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Estimate power spectral density.

        Args:
            data: Time series data
            sampling_rate: Samples per time unit
            nperseg: Segment length for Welch method

        Returns:
            Tuple of (frequencies, power_spectral_density)
        """
        if nperseg is None:
            nperseg = min(256, len(data) // 4)

        if self.method == "periodogram":
            freqs, psd = scipy_signal.periodogram(
                data, fs=sampling_rate, detrend='linear'
            )
        elif self.method == "welch":
            freqs, psd = scipy_signal.welch(
                data, fs=sampling_rate, nperseg=nperseg, detrend='linear'
            )
        else:
            raise ValueError(f"Unknown method: {self.method}")

        return freqs, psd

    def estimate_noise_exponent(
        self,
        data: np.ndarray,
        sampling_rate: float = 1.0
    ) -> Tuple[float, float]:
        """
        Estimate the noise exponent β where PSD ~ 1/f^β.

        Returns:
            Tuple of (beta, r_squared)

        Interpretation:
        - β ≈ 0: White noise (unpredictable)
        - β ≈ 1: Pink noise (some memory, mean reverting)
        - β ≈ 2: Brownian motion (integrated white noise)
        - β > 2: Strongly persistent (trending)
        """
        freqs, psd = self.estimate(data, sampling_rate)

        # Avoid DC component and very high frequencies
        mask = (freqs > 0.01) & (freqs < sampling_rate / 4)
        log_freqs = np.log10(freqs[mask])
        log_psd = np.log10(psd[mask])

        # Linear regression: log(PSD) = -β·log(f) + const
        coeffs = np.polyfit(log_freqs, log_psd, 1)
        beta = -coeffs[0]

        # R-squared for fit quality
        predicted = np.polyval(coeffs, log_freqs)
        ss_res = np.sum((log_psd - predicted)**2)
        ss_tot = np.sum((log_psd - np.mean(log_psd))**2)
        r_squared = 1 - ss_res / ss_tot

        return beta, r_squared


def detect_seasonality(
    data: np.ndarray,
    expected_periods: List[int] = None,
    significance_threshold: float = 0.05
) -> dict:
    """
    Detect seasonal patterns using Fourier analysis.

    Common trading seasonalities:
    - 5 days (weekly effect)
    - 21 days (monthly effect)
    - 63 days (quarterly effect)
    - 252 days (annual effect)

    Args:
        data: Time series (usually returns or detrended prices)
        expected_periods: List of periods to test
        significance_threshold: p-value threshold for significance

    Returns:
        Dictionary with detected seasonal patterns
    """
    if expected_periods is None:
        expected_periods = [5, 10, 21, 42, 63, 126, 252]

    n = len(data)
    analyzer = FourierAnalyzer(sampling_rate=1.0)
    components = analyzer.analyze(data)

    results = {}
    for period in expected_periods:
        if period > n / 2:
            continue

        # Find component closest to this period
        target_freq = 1 / period
        closest = min(components, key=lambda c: abs(c.frequency - target_freq))

        # Fisher's test for periodic signal
        # Under null (no periodicity), 2*power/noise_var ~ chi-squared(2)
        # This is a simplified significance test
        power_ratio = closest.significance
        p_value = np.exp(-power_ratio)  # Approximate

        results[period] = {
            "detected_period": closest.period,
            "power_ratio": power_ratio,
            "p_value": p_value,
            "significant": p_value < significance_threshold,
            "amplitude": closest.amplitude
        }

    return results
