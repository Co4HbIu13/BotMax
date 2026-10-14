import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
import unittest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.services.notification import NotificationService


class TestNotificationDelivery(unittest.IsolatedAsyncioTestCase):
    async def test_notify_admin_and_group_broadcast(self):
        # Mock bot
        mock_bot = MagicMock()
        mock_bot.me = MagicMock()
        mock_bot.me.user_id = 471249415  # bot's own user ID
        mock_bot.send_message = AsyncMock(return_value=True)

        # Mock DB
        mock_db = MagicMock()
        mock_db.get_admin_max_user_ids = AsyncMock(return_value=[916217, 376514])
        mock_db.get_active_chats = AsyncMock(return_value=[{"chat_id": -79357085377885}])

        # Init notification service
        service = NotificationService(
            bot=mock_bot,
            db=mock_db,
            admin_ids=[471249415],  # contains bot ID which must be ignored
            mini_app_url="https://anussai.duckdns.org",
        )

        success = await service.notify_admin_new_reservation(
            raffle_title="Мясорубка",
            buyer_username="бобр",
            buyer_user_id=376514,
            buyer_phone="+79991234567",
            ticket_numbers=[2, 7],
            amount=200.0,
            order_id="ord_TEST1234",
            recipient_name="Дмитрий Л",
            recipient_phone="+79135355314",
            recipient_bank="Озон банк",
        )

        self.assertTrue(success)

        # Verify bot.send_message calls
        calls = mock_bot.send_message.call_args_list
        sent_user_ids = [c.kwargs.get("user_id") for c in calls if "user_id" in c.kwargs]
        sent_chat_ids = [c.kwargs.get("chat_id") for c in calls if "chat_id" in c.kwargs]

        # 1. Bot's own ID must NOT be messaged
        self.assertNotIn(471249415, sent_user_ids)

        # 2. Registered admins must be messaged
        self.assertIn(916217, sent_user_ids)
        self.assertIn(376514, sent_user_ids)

        # 3. Group chat must be notified
        self.assertIn(-79357085377885, sent_chat_ids)

        # 4. Content check
        call_texts = [c.kwargs.get("text", "") for c in calls]
        for t in call_texts:
            self.assertIn("Мясорубка", t)
            self.assertIn("ord_TEST1234", t)
            self.assertIn("200.00 ₽", t)
            self.assertIn("Озон банк", t)

        print("✅ ALL NOTIFICATION SERVICE TESTS PASSED!")


if __name__ == "__main__":
    unittest.main()
