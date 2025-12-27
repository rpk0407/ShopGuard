"""
Broker Adapters for Live Trading

Supports multiple brokers/exchanges:
- Alpaca (US stocks, crypto)
- Binance (Crypto)
- Interactive Brokers (Stocks, Options, Futures)
- Coinbase (Crypto)
- Paper Trading (Demo mode)

Each adapter implements a common interface for:
- Account info
- Order submission
- Position management
- Market data streaming
"""

import os
import json
import time
import hmac
import hashlib
import requests
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import deque
import threading


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AssetClass(Enum):
    STOCK = "stock"
    CRYPTO = "crypto"
    FOREX = "forex"
    FUTURES = "futures"
    OPTIONS = "options"


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    client_order_id: Optional[str] = None
    time_in_force: str = "gtc"


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    asset_class: AssetClass = AssetClass.STOCK
    side: str = "long"


@dataclass
class AccountInfo:
    account_id: str
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    currency: str = "USD"
    is_paper: bool = True
    positions: List[Position] = field(default_factory=list)
    open_orders: List[Order] = field(default_factory=list)


@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: datetime


class BrokerAdapter(ABC):
    """Abstract base class for all broker adapters"""

    def __init__(self, api_key: str = "", api_secret: str = "", paper: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.connected = False
        self.callbacks: Dict[str, List[Callable]] = {
            'order_update': [],
            'position_update': [],
            'quote_update': [],
            'trade_update': []
        }

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the broker"""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the broker"""
        pass

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Get account information"""
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get all positions"""
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol"""
        pass

    @abstractmethod
    def submit_order(self, symbol: str, side: OrderSide, quantity: float,
                     order_type: OrderType = OrderType.MARKET,
                     price: Optional[float] = None,
                     stop_price: Optional[float] = None) -> Order:
        """Submit an order"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order status"""
        pass

    @abstractmethod
    def get_open_orders(self) -> List[Order]:
        """Get all open orders"""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Get current quote for a symbol"""
        pass

    @abstractmethod
    def get_historical_bars(self, symbol: str, timeframe: str,
                            start: datetime, end: datetime) -> List[Dict]:
        """Get historical price bars"""
        pass

    def subscribe_quotes(self, symbols: List[str], callback: Callable):
        """Subscribe to real-time quotes"""
        self.callbacks['quote_update'].append(callback)

    def on_order_update(self, callback: Callable):
        """Register order update callback"""
        self.callbacks['order_update'].append(callback)


class PaperTradingAdapter(BrokerAdapter):
    """
    Paper trading adapter for demo/testing.
    Simulates realistic order execution.
    """

    def __init__(self, initial_capital: float = 100000.0, **kwargs):
        super().__init__(paper=True, **kwargs)
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        self.prices: Dict[str, float] = {}
        self.trade_history: List[Dict] = []
        self.connected = False

        # Simulation settings
        self.slippage = 0.0005  # 0.05% slippage
        self.commission = 0.0  # No commission for paper

    def connect(self) -> bool:
        self.connected = True
        print("[PAPER] Connected to paper trading")
        return True

    def disconnect(self) -> bool:
        self.connected = False
        print("[PAPER] Disconnected from paper trading")
        return True

    def set_price(self, symbol: str, price: float):
        """Set current price for a symbol (for simulation)"""
        self.prices[symbol] = price
        # Update position P&L
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.current_price = price
            if pos.side == "long":
                pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
            else:
                pos.unrealized_pnl = (pos.entry_price - price) * pos.quantity

    def get_account(self) -> AccountInfo:
        positions = list(self.positions.values())
        portfolio_value = self.cash + sum(
            p.quantity * p.current_price for p in positions if p.side == "long"
        )

        return AccountInfo(
            account_id="PAPER-001",
            equity=portfolio_value,
            cash=self.cash,
            buying_power=self.cash,
            portfolio_value=portfolio_value,
            is_paper=True,
            positions=positions,
            open_orders=[o for o in self.orders.values() if o.status == OrderStatus.PENDING]
        )

    def get_positions(self) -> List[Position]:
        return list(self.positions.values())

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def submit_order(self, symbol: str, side: OrderSide, quantity: float,
                     order_type: OrderType = OrderType.MARKET,
                     price: Optional[float] = None,
                     stop_price: Optional[float] = None) -> Order:

        self.order_counter += 1
        order_id = f"PAPER-{self.order_counter:06d}"

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status=OrderStatus.SUBMITTED
        )

        self.orders[order_id] = order

        # Simulate immediate execution for market orders
        if order_type == OrderType.MARKET:
            self._execute_order(order)

        return order

    def _execute_order(self, order: Order):
        """Execute an order (simulate fill)"""
        symbol = order.symbol
        base_price = self.prices.get(symbol, 100.0)

        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = base_price * (1 + self.slippage)
        else:
            fill_price = base_price * (1 - self.slippage)

        # Check if we have enough cash/position
        if order.side == OrderSide.BUY:
            cost = fill_price * order.quantity
            if cost > self.cash:
                order.status = OrderStatus.REJECTED
                return
            self.cash -= cost

            # Update or create position
            if symbol in self.positions:
                pos = self.positions[symbol]
                total_qty = pos.quantity + order.quantity
                pos.entry_price = (pos.entry_price * pos.quantity + fill_price * order.quantity) / total_qty
                pos.quantity = total_qty
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=order.quantity,
                    entry_price=fill_price,
                    current_price=fill_price,
                    unrealized_pnl=0
                )

        else:  # SELL
            if symbol not in self.positions or self.positions[symbol].quantity < order.quantity:
                order.status = OrderStatus.REJECTED
                return

            pos = self.positions[symbol]
            pnl = (fill_price - pos.entry_price) * order.quantity
            self.cash += fill_price * order.quantity
            pos.quantity -= order.quantity
            pos.realized_pnl += pnl

            if pos.quantity == 0:
                del self.positions[symbol]

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.updated_at = datetime.now()

        # Record trade
        self.trade_history.append({
            'order_id': order.order_id,
            'symbol': symbol,
            'side': order.side.value,
            'quantity': order.quantity,
            'price': fill_price,
            'timestamp': datetime.now().isoformat()
        })

        print(f"[PAPER] {order.side.value.upper()} {order.quantity} {symbol} @ ${fill_price:.2f}")

        # Trigger callbacks
        for cb in self.callbacks['order_update']:
            cb(order)

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                return True
        return False

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)

    def get_open_orders(self) -> List[Order]:
        return [o for o in self.orders.values()
                if o.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]]

    def get_quote(self, symbol: str) -> Quote:
        price = self.prices.get(symbol, 100.0)
        spread = price * 0.001  # 0.1% spread

        return Quote(
            symbol=symbol,
            bid=price - spread / 2,
            ask=price + spread / 2,
            last=price,
            volume=1000000,
            timestamp=datetime.now()
        )

    def get_historical_bars(self, symbol: str, timeframe: str,
                            start: datetime, end: datetime) -> List[Dict]:
        # Return empty for paper trading (use external data)
        return []


class AlpacaAdapter(BrokerAdapter):
    """
    Alpaca Markets adapter for US stocks and crypto.
    Supports both paper and live trading.
    """

    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"
    DATA_URL = "https://data.alpaca.markets"

    def __init__(self, api_key: str, api_secret: str, paper: bool = True):
        super().__init__(api_key, api_secret, paper)
        self.base_url = self.PAPER_URL if paper else self.LIVE_URL
        self.headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
            "Content-Type": "application/json"
        }

    def connect(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}/v2/account",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                self.connected = True
                mode = "PAPER" if self.paper else "LIVE"
                print(f"[ALPACA-{mode}] Connected successfully")
                return True
            else:
                print(f"[ALPACA] Connection failed: {response.text}")
                return False
        except Exception as e:
            print(f"[ALPACA] Connection error: {e}")
            return False

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def get_account(self) -> AccountInfo:
        response = requests.get(
            f"{self.base_url}/v2/account",
            headers=self.headers
        )
        data = response.json()

        return AccountInfo(
            account_id=data['id'],
            equity=float(data['equity']),
            cash=float(data['cash']),
            buying_power=float(data['buying_power']),
            portfolio_value=float(data['portfolio_value']),
            is_paper=self.paper,
            positions=self.get_positions()
        )

    def get_positions(self) -> List[Position]:
        response = requests.get(
            f"{self.base_url}/v2/positions",
            headers=self.headers
        )
        positions = []
        for p in response.json():
            positions.append(Position(
                symbol=p['symbol'],
                quantity=float(p['qty']),
                entry_price=float(p['avg_entry_price']),
                current_price=float(p['current_price']),
                unrealized_pnl=float(p['unrealized_pl']),
                asset_class=AssetClass.CRYPTO if '/' in p['symbol'] else AssetClass.STOCK,
                side="long" if float(p['qty']) > 0 else "short"
            ))
        return positions

    def get_position(self, symbol: str) -> Optional[Position]:
        try:
            response = requests.get(
                f"{self.base_url}/v2/positions/{symbol}",
                headers=self.headers
            )
            if response.status_code == 200:
                p = response.json()
                return Position(
                    symbol=p['symbol'],
                    quantity=float(p['qty']),
                    entry_price=float(p['avg_entry_price']),
                    current_price=float(p['current_price']),
                    unrealized_pnl=float(p['unrealized_pl'])
                )
        except:
            pass
        return None

    def submit_order(self, symbol: str, side: OrderSide, quantity: float,
                     order_type: OrderType = OrderType.MARKET,
                     price: Optional[float] = None,
                     stop_price: Optional[float] = None) -> Order:

        order_data = {
            "symbol": symbol,
            "qty": str(quantity),
            "side": side.value,
            "type": order_type.value,
            "time_in_force": "gtc"
        }

        if price:
            order_data["limit_price"] = str(price)
        if stop_price:
            order_data["stop_price"] = str(stop_price)

        response = requests.post(
            f"{self.base_url}/v2/orders",
            headers=self.headers,
            json=order_data
        )

        data = response.json()

        return Order(
            order_id=data['id'],
            symbol=data['symbol'],
            side=OrderSide(data['side']),
            order_type=OrderType(data['type']),
            quantity=float(data['qty']),
            price=float(data.get('limit_price', 0)) or None,
            stop_price=float(data.get('stop_price', 0)) or None,
            status=OrderStatus(data['status'].lower()),
            filled_quantity=float(data.get('filled_qty', 0)),
            filled_price=float(data.get('filled_avg_price', 0) or 0)
        )

    def cancel_order(self, order_id: str) -> bool:
        response = requests.delete(
            f"{self.base_url}/v2/orders/{order_id}",
            headers=self.headers
        )
        return response.status_code == 204

    def get_order(self, order_id: str) -> Optional[Order]:
        response = requests.get(
            f"{self.base_url}/v2/orders/{order_id}",
            headers=self.headers
        )
        if response.status_code == 200:
            data = response.json()
            return Order(
                order_id=data['id'],
                symbol=data['symbol'],
                side=OrderSide(data['side']),
                order_type=OrderType(data['type']),
                quantity=float(data['qty']),
                status=OrderStatus(data['status'].lower()),
                filled_quantity=float(data.get('filled_qty', 0)),
                filled_price=float(data.get('filled_avg_price', 0) or 0)
            )
        return None

    def get_open_orders(self) -> List[Order]:
        response = requests.get(
            f"{self.base_url}/v2/orders?status=open",
            headers=self.headers
        )
        orders = []
        for data in response.json():
            orders.append(Order(
                order_id=data['id'],
                symbol=data['symbol'],
                side=OrderSide(data['side']),
                order_type=OrderType(data['type']),
                quantity=float(data['qty']),
                status=OrderStatus(data['status'].lower())
            ))
        return orders

    def get_quote(self, symbol: str) -> Quote:
        response = requests.get(
            f"{self.DATA_URL}/v2/stocks/{symbol}/quotes/latest",
            headers=self.headers
        )
        data = response.json()['quote']
        return Quote(
            symbol=symbol,
            bid=float(data['bp']),
            ask=float(data['ap']),
            last=(float(data['bp']) + float(data['ap'])) / 2,
            volume=0,
            timestamp=datetime.now()
        )

    def get_historical_bars(self, symbol: str, timeframe: str,
                            start: datetime, end: datetime) -> List[Dict]:
        params = {
            "start": start.isoformat() + "Z",
            "end": end.isoformat() + "Z",
            "timeframe": timeframe
        }
        response = requests.get(
            f"{self.DATA_URL}/v2/stocks/{symbol}/bars",
            headers=self.headers,
            params=params
        )
        return response.json().get('bars', [])


class BinanceAdapter(BrokerAdapter):
    """
    Binance adapter for cryptocurrency trading.
    Supports both testnet (paper) and mainnet (live).
    """

    TESTNET_URL = "https://testnet.binance.vision"
    MAINNET_URL = "https://api.binance.com"

    def __init__(self, api_key: str, api_secret: str, paper: bool = True):
        super().__init__(api_key, api_secret, paper)
        self.base_url = self.TESTNET_URL if paper else self.MAINNET_URL

    def _sign(self, params: Dict) -> str:
        """Generate HMAC signature for authenticated requests"""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, endpoint: str, signed: bool = False, **params) -> Dict:
        """Make API request"""
        headers = {"X-MBX-APIKEY": self.api_key}

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._sign(params)

        url = f"{self.base_url}{endpoint}"

        if method == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            response = requests.post(url, headers=headers, params=params)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, params=params)

        return response.json()

    def connect(self) -> bool:
        try:
            data = self._request("GET", "/api/v3/ping")
            if data == {}:
                self.connected = True
                mode = "TESTNET" if self.paper else "MAINNET"
                print(f"[BINANCE-{mode}] Connected successfully")
                return True
        except Exception as e:
            print(f"[BINANCE] Connection error: {e}")
        return False

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def get_account(self) -> AccountInfo:
        data = self._request("GET", "/api/v3/account", signed=True)

        balances = {b['asset']: float(b['free']) + float(b['locked'])
                    for b in data['balances'] if float(b['free']) > 0 or float(b['locked']) > 0}

        usdt_balance = balances.get('USDT', 0)

        return AccountInfo(
            account_id=str(data.get('uid', 'binance')),
            equity=usdt_balance,
            cash=usdt_balance,
            buying_power=usdt_balance,
            portfolio_value=usdt_balance,
            currency="USDT",
            is_paper=self.paper
        )

    def get_positions(self) -> List[Position]:
        data = self._request("GET", "/api/v3/account", signed=True)
        positions = []

        for b in data['balances']:
            qty = float(b['free']) + float(b['locked'])
            if qty > 0 and b['asset'] != 'USDT':
                symbol = b['asset'] + 'USDT'
                try:
                    ticker = self._request("GET", "/api/v3/ticker/price", symbol=symbol)
                    price = float(ticker['price'])
                    positions.append(Position(
                        symbol=symbol,
                        quantity=qty,
                        entry_price=price,  # We don't have entry price
                        current_price=price,
                        unrealized_pnl=0,
                        asset_class=AssetClass.CRYPTO
                    ))
                except:
                    pass

        return positions

    def get_position(self, symbol: str) -> Optional[Position]:
        positions = self.get_positions()
        for p in positions:
            if p.symbol == symbol:
                return p
        return None

    def submit_order(self, symbol: str, side: OrderSide, quantity: float,
                     order_type: OrderType = OrderType.MARKET,
                     price: Optional[float] = None,
                     stop_price: Optional[float] = None) -> Order:

        params = {
            "symbol": symbol,
            "side": side.value.upper(),
            "type": order_type.value.upper(),
            "quantity": f"{quantity:.8f}"
        }

        if order_type == OrderType.LIMIT:
            params["price"] = f"{price:.8f}"
            params["timeInForce"] = "GTC"
        elif order_type == OrderType.STOP_LIMIT:
            params["price"] = f"{price:.8f}"
            params["stopPrice"] = f"{stop_price:.8f}"
            params["timeInForce"] = "GTC"

        data = self._request("POST", "/api/v3/order", signed=True, **params)

        return Order(
            order_id=str(data['orderId']),
            symbol=data['symbol'],
            side=OrderSide(data['side'].lower()),
            order_type=OrderType(data['type'].lower()),
            quantity=float(data['origQty']),
            price=float(data.get('price', 0)) or None,
            status=self._map_status(data['status']),
            filled_quantity=float(data.get('executedQty', 0))
        )

    def _map_status(self, binance_status: str) -> OrderStatus:
        mapping = {
            'NEW': OrderStatus.SUBMITTED,
            'PARTIALLY_FILLED': OrderStatus.PARTIAL,
            'FILLED': OrderStatus.FILLED,
            'CANCELED': OrderStatus.CANCELLED,
            'REJECTED': OrderStatus.REJECTED,
            'EXPIRED': OrderStatus.EXPIRED
        }
        return mapping.get(binance_status, OrderStatus.PENDING)

    def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        try:
            self._request("DELETE", "/api/v3/order", signed=True,
                          symbol=symbol, orderId=order_id)
            return True
        except:
            return False

    def get_order(self, order_id: str, symbol: str = "") -> Optional[Order]:
        try:
            data = self._request("GET", "/api/v3/order", signed=True,
                                 symbol=symbol, orderId=order_id)
            return Order(
                order_id=str(data['orderId']),
                symbol=data['symbol'],
                side=OrderSide(data['side'].lower()),
                order_type=OrderType(data['type'].lower()),
                quantity=float(data['origQty']),
                status=self._map_status(data['status']),
                filled_quantity=float(data.get('executedQty', 0))
            )
        except:
            return None

    def get_open_orders(self) -> List[Order]:
        data = self._request("GET", "/api/v3/openOrders", signed=True)
        return [Order(
            order_id=str(o['orderId']),
            symbol=o['symbol'],
            side=OrderSide(o['side'].lower()),
            order_type=OrderType(o['type'].lower()),
            quantity=float(o['origQty']),
            status=self._map_status(o['status'])
        ) for o in data]

    def get_quote(self, symbol: str) -> Quote:
        ticker = self._request("GET", "/api/v3/ticker/bookTicker", symbol=symbol)
        return Quote(
            symbol=symbol,
            bid=float(ticker['bidPrice']),
            ask=float(ticker['askPrice']),
            last=(float(ticker['bidPrice']) + float(ticker['askPrice'])) / 2,
            volume=float(ticker.get('bidQty', 0)),
            timestamp=datetime.now()
        )

    def get_historical_bars(self, symbol: str, timeframe: str,
                            start: datetime, end: datetime) -> List[Dict]:
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h',
            '4h': '4h', '1d': '1d', '1w': '1w'
        }
        interval = interval_map.get(timeframe, '1h')

        data = self._request("GET", "/api/v3/klines",
                             symbol=symbol,
                             interval=interval,
                             startTime=int(start.timestamp() * 1000),
                             endTime=int(end.timestamp() * 1000),
                             limit=1000)

        return [{'t': k[0], 'o': k[1], 'h': k[2], 'l': k[3], 'c': k[4], 'v': k[5]} for k in data]


class BrokerFactory:
    """Factory for creating broker adapters"""

    @staticmethod
    def create(broker_type: str, api_key: str = "", api_secret: str = "",
               paper: bool = True, **kwargs) -> BrokerAdapter:

        brokers = {
            'paper': PaperTradingAdapter,
            'alpaca': AlpacaAdapter,
            'binance': BinanceAdapter,
        }

        broker_class = brokers.get(broker_type.lower())
        if not broker_class:
            raise ValueError(f"Unknown broker type: {broker_type}")

        if broker_type.lower() == 'paper':
            return broker_class(**kwargs)

        return broker_class(api_key, api_secret, paper)


class MultiBrokerManager:
    """
    Manages multiple broker connections.
    Allows trading across different exchanges.
    """

    def __init__(self):
        self.brokers: Dict[str, BrokerAdapter] = {}
        self.default_broker: Optional[str] = None

    def add_broker(self, name: str, broker: BrokerAdapter, default: bool = False):
        """Add a broker"""
        self.brokers[name] = broker
        if default or self.default_broker is None:
            self.default_broker = name

    def get_broker(self, name: Optional[str] = None) -> BrokerAdapter:
        """Get a broker by name or default"""
        name = name or self.default_broker
        if name not in self.brokers:
            raise ValueError(f"Broker not found: {name}")
        return self.brokers[name]

    def connect_all(self) -> Dict[str, bool]:
        """Connect all brokers"""
        results = {}
        for name, broker in self.brokers.items():
            results[name] = broker.connect()
        return results

    def disconnect_all(self):
        """Disconnect all brokers"""
        for broker in self.brokers.values():
            broker.disconnect()

    def get_total_equity(self) -> float:
        """Get total equity across all brokers"""
        total = 0
        for broker in self.brokers.values():
            if broker.connected:
                account = broker.get_account()
                total += account.equity
        return total

    def get_all_positions(self) -> Dict[str, List[Position]]:
        """Get positions from all brokers"""
        positions = {}
        for name, broker in self.brokers.items():
            if broker.connected:
                positions[name] = broker.get_positions()
        return positions
