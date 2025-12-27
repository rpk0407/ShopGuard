"""
Broker Connections
- PaperBroker: Local simulation (no API needed)
- AlpacaBroker: Real paper/live trading via Alpaca (FREE)
"""
import os
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import requests


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Trading order"""
    id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Position:
    """Open position"""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_time: datetime = field(default_factory=datetime.now)

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.entry_price

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0
        return (self.unrealized_pnl / self.cost_basis) * 100


@dataclass
class Account:
    """Trading account"""
    cash: float
    equity: float
    buying_power: float
    positions: Dict[str, Position] = field(default_factory=dict)


class Broker(ABC):
    """Abstract broker interface"""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker"""
        pass

    @abstractmethod
    def get_account(self) -> Account:
        """Get account information"""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Get all positions"""
        pass

    @abstractmethod
    def get_price(self, symbol: str) -> float:
        """Get current price"""
        pass

    @abstractmethod
    def submit_order(self, symbol: str, side: OrderSide, quantity: float,
                     stop_loss: float = None, take_profit: float = None) -> Order:
        """Submit an order"""
        pass

    @abstractmethod
    def close_position(self, symbol: str) -> Order:
        """Close a position"""
        pass


# =============================================================================
# PAPER BROKER (Local simulation - no API needed)
# =============================================================================

class PaperBroker(Broker):
    """
    Paper trading broker - simulates trading locally
    No API keys needed!
    """

    SAVE_FILE = "paper_portfolio.json"

    def __init__(self, initial_capital: float = 100.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.order_counter = 0
        self._prices: Dict[str, float] = {}
        self._load()

    def connect(self) -> bool:
        print("📄 Paper broker connected (local simulation)")
        return True

    def get_account(self) -> Account:
        equity = self.cash + sum(p.market_value for p in self.positions.values())
        return Account(
            cash=self.cash,
            equity=equity,
            buying_power=self.cash,
            positions=self.positions
        )

    def get_positions(self) -> Dict[str, Position]:
        return self.positions

    def set_price(self, symbol: str, price: float):
        """Set price for simulation"""
        self._prices[symbol] = price
        if symbol in self.positions:
            self.positions[symbol].current_price = price

    def get_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 0)

    def submit_order(self, symbol: str, side: OrderSide, quantity: float,
                     stop_loss: float = None, take_profit: float = None) -> Order:
        """Submit a paper order"""
        self.order_counter += 1
        order_id = f"PAPER-{self.order_counter}"

        price = self._prices.get(symbol, 100)

        order = Order(
            id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status=OrderStatus.PENDING
        )

        # Execute immediately (paper trading)
        if side == OrderSide.BUY:
            cost = quantity * price
            if cost > self.cash:
                order.status = OrderStatus.REJECTED
                print(f"❌ Order rejected: Insufficient funds (need ${cost:.2f}, have ${self.cash:.2f})")
            else:
                self.cash -= cost
                if symbol in self.positions:
                    # Add to existing position
                    pos = self.positions[symbol]
                    total_qty = pos.quantity + quantity
                    avg_price = (pos.cost_basis + cost) / total_qty
                    pos.quantity = total_qty
                    pos.entry_price = avg_price
                else:
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        quantity=quantity,
                        entry_price=price,
                        current_price=price,
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                order.status = OrderStatus.FILLED
                order.filled_price = price
                print(f"✅ BOUGHT {quantity:.4f} {symbol} @ ${price:.2f}")

        elif side == OrderSide.SELL:
            if symbol not in self.positions:
                order.status = OrderStatus.REJECTED
                print(f"❌ Order rejected: No position in {symbol}")
            else:
                pos = self.positions[symbol]
                if quantity > pos.quantity:
                    quantity = pos.quantity

                proceeds = quantity * price
                pnl = (price - pos.entry_price) * quantity

                self.cash += proceeds

                if quantity >= pos.quantity:
                    del self.positions[symbol]
                else:
                    pos.quantity -= quantity

                order.status = OrderStatus.FILLED
                order.filled_price = price

                emoji = "📈" if pnl > 0 else "📉"
                print(f"✅ SOLD {quantity:.4f} {symbol} @ ${price:.2f} | P&L: ${pnl:.2f} {emoji}")

        self.orders.append(order)
        self._save()
        return order

    def close_position(self, symbol: str) -> Order:
        """Close entire position"""
        if symbol not in self.positions:
            return None
        pos = self.positions[symbol]
        return self.submit_order(symbol, OrderSide.SELL, pos.quantity)

    def check_stops(self):
        """Check stop loss and take profit for all positions"""
        for symbol, pos in list(self.positions.items()):
            if pos.stop_loss and pos.current_price <= pos.stop_loss:
                print(f"🛑 STOP LOSS triggered for {symbol}")
                self.close_position(symbol)
            elif pos.take_profit and pos.current_price >= pos.take_profit:
                print(f"🎯 TAKE PROFIT triggered for {symbol}")
                self.close_position(symbol)

    def _save(self):
        """Save state to file"""
        data = {
            "cash": self.cash,
            "positions": {
                s: {
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "entry_time": p.entry_time.isoformat()
                } for s, p in self.positions.items()
            }
        }
        with open(self.SAVE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def _load(self):
        """Load state from file"""
        try:
            with open(self.SAVE_FILE, 'r') as f:
                data = json.load(f)
            self.cash = data.get("cash", self.initial_capital)
            for symbol, pos_data in data.get("positions", {}).items():
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=pos_data["quantity"],
                    entry_price=pos_data["entry_price"],
                    current_price=pos_data.get("current_price", pos_data["entry_price"]),
                    stop_loss=pos_data.get("stop_loss"),
                    take_profit=pos_data.get("take_profit"),
                    entry_time=datetime.fromisoformat(pos_data.get("entry_time", datetime.now().isoformat()))
                )
        except FileNotFoundError:
            pass


# =============================================================================
# ALPACA BROKER (Real paper/live trading - FREE)
# =============================================================================

class AlpacaBroker(Broker):
    """
    Alpaca broker - Real paper trading (FREE!)
    Sign up at: https://alpaca.markets

    Set environment variables:
    - ALPACA_API_KEY
    - ALPACA_SECRET_KEY
    """

    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"
    DATA_URL = "https://data.alpaca.markets"

    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.paper = paper
        self.base_url = self.PAPER_URL if paper else self.LIVE_URL

        self.session = requests.Session()
        self.session.headers.update({
            "APCA-API-KEY-ID": self.api_key or "",
            "APCA-API-SECRET-KEY": self.secret_key or ""
        })

        self.connected = False

    def connect(self) -> bool:
        """Connect to Alpaca"""
        if not self.api_key or not self.secret_key:
            print("❌ Alpaca API keys not set!")
            print("   Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
            print("   Or sign up for FREE at: https://alpaca.markets")
            return False

        try:
            resp = self.session.get(f"{self.base_url}/v2/account")
            if resp.status_code == 200:
                account = resp.json()
                mode = "PAPER" if self.paper else "LIVE"
                print(f"✅ Connected to Alpaca ({mode} trading)")
                print(f"   Account: ${float(account['equity']):,.2f}")
                self.connected = True
                return True
            else:
                print(f"❌ Alpaca connection failed: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Alpaca connection error: {e}")
            return False

    def get_account(self) -> Account:
        """Get Alpaca account"""
        if not self.connected:
            return Account(cash=0, equity=0, buying_power=0)

        try:
            resp = self.session.get(f"{self.base_url}/v2/account")
            data = resp.json()

            positions = self.get_positions()

            return Account(
                cash=float(data["cash"]),
                equity=float(data["equity"]),
                buying_power=float(data["buying_power"]),
                positions=positions
            )
        except Exception as e:
            print(f"Error getting account: {e}")
            return Account(cash=0, equity=0, buying_power=0)

    def get_positions(self) -> Dict[str, Position]:
        """Get all Alpaca positions"""
        if not self.connected:
            return {}

        try:
            resp = self.session.get(f"{self.base_url}/v2/positions")
            data = resp.json()

            positions = {}
            for pos in data:
                positions[pos["symbol"]] = Position(
                    symbol=pos["symbol"],
                    quantity=float(pos["qty"]),
                    entry_price=float(pos["avg_entry_price"]),
                    current_price=float(pos["current_price"]),
                    stop_loss=None,
                    take_profit=None
                )
            return positions
        except Exception as e:
            print(f"Error getting positions: {e}")
            return {}

    def get_price(self, symbol: str) -> float:
        """Get current price from Alpaca"""
        try:
            # Try stocks first
            resp = self.session.get(
                f"{self.DATA_URL}/v2/stocks/{symbol}/trades/latest",
                headers={"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.secret_key}
            )
            if resp.status_code == 200:
                return float(resp.json()["trade"]["p"])

            # Try crypto
            resp = self.session.get(
                f"{self.DATA_URL}/v1beta3/crypto/us/latest/trades?symbols={symbol}",
                headers={"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.secret_key}
            )
            if resp.status_code == 200:
                return float(resp.json()["trades"][symbol]["p"])

            return 0
        except:
            return 0

    def submit_order(self, symbol: str, side: OrderSide, quantity: float,
                     stop_loss: float = None, take_profit: float = None) -> Order:
        """Submit order to Alpaca"""
        if not self.connected:
            return Order(id="ERROR", symbol=symbol, side=side, quantity=quantity,
                         price=0, status=OrderStatus.REJECTED)

        try:
            # Submit market order
            order_data = {
                "symbol": symbol,
                "qty": str(quantity),
                "side": side.value,
                "type": "market",
                "time_in_force": "day"
            }

            resp = self.session.post(f"{self.base_url}/v2/orders", json=order_data)

            if resp.status_code in [200, 201]:
                data = resp.json()
                order = Order(
                    id=data["id"],
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=float(data.get("filled_avg_price", 0)),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    status=OrderStatus.FILLED if data["status"] == "filled" else OrderStatus.PENDING
                )

                # Submit bracket orders for SL/TP if filled
                if stop_loss and take_profit and data["status"] == "filled":
                    self._submit_bracket(symbol, side, quantity, stop_loss, take_profit)

                print(f"✅ {side.value.upper()} {quantity} {symbol} submitted to Alpaca")
                return order
            else:
                print(f"❌ Order failed: {resp.text}")
                return Order(id="ERROR", symbol=symbol, side=side, quantity=quantity,
                             price=0, status=OrderStatus.REJECTED)

        except Exception as e:
            print(f"❌ Order error: {e}")
            return Order(id="ERROR", symbol=symbol, side=side, quantity=quantity,
                         price=0, status=OrderStatus.REJECTED)

    def _submit_bracket(self, symbol: str, side: OrderSide, quantity: float,
                        stop_loss: float, take_profit: float):
        """Submit stop loss and take profit orders"""
        try:
            # For a BUY, we need SELL orders for SL/TP
            exit_side = "sell" if side == OrderSide.BUY else "buy"

            # Stop loss
            sl_order = {
                "symbol": symbol,
                "qty": str(quantity),
                "side": exit_side,
                "type": "stop",
                "stop_price": str(stop_loss),
                "time_in_force": "gtc"
            }
            self.session.post(f"{self.base_url}/v2/orders", json=sl_order)

            # Take profit
            tp_order = {
                "symbol": symbol,
                "qty": str(quantity),
                "side": exit_side,
                "type": "limit",
                "limit_price": str(take_profit),
                "time_in_force": "gtc"
            }
            self.session.post(f"{self.base_url}/v2/orders", json=tp_order)

        except Exception as e:
            print(f"Warning: Could not set SL/TP: {e}")

    def close_position(self, symbol: str) -> Order:
        """Close position on Alpaca"""
        if not self.connected:
            return None

        try:
            resp = self.session.delete(f"{self.base_url}/v2/positions/{symbol}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Closed {symbol} position on Alpaca")
                return Order(
                    id=data.get("id", "CLOSED"),
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=float(data.get("qty", 0)),
                    price=float(data.get("filled_avg_price", 0)),
                    status=OrderStatus.FILLED
                )
            return None
        except Exception as e:
            print(f"Error closing position: {e}")
            return None

    def close_all_positions(self):
        """Close all positions"""
        if not self.connected:
            return

        try:
            self.session.delete(f"{self.base_url}/v2/positions")
            print("✅ All positions closed on Alpaca")
        except Exception as e:
            print(f"Error closing all positions: {e}")
