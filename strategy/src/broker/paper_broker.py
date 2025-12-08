"""Paper broker for simulated order execution."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx
import structlog

from ..config import get_settings
from ..models import (
    Account,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    Trade,
)
from ..storage import Database

logger = structlog.get_logger()


class PaperBroker:
    """Simulated broker for paper trading."""

    # Binance fee structure (VIP 0)
    MAKER_FEE = Decimal("0.001")  # 0.1%
    TAKER_FEE = Decimal("0.001")  # 0.1%

    def __init__(self, db: Database) -> None:
        """Initialize the paper broker."""
        self.db = db
        self.settings = get_settings()
        self._order_counter = 0

        # Account state (loaded from DB on startup)
        self.account = Account(
            balance=Decimal(str(self.settings.initial_balance)),
            equity=Decimal(str(self.settings.initial_balance)),
            initial_balance=Decimal(str(self.settings.initial_balance)),
        )

        # Position cache
        self.positions: dict[str, Position] = {}

        # HTTP client for risk gateway
        self._http_client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize broker state from database."""
        # Load positions from database
        positions = await self.db.get_all_positions()
        self.positions = {p.symbol: p for p in positions}

        # Calculate account equity
        self._update_account_equity()

        self._http_client = httpx.AsyncClient(
            base_url=self.settings.core_api_url,
            timeout=5.0,
        )

        logger.info(
            "broker_initialized",
            balance=str(self.account.balance),
            positions=len(self.positions),
        )

    async def close(self) -> None:
        """Close the broker."""
        if self._http_client:
            await self._http_client.aclose()

    def _generate_order_id(self) -> str:
        """Generate a unique order ID."""
        self._order_counter += 1
        return f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self._order_counter}"

    def _generate_trade_id(self) -> str:
        """Generate a unique trade ID."""
        return f"TRD-{uuid.uuid4().hex[:12]}"

    def _calculate_fee(self, price: Decimal, quantity: Decimal, is_maker: bool = False) -> Decimal:
        """Calculate trading fee."""
        fee_rate = self.MAKER_FEE if is_maker else self.TAKER_FEE
        return price * quantity * fee_rate

    def _update_account_equity(self) -> None:
        """Update account equity based on positions."""
        # In real implementation, we'd need current prices
        # For now, equity = balance + sum of unrealized PnL
        unrealized_pnl = sum(
            p.unrealized_pnl for p in self.positions.values()
        )
        self.account.equity = self.account.balance + unrealized_pnl

    async def check_risk(self, symbol: str, side: Side, quantity: Decimal) -> tuple[bool, Optional[str], Optional[Decimal]]:
        """Check order against risk rules via core API."""
        if not self._http_client:
            logger.warning("risk_gateway_not_available")
            return True, None, None

        try:
            response = await self._http_client.post(
                "/check-order",
                json={
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": float(quantity),
                },
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("approved"):
                return False, data.get("reason"), None

            if data.get("adjusted"):
                return True, data.get("reason"), Decimal(str(data["adjusted_qty"]))

            return True, None, None

        except Exception as e:
            logger.warning("risk_check_failed", error=str(e))
            # Fall back to basic local checks
            return self._local_risk_check(symbol, side, quantity)

    def _local_risk_check(self, symbol: str, side: Side, quantity: Decimal) -> tuple[bool, Optional[str], Optional[Decimal]]:
        """Basic local risk checks as fallback."""
        max_pos = Decimal(str(self.settings.max_position_size))
        current_pos = self.positions.get(symbol)
        current_qty = current_pos.quantity if current_pos else Decimal("0")

        new_qty = current_qty + quantity if side == Side.BUY else current_qty - quantity

        if abs(new_qty) > max_pos:
            allowed = max_pos - abs(current_qty)
            if allowed <= 0:
                return False, "Position limit reached", None
            return True, "Adjusted for position limit", allowed

        return True, None, None

    async def submit_order(
        self,
        symbol: str,
        side: Side,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        order_type: OrderType = OrderType.MARKET,
    ) -> Optional[Order]:
        """Submit an order for execution."""
        # Check daily trade limit
        trades_today = await self.db.get_trade_count_today()
        if trades_today >= self.settings.max_daily_trades:
            logger.warning("daily_trade_limit_reached", count=trades_today)
            return None

        # Risk check
        approved, reason, adjusted_qty = await self.check_risk(symbol, side, quantity)
        if not approved:
            logger.warning("order_rejected_risk", symbol=symbol, reason=reason)
            return None

        if adjusted_qty:
            logger.info("order_quantity_adjusted", original=str(quantity), adjusted=str(adjusted_qty))
            quantity = adjusted_qty

        # Create order
        order = Order(
            id=self._generate_order_id(),
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )

        await self.db.save_order(order)
        logger.info("order_submitted", order_id=order.id, symbol=symbol, side=side.value)

        return order

    async def execute_market_order(
        self,
        order: Order,
        current_price: Decimal,
        slippage_bps: Decimal = Decimal("5"),
    ) -> Optional[Trade]:
        """Execute a market order with simulated slippage."""
        # Apply slippage
        slippage = current_price * slippage_bps / Decimal("10000")
        if order.side == Side.BUY:
            fill_price = current_price + slippage
        else:
            fill_price = current_price - slippage

        # Calculate fee
        fee = self._calculate_fee(fill_price, order.quantity)

        # Calculate P&L if closing position
        pnl: Optional[Decimal] = None
        position = self.positions.get(order.symbol)

        if position and position.quantity != 0:
            # Check if this is a closing trade
            is_closing = (
                (position.quantity > 0 and order.side == Side.SELL) or
                (position.quantity < 0 and order.side == Side.BUY)
            )
            if is_closing:
                close_qty = min(abs(position.quantity), order.quantity)
                if position.quantity > 0:
                    pnl = (fill_price - position.entry_price) * close_qty - fee
                else:
                    pnl = (position.entry_price - fill_price) * close_qty - fee

        # Create trade
        trade = Trade(
            id=self._generate_trade_id(),
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            fee=fee,
            pnl=pnl,
        )

        # Update order status
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.updated_at = datetime.utcnow()

        # Update position
        await self._update_position(order.symbol, order.side, order.quantity, fill_price, pnl)

        # Update account balance
        cost = fill_price * order.quantity + fee
        if order.side == Side.BUY:
            self.account.balance -= cost
        else:
            self.account.balance += cost - (fee * 2)  # fee already deducted

        if pnl:
            self.account.total_pnl += pnl
            self.account.total_trades += 1

        self._update_account_equity()

        # Persist
        await self.db.save_trade(trade)
        await self.db.save_order(order)

        logger.info(
            "trade_executed",
            trade_id=trade.id,
            symbol=order.symbol,
            side=order.side.value,
            price=str(fill_price),
            quantity=str(order.quantity),
            pnl=str(pnl) if pnl else None,
        )

        return trade

    async def _update_position(
        self,
        symbol: str,
        side: Side,
        quantity: Decimal,
        price: Decimal,
        pnl: Optional[Decimal],
    ) -> None:
        """Update position after a trade."""
        position = self.positions.get(symbol)

        if position is None:
            # New position
            qty = quantity if side == Side.BUY else -quantity
            position = Position(
                symbol=symbol,
                quantity=qty,
                entry_price=price,
            )
        else:
            current_qty = position.quantity
            trade_qty = quantity if side == Side.BUY else -quantity
            new_qty = current_qty + trade_qty

            if new_qty == 0:
                # Position closed
                position.quantity = Decimal("0")
                position.realized_pnl += pnl or Decimal("0")
            elif (current_qty > 0 and new_qty > 0) or (current_qty < 0 and new_qty < 0):
                # Adding to position - calculate new average price
                if current_qty != 0:
                    total_cost = position.entry_price * abs(current_qty) + price * quantity
                    position.entry_price = total_cost / abs(new_qty)
                position.quantity = new_qty
            else:
                # Position flipped
                position.quantity = new_qty
                position.entry_price = price
                if pnl:
                    position.realized_pnl += pnl

            position.updated_at = datetime.utcnow()

        self.positions[symbol] = position
        await self.db.save_position(position)

        # Update risk gateway
        if self._http_client:
            try:
                await self._http_client.post(
                    "/update-position",
                    json={
                        "symbol": symbol,
                        "quantity": float(position.quantity),
                        "entry_price": float(position.entry_price),
                    },
                )
            except Exception as e:
                logger.warning("failed_to_update_risk_position", error=str(e))

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for a symbol."""
        return self.positions.get(symbol)

    def get_account(self) -> Account:
        """Get current account state."""
        self.account.positions = list(self.positions.values())
        return self.account
