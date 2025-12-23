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
    reset_choice_keyboard,
    get_preferences_keyboard,
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
    await message.answer("Привет❕ \nМы рады помочь вам увидеть всю красоту <b> Республики Тывы </b>❕🏔️🤍 \n\nРасскажите нам чего бы вам хотелось❔ \nНажмите <i>'Установить предпочтения'</i>.", reply_markup=main_menu)


@router.message(lambda m: m.text == "Посмотреть предпочтения")
async def view_preferences(message: types.Message):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, message.from_user.id))
        user = q.scalars().first()

        if not user:
            await message.answer(
                "У вас ещё нет предпочтений и мы не можем подобрать маршруты. \nСначала установите их через кнопку <i>'Установить предпочтения'</i>.",
                reply_markup=main_menu)
            return

        prefs = json.loads(user.preferences) if user.preferences else {}

        if not prefs:
            await message.answer(
                "У вас ещё нет предпочтений и мы не можем подобрать маршруты. \nСначала установите их через кнопку <i>'Установить предпочтения'</i>.",
                reply_markup=main_menu)
            return

        # Форматируем предпочтения в читаемый вид
        prefs_text = "📋 <b>Ваши текущие пожелания</b> 📋\n\nПроверьте, что все <b>актуально</b>, если же нет, \nобновите предпочтения по кнопке внизу❕\n\n"

        # Сезон
        if prefs.get("season"):
            if prefs['season'] == "winter":
                prefs_text += f"- <b>Сезон:</b> зима\n"
            elif prefs['season'] == "spring":
                prefs_text += f"- <b>Сезон:</b> весна\n"
            elif prefs['season'] == "summer":
                prefs_text += f"- <b>Сезон:</b> лето\n"
            else:
                prefs_text += f"- <b>Сезон:</b> осень\n"
        else:
            prefs_text += "<b>Сезон:</b> не установлен\n"

        # Длина маршрута
        if prefs.get("length_km"):
            prefs_text += f"- <b>Длина маршрута:</b> {prefs['length_km']} км\n"
        else:
            prefs_text += "<b>Длина маршрута:</b> не установлена\n"

        # Цена
        if prefs.get("price_estimate"):
            prefs_text += f"- <b>Цена:</b> {prefs['price_estimate']} руб\n"
        else:
            prefs_text += "<b>Цена:</b> не установлена\n"

        # Сложность
        if prefs.get("difficulty"):
            prefs_text += f"- <b>Сложность:</b> {prefs['difficulty']}\n"
        else:
            prefs_text += "<b>Сложность:</b> не установлена\n"

        # Популярность
        if prefs.get("popularity"):
            prefs_text += f"- <b>Популярность:</b> {prefs['popularity']}/100\n"
        else:
            prefs_text += "<b>Популярность:</b> не установлена\n"

        # Транспорт
        if prefs.get("transport"):
            prefs_text += f"- <b>Транспорт:</b> {prefs['transport']}\n"
        else:
            prefs_text += "<b>Транспорт:</b> не установлен\n"

        # Теги
        if prefs.get("tags"):
            tags_str = ", ".join(prefs['tags'])
            prefs_text += f"- <b>Теги:</b> {tags_str}\n"
        else:
            prefs_text += "<b>Теги:</b> не установлены\n"

        # Статус настройки (если в процессе)
        if prefs.get("prefs_step"):
            steps = {
                "length_km": "ожидание ввода длины маршрута",
                "price_estimate": "ожидание ввода цены",
                "difficulty": "ожидание выбора сложности",
                "popularity": "ожидание ввода популярности",
                "transport": "ожидание выбора транспорта",
                "tags": "ожидание выбора тегов"
            }
            prefs_text += f"\n⏳ <i>Процесс настройки: {steps.get(prefs['prefs_step'], prefs['prefs_step'])}</i>"

        # Отправляем сообщение с кнопкой сброса
        from utils import get_preferences_keyboard  # импортируем вверху файла
        await message.answer(prefs_text, reply_markup=get_preferences_keyboard())


@router.message(lambda m: m.text == "Установить предпочтения")
async def ask_season(message: types.Message):
    # Спрашиваем, хочет ли пользователь сбросить текущие предпочтения
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, message.from_user.id))
        user = q.scalars().first()

        if user and user.preferences and user.preferences != "{}":
            await message.answer(
                "🖇️ У вас уже есть сохранённые предпочтения.\n"
                "Хотите сбросить их и начать заново или продолжить настройку с текущими❔",
                reply_markup=reset_choice_keyboard  # Используем клавиатуру из utils.py
            )
            return

    # Если предпочтений нет или они пустые, сразу переходим к выбору сезона
    await message.answer("Выберите сезон года:", reply_markup=season_buttons)


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

    await callback.message.answer("Хороший выбор❕\nВведите желаемую длину маршрута (км):")
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
                await message.answer("Сначала установите предпочтения через кнопку <i>'Установить предпочтения'</i>.")
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
                logs.append(f"➤{route['title']} \n📎 <i>score {score}</i>")
                await message.answer(
                    f"🏔️<b>{route['title']}</b> (score: {score})\n\n"
                    f"<i>{route.get('description')}</i>\n\n"
                    f"Длина: {route.get('length_km')} км\n"
                    f"Сложность: {route.get('difficulty')}\n"
                    f"Цена: {route.get('price_estimate')}\n"
                    f"Теги: {', '.join(route.get('tags', []))}"
                )
            # send simple log summary
            await message.answer("🗺️ <b>ТОП МАРШРУТОВ</b> 🗺️\n\n" + "\n".join(logs))
            return

        # catch-all
        # if user typed something unrelated, show the main menu
        await message.answer("Нажмите пожалуйста одну из кнопок меню 👇🏼:", reply_markup=main_menu)


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

    await callback.message.answer("Все выборы сохранены! 📂\nНажмите <i>'Найти маршруты'</i>, чтобы получить рекомендации \nили <i>'Посмотреть предпочтения'</i>, чтобы уточнить пожелания", reply_markup=main_menu)
    await callback.answer()


@router.callback_query(lambda c: c.data == "reset_and_start")
async def reset_and_start(callback: types.CallbackQuery):
    # Сбрасываем предпочтения
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()
        if user:
            user.preferences = "{}"
            session.add(user)
            await session.commit()

    # Начинаем новую настройку
    await callback.message.edit_text("Все предпочтения успешно сброшены ☑️ \nВыберите сезон:", reply_markup=season_buttons)
    await callback.answer()


@router.callback_query(lambda c: c.data == "continue_current")
async def continue_current(callback: types.CallbackQuery):
    # Продолжаем с текущими предпочтениями
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if user and user.preferences:
            prefs = json.loads(user.preferences)
            # Определяем текущий шаг
            current_step = prefs.get("prefs_step")

            if not current_step:
                # Если настройка была завершена, начинаем заново с выбора сезона
                await callback.message.edit_text("Выберите сезон года:", reply_markup=season_buttons)
            else:
                # Если настройка прервана, продолжаем с того же шага
                steps = {
                    "length_km": "Введите желаемую длину маршрута (км):",
                    "price_estimate": "Введите желаемую цену (руб):",
                    "difficulty": "Выберите сложность:",
                    "popularity": "Введите желаемую популярность (0–100):",
                    "transport": "Выберите транспорт:",
                    "tags": "Выберите предпочитаемые теги (можно несколько):"
                }

                message_text = f"Продолжаем настройку предпочтений. {steps.get(current_step, 'Выберите сезон:')}"

                if current_step == "difficulty":
                    await callback.message.edit_text(message_text, reply_markup=difficulty_buttons)
                elif current_step == "transport":
                    await callback.message.edit_text(message_text, reply_markup=transport_buttons)
                elif current_step == "tags":
                    await callback.message.edit_text(message_text, reply_markup=tags_buttons)
                else:
                    await callback.message.edit_text(message_text)
        else:
            await callback.message.edit_text("Выберите сезон года:", reply_markup=season_buttons)

    await callback.answer()

@router.callback_query(lambda c: c.data == "reset_prefs")
async def reset_preferences(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.answer("У вас нет сохранённых предпочтений ⛓️‍💥. Нажмите пожалуйста <i>'Установить предпочтения'</i>.")
            return

        # Сбрасываем предпочтения
        user.preferences = "{}"  # пустой JSON
        session.add(user)
        await session.commit()

        logger.info("User %s reset preferences", callback.from_user.id)

        await callback.message.edit_text(
            " ☑️ Все предпочтения успешно сброшены❕\n\nВы можете установить новые предпочтения через кнопку <i>'Установить предпочтения'</i>.",
            reply_markup=None)
        await callback.answer()
