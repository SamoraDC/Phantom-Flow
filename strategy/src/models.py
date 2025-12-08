"""Data models for the strategy engine."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Side(str, Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""

    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    """Order status."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PriceLevel(BaseModel):
    """A price level in the order book."""

    price: Decimal
    quantity: Decimal


class OrderBookState(BaseModel):
    """Order book state from market data."""

    symbol: str
    timestamp: int
    last_update_id: int
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    mid_price: Optional[Decimal] = None
    spread_bps: Optional[Decimal] = None
    imbalance: Optional[Decimal] = None
    weighted_imbalance: Optional[Decimal] = None


class Signal(BaseModel):
    """Trading signal from strategy."""

    symbol: str
    side: Side
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_size: Decimal
    reason: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Order(BaseModel):
    """Order model."""

    id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Trade(BaseModel):
    """Trade execution model."""

    id: str
    order_id: str
    symbol: str
    side: Side
    price: Decimal
    quantity: Decimal
    fee: Decimal
    fee_asset: str = "USDT"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pnl: Optional[Decimal] = None


class Position(BaseModel):
    """Position model."""

    symbol: str
    quantity: Decimal  # Positive for long, negative for short
    entry_price: Decimal
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Account(BaseModel):
    """Account state model."""

    balance: Decimal
    equity: Decimal
    positions: list[Position] = Field(default_factory=list)
    initial_balance: Decimal
    total_pnl: Decimal = Decimal("0")
    win_rate: float = 0.0
    total_trades: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HealthStatus(BaseModel):
    """Health check response."""

    status: str
    component: str
    timestamp: datetime
    details: dict = Field(default_factory=dict)


class RiskCheckRequest(BaseModel):
    """Request to check order against risk rules."""

    symbol: str
    side: Side
    quantity: float


class RiskCheckResponse(BaseModel):
    """Response from risk check."""

    approved: bool
    order_id: Optional[str] = None
    adjusted: bool = False
    adjusted_qty: Optional[float] = None
    reason: Optional[str] = None
