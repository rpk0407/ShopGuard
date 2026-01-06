"""
TQO MVP Settings

Runtime configuration loaded from environment or config file.
Separate from constants (which are validated at import).
"""
import os
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path
import json


@dataclass
class ExchangeSettings:
    """Exchange connection settings."""
    name: str = "hyperliquid"
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True  # Default to testnet for safety

    # WebSocket settings
    ws_url: str = "wss://api.hyperliquid.xyz/ws"
    ws_testnet_url: str = "wss://api.hyperliquid-testnet.xyz/ws"

    # REST settings
    rest_url: str = "https://api.hyperliquid.xyz"
    rest_testnet_url: str = "https://api.hyperliquid-testnet.xyz"

    @property
    def active_ws_url(self) -> str:
        return self.ws_testnet_url if self.testnet else self.ws_url

    @property
    def active_rest_url(self) -> str:
        return self.rest_testnet_url if self.testnet else self.rest_url


@dataclass
class TradingSettings:
    """Trading parameters."""
    # Assets to trade
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH"])

    # Account settings
    initial_capital: float = 5000.0
    leverage: float = 3.0  # Conservative 3x

    # Mode
    paper_trading: bool = True
    live_trading: bool = False

    # Timeframes
    signal_timeframe: str = "1m"  # 1 minute candles for signals
    data_timeframe: str = "tick"  # Tick data for CVD


@dataclass
class LoggingSettings:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"  # 'json' or 'text'
    file_path: Optional[str] = None

    # Separate logs
    trade_log_path: str = "logs/trades.jsonl"
    signal_log_path: str = "logs/signals.jsonl"
    error_log_path: str = "logs/errors.log"


@dataclass
class DatabaseSettings:
    """Data storage settings."""
    # SQLite for MVP (easy), PostgreSQL for scale
    type: str = "sqlite"
    path: str = "data/titan_mvp.db"

    # TimescaleDB for tick data (future)
    timescale_url: Optional[str] = None


@dataclass
class Settings:
    """
    Master settings container.

    Load order:
    1. Defaults (defined here)
    2. Config file (if exists)
    3. Environment variables (highest priority)
    """
    exchange: ExchangeSettings = field(default_factory=ExchangeSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)

    # Meta
    environment: str = "development"  # 'development', 'staging', 'production'
    debug: bool = True

    @classmethod
    def from_env(cls) -> 'Settings':
        """Load settings from environment variables."""
        settings = cls()

        # Exchange
        settings.exchange.api_key = os.getenv('HYPERLIQUID_API_KEY', '')
        settings.exchange.api_secret = os.getenv('HYPERLIQUID_API_SECRET', '')
        settings.exchange.testnet = os.getenv('HYPERLIQUID_TESTNET', 'true').lower() == 'true'

        # Trading
        capital = os.getenv('INITIAL_CAPITAL')
        if capital:
            settings.trading.initial_capital = float(capital)

        leverage = os.getenv('LEVERAGE')
        if leverage:
            settings.trading.leverage = float(leverage)

        settings.trading.paper_trading = os.getenv('PAPER_TRADING', 'true').lower() == 'true'
        settings.trading.live_trading = os.getenv('LIVE_TRADING', 'false').lower() == 'true'

        # Assets
        assets = os.getenv('TRADING_ASSETS')
        if assets:
            settings.trading.assets = [a.strip() for a in assets.split(',')]

        # Logging
        settings.logging.level = os.getenv('LOG_LEVEL', 'INFO')

        # Environment
        settings.environment = os.getenv('ENVIRONMENT', 'development')
        settings.debug = os.getenv('DEBUG', 'true').lower() == 'true'

        return settings

    @classmethod
    def from_file(cls, path: str) -> 'Settings':
        """Load settings from JSON config file."""
        config_path = Path(path)
        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = json.load(f)

        settings = cls()

        # Exchange settings
        if 'exchange' in data:
            for key, value in data['exchange'].items():
                if hasattr(settings.exchange, key):
                    setattr(settings.exchange, key, value)

        # Trading settings
        if 'trading' in data:
            for key, value in data['trading'].items():
                if hasattr(settings.trading, key):
                    setattr(settings.trading, key, value)

        # Logging settings
        if 'logging' in data:
            for key, value in data['logging'].items():
                if hasattr(settings.logging, key):
                    setattr(settings.logging, key, value)

        return settings

    def validate(self) -> List[str]:
        """Validate settings. Returns list of errors."""
        errors = []

        # Check for API keys in live mode
        if self.trading.live_trading:
            if not self.exchange.api_key:
                errors.append("API key required for live trading")
            if not self.exchange.api_secret:
                errors.append("API secret required for live trading")
            if self.exchange.testnet:
                errors.append("Testnet enabled but live_trading=True")

        # Sanity checks
        if self.trading.leverage > 10:
            errors.append(f"Leverage {self.trading.leverage}x is dangerously high")

        if self.trading.initial_capital < 100:
            errors.append(f"Initial capital ${self.trading.initial_capital} too low")

        # Paper vs Live conflict
        if self.trading.paper_trading and self.trading.live_trading:
            errors.append("Cannot have both paper_trading and live_trading enabled")

        return errors

    def to_dict(self) -> dict:
        """Convert to dictionary (for logging/debugging)."""
        return {
            'exchange': {
                'name': self.exchange.name,
                'testnet': self.exchange.testnet,
                # Don't log secrets!
            },
            'trading': {
                'assets': self.trading.assets,
                'initial_capital': self.trading.initial_capital,
                'leverage': self.trading.leverage,
                'paper_trading': self.trading.paper_trading,
                'live_trading': self.trading.live_trading,
            },
            'logging': {
                'level': self.logging.level,
                'format': self.logging.format,
            },
            'environment': self.environment,
            'debug': self.debug,
        }


# Singleton pattern for global settings
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        # Load from env first, then config file
        _settings = Settings.from_env()

        # Override with config file if exists
        config_path = os.getenv('CONFIG_FILE', 'config/settings.json')
        if Path(config_path).exists():
            file_settings = Settings.from_file(config_path)
            # Merge (file settings override env for non-sensitive values)
            # Keep API keys from env for security

    return _settings


def reset_settings():
    """Reset settings (for testing)."""
    global _settings
    _settings = None
