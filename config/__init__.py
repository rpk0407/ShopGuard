"""
TITAN Configuration Loader
===========================
Load settings from YAML config file with environment variable overrides.
"""

import os
import yaml
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HyperliquidConfig:
    """Hyperliquid broker configuration"""
    private_key: str = ""
    testnet: bool = True


@dataclass
class ExternalAlphaConfig:
    """External alpha sources configuration"""
    enabled: bool = True
    weight: float = 0.25
    polymarket_enabled: bool = True
    twitter_bearer_token: str = ""
    reddit_enabled: bool = True
    lunarcrush_api_key: str = ""
    newsapi_key: str = ""
    news_enabled: bool = True


@dataclass
class SmartMoneyConfig:
    """Smart money protection configuration"""
    whale_manipulation_detection: bool = True
    liquidity_trap_detection: bool = True
    block_on_manipulation: bool = True


@dataclass
class TechnicalConfig:
    """Technical analysis configuration"""
    entropy_filter: bool = True
    entropy_lookback: int = 100
    hurst_threshold: float = 0.55
    entropy_threshold: float = 2.5


@dataclass
class RiskConfig:
    """Risk management configuration"""
    atr_stop_multiplier: float = 1.5
    atr_target_multiplier: float = 3.0
    max_risk_per_trade: float = 0.02


@dataclass
class TradingConfig:
    """Main trading configuration"""
    testnet: bool = True
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH"])
    min_confidence: float = 0.6
    max_position_pct: float = 0.25
    max_leverage: int = 3
    max_concurrent_positions: int = 3
    signal_cooldown: int = 60


@dataclass
class TitanConfig:
    """Complete TITAN system configuration"""
    trading: TradingConfig = field(default_factory=TradingConfig)
    hyperliquid: HyperliquidConfig = field(default_factory=HyperliquidConfig)
    external_alpha: ExternalAlphaConfig = field(default_factory=ExternalAlphaConfig)
    smart_money: SmartMoneyConfig = field(default_factory=SmartMoneyConfig)
    technical: TechnicalConfig = field(default_factory=TechnicalConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    funding_arbitrage_enabled: bool = True
    min_funding_rate: float = 0.0005


def load_config(config_path: str = None) -> TitanConfig:
    """
    Load configuration from YAML file with environment variable overrides.

    Priority:
    1. Environment variables (highest)
    2. settings.yaml
    3. settings.example.yaml
    4. Default values (lowest)

    Environment variable format: TITAN_SECTION_KEY
    Example: TITAN_HYPERLIQUID_PRIVATE_KEY
    """
    config = TitanConfig()

    # Find config file
    if config_path is None:
        config_dir = Path(__file__).parent
        if (config_dir / "settings.yaml").exists():
            config_path = config_dir / "settings.yaml"
        elif (config_dir / "settings.example.yaml").exists():
            config_path = config_dir / "settings.example.yaml"
            logger.warning("Using example config - copy to settings.yaml for production")

    # Load YAML config
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f) or {}

        # Parse trading config
        trading = yaml_config.get('trading', {})
        config.trading = TradingConfig(
            testnet=trading.get('testnet', True),
            assets=trading.get('assets', ["BTC", "ETH"]),
            min_confidence=trading.get('min_confidence', 0.6),
            max_position_pct=trading.get('max_position_pct', 0.25),
            max_leverage=trading.get('max_leverage', 3),
            max_concurrent_positions=trading.get('max_concurrent_positions', 3),
            signal_cooldown=yaml_config.get('monitoring', {}).get('signal_cooldown', 60)
        )

        # Parse hyperliquid config
        hl = yaml_config.get('hyperliquid', {})
        config.hyperliquid = HyperliquidConfig(
            private_key=hl.get('private_key', ''),
            testnet=hl.get('testnet', True)
        )

        # Parse external alpha config
        ext = yaml_config.get('external_alpha', {})
        config.external_alpha = ExternalAlphaConfig(
            enabled=ext.get('enabled', True),
            weight=ext.get('weight', 0.25),
            polymarket_enabled=ext.get('polymarket', {}).get('enabled', True),
            twitter_bearer_token=ext.get('social', {}).get('twitter_bearer_token', ''),
            reddit_enabled=ext.get('social', {}).get('reddit_enabled', True),
            lunarcrush_api_key=ext.get('social', {}).get('lunarcrush_api_key', ''),
            newsapi_key=ext.get('news', {}).get('newsapi_key', ''),
            news_enabled=ext.get('news', {}).get('enabled', True)
        )

        # Parse smart money config
        sm = yaml_config.get('smart_money_protection', {})
        config.smart_money = SmartMoneyConfig(
            whale_manipulation_detection=sm.get('whale_manipulation_detection', True),
            liquidity_trap_detection=sm.get('liquidity_trap_detection', True),
            block_on_manipulation=sm.get('block_on_manipulation', True)
        )

        # Parse technical config
        ta = yaml_config.get('technical_analysis', {})
        config.technical = TechnicalConfig(
            entropy_filter=ta.get('entropy_filter', True),
            entropy_lookback=ta.get('entropy_lookback', 100),
            hurst_threshold=ta.get('hurst_threshold', 0.55),
            entropy_threshold=ta.get('entropy_threshold', 2.5)
        )

        # Parse risk config
        risk = yaml_config.get('risk', {})
        config.risk = RiskConfig(
            atr_stop_multiplier=risk.get('atr_stop_multiplier', 1.5),
            atr_target_multiplier=risk.get('atr_target_multiplier', 3.0),
            max_risk_per_trade=risk.get('max_risk_per_trade', 0.02)
        )

        # Funding arbitrage
        funding = yaml_config.get('funding_arbitrage', {})
        config.funding_arbitrage_enabled = funding.get('enabled', True)
        config.min_funding_rate = funding.get('min_funding_rate', 0.0005)

    # Override with environment variables
    config = _apply_env_overrides(config)

    return config


def _apply_env_overrides(config: TitanConfig) -> TitanConfig:
    """Apply environment variable overrides"""

    # Hyperliquid
    if os.getenv('TITAN_HYPERLIQUID_PRIVATE_KEY'):
        config.hyperliquid.private_key = os.getenv('TITAN_HYPERLIQUID_PRIVATE_KEY')
    if os.getenv('TITAN_HYPERLIQUID_TESTNET'):
        config.hyperliquid.testnet = os.getenv('TITAN_HYPERLIQUID_TESTNET').lower() == 'true'

    # External Alpha
    if os.getenv('TITAN_TWITTER_BEARER_TOKEN'):
        config.external_alpha.twitter_bearer_token = os.getenv('TITAN_TWITTER_BEARER_TOKEN')
    if os.getenv('TITAN_NEWSAPI_KEY'):
        config.external_alpha.newsapi_key = os.getenv('TITAN_NEWSAPI_KEY')
    if os.getenv('TITAN_LUNARCRUSH_API_KEY'):
        config.external_alpha.lunarcrush_api_key = os.getenv('TITAN_LUNARCRUSH_API_KEY')

    # Trading
    if os.getenv('TITAN_TESTNET'):
        config.trading.testnet = os.getenv('TITAN_TESTNET').lower() == 'true'
    if os.getenv('TITAN_ASSETS'):
        config.trading.assets = os.getenv('TITAN_ASSETS').split(',')

    return config


# Global config instance
_config: Optional[TitanConfig] = None


def get_config() -> TitanConfig:
    """Get or create global config instance"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: str = None) -> TitanConfig:
    """Reload configuration from file"""
    global _config
    _config = load_config(config_path)
    return _config


if __name__ == "__main__":
    # Test config loading
    config = load_config()
    print("TITAN Configuration Loaded:")
    print(f"  Testnet: {config.trading.testnet}")
    print(f"  Assets: {config.trading.assets}")
    print(f"  External Alpha: {config.external_alpha.enabled}")
    print(f"  Whale Detection: {config.smart_money.whale_manipulation_detection}")
    print(f"  Entropy Filter: {config.technical.entropy_filter}")
