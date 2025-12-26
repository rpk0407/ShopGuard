"""
Wavelet Analysis for Financial Time Series

Wavelets overcome a key limitation of Fourier analysis:
Fourier tells you WHAT frequencies exist but not WHEN they occur.
Wavelets provide TIME-FREQUENCY localization.

For trading, this is crucial because:
1. Volatility regimes change over time
2. Momentum can appear and disappear
3. Mean-reversion strength varies with market conditions
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Optional
from enum import Enum


class WaveletFamily(Enum):
    """Wavelet families for different use cases."""
    HAAR = "haar"              # Simple, good for jump detection
    DAUBECHIES_4 = "db4"       # Good general purpose
    DAUBECHIES_8 = "db8"       # Smoother reconstruction
    SYMLET_8 = "sym8"          # Near-symmetric, good for denoising
    COIFLET_4 = "coif4"        # Good for signal approximation


@dataclass
class WaveletCoefficients:
    """Result of wavelet decomposition."""
    approximation: np.ndarray           # Low-frequency (trend) component
    details: List[np.ndarray]           # High-frequency (noise/signal) at each level
    levels: int                         # Number of decomposition levels


class WaveletDenoiser:
    """
    Wavelet-based denoising for financial time series.

    The key insight: Price data = Signal + Noise
    - Signal: Information about fundamental value changes
    - Noise: Random fluctuations, microstructure noise, irrelevant movements

    Wavelet denoising works by:
    1. Decompose signal into wavelet coefficients
    2. Threshold small coefficients (likely noise)
    3. Reconstruct from remaining coefficients

    WHY WAVELETS BEAT MOVING AVERAGES:
    - Moving averages introduce lag
    - Wavelets are more adaptive to local structure
    - Better edge preservation (trend changes)
    """

    def __init__(
        self,
        wavelet: WaveletFamily = WaveletFamily.SYMLET_8,
        levels: int = 4
    ):
        """
        Initialize denoiser.

        Args:
            wavelet: Wavelet family to use
            levels: Decomposition levels (more levels = more smoothing)
        """
        self.wavelet = wavelet
        self.levels = levels

    def decompose(self, data: np.ndarray) -> WaveletCoefficients:
        """
        Perform multi-level wavelet decomposition.

        Uses the Discrete Wavelet Transform (DWT):
        - Each level splits signal into approximation (low-pass) and detail (high-pass)
        - Approximation captures trend, details capture fluctuations
        """
        # Simple implementation using Haar wavelets for clarity
        # In production, use PyWavelets (pywt) library
        coeffs = self._haar_decompose(data, self.levels)
        return coeffs

    def _haar_decompose(self, data: np.ndarray, levels: int) -> WaveletCoefficients:
        """
        Haar wavelet decomposition (simplest wavelet).

        The Haar wavelet:
        - Low-pass: (x[2n] + x[2n+1]) / sqrt(2)  [averaging]
        - High-pass: (x[2n] - x[2n+1]) / sqrt(2)  [differencing]
        """
        details = []
        current = data.copy()
        sqrt2 = np.sqrt(2)

        for level in range(levels):
            n = len(current)
            if n < 2:
                break

            # Ensure even length
            if n % 2 != 0:
                current = np.append(current, current[-1])
                n += 1

            # Decompose
            approx = (current[::2] + current[1::2]) / sqrt2
            detail = (current[::2] - current[1::2]) / sqrt2

            details.append(detail)
            current = approx

        return WaveletCoefficients(
            approximation=current,
            details=details[::-1],  # Reverse so index 0 is coarsest
            levels=len(details)
        )

    def denoise(
        self,
        data: np.ndarray,
        threshold_type: str = "soft",
        threshold_rule: str = "universal"
    ) -> np.ndarray:
        """
        Denoise time series using wavelet thresholding.

        Args:
            data: Noisy time series
            threshold_type: 'soft' (shrinkage) or 'hard' (zeroing)
            threshold_rule: 'universal', 'sure', or 'bayes'

        Returns:
            Denoised time series
        """
        coeffs = self.decompose(data)

        # Calculate threshold based on noise estimate
        if threshold_rule == "universal":
            # Universal threshold (Donoho & Johnstone)
            # λ = σ · sqrt(2 · log(n))
            # Estimate σ from finest detail coefficients (MAD estimator)
            finest_detail = coeffs.details[-1] if coeffs.details else np.array([0])
            sigma = np.median(np.abs(finest_detail)) / 0.6745  # MAD to std
            n = len(data)
            threshold = sigma * np.sqrt(2 * np.log(n))
        else:
            # Simple percentile-based threshold
            all_details = np.concatenate(coeffs.details) if coeffs.details else np.array([0])
            threshold = np.percentile(np.abs(all_details), 90)

        # Apply thresholding to detail coefficients
        thresholded_details = []
        for detail in coeffs.details:
            if threshold_type == "soft":
                # Soft thresholding: shrink towards zero
                thresholded = np.sign(detail) * np.maximum(np.abs(detail) - threshold, 0)
            else:
                # Hard thresholding: zero out small coefficients
                thresholded = detail * (np.abs(detail) > threshold)
            thresholded_details.append(thresholded)

        # Reconstruct
        denoised = self._haar_reconstruct(coeffs.approximation, thresholded_details)

        # Match original length
        return denoised[:len(data)]

    def _haar_reconstruct(
        self,
        approximation: np.ndarray,
        details: List[np.ndarray]
    ) -> np.ndarray:
        """Reconstruct signal from Haar wavelet coefficients."""
        sqrt2 = np.sqrt(2)
        current = approximation

        for detail in details:  # Already in coarsest-to-finest order
            n = len(current)
            # Upsample and add detail
            reconstructed = np.zeros(2 * n)
            reconstructed[::2] = (current + detail) / sqrt2
            reconstructed[1::2] = (current - detail) / sqrt2
            current = reconstructed

        return current


class MultiResolutionAnalysis:
    """
    Multi-Resolution Analysis for extracting trading signals.

    The idea: Different time scales contain different information.
    - Short-term (hours/days): Noise, microstructure, noise traders
    - Medium-term (weeks): Momentum, sentiment cycles
    - Long-term (months): Fundamental value changes

    By separating these scales, we can:
    1. Trade the appropriate time scale for our strategy
    2. Filter out noise that's irrelevant to our horizon
    3. Detect regime changes at different scales
    """

    def __init__(self, max_levels: int = 6):
        """
        Initialize MRA.

        Args:
            max_levels: Maximum decomposition levels
                       Level 1: ~2 periods (daily data = 2 days)
                       Level 2: ~4 periods
                       Level 3: ~8 periods
                       etc.
        """
        self.max_levels = max_levels

    def decompose(self, data: np.ndarray) -> dict:
        """
        Perform multi-resolution decomposition.

        Returns dict with components at each scale plus trend.
        """
        denoiser = WaveletDenoiser(levels=self.max_levels)
        coeffs = denoiser.decompose(data)

        result = {
            "trend": coeffs.approximation,
            "scales": {}
        }

        for i, detail in enumerate(coeffs.details):
            period = 2 ** (self.max_levels - i)
            result["scales"][f"scale_{period}"] = detail

        return result

    def extract_momentum(
        self,
        data: np.ndarray,
        momentum_scales: List[int] = None
    ) -> np.ndarray:
        """
        Extract momentum signal by isolating relevant scales.

        Args:
            data: Price or returns data
            momentum_scales: Scales to include in momentum signal
                           (e.g., [8, 16, 32] for ~1-6 week momentum)

        Returns:
            Momentum component of the signal
        """
        if momentum_scales is None:
            momentum_scales = [8, 16, 32]  # ~1-6 weeks for daily data

        decomposition = self.decompose(data)

        momentum = np.zeros(len(data))
        for scale_name, coeffs in decomposition["scales"].items():
            scale = int(scale_name.split("_")[1])
            if scale in momentum_scales:
                # Upsample to original resolution
                upsampled = np.repeat(coeffs, len(data) // len(coeffs) + 1)[:len(data)]
                momentum += upsampled

        return momentum

    def extract_mean_reversion(
        self,
        data: np.ndarray,
        mean_revert_scales: List[int] = None
    ) -> np.ndarray:
        """
        Extract mean-reversion signal from short-term scales.

        Short-term fluctuations often mean-revert as noise corrects.

        Args:
            data: Price data
            mean_revert_scales: Scales for mean-reversion (default: 2, 4)

        Returns:
            Mean-reversion component
        """
        if mean_revert_scales is None:
            mean_revert_scales = [2, 4]  # ~2-4 day fluctuations

        decomposition = self.decompose(data)

        mr_signal = np.zeros(len(data))
        for scale_name, coeffs in decomposition["scales"].items():
            scale = int(scale_name.split("_")[1])
            if scale in mean_revert_scales:
                upsampled = np.repeat(coeffs, len(data) // len(coeffs) + 1)[:len(data)]
                mr_signal += upsampled

        return mr_signal

    def detect_regime_change(
        self,
        data: np.ndarray,
        window: int = 50
    ) -> np.ndarray:
        """
        Detect regime changes using wavelet variance.

        Regime changes often appear as sudden increases in
        wavelet coefficient variance at multiple scales.

        Returns:
            Array of regime change scores (higher = more likely change)
        """
        decomposition = self.decompose(data)

        # Track variance of each scale over rolling windows
        n = len(data)
        regime_scores = np.zeros(n)

        for scale_name, coeffs in decomposition["scales"].items():
            # Upsample coefficients
            upsampled = np.repeat(coeffs, n // len(coeffs) + 1)[:n]

            # Rolling variance
            for i in range(window, n):
                local_var = np.var(upsampled[i-window:i])
                global_var = np.var(upsampled[:i])
                if global_var > 0:
                    regime_scores[i] += local_var / global_var

        # Normalize
        regime_scores = regime_scores / len(decomposition["scales"])

        return regime_scores
