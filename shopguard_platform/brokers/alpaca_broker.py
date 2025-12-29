"""
Alpaca Broker Integration
- Free paper trading for US stocks
- Real trading with approved account
- No minimum balance required

Get your FREE API keys at: https://alpaca.markets
"""
import requests
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class AlpacaOrder:
    id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    qty: float
    filled_qty: float
    avg_price: float
    status: str
    created_at: str


@dataclass
class AlpacaPosition:
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float


class AlpacaBroker:
    """
    Alpaca Trading API Integration

    Supports:
    - Paper trading (free, no real money)
    - Live trading (requires approval)
    - Fractional shares
    - Market & limit orders
    """

    # Paper trading URL (safe, no real money)
    PAPER_URL = "https://paper-api.alpaca.markets"
    # Live trading URL (real money!)
    LIVE_URL = "https://api.alpaca.markets"

    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.base_url = self.PAPER_URL if paper else self.LIVE_URL
        self.connected = False
        self.account_info = None

        if api_key and secret_key:
            self._test_connection()

    def _headers(self) -> Dict:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, data: dict = None) -> Dict:
        """Make API request to Alpaca"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=self._headers(), timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=self._headers(), json=data, timeout=10)
            elif method == "DELETE":
                resp = requests.delete(url, headers=self._headers(), timeout=10)
            else:
                return {"error": f"Unknown method: {method}"}

            if resp.status_code == 200 or resp.status_code == 201:
                return resp.json()
            elif resp.status_code == 204:
                return {"success": True}
            else:
                return {"error": resp.text, "status": resp.status_code}
        except Exception as e:
            return {"error": str(e)}

    def _test_connection(self) -> bool:
        """Test API connection"""
        result = self._request("GET", "/v2/account")
        if "error" not in result:
            self.connected = True
            self.account_info = result
            return True
        self.connected = False
        return False

    def configure(self, api_key: str, secret_key: str, paper: bool = True) -> Dict:
        """Configure API credentials"""
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.base_url = self.PAPER_URL if paper else self.LIVE_URL

        if self._test_connection():
            return {
                "success": True,
                "message": f"Connected to Alpaca {'Paper' if paper else 'LIVE'} Trading",
                "account": {
                    "equity": float(self.account_info.get("equity", 0)),
                    "cash": float(self.account_info.get("cash", 0)),
                    "buying_power": float(self.account_info.get("buying_power", 0)),
                    "status": self.account_info.get("status", "unknown")
                }
            }
        return {"success": False, "error": "Failed to connect. Check your API keys."}

    def get_account(self) -> Dict:
        """Get account information"""
        if not self.connected:
            return {"error": "Not connected"}

        result = self._request("GET", "/v2/account")
        if "error" in result:
            return result

        return {
            "equity": float(result.get("equity", 0)),
            "cash": float(result.get("cash", 0)),
            "buying_power": float(result.get("buying_power", 0)),
            "portfolio_value": float(result.get("portfolio_value", 0)),
            "status": result.get("status", "unknown"),
            "trading_blocked": result.get("trading_blocked", False),
            "pattern_day_trader": result.get("pattern_day_trader", False)
        }

    def get_positions(self) -> List[AlpacaPosition]:
        """Get all open positions"""
        if not self.connected:
            return []

        result = self._request("GET", "/v2/positions")
        if isinstance(result, list):
            return [
                AlpacaPosition(
                    symbol=p["symbol"],
                    qty=float(p["qty"]),
                    avg_entry_price=float(p["avg_entry_price"]),
                    current_price=float(p["current_price"]),
                    market_value=float(p["market_value"]),
                    unrealized_pl=float(p["unrealized_pl"]),
                    unrealized_plpc=float(p["unrealized_plpc"]) * 100
                )
                for p in result
            ]
        return []

    def get_position(self, symbol: str) -> Optional[AlpacaPosition]:
        """Get position for a specific symbol"""
        if not self.connected:
            return None

        result = self._request("GET", f"/v2/positions/{symbol}")
        if "error" in result:
            return None

        return AlpacaPosition(
            symbol=result["symbol"],
            qty=float(result["qty"]),
            avg_entry_price=float(result["avg_entry_price"]),
            current_price=float(result["current_price"]),
            market_value=float(result["market_value"]),
            unrealized_pl=float(result["unrealized_pl"]),
            unrealized_plpc=float(result["unrealized_plpc"]) * 100
        )

    def buy(self, symbol: str, qty: float = None, notional: float = None) -> Dict:
        """
        Place a buy order

        Args:
            symbol: Stock symbol (e.g., 'NVDA', 'SPY')
            qty: Number of shares (can be fractional)
            notional: Dollar amount to buy (alternative to qty)
        """
        if not self.connected:
            return {"success": False, "error": "Not connected to Alpaca"}

        order_data = {
            "symbol": symbol.upper(),
            "side": "buy",
            "type": "market",
            "time_in_force": "day"
        }

        if notional:
            order_data["notional"] = str(notional)
        elif qty:
            order_data["qty"] = str(qty)
        else:
            return {"success": False, "error": "Must specify qty or notional"}

        result = self._request("POST", "/v2/orders", order_data)

        if "error" in result:
            return {"success": False, "error": result["error"]}

        return {
            "success": True,
            "order_id": result.get("id"),
            "symbol": result.get("symbol"),
            "side": "buy",
            "qty": result.get("qty"),
            "status": result.get("status"),
            "message": f"Buy order placed for {symbol}"
        }

    def sell(self, symbol: str, qty: float = None, close_all: bool = False) -> Dict:
        """
        Place a sell order

        Args:
            symbol: Stock symbol
            qty: Number of shares to sell
            close_all: If True, close entire position
        """
        if not self.connected:
            return {"success": False, "error": "Not connected to Alpaca"}

        if close_all:
            # Close entire position
            result = self._request("DELETE", f"/v2/positions/{symbol.upper()}")
            if "error" in result:
                return {"success": False, "error": result["error"]}
            return {
                "success": True,
                "message": f"Closed position in {symbol}",
                "order_id": result.get("id") if isinstance(result, dict) else None
            }

        if not qty:
            return {"success": False, "error": "Must specify qty or use close_all=True"}

        order_data = {
            "symbol": symbol.upper(),
            "side": "sell",
            "qty": str(qty),
            "type": "market",
            "time_in_force": "day"
        }

        result = self._request("POST", "/v2/orders", order_data)

        if "error" in result:
            return {"success": False, "error": result["error"]}

        return {
            "success": True,
            "order_id": result.get("id"),
            "symbol": result.get("symbol"),
            "side": "sell",
            "qty": result.get("qty"),
            "status": result.get("status"),
            "message": f"Sell order placed for {symbol}"
        }

    def close_all_positions(self) -> Dict:
        """Close all open positions"""
        if not self.connected:
            return {"success": False, "error": "Not connected to Alpaca"}

        result = self._request("DELETE", "/v2/positions")

        if "error" in result:
            return {"success": False, "error": result["error"]}

        return {
            "success": True,
            "message": "All positions closed"
        }

    def get_orders(self, status: str = "open") -> List[Dict]:
        """Get orders by status"""
        if not self.connected:
            return []

        result = self._request("GET", f"/v2/orders?status={status}")
        if isinstance(result, list):
            return result
        return []

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        if not self.connected:
            return {"success": False, "error": "Not connected"}

        result = self._request("DELETE", f"/v2/orders/{order_id}")
        return {"success": "error" not in result}

    def get_quote(self, symbol: str) -> Dict:
        """Get latest quote for a symbol"""
        if not self.connected:
            return {}

        # Use data API
        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                quote = data.get("quote", {})
                return {
                    "symbol": symbol,
                    "bid": quote.get("bp", 0),
                    "ask": quote.get("ap", 0),
                    "mid": (quote.get("bp", 0) + quote.get("ap", 0)) / 2
                }
        except:
            pass
        return {}


# Global instance
alpaca = AlpacaBroker()
