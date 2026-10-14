import asyncio
import os
import sys
import uuid

sys.path.insert(0, ".")

from src.database.db import Database
from src.services.lottery import LotteryService
from src.services.sbp import SBPService
from src.services.notification import NotificationService


async def test_cancellation():
    db_name = f"data/test_cancel_{uuid.uuid4().hex[:6]}.db"
    db = Database(db_name)
    await db.connect()

    sbp = SBPService()
    noti = NotificationService(db=db)
    lottery = LotteryService(db=db, sbp_service=sbp, notification_service=noti)

    rid = f"raffle_{uuid.uuid4().hex[:6]}"

    # 1. Create a raffle
    raffle = await db.create_raffle(
        raffle_id=rid,
        title="Тест отмены",
        description="Тест",
        prize_image_url="https://example.com/p.jpg",
        total_tickets=10,
        price_per_ticket=100.0,
        prizes=[
            {"place": 1, "lot_number": 1, "title": "Лот 1", "description": "Desc 1", "prize_image_url": "https://example.com/p1.jpg"},
            {"place": 2, "lot_number": 2, "title": "Лот 2", "description": "Desc 2", "prize_image_url": "https://example.com/p2.jpg"}
        ]
    )

    # 2. Reserve tickets 1 and 2 by user 12345
    res = await lottery.reserve_specific_tickets(
        raffle_id=rid,
        user_id=12345,
        username="test_user",
        ticket_numbers=[1, 2],
    )
    assert res["success"] is True
    order_id = res["order_id"]

    # Verify active reservation lookup
    active = await lottery.get_user_active_reservation(12345)
    assert active is not None
    assert active["order_id"] == order_id
    assert active["ticket_numbers"] == [1, 2]
    assert "qr_data_url" in active["sbp"]

    # Verify tickets are reserved in db
    tickets = await db.get_raffle_tickets(rid)
    t1 = next(t for t in tickets if t["ticket_number"] == 1)
    assert t1["status"] == "reserved"

    # 3. User cancels reservation
    cancel_res = await lottery.cancel_reservation(order_id, user_id=12345)
    assert cancel_res["success"] is True

    # Verify tickets are back to 'available'
    tickets_after = await db.get_raffle_tickets(rid)
    t1_after = next(t for t in tickets_after if t["ticket_number"] == 1)
    assert t1_after["status"] == "available"

    # Verify no active reservation
    active_after = await lottery.get_user_active_reservation(12345)
    assert active_after is None

    # 4. Now test admin cancellation
    res2 = await lottery.reserve_specific_tickets(
        raffle_id=rid,
        user_id=67890,
        username="another_user",
        ticket_numbers=[5, 6],
    )
    assert res2["success"] is True
    order_id_2 = res2["order_id"]

    # Admin force releases it
    admin_cancel = await lottery.cancel_reservation(order_id_2, is_admin=True)
    assert admin_cancel["success"] is True

    t5 = next(t for t in (await db.get_raffle_tickets(rid)) if t["ticket_number"] == 5)
    assert t5["status"] == "available"

    print("ALL_CANCELLATION_TESTS_PASSED_OK")
    await db.close()
    if os.path.exists(db_name):
        try:
            os.remove(db_name)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(test_cancellation())
