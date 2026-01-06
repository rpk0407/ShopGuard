"""
Backtest Engine

Event-driven backtesting with:
- Realistic execution modeling
- Cost modeling (fees, slippage, funding)
- Walk-forward validation support
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable
from datetime import datetime
import logging

from ..config.constants import (
    MAKER_FEE_BPS,
    TAKER_FEE_BPS,
    FIXED_SLIPPAGE_BPS,
)
from ..data.candles import Candle
from ..signals.signal_combiner import SignalCombiner, CombinedSignal, TradeDirection
from ..risk.risk_manager import RiskManager
from ..risk.atr_calculator import ATRCalculator
from .metrics import BacktestMetrics, TradeResult, calculate_metrics

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Open position."""
    entry_price: float
    entry_time: int
    size: float
    direction: str  # 'long' or 'short'
    stop_price: float
    target_price: float
    entry_candle_idx: int


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    initial_capital: float = 10000.0
    maker_fee_bps: float = MAKER_FEE_BPS
    taker_fee_bps: float = TAKER_FEE_BPS
    slippage_bps: float = FIXED_SLIPPAGE_BPS
    use_limit_orders: bool = True  # True = maker fees, False = taker
    include_funding: bool = True
    funding_rate_bps: float = 1.0  # Per 8 hours


@dataclass
class BacktestResult:
    """Complete backtest result."""
    metrics: BacktestMetrics
    trades: List[TradeResult]
    equity_curve: List[float]
    config: BacktestConfig
    start_time: datetime
    end_time: datetime
    candles_processed: int

    def to_dict(self) -> dict:
        return {
            'metrics': self.metrics.to_dict(),
            'num_trades': len(self.trades),
            'candles_processed': self.candles_processed,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'config': {
                'initial_capital': self.config.initial_capital,
                'maker_fee_bps': self.config.maker_fee_bps,
                'slippage_bps': self.config.slippage_bps,
            }
        }


class BacktestEngine:
    """
    Event-driven backtesting engine.

    Simulates trading with realistic execution:
    1. Processes candles sequentially
    2. Generates signals from SignalCombiner
    3. Executes trades with slippage/fees
    4. Tracks P&L and positions
    5. Calculates metrics

    Usage:
        engine = BacktestEngine(config)
        result = engine.run(candles)
        print(result.metrics.summary())
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        signal_combiner: Optional[SignalCombiner] = None,
        risk_manager: Optional[RiskManager] = None
    ):
        """
        Initialize backtest engine.

        Args:
            config: Backtest configuration
            signal_combiner: Signal generator
            risk_manager: Risk manager
        """
        self.config = config or BacktestConfig()
        self.signal_combiner = signal_combiner or SignalCombiner()
        self.risk_manager = risk_manager or RiskManager(
            initial_capital=self.config.initial_capital
        )

        # State
        self._position: Optional[Position] = None
        self._trades: List[TradeResult] = []
        self._equity_curve: List[float] = []
        self._current_equity = self.config.initial_capital

        # Tracking
        self._candles_processed = 0
        self._signals_generated = 0

        logger.info(
            "Backtest Engine initialized: capital=$%.2f, fees=%.1fbps, slippage=%.1fbps",
            self.config.initial_capital, self.config.maker_fee_bps, self.config.slippage_bps
        )

    def run(
        self,
        candles: List[Candle],
        warmup_period: int = 50,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> BacktestResult:
        """
        Run backtest on historical candles.

        Args:
            candles: List of candles (oldest first)
            warmup_period: Candles to skip for indicator warmup
            progress_callback: Optional callback(current, total)

        Returns:
            BacktestResult with metrics and trade history
        """
        start_time = datetime.now()
        logger.info("Starting backtest: %d candles, warmup=%d", len(candles), warmup_period)

        # Reset state
        self._reset()

        # Process candles
        for i, candle in enumerate(candles):
            # Skip warmup period
            if i < warmup_period:
                # Still update ATR during warmup
                self.risk_manager.atr_calculator.update(candle)
                continue

            # Process candle
            self._process_candle(candle, candles[max(0, i-100):i+1], i)

            # Progress callback
            if progress_callback and i % 100 == 0:
                progress_callback(i, len(candles))

        # Close any open position at end
        if self._position:
            self._close_position(candles[-1], "backtest_end")

        end_time = datetime.now()

        # Calculate metrics
        metrics = calculate_metrics(
            trades=self._trades,
            initial_capital=self.config.initial_capital
        )

        logger.info(
            "Backtest complete: %d trades, Sharpe=%.2f, Total PnL=$%.2f",
            len(self._trades), metrics.sharpe_ratio, metrics.total_pnl
        )

        return BacktestResult(
            metrics=metrics,
            trades=self._trades,
            equity_curve=self._equity_curve,
            config=self.config,
            start_time=start_time,
            end_time=end_time,
            candles_processed=self._candles_processed
        )

    def _process_candle(
        self,
        candle: Candle,
        history: List[Candle],
        candle_idx: int
    ) -> None:
        """Process a single candle."""
        self._candles_processed += 1

        # Update ATR
        self.risk_manager.atr_calculator.update(candle)

        # Check if we have a position
        if self._position:
            # Check stop/target
            self._check_exit(candle)
        else:
            # Generate signal
            signal = self.signal_combiner.analyze(history)
            self._signals_generated += 1

            # Execute if valid
            if signal.should_trade:
                self._open_position(candle, signal, candle_idx)

        # Update equity curve
        self._update_equity(candle)

    def _open_position(
        self,
        candle: Candle,
        signal: CombinedSignal,
        candle_idx: int
    ) -> None:
        """Open a new position."""
        # Check risk manager
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.debug("Trade blocked by risk manager: %s", reason)
            return

        # Calculate position size
        direction = 'long' if signal.direction == TradeDirection.LONG else 'short'
        position_size = self.risk_manager.calculate_position(
            entry_price=candle.close,
            direction=direction,
            confidence=signal.confidence
        )

        if position_size is None:
            return

        # Apply slippage to entry
        slippage = candle.close * (self.config.slippage_bps / 10000)
        if direction == 'long':
            entry_price = candle.close + slippage
        else:
            entry_price = candle.close - slippage

        # Create position
        self._position = Position(
            entry_price=entry_price,
            entry_time=candle.timestamp,
            size=position_size.size_usd,
            direction=direction,
            stop_price=position_size.stop_price,
            target_price=position_size.target_price,
            entry_candle_idx=candle_idx
        )

        # Deduct entry fee
        fee = self._calculate_fee(position_size.size_usd)
        self._current_equity -= fee

        logger.debug(
            "Opened %s position: entry=$%.2f, size=$%.2f, stop=$%.2f, target=$%.2f",
            direction, entry_price, position_size.size_usd,
            position_size.stop_price, position_size.target_price
        )

    def _check_exit(self, candle: Candle) -> None:
        """Check if position should be closed."""
        if not self._position:
            return

        exit_price = None
        exit_reason = None

        if self._position.direction == 'long':
            # Check stop loss
            if candle.low <= self._position.stop_price:
                exit_price = self._position.stop_price
                exit_reason = "stop_loss"
            # Check take profit
            elif candle.high >= self._position.target_price:
                exit_price = self._position.target_price
                exit_reason = "take_profit"

        else:  # short
            # Check stop loss
            if candle.high >= self._position.stop_price:
                exit_price = self._position.stop_price
                exit_reason = "stop_loss"
            # Check take profit
            elif candle.low <= self._position.target_price:
                exit_price = self._position.target_price
                exit_reason = "take_profit"

        if exit_price:
            self._close_position(candle, exit_reason, exit_price)

    def _close_position(
        self,
        candle: Candle,
        reason: str,
        exit_price: Optional[float] = None
    ) -> None:
        """Close the current position."""
        if not self._position:
            return

        # Use candle close if no specific exit price
        if exit_price is None:
            exit_price = candle.close

        # Apply slippage to exit
        slippage = exit_price * (self.config.slippage_bps / 10000)
        if self._position.direction == 'long':
            exit_price = exit_price - slippage
        else:
            exit_price = exit_price + slippage

        # Calculate P&L
        if self._position.direction == 'long':
            pnl = (exit_price - self._position.entry_price) / self._position.entry_price
        else:
            pnl = (self._position.entry_price - exit_price) / self._position.entry_price

        pnl_usd = pnl * self._position.size

        # Deduct exit fee
        fee = self._calculate_fee(self._position.size)
        pnl_usd -= fee

        # Update equity
        self._current_equity += pnl_usd

        # Record trade
        trade = TradeResult(
            entry_price=self._position.entry_price,
            exit_price=exit_price,
            size=self._position.size,
            direction=self._position.direction,
            pnl=pnl_usd,
            pnl_pct=pnl,
            duration=self._candles_processed - self._position.entry_candle_idx,
            entry_time=self._position.entry_time,
            exit_time=candle.timestamp
        )
        self._trades.append(trade)

        # Update risk manager
        self.risk_manager.record_trade(pnl_usd)

        logger.debug(
            "Closed %s position: exit=$%.2f, PnL=$%.2f (%.2f%%), reason=%s",
            self._position.direction, exit_price, pnl_usd, pnl * 100, reason
        )

        # Clear position
        self._position = None

    def _calculate_fee(self, size: float) -> float:
        """Calculate trading fee."""
        fee_bps = self.config.maker_fee_bps if self.config.use_limit_orders else self.config.taker_fee_bps
        return size * (fee_bps / 10000)

    def _update_equity(self, candle: Candle) -> None:
        """Update equity curve with unrealized P&L."""
        equity = self._current_equity

        # Add unrealized P&L if in position
        if self._position:
            if self._position.direction == 'long':
                unrealized = (candle.close - self._position.entry_price) / self._position.entry_price
            else:
                unrealized = (self._position.entry_price - candle.close) / self._position.entry_price
            equity += unrealized * self._position.size

        self._equity_curve.append(equity)

    def _reset(self) -> None:
        """Reset engine state for new backtest."""
        self._position = None
        self._trades = []
        self._equity_curve = [self.config.initial_capital]
        self._current_equity = self.config.initial_capital
        self._candles_processed = 0
        self._signals_generated = 0

        # Reset components
        self.signal_combiner.reset()
        self.risk_manager.reset()
