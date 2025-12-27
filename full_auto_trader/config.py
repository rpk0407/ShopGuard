"""
Configuration for Full Auto Trader
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class TradingMode(Enum):
    PAPER = "paper"      # Simulated trading (no real money)
    LIVE = "live"        # Real money (BE CAREFUL!)


class RiskLevel(Enum):
    CONSERVATIVE = "conservative"  # 2% risk per trade
    MODERATE = "moderate"          # 5% risk per trade
    AGGRESSIVE = "aggressive"      # 10% risk per trade


@dataclass
class Config:
    """Trading configuration"""

    # =========================================================================
    # TRADING MODE
    # =========================================================================
    mode: TradingMode = TradingMode.PAPER

    # =========================================================================
    # CAPITAL & RISK
    # =========================================================================
    initial_capital: float = 100.0
    risk_level: RiskLevel = RiskLevel.MODERATE

    # Risk parameters based on risk level
    @property
    def max_position_pct(self) -> float:
        """Max % of portfolio per position"""
        return {
            RiskLevel.CONSERVATIVE: 0.10,
            RiskLevel.MODERATE: 0.20,
            RiskLevel.AGGRESSIVE: 0.30
        }[self.risk_level]

    @property
    def stop_loss_pct(self) -> float:
        """Stop loss percentage"""
        return {
            RiskLevel.CONSERVATIVE: 0.02,
            RiskLevel.MODERATE: 0.03,
            RiskLevel.AGGRESSIVE: 0.05
        }[self.risk_level]

    @property
    def take_profit_pct(self) -> float:
        """Take profit percentage"""
        return {
            RiskLevel.CONSERVATIVE: 0.04,
            RiskLevel.MODERATE: 0.06,
            RiskLevel.AGGRESSIVE: 0.10
        }[self.risk_level]

    @property
    def max_daily_loss_pct(self) -> float:
        """Max daily loss before stopping"""
        return {
            RiskLevel.CONSERVATIVE: 0.03,
            RiskLevel.MODERATE: 0.05,
            RiskLevel.AGGRESSIVE: 0.10
        }[self.risk_level]

    # =========================================================================
    # ASSETS TO TRADE
    # =========================================================================
    stocks: List[str] = field(default_factory=lambda: [
        "NVDA", "SPY", "QQQ", "AAPL", "TSLA", "AMD", "META", "GOOGL", "MSFT", "AMZN"
    ])

    crypto: List[str] = field(default_factory=lambda: [
        "BTCUSD", "ETHUSD"  # Alpaca crypto symbols
    ])

    # CoinGecko IDs for price fetching
    crypto_ids: List[str] = field(default_factory=lambda: [
        "bitcoin", "ethereum"
    ])

    # =========================================================================
    # BROKER API KEYS (set via environment variables)
    # =========================================================================
    # Alpaca (FREE paper trading at alpaca.markets)
    alpaca_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ALPACA_API_KEY"))
    alpaca_secret_key: Optional[str] = field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY"))
    alpaca_paper: bool = True  # Use paper trading endpoint

    # =========================================================================
    # NEWS & SENTIMENT SOURCES
    # =========================================================================
    enable_news: bool = True
    enable_reddit: bool = True
    enable_twitter: bool = False  # Requires API key

    # Subreddits to monitor
    subreddits: List[str] = field(default_factory=lambda: [
        "wallstreetbets",
        "stocks",
        "investing",
        "cryptocurrency",
        "Bitcoin"
    ])

    # =========================================================================
    # AI SETTINGS
    # =========================================================================
    min_confidence: float = 0.65  # Minimum confidence to execute trade

    # Signal weights
    technical_weight: float = 0.40   # Technical analysis weight
    news_weight: float = 0.30        # News sentiment weight
    social_weight: float = 0.30      # Social media sentiment weight

    # =========================================================================
    # AUTOMATION SETTINGS
    # =========================================================================
    scan_interval_minutes: int = 5   # How often to scan for opportunities
    max_open_positions: int = 5      # Maximum concurrent positions
    min_hold_minutes: int = 15       # Minimum hold time
    max_hold_hours: int = 24         # Maximum hold time

    # =========================================================================
    # DISPLAY SYMBOLS
    # =========================================================================
    symbol_display: dict = field(default_factory=lambda: {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "SPY": "S&P 500",
        "QQQ": "NASDAQ"
    })


# Global config instance
DEFAULT_CONFIG = Config()
