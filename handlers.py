# handlers.py
import json
import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

from db import AsyncSessionLocal
from models import User
from recommender import recommend_routes
from utils import (
    main_menu,
    season_buttons,
    difficulty_buttons,
    transport_buttons,
    tags_buttons,
)

logger = logging.getLogger(__name__)
router = Router()

# Create bot and dispatcher here, but real token will be provided in run.py via environment.
# For convenience we will create placeholders; run.py will import bot, dp from here after setting token.
bot: Bot = None
dp: Dispatcher = None


async def upsert_user(session, tg_id: int, name: str | None = None) -> User:
    q = await session.execute(select_user_by_tg(session, tg_id))
    user = q.scalars().first()
    if not user:
        user = User(tg_id=tg_id, name=name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    elif name and user.name != name:
        user.name = name
        await session.commit()
        await session.refresh(user)
    return user


# helper to select user
from sqlalchemy import select
def select_user_by_tg(session, tg_id):
    return select(User).where(User.tg_id == tg_id)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # ensure user exists
    async with AsyncSessionLocal() as session:
        await upsert_user(session, message.from_user.id, message.from_user.full_name)
    await message.answer("Привет! Выберите действие:", reply_markup=main_menu)


@router.message(lambda m: m.text == "Установить предпочтения")
async def ask_season(message: types.Message):
    await message.answer("Выберите сезон:", reply_markup=season_buttons)


@router.callback_query(lambda c: c.data and c.data.startswith("season_"))
async def set_season(callback: types.CallbackQuery):
    season = callback.data.split("_")[1]
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()
        if not user:
            user = await upsert_user(session, callback.from_user.id, callback.from_user.full_name)
        prefs = json.loads(user.preferences) if user.preferences else {}
        prefs["season"] = season
        prefs["prefs_step"] = "length_km"
        user.preferences = json.dumps(prefs, ensure_ascii=False)
        session.add(user)
        await session.commit()
        logger.info("User %s set season=%s", callback.from_user.id, season)

    await callback.message.answer("Сезон установлен!\nВведите желаемую длину маршрута (км):")
    await callback.answer()


@router.message()
async def collect_prefs(message: types.Message):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, message.from_user.id))
        user = q.scalars().first()
        if not user:
            user = await upsert_user(session, message.from_user.id, message.from_user.full_name)
        prefs = json.loads(user.preferences) if user.preferences else {}
        step = prefs.get("prefs_step")

        # length_km
        if step == "length_km":
            try:
                prefs["length_km"] = float(message.text)
                prefs["prefs_step"] = "price_estimate"
                user.preferences = json.dumps(prefs, ensure_ascii=False)
                session.add(user)
                await session.commit()
                await message.answer("Введите желаемую цену (руб):")
            except Exception:
                await message.answer("Пожалуйста, введите число для длины (например: 12 или 45.5).")
            return

        # price_estimate
        if step == "price_estimate":
            try:
                prefs["price_estimate"] = float(message.text)
                prefs["prefs_step"] = "difficulty"
                user.preferences = json.dumps(prefs, ensure_ascii=False)
                session.add(user)
                await session.commit()
                await message.answer("Выберите сложность:", reply_markup=difficulty_buttons)
            except Exception:
                await message.answer("Пожалуйста, введите число для цены (например: 2000).")
            return

        # popularity input step (this step is set after difficulty)
        if step == "popularity":
            try:
                val = int(message.text)
                if not (0 <= val <= 100):
                    raise ValueError()
                prefs["popularity"] = val
                prefs["prefs_step"] = "transport"
                user.preferences = json.dumps(prefs, ensure_ascii=False)
                session.add(user)
                await session.commit()
                await message.answer("Выберите транспорт:", reply_markup=transport_buttons)
            except Exception:
                await message.answer("Введите число от 0 до 100.")
            return

        # If user requests find routes by pressing button
        if message.text == "Найти маршруты":
            prefs = json.loads(user.preferences) if user.preferences else {}
            if not prefs:
                await message.answer("Сначала установите предпочтения через кнопку 'Установить предпочтения'.")
                return

            # recommend
            recs = await recommend_routes(session, prefs, limit=10)
            logs = []
            if not recs:
                await message.answer("Не найдено маршрутов.")
                return

            for r in recs:
                route = r["route"]
                score = r["score"]
                logs.append(f"{route['title']} — score {score}")
                await message.answer(
                    f"<b>{route['title']}</b> (score: {score})\n"
                    f"{route.get('description')}\n"
                    f"Длина: {route.get('length_km')} км\n"
                    f"Сложность: {route.get('difficulty')}\n"
                    f"Цена: {route.get('price_estimate')}\n"
                    f"Теги: {', '.join(route.get('tags', []))}"
                )
            # send simple log summary
            await message.answer("<b>ЛОГ: ТОП-РЕЗУЛЬТАТЫ</b>\n" + "\n".join(logs))
            return

        # catch-all
        # if user typed something unrelated, show the main menu
        await message.answer("Нажмите одну из кнопок меню:", reply_markup=main_menu)


@router.callback_query(lambda c: c.data and c.data.startswith("diff_"))
async def set_diff(callback: types.CallbackQuery):
    diff = callback.data.split("_")[1]
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()
        if not user:
            user = await upsert_user(session, callback.from_user.id, callback.from_user.full_name)
        prefs = json.loads(user.preferences) if user.preferences else {}
        prefs["difficulty"] = diff
        prefs["prefs_step"] = "popularity"
        user.preferences = json.dumps(prefs, ensure_ascii=False)
        session.add(user)
        await session.commit()
        logger.info("User %s set difficulty=%s", callback.from_user.id, diff)

    await callback.message.answer("Введите желаемую популярность (0–100):")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("trans_"))
async def set_transport(callback: types.CallbackQuery):
    transport = callback.data.split("_")[1]
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()
        if not user:
            user = await upsert_user(session, callback.from_user.id, callback.from_user.full_name)
        prefs = json.loads(user.preferences) if user.preferences else {}
        prefs["transport"] = transport
        prefs["prefs_step"] = "tags"
        user.preferences = json.dumps(prefs, ensure_ascii=False)
        session.add(user)
        await session.commit()
        logger.info("User %s set transport=%s", callback.from_user.id, transport)

    await callback.message.answer("Выберите предпочитаемые теги (можно несколько):", reply_markup=tags_buttons)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("tag_"))
async def select_tag(callback: types.CallbackQuery):
    tag = callback.data.split("_", 1)[1]
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()
        if not user:
            user = await upsert_user(session, callback.from_user.id, callback.from_user.full_name)
        prefs = json.loads(user.preferences) if user.preferences else {}
        tags = prefs.get("tags", [])
        if tag not in tags:
            tags.append(tag)
        prefs["tags"] = tags
        user.preferences = json.dumps(prefs, ensure_ascii=False)
        session.add(user)
        await session.commit()
        logger.info("User %s added tag=%s", callback.from_user.id, tag)

    await callback.answer(f"Добавлен тег: {tag}")


@router.callback_query(lambda c: c.data == "tags_done")
async def tags_done(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()
        if user:
            prefs = json.loads(user.preferences) if user.preferences else {}
            prefs["prefs_step"] = None
            user.preferences = json.dumps(prefs, ensure_ascii=False)
            session.add(user)
            await session.commit()
            logger.info("User %s finished tags selection", callback.from_user.id)

    await callback.message.answer("Теги сохранены!\nНажмите «Найти маршруты» чтобы получить рекомендации.", reply_markup=main_menu)
    await callback.answer()
