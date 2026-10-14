"""Default prize lottery seeder for BotMAX"""

import logging
from typing import Dict, Any, List
from .db import Database

logger = logging.getLogger("botmax.seed")

DEFAULT_RAFFLES: List[Dict[str, Any]] = [
    {
        "id": "game_kuhnya_master",
        "lot_number": 1,
        "title": "🍳 Кухонный батл: Посуда и бытовая техника",
        "description": "Большая семейная игра! 1 купленный билет участвует в розыгрыше всех трех призовых мест (сковорода, порошок, набор посуды).",
        "category": "lot",
        "prize_image_url": "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80",
        "total_tickets": 50,
        "price_per_ticket": 100.0,
        "pre_sold_count": 22,
        "prizes": [
            {
                "place": 1,
                "lot_number": 1,
                "title": "🍳 Сковорода Tefal с антипригарным покрытием 28 см",
                "prize_image_url": "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80",
                "description": "Оригинальная сковорода Tefal со стойким антипригарным покрытием Titanium.",
            },
            {
                "place": 2,
                "lot_number": 2,
                "title": "🧺 Стиральный порошок Ariel Горный Родник Автомат 9 кг",
                "prize_image_url": "https://images.unsplash.com/photo-1585421514284-efb74c2b69ba?auto=format&fit=crop&w=800&q=80",
                "description": "Большая экономичная упаковка 9 кг премиального порошка Ariel.",
            },
            {
                "place": 3,
                "lot_number": 3,
                "title": "🥘 Набор кухонной посуды из нержавеющей стали (6 предметов)",
                "prize_image_url": "https://images.unsplash.com/photo-1584990347449-399c51239bf0?auto=format&fit=crop&w=800&q=80",
                "description": "Премиальный комплект кастрюль и ковша со стеклянными крышками.",
            },
        ],
    },
    {
        "id": "game_chistota_uyut",
        "lot_number": 2,
        "title": "🧹 Чистый дом: Робот-пылесос и средства для дома",
        "description": "Призы для идеальной чистоты в вашем доме! 2 ценных призовых места в одной игре.",
        "category": "lot",
        "prize_image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
        "total_tickets": 60,
        "price_per_ticket": 150.0,
        "pre_sold_count": 28,
        "prizes": [
            {
                "place": 1,
                "lot_number": 1,
                "title": "🧹 Робот-пылесос Xiaomi Robot Vacuum с влажной уборкой",
                "prize_image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
                "description": "Умный робот-пылесос с лазерной навигацией LiDAR.",
            },
            {
                "place": 2,
                "lot_number": 2,
                "title": "🧺 Стиральный порошок Ariel Горный Родник Автомат 9 кг",
                "prize_image_url": "https://images.unsplash.com/photo-1585421514284-efb74c2b69ba?auto=format&fit=crop&w=800&q=80",
                "description": "Большая экономичная упаковка 9 кг премиального порошка Ariel.",
            },
        ],
    },
]

DUMMY_BUYERS = [
    (101, "alex_spb", "Алексей"),
    (102, "dmitry_k", "Дмитрий"),
    (103, "elena_m", "Елена"),
    (104, "sergey_dev", "Сергей"),
    (105, "olga_v", "Ольга"),
    (106, "artem_99", "Артём"),
    (107, "maxim_pro", "Максим"),
    (108, "victoria_s", "Виктория"),
]


async def seed_default_raffles(db: Database) -> None:
    """Check if database is empty and seed initial raffles and tickets"""
    existing = await db.get_all_raffles()
    if existing:
        logger.info(f"Database already contains {len(existing)} raffles. Skipping seed.")
        return

    logger.info("Seeding initial prize raffles...")
    conn = await db.connect()

    for item in DEFAULT_RAFFLES:
        raffle_id = item["id"]
        total = item["total_tickets"]
        pre_sold = item["pre_sold_count"]

        await db.create_raffle(
            raffle_id=raffle_id,
            title=item["title"],
            description=item["description"],
            prize_image_url=item["prize_image_url"],
            total_tickets=total,
            price_per_ticket=item["price_per_ticket"],
            lot_number=item.get("lot_number", 1),
            category=item.get("category", "lot"),
            prizes=item.get("prizes"),
        )

        # Pre-sell a portion of tickets to simulate active live drawdown
        if pre_sold > 0:
            sold_numbers = list(range(1, pre_sold + 1))
            async with conn.cursor() as cur:
                for idx, t_num in enumerate(sold_numbers):
                    buyer = DUMMY_BUYERS[idx % len(DUMMY_BUYERS)]
                    await cur.execute("""
                        UPDATE tickets
                        SET status = 'sold',
                            user_id = ?,
                            username = ?,
                            sold_at = datetime('now', '-' || ? || ' minutes')
                        WHERE raffle_id = ? AND ticket_number = ?
                    """, (buyer[0], buyer[1], (pre_sold - idx) * 12, raffle_id, t_num))
            await conn.commit()
            logger.info(f"Raffle {raffle_id}: pre-sold {pre_sold}/{total} tickets for initial live state.")

    logger.info("Default raffles successfully seeded.")
