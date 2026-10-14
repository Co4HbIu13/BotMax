import asyncio
import os
import sys
import uuid

sys.path.insert(0, ".")
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.database.db import Database
from src.services.lottery import LotteryService
from src.services.sbp import SBPService
from src.services.notification import NotificationService


async def test_cashier_flow():
    print("--- 1. Testing Cashier database setup ---")
    db_name = f"data/test_cashier_{uuid.uuid4().hex[:6]}.db"
    db = Database(db_name)
    await db.connect()

    sbp = SBPService()
    noti = NotificationService(db=db)
    lottery = LotteryService(db=db, sbp_service=sbp, notification_service=noti)

    rid = f"raffle_{uuid.uuid4().hex[:6]}"
    await db.create_raffle(
        raffle_id=rid,
        title="Тест Кассы 1-клик",
        description="Тест",
        prize_image_url="https://example.com/p.jpg",
        total_tickets=10,
        price_per_ticket=200.0,
        prizes=[
            {"place": 1, "lot_number": 1, "title": "Приз", "description": "", "prize_image_url": "https://example.com/p.jpg"}
        ]
    )

    # 1. User 1 reserves tickets #1, #2 = 400 RUB
    res1 = await lottery.reserve_specific_tickets(
        raffle_id=rid,
        user_id=101,
        username="mikhail",
        ticket_numbers=[1, 2],
        phone="+79991234567",
    )
    assert res1["success"] is True
    order1_id = res1["order_id"]

    # 2. User 2 reserves ticket #3 = 200 RUB
    res2 = await lottery.reserve_specific_tickets(
        raffle_id=rid,
        user_id=102,
        username="elena",
        ticket_numbers=[3],
        phone="+79997654321",
    )
    assert res2["success"] is True
    order2_id = res2["order_id"]

    # Verify Cashier sees both pending orders
    pending = await db.get_cashier_pending_orders()
    assert len(pending) == 2
    order_ids = [o["id"] for o in pending]
    assert order1_id in order_ids and order2_id in order_ids
    print(f"✅ Cashier successfully sees {len(pending)} pending reservations!")

    # 3. 1-Click Confirmation of Order 1
    print("--- 2. 1-Click Confirmation of Order 1 ---")
    confirm_res = await lottery.complete_sbp_payment(order1_id)
    assert confirm_res["success"] is True

    # Verify tickets #1, #2 are sold
    tickets = await db.get_raffle_tickets(rid)
    t1 = next(t for t in tickets if t["ticket_number"] == 1)
    t2 = next(t for t in tickets if t["ticket_number"] == 2)
    assert t1["status"] == "sold"
    assert t2["status"] == "sold"

    # Verify pending orders count decreased
    pending_after = await db.get_cashier_pending_orders()
    assert len(pending_after) == 1
    assert pending_after[0]["id"] == order2_id

    # Verify Order 1 appears in recent payments history
    recent_paid = await db.get_cashier_recent_payments()
    assert len(recent_paid) == 1
    assert recent_paid[0]["id"] == order1_id
    assert recent_paid[0]["amount"] == 400.0
    print("✅ 1-Click confirmation succeeded! Tickets permanently sold, appeared in paid history.")

    # 4. 1-Click Cancellation of Order 2 (Release tickets)
    print("--- 3. 1-Click Cancellation of Order 2 ---")
    cancel_res = await lottery.cancel_reservation(order2_id, is_admin=True)
    assert cancel_res["success"] is True

    # Verify ticket #3 is available again
    tickets_after_cancel = await db.get_raffle_tickets(rid)
    t3 = next(t for t in tickets_after_cancel if t["ticket_number"] == 3)
    assert t3["status"] == "available"

    # Pending orders is now empty
    pending_final = await db.get_cashier_pending_orders()
    assert len(pending_final) == 0
    print("✅ 1-Click cancellation succeeded! Tickets returned to available pool.")

    await db.close()
    if os.path.exists(db_name):
        os.remove(db_name)
    print("🎉 ALL CASHIER FLOW TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(test_cashier_flow())
