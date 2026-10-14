import asyncio
import os
import sys
import uuid

sys.path.insert(0, ".")

from src.database.db import Database
from src.services.lottery import LotteryService
from src.services.sbp import SBPService
from src.services.notification import NotificationService


async def test_nickname_profile():
    test_db = f"data/test_nick_{uuid.uuid4().hex[:6]}.db"
    db = Database(test_db)
    await db.connect()

    sbp = SBPService()
    noti = NotificationService(db=db)
    lottery = LotteryService(db=db, sbp_service=sbp, notification_service=noti)

    # 1. Test Nickname uniqueness
    # Available check
    assert await db.check_nickname_available("LuckyTiger", current_user_id=100) is True
    # Disallow user_xxx
    assert await db.check_nickname_available("user_12345", current_user_id=100) is False
    # Disallow < 3 chars
    assert await db.check_nickname_available("ab", current_user_id=100) is False

    # Save user 100 profile with nickname "LuckyTiger" and phone "+79991112233"
    prof1 = await db.update_user_profile(
        user_id=100,
        nickname="LuckyTiger",
        phone="+7 (999) 111-22-33",
    )
    assert prof1["username"] == "LuckyTiger"
    assert prof1["phone"] == "+7 (999) 111-22-33"

    # User 100 checking their own nickname -> True
    assert await db.check_nickname_available("LuckyTiger", current_user_id=100) is True
    # Another user (200) checking "luckytiger" -> False (taken!)
    assert await db.check_nickname_available("luckytiger", current_user_id=200) is False

    # User 200 picks "HappyCat" without phone
    prof2 = await db.update_user_profile(
        user_id=200,
        nickname="HappyCat",
        phone="",
    )
    assert prof2["username"] == "HappyCat"
    assert prof2["phone"] == ""

    # 2. Create raffle with 2 prize lots
    rid = f"raffle_{uuid.uuid4().hex[:6]}"
    await db.create_raffle(
        raffle_id=rid,
        title="Тест никнеймов",
        description="Розыгрыш",
        prize_image_url="https://example.com/p.jpg",
        total_tickets=10,
        price_per_ticket=50.0,
        prizes=[
            {"place": 1, "lot_number": 1, "title": "Лот 1 (iPhone)", "prize_image_url": "https://example.com/1.jpg"},
            {"place": 2, "lot_number": 2, "title": "Лот 2 (Наушники)", "prize_image_url": "https://example.com/2.jpg"},
        ]
    )

    # User 100 reserves ticket 1 with their chosen nickname & phone
    res1 = await lottery.reserve_specific_tickets(
        raffle_id=rid,
        user_id=100,
        username="LuckyTiger",
        ticket_numbers=[1],
        phone="+7 (999) 111-22-33",
    )
    assert res1["success"] is True

    # User 200 reserves ticket 2 with anonymous nickname
    res2 = await lottery.reserve_specific_tickets(
        raffle_id=rid,
        user_id=200,
        username="HappyCat",
        ticket_numbers=[2],
    )
    assert res2["success"] is True

    # Confirm payments
    await lottery.complete_sbp_payment(res1["order_id"])
    await lottery.complete_sbp_payment(res2["order_id"])

    # Verify pending reservations (should be empty since paid)
    pending = await db.get_raffle_pending_orders(rid)
    assert len(pending) == 0

    # Verify tickets have username and phone joined
    tickets = await db.get_raffle_tickets(rid)
    t1 = next(t for t in tickets if t["ticket_number"] == 1)
    assert t1["username"] == "LuckyTiger"
    assert t1["phone"] == "+7 (999) 111-22-33"

    t2 = next(t for t in tickets if t["ticket_number"] == 2)
    assert t2["username"] == "HappyCat"
    assert t2["phone"] == ""

    # 3. Draw winners
    draw_res = await lottery.draw_raffle_winner(rid)
    assert draw_res["success"] is True
    winners = draw_res["winners"]
    assert len(winners) == 2

    # Verify winners have nicknames
    usernames = {w["username"] for w in winners}
    assert usernames == {"LuckyTiger", "HappyCat"}

    print("[OK] ALL NICKNAME & PROFILE TESTS PASSED!")
    await db.close()
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(test_nickname_profile())
