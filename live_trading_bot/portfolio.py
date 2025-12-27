"""
Portfolio Management - Tracks positions and P&L
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import json


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Position:
    """A trading position"""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    entry_time: datetime = None

    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()

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

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": round(self.entry_price, 2),
            "current_price": round(self.current_price, 2),
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2),
            "entry_time": self.entry_time.isoformat() if self.entry_time else None
        }


@dataclass
class Trade:
    """A completed trade"""
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    timestamp: datetime = None
    pnl: float = 0

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": round(self.price, 2),
            "pnl": round(self.pnl, 2),
            "timestamp": self.timestamp.isoformat()
        }


class Portfolio:
    """Portfolio manager for paper/live trading"""

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.realized_pnl = 0.0

    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + positions)"""
        positions_value = sum(p.market_value for p in self.positions.values())
        return self.cash + positions_value

    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized P&L"""
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)"""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def total_return_pct(self) -> float:
        """Total return as percentage"""
        return ((self.total_value - self.initial_capital) / self.initial_capital) * 100

    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions"""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.current_price = prices[symbol]

    def buy(self, symbol: str, quantity: float, price: float) -> bool:
        """
        Buy an asset

        Args:
            symbol: Asset symbol
            quantity: Quantity to buy
            price: Current price

        Returns:
            True if successful
        """
        cost = quantity * price

        if cost > self.cash:
            print(f"Insufficient cash: need ${cost:.2f}, have ${self.cash:.2f}")
            return False

        self.cash -= cost

        if symbol in self.positions:
            # Add to existing position (average in)
            pos = self.positions[symbol]
            total_qty = pos.quantity + quantity
            avg_price = (pos.cost_basis + cost) / total_qty
            pos.quantity = total_qty
            pos.entry_price = avg_price
            pos.current_price = price
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=price,
                current_price=price
            )

        # Record trade
        self.trades.append(Trade(
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            price=price
        ))

        print(f"✅ BOUGHT {quantity} {symbol} @ ${price:.2f} (Total: ${cost:.2f})")
        return True

    def sell(self, symbol: str, quantity: float, price: float) -> bool:
        """
        Sell an asset

        Args:
            symbol: Asset symbol
            quantity: Quantity to sell (use -1 for all)
            price: Current price

        Returns:
            True if successful
        """
        if symbol not in self.positions:
            print(f"No position in {symbol}")
            return False

        pos = self.positions[symbol]

        if quantity == -1:
            quantity = pos.quantity

        if quantity > pos.quantity:
            print(f"Cannot sell {quantity}, only have {pos.quantity}")
            return False

        # Calculate P&L
        proceeds = quantity * price
        cost_basis = quantity * pos.entry_price
        pnl = proceeds - cost_basis

        self.cash += proceeds
        self.realized_pnl += pnl

        if quantity == pos.quantity:
            # Close entire position
            del self.positions[symbol]
        else:
            # Reduce position
            pos.quantity -= quantity
            pos.current_price = price

        # Record trade
        self.trades.append(Trade(
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            price=price,
            pnl=pnl
        ))

        pnl_emoji = "📈" if pnl > 0 else "📉"
        print(f"✅ SOLD {quantity} {symbol} @ ${price:.2f} | P&L: ${pnl:.2f} {pnl_emoji}")
        return True

    def close_all(self, prices: Dict[str, float]):
        """Close all positions"""
        for symbol in list(self.positions.keys()):
            price = prices.get(symbol, self.positions[symbol].current_price)
            self.sell(symbol, -1, price)

    def get_summary(self) -> dict:
        """Get portfolio summary"""
        return {
            "initial_capital": self.initial_capital,
            "cash": round(self.cash, 2),
            "positions_value": round(sum(p.market_value for p in self.positions.values()), 2),
            "total_value": round(self.total_value, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "num_positions": len(self.positions),
            "num_trades": len(self.trades),
            "positions": [p.to_dict() for p in self.positions.values()],
            "recent_trades": [t.to_dict() for t in self.trades[-10:]]
        }

    def save(self, filepath: str):
        """Save portfolio state to file"""
        data = {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "positions": {s: {
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "entry_time": p.entry_time.isoformat() if p.entry_time else None
            } for s, p in self.positions.items()},
            "trades": [t.to_dict() for t in self.trades]
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Portfolio saved to {filepath}")

    def load(self, filepath: str):
        """Load portfolio state from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            self.initial_capital = data["initial_capital"]
            self.cash = data["cash"]
            self.realized_pnl = data.get("realized_pnl", 0)

            self.positions = {}
            for symbol, pos_data in data.get("positions", {}).items():
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=pos_data["quantity"],
                    entry_price=pos_data["entry_price"],
                    current_price=pos_data["current_price"],
                    entry_time=datetime.fromisoformat(pos_data["entry_time"]) if pos_data.get("entry_time") else None
                )

            print(f"Portfolio loaded from {filepath}")
            return True
        except FileNotFoundError:
            print(f"No saved portfolio found at {filepath}")
            return False
        except Exception as e:
            print(f"Error loading portfolio: {e}")
            return False
