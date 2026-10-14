"""Automated end-to-end test suite for BotMAX: Ticket Drawdown & SBP Payments"""

import asyncio
import os
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.config import Config
from src.database.db import Database
from src.database.seed import seed_default_raffles
from src.services.sbp import SBPService
from src.services.notification import NotificationService
from src.services.lottery import LotteryService


async def run_tests():
    print("==================================================")
    print(">>> STARTING BOTMAX END-TO-END TESTS")
    print("==================================================")

    test_db_path = "./data/test_botmax.db"
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

    db = Database(test_db_path)
    await db.connect()
    print("[OK] Database initialized successfully")

    # 1. Test Seeding
    await seed_default_raffles(db)
    raffles = await db.get_all_raffles()
    assert len(raffles) >= 2, f"Expected at least 2 seeded games, got {len(raffles)}"
    assert len(raffles[0].get("prizes", [])) >= 2, "Expected first game to have multiple prizes"
    print(f"[OK] Seeded {len(raffles)} default games with multi-prize places")

    test_raffle = raffles[0]
    test_raffle_id = test_raffle["id"]
    raffle = await db.get_raffle(test_raffle_id)
    assert raffle is not None
    assert raffle["total_tickets"] > 0
    initial_available = raffle["available_tickets"]
    print(f"[OK] Initial state for {raffle['title']}: Total={raffle['total_tickets']}, Available={initial_available}, Sold={raffle['sold_tickets']}")

    # 2. Test SBP Service
    sbp_service = SBPService("test_merchant", "secret123")
    notification_service = NotificationService()
    lottery_service = LotteryService(
        db=db,
        sbp_service=sbp_service,
        notification_service=notification_service,
        reservation_duration_minutes=10,
    )

    # 3. Test Ticket Reservation ("Убытие билетов")
    user_id = 999111
    username = "test_lucky_user"

    # Find free ticket numbers
    tickets = await db.get_raffle_tickets(test_raffle_id)
    free_nums = [t["ticket_number"] for t in tickets if t["status"] == "available"]
    test_pick = free_nums[:3]  # Pick 3 tickets
    print(f"-> Reserving tickets: {test_pick}...")

    reserve_res = await lottery_service.reserve_specific_tickets(
        raffle_id=test_raffle_id,
        user_id=user_id,
        username=username,
        ticket_numbers=test_pick,
    )
    assert reserve_res["success"] is True, f"Reservation failed: {reserve_res}"
    order_id = reserve_res["order_id"]
    print(f"[OK] Order created: {order_id}, Amount: {reserve_res['amount']} RUB")
    print(f"[OK] SBP QR Data URL generated: {reserve_res['sbp']['qr_data_url'][:40]}...")
    print(f"[OK] SBP NSPK URL: {reserve_res['sbp']['nspk_url']}")

    # Verify tickets status and pool reduction
    raffle_after_res = await db.get_raffle(test_raffle_id)
    assert raffle_after_res["available_tickets"] == initial_available - 3, "Available pool did not decrease!"
    assert raffle_after_res["reserved_tickets"] == 3
    print(f"[OK] LIVE DRAWDOWN VERIFIED: Available tickets decreased from {initial_available} to {raffle_after_res['available_tickets']}")

    # 4. Test Collision Prevention (Trying to reserve already reserved tickets)
    collision_res = await lottery_service.reserve_specific_tickets(
        raffle_id=test_raffle_id,
        user_id=888222,
        username="another_user",
        ticket_numbers=[test_pick[0]],
    )
    assert collision_res["success"] is False, "Collision check failed! Another user was able to reserve already held ticket!"
    print(f"[OK] Collision prevention verified: {collision_res['error']}")

    # 5. Test SBP Payment Confirmation
    print(f"-> Confirming SBP payment for order {order_id}...")
    pay_res = await lottery_service.complete_sbp_payment(order_id)
    assert pay_res["success"] is True
    print("[OK] SBP Payment confirmed successfully!")

    # Verify permanent drawdown
    raffle_after_pay = await db.get_raffle(test_raffle_id)
    assert raffle_after_pay["reserved_tickets"] == 0
    assert raffle_after_pay["sold_tickets"] == raffle["sold_tickets"] + 3
    print(f"[OK] PERMANENT DRAWDOWN VERIFIED: Sold count increased to {raffle_after_pay['sold_tickets']}")

    # 6. Test Provably Fair Draw (Winner selection)
    print("-> Testing provably fair winner draw...")
    draw_res = await lottery_service.draw_raffle_winner(test_raffle_id)
    assert draw_res["success"] is True
    print(f"[OK] Winner drawn: Ticket #{draw_res['winning_ticket_number']}, User: @{draw_res['winner_username']}")

    # 7. Test User Portfolio
    user_tickets = await db.get_user_tickets(user_id)
    assert len(user_tickets) == 3
    print(f"[OK] User portfolio verified: {len(user_tickets)} tickets found for user {user_id}")

    # Clean up test DB
    await db.close()
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

    print("==================================================")
    print(">>> ALL TESTS PASSED SUCCESSFULLY! 100% GREEN! :)")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
