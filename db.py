# db.py - обновляем с реальными ссылками
import os
import json
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from models import Base, Route, route_tags, route_seasons, route_transports

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./tuva_travel.db")
logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db_and_seed():
    logger.info("Initializing DB and seeding (if needed)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        q = await session.execute(select(func.count(Route.id)))
        count = q.scalar_one()
        logger.info("Routes in DB: %s", count)
        if count == 0:
            logger.info("Seeding sample routes...")
            
            # Обновленные данные с реальными ссылками из скриншота
            sample_routes = [
                {
                    "title": "Кызыл — озеро Дьенгек",
                    "description": "Лёгкий однодневный маршрут",
                    "length_km": 40.0,
                    "difficulty": "легко",
                    "price_estimate": 8500.0,
                    "popularity": 50,
                    "link": "https://yandex.ru/maps/-/CLD~4Lnt",  # Ссылка из таблицы
                    "tags": ["nature", "family", "hiking"],
                    "seasons": ["summer", "autumn"],
                    "transports": ["car", "minibus"]
                },
                {
                    "title": "Чадан — курган Чыратас",
                    "description": "Двухдневный маршрут с треккингом",
                    "length_km": 120.0,
                    "difficulty": "варьируется",
                    "price_estimate": 10000.0,
                    "popularity": 30,
                    "link": "https://yandex.ru/maps/-/CLD~eImu",  # Ссылка из таблицы
                    "tags": ["adventure", "trekking", "nature"],
                    "seasons": ["summer"],
                    "transports": ["car"]
                },
                {
                    "title": "Шашлык тур с гидом",
                    "description": "Короткая экскурсия с дегустацией",
                    "length_km": 10.0,
                    "difficulty": "легко",
                    "price_estimate": 8000.0,
                    "popularity": 80,
                    "link": None,  # NULL в таблице
                    "tags": ["culture", "food", "family"],
                    "seasons": ["spring", "summer", "autumn"],
                    "transports": ["car", "minibus"]
                },
                {
                    "title": "Кызыл — Центр Азии — Хайыран-Хол",
                    "description": "Обзорный маршрут по столице с посещением географического центра Азии и хурула.",
                    "length_km": 28.0,
                    "difficulty": "легко",
                    "price_estimate": 1500.0,
                    "popularity": 90,
                    "link": "https://yandex.ru/maps/-/CLsKAIKK",
                    "tags": ["culture", "city", "history"],
                    "seasons": ["summer", "spring", "autumn", "winter"],
                    "transports": ["car", "minibus"]
                },
                {
                    "title": "Кызыл — Тос-Булак",
                    "description": "Однодневный маршрут к природному парку Тос-Булак, площадке для Наадыма.",
                    "length_km": 16.0,
                    "difficulty": "легко",
                    "price_estimate": 1300.0,
                    "popularity": 70,
                    "link": "https://yandex.ru/maps/-/CLsKA-ND",
                    "tags": ["nature", "family"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["car", "minibus"]
                },
                {
                    "title": "Кызыл — Долина царей (Аржаан-III, Бай-Даг)",
                    "description": "Поездка к древним курганам, включая знаменитый курган Аржаан-II.",
                    "length_km": 60.0,
                    "difficulty": "легко",
                    "price_estimate": 2000.0,
                    "popularity": 75,
                    "link": "https://yandex.ru/maps/-/CLsK188H",
                    "tags": ["history", "archaeology", "culture"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["car"]
                },
                {
                    "title": "Ак-Довурак — Чадаана — монастырь Устуу-Хурээ",
                    "description": "Культурный маршрут по западной Туве с посещением легендарного храма.",
                    "length_km": 140.0,
                    "difficulty": "легко",
                    "price_estimate": 8500.0,
                    "popularity": 50,
                    "link": "https://yandex.ru/maps/-/CLsKM6zx",
                    "tags": ["culture", "religion", "history"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["car", "minibus"]
                },
                {
                    "title": "Кызыл — Уш-Белдир через Чаа-Холь",
                    "description": "Популярный маршрут в горно-таёжную зону, к горячим источникам Уш-Белдир.",
                    "length_km": 280.0,
                    "difficulty": "варьируется",
                    "price_estimate": 7000.0,
                    "popularity": 65,
                    "link": "https://yandex.ru/maps/-/CLDxV25L",
                    "tags": ["nature", "hot_springs", "adventure"],
                    "seasons": ["summer"],
                    "transports": ["car", "4x4"]
                },
                {
                    "title": "Чаа-Холь — Кара-Холь",
                    "description": "Треккинг и джип-тур к озеру Кара-Холь — одному из красивейших озёр Тувы.",
                    "length_km": 90.0,
                    "difficulty": "варьируется",
                    "price_estimate": 4800.0,
                    "popularity": 40,
                    "link": "https://yandex.ru/maps/-/CLD~mNmD",
                    "tags": ["nature", "trekking", "photography"],
                    "seasons": ["summer", "autumn"],
                    "transports": ["car", "4x4"]
                },
                {
                    "title": "Тоора-Хем — озеро Азас",
                    "description": "Маршрут в сердце Тоджинского района к озеру Азас (Азыас), с катанием на лодках.",
                    "length_km": 110.0,
                    "difficulty": "варьируется",
                    "price_estimate": 8500.0,
                    "popularity": 60,
                    "link": "https://yandex.ru/maps/-/CLDx6F5A",
                    "tags": ["wildlife", "nature", "adventure"],
                    "seasons": ["summer"],
                    "transports": ["boat", "car"]
                },
                {
                    "title": "Кызыл — Сарыг-Сеп — Алдын-Булак",
                    "description": "Экскурсия в этнокультурный комплекс Алдын-Булак с мастер-классами.",
                    "length_km": 48.0,
                    "difficulty": "легко",
                    "price_estimate": 2500.0,
                    "popularity": 80,
                    "link": "https://yandex.ru/maps/-/CLDx60iM",
                    "tags": ["culture", "family", "food"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["car", "minibus"]
                },
                {
                    "title": "Кызыл — пороги Каа-Хема",
                    "description": "Рафтинг/сплав по реке Малый Енисей с посещением окрестных водопадов.",
                    "length_km": 160.0,
                    "difficulty": "сложно",
                    "price_estimate": 18000.0,
                    "popularity": 45,
                    "link": "https://yandex.ru/maps/-/CLDxbW4~",  # Убрал лишнюю кавычку
                    "tags": ["rafting", "adventure", "sport"],
                    "seasons": ["summer"],
                    "transports": ["car", "boat"]
                },
                {
                    "title": "Кызыл — Аржаан Чалма-Тайга",
                    "description": "Поездка к священному минеральному источнику Чалма-Тайга.",
                    "length_km": 88.0,
                    "difficulty": "легко",
                    "price_estimate": 3000.0,
                    "popularity": 40,
                    "link": "https://yandex.ru/maps/-/CLDxbXzE",
                    "tags": ["spiritual", "nature"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["car"]
                },
                {
                    "title": "Самагалтай — Дурген",
                    "description": "Поездка в Тес-Хемский район к песчаным массивам Дурген — тувинской пустыне.",
                    "length_km": 60.0,
                    "difficulty": "легко",
                    "price_estimate": 8000.0,
                    "popularity": 55,
                    "link": "https://yandex.ru/maps/-/CLDxfYyf",
                    "tags": ["nature", "desert", "photography"],
                    "seasons": ["summer"],
                    "transports": ["car"]
                },
                {
                    "title": "Кызыл — гора Догээ",
                    "description": "Лёгкий подъём на гору Догээ рядом со столицей, панорама долины Енисея.",
                    "length_km": 18.0,
                    "difficulty": "легко",
                    "price_estimate": 500.0,
                    "popularity": 85,
                    "link": "https://yandex.ru/maps/-/CLDxfVPJ",
                    "tags": ["hiking", "family", "city"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["car"]
                },
                {
                    "title": "Треккинг на гору Догээ (Кызыл)",
                    "description": "Лёгкий подъём на одну из главных обзорных точек столицы. Вид на Енисей и весь Кызыл.",
                    "length_km": 6.0,
                    "difficulty": "легко",
                    "price_estimate": 0.0,
                    "popularity": 90,
                    "link": "https://yandex.ru/maps/-/CLDxfVPJ",
                    "tags": ["hiking", "panorama", "city"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Треккинг у озера Хадын",
                    "description": "Пеший маршрут вокруг озера Хадын с выходом к болотистым поймам и смотровым точкам.",
                    "length_km": 18.0,
                    "difficulty": "легко",
                    "price_estimate": 0.0,
                    "popularity": 70,
                    "link": "https://yandex.ru/maps/-/CLDxf88I",
                    "tags": ["nature", "family", "hiking"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Уюкская долина — Пор-Бажын (пешая часть)",
                    "description": "Пешая часть маршрута по Уюкской котловине с осмотром курганов и подъёмом на ближайшие хребты.",
                    "length_km": 14.0,
                    "difficulty": "варьируется",
                    "price_estimate": 1000.0,
                    "popularity": 50,
                    "link": "https://yandex.ru/maps/-/CLDxjJPx",
                    "tags": ["history", "archaeology", "nature", "trekking"],
                    "seasons": ["summer", "autumn"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Ак-Кыргара — водопады Чаш-Тал",
                    "description": "Красивый пеший маршрут к водопадам на территории природного парка Ак-Кыргара.",
                    "length_km": 10.0,
                    "difficulty": "легко",
                    "price_estimate": 900.0,
                    "popularity": 65,
                    "link": "https://yandex.ru/maps/-/CLDxjHM~",  # Убрал лишнюю кавычку
                    "tags": ["nature", "waterfalls", "hiking"],
                    "seasons": ["summer"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Туран — гора Теве-Хая",
                    "description": "Подъём на одну из живописных вершин Туранского хребта, обзор Улуг-Хемской долины.",
                    "length_km": 11.0,
                    "difficulty": "варьируется",
                    "price_estimate": 0.0,
                    "popularity": 45,
                    "link": "https://yandex.ru/maps/-/CLDxnAit",
                    "tags": ["hiking", "panorama", "nature"],
                    "seasons": ["summer", "autumn"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Сарыг-Сеп — подъём к скалам Чолдо",
                    "description": "Невысокий, но живописный маршрут к скалам Чолдо над Каа-Хемом.",
                    "length_km": 7.0,
                    "difficulty": "легко",
                    "price_estimate": 0.0,
                    "popularity": 55,
                    "link": "https://yandex.ru/maps/-/CLDxr8mL",
                    "tags": ["hiking", "nature"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Бай-Тайга — перевал Арыскан",
                    "description": "Горный маршрут по хребтам Бай-Тайги через перевал Арыскан. Потрясающие виды высокогорья.",
                    "length_km": 18.0,
                    "difficulty": "сложно",
                    "price_estimate": 0.0,
                    "popularity": 35,
                    "link": "https://yandex.ru/maps/-/CLDxr-nC",
                    "tags": ["mountains", "trekking", "adventure", "nature"],
                    "seasons": ["summer"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Эрзин — Чыргакы-Тайга",
                    "description": "Пешеходный маршрут по югу Тувы вдоль монгольской границы. Степи и скальные выходы.",
                    "length_km": 9.0,
                    "difficulty": "варьируется",
                    "price_estimate": 0.0,
                    "popularity": 40,
                    "link": "https://yandex.ru/maps/-/CLDxv4ZY",
                    "tags": ["hiking", "steppe", "nature"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Танды — гора Хайыракан",
                    "description": "Священная гора Хайыракан: подъём по тропе паломников, виды на долину Улуг-Хема.",
                    "length_km": 8.0,
                    "difficulty": "легко",
                    "price_estimate": 200.0,
                    "popularity": 75,
                    "link": "https://yandex.ru/maps/-/CLDxvZ3Z",
                    "tags": ["spiritual", "hiking", "culture"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["on_foot"]
                },
                {
                    "title": "Кызыл — тропа вдоль Бий-Хема",
                    "description": "Пеший маршрут вдоль Енисея (Бий-Хема) через прибрежные сосновые леса.",
                    "length_km": 8.0,
                    "difficulty": "легко",
                    "price_estimate": 0.0,
                    "popularity": 85,
                    "link": "https://yandex.ru/maps/-/CLDxvLj0",
                    "tags": ["nature", "family", "hiking"],
                    "seasons": ["summer", "spring", "autumn"],
                    "transports": ["on_foot"]
                }
            ]

            for r in sample_routes:
                route = Route(
                    title=r["title"],
                    description=r.get("description"),
                    length_km=r.get("length_km"),
                    difficulty=r.get("difficulty"),
                    price_estimate=r.get("price_estimate"),
                    link=r.get("link"),  # Добавляем ссылку
                    popularity=r.get("popularity", 0),
                )
                session.add(route)
                await session.flush()
                for tag in r.get("tags", []):
                    await session.execute(route_tags.insert().values(route_id=route.id, tag=tag))
                for s in r.get("seasons", []):
                    await session.execute(route_seasons.insert().values(route_id=route.id, season=s))
                for t in r.get("transports", []):
                    await session.execute(route_transports.insert().values(route_id=route.id, transport=t))
            await session.commit()
            logger.info("Seeding finished.")
        else:
            logger.info("DB already seeded.")