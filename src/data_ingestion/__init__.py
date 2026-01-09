"""
Data Ingestion Tools

Tools for downloading and processing historical market data:
- Yahoo Finance (free)
- Alpha Vantage
- Polygon.io
- Alpaca Markets
- CSV/Parquet files
"""

from .historical import (
    DataProvider,
    YahooFinanceProvider,
    AlphaVantageProvider,
    PolygonProvider,
    AlpacaProvider,
    DataIngestion
)

__all__ = [
    'DataProvider',
    'YahooFinanceProvider',
    'AlphaVantageProvider',
    'PolygonProvider',
    'AlpacaProvider',
    'DataIngestion'
]
