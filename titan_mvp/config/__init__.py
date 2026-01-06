"""
TQO MVP Configuration Module

Centralized configuration with validation.
"""
from .settings import Settings, get_settings
from .constants import (
    # Entropy thresholds
    ENTROPY_CRYSTAL_THRESHOLD,
    ENTROPY_GAS_THRESHOLD,

    # CVD thresholds
    CVD_DIVERGENCE_MIN_PERSISTENCE,
    CVD_ZSCORE_THRESHOLD,

    # Risk parameters
    DEFAULT_RISK_PER_TRADE,
    MAX_POSITION_PCT,
    ATR_STOP_MULTIPLIER,
    ATR_PROFIT_MULTIPLIER,

    # Trading limits
    MAX_DAILY_LOSS_PCT,
    MAX_WEEKLY_LOSS_PCT,
    MAX_DRAWDOWN_PCT,
    MAX_CONSECUTIVE_LOSSES,
)

__all__ = [
    'Settings',
    'get_settings',
    'ENTROPY_CRYSTAL_THRESHOLD',
    'ENTROPY_GAS_THRESHOLD',
    'CVD_DIVERGENCE_MIN_PERSISTENCE',
    'CVD_ZSCORE_THRESHOLD',
    'DEFAULT_RISK_PER_TRADE',
    'MAX_POSITION_PCT',
    'ATR_STOP_MULTIPLIER',
    'ATR_PROFIT_MULTIPLIER',
    'MAX_DAILY_LOSS_PCT',
    'MAX_WEEKLY_LOSS_PCT',
    'MAX_DRAWDOWN_PCT',
    'MAX_CONSECUTIVE_LOSSES',
]
