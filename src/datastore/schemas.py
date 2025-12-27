"""
Database Schemas

Core data models for the trading system.
These would map to database tables in production.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import json


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    GTC = "gtc"  # Good Till Cancelled


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AssetClass(Enum):
    EQUITY = "equity"
    OPTION = "option"
    FUTURE = "future"
    FOREX = "forex"
    CRYPTO = "crypto"
    BOND = "bond"


@dataclass
class Symbol:
    """
    Security/instrument identifier.

    Schema:
    - symbol: Primary identifier (e.g., "AAPL")
    - exchange: Exchange code (e.g., "NASDAQ")
    - asset_class: Type of asset
    - currency: Quote currency
    - tick_size: Minimum price increment
    - lot_size: Minimum order size
    """
    symbol: str
    exchange: str
    asset_class: AssetClass
    currency: str = "USD"
    tick_size: float = 0.01
    lot_size: int = 1
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None

    def __hash__(self):
        return hash((self.symbol, self.exchange))


@dataclass
class OHLCV:
    """
    OHLCV bar data.

    Schema for time-series database (e.g., TimescaleDB):
    - timestamp: Bar timestamp (indexed, hypertable key)
    - symbol: Security identifier (indexed)
    - timeframe: Bar duration (e.g., "1m", "1h", "1d")
    - open, high, low, close: Prices
    - volume: Trading volume
    - trades: Number of trades
    - vwap: Volume-weighted average price
    """
    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int = 0
    vwap: Optional[float] = None

    @property
    def typical_price(self) -> float:
        """(High + Low + Close) / 3"""
        return (self.high + self.low + self.close) / 3

    @property
    def range(self) -> float:
        """High - Low"""
        return self.high - self.low

    @property
    def body(self) -> float:
        """Close - Open (signed)"""
        return self.close - self.open

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'trades': self.trades,
            'vwap': self.vwap
        }


@dataclass
class MarketData:
    """
    Real-time market data snapshot.

    Schema:
    - timestamp: Data timestamp (indexed)
    - symbol: Security identifier (indexed)
    - bid/ask: Best bid/offer
    - bid_size/ask_size: Depth at best prices
    - last: Last trade price
    - last_size: Last trade size
    - volume: Cumulative day volume
    """
    timestamp: datetime
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: Optional[float] = None
    last_size: Optional[int] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None  # For derivatives

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_bps(self) -> float:
        return self.spread / self.mid * 10000 if self.mid > 0 else 0


@dataclass
class Trade:
    """
    Executed trade record.

    Schema (trade history table):
    - trade_id: Unique trade identifier (primary key)
    - order_id: Parent order (foreign key)
    - timestamp: Execution timestamp (indexed)
    - symbol: Security (indexed)
    - side: Buy or sell
    - quantity: Filled quantity
    - price: Execution price
    - venue: Execution venue
    - fees: Transaction fees
    """
    trade_id: str
    order_id: str
    timestamp: datetime
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    venue: str
    fees: float = 0.0
    metadata: Dict = field(default_factory=dict)

    @property
    def value(self) -> float:
        return self.quantity * self.price

    @property
    def net_value(self) -> float:
        if self.side == OrderSide.BUY:
            return -(self.value + self.fees)
        else:
            return self.value - self.fees

    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'order_id': self.order_id,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': self.quantity,
            'price': self.price,
            'venue': self.venue,
            'fees': self.fees,
            'value': self.value
        }


@dataclass
class Order:
    """
    Order record.

    Schema (order history table):
    - order_id: Unique identifier (primary key)
    - client_order_id: Client-assigned ID (indexed)
    - created_at: Creation timestamp (indexed)
    - symbol: Security (indexed)
    - side: Buy or sell
    - order_type: Market, limit, etc.
    - quantity: Ordered quantity
    - filled_quantity: Executed quantity
    - price: Limit price (if applicable)
    - status: Current status
    - strategy_id: Source strategy (indexed)
    """
    order_id: str
    client_order_id: str
    created_at: datetime
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    filled_quantity: int = 0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    updated_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    avg_fill_price: Optional[float] = None
    strategy_id: Optional[str] = None
    parent_order_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    @property
    def fill_rate(self) -> float:
        return self.filled_quantity / self.quantity if self.quantity > 0 else 0

    @property
    def is_complete(self) -> bool:
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        ]

    def to_dict(self) -> Dict:
        return {
            'order_id': self.order_id,
            'client_order_id': self.client_order_id,
            'created_at': self.created_at.isoformat(),
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'filled_quantity': self.filled_quantity,
            'price': self.price,
            'status': self.status.value,
            'strategy_id': self.strategy_id
        }


@dataclass
class Position:
    """
    Current position.

    Schema (positions table):
    - symbol: Security (primary key with account)
    - account_id: Trading account
    - quantity: Current quantity (signed)
    - avg_price: Average entry price
    - market_price: Current market price
    - realized_pnl: Closed P&L
    - unrealized_pnl: Open P&L
    - updated_at: Last update timestamp
    """
    symbol: str
    account_id: str
    quantity: int
    avg_price: float
    market_price: float
    realized_pnl: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)
    cost_basis: Optional[float] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def unrealized_pnl(self) -> float:
        return (self.market_price - self.avg_price) * self.quantity

    @property
    def market_value(self) -> float:
        return abs(self.quantity * self.market_price)

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'account_id': self.account_id,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'market_price': self.market_price,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': self.total_pnl
        }


@dataclass
class Account:
    """
    Trading account.

    Schema (accounts table):
    - account_id: Unique identifier
    - name: Account name
    - cash: Available cash
    - equity: Total equity
    - margin_used: Margin in use
    - margin_available: Available margin
    """
    account_id: str
    name: str
    cash: float
    equity: float
    margin_used: float = 0.0
    buying_power: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    @property
    def margin_available(self) -> float:
        return max(0, self.equity - self.margin_used)


@dataclass
class Strategy:
    """
    Trading strategy definition.

    Schema (strategies table):
    - strategy_id: Unique identifier
    - name: Strategy name
    - version: Strategy version
    - status: Active, paused, stopped
    - parameters: Strategy configuration
    """
    strategy_id: str
    name: str
    version: str
    status: str = "inactive"
    parameters: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    max_position_size: Optional[float] = None
    max_order_size: Optional[float] = None
    symbols: List[str] = field(default_factory=list)


@dataclass
class Signal:
    """
    Trading signal.

    Schema (signals table):
    - signal_id: Unique identifier
    - timestamp: Signal generation time
    - strategy_id: Source strategy
    - symbol: Target security
    - direction: Long/short/neutral
    - strength: Signal strength
    - confidence: Model confidence
    """
    signal_id: str
    timestamp: datetime
    strategy_id: str
    symbol: str
    direction: float  # -1 to 1
    strength: float  # 0 to 1
    confidence: float  # 0 to 1
    expiry: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        if self.expiry is None:
            return True
        return datetime.now() < self.expiry


@dataclass
class RiskSnapshot:
    """
    Risk metrics snapshot.

    Schema (risk_snapshots table):
    - timestamp: Snapshot time
    - account_id: Account
    - var_95: Value at Risk (95%)
    - var_99: Value at Risk (99%)
    - cvar: Conditional VaR
    - max_drawdown: Current drawdown
    - gross_exposure: Total exposure
    - net_exposure: Net exposure
    """
    timestamp: datetime
    account_id: str
    var_95: float
    var_99: float
    cvar: float
    max_drawdown: float
    gross_exposure: float
    net_exposure: float
    beta: float = 0.0
    sharpe: float = 0.0
    metadata: Dict = field(default_factory=dict)


# SQL Schema Definitions (for reference)
SQL_SCHEMAS = """
-- TimescaleDB hypertable for OHLCV data
CREATE TABLE ohlcv (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    trades INTEGER,
    vwap DOUBLE PRECISION
);
SELECT create_hypertable('ohlcv', 'timestamp');
CREATE INDEX idx_ohlcv_symbol ON ohlcv (symbol, timestamp DESC);

-- Orders table
CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    client_order_id VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    filled_quantity INTEGER DEFAULT 0,
    price DOUBLE PRECISION,
    stop_price DOUBLE PRECISION,
    status VARCHAR(20) NOT NULL,
    strategy_id VARCHAR(50),
    metadata JSONB
);
CREATE INDEX idx_orders_symbol ON orders (symbol, created_at DESC);
CREATE INDEX idx_orders_strategy ON orders (strategy_id, created_at DESC);

-- Trades table
CREATE TABLE trades (
    trade_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50) REFERENCES orders(order_id),
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    venue VARCHAR(50),
    fees DOUBLE PRECISION DEFAULT 0,
    metadata JSONB
);
CREATE INDEX idx_trades_symbol ON trades (symbol, timestamp DESC);
CREATE INDEX idx_trades_order ON trades (order_id);

-- Positions table
CREATE TABLE positions (
    symbol VARCHAR(20) NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    quantity INTEGER NOT NULL,
    avg_price DOUBLE PRECISION NOT NULL,
    market_price DOUBLE PRECISION,
    realized_pnl DOUBLE PRECISION DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL,
    metadata JSONB,
    PRIMARY KEY (symbol, account_id)
);

-- Signals table (TimescaleDB hypertable)
CREATE TABLE signals (
    signal_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction DOUBLE PRECISION,
    strength DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    expiry TIMESTAMPTZ,
    metadata JSONB
);
SELECT create_hypertable('signals', 'timestamp');
CREATE INDEX idx_signals_strategy ON signals (strategy_id, timestamp DESC);
"""
