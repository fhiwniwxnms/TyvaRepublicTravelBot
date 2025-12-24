import json
import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, delete
from models import Favorite, route_transports, route_seasons, route_tags, Route

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


from sqlalchemy import select


def select_user_by_tg(session, tg_id):
    return select(User).where(User.tg_id == tg_id)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async with AsyncSessionLocal() as session:
        await upsert_user(session, message.from_user.id, message.from_user.full_name)
    await message.answer(
        "Привет❕ \nМы рады помочь вам увидеть всю красоту <b> Республики Тывы </b>❕🏔️🤍 \n\nРасскажите нам чего бы вам хотелось❔ \nНажмите <i>'Установить предпочтения'</i>.",
        reply_markup=main_menu)


@router.message(lambda m: m.text == "Мои маршруты")
async def my_routes(message: types.Message):
    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        q = await session.execute(select_user_by_tg(session, message.from_user.id))
        user = q.scalars().first()

        if not user:
            await message.answer("Пользователь не найден.")
            return

        # Получаем избранные маршруты
        favorites_q = await session.execute(
            select(Favorite).where(Favorite.user_id == user.id)
        )
        favorites = favorites_q.scalars().all()

        if not favorites:
            await message.answer(
                "У вас пока нет сохранённых маршрутов.\n\n"
                "Чтобы добавить маршрут в избранное, найдите маршруты через кнопку "
                "<i>'Найти маршруты'</i> и нажмите на кнопку ❤️ под понравившимся маршрутом.",
                reply_markup=main_menu
            )
            return

        # Получаем информацию о каждом маршруте
        route_ids = [fav.route_id for fav in favorites]
        routes_q = await session.execute(
            select(Route).where(Route.id.in_(route_ids))
        )
        routes = routes_q.scalars().all()

        # Выводим маршруты
        await message.answer(f"📋 <b>Ваши сохранённые маршруты ({len(routes)})\n\n")

        for route in routes:
            # Получаем теги, сезоны и транспорт для маршрута
            tags_q = await session.execute(
                select(route_tags.c.tag).where(route_tags.c.route_id == route.id)
            )
            tags = [t[0] for t in tags_q.all()]

            seasons_q = await session.execute(
                select(route_seasons.c.season).where(route_seasons.c.route_id == route.id)
            )
            seasons = [s[0] for s in seasons_q.all()]

            transports_q = await session.execute(
                select(route_transports.c.transport).where(route_transports.c.route_id == route.id)
            )
            transports = [t[0] for t in transports_q.all()]

            # Форматируем сезоны для отображения
            season_names = {
                "winter": "❄️ Зима",
                "spring": "🌸 Весна",
                "summer": "☀️ Лето",
                "autumn": "🍁 Осень"
            }
            seasons_display = [season_names.get(s, s) for s in seasons]

            # Создаем кнопку для удаления
            remove_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="❌ Удалить из моих маршрутов",
                        callback_data=f"remove_fav_{route.id}"
                    )]
                ]
            )

            message_text = (
                f"🏔️<b>{route.title}</b>\n\n"
                f"<i>{route.description}</i>\n\n"
                f"📏 Длина: {route.length_km} км\n"
                f"⚡ Сложность: {route.difficulty}\n"
                f"💰 Цена: {route.price_estimate} руб\n"
                f"📈 Популярность: {route.popularity}/100\n"
                f"🏷️ Теги: {', '.join(tags)}\n"
                f"📅 Сезоны: {', '.join(seasons_display)}\n"
                f"🚗 Транспорт: {', '.join(transports)}"
            )

            if route.link:
                actual_link = route.link
                if isinstance(actual_link, list) and len(actual_link) > 0:
                    actual_link = actual_link[0]
                if isinstance(actual_link, str) and actual_link.strip():
                    if not actual_link.startswith(('http://', 'https://')):
                        actual_link = 'https://' + actual_link
                    message_text += f"\n🔗 <a href='{actual_link}'>Подробнее о маршруте</a>"

            await message.answer(message_text, parse_mode='HTML',
                                 disable_web_page_preview=False,
                                 reply_markup=remove_keyboard)

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

        prefs_text = "📋 <b>Ваши текущие пожелания</b> 📋\n\nПроверьте, что все <b>актуально</b>, если же нет, \nобновите предпочтения по кнопке внизу❕\n\n"

        if prefs.get("season"):
            if prefs['season'] == "winter":
                prefs_text += f"❄️ <b>Сезон:</b> зима\n"
            elif prefs['season'] == "spring":
                prefs_text += f"🌸 <b>Сезон:</b> весна\n"
            elif prefs['season'] == "summer":
                prefs_text += f"☀️ <b>Сезон:</b> лето\n"
            else:
                prefs_text += f"🍁 <b>Сезон:</b> осень\n"
        else:
            prefs_text += "⚠️ <b>Сезон:</b> не установлен\n"

        if prefs.get("length_km"):
            prefs_text += f"📏 <b>Длина маршрута:</b> {prefs['length_km']} км\n"
        else:
            prefs_text += "⚠️ <b>Длина маршрута:</b> не установлена\n"

        if prefs.get("price_estimate"):
            prefs_text += f"💸 <b>Цена:</b> {prefs['price_estimate']} руб\n"
        else:
            prefs_text += "⚠️ <b>Цена:</b> не установлена\n"

        if prefs.get("difficulty"):
            prefs_text += f"🟢 <b>Сложность:</b> {prefs['difficulty']}\n"
        else:
            prefs_text += "⚠️ <b>Сложность:</b> не установлена\n"

        if prefs.get("popularity"):
            prefs_text += f"📈 <b>Популярность:</b> {prefs['popularity']}/100\n"
        else:
            prefs_text += "⚠️ <b>Популярность:</b> не установлена\n"

        if prefs.get("transport"):
            prefs_text += f"🚞 <b>Транспорт:</b> {prefs['transport']}\n"
        else:
            prefs_text += "⚠️ <b>Транспорт:</b> не установлен\n"

        if prefs.get("tags"):
            tags_str = ", ".join(prefs['tags'])
            prefs_text += f"📌 <b>Теги:</b> {tags_str}\n"
        else:
            prefs_text += "⚠️ <b>Теги:</b> не установлены\n"

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

        from utils import get_preferences_keyboard
        await message.answer(prefs_text, reply_markup=get_preferences_keyboard())


@router.message(lambda m: m.text == "Установить предпочтения")
async def ask_season(message: types.Message):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, message.from_user.id))
        user = q.scalars().first()

        if user and user.preferences and user.preferences != "{}":
            await message.answer(
                "🖇️ У вас уже есть сохранённые предпочтения.\n"
                "Хотите сбросить их и начать заново или продолжить настройку с текущими❔",
                reply_markup=reset_choice_keyboard
            )
            return

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

        if message.text == "Найти маршруты":
            prefs = json.loads(user.preferences) if user.preferences else {}
            if not prefs:
                await message.answer("Сначала установите предпочтения через кнопку <i>'Установить предпочтения'</i>.")
                return

            q = await session.execute(select_user_by_tg(session, message.from_user.id))
            user = q.scalars().first()
            recs = await recommend_routes(session, prefs, limit=10)
            logs = []
            if not recs:
                await message.answer("Не найдено маршрутов.")
                return

            for r in recs:
                route = r["route"]
                score = r["score"]
                is_favorite = await is_route_favorite(session, user.id, route["id"])
                favorite_button_text = "❌ Удалить из моих маршрутов" if is_favorite else "❤️ Добавить в мои маршруты"
                favorite_button_data = f"remove_fav_{route['id']}" if is_favorite else f"add_fav_{route['id']}"

                favorite_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text=favorite_button_text,
                            callback_data=favorite_button_data
                        )]
                    ]
                )
                link = route.get('link')

                if link:
                    if isinstance(link, list) and len(link) > 0:
                        actual_link = link[0]
                        if not actual_link.startswith(('http://', 'https://')):
                            actual_link = 'https://' + actual_link
                        link_text = f"\n🔗 <a href='{actual_link}'>Подробнее о маршруте</a>"
                    elif isinstance(link, str) and link.strip():
                        actual_link = link.strip()
                        if not actual_link.startswith(('http://', 'https://')):
                            actual_link = 'https://' + actual_link
                        link_text = f"\n🔗 <a href='{actual_link}'>Подробнее о маршруте</a>"

                logs.append(f"📍 {route['title']} \n📎 <i>score {score}</i>\n")

                message_text = (
                    f"🏔️<b>{route['title']}</b> (score: {score})\n\n"
                    f"<i>{route.get('description')}</i>\n\n"
                    f"📏 Длина: {route.get('length_km')} км\n"
                    f"⚡ Сложность: {route.get('difficulty')}\n"
                    f"💰 Цена: {route.get('price_estimate')}\n"
                    f"🏷️ Теги: {', '.join(route.get('tags', []))}"
                    f"{link_text}"
                )

                await message.answer(message_text, parse_mode='HTML',
                                     disable_web_page_preview=False,
                                     reply_markup=favorite_keyboard)

            await message.answer("🗺️ <b>ТОП-10 МАРШРУТОВ</b> 🗺️\n\n" + "\n".join(logs), parse_mode='HTML')
            return

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

    await callback.message.answer(
        "Все выборы сохранены! 📂\nНажмите <i>'Найти маршруты'</i>, чтобы получить рекомендации \nили <i>'Посмотреть предпочтения'</i>, чтобы уточнить пожелания",
        reply_markup=main_menu)
    await callback.answer()


@router.callback_query(lambda c: c.data == "reset_and_start")
async def reset_and_start(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()
        if user:
            user.preferences = "{}"
            session.add(user)
            await session.commit()

    await callback.message.edit_text("Все предпочтения успешно сброшены ✅ \nВыберите сезон:",
                                     reply_markup=season_buttons)
    await callback.answer()


@router.callback_query(lambda c: c.data == "continue_current")
async def continue_current(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if user and user.preferences:
            prefs = json.loads(user.preferences)
            current_step = prefs.get("prefs_step")

            if not current_step:
                await callback.message.edit_text("Выберите сезон года:", reply_markup=season_buttons)
            else:
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
            await callback.answer(
                "У вас нет сохранённых предпочтений ⛓️‍💥. Нажмите пожалуйста <i>'Установить предпочтения'</i>.")
            return

        user.preferences = "{}"
        session.add(user)
        await session.commit()

        logger.info("User %s reset preferences", callback.from_user.id)

        await callback.message.edit_text(
            " ☑️ Все предпочтения успешно сброшены❕\n\nВы можете установить новые предпочтения через кнопку <i>'Установить предпочтения'</i>.",
            reply_markup=None)
        await callback.answer()


async def is_route_favorite(session, user_id: int, route_id: int) -> bool:
    q = await session.execute(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.route_id == route_id
        )
    )
    return q.scalars().first() is not None


@router.callback_query(lambda c: c.data and c.data.startswith("add_fav_"))
async def add_to_favorites(callback: types.CallbackQuery):
    route_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        # Проверяем, не добавлен ли уже маршрут
        existing_q = await session.execute(
            select(Favorite).where(
                Favorite.user_id == user.id,
                Favorite.route_id == route_id
            )
        )
        existing = existing_q.scalars().first()

        if existing:
            await callback.answer("Маршрут уже в избранном")
            return

        # Добавляем в избранное
        favorite = Favorite(user_id=user.id, route_id=route_id)
        session.add(favorite)
        await session.commit()

        await callback.answer("✅ Маршрут добавлен в избранное")

        # Обновляем кнопку
        favorite_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="❌ Удалить из моих маршрутов",
                    callback_data=f"remove_fav_{route_id}"
                )]
            ]
        )

        await callback.message.edit_reply_markup(reply_markup=favorite_keyboard)


# Обработчик для удаления маршрута из избранного
@router.callback_query(lambda c: c.data and c.data.startswith("remove_fav_"))
async def remove_from_favorites(callback: types.CallbackQuery):
    route_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        # Удаляем из избранного
        await session.execute(
            delete(Favorite).where(
                Favorite.user_id == user.id,
                Favorite.route_id == route_id
            )
        )
        await session.commit()

        await callback.answer("❌ Маршрут удален из избранного")

        # Обновляем кнопку
        favorite_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="❤️ Добавить в мои маршруты",
                    callback_data=f"add_fav_{route_id}"
                )]
            ]
        )

        await callback.message.edit_reply_markup(reply_markup=favorite_keyboard)


