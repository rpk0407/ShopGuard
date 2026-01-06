"""
TQO MVP Constants

All magic numbers in one place. Validated at import time.
Based on quantitative research and industry standards.

IMPORTANT: These are starting points. Must be validated via backtest
before production use.
"""

# =============================================================================
# ENTROPY FILTER CONSTANTS (Physics-Cortex)
# =============================================================================

# Shannon Entropy thresholds (normalized 0-1)
# Based on: Information theory + empirical crypto analysis
ENTROPY_CRYSTAL_THRESHOLD = 0.4      # Below = ordered, tradeable ("Crystal")
ENTROPY_LIQUID_THRESHOLD = 0.7       # Below = normal conditions
ENTROPY_GAS_THRESHOLD = 0.85         # Above = chaos, halt trading ("Gas")

# Entropy calculation parameters
ENTROPY_LOOKBACK_TICKS = 150         # Ticks for entropy calculation
ENTROPY_NUM_BINS = 20                # Histogram bins (Sturges' rule)
ENTROPY_MIN_SAMPLES = 50             # Minimum samples before calculating

# Adaptive threshold parameters (percentile-based)
ENTROPY_ADAPTIVE_LOOKBACK = 1000     # Ticks for adaptive threshold
ENTROPY_CRYSTAL_PERCENTILE = 25      # Bottom 25% = Crystal regime
ENTROPY_GAS_PERCENTILE = 90          # Top 10% = Gas regime


# =============================================================================
# CVD ENGINE CONSTANTS (Micro-Cortex)
# =============================================================================

# Divergence detection
CVD_LOOKBACK_CANDLES = 20            # Candles to check for divergence
CVD_DIVERGENCE_MIN_PERSISTENCE = 3   # Minimum candles divergence must persist
CVD_ZSCORE_THRESHOLD = 1.5           # Z-score for significant CVD move

# CVD calculation parameters
CVD_SMOOTHING_PERIOD = 5             # EMA smoothing for noise reduction
CVD_VOLUME_THRESHOLD = 0.0           # Minimum volume to include tick

# Divergence types
BULLISH_DIVERGENCE_MIN_DEPTH = 0.02  # Price must drop 2% for bullish div
BEARISH_DIVERGENCE_MIN_HEIGHT = 0.02 # Price must rise 2% for bearish div


# =============================================================================
# HURST EXPONENT CONSTANTS (Secondary Filter)
# =============================================================================

HURST_LOOKBACK_TICKS = 200           # Ticks for Hurst calculation
HURST_TRENDING_THRESHOLD = 0.55      # Above = trending
HURST_MEAN_REVERTING_THRESHOLD = 0.45  # Below = mean-reverting
HURST_MIN_SAMPLES = 100              # Minimum samples


# =============================================================================
# ATR / RISK CONSTANTS
# =============================================================================

# ATR calculation
ATR_PERIOD = 14                      # Standard ATR period
ATR_SMOOTHING = 'wilder'             # 'wilder' (original) or 'ema'

# Position sizing (ATR-based)
DEFAULT_RISK_PER_TRADE = 0.02        # 2% risk per trade
MAX_POSITION_PCT = 0.25              # Max 25% of account in single position
MIN_POSITION_SIZE_USD = 100          # Minimum position size

# Stop loss / Take profit
ATR_STOP_MULTIPLIER = 1.5            # Stop = 1.5 * ATR
ATR_PROFIT_MULTIPLIER = 3.0          # TP = 3.0 * ATR (2:1 R:R)
TRAILING_STOP_ACTIVATION = 1.0       # Activate trailing at 1 * ATR profit
TRAILING_STOP_DISTANCE = 1.0         # Trail at 1 * ATR


# =============================================================================
# RISK MANAGEMENT LIMITS
# =============================================================================

# Loss limits
MAX_DAILY_LOSS_PCT = 0.05            # -5% daily = halt
MAX_WEEKLY_LOSS_PCT = 0.10           # -10% weekly = reduce size 50%
MAX_DRAWDOWN_PCT = 0.20              # -20% = full stop

# Trading limits
MAX_CONSECUTIVE_LOSSES = 5           # 5 losses = 1 hour pause
MAX_TRADES_PER_DAY = 10              # Prevent overtrading
MIN_TIME_BETWEEN_TRADES = 300        # 5 minutes minimum

# Correlation limits
MAX_CORRELATED_POSITIONS = 3         # Max positions in correlated assets
CORRELATION_THRESHOLD = 0.7          # Assets with corr > 0.7 are "correlated"


# =============================================================================
# EXECUTION CONSTANTS
# =============================================================================

# Order parameters
DEFAULT_ORDER_TYPE = 'limit'         # 'limit' or 'market'
LIMIT_ORDER_OFFSET_BPS = 5           # 5 bps from mid for limit orders
ORDER_TIMEOUT_SECONDS = 30           # Cancel unfilled after 30s
MAX_SLIPPAGE_BPS = 20                # Max acceptable slippage

# Retry logic
MAX_ORDER_RETRIES = 3
RETRY_DELAY_BASE = 1.0               # Exponential backoff base
RETRY_DELAY_MAX = 10.0               # Max retry delay


# =============================================================================
# BACKTEST CONSTANTS
# =============================================================================

# Cost modeling
MAKER_FEE_BPS = 2                    # 0.02% maker fee
TAKER_FEE_BPS = 5                    # 0.05% taker fee
SLIPPAGE_MODEL = 'fixed'             # 'fixed', 'volume_based', 'spread_based'
FIXED_SLIPPAGE_BPS = 5               # 5 bps fixed slippage

# Funding rates (8-hour)
AVG_FUNDING_RATE_BPS = 1             # Average 0.01% per 8 hours
FUNDING_RATE_VOLATILITY = 2          # Can swing to 0.02%

# Validation thresholds
MIN_BACKTEST_TRADES = 100            # Minimum trades for valid backtest
MIN_SHARPE_RATIO = 1.0               # Minimum Sharpe to proceed
MIN_WIN_RATE = 0.40                  # Minimum win rate
MAX_ACCEPTABLE_DRAWDOWN = 0.25       # 25% max DD in backtest


# =============================================================================
# SIGNAL COMBINATION LOGIC
# =============================================================================

# Required confirmations for trade
REQUIRE_CVD_SIGNAL = True            # CVD divergence required?
REQUIRE_ENTROPY_FILTER = True        # Low entropy required?
REQUIRE_HURST_FILTER = False         # Hurst confirmation required?

# Signal weights (if using weighted combination)
CVD_SIGNAL_WEIGHT = 0.6
ENTROPY_SIGNAL_WEIGHT = 0.3
HURST_SIGNAL_WEIGHT = 0.1

# Confidence thresholds
MIN_SIGNAL_CONFIDENCE = 0.6          # Minimum combined confidence
HIGH_CONFIDENCE_THRESHOLD = 0.8      # High confidence = full size


# =============================================================================
# VALIDATION
# =============================================================================

def validate_constants():
    """Validate all constants at import time."""
    # Entropy
    assert 0 < ENTROPY_CRYSTAL_THRESHOLD < ENTROPY_LIQUID_THRESHOLD < ENTROPY_GAS_THRESHOLD < 1
    assert ENTROPY_LOOKBACK_TICKS >= ENTROPY_MIN_SAMPLES
    assert ENTROPY_NUM_BINS >= 5

    # CVD
    assert CVD_DIVERGENCE_MIN_PERSISTENCE >= 1
    assert CVD_ZSCORE_THRESHOLD > 0

    # Risk
    assert 0 < DEFAULT_RISK_PER_TRADE <= 0.05  # Max 5% per trade
    assert 0 < MAX_POSITION_PCT <= 0.5         # Max 50% in single position
    assert ATR_PROFIT_MULTIPLIER > ATR_STOP_MULTIPLIER  # TP > SL

    # Limits
    assert MAX_DAILY_LOSS_PCT < MAX_WEEKLY_LOSS_PCT < MAX_DRAWDOWN_PCT
    assert MIN_SHARPE_RATIO > 0

    # Weights
    if not (REQUIRE_CVD_SIGNAL and REQUIRE_ENTROPY_FILTER):
        # If using weights, they should sum to 1
        total_weight = CVD_SIGNAL_WEIGHT + ENTROPY_SIGNAL_WEIGHT + HURST_SIGNAL_WEIGHT
        assert 0.99 <= total_weight <= 1.01, f"Weights sum to {total_weight}, not 1"


# Run validation at import
validate_constants()
