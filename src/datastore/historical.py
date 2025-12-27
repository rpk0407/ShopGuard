"""
Historical Data Loader

Fetch and manage historical market data:
- Load from CSV files
- Generate synthetic data for testing
- Calculate technical indicators
- Resample to different timeframes
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import os


@dataclass
class HistoricalBar:
    """Single OHLCV bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


@dataclass
class HistoricalData:
    """Historical data for a symbol."""
    symbol: str
    bars: List[HistoricalBar]
    timeframe: str = "1d"

    def __len__(self) -> int:
        return len(self.bars)

    @property
    def timestamps(self) -> np.ndarray:
        return np.array([b.timestamp for b in self.bars])

    @property
    def opens(self) -> np.ndarray:
        return np.array([b.open for b in self.bars])

    @property
    def highs(self) -> np.ndarray:
        return np.array([b.high for b in self.bars])

    @property
    def lows(self) -> np.ndarray:
        return np.array([b.low for b in self.bars])

    @property
    def closes(self) -> np.ndarray:
        return np.array([b.close for b in self.bars])

    @property
    def volumes(self) -> np.ndarray:
        return np.array([b.volume for b in self.bars])

    @property
    def returns(self) -> np.ndarray:
        closes = self.closes
        return np.diff(closes) / closes[:-1]

    @property
    def log_returns(self) -> np.ndarray:
        return np.diff(np.log(self.closes))


class HistoricalDataLoader:
    """
    Load and manage historical market data.

    Supports:
    - CSV file loading
    - Synthetic data generation
    - Multiple symbols
    - Different timeframes
    """

    def __init__(self, data_dir: str = None):
        """
        Initialize loader.

        Args:
            data_dir: Directory for CSV files
        """
        self.data_dir = data_dir or os.path.join(os.getcwd(), 'data')
        self._cache: Dict[str, HistoricalData] = {}

    def load_csv(
        self,
        filepath: str,
        symbol: str,
        date_column: str = 'Date',
        date_format: str = '%Y-%m-%d'
    ) -> HistoricalData:
        """
        Load data from a CSV file.

        Expected columns: Date, Open, High, Low, Close, Volume
        """
        import csv

        bars = []

        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    bar = HistoricalBar(
                        timestamp=datetime.strptime(row[date_column], date_format),
                        open=float(row.get('Open', row.get('open', 0))),
                        high=float(row.get('High', row.get('high', 0))),
                        low=float(row.get('Low', row.get('low', 0))),
                        close=float(row.get('Close', row.get('close', 0))),
                        volume=float(row.get('Volume', row.get('volume', 0)))
                    )
                    bars.append(bar)
                except (ValueError, KeyError):
                    continue

        # Sort by timestamp
        bars.sort(key=lambda x: x.timestamp)

        data = HistoricalData(symbol=symbol, bars=bars)
        self._cache[symbol] = data

        return data

    def generate_synthetic(
        self,
        symbol: str,
        start_date: datetime = None,
        end_date: datetime = None,
        initial_price: float = 100.0,
        volatility: float = 0.02,
        drift: float = 0.0005,
        n_days: int = 252
    ) -> HistoricalData:
        """
        Generate synthetic price data using geometric Brownian motion.

        Args:
            symbol: Symbol name
            start_date: Start date (default: 1 year ago)
            end_date: End date (default: today)
            initial_price: Starting price
            volatility: Daily volatility (e.g., 0.02 = 2%)
            drift: Daily drift (e.g., 0.0005 = 0.05%)
            n_days: Number of trading days
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now()

        np.random.seed(hash(symbol) % 2**32)

        # Generate daily returns using GBM
        returns = np.random.normal(drift, volatility, n_days)

        # Calculate prices
        prices = initial_price * np.cumprod(1 + returns)
        prices = np.insert(prices, 0, initial_price)

        # Generate OHLCV bars
        bars = []
        current_date = start_date

        for i, close in enumerate(prices[1:]):
            # Simulate intraday movement
            daily_vol = abs(np.random.normal(0, volatility))
            open_price = prices[i]
            high = max(open_price, close) * (1 + daily_vol * 0.5)
            low = min(open_price, close) * (1 - daily_vol * 0.5)

            # Volume correlated with volatility
            base_volume = 1_000_000
            volume = base_volume * (1 + abs(close - open_price) / open_price * 10)

            bar = HistoricalBar(
                timestamp=current_date,
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=int(volume)
            )
            bars.append(bar)

            # Move to next trading day (skip weekends)
            current_date += timedelta(days=1)
            while current_date.weekday() >= 5:
                current_date += timedelta(days=1)

        data = HistoricalData(symbol=symbol, bars=bars)
        self._cache[symbol] = data

        return data

    def get(self, symbol: str) -> Optional[HistoricalData]:
        """Get cached data for a symbol."""
        return self._cache.get(symbol)

    def get_multiple(self, symbols: List[str]) -> Dict[str, HistoricalData]:
        """Get data for multiple symbols."""
        return {s: self._cache[s] for s in symbols if s in self._cache}


class TechnicalIndicators:
    """
    Calculate technical indicators from historical data.

    All methods are static and work with numpy arrays.
    """

    @staticmethod
    def sma(prices: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average."""
        if len(prices) < period:
            return np.full(len(prices), np.nan)

        result = np.full(len(prices), np.nan)
        for i in range(period - 1, len(prices)):
            result[i] = np.mean(prices[i - period + 1:i + 1])
        return result

    @staticmethod
    def ema(prices: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        if len(prices) < period:
            return np.full(len(prices), np.nan)

        result = np.full(len(prices), np.nan)
        multiplier = 2 / (period + 1)

        # First EMA is SMA
        result[period - 1] = np.mean(prices[:period])

        for i in range(period, len(prices)):
            result[i] = (prices[i] - result[i - 1]) * multiplier + result[i - 1]

        return result

    @staticmethod
    def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        if len(prices) < period + 1:
            return np.full(len(prices), np.nan)

        deltas = np.diff(prices)
        result = np.full(len(prices), np.nan)

        for i in range(period, len(prices)):
            gains = deltas[i - period:i].copy()
            losses = deltas[i - period:i].copy()

            gains[gains < 0] = 0
            losses[losses > 0] = 0
            losses = np.abs(losses)

            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)

            if avg_loss == 0:
                result[i] = 100
            else:
                rs = avg_gain / avg_loss
                result[i] = 100 - (100 / (1 + rs))

        return result

    @staticmethod
    def bollinger_bands(
        prices: np.ndarray,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Bollinger Bands.

        Returns: (upper, middle, lower)
        """
        middle = TechnicalIndicators.sma(prices, period)

        result_upper = np.full(len(prices), np.nan)
        result_lower = np.full(len(prices), np.nan)

        for i in range(period - 1, len(prices)):
            std = np.std(prices[i - period + 1:i + 1])
            result_upper[i] = middle[i] + std_dev * std
            result_lower[i] = middle[i] - std_dev * std

        return result_upper, middle, result_lower

    @staticmethod
    def macd(
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        MACD (Moving Average Convergence Divergence).

        Returns: (macd_line, signal_line, histogram)
        """
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)

        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line[~np.isnan(macd_line)], signal)

        # Pad signal line to match length
        padded_signal = np.full(len(prices), np.nan)
        start_idx = np.where(~np.isnan(macd_line))[0][0] + signal - 1
        if start_idx < len(padded_signal):
            padded_signal[start_idx:start_idx + len(signal_line)] = signal_line

        histogram = macd_line - padded_signal

        return macd_line, padded_signal, histogram

    @staticmethod
    def atr(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """Average True Range."""
        if len(highs) < period + 1:
            return np.full(len(highs), np.nan)

        result = np.full(len(highs), np.nan)

        # True Range
        tr = np.zeros(len(highs))
        tr[0] = highs[0] - lows[0]

        for i in range(1, len(highs)):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )

        # ATR is EMA of TR
        for i in range(period - 1, len(highs)):
            if i == period - 1:
                result[i] = np.mean(tr[:period])
            else:
                result[i] = (tr[i] + (period - 1) * result[i - 1]) / period

        return result

    @staticmethod
    def stochastic(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        k_period: int = 14,
        d_period: int = 3
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Stochastic Oscillator.

        Returns: (%K, %D)
        """
        if len(highs) < k_period:
            return np.full(len(highs), np.nan), np.full(len(highs), np.nan)

        k = np.full(len(highs), np.nan)

        for i in range(k_period - 1, len(highs)):
            highest = np.max(highs[i - k_period + 1:i + 1])
            lowest = np.min(lows[i - k_period + 1:i + 1])

            if highest != lowest:
                k[i] = 100 * (closes[i] - lowest) / (highest - lowest)
            else:
                k[i] = 50

        d = TechnicalIndicators.sma(k, d_period)

        return k, d

    @staticmethod
    def volume_profile(
        closes: np.ndarray,
        volumes: np.ndarray,
        n_bins: int = 20
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Volume Profile.

        Returns: (price_levels, volumes_at_levels)
        """
        price_min = np.min(closes)
        price_max = np.max(closes)

        bins = np.linspace(price_min, price_max, n_bins + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2

        bin_volumes = np.zeros(n_bins)

        for i, close in enumerate(closes):
            bin_idx = np.searchsorted(bins[1:], close)
            bin_idx = min(bin_idx, n_bins - 1)
            bin_volumes[bin_idx] += volumes[i]

        return bin_centers, bin_volumes


class DataAnalyzer:
    """
    Analyze historical data and compute statistics.
    """

    @staticmethod
    def summary_stats(data: HistoricalData) -> Dict:
        """Calculate summary statistics."""
        closes = data.closes
        returns = data.returns

        return {
            'symbol': data.symbol,
            'start_date': data.bars[0].timestamp.isoformat(),
            'end_date': data.bars[-1].timestamp.isoformat(),
            'n_bars': len(data),
            'first_price': round(closes[0], 2),
            'last_price': round(closes[-1], 2),
            'total_return': round((closes[-1] / closes[0] - 1) * 100, 2),
            'mean_daily_return': round(np.mean(returns) * 100, 4),
            'std_daily_return': round(np.std(returns) * 100, 4),
            'annualized_return': round(np.mean(returns) * 252 * 100, 2),
            'annualized_volatility': round(np.std(returns) * np.sqrt(252) * 100, 2),
            'sharpe_ratio': round(np.mean(returns) / np.std(returns) * np.sqrt(252), 2) if np.std(returns) > 0 else 0,
            'max_drawdown': round(DataAnalyzer.max_drawdown(closes) * 100, 2),
            'max_price': round(np.max(closes), 2),
            'min_price': round(np.min(closes), 2),
            'total_volume': int(np.sum(data.volumes))
        }

    @staticmethod
    def max_drawdown(prices: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        peak = prices[0]
        max_dd = 0

        for price in prices:
            if price > peak:
                peak = price
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd

        return max_dd

    @staticmethod
    def rolling_sharpe(
        returns: np.ndarray,
        window: int = 252,
        risk_free_rate: float = 0.0
    ) -> np.ndarray:
        """Calculate rolling Sharpe ratio."""
        result = np.full(len(returns), np.nan)

        for i in range(window - 1, len(returns)):
            window_returns = returns[i - window + 1:i + 1]
            excess_returns = window_returns - risk_free_rate / 252

            if np.std(window_returns) > 0:
                result[i] = np.mean(excess_returns) / np.std(window_returns) * np.sqrt(252)

        return result

    @staticmethod
    def correlation_matrix(
        data_dict: Dict[str, HistoricalData]
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Calculate correlation matrix between symbols.

        Returns: (correlation_matrix, symbol_list)
        """
        symbols = list(data_dict.keys())
        n = len(symbols)

        # Align returns by date
        min_len = min(len(d.returns) for d in data_dict.values())

        returns_matrix = np.zeros((min_len, n))
        for i, symbol in enumerate(symbols):
            returns_matrix[:, i] = data_dict[symbol].returns[-min_len:]

        corr = np.corrcoef(returns_matrix.T)

        return corr, symbols
