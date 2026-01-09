"""
Historical Data Ingestion

Download and process historical market data from multiple providers.
"""

import os
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
import requests
import time


class DataProvider(ABC):
    """Abstract base class for data providers"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """Get historical OHLCV data"""
        pass

    @abstractmethod
    def get_multiple_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """Get data for multiple symbols"""
        pass

    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """Validate OHLCV dataframe"""
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        return all(col in df.columns for col in required_columns)


# =============================================================================
# Yahoo Finance Provider (Free)
# =============================================================================

class YahooFinanceProvider(DataProvider):
    """
    Yahoo Finance data provider (free, no API key required)

    Pros: Free, good coverage, reliable
    Cons: Rate limited, no real-time data
    """

    def __init__(self):
        super().__init__()
        self.base_url = "https://query1.finance.yahoo.com/v7/finance/download"

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """Download data from Yahoo Finance"""
        try:
            # Convert dates to timestamps
            start_ts = int(pd.Timestamp(start_date).timestamp())
            end_ts = int(pd.Timestamp(end_date).timestamp())

            # Map interval
            yahoo_interval = {
                '1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h',
                '1d': '1d', '1wk': '1wk', '1mo': '1mo'
            }.get(interval, '1d')

            # Build URL
            url = f"{self.base_url}/{symbol}"
            params = {
                'period1': start_ts,
                'period2': end_ts,
                'interval': yahoo_interval,
                'events': 'history'
            }

            # Download
            logger.info(f"Downloading {symbol} from Yahoo Finance...")
            df = pd.read_csv(url, params=params)

            # Standardize column names
            df.columns = df.columns.str.lower()
            df['symbol'] = symbol
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            logger.info(f"Downloaded {len(df)} bars for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error downloading {symbol} from Yahoo Finance: {e}")
            return pd.DataFrame()

    def get_multiple_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """Download multiple symbols with rate limiting"""
        data = {}

        for i, symbol in enumerate(symbols):
            df = self.get_historical_data(symbol, start_date, end_date, interval)
            if not df.empty:
                data[symbol] = df

            # Rate limiting
            if i < len(symbols) - 1:
                time.sleep(0.5)  # Be nice to Yahoo

        return data


# =============================================================================
# Alpha Vantage Provider
# =============================================================================

class AlphaVantageProvider(DataProvider):
    """
    Alpha Vantage data provider

    Pros: Free tier available, good for stocks
    Cons: Rate limited (5 requests/min on free tier)
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key or os.getenv('ALPHAVANTAGE_API_KEY'))
        self.base_url = "https://www.alphavantage.co/query"

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """Download data from Alpha Vantage"""
        if not self.api_key:
            logger.error("Alpha Vantage API key not configured")
            return pd.DataFrame()

        try:
            # Determine function based on interval
            if interval in ['1m', '5m', '15m', '30m', '60m']:
                function = 'TIME_SERIES_INTRADAY'
                params = {
                    'function': function,
                    'symbol': symbol,
                    'interval': interval,
                    'outputsize': 'full',
                    'apikey': self.api_key
                }
            else:
                function = 'TIME_SERIES_DAILY'
                params = {
                    'function': function,
                    'symbol': symbol,
                    'outputsize': 'full',
                    'apikey': self.api_key
                }

            logger.info(f"Downloading {symbol} from Alpha Vantage...")
            response = requests.get(self.base_url, params=params)
            data = response.json()

            # Extract time series data
            if 'Time Series' in str(data):
                # Find the time series key
                ts_key = [k for k in data.keys() if 'Time Series' in k][0]
                ts_data = data[ts_key]

                # Convert to DataFrame
                df = pd.DataFrame.from_dict(ts_data, orient='index')
                df.index = pd.to_datetime(df.index)
                df = df.sort_index()

                # Standardize column names
                df.columns = [c.split('. ')[1] for c in df.columns]
                df.columns = df.columns.str.lower()
                df = df.astype(float)
                df['symbol'] = symbol

                # Filter date range
                df = df.loc[start_date:end_date]

                logger.info(f"Downloaded {len(df)} bars for {symbol}")
                return df
            else:
                logger.error(f"No data in response for {symbol}: {data}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error downloading {symbol} from Alpha Vantage: {e}")
            return pd.DataFrame()

    def get_multiple_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """Download multiple symbols with strict rate limiting"""
        data = {}

        for i, symbol in enumerate(symbols):
            df = self.get_historical_data(symbol, start_date, end_date, interval)
            if not df.empty:
                data[symbol] = df

            # Strict rate limiting for free tier
            if i < len(symbols) - 1:
                logger.info("Waiting 12s (Alpha Vantage rate limit)...")
                time.sleep(12)  # 5 requests/min = 12s between requests

        return data


# =============================================================================
# Polygon.io Provider
# =============================================================================

class PolygonProvider(DataProvider):
    """
    Polygon.io data provider

    Pros: High quality, real-time, multiple asset classes
    Cons: Paid (free tier very limited)
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key or os.getenv('POLYGON_API_KEY'))
        self.base_url = "https://api.polygon.io"

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """Download data from Polygon.io"""
        if not self.api_key:
            logger.error("Polygon API key not configured")
            return pd.DataFrame()

        try:
            # Map interval to timespan/multiplier
            interval_map = {
                '1m': ('minute', 1), '5m': ('minute', 5),
                '15m': ('minute', 15), '1h': ('hour', 1),
                '1d': ('day', 1), '1wk': ('week', 1), '1mo': ('month', 1)
            }
            timespan, multiplier = interval_map.get(interval, ('day', 1))

            # Build URL
            url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date}/{end_date}"
            params = {'apiKey': self.api_key, 'limit': 50000}

            logger.info(f"Downloading {symbol} from Polygon.io...")
            response = requests.get(url, params=params)
            data = response.json()

            if data.get('status') == 'OK' and 'results' in data:
                # Convert to DataFrame
                df = pd.DataFrame(data['results'])
                df['date'] = pd.to_datetime(df['t'], unit='ms')
                df = df.set_index('date')

                # Rename columns
                df = df.rename(columns={
                    'o': 'open', 'h': 'high', 'l': 'low',
                    'c': 'close', 'v': 'volume', 'vw': 'vwap'
                })
                df['symbol'] = symbol

                # Select relevant columns
                df = df[['open', 'high', 'low', 'close', 'volume', 'vwap', 'symbol']]

                logger.info(f"Downloaded {len(df)} bars for {symbol}")
                return df
            else:
                logger.error(f"Error in Polygon response for {symbol}: {data.get('error', 'Unknown error')}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error downloading {symbol} from Polygon.io: {e}")
            return pd.DataFrame()

    def get_multiple_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """Download multiple symbols"""
        data = {}

        for symbol in symbols:
            df = self.get_historical_data(symbol, start_date, end_date, interval)
            if not df.empty:
                data[symbol] = df
            time.sleep(0.1)  # Small delay to be respectful

        return data


# =============================================================================
# Alpaca Markets Provider
# =============================================================================

class AlpacaProvider(DataProvider):
    """
    Alpaca Markets data provider

    Pros: Free for US equities, good quality
    Cons: US markets only
    """

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        super().__init__(api_key or os.getenv('ALPACA_API_KEY'))
        self.secret_key = secret_key or os.getenv('ALPACA_SECRET_KEY')
        self.base_url = "https://data.alpaca.markets/v2"

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """Download data from Alpaca"""
        if not self.api_key or not self.secret_key:
            logger.error("Alpaca API credentials not configured")
            return pd.DataFrame()

        try:
            # Map interval
            timeframe_map = {
                '1m': '1Min', '5m': '5Min', '15m': '15Min',
                '1h': '1Hour', '1d': '1Day'
            }
            timeframe = timeframe_map.get(interval, '1Day')

            # Build URL
            url = f"{self.base_url}/stocks/{symbol}/bars"
            headers = {
                'APCA-API-KEY-ID': self.api_key,
                'APCA-API-SECRET-KEY': self.secret_key
            }
            params = {
                'start': start_date,
                'end': end_date,
                'timeframe': timeframe,
                'limit': 10000
            }

            logger.info(f"Downloading {symbol} from Alpaca...")
            response = requests.get(url, headers=headers, params=params)
            data = response.json()

            if 'bars' in data and data['bars']:
                # Convert to DataFrame
                df = pd.DataFrame(data['bars'])
                df['date'] = pd.to_datetime(df['t'])
                df = df.set_index('date')

                # Rename columns
                df = df.rename(columns={
                    'o': 'open', 'h': 'high', 'l': 'low',
                    'c': 'close', 'v': 'volume', 'vw': 'vwap'
                })
                df['symbol'] = symbol

                logger.info(f"Downloaded {len(df)} bars for {symbol}")
                return df
            else:
                logger.error(f"No data for {symbol} from Alpaca")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error downloading {symbol} from Alpaca: {e}")
            return pd.DataFrame()

    def get_multiple_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """Download multiple symbols"""
        data = {}

        for symbol in symbols:
            df = self.get_historical_data(symbol, start_date, end_date, interval)
            if not df.empty:
                data[symbol] = df

        return data


# =============================================================================
# Data Ingestion Manager
# =============================================================================

class DataIngestion:
    """
    Main data ingestion class with automatic provider fallback
    """

    def __init__(self, preferred_provider: str = 'yahoo'):
        """
        Initialize with preferred provider

        Args:
            preferred_provider: 'yahoo', 'alphavantage', 'polygon', 'alpaca'
        """
        self.providers = {
            'yahoo': YahooFinanceProvider(),
            'alphavantage': AlphaVantageProvider(),
            'polygon': PolygonProvider(),
            'alpaca': AlpacaProvider()
        }
        self.preferred_provider = preferred_provider

    def download_data(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = '1d',
        provider: Optional[str] = None,
        save_to_csv: bool = False,
        output_dir: str = 'data/historical'
    ) -> Dict[str, pd.DataFrame]:
        """
        Download historical data with automatic fallback

        Args:
            symbols: List of symbols to download
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Data interval
            provider: Specific provider to use (None = use preferred)
            save_to_csv: Save data to CSV files
            output_dir: Directory for CSV files

        Returns:
            Dictionary mapping symbols to DataFrames
        """
        provider_name = provider or self.preferred_provider

        if provider_name not in self.providers:
            logger.error(f"Unknown provider: {provider_name}")
            return {}

        logger.info(f"Downloading data using {provider_name} provider...")
        data_provider = self.providers[provider_name]

        # Download data
        data = data_provider.get_multiple_symbols(symbols, start_date, end_date, interval)

        # Save to CSV if requested
        if save_to_csv:
            os.makedirs(output_dir, exist_ok=True)
            for symbol, df in data.items():
                filename = f"{output_dir}/{symbol}_{start_date}_{end_date}_{interval}.csv"
                df.to_csv(filename)
                logger.info(f"Saved {symbol} to {filename}")

        logger.info(f"Downloaded data for {len(data)}/{len(symbols)} symbols")
        return data

    def load_from_csv(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = '1d',
        data_dir: str = 'data/historical'
    ) -> Dict[str, pd.DataFrame]:
        """Load previously downloaded CSV files"""
        data = {}

        for symbol in symbols:
            filename = f"{data_dir}/{symbol}_{start_date}_{end_date}_{interval}.csv"
            if os.path.exists(filename):
                df = pd.read_csv(filename, index_col=0, parse_dates=True)
                data[symbol] = df
                logger.info(f"Loaded {symbol} from {filename}")
            else:
                logger.warning(f"File not found: {filename}")

        return data

    def get_data_quality_report(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Generate data quality report"""
        report = []

        for symbol, df in data.items():
            report.append({
                'symbol': symbol,
                'bars': len(df),
                'start_date': df.index.min(),
                'end_date': df.index.max(),
                'missing_days': df.isna().sum().sum(),
                'avg_volume': df['volume'].mean() if 'volume' in df else 0,
                'price_range': f"${df['low'].min():.2f} - ${df['high'].max():.2f}"
            })

        return pd.DataFrame(report)
