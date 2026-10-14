"""Database manager for BotMAX using SQLite with aiosqlite"""

import aiosqlite
import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger("botmax.database")


def utc_now_iso() -> str:
    """Current UTC timestamp as ISO 8601 string"""
    return datetime.now(timezone.utc).isoformat()


class Database:
    """Async database layer for BotMAX with transactional ticket drawdown"""

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash password using SHA-256 with cryptographic random salt"""
        if not salt:
            salt = secrets.token_hex(16)
        pw_hash = hashlib.sha256(f"{salt}:{password.strip()}".encode("utf-8")).hexdigest()
        return pw_hash, salt

    @staticmethod
    def verify_password(password: str, salt: str, expected_hash: str) -> bool:
        """Verify password against salt and expected hash using constant-time comparison"""
        pw_hash = hashlib.sha256(f"{salt}:{password.strip()}".encode("utf-8")).hexdigest()
        return secrets.compare_digest(pw_hash, expected_hash)

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> aiosqlite.Connection:
        """Connect to database and enable WAL mode for high concurrency"""
        if self._connection is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA journal_mode = WAL")
            await self._connection.execute("PRAGMA busy_timeout = 10000")
            await self._connection.execute("PRAGMA foreign_keys = ON")
            await self._connection.commit()
            await self._create_tables()
        return self._connection

    async def close(self) -> None:
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    async def _create_tables(self) -> None:
        """Initialize schema and tables"""
        async with self._connection.cursor() as cur:
            # 0. Admins (Администраторы и организаторы с реквизитами СБП)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT DEFAULT 'admin', -- 'superadmin', 'admin'
                    sbp_phone TEXT DEFAULT '',
                    sbp_bank TEXT DEFAULT 'СБП',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            # 1. Raffles (Розыгрыши призов / Лоты)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS raffles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    lot_number INTEGER DEFAULT 1,
                    category TEXT DEFAULT 'lot',
                    prize_image_url TEXT,
                    total_tickets INTEGER NOT NULL,
                    price_per_ticket REAL NOT NULL,
                    status TEXT DEFAULT 'active', -- active, drawing, completed, cancelled
                    winner_ticket_number INTEGER,
                    winner_user_id INTEGER,
                    winner_username TEXT,
                    created_at TEXT NOT NULL,
                    drawn_at TEXT,
                    creator_admin_id TEXT DEFAULT 'admin_super'
                )
            """)
            try:
                await cur.execute("ALTER TABLE raffles ADD COLUMN lot_number INTEGER DEFAULT 1")
            except Exception:
                pass
            try:
                await cur.execute("ALTER TABLE raffles ADD COLUMN creator_admin_id TEXT DEFAULT 'admin_super'")
            except Exception:
                pass

            # 1.1 Raffle Prizes (Призы и призовые места в рамках игры: 1 место - Лот 1, 2 место - Лот 2...)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS raffle_prizes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raffle_id TEXT NOT NULL,
                    place INTEGER NOT NULL,          -- 1, 2, 3 ...
                    lot_number INTEGER NOT NULL,     -- 1, 2, 3 ...
                    title TEXT NOT NULL,             -- Название приза
                    description TEXT DEFAULT '',
                    prize_image_url TEXT NOT NULL,
                    winner_ticket_number INTEGER,
                    winner_user_id INTEGER,
                    winner_username TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (raffle_id) REFERENCES raffles(id) ON DELETE CASCADE
                )
            """)
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_prizes_raffle ON raffle_prizes(raffle_id)")

            # Auto-populate raffle_prizes for existing raffles without prizes
            try:
                await cur.execute("""
                    INSERT INTO raffle_prizes (raffle_id, place, lot_number, title, description, prize_image_url, winner_ticket_number, winner_user_id, winner_username, created_at)
                    SELECT r.id, 1, COALESCE(r.lot_number, 1), r.title, COALESCE(r.description, ''), COALESCE(r.prize_image_url, ''), r.winner_ticket_number, r.winner_user_id, r.winner_username, r.created_at
                    FROM raffles r
                    WHERE r.id NOT IN (SELECT DISTINCT raffle_id FROM raffle_prizes)
                """)
            except Exception:
                pass

            # 2. Tickets (Билеты и статус их убытия)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raffle_id TEXT NOT NULL,
                    ticket_number INTEGER NOT NULL,
                    status TEXT DEFAULT 'available', -- available, reserved, sold, winner
                    user_id INTEGER,
                    username TEXT,
                    order_id TEXT,
                    reserved_until TEXT,
                    sold_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (raffle_id) REFERENCES raffles(id) ON DELETE CASCADE,
                    UNIQUE(raffle_id, ticket_number)
                )
            """)

            # 3. Orders / Payments (Заказы и платежи через СБП)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    raffle_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    ticket_numbers TEXT NOT NULL, -- JSON array of ints
                    ticket_count INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'pending', -- pending, paid, expired, cancelled
                    sbp_qrid TEXT,
                    sbp_pay_url TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    paid_at TEXT,
                    recipient_admin_id TEXT DEFAULT 'admin_super',
                    FOREIGN KEY (raffle_id) REFERENCES raffles(id)
                )
            """)
            try:
                await cur.execute("ALTER TABLE orders ADD COLUMN recipient_admin_id TEXT DEFAULT 'admin_super'")
            except Exception:
                pass

            # 4. Users (Пользователи бота и мини-приложения)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    balance REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
            """)

            # 5. Chats / Groups (Группы и каналы)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT,
                    chat_type TEXT DEFAULT 'chat',
                    pinned_message_id TEXT,
                    added_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # Indexes for fast lookup
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickets_raffle_status
                ON tickets(raffle_id, status)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickets_user
                ON tickets(user_id)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickets_reserved_until
                ON tickets(status, reserved_until)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_status
                ON orders(status)
            """)
            await cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_raffles_creator
                ON raffles(creator_admin_id)
            """)

            # Seed default SuperAdmin if table has no superadmin
            await cur.execute("SELECT COUNT(*) FROM admins WHERE role = 'superadmin'")
            sa_row = await cur.fetchone()
            if not sa_row or sa_row[0] == 0:
                h, s = Database.hash_password("maxadmin2026")
                await cur.execute("""
                    INSERT INTO admins (
                        id, username, password_hash, password_salt, display_name,
                        role, sbp_phone, sbp_bank, is_active, created_at
                    ) VALUES ('admin_super', 'superadmin', ?, ?, 'Главный Администратор', 'superadmin', '+7 (999) 000-00-00', 'СБП / Т-Банк', 1, ?)
                    ON CONFLICT(id) DO UPDATE SET password_hash = excluded.password_hash, password_salt = excluded.password_salt
                """, (h, s, utc_now_iso()))

            await self._connection.commit()
            logger.info("Database schema initialized successfully")

    # ==========================================
    # ADMIN MANAGEMENT OPERATIONS
    # ==========================================
    async def create_admin(
        self,
        username: str,
        password: str,
        display_name: str,
        role: str = "admin",
        sbp_phone: str = "",
        sbp_bank: str = "СБП",
    ) -> Dict[str, Any]:
        """Create a new administrator / organizer with SBP payout credentials"""
        username = username.strip().lower()
        if not username or len(username) < 3:
            raise ValueError("Логин должен содержать не менее 3 символов")
        if not password or len(password) < 4:
            raise ValueError("Пароль должен содержать не менее 4 символов")
        if not display_name:
            display_name = username

        pw_hash, salt = self.hash_password(password)
        admin_id = f"admin_{secrets.token_hex(6)}"
        now = utc_now_iso()

        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM admins WHERE username = ?", (username,))
            if await cur.fetchone():
                raise ValueError(f"Администратор с логином '{username}' уже существует")

            await cur.execute("""
                INSERT INTO admins (
                    id, username, password_hash, password_salt, display_name,
                    role, sbp_phone, sbp_bank, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (admin_id, username, pw_hash, salt, display_name, role, sbp_phone, sbp_bank, now))
            await conn.commit()

        admin = await self.get_admin_by_id(admin_id)
        logger.info(f"Created new admin profile: {username} ({role}) with SBP phone '{sbp_phone}'")
        return admin

    async def get_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        """Fetch admin by unique ID without exposing secret salt and hash"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, username, display_name, role, sbp_phone, sbp_bank, is_active, created_at
                FROM admins WHERE id = ?
            """, (admin_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_admin_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch full admin record including hash and salt for authentication"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM admins WHERE username = ?", (username.strip().lower(),))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_all_admins(self) -> List[Dict[str, Any]]:
        """List all admins with per-organizer revenue, ticket sales, and games counts"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, username, display_name, role, sbp_phone, sbp_bank, is_active, created_at
                FROM admins
                ORDER BY CASE WHEN role = 'superadmin' THEN 0 ELSE 1 END, created_at ASC
            """)
            rows = await cur.fetchall()
            admins = [dict(r) for r in rows]

            for adm in admins:
                aid = adm["id"]
                # Raffles metrics
                await cur.execute("""
                    SELECT
                        COUNT(*) as total_raffles,
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_raffles
                    FROM raffles WHERE creator_admin_id = ?
                """, (aid,))
                r_stat = await cur.fetchone()
                adm["total_raffles"] = r_stat["total_raffles"] or 0
                adm["active_raffles"] = r_stat["active_raffles"] or 0

                # SBP revenue from sold tickets
                await cur.execute("""
                    SELECT SUM(amount) as revenue
                    FROM orders
                    WHERE (recipient_admin_id = ? OR raffle_id IN (SELECT id FROM raffles WHERE creator_admin_id = ?))
                      AND status = 'paid'
                """, (aid, aid))
                rev = await cur.fetchone()
                adm["total_revenue"] = rev["revenue"] or 0.0

            return admins

    async def update_admin(
        self,
        admin_id: str,
        display_name: Optional[str] = None,
        sbp_phone: Optional[str] = None,
        sbp_bank: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """Update organizer display name, SBP payout details or password"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            updates = []
            params = []
            if display_name is not None:
                updates.append("display_name = ?")
                params.append(display_name.strip())
            if sbp_phone is not None:
                updates.append("sbp_phone = ?")
                params.append(sbp_phone.strip())
            if sbp_bank is not None:
                updates.append("sbp_bank = ?")
                params.append(sbp_bank.strip())
            if password:
                pw_hash, salt = self.hash_password(password)
                updates.append("password_hash = ?")
                params.append(pw_hash)
                updates.append("password_salt = ?")
                params.append(salt)

            if not updates:
                return True

            params.append(admin_id)
            await cur.execute(f"UPDATE admins SET {', '.join(updates)} WHERE id = ?", params)
            await conn.commit()
            return True

    async def delete_admin(self, admin_id: str) -> bool:
        """Permanently delete organizer profile, reassigning their games to SuperAdmin"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("SELECT role FROM admins WHERE id = ?", (admin_id,))
            row = await cur.fetchone()
            if not row:
                return False
            if row["role"] == "superadmin":
                raise ValueError("Нельзя удалить Главного СуперАдминистратора")

            # Reassign existing raffles and orders to superadmin so games don't orphan
            await cur.execute("UPDATE raffles SET creator_admin_id = 'admin_super' WHERE creator_admin_id = ?", (admin_id,))
            await cur.execute("UPDATE orders SET recipient_admin_id = 'admin_super' WHERE recipient_admin_id = ?", (admin_id,))
            await cur.execute("DELETE FROM admins WHERE id = ?", (admin_id,))
            await conn.commit()
            logger.info(f"Deleted admin {admin_id}. Reassigned games to superadmin.")
            return True

    # ==========================================
    # CHAT / GROUP OPERATIONS
    # ==========================================
    async def save_chat(
        self,
        chat_id: int,
        title: Optional[str] = None,
        chat_type: str = "chat",
        pinned_message_id: Optional[str] = None,
    ) -> None:
        """Register or update a group/channel where bot is added"""
        now = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO chats (chat_id, title, chat_type, pinned_message_id, added_at, last_active_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title = COALESCE(excluded.title, chats.title),
                    pinned_message_id = COALESCE(excluded.pinned_message_id, chats.pinned_message_id),
                    last_active_at = excluded.last_active_at,
                    is_active = 1
            """, (chat_id, title, chat_type, pinned_message_id, now, now))
            await conn.commit()

    async def get_active_chats(self) -> List[Dict[str, Any]]:
        """Return list of active groups and channels"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM chats WHERE is_active = 1")
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # ==========================================
    # USER OPERATIONS
    # ==========================================
    async def upsert_user(
        self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record or update user activity"""
        now = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO users (user_id, username, first_name, created_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = COALESCE(excluded.username, users.username),
                    first_name = COALESCE(excluded.first_name, users.first_name),
                    last_seen_at = excluded.last_seen_at
            """, (user_id, username, first_name, now, now))
            await conn.commit()
            return {"user_id": user_id, "username": username, "first_name": first_name}

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    # ==========================================
    # RAFFLE OPERATIONS
    # ==========================================
    async def create_raffle(
        self,
        raffle_id: str,
        title: str,
        description: str,
        prize_image_url: str,
        total_tickets: int,
        price_per_ticket: float,
        lot_number: Optional[int] = None,
        category: str = "lot",
        prizes: Optional[List[Dict[str, Any]]] = None,
        creator_admin_id: str = "admin_super",
    ) -> Dict[str, Any]:
        """Create a new raffle game with one or multiple prize places (Лоты) associated with a creator admin"""
        now = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            if lot_number is None:
                await cur.execute("SELECT COALESCE(MAX(lot_number), 0) + 1 FROM raffles")
                row = await cur.fetchone()
                lot_number = int(row[0]) if row and row[0] is not None else 1

            # Fallback prize image
            if not prize_image_url and prizes and len(prizes) > 0:
                prize_image_url = prizes[0].get("prize_image_url", "")

            await cur.execute("""
                INSERT INTO raffles (
                    id, title, description, lot_number, category, prize_image_url,
                    total_tickets, price_per_ticket, status, created_at, creator_admin_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """, (
                raffle_id, title, description, lot_number, category, prize_image_url,
                total_tickets, price_per_ticket, now, creator_admin_id
            ))

            # Normalize prizes list
            if not prizes:
                prizes = [{
                    "place": 1,
                    "lot_number": lot_number,
                    "title": title,
                    "description": description or "",
                    "prize_image_url": prize_image_url,
                }]

            for idx, p in enumerate(prizes, start=1):
                p_place = int(p.get("place", idx))
                p_lot = int(p.get("lot_number", idx))
                p_title = str(p.get("title") or f"Лот №{p_lot}")
                p_desc = str(p.get("description") or "")
                p_img = str(p.get("prize_image_url") or prize_image_url)

                await cur.execute("""
                    INSERT INTO raffle_prizes (
                        raffle_id, place, lot_number, title, description, prize_image_url, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (raffle_id, p_place, p_lot, p_title, p_desc, p_img, now))

            # Batch insert all initial tickets as available
            tickets_data = [
                (raffle_id, num, "available", now)
                for num in range(1, total_tickets + 1)
            ]
            await cur.executemany("""
                INSERT INTO tickets (raffle_id, ticket_number, status, created_at)
                VALUES (?, ?, ?, ?)
            """, tickets_data)

            await conn.commit()
            logger.info(f"Created raffle {raffle_id} (creator: {creator_admin_id}) with {len(prizes)} prizes and {total_tickets} tickets")
            return await self.get_raffle(raffle_id)

    async def get_raffle_prizes(self, raffle_id: str) -> List[Dict[str, Any]]:
        """Get all prizes / lots for a raffle ordered by place (1st, 2nd, 3rd place)"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT * FROM raffle_prizes
                WHERE raffle_id = ?
                ORDER BY place ASC, lot_number ASC
            """, (raffle_id,))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_raffle(self, raffle_id: str) -> Optional[Dict[str, Any]]:
        """Get single raffle with prizes, organizer details, and aggregated stats"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT r.*,
                       COALESCE(a.display_name, 'Главный Администратор') as creator_name,
                       COALESCE(a.username, 'superadmin') as creator_username,
                       COALESCE(a.sbp_phone, '') as creator_sbp_phone,
                       COALESCE(a.sbp_bank, 'СБП') as creator_sbp_bank
                FROM raffles r
                LEFT JOIN admins a ON r.creator_admin_id = a.id
                WHERE r.id = ?
            """, (raffle_id,))
            row = await cur.fetchone()
            if not row:
                return None
            raffle = dict(row)

            # Compute ticket stats
            await cur.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                    SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved,
                    SUM(CASE WHEN status IN ('sold', 'winner') THEN 1 ELSE 0 END) as sold
                FROM tickets WHERE raffle_id = ?
            """, (raffle_id,))
            stats = await cur.fetchone()
            raffle["available_tickets"] = stats["available"] or 0
            raffle["reserved_tickets"] = stats["reserved"] or 0
            raffle["sold_tickets"] = stats["sold"] or 0
            raffle["percent_sold"] = (
                round((raffle["sold_tickets"] / raffle["total_tickets"]) * 100, 1)
                if raffle["total_tickets"] > 0 else 0
            )

            # Attach prize places
            raffle["prizes"] = await self.get_raffle_prizes(raffle_id)
            return raffle

    async def get_all_raffles(
        self, status: Optional[str] = None, creator_admin_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all raffles (optionally filtered by status or creator admin) with organizer details"""
        query = """
            SELECT r.*,
                   COALESCE(a.display_name, 'Главный Администратор') as creator_name,
                   COALESCE(a.username, 'superadmin') as creator_username,
                   COALESCE(a.sbp_phone, '') as creator_sbp_phone,
                   COALESCE(a.sbp_bank, 'СБП') as creator_sbp_bank
            FROM raffles r
            LEFT JOIN admins a ON r.creator_admin_id = a.id
        """
        clauses = []
        params = []
        if status:
            clauses.append("r.status = ?")
            params.append(status)
        if creator_admin_id:
            clauses.append("r.creator_admin_id = ?")
            params.append(creator_admin_id)

        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY r.lot_number ASC, r.created_at DESC"

        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
            results = []
            for row in rows:
                raffle = dict(row)
                raffle_id = raffle["id"]
                await cur.execute("""
                    SELECT
                        SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                        SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved,
                        SUM(CASE WHEN status IN ('sold', 'winner') THEN 1 ELSE 0 END) as sold
                    FROM tickets WHERE raffle_id = ?
                """, (raffle_id,))
                stats = await cur.fetchone()
                raffle["available_tickets"] = stats["available"] or 0
                raffle["reserved_tickets"] = stats["reserved"] or 0
                raffle["sold_tickets"] = stats["sold"] or 0
                raffle["percent_sold"] = (
                    round((raffle["sold_tickets"] / raffle["total_tickets"]) * 100, 1)
                    if raffle["total_tickets"] > 0 else 0
                )
                raffle["prizes"] = await self.get_raffle_prizes(raffle_id)
                results.append(raffle)
            return results

    async def delete_raffle(self, raffle_id: str) -> bool:
        """Permanently delete raffle, its prizes, and tickets"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM raffle_prizes WHERE raffle_id = ?", (raffle_id,))
            await cur.execute("DELETE FROM tickets WHERE raffle_id = ?", (raffle_id,))
            await cur.execute("DELETE FROM orders WHERE raffle_id = ?", (raffle_id,))
            await cur.execute("DELETE FROM raffles WHERE id = ?", (raffle_id,))
            await conn.commit()
            logger.info(f"Deleted raffle {raffle_id}")
            return True

    async def update_raffle_status(self, raffle_id: str, status: str) -> bool:
        """Update raffle state (e.g. active, completed, cancelled)"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("UPDATE raffles SET status = ? WHERE id = ?", (status, raffle_id))
            await conn.commit()
            return True

    async def get_admin_stats(self, admin_id: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate KPI metrics (filtered by creator admin, or global for superadmin)"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            if admin_id:
                # Per-organizer metrics
                await cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                    FROM raffles
                    WHERE creator_admin_id = ?
                """, (admin_id,))
                r_row = await cur.fetchone()

                await cur.execute("""
                    SELECT
                        COUNT(*) as total_tickets,
                        SUM(CASE WHEN t.status IN ('sold', 'winner') THEN 1 ELSE 0 END) as sold_tickets,
                        SUM(CASE WHEN t.status = 'reserved' THEN 1 ELSE 0 END) as reserved_tickets,
                        SUM(CASE WHEN t.status = 'available' THEN 1 ELSE 0 END) as available_tickets
                    FROM tickets t
                    JOIN raffles r ON t.raffle_id = r.id
                    WHERE r.creator_admin_id = ?
                """, (admin_id,))
                t_row = await cur.fetchone()

                await cur.execute("""
                    SELECT SUM(amount) as revenue
                    FROM orders
                    WHERE (recipient_admin_id = ? OR raffle_id IN (SELECT id FROM raffles WHERE creator_admin_id = ?))
                      AND status = 'paid'
                """, (admin_id, admin_id))
                o_row = await cur.fetchone()

                return {
                    "total_raffles": r_row["total"] if r_row else 0,
                    "active_raffles": r_row["active"] if r_row else 0,
                    "completed_raffles": r_row["completed"] if r_row else 0,
                    "total_tickets": t_row["total_tickets"] if t_row else 0,
                    "sold_tickets": t_row["sold_tickets"] if t_row else 0,
                    "reserved_tickets": t_row["reserved_tickets"] if t_row else 0,
                    "available_tickets": t_row["available_tickets"] if t_row else 0,
                    "total_revenue": o_row["revenue"] if o_row and o_row["revenue"] else 0.0,
                    "total_users": 0,
                    "total_groups": 0,
                }
            else:
                # Platform-wide totals (SuperAdmin)
                await cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                    FROM raffles
                """)
                r_row = await cur.fetchone()

                await cur.execute("""
                    SELECT
                        COUNT(*) as total_tickets,
                        SUM(CASE WHEN status IN ('sold', 'winner') THEN 1 ELSE 0 END) as sold_tickets,
                        SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved_tickets,
                        SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available_tickets
                    FROM tickets
                """)
                t_row = await cur.fetchone()

                await cur.execute("SELECT SUM(amount) as revenue FROM orders WHERE status = 'paid'")
                o_row = await cur.fetchone()

                await cur.execute("SELECT COUNT(*) as users_count FROM users")
                u_row = await cur.fetchone()

                await cur.execute("SELECT COUNT(*) as chats_count FROM chats WHERE is_active = 1")
                c_row = await cur.fetchone()

                return {
                    "total_raffles": r_row["total"] if r_row else 0,
                    "active_raffles": r_row["active"] if r_row else 0,
                    "completed_raffles": r_row["completed"] if r_row else 0,
                    "total_tickets": t_row["total_tickets"] if t_row else 0,
                    "sold_tickets": t_row["sold_tickets"] if t_row else 0,
                    "reserved_tickets": t_row["reserved_tickets"] if t_row else 0,
                    "available_tickets": t_row["available_tickets"] if t_row else 0,
                    "total_revenue": o_row["revenue"] if o_row and o_row["revenue"] else 0.0,
                    "total_users": u_row["users_count"] if u_row else 0,
                    "total_groups": c_row["chats_count"] if c_row else 0,
                }

    # ==========================================
    # TICKET OPERATIONS & REALTIME DRAWDOWN
    # ==========================================
    async def get_raffle_tickets(self, raffle_id: str) -> List[Dict[str, Any]]:
        """Get all tickets for a raffle with their current status for visual grid"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, raffle_id, ticket_number, status, user_id, username, reserved_until, sold_at
                FROM tickets
                WHERE raffle_id = ?
                ORDER BY ticket_number ASC
            """, (raffle_id,))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def reserve_tickets(
        self,
        raffle_id: str,
        user_id: int,
        username: str,
        ticket_numbers: List[int],
        order_id: str,
        duration_minutes: int = 10,
    ) -> Dict[str, Any]:
        """
        Atomically reserve tickets for checkout.
        Tickets transition from 'available' to 'reserved' and decrease the available pool.
        """
        now = datetime.now(timezone.utc)
        reserved_until = datetime.fromtimestamp(
            now.timestamp() + duration_minutes * 60, timezone.utc
        ).isoformat()

        conn = await self.connect()
        async with conn.cursor() as cur:
            # Check availability first
            placeholders = ",".join(["?"] * len(ticket_numbers))
            await cur.execute(f"""
                SELECT ticket_number, status FROM tickets
                WHERE raffle_id = ? AND ticket_number IN ({placeholders})
            """, [raffle_id, *ticket_numbers])
            found = await cur.fetchall()

            unavailable = [
                row["ticket_number"] for row in found if row["status"] != "available"
            ]
            if unavailable:
                return {
                    "success": False,
                    "error": f"Билеты {unavailable} уже заняты или куплены",
                    "unavailable_tickets": unavailable,
                }

            if len(found) != len(ticket_numbers):
                return {
                    "success": False,
                    "error": "Некоторые указанные билеты не существуют в этом розыгрыше",
                }

            # Perform atomic reservation
            await cur.execute(f"""
                UPDATE tickets
                SET status = 'reserved',
                    user_id = ?,
                    username = ?,
                    order_id = ?,
                    reserved_until = ?
                WHERE raffle_id = ?
                  AND ticket_number IN ({placeholders})
                  AND status = 'available'
            """, [user_id, username, order_id, reserved_until, raffle_id, *ticket_numbers])

            await conn.commit()
            logger.info(
                f"User {user_id} ({username}) reserved tickets {ticket_numbers} "
                f"for raffle {raffle_id} under order {order_id}"
            )
            return {
                "success": True,
                "reserved_until": reserved_until,
                "ticket_numbers": ticket_numbers,
            }

    async def release_expired_reservations(self) -> int:
        """
        Background task helper: releases all tickets whose reservation window has expired.
        Tickets return back to 'available' pool.
        """
        now_iso = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            # Find expired tickets
            await cur.execute("""
                SELECT id, raffle_id, ticket_number, order_id
                FROM tickets
                WHERE status = 'reserved' AND reserved_until < ?
            """, (now_iso,))
            expired_tickets = await cur.fetchall()

            if not expired_tickets:
                return 0

            # Revert tickets back to available
            await cur.execute("""
                UPDATE tickets
                SET status = 'available',
                    user_id = NULL,
                    username = NULL,
                    order_id = NULL,
                    reserved_until = NULL
                WHERE status = 'reserved' AND reserved_until < ?
            """, (now_iso,))

            # Mark associated pending orders as expired
            order_ids = list({row["order_id"] for row in expired_tickets if row["order_id"]})
            if order_ids:
                placeholders = ",".join(["?"] * len(order_ids))
                await cur.execute(f"""
                    UPDATE orders
                    SET status = 'expired'
                    WHERE id IN ({placeholders}) AND status = 'pending'
                """, order_ids)

            await conn.commit()
            count = len(expired_tickets)
            logger.info(f"Released {count} expired ticket reservations back to available pool")
            return count

    # ==========================================
    # ORDERS & SBP PAYMENTS
    # ==========================================
    async def create_order(
        self,
        order_id: str,
        raffle_id: str,
        user_id: int,
        username: str,
        ticket_numbers: List[int],
        amount: float,
        sbp_qrid: str,
        sbp_pay_url: str,
        duration_minutes: int = 10,
        recipient_admin_id: str = "admin_super",
    ) -> Dict[str, Any]:
        """Create a pending order for SBP payment routed to recipient admin"""
        now = datetime.now(timezone.utc)
        created_at = now.isoformat()
        expires_at = datetime.fromtimestamp(
            now.timestamp() + duration_minutes * 60, timezone.utc
        ).isoformat()

        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO orders (
                    id, raffle_id, user_id, username, ticket_numbers,
                    ticket_count, amount, status, sbp_qrid, sbp_pay_url,
                    created_at, expires_at, recipient_admin_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
            """, (
                order_id, raffle_id, user_id, username,
                json.dumps(ticket_numbers), len(ticket_numbers), amount,
                sbp_qrid, sbp_pay_url, created_at, expires_at, recipient_admin_id
            ))
            await conn.commit()
            return {
                "order_id": order_id,
                "raffle_id": raffle_id,
                "user_id": user_id,
                "amount": amount,
                "ticket_numbers": ticket_numbers,
                "sbp_qrid": sbp_qrid,
                "sbp_pay_url": sbp_pay_url,
                "expires_at": expires_at,
                "recipient_admin_id": recipient_admin_id,
            }

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by ID"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = await cur.fetchone()
            if not row:
                return None
            order = dict(row)
            order["ticket_numbers"] = json.loads(order["ticket_numbers"])
            return order

    async def confirm_order_payment(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Mark order as paid and convert reserved tickets into permanently sold tickets.
        This triggers permanent drawdown of tickets from the lottery pool.
        """
        now_iso = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = await cur.fetchone()
            if not row:
                return None
            order = dict(row)

            if order["status"] == "paid":
                order["ticket_numbers"] = json.loads(order["ticket_numbers"])
                return order

            ticket_numbers = json.loads(order["ticket_numbers"])
            placeholders = ",".join(["?"] * len(ticket_numbers))

            # 1. Update order
            await cur.execute("""
                UPDATE orders
                SET status = 'paid', paid_at = ?
                WHERE id = ?
            """, (now_iso, order_id))

            # 2. Update tickets: from 'reserved' to 'sold'
            await cur.execute(f"""
                UPDATE tickets
                SET status = 'sold',
                    sold_at = ?,
                    reserved_until = NULL
                WHERE raffle_id = ?
                  AND ticket_number IN ({placeholders})
                  AND order_id = ?
            """, [now_iso, order["raffle_id"], *ticket_numbers, order_id])

            await conn.commit()
            logger.info(
                f"Order {order_id} confirmed paid via SBP! "
                f"Tickets {ticket_numbers} permanently sold for raffle {order['raffle_id']}"
            )

            order["status"] = "paid"
            order["paid_at"] = now_iso
            order["ticket_numbers"] = ticket_numbers
            return order

    async def cancel_order(
        self, order_id: str, reason: str = "cancelled_by_user"
    ) -> Optional[Dict[str, Any]]:
        """
        Cancel a pending order and immediately release its reserved tickets back to 'available'.
        Can be triggered by participant or admin.
        """
        now_iso = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = await cur.fetchone()
            if not row:
                return None
            order = dict(row)

            if order["status"] != "pending":
                logger.warning(f"Cannot cancel order {order_id} in status {order['status']}")
                return None

            ticket_numbers = json.loads(order["ticket_numbers"])
            placeholders = ",".join(["?"] * len(ticket_numbers))

            # 1. Update order status to cancelled
            await cur.execute("""
                UPDATE orders
                SET status = 'cancelled'
                WHERE id = ? AND status = 'pending'
            """, (order_id,))

            # 2. Release reserved tickets back to 'available'
            await cur.execute(f"""
                UPDATE tickets
                SET status = 'available',
                    user_id = NULL,
                    username = NULL,
                    order_id = NULL,
                    reserved_until = NULL
                WHERE raffle_id = ?
                  AND ticket_number IN ({placeholders})
                  AND status = 'reserved'
            """, [order["raffle_id"], *ticket_numbers])

            await conn.commit()
            logger.info(
                f"Cancelled order {order_id} ({reason}). "
                f"Released tickets {ticket_numbers} back to available pool for raffle {order['raffle_id']}"
            )

            order["status"] = "cancelled"
            order["ticket_numbers"] = ticket_numbers
            return order

    async def get_active_user_order(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve active unexpired pending order for user so they can resume payment or cancel reservation.
        """
        now_iso = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT o.*,
                       r.title as raffle_title,
                       r.price_per_ticket,
                       COALESCE(a.display_name, 'Главный Администратор') as creator_name,
                       COALESCE(a.sbp_phone, '') as creator_sbp_phone,
                       COALESCE(a.sbp_bank, 'СБП') as creator_sbp_bank
                FROM orders o
                LEFT JOIN raffles r ON o.raffle_id = r.id
                LEFT JOIN admins a ON o.recipient_admin_id = a.id
                WHERE o.user_id = ?
                  AND o.status = 'pending'
                  AND o.expires_at > ?
                ORDER BY o.created_at DESC
                LIMIT 1
            """, (user_id, now_iso))
            row = await cur.fetchone()
            if not row:
                return None
            order = dict(row)
            order["ticket_numbers"] = json.loads(order["ticket_numbers"])
            return order

    async def get_raffle_pending_orders(self, raffle_id: str) -> List[Dict[str, Any]]:
        """
        List all active pending reservations for a raffle (for admin inspection and cancellation).
        """
        now_iso = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT * FROM orders
                WHERE raffle_id = ?
                  AND status = 'pending'
                  AND expires_at > ?
                ORDER BY created_at DESC
            """, (raffle_id, now_iso))
            rows = await cur.fetchall()
            results = []
            for r in rows:
                o = dict(r)
                o["ticket_numbers"] = json.loads(o["ticket_numbers"])
                results.append(o)
            return results

    async def get_user_tickets(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all tickets purchased or reserved by a user across all raffles"""
        conn = await self.connect()
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    t.id as ticket_id,
                    t.ticket_number,
                    t.status as ticket_status,
                    t.sold_at,
                    r.id as raffle_id,
                    r.title as raffle_title,
                    r.prize_image_url,
                    r.status as raffle_status,
                    r.winner_ticket_number,
                    r.winner_user_id
                FROM tickets t
                JOIN raffles r ON t.raffle_id = r.id
                WHERE t.user_id = ? AND t.status IN ('sold', 'winner', 'reserved')
                ORDER BY t.sold_at DESC, t.id DESC
            """, (user_id,))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # ==========================================
    # WINNER SELECTION & FAIR DRAW
    # ==========================================
    async def finish_raffle_draw_multi(
        self, raffle_id: str, winners: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Record winners for all prize places (Лоты) and mark raffle as completed"""
        now_iso = utc_now_iso()
        conn = await self.connect()
        async with conn.cursor() as cur:
            for w in winners:
                prize_id = w.get("prize_id")
                ticket_num = w["ticket_number"]
                uid = w["user_id"]
                uname = w.get("username", "")

                await cur.execute("""
                    UPDATE tickets
                    SET status = 'winner'
                    WHERE raffle_id = ? AND ticket_number = ?
                """, (raffle_id, ticket_num))

                if prize_id:
                    await cur.execute("""
                        UPDATE raffle_prizes
                        SET winner_ticket_number = ?, winner_user_id = ?, winner_username = ?
                        WHERE id = ?
                    """, (ticket_num, uid, uname, prize_id))
                else:
                    await cur.execute("""
                        UPDATE raffle_prizes
                        SET winner_ticket_number = ?, winner_user_id = ?, winner_username = ?
                        WHERE raffle_id = ? AND place = ?
                    """, (ticket_num, uid, uname, raffle_id, w.get("place", 1)))

            # Legacy fields on raffles set to 1st place winner
            first_w = winners[0] if winners else {}
            await cur.execute("""
                UPDATE raffles
                SET status = 'completed',
                    winner_ticket_number = ?,
                    winner_user_id = ?,
                    winner_username = ?,
                    drawn_at = ?
                WHERE id = ?
            """, (
                first_w.get("ticket_number"),
                first_w.get("user_id"),
                first_w.get("username"),
                now_iso,
                raffle_id,
            ))

            await conn.commit()
            logger.info(
                f"Raffle {raffle_id} completed with {len(winners)} winners drawn!"
            )
            return await self.get_raffle(raffle_id)

    async def finish_raffle_draw(
        self, raffle_id: str, winning_ticket_number: int, winner_user_id: int, winner_username: str
    ) -> Dict[str, Any]:
        """Record single winner (place 1) and mark raffle as completed"""
        return await self.finish_raffle_draw_multi(raffle_id, [{
            "place": 1,
            "lot_number": 1,
            "ticket_number": winning_ticket_number,
            "user_id": winner_user_id,
            "username": winner_username,
        }])

