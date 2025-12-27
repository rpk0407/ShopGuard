"""
Trading Signals
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SignalType(Enum):
    """Type of trading signal"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class Signal:
    """Trading signal"""
    symbol: str
    signal_type: SignalType
    confidence: float  # 0.0 to 1.0
    price: float
    strategy: str
    reason: str
    timestamp: datetime = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def is_buy(self) -> bool:
        return self.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]

    @property
    def is_sell(self) -> bool:
        return self.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signal": self.signal_type.value,
            "confidence": round(self.confidence * 100, 1),
            "price": self.price,
            "strategy": self.strategy,
            "reason": self.reason,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "timestamp": self.timestamp.isoformat()
        }
