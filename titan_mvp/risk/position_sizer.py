"""
Position Sizer

Calculates position size based on:
1. Account risk (% of account to risk per trade)
2. Stop distance (ATR-based)
3. Maximum position limits

Formula:
Position Size = (Account * Risk%) / Stop Distance

With constraints:
- Max position as % of account
- Min position size
- Leverage limits
"""
from dataclasses import dataclass
from typing import Optional
import logging

from ..config.constants import (
    DEFAULT_RISK_PER_TRADE,
    MAX_POSITION_PCT,
    MIN_POSITION_SIZE_USD,
    ATR_STOP_MULTIPLIER,
)
from .atr_calculator import ATRCalculator

logger = logging.getLogger(__name__)


@dataclass
class PositionSize:
    """Calculated position size with details."""
    size_usd: float          # Position size in USD
    size_base: float         # Position size in base currency
    risk_amount: float       # Dollar amount at risk
    stop_distance: float     # Stop distance in price
    stop_price: float        # Absolute stop price
    target_distance: float   # Target distance in price
    target_price: float      # Absolute target price
    leverage_used: float     # Effective leverage
    is_constrained: bool     # True if size was reduced by limits
    constraint_reason: str   # Why size was constrained

    def to_dict(self) -> dict:
        return {
            'size_usd': round(self.size_usd, 2),
            'size_base': round(self.size_base, 6),
            'risk_amount': round(self.risk_amount, 2),
            'stop_distance': round(self.stop_distance, 4),
            'stop_price': round(self.stop_price, 2),
            'target_distance': round(self.target_distance, 4),
            'target_price': round(self.target_price, 2),
            'leverage_used': round(self.leverage_used, 2),
            'is_constrained': self.is_constrained,
            'constraint_reason': self.constraint_reason,
        }


class PositionSizer:
    """
    ATR-based position sizer.

    Calculates optimal position size to risk a fixed percentage
    of account on each trade, with safety limits.

    Usage:
        sizer = PositionSizer(account_size=10000)
        size = sizer.calculate(
            entry_price=50000,
            atr=1000,
            direction='long'
        )
    """

    def __init__(
        self,
        account_size: float,
        risk_per_trade: float = DEFAULT_RISK_PER_TRADE,
        max_position_pct: float = MAX_POSITION_PCT,
        min_position_usd: float = MIN_POSITION_SIZE_USD,
        max_leverage: float = 5.0,
        atr_stop_multiplier: float = ATR_STOP_MULTIPLIER,
        atr_target_multiplier: float = 3.0
    ):
        """
        Initialize position sizer.

        Args:
            account_size: Account size in USD
            risk_per_trade: Risk per trade as decimal (0.02 = 2%)
            max_position_pct: Max position as % of account
            min_position_usd: Minimum position size
            max_leverage: Maximum leverage allowed
            atr_stop_multiplier: ATR multiplier for stop loss
            atr_target_multiplier: ATR multiplier for take profit
        """
        self.account_size = account_size
        self.risk_per_trade = risk_per_trade
        self.max_position_pct = max_position_pct
        self.min_position_usd = min_position_usd
        self.max_leverage = max_leverage
        self.atr_stop_multiplier = atr_stop_multiplier
        self.atr_target_multiplier = atr_target_multiplier

        logger.info(
            "Position Sizer initialized: account=$%.2f, risk=%.1f%%, max_pos=%.0f%%",
            account_size, risk_per_trade * 100, max_position_pct * 100
        )

    def calculate(
        self,
        entry_price: float,
        atr: float,
        direction: str,  # 'long' or 'short'
        confidence_multiplier: float = 1.0
    ) -> PositionSize:
        """
        Calculate position size.

        Args:
            entry_price: Entry price
            atr: Current ATR value
            direction: 'long' or 'short'
            confidence_multiplier: Scale size by confidence (0.5-1.5)

        Returns:
            PositionSize with all details
        """
        # Calculate stop distance
        stop_distance = atr * self.atr_stop_multiplier
        target_distance = atr * self.atr_target_multiplier

        # Calculate stop and target prices
        if direction == 'long':
            stop_price = entry_price - stop_distance
            target_price = entry_price + target_distance
        else:
            stop_price = entry_price + stop_distance
            target_price = entry_price - target_distance

        # Calculate risk amount
        risk_amount = self.account_size * self.risk_per_trade * confidence_multiplier

        # Calculate raw position size
        # Position Size = Risk Amount / Stop Distance (as %)
        stop_pct = stop_distance / entry_price
        raw_size_usd = risk_amount / stop_pct

        # Apply constraints
        is_constrained = False
        constraint_reason = ""

        # Constraint 1: Maximum position size
        max_size = self.account_size * self.max_position_pct * self.max_leverage
        if raw_size_usd > max_size:
            raw_size_usd = max_size
            is_constrained = True
            constraint_reason = f"Max position limit (${max_size:.0f})"

        # Constraint 2: Minimum position size
        if raw_size_usd < self.min_position_usd:
            raw_size_usd = self.min_position_usd
            is_constrained = True
            constraint_reason = f"Min position limit (${self.min_position_usd:.0f})"

        # Constraint 3: Max leverage
        leverage_used = raw_size_usd / self.account_size
        if leverage_used > self.max_leverage:
            raw_size_usd = self.account_size * self.max_leverage
            leverage_used = self.max_leverage
            is_constrained = True
            constraint_reason = f"Max leverage limit ({self.max_leverage}x)"

        # Calculate size in base currency
        size_base = raw_size_usd / entry_price

        # Recalculate actual risk (might differ due to constraints)
        actual_risk = raw_size_usd * stop_pct

        return PositionSize(
            size_usd=raw_size_usd,
            size_base=size_base,
            risk_amount=actual_risk,
            stop_distance=stop_distance,
            stop_price=stop_price,
            target_distance=target_distance,
            target_price=target_price,
            leverage_used=leverage_used,
            is_constrained=is_constrained,
            constraint_reason=constraint_reason
        )

    def update_account_size(self, new_size: float) -> None:
        """Update account size (after P&L)."""
        self.account_size = new_size
        logger.info("Account size updated: $%.2f", new_size)

    def adjust_for_correlation(
        self,
        size: PositionSize,
        num_correlated_positions: int,
        correlation: float = 0.7
    ) -> PositionSize:
        """
        Adjust position size for correlated positions.

        When holding multiple correlated positions, reduce size
        to maintain overall portfolio risk.

        Args:
            size: Original position size
            num_correlated_positions: Number of existing correlated positions
            correlation: Average correlation

        Returns:
            Adjusted PositionSize
        """
        if num_correlated_positions == 0:
            return size

        # Reduce size by sqrt(n) for n correlated positions
        # This approximates portfolio variance adjustment
        adjustment = 1 / (num_correlated_positions + 1) ** 0.5

        # Apply adjustment
        adjusted_size_usd = size.size_usd * adjustment
        adjusted_size_base = size.size_base * adjustment

        return PositionSize(
            size_usd=adjusted_size_usd,
            size_base=adjusted_size_base,
            risk_amount=size.risk_amount * adjustment,
            stop_distance=size.stop_distance,
            stop_price=size.stop_price,
            target_distance=size.target_distance,
            target_price=size.target_price,
            leverage_used=size.leverage_used * adjustment,
            is_constrained=True,
            constraint_reason=f"Correlation adjustment ({num_correlated_positions} positions)"
        )
