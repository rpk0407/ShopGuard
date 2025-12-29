"""
Binance Broker Integration
- Spot trading for crypto
- Testnet for paper trading
- Real trading with API keys

Get your API keys at: https://www.binance.com/en/my/settings/api-management
For testnet: https://testnet.binance.vision/
"""
import hmac
import hashlib
import time
import requests
from dataclasses import dataclass
from typing import Optional, List, Dict
from urllib.parse import urlencode


@dataclass
class BinancePosition:
    symbol: str
    free: float  # Available balance
    locked: float  # In orders
    total: float
    usd_value: float


@dataclass
class BinanceOrder:
    order_id: int
    symbol: str
    side: str
    qty: float
    price: float
    status: str
    time: str


class BinanceBroker:
    """
    Binance Spot Trading API Integration

    Supports:
    - Testnet (paper trading, free)
    - Real trading
    - Market & limit orders
    - All major crypto pairs
    """

    # Testnet URL (safe, no real money)
    TESTNET_URL = "https://testnet.binance.vision"
    # Real trading URL
    LIVE_URL = "https://api.binance.com"

    # Symbol mappings for common names
    SYMBOL_MAP = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT",
        "DOGE": "DOGEUSDT",
        "ADA": "ADAUSDT",
        "AVAX": "AVAXUSDT",
        "DOT": "DOTUSDT",
        "MATIC": "MATICUSDT",
        "LINK": "LINKUSDT"
    }

    def __init__(self, api_key: str = None, secret_key: str = None, testnet: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        self.base_url = self.TESTNET_URL if testnet else self.LIVE_URL
        self.connected = False
        self.account_info = None

        if api_key and secret_key:
            self._test_connection()

    def _sign(self, params: dict) -> str:
        """Create HMAC SHA256 signature"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _headers(self) -> Dict:
        return {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, params: dict = None, signed: bool = False) -> Dict:
        """Make API request to Binance"""
        url = f"{self.base_url}{endpoint}"
        params = params or {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)

        try:
            if method == "GET":
                resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=self._headers(), params=params, timeout=10)
            elif method == "DELETE":
                resp = requests.delete(url, headers=self._headers(), params=params, timeout=10)
            else:
                return {"error": f"Unknown method: {method}"}

            if resp.status_code == 200:
                return resp.json()
            else:
                return {"error": resp.text, "status": resp.status_code}
        except Exception as e:
            return {"error": str(e)}

    def _test_connection(self) -> bool:
        """Test API connection"""
        result = self._request("GET", "/api/v3/account", signed=True)
        if "error" not in result:
            self.connected = True
            self.account_info = result
            return True
        self.connected = False
        return False

    def configure(self, api_key: str, secret_key: str, testnet: bool = True) -> Dict:
        """Configure API credentials"""
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        self.base_url = self.TESTNET_URL if testnet else self.LIVE_URL

        if self._test_connection():
            # Get USDT balance
            balances = self.account_info.get("balances", [])
            usdt = next((b for b in balances if b["asset"] == "USDT"), {"free": "0", "locked": "0"})

            return {
                "success": True,
                "message": f"Connected to Binance {'Testnet' if testnet else 'LIVE'}",
                "account": {
                    "usdt_free": float(usdt.get("free", 0)),
                    "usdt_locked": float(usdt.get("locked", 0)),
                    "can_trade": self.account_info.get("canTrade", False)
                }
            }
        return {"success": False, "error": "Failed to connect. Check your API keys."}

    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Binance format"""
        symbol = symbol.upper()
        if symbol in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[symbol]
        if not symbol.endswith("USDT"):
            return f"{symbol}USDT"
        return symbol

    def get_account(self) -> Dict:
        """Get account information"""
        if not self.connected:
            return {"error": "Not connected"}

        result = self._request("GET", "/api/v3/account", signed=True)
        if "error" in result:
            return result

        balances = result.get("balances", [])
        usdt = next((b for b in balances if b["asset"] == "USDT"), {"free": "0", "locked": "0"})

        # Calculate total portfolio value
        total_value = float(usdt.get("free", 0)) + float(usdt.get("locked", 0))

        return {
            "usdt_balance": float(usdt.get("free", 0)),
            "usdt_locked": float(usdt.get("locked", 0)),
            "total_value": total_value,
            "can_trade": result.get("canTrade", False)
        }

    def get_positions(self) -> List[BinancePosition]:
        """Get all non-zero balances"""
        if not self.connected:
            return []

        result = self._request("GET", "/api/v3/account", signed=True)
        if "error" in result:
            return []

        positions = []
        for balance in result.get("balances", []):
            free = float(balance.get("free", 0))
            locked = float(balance.get("locked", 0))
            total = free + locked

            if total > 0:
                # Get USD value
                usd_value = total
                if balance["asset"] != "USDT":
                    price = self.get_price(balance["asset"])
                    usd_value = total * price

                positions.append(BinancePosition(
                    symbol=balance["asset"],
                    free=free,
                    locked=locked,
                    total=total,
                    usd_value=usd_value
                ))

        return positions

    def get_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        binance_symbol = self._normalize_symbol(symbol)

        result = self._request("GET", "/api/v3/ticker/price", params={"symbol": binance_symbol})
        if "error" in result:
            return 0

        return float(result.get("price", 0))

    def buy(self, symbol: str, qty: float = None, quote_qty: float = None) -> Dict:
        """
        Place a buy order

        Args:
            symbol: Crypto symbol (e.g., 'BTC', 'ETH')
            qty: Amount of crypto to buy
            quote_qty: Dollar amount to spend (alternative to qty)
        """
        if not self.connected:
            return {"success": False, "error": "Not connected to Binance"}

        binance_symbol = self._normalize_symbol(symbol)

        params = {
            "symbol": binance_symbol,
            "side": "BUY",
            "type": "MARKET"
        }

        if quote_qty:
            params["quoteOrderQty"] = str(quote_qty)
        elif qty:
            params["quantity"] = str(qty)
        else:
            return {"success": False, "error": "Must specify qty or quote_qty"}

        result = self._request("POST", "/api/v3/order", params=params, signed=True)

        if "error" in result:
            return {"success": False, "error": result["error"]}

        return {
            "success": True,
            "order_id": result.get("orderId"),
            "symbol": symbol.upper(),
            "side": "buy",
            "executed_qty": result.get("executedQty"),
            "price": result.get("fills", [{}])[0].get("price", 0) if result.get("fills") else 0,
            "status": result.get("status"),
            "message": f"Bought {result.get('executedQty')} {symbol.upper()}"
        }

    def sell(self, symbol: str, qty: float = None, sell_all: bool = False) -> Dict:
        """
        Place a sell order

        Args:
            symbol: Crypto symbol
            qty: Amount to sell
            sell_all: If True, sell entire balance
        """
        if not self.connected:
            return {"success": False, "error": "Not connected to Binance"}

        binance_symbol = self._normalize_symbol(symbol)

        if sell_all:
            # Get current balance
            positions = self.get_positions()
            pos = next((p for p in positions if p.symbol == symbol.upper()), None)
            if not pos or pos.free <= 0:
                return {"success": False, "error": f"No {symbol} to sell"}
            qty = pos.free

        if not qty:
            return {"success": False, "error": "Must specify qty or use sell_all=True"}

        params = {
            "symbol": binance_symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": str(qty)
        }

        result = self._request("POST", "/api/v3/order", params=params, signed=True)

        if "error" in result:
            return {"success": False, "error": result["error"]}

        return {
            "success": True,
            "order_id": result.get("orderId"),
            "symbol": symbol.upper(),
            "side": "sell",
            "executed_qty": result.get("executedQty"),
            "price": result.get("fills", [{}])[0].get("price", 0) if result.get("fills") else 0,
            "status": result.get("status"),
            "message": f"Sold {result.get('executedQty')} {symbol.upper()}"
        }

    def get_orders(self, symbol: str = None) -> List[Dict]:
        """Get open orders"""
        if not self.connected:
            return []

        params = {}
        if symbol:
            params["symbol"] = self._normalize_symbol(symbol)

        result = self._request("GET", "/api/v3/openOrders", params=params, signed=True)
        if isinstance(result, list):
            return result
        return []

    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel an order"""
        if not self.connected:
            return {"success": False, "error": "Not connected"}

        params = {
            "symbol": self._normalize_symbol(symbol),
            "orderId": order_id
        }

        result = self._request("DELETE", "/api/v3/order", params=params, signed=True)
        return {"success": "error" not in result}

    def get_trade_history(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get trade history for a symbol"""
        if not self.connected:
            return []

        params = {
            "symbol": self._normalize_symbol(symbol),
            "limit": limit
        }

        result = self._request("GET", "/api/v3/myTrades", params=params, signed=True)
        if isinstance(result, list):
            return result
        return []


# Global instance
binance = BinanceBroker()
