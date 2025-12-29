"""
Broker Manager - Coordinates Alpaca (stocks) and Binance (crypto)
Automatically routes trades to the correct broker based on asset type
"""
from typing import Dict, List, Optional
from dataclasses import dataclass

from .alpaca_broker import AlpacaBroker, alpaca
from .binance_broker import BinanceBroker, binance


@dataclass
class UnifiedPosition:
    symbol: str
    asset_type: str  # 'stock' or 'crypto'
    quantity: float
    entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    broker: str  # 'alpaca' or 'binance'


class BrokerManager:
    """
    Unified broker manager for stocks and crypto

    Automatically routes:
    - Stocks (NVDA, SPY, QQQ, etc.) -> Alpaca
    - Crypto (BTC, ETH, etc.) -> Binance
    """

    # Known stock symbols
    STOCK_SYMBOLS = {
        "NVDA", "SPY", "QQQ", "AAPL", "TSLA", "AMD", "MSFT", "GOOGL", "GOOG",
        "AMZN", "META", "NFLX", "DIS", "BABA", "V", "MA", "JPM", "BAC", "WFC",
        "XOM", "CVX", "PFE", "JNJ", "UNH", "HD", "WMT", "COST", "TGT", "NKE"
    }

    # Known crypto symbols
    CRYPTO_SYMBOLS = {
        "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT", "MATIC",
        "LINK", "UNI", "ATOM", "LTC", "BCH", "ETC", "XLM", "ALGO", "VET",
        "BITCOIN", "ETHEREUM"
    }

    def __init__(self):
        self.alpaca = alpaca
        self.binance = binance

    def _is_crypto(self, symbol: str) -> bool:
        """Determine if symbol is crypto"""
        symbol = symbol.upper()
        if symbol in self.CRYPTO_SYMBOLS:
            return True
        if symbol in self.STOCK_SYMBOLS:
            return False
        # Default: assume crypto if not in stock list
        return symbol not in self.STOCK_SYMBOLS

    def configure_alpaca(self, api_key: str, secret_key: str, paper: bool = True) -> Dict:
        """Configure Alpaca for stock trading"""
        return self.alpaca.configure(api_key, secret_key, paper)

    def configure_binance(self, api_key: str, secret_key: str, testnet: bool = True) -> Dict:
        """Configure Binance for crypto trading"""
        return self.binance.configure(api_key, secret_key, testnet)

    def get_status(self) -> Dict:
        """Get connection status for all brokers"""
        return {
            "alpaca": {
                "connected": self.alpaca.connected,
                "mode": "paper" if self.alpaca.paper else "live",
                "account": self.alpaca.get_account() if self.alpaca.connected else None
            },
            "binance": {
                "connected": self.binance.connected,
                "mode": "testnet" if self.binance.testnet else "live",
                "account": self.binance.get_account() if self.binance.connected else None
            }
        }

    def get_total_equity(self) -> Dict:
        """Get combined equity from all brokers"""
        total = 0
        breakdown = {}

        if self.alpaca.connected:
            acc = self.alpaca.get_account()
            if "equity" in acc:
                breakdown["alpaca"] = acc["equity"]
                total += acc["equity"]

        if self.binance.connected:
            acc = self.binance.get_account()
            if "total_value" in acc:
                breakdown["binance"] = acc["total_value"]
                total += acc["total_value"]

        return {
            "total_equity": total,
            "breakdown": breakdown,
            "alpaca_connected": self.alpaca.connected,
            "binance_connected": self.binance.connected
        }

    def get_all_positions(self) -> List[UnifiedPosition]:
        """Get all positions from all brokers"""
        positions = []

        # Alpaca positions (stocks)
        if self.alpaca.connected:
            for pos in self.alpaca.get_positions():
                positions.append(UnifiedPosition(
                    symbol=pos.symbol,
                    asset_type="stock",
                    quantity=pos.qty,
                    entry_price=pos.avg_entry_price,
                    current_price=pos.current_price,
                    market_value=pos.market_value,
                    unrealized_pnl=pos.unrealized_pl,
                    unrealized_pnl_pct=pos.unrealized_plpc,
                    broker="alpaca"
                ))

        # Binance positions (crypto)
        if self.binance.connected:
            for pos in self.binance.get_positions():
                if pos.symbol != "USDT" and pos.total > 0:
                    price = self.binance.get_price(pos.symbol)
                    # We don't have entry price from Binance, estimate from current
                    positions.append(UnifiedPosition(
                        symbol=pos.symbol,
                        asset_type="crypto",
                        quantity=pos.total,
                        entry_price=price,  # Approximation
                        current_price=price,
                        market_value=pos.usd_value,
                        unrealized_pnl=0,  # Unknown without entry price
                        unrealized_pnl_pct=0,
                        broker="binance"
                    ))

        return positions

    def buy(self, symbol: str, amount: float = None, qty: float = None) -> Dict:
        """
        Buy an asset - automatically routes to correct broker

        Args:
            symbol: Asset symbol (e.g., 'BTC', 'NVDA')
            amount: Dollar amount to spend
            qty: Quantity to buy (alternative to amount)
        """
        symbol = symbol.upper()
        is_crypto = self._is_crypto(symbol)

        if is_crypto:
            if not self.binance.connected:
                return {"success": False, "error": "Binance not connected. Add API keys in Settings."}
            return self.binance.buy(symbol, qty=qty, quote_qty=amount)
        else:
            if not self.alpaca.connected:
                return {"success": False, "error": "Alpaca not connected. Add API keys in Settings."}
            return self.alpaca.buy(symbol, qty=qty, notional=amount)

    def sell(self, symbol: str, qty: float = None, close_all: bool = False) -> Dict:
        """
        Sell an asset - automatically routes to correct broker

        Args:
            symbol: Asset symbol
            qty: Quantity to sell
            close_all: If True, close entire position
        """
        symbol = symbol.upper()
        is_crypto = self._is_crypto(symbol)

        if is_crypto:
            if not self.binance.connected:
                return {"success": False, "error": "Binance not connected"}
            return self.binance.sell(symbol, qty=qty, sell_all=close_all)
        else:
            if not self.alpaca.connected:
                return {"success": False, "error": "Alpaca not connected"}
            return self.alpaca.sell(symbol, qty=qty, close_all=close_all)

    def close_all_positions(self) -> Dict:
        """Close all positions on all brokers"""
        results = {
            "alpaca": None,
            "binance": None
        }

        if self.alpaca.connected:
            results["alpaca"] = self.alpaca.close_all_positions()

        if self.binance.connected:
            # Binance doesn't have a close-all, we need to sell each
            positions = self.binance.get_positions()
            for pos in positions:
                if pos.symbol != "USDT" and pos.free > 0:
                    self.binance.sell(pos.symbol, sell_all=True)
            results["binance"] = {"success": True, "message": "All crypto positions closed"}

        return results

    def get_price(self, symbol: str) -> float:
        """Get current price for any symbol"""
        symbol = symbol.upper()

        if self._is_crypto(symbol):
            return self.binance.get_price(symbol)
        else:
            if self.alpaca.connected:
                quote = self.alpaca.get_quote(symbol)
                return quote.get("mid", 0)
            return 0

    def can_trade(self, symbol: str) -> Dict:
        """Check if we can trade a symbol"""
        symbol = symbol.upper()
        is_crypto = self._is_crypto(symbol)

        if is_crypto:
            return {
                "can_trade": self.binance.connected,
                "broker": "binance",
                "mode": "testnet" if self.binance.testnet else "live",
                "reason": None if self.binance.connected else "Binance not connected"
            }
        else:
            return {
                "can_trade": self.alpaca.connected,
                "broker": "alpaca",
                "mode": "paper" if self.alpaca.paper else "live",
                "reason": None if self.alpaca.connected else "Alpaca not connected"
            }


# Global instance
broker_manager = BrokerManager()
