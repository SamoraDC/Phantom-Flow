"""SQLite database for trade persistence."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import aiosqlite
import structlog

from ..models import Account, Order, Position, Side, Trade

logger = structlog.get_logger()


def decimal_encoder(obj: object) -> str:
    """JSON encoder for Decimal."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: str) -> None:
        """Initialize database."""
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Connect to the database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info("database_connected", path=self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        assert self._conn is not None

        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price TEXT NOT NULL,
                quantity TEXT NOT NULL,
                fee TEXT NOT NULL,
                fee_asset TEXT NOT NULL,
                pnl TEXT,
                timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity TEXT NOT NULL,
                price TEXT,
                status TEXT NOT NULL,
                filled_quantity TEXT NOT NULL,
                avg_fill_price TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );

            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity TEXT NOT NULL,
                entry_price TEXT NOT NULL,
                unrealized_pnl TEXT NOT NULL,
                realized_pnl TEXT NOT NULL,
                updated_at DATETIME NOT NULL
            );

            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                balance TEXT NOT NULL,
                equity TEXT NOT NULL,
                total_pnl TEXT NOT NULL,
                win_rate REAL NOT NULL,
                total_trades INTEGER NOT NULL,
                positions_json TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                date DATE PRIMARY KEY,
                starting_balance TEXT NOT NULL,
                ending_balance TEXT NOT NULL,
                pnl TEXT NOT NULL,
                trades_count INTEGER NOT NULL,
                winning_trades INTEGER NOT NULL,
                losing_trades INTEGER NOT NULL,
                max_drawdown TEXT NOT NULL,
                sharpe_ratio REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
            CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        """)
        await self._conn.commit()

    async def save_trade(self, trade: Trade) -> None:
        """Save a trade to the database."""
        assert self._conn is not None

        await self._conn.execute(
            """
            INSERT INTO trades (id, order_id, symbol, side, price, quantity, fee, fee_asset, pnl, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.id,
                trade.order_id,
                trade.symbol,
                trade.side.value,
                str(trade.price),
                str(trade.quantity),
                str(trade.fee),
                trade.fee_asset,
                str(trade.pnl) if trade.pnl else None,
                trade.timestamp.isoformat(),
            ),
        )
        await self._conn.commit()
        logger.info("trade_saved", trade_id=trade.id, symbol=trade.symbol)

    async def save_order(self, order: Order) -> None:
        """Save or update an order."""
        assert self._conn is not None

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO orders
            (id, symbol, side, order_type, quantity, price, status, filled_quantity, avg_fill_price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.id,
                order.symbol,
                order.side.value,
                order.order_type.value,
                str(order.quantity),
                str(order.price) if order.price else None,
                order.status.value,
                str(order.filled_quantity),
                str(order.avg_fill_price) if order.avg_fill_price else None,
                order.created_at.isoformat(),
                order.updated_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def save_position(self, position: Position) -> None:
        """Save or update a position."""
        assert self._conn is not None

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO positions
            (symbol, quantity, entry_price, unrealized_pnl, realized_pnl, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                position.symbol,
                str(position.quantity),
                str(position.entry_price),
                str(position.unrealized_pnl),
                str(position.realized_pnl),
                position.updated_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        assert self._conn is not None

        async with self._conn.execute(
            "SELECT * FROM positions WHERE symbol = ?", (symbol,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Position(
                    symbol=row["symbol"],
                    quantity=Decimal(row["quantity"]),
                    entry_price=Decimal(row["entry_price"]),
                    unrealized_pnl=Decimal(row["unrealized_pnl"]),
                    realized_pnl=Decimal(row["realized_pnl"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            return None

    async def get_all_positions(self) -> list[Position]:
        """Get all positions."""
        assert self._conn is not None

        positions = []
        async with self._conn.execute("SELECT * FROM positions") as cursor:
            async for row in cursor:
                positions.append(
                    Position(
                        symbol=row["symbol"],
                        quantity=Decimal(row["quantity"]),
                        entry_price=Decimal(row["entry_price"]),
                        unrealized_pnl=Decimal(row["unrealized_pnl"]),
                        realized_pnl=Decimal(row["realized_pnl"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                )
        return positions

    async def save_account_snapshot(self, account: Account) -> None:
        """Save an account snapshot."""
        assert self._conn is not None

        positions_json = json.dumps(
            [p.model_dump() for p in account.positions], default=decimal_encoder
        )

        await self._conn.execute(
            """
            INSERT INTO account_snapshots
            (balance, equity, total_pnl, win_rate, total_trades, positions_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(account.balance),
                str(account.equity),
                str(account.total_pnl),
                account.win_rate,
                account.total_trades,
                positions_json,
            ),
        )
        await self._conn.commit()

    async def get_trades(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[Trade]:
        """Get trades with optional filters."""
        assert self._conn is not None

        query = "SELECT * FROM trades WHERE 1=1"
        params: list = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())

        query += f" ORDER BY timestamp DESC LIMIT {limit}"

        trades = []
        async with self._conn.execute(query, params) as cursor:
            async for row in cursor:
                trades.append(
                    Trade(
                        id=row["id"],
                        order_id=row["order_id"],
                        symbol=row["symbol"],
                        side=Side(row["side"]),
                        price=Decimal(row["price"]),
                        quantity=Decimal(row["quantity"]),
                        fee=Decimal(row["fee"]),
                        fee_asset=row["fee_asset"],
                        pnl=Decimal(row["pnl"]) if row["pnl"] else None,
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
        return trades

    async def get_trade_count_today(self) -> int:
        """Get number of trades today."""
        assert self._conn is not None

        today = datetime.utcnow().date().isoformat()
        async with self._conn.execute(
            "SELECT COUNT(*) FROM trades WHERE DATE(timestamp) = ?", (today,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


def init_database(db_path: str) -> None:
    """Initialize database synchronously (for startup scripts)."""
    import sqlite3
    from pathlib import Path

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            price TEXT NOT NULL,
            quantity TEXT NOT NULL,
            fee TEXT NOT NULL,
            fee_asset TEXT NOT NULL,
            pnl TEXT,
            timestamp DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            quantity TEXT NOT NULL,
            price TEXT,
            status TEXT NOT NULL,
            filled_quantity TEXT NOT NULL,
            avg_fill_price TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            quantity TEXT NOT NULL,
            entry_price TEXT NOT NULL,
            unrealized_pnl TEXT NOT NULL,
            realized_pnl TEXT NOT NULL,
            updated_at DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS account_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            balance TEXT NOT NULL,
            equity TEXT NOT NULL,
            total_pnl TEXT NOT NULL,
            win_rate REAL NOT NULL,
            total_trades INTEGER NOT NULL,
            positions_json TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            date DATE PRIMARY KEY,
            starting_balance TEXT NOT NULL,
            ending_balance TEXT NOT NULL,
            pnl TEXT NOT NULL,
            trades_count INTEGER NOT NULL,
            winning_trades INTEGER NOT NULL,
            losing_trades INTEGER NOT NULL,
            max_drawdown TEXT NOT NULL,
            sharpe_ratio REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")
