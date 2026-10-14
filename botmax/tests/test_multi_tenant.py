"""
Test Multi-Tenant Organizer Hierarchy and SBP routing in BotMAX
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import Database
from src.services.admin_auth import AdminAuthService
from src.services.lottery import LotteryService


async def test_multi_tenant_flow():
    test_db_path = f"test_multi_tenant_{os.getpid()}.db"
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

    try:
        db = Database(test_db_path)
        await db.connect()

        auth = AdminAuthService(admin_password="super_pass_123", secret_key="salt", db=db)

        # 1. Verify default SuperAdmin is created
        super_admin = await db.get_admin_by_username("superadmin")
        assert super_admin is not None
        assert super_admin["role"] == "superadmin"
        assert super_admin["id"] == "admin_super"

        # 2. SuperAdmin creates a new organizer
        new_org = await db.create_admin(
            username="ivan_organizer",
            password="ivan_password_999",
            display_name="Иван Организатор",
            role="admin",
            sbp_phone="+79991112233",
            sbp_bank="Т-Банк",
        )
        assert new_org is not None
        assert new_org["username"] == "ivan_organizer"
        assert new_org["sbp_phone"] == "+79991112233"

        # 3. Authenticate as Ivan Organizer
        ok, msg, token, info = await auth.authenticate("ivan_organizer", "ivan_password_999", "127.0.0.1")
        assert ok is True
        assert token is not None
        assert info["role"] == "admin"
        assert info["id"] == new_org["id"]

        from src.services.sbp import SBPService
        sbp = SBPService()
        lottery = LotteryService(db=db, sbp_service=sbp, notification_service=None)
        raffle = await db.create_raffle(
            raffle_id="raf_ivan_test_01",
            title="Иван: Розыгрыш Смартфона",
            category="electronics",
            description="Розыгрыш от Ивана",
            total_tickets=10,
            price_per_ticket=200.0,
            prize_image_url="https://example.com/phone.jpg",
            creator_admin_id=new_org["id"],
        )
        assert raffle is not None
        assert raffle["creator_admin_id"] == new_org["id"]

        # 5. Check raffles isolation
        # Ivan's view: only 1 raffle
        ivan_raffles = await db.get_all_raffles(creator_admin_id=new_org["id"])
        assert len(ivan_raffles) == 1
        assert ivan_raffles[0]["id"] == raffle["id"]

        # SuperAdmin's view: sees Ivan's raffle + seeded raffles
        all_raffles = await db.get_all_raffles(creator_admin_id=None)
        assert any(r["id"] == raffle["id"] for r in all_raffles)

        # 6. User reserves tickets for Ivan's raffle -> SBP routing check
        res = await lottery.reserve_specific_tickets(
            raffle_id=raffle["id"],
            user_id=777888,
            username="buyer_alex",
            ticket_numbers=[1, 2],
        )
        assert res["success"] is True
        assert "recipient" in res
        assert res["recipient"]["admin_id"] == new_org["id"]
        assert res["recipient"]["display_name"] == "Иван Организатор"
        assert res["recipient"]["sbp_phone"] == "+79991112233"
        assert res["recipient"]["sbp_bank"] == "Т-Банк"

        # Check order in DB
        order = await db.get_order(res["order_id"])
        assert order is not None
        assert order["recipient_admin_id"] == new_org["id"]

        # 7. SuperAdmin deletes Ivan -> games reassigned to SuperAdmin
        del_ok = await db.delete_admin(new_org["id"])
        assert del_ok is True

        reassigned_raffle = await db.get_raffle(raffle["id"])
        assert reassigned_raffle is not None
        assert reassigned_raffle["creator_admin_id"] == "admin_super"
        assert reassigned_raffle["creator_name"] == "Главный Администратор"

        # SuperAdmin cannot be deleted
        try:
            await db.delete_admin("admin_super")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

        print("[OK] Multi-tenant organizer flow, SBP routing, and safe deletion tested successfully!")
    finally:
        try:
            await db.disconnect()
            await asyncio.sleep(0.25)
        except Exception:
            pass
        for suffix in ("", "-shm", "-wal"):
            fpath = test_db_path + suffix
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass


if __name__ == "__main__":
    asyncio.run(test_multi_tenant_flow())
