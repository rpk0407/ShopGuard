"""
Signal Processing for Financial Time Series

Separating signal from noise is THE fundamental problem in quantitative trading.

This module implements:
- Fourier analysis (frequency decomposition)
- Wavelet transforms (time-frequency analysis)
- Kalman filtering (adaptive signal extraction)
- Noise estimation (determining what's tradeable vs. random)
"""

from .fourier import FourierAnalyzer, SpectralDensity
from .wavelets import WaveletDenoiser, MultiResolutionAnalysis
from .kalman import KalmanFilter, AdaptiveKalman
from .noise import NoiseEstimator, SignalToNoiseAnalyzer

__all__ = [
    "FourierAnalyzer",
    "SpectralDensity",
    "WaveletDenoiser",
    "MultiResolutionAnalysis",
    "KalmanFilter",
    "AdaptiveKalman",
    "NoiseEstimator",
    "SignalToNoiseAnalyzer",
]
