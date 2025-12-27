"""
Real-time price fetcher using FREE APIs
- CoinGecko for crypto (no API key needed)
- Yahoo Finance for stocks (no API key needed)
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import time


@dataclass
class PriceData:
    """Price data for an asset"""
    symbol: str
    price: float
    change_24h: float  # Percentage
    volume_24h: float
    high_24h: float
    low_24h: float
    market_cap: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class HistoricalBar:
    """Historical price bar"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceFetcher:
    """Fetches real-time prices from free APIs"""

    COINGECKO_BASE = "https://api.coingecko.com/api/v3"
    YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 30  # Cache for 30 seconds

    def _is_cached(self, key: str) -> bool:
        """Check if data is cached and fresh"""
        if key not in self._cache:
            return False
        if datetime.now() - self._cache_time[key] > timedelta(seconds=self._cache_ttl):
            return False
        return True

    # =========================================================================
    # CRYPTO PRICES (CoinGecko - FREE, no API key)
    # =========================================================================

    def get_crypto_prices(self, coins: List[str] = None) -> Dict[str, PriceData]:
        """
        Get real-time crypto prices from CoinGecko

        Args:
            coins: List of CoinGecko IDs (e.g., ["bitcoin", "ethereum"])

        Returns:
            Dict mapping coin ID to PriceData
        """
        if coins is None:
            coins = ["bitcoin", "ethereum", "solana", "cardano", "dogecoin"]

        cache_key = f"crypto_{','.join(sorted(coins))}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"{self.COINGECKO_BASE}/coins/markets"
            params = {
                "vs_currency": "usd",
                "ids": ",".join(coins),
                "order": "market_cap_desc",
                "sparkline": "false",
                "price_change_percentage": "24h"
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = {}
            for coin in data:
                result[coin["id"]] = PriceData(
                    symbol=coin["symbol"].upper(),
                    price=coin["current_price"] or 0,
                    change_24h=coin["price_change_percentage_24h"] or 0,
                    volume_24h=coin["total_volume"] or 0,
                    high_24h=coin["high_24h"] or coin["current_price"],
                    low_24h=coin["low_24h"] or coin["current_price"],
                    market_cap=coin["market_cap"]
                )

            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()
            return result

        except Exception as e:
            print(f"Error fetching crypto prices: {e}")
            return {}

    def get_crypto_history(self, coin: str, days: int = 30) -> List[HistoricalBar]:
        """
        Get historical crypto prices

        Args:
            coin: CoinGecko coin ID (e.g., "bitcoin")
            days: Number of days of history

        Returns:
            List of HistoricalBar objects
        """
        cache_key = f"crypto_hist_{coin}_{days}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"{self.COINGECKO_BASE}/coins/{coin}/ohlc"
            params = {
                "vs_currency": "usd",
                "days": days
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            bars = []
            for candle in data:
                bars.append(HistoricalBar(
                    timestamp=datetime.fromtimestamp(candle[0] / 1000),
                    open=candle[1],
                    high=candle[2],
                    low=candle[3],
                    close=candle[4],
                    volume=0  # OHLC endpoint doesn't include volume
                ))

            self._cache[cache_key] = bars
            self._cache_time[cache_key] = datetime.now()
            return bars

        except Exception as e:
            print(f"Error fetching crypto history: {e}")
            return []

    # =========================================================================
    # STOCK PRICES (Yahoo Finance - FREE, no API key)
    # =========================================================================

    def get_stock_price(self, symbol: str) -> Optional[PriceData]:
        """
        Get real-time stock price from Yahoo Finance

        Args:
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            PriceData object or None
        """
        cache_key = f"stock_{symbol}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"{self.YAHOO_BASE}/{symbol}"
            params = {
                "interval": "1d",
                "range": "2d"
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = data["chart"]["result"][0]
            meta = result["meta"]
            quote = result["indicators"]["quote"][0]

            current_price = meta["regularMarketPrice"]
            previous_close = meta.get("previousClose", current_price)

            # Calculate 24h change
            change_24h = ((current_price - previous_close) / previous_close) * 100 if previous_close else 0

            price_data = PriceData(
                symbol=symbol,
                price=current_price,
                change_24h=change_24h,
                volume_24h=meta.get("regularMarketVolume", 0),
                high_24h=meta.get("regularMarketDayHigh", current_price),
                low_24h=meta.get("regularMarketDayLow", current_price),
                market_cap=meta.get("marketCap")
            )

            self._cache[cache_key] = price_data
            self._cache_time[cache_key] = datetime.now()
            return price_data

        except Exception as e:
            print(f"Error fetching stock price for {symbol}: {e}")
            return None

    def get_stock_prices(self, symbols: List[str]) -> Dict[str, PriceData]:
        """
        Get real-time prices for multiple stocks

        Args:
            symbols: List of stock symbols

        Returns:
            Dict mapping symbol to PriceData
        """
        result = {}
        for symbol in symbols:
            price = self.get_stock_price(symbol)
            if price:
                result[symbol] = price
            time.sleep(0.1)  # Rate limiting
        return result

    def get_stock_history(self, symbol: str, days: int = 30) -> List[HistoricalBar]:
        """
        Get historical stock prices

        Args:
            symbol: Stock symbol
            days: Number of days of history

        Returns:
            List of HistoricalBar objects
        """
        cache_key = f"stock_hist_{symbol}_{days}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"{self.YAHOO_BASE}/{symbol}"

            # Convert days to Yahoo range format
            if days <= 5:
                range_str = "5d"
            elif days <= 30:
                range_str = "1mo"
            elif days <= 90:
                range_str = "3mo"
            else:
                range_str = "1y"

            params = {
                "interval": "1d",
                "range": range_str
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]

            bars = []
            for i in range(len(timestamps)):
                if quote["open"][i] is None:
                    continue
                bars.append(HistoricalBar(
                    timestamp=datetime.fromtimestamp(timestamps[i]),
                    open=quote["open"][i],
                    high=quote["high"][i],
                    low=quote["low"][i],
                    close=quote["close"][i],
                    volume=quote["volume"][i] or 0
                ))

            self._cache[cache_key] = bars
            self._cache_time[cache_key] = datetime.now()
            return bars

        except Exception as e:
            print(f"Error fetching stock history for {symbol}: {e}")
            return []

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def get_all_prices(self, stocks: List[str] = None, cryptos: List[str] = None) -> Dict[str, PriceData]:
        """Get all prices for stocks and cryptos"""
        result = {}

        if stocks:
            result.update(self.get_stock_prices(stocks))

        if cryptos:
            crypto_prices = self.get_crypto_prices(cryptos)
            # Use symbol as key instead of CoinGecko ID
            for coin_id, price_data in crypto_prices.items():
                result[price_data.symbol] = price_data

        return result


# Quick test
if __name__ == "__main__":
    fetcher = PriceFetcher()

    print("\n📊 REAL-TIME CRYPTO PRICES")
    print("=" * 50)
    crypto = fetcher.get_crypto_prices(["bitcoin", "ethereum", "solana"])
    for coin_id, price in crypto.items():
        arrow = "🟢" if price.change_24h > 0 else "🔴"
        print(f"{arrow} {price.symbol}: ${price.price:,.2f} ({price.change_24h:+.2f}%)")

    print("\n📈 REAL-TIME STOCK PRICES")
    print("=" * 50)
    stocks = fetcher.get_stock_prices(["AAPL", "GOOGL", "MSFT", "NVDA"])
    for symbol, price in stocks.items():
        arrow = "🟢" if price.change_24h > 0 else "🔴"
        print(f"{arrow} {symbol}: ${price.price:,.2f} ({price.change_24h:+.2f}%)")
