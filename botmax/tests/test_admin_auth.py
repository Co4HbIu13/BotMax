"""Tests for Admin Auth, Security Protection, and Raffle Management APIs"""

import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.services.admin_auth import AdminAuthService
from src.database.db import Database
from src.services.lottery import LotteryService
from src.services.sbp import SBPService
from src.services.notification import NotificationService
from src.config import Config


def test_admin_auth_security():
    auth = AdminAuthService(admin_password="secret_password_123", secret_key="test_secret_salt")

    # 1. Wrong password
    ok, msg, token = auth.login("wrong_pass", "127.0.0.1")
    assert not ok
    assert token is None
    assert "Неверный пароль" in msg

    # 2. Brute force lock simulation
    for _ in range(4):
        auth.login("wrong_pass", "127.0.0.1")

    # 6th attempt should be blocked
    ok, msg, token = auth.login("secret_password_123", "127.0.0.1")
    assert not ok
    assert "заблокирован" in msg

    # 3. Different IP succeeds
    ok, msg, token = auth.login("secret_password_123", "192.168.1.1")
    assert ok
    assert token is not None
    assert auth.verify_token(token)

    # 4. Logout invalidates token
    auth.logout(token)
    assert not auth.verify_token(token)


async def test_admin_db_and_services():
    db = Database("./data/test_admin_db.db")
    await db.connect()

    # 1. Create raffle via DB
    raffle = await db.create_raffle(
        raffle_id="raffle_test_switch",
        title="🎮 Nintendo Switch OLED",
        description="Портативная консоль",
        prize_image_url="https://example.com/switch.jpg",
        total_tickets=25,
        price_per_ticket=100,
        category="gaming",
    )
    assert raffle["id"] == "raffle_test_switch"
    assert raffle["total_tickets"] == 25
    assert raffle["available_tickets"] == 25

    # 2. Verify admin stats
    stats = await db.get_admin_stats()
    assert stats["total_raffles"] >= 1
    assert stats["total_tickets"] >= 25

    # 3. Update status
    await db.update_raffle_status("raffle_test_switch", "completed")
    updated = await db.get_raffle("raffle_test_switch")
    assert updated["status"] == "completed"

    # 4. Delete raffle
    await db.delete_raffle("raffle_test_switch")
    deleted = await db.get_raffle("raffle_test_switch")
    assert deleted is None

    await db.close()
    import os
    if os.path.exists("./data/test_admin_db.db"):
        os.remove("./data/test_admin_db.db")


if __name__ == "__main__":
    print("Testing admin auth security & brute-force protection...")
    test_admin_auth_security()
    print("[OK] Admin auth & brute-force lock verified!")

    print("Testing admin DB metrics, creation, and deletion...")
    asyncio.run(test_admin_db_and_services())
    print("[OK] Admin DB & statistics verified!")
    print("ALL TESTS PASSED SUCCESSFULLY! 100% GREEN!")
