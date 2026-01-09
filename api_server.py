#!/usr/bin/env python3
"""
ShopGuard Trading Platform - RESTful API Server

Provides programmatic access to:
- Trading operations (orders, positions)
- Market data
- Strategy management
- Portfolio analytics
- System status

Run: python api_server.py
API Docs: http://localhost:8000/docs
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import secrets
import uvicorn

# =============================================================================
# Configuration
# =============================================================================

API_KEYS = {
    # Generate your API keys with: secrets.token_urlsafe(32)
    "demo_key_" + hashlib.sha256("shopguard".encode()).hexdigest()[:16]: "demo_user"
}

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="ShopGuard Trading API",
    description="RESTful API for algorithmic trading platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Models (Pydantic)
# =============================================================================

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class CreateOrderRequest(BaseModel):
    symbol: str = Field(..., example="AAPL")
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: float = Field(..., gt=0, example=100)
    price: Optional[float] = Field(None, gt=0, example=150.50)
    stop_price: Optional[float] = Field(None, gt=0)
    time_in_force: str = Field("gtc", example="gtc")


class OrderResponse(BaseModel):
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    status: OrderStatus
    filled_quantity: float
    created_at: datetime
    updated_at: datetime


class Position(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    market_value: float


class PortfolioSummary(BaseModel):
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    positions: List[Position]


class StrategyStatus(BaseModel):
    name: str
    state: str
    symbols: List[str]
    active_positions: int
    total_trades: int
    win_rate: float
    sharpe_ratio: Optional[float]
    total_pnl: float


class MarketQuote(BaseModel):
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: datetime


class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: float


# =============================================================================
# Security
# =============================================================================

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key authentication"""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key"
        )

    if api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )

    return API_KEYS[api_key]


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", tags=["General"])
async def root():
    """API root - returns basic info"""
    return {
        "name": "ShopGuard Trading API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthCheck, tags=["General"])
async def health_check():
    """Health check endpoint"""
    import time
    start_time = time.time()  # Would be set at app startup

    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        version="1.0.0",
        uptime_seconds=time.time() - start_time
    )


# -----------------------------------------------------------------------------
# Orders
# -----------------------------------------------------------------------------

@app.post("/orders", response_model=OrderResponse, tags=["Trading"])
async def create_order(
    order: CreateOrderRequest,
    user: str = Depends(verify_api_key)
):
    """
    Create a new order

    - **symbol**: Stock/crypto symbol (e.g., AAPL, BTCUSDT)
    - **side**: buy or sell
    - **order_type**: market, limit, stop, or stop_limit
    - **quantity**: Number of shares/coins
    - **price**: Limit price (required for limit orders)
    - **stop_price**: Stop price (required for stop orders)
    """
    try:
        from trading.broker_adapters import PaperBroker, OrderSide as BrokerOrderSide, OrderType as BrokerOrderType

        # For demo, use paper broker
        broker = PaperBroker(initial_capital=100000)
        broker.connect()

        # Map API types to broker types
        broker_side = BrokerOrderSide.BUY if order.side == OrderSide.BUY else BrokerOrderSide.SELL
        broker_type = {
            OrderType.MARKET: BrokerOrderType.MARKET,
            OrderType.LIMIT: BrokerOrderType.LIMIT,
            OrderType.STOP: BrokerOrderType.STOP,
            OrderType.STOP_LIMIT: BrokerOrderType.STOP_LIMIT
        }[order.order_type]

        # Submit order
        submitted_order = broker.submit_order(
            symbol=order.symbol,
            side=broker_side,
            order_type=broker_type,
            quantity=order.quantity,
            price=order.price,
            stop_price=order.stop_price
        )

        return OrderResponse(
            order_id=submitted_order.order_id,
            symbol=submitted_order.symbol,
            side=OrderSide.BUY if submitted_order.side == BrokerOrderSide.BUY else OrderSide.SELL,
            order_type=order.order_type,
            quantity=submitted_order.quantity,
            price=submitted_order.price,
            status=OrderStatus(submitted_order.status.value),
            filled_quantity=submitted_order.filled_quantity,
            created_at=submitted_order.created_at,
            updated_at=submitted_order.updated_at
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/orders", response_model=List[OrderResponse], tags=["Trading"])
async def list_orders(
    status: Optional[OrderStatus] = None,
    symbol: Optional[str] = None,
    limit: int = 100,
    user: str = Depends(verify_api_key)
):
    """
    List orders with optional filters

    - **status**: Filter by order status
    - **symbol**: Filter by symbol
    - **limit**: Maximum number of orders to return
    """
    # Placeholder implementation
    return []


@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["Trading"])
async def get_order(
    order_id: str,
    user: str = Depends(verify_api_key)
):
    """Get order by ID"""
    raise HTTPException(status_code=404, detail="Order not found")


@app.delete("/orders/{order_id}", tags=["Trading"])
async def cancel_order(
    order_id: str,
    user: str = Depends(verify_api_key)
):
    """Cancel an order"""
    return {"message": f"Order {order_id} cancelled"}


# -----------------------------------------------------------------------------
# Positions & Portfolio
# -----------------------------------------------------------------------------

@app.get("/positions", response_model=List[Position], tags=["Portfolio"])
async def list_positions(user: str = Depends(verify_api_key)):
    """List all current positions"""
    try:
        from trading.broker_adapters import PaperBroker

        broker = PaperBroker(initial_capital=100000)
        broker.connect()
        positions = broker.get_positions()

        return [
            Position(
                symbol=p.symbol,
                quantity=p.quantity,
                entry_price=p.entry_price,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                unrealized_pnl_pct=(p.unrealized_pnl / (p.entry_price * abs(p.quantity))) * 100 if p.entry_price > 0 else 0,
                market_value=p.current_price * abs(p.quantity)
            )
            for p in positions
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/portfolio", response_model=PortfolioSummary, tags=["Portfolio"])
async def get_portfolio(user: str = Depends(verify_api_key)):
    """Get portfolio summary"""
    try:
        from trading.broker_adapters import PaperBroker

        broker = PaperBroker(initial_capital=100000)
        broker.connect()
        account = broker.get_account()
        positions = broker.get_positions()

        position_list = [
            Position(
                symbol=p.symbol,
                quantity=p.quantity,
                entry_price=p.entry_price,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                unrealized_pnl_pct=(p.unrealized_pnl / (p.entry_price * abs(p.quantity))) * 100 if p.entry_price > 0 else 0,
                market_value=p.current_price * abs(p.quantity)
            )
            for p in positions
        ]

        total_unrealized = sum(p.unrealized_pnl for p in position_list)

        return PortfolioSummary(
            equity=account.equity,
            cash=account.cash,
            buying_power=account.buying_power,
            portfolio_value=account.portfolio_value,
            daily_pnl=total_unrealized,
            daily_pnl_pct=(total_unrealized / account.equity) * 100 if account.equity > 0 else 0,
            total_pnl=account.equity - 100000,  # Assuming initial capital
            total_pnl_pct=((account.equity - 100000) / 100000) * 100,
            positions=position_list
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Market Data
# -----------------------------------------------------------------------------

@app.get("/market/quote/{symbol}", response_model=MarketQuote, tags=["Market Data"])
async def get_quote(
    symbol: str,
    user: str = Depends(verify_api_key)
):
    """Get real-time quote for a symbol"""
    try:
        from trading.broker_adapters import PaperBroker

        broker = PaperBroker(initial_capital=100000)
        broker.connect()
        quote = broker.get_quote(symbol)

        if quote is None:
            raise HTTPException(status_code=404, detail=f"Quote not found for {symbol}")

        return MarketQuote(
            symbol=quote.symbol,
            bid=quote.bid,
            ask=quote.ask,
            last=quote.last,
            volume=quote.volume,
            timestamp=quote.timestamp
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/quotes", response_model=List[MarketQuote], tags=["Market Data"])
async def get_quotes(
    symbols: str,  # Comma-separated symbols
    user: str = Depends(verify_api_key)
):
    """Get quotes for multiple symbols (comma-separated)"""
    symbol_list = [s.strip() for s in symbols.split(',')]
    quotes = []

    for symbol in symbol_list:
        try:
            quote = await get_quote(symbol, user)
            quotes.append(quote)
        except:
            continue

    return quotes


# -----------------------------------------------------------------------------
# Strategies
# -----------------------------------------------------------------------------

@app.get("/strategies", response_model=List[StrategyStatus], tags=["Strategies"])
async def list_strategies(user: str = Depends(verify_api_key)):
    """List all strategies and their status"""
    # Placeholder - would query strategy manager
    return []


@app.post("/strategies/{strategy_name}/start", tags=["Strategies"])
async def start_strategy(
    strategy_name: str,
    user: str = Depends(verify_api_key)
):
    """Start a strategy"""
    return {"message": f"Strategy {strategy_name} started"}


@app.post("/strategies/{strategy_name}/stop", tags=["Strategies"])
async def stop_strategy(
    strategy_name: str,
    user: str = Depends(verify_api_key)
):
    """Stop a strategy"""
    return {"message": f"Strategy {strategy_name} stopped"}


# -----------------------------------------------------------------------------
# Analytics
# -----------------------------------------------------------------------------

@app.get("/analytics/performance", tags=["Analytics"])
async def get_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: str = Depends(verify_api_key)
):
    """Get performance analytics"""
    return {
        "sharpe_ratio": 1.5,
        "max_drawdown": -0.08,
        "total_return": 0.12,
        "win_rate": 0.58,
        "num_trades": 150
    }


@app.get("/analytics/risk", tags=["Analytics"])
async def get_risk_metrics(user: str = Depends(verify_api_key)):
    """Get current risk metrics"""
    return {
        "var_95": -1500.0,
        "cvar_95": -2200.0,
        "current_drawdown": -0.03,
        "gross_exposure": 0.85,
        "net_exposure": 0.42,
        "leverage": 1.2
    }


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.now().isoformat()}
    )


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ShopGuard Trading API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🚀  SHOPGUARD TRADING API SERVER                          ║
    ║                                                              ║
    ║   API Docs:  http://{args.host}:{args.port}/docs              ║
    ║   ReDoc:     http://{args.host}:{args.port}/redoc             ║
    ║                                                              ║
    ║   Demo API Key: demo_key_{hashlib.sha256("shopguard".encode()).hexdigest()[:16]}    ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )
