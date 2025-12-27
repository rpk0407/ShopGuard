"""
Live Trading Bot Configuration
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class TradingConfig:
    """Trading configuration"""
    # Trading mode
    mode: str = "paper"  # "paper" or "live"

    # Initial capital for paper trading
    paper_capital: float = 100000.0

    # Risk management
    max_position_pct: float = 0.10  # Max 10% per position
    max_daily_loss_pct: float = 0.02  # Stop trading if down 2%

    # Strategy settings
    default_strategy: str = "momentum"

    # API Keys (set via environment variables)
    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    alpaca_paper: bool = True

    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None

    def __post_init__(self):
        # Load from environment
        self.alpaca_api_key = os.getenv("ALPACA_API_KEY", self.alpaca_api_key)
        self.alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY", self.alpaca_secret_key)
        self.binance_api_key = os.getenv("BINANCE_API_KEY", self.binance_api_key)
        self.binance_secret_key = os.getenv("BINANCE_SECRET_KEY", self.binance_secret_key)


# Default watchlists
STOCK_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "NVDA",
    "TSLA", "META", "AMD", "NFLX", "SPY"
]

CRYPTO_WATCHLIST = [
    "bitcoin", "ethereum", "solana", "cardano",
    "dogecoin", "ripple", "polkadot", "avalanche-2"
]

# CoinGecko IDs to symbols
CRYPTO_SYMBOLS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "cardano": "ADA",
    "dogecoin": "DOGE",
    "ripple": "XRP",
    "polkadot": "DOT",
    "avalanche-2": "AVAX"
}
