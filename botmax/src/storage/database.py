"""Database layer for BotMAX using SQLite with aiosqlite"""

import aiosqlite
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..config import Config
from ..logger import get_logger


logger = get_logger(__name__)


class Database:
    """Database manager for BotMAX"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database and create tables"""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row

        # Create tables
        await self._create_tables()
        logger.info("Database initialized successfully")

    async def _create_tables(self) -> None:
        """Create database tables"""
        # Lottery tickets table
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS lottery_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raffle_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                ticket_number INTEGER NOT NULL,
                status TEXT DEFAULT 'available', -- available, sold, reserved
                price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(raffle_id, ticket_number)
            )
        """)

        # Raffles table
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS raffles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                total_tickets INTEGER NOT NULL,
                price_per_ticket REAL NOT NULL,
                status TEXT DEFAULT 'active', -- active, completed, cancelled
                winner_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP
            )
        """)

        # Participants table
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raffle_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                ticket_count INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (raffle_id) REFERENCES raffles(id)
            )
        """)

        # Payments table
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raffle_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                ticket_count INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'pending', -- pending, completed, failed, refunded
                payment_id TEXT, -- External payment ID
                metadata TEXT, -- JSON for additional data
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (raffle_id) REFERENCES raffles(id)
            )
        """)

        # Create indexes
        await self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_raffle_status 
            ON lottery_tickets(raffle_id, status)
        """)
        await self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_status 
            ON payments(status)
        """)

        await self.connection.commit()

    async def close(self) -> None:
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None

    # Ticket operations
    async def create_ticket(
        self,
        raffle_id: str,
        user_id: int,
        username: str,
        ticket_number: int,
        price: float,
    ) -> int:
        """Create a new lottery ticket"""
        cursor = await self.connection.execute("""
            INSERT INTO lottery_tickets 
            (raffle_id, user_id, username, ticket_number, price)
            VALUES (?, ?, ?, ?, ?)
        """, (raffle_id, user_id, username, ticket_number, price))
        await self.connection.commit()
        return cursor.lastrowid

    async def get_available_tickets(self, raffle_id: str) -> List[Dict[str, Any]]:
        """Get all available tickets for a raffle"""
        cursor = await self.connection.execute("""
            SELECT * FROM lottery_tickets 
            WHERE raffle_id = ? AND status = 'available'
            ORDER BY ticket_number
        """, (raffle_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def sell_ticket(self, ticket_id: int, user_id: int) -> bool:
        """Mark ticket as sold to a user"""
        cursor = await self.connection.execute("""
            UPDATE lottery_tickets 
            SET status = 'sold', user_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'available'
        """, (user_id, ticket_id))
        await self.connection.commit()
        return cursor.rowcount > 0

    async def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Get ticket by ID"""
        cursor = await self.connection.execute("""
            SELECT * FROM lottery_tickets WHERE id = ?
        """, (ticket_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    # Raffle operations
    async def create_raffle(
        self,
        raffle_id: str,
        title: str,
        description: str,
        total_tickets: int,
        price_per_ticket: float,
    ) -> None:
        """Create a new raffle"""
        await self.connection.execute("""
            INSERT INTO raffles 
            (id, title, description, total_tickets, price_per_ticket)
            VALUES (?, ?, ?, ?, ?)
        """, (raffle_id, title, description, total_tickets, price_per_ticket))
        await self.connection.commit()

    async def get_raffle(self, raffle_id: str) -> Optional[Dict[str, Any]]:
        """Get raffle by ID"""
        cursor = await self.connection.execute("""
            SELECT * FROM raffles WHERE id = ?
        """, (raffle_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_raffle_status(
        self, raffle_id: str, status: str, winner_user_id: Optional[int] = None
    ) -> None:
        """Update raffle status"""
        if winner_user_id is not None:
            await self.connection.execute("""
                UPDATE raffles 
                SET status = ?, winner_user_id = ?, ended_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, winner_user_id, raffle_id))
        else:
            await self.connection.execute("""
                UPDATE raffles 
                SET status = ?, ended_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, raffle_id))
        await self.connection.commit()

    # Participant operations
    async def add_participant(
        self, raffle_id: str, user_id: int, username: str, ticket_count: int = 1
    ) -> None:
        """Add participant to raffle"""
        await self.connection.execute("""
            INSERT OR REPLACE INTO participants 
            (raffle_id, user_id, username, ticket_count)
            VALUES (?, ?, ?, ?)
        """, (raffle_id, user_id, username, ticket_count))
        await self.connection.commit()

    async def get_participants(self, raffle_id: str) -> List[Dict[str, Any]]:
        """Get all participants for a raffle"""
        cursor = await self.connection.execute("""
            SELECT * FROM participants WHERE raffle_id = ?
        """, (raffle_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # Payment operations
    async def create_payment(
        self,
        raffle_id: str,
        user_id: int,
        ticket_count: int,
        amount: float,
        payment_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Create a new payment record"""
        metadata_json = json.dumps(metadata) if metadata else None
        cursor = await self.connection.execute("""
            INSERT INTO payments 
            (raffle_id, user_id, ticket_count, amount, payment_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (raffle_id, user_id, ticket_count, amount, payment_id, metadata_json))
        await self.connection.commit()
        return cursor.lastrowid

    async def update_payment_status(
        self, payment_id: int, status: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update payment status"""
        metadata_json = json.dumps(metadata) if metadata else None
        await self.connection.execute("""
            UPDATE payments 
            SET status = ?, metadata = COALESCE(?, metadata), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, metadata_json, payment_id))
        await self.connection.commit()

    async def get_payments_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get payments by status"""
        cursor = await self.connection.execute("""
            SELECT * FROM payments WHERE status = ?
        """, (status,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]