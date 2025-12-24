import json
import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, delete, and_
from models import Favorite, route_transports, route_seasons, route_tags, Route, User, CompletedRoute
from datetime import datetime
from db import AsyncSessionLocal
from recommender import recommend_routes
from utils import (
    main_menu,
    season_buttons,
    difficulty_buttons,
    transport_buttons,
    tags_buttons,
    reset_choice_keyboard,
    get_preferences_keyboard,
    inline_main_menu,
    back_to_main_menu,
    stats_with_details
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


def select_user_by_tg(session, tg_id):
    return select(User).where(User.tg_id == tg_id)


async def is_route_favorite(session, user_id: int, route_id: int) -> bool:
    q = await session.execute(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.route_id == route_id
        )
    )
    return q.scalars().first() is not None


async def is_route_completed(session, user_id: int, route_id: int) -> bool:
    q = await session.execute(
        select(CompletedRoute).where(
            CompletedRoute.user_id == user_id,
            CompletedRoute.route_id == route_id
        )
    )
    return q.scalars().first() is not None


async def send_main_menu(chat_id: int, message_text: str = None):
    """Функция для отправки главного меню"""
    if message_text:
        await bot.send_message(chat_id, message_text, reply_markup=inline_main_menu)
    else:
        await bot.send_message(chat_id,
                               "🏔️ <b>Добро пожаловать в Тувинский путеводитель!</b>\n\n"
                               "Выберите действие из меню ниже:",
                               reply_markup=inline_main_menu)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async with AsyncSessionLocal() as session:
        await upsert_user(session, message.from_user.id, message.from_user.full_name)

    await send_main_menu(message.chat.id,
                         "Привет❕ \nМы рады помочь вам увидеть всю красоту <b> Республики Тывы </b>❕🏔️🤍 \n\n"
                         "Выберите действие из меню ниже:")


@router.callback_query(lambda c: c.data == "main_menu")
async def handle_main_menu(callback: types.CallbackQuery):
    """Обработчик кнопки Главное меню"""
    await callback.message.edit_text(
        "🏔️ <b>Добро пожаловать в Тувинский путеводитель!</b>\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=inline_main_menu
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "set_prefs")
async def handle_set_prefs(callback: types.CallbackQuery):
    """Обработчик кнопки Установить предпочтения"""
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if user and user.preferences and user.preferences != "{}":
            await callback.message.edit_text(
                "🖇️ У вас уже есть сохранённые предпочтения.\n"
                "Хотите сбросить их и начать заново или продолжить настройку с текущими❔",
                reply_markup=reset_choice_keyboard
            )
        else:
            await callback.message.edit_text(
                "Выберите сезон года:",
                reply_markup=season_buttons
            )
    await callback.answer()


@router.callback_query(lambda c: c.data == "view_prefs")
async def handle_view_prefs(callback: types.CallbackQuery):
    """Обработчик кнопки Посмотреть предпочтения"""
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.message.edit_text(
                "У вас ещё нет предпочтений и мы не можем подобрать маршруты.\n"
                "Сначала установите их через кнопку <i>'Установить предпочтения'</i>.",
                reply_markup=inline_main_menu
            )
            await callback.answer()
            return

        prefs = json.loads(user.preferences) if user.preferences else {}

        if not prefs:
            await callback.message.edit_text(
                "У вас ещё нет предпочтений и мы не можем подобрать маршруты.\n"
                "Сначала установите их через кнопку <i>'Установить предпочтения'</i>.",
                reply_markup=inline_main_menu
            )
            await callback.answer()
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

        await callback.message.edit_text(prefs_text, reply_markup=get_preferences_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "my_routes")
async def handle_my_routes(callback: types.CallbackQuery):
    """Обработчик кнопки Мои маршруты"""
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.message.edit_text("Пользователь не найден.", reply_markup=inline_main_menu)
            await callback.answer()
            return

        favorites_q = await session.execute(
            select(Favorite).where(Favorite.user_id == user.id)
        )
        favorites = favorites_q.scalars().all()

        if not favorites:
            await callback.message.edit_text(
                "У вас пока нет сохранённых маршрутов.\n\n"
                "Чтобы добавить маршрут в избранное, найдите маршруты через кнопку "
                "<i>'Найти маршруты'</i> и нажмите на кнопку ❤️ под понравившимся маршрутом.",
                reply_markup=inline_main_menu
            )
            await callback.answer()
            return

        route_ids = [fav.route_id for fav in favorites]
        routes_q = await session.execute(
            select(Route).where(Route.id.in_(route_ids))
        )
        routes = routes_q.scalars().all()

        await callback.message.edit_text(f"📋 <b>Ваши сохранённые маршруты ({len(routes)})</b>\n\n"
                                         "Ниже вы найдете подробную информацию о каждом маршруте:",
                                         reply_markup=back_to_main_menu)
        await callback.answer()

        for route in routes:
            is_completed = await is_route_completed(session, user.id, route.id)

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

            season_names = {
                "winter": "❄️ Зима",
                "spring": "🌸 Весна",
                "summer": "☀️ Лето",
                "autumn": "🍁 Осень"
            }
            seasons_display = [season_names.get(s, s) for s in seasons]

            buttons = []
            buttons.append([InlineKeyboardButton(
                text="❌ Удалить из моих маршрутов",
                callback_data=f"remove_fav_{route.id}"
            )])

            completed_button_text = "✅ Пройден" if is_completed else "🏁 Отметить как пройденный"
            completed_button_data = f"uncomplete_{route.id}" if is_completed else f"complete_{route.id}"
            buttons.append([InlineKeyboardButton(
                text=completed_button_text,
                callback_data=completed_button_data
            )])

            route_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

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

            await bot.send_message(callback.message.chat.id, message_text, parse_mode='HTML',
                                   disable_web_page_preview=False,
                                   reply_markup=route_keyboard)

        await bot.send_message(
            callback.message.chat.id,
            "✅ Все ваши сохранённые маршруты показаны.\n\n"
            "Нажмите на кнопку для перехода в главное меню:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )


@router.callback_query(lambda c: c.data == "show_stats")
async def handle_show_stats(callback: types.CallbackQuery):
    """Обработчик кнопки Статистика"""
    await show_statistics(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(lambda c: c.data == "find_routes")
async def handle_find_routes(callback: types.CallbackQuery):
    """Обработчик кнопки Найти маршруты"""
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.message.edit_text("Пользователь не найден.", reply_markup=inline_main_menu)
            await callback.answer()
            return

        prefs = json.loads(user.preferences) if user.preferences else {}

        if not prefs:
            await callback.message.edit_text(
                "Сначала установите предпочтения через кнопку <i>'Установить предпочтения'</i>.",
                reply_markup=inline_main_menu
            )
            await callback.answer()
            return

        recs = await recommend_routes(session, prefs, limit=10)

        if not recs:
            await callback.message.edit_text("Не найдено маршрутов.", reply_markup=inline_main_menu)
            await callback.answer()
            return

        await callback.message.edit_text("🔍 <b>Ищу маршруты по вашим предпочтениям...</b>",
                                         reply_markup=back_to_main_menu)
        await callback.answer()

        logs = []
        for r in recs:
            route = r["route"]
            score = r["score"]

            is_favorite = await is_route_favorite(session, user.id, route["id"])
            is_completed = await is_route_completed(session, user.id, route["id"])

            buttons = []

            favorite_button_text = "❌ Удалить из моих маршрутов" if is_favorite else "❤️ Добавить в мои маршруты"
            favorite_button_data = f"remove_fav_{route['id']}" if is_favorite else f"add_fav_{route['id']}"
            buttons.append([InlineKeyboardButton(
                text=favorite_button_text,
                callback_data=favorite_button_data
            )])

            completed_button_text = "✅ Пройден" if is_completed else "🏁 Отметить как пройденный"
            completed_button_data = f"uncomplete_{route['id']}" if is_completed else f"complete_{route['id']}"
            buttons.append([InlineKeyboardButton(
                text=completed_button_text,
                callback_data=completed_button_data
            )])

            route_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            link = route.get('link')
            link_text = ""

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

            await bot.send_message(callback.message.chat.id, message_text, parse_mode='HTML',
                                   disable_web_page_preview=False,
                                   reply_markup=route_keyboard)

        await bot.send_message(
            callback.message.chat.id,
            "🗺️ <b>ТОП-10 МАРШРУТОВ</b> 🗺️\n\n" + "\n".join(logs),
            parse_mode='HTML',
            reply_markup=back_to_main_menu
        )


@router.callback_query(lambda c: c.data == "help")
async def handle_help(callback: types.CallbackQuery):
    """Обработчик кнопки Помощь"""
    help_text = (
        "ℹ️ <b>Помощь по использованию бота</b>\n\n"
        "🎯 <b>Установить предпочтения</b> - настройте параметры для поиска маршрутов\n"
        "👁 <b>Посмотреть предпочтения</b> - просмотр текущих настроек\n"
        "🔍 <b>Найти маршруты</b> - поиск маршрутов по вашим предпочтениям\n"
        "❤️ <b>Мои маршруты</b> - просмотр сохраненных маршрутов\n"
        "📊 <b>Статистика</b> - ваша статистика по пройденным маршрутам\n\n"
        "📌 <b>Как работать с маршрутами:</b>\n"
        "1. Нажмите ❤️ чтобы добавить маршрут в избранное\n"
        "2. Нажмите 🏁 чтобы отметить маршрут как пройденный\n"
        "3. Используйте кнопки под каждым маршрутом для управления\n\n"
        "❔ Если у вас есть какие-то вопросы, не относящиеся к работе бота, напишите разработчицам:\n"
        "<i>@by_gelya - Ангелина,</i>\n"
        "<i>@numieux - Анастасия</i>\n\n"
        "Для возврата в главное меню используйте кнопку <b>🏠 Главное меню</b>"
    )

    await callback.message.edit_text(help_text, reply_markup=back_to_main_menu)
    await callback.answer()


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

    await callback.message.edit_text("Хороший выбор❕\nВведите желаемую длину маршрута (км):\n\n"
                                     "<i>Просто отправьте число в чат</i>",
                                     reply_markup=back_to_main_menu)
    await callback.answer()


@router.message()
async def collect_prefs(message: types.Message):
    """Обработчик текстовых сообщений для сбора предпочтений"""
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
                await message.answer("Введите желаемую цену (руб):\n\n"
                                     "<i>Просто отправьте число в чат</i>",
                                     reply_markup=back_to_main_menu)
            except Exception:
                await message.answer("Пожалуйста, введите число для длины (например: 12 или 45.5).",
                                     reply_markup=back_to_main_menu)
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
                await message.answer("Пожалуйста, введите число для цены (например: 2000).",
                                     reply_markup=back_to_main_menu)
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
                await message.answer("Введите число от 0 до 100.",
                                     reply_markup=back_to_main_menu)
            return

        await send_main_menu(message.chat.id,
                             "Выберите действие из меню ниже:")


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

    await callback.message.edit_text("Введите желаемую популярность (0–100):\n\n"
                                     "<i>Просто отправьте число в чат</i>",
                                     reply_markup=back_to_main_menu)
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

    await callback.message.edit_text("Выберите предпочитаемые теги (можно несколько):",
                                     reply_markup=tags_buttons)
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

    await callback.message.edit_text(
        "Все выборы сохранены! 📂\n\n"
        "Теперь вы можете найти маршруты по вашим предпочтениям.",
        reply_markup=inline_main_menu)
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
                    await callback.message.edit_text(message_text + "\n\n<i>Просто отправьте число в чат</i>",
                                                     reply_markup=back_to_main_menu)
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
            reply_markup=inline_main_menu)
        await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("add_fav_"))
async def add_to_favorites(callback: types.CallbackQuery):
    route_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.answer("Пользователь не найден")
            return

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

        favorite = Favorite(user_id=user.id, route_id=route_id)
        session.add(favorite)
        await session.commit()

        await callback.answer("✅ Маршрут добавлен в избранное")

        is_completed = await is_route_completed(session, user.id, route_id)
        buttons = []

        buttons.append([InlineKeyboardButton(
            text="❌ Удалить из моих маршрутов",
            callback_data=f"remove_fav_{route_id}"
        )])

        completed_button_text = "✅ Пройден" if is_completed else "🏁 Отметить как пройденный"
        completed_button_data = f"uncomplete_{route_id}" if is_completed else f"complete_{route_id}"
        buttons.append([InlineKeyboardButton(
            text=completed_button_text,
            callback_data=completed_button_data
        )])

        route_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_reply_markup(reply_markup=route_keyboard)


@router.callback_query(lambda c: c.data and c.data.startswith("remove_fav_"))
async def remove_from_favorites(callback: types.CallbackQuery):
    route_id = int(callback.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        await session.execute(
            delete(Favorite).where(
                Favorite.user_id == user.id,
                Favorite.route_id == route_id
            )
        )
        await session.commit()

        await callback.answer("❌ Маршрут удален из избранного")

        is_completed = await is_route_completed(session, user.id, route_id)
        buttons = []

        buttons.append([InlineKeyboardButton(
            text="❤️ Добавить в мои маршруты",
            callback_data=f"add_fav_{route_id}"
        )])

        completed_button_text = "✅ Пройден" if is_completed else "🏁 Отметить как пройденный"
        completed_button_data = f"uncomplete_{route_id}" if is_completed else f"complete_{route_id}"
        buttons.append([InlineKeyboardButton(
            text=completed_button_text,
            callback_data=completed_button_data
        )])

        route_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_reply_markup(reply_markup=route_keyboard)


@router.callback_query(lambda c: c.data and c.data.startswith("complete_"))
async def mark_as_completed(callback: types.CallbackQuery):
    route_id = int(callback.data.split("_")[1])

    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        existing_q = await session.execute(
            select(CompletedRoute).where(
                CompletedRoute.user_id == user.id,
                CompletedRoute.route_id == route_id
            )
        )
        existing = existing_q.scalars().first()

        if existing:
            await callback.answer("Маршрут уже отмечен как пройденный")
            return

        completed = CompletedRoute(user_id=user.id, route_id=route_id)
        session.add(completed)
        await session.commit()

        await callback.answer("✅ Маршрут отмечен как пройденный")

        is_favorite = await is_route_favorite(session, user.id, route_id)
        buttons = []

        favorite_button_text = "❌ Удалить из моих маршрутов" if is_favorite else "❤️ Добавить в мои маршруты"
        favorite_button_data = f"remove_fav_{route_id}" if is_favorite else f"add_fav_{route_id}"
        buttons.append([InlineKeyboardButton(
            text=favorite_button_text,
            callback_data=favorite_button_data
        )])

        buttons.append([InlineKeyboardButton(
            text="✅ Пройден",
            callback_data=f"uncomplete_{route_id}"
        )])

        route_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_reply_markup(reply_markup=route_keyboard)


@router.callback_query(lambda c: c.data and c.data.startswith("uncomplete_"))
async def unmark_as_completed(callback: types.CallbackQuery):
    route_id = int(callback.data.split("_")[1])

    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        await session.execute(
            delete(CompletedRoute).where(
                CompletedRoute.user_id == user.id,
                CompletedRoute.route_id == route_id
            )
        )
        await session.commit()

        await callback.answer("❌ Отметка о прохождении снята")

        is_favorite = await is_route_favorite(session, user.id, route_id)
        buttons = []

        favorite_button_text = "❌ Удалить из моих маршрутов" if is_favorite else "❤️ Добавить в мои маршруты"
        favorite_button_data = f"remove_fav_{route_id}" if is_favorite else f"add_fav_{route_id}"
        buttons.append([InlineKeyboardButton(
            text=favorite_button_text,
            callback_data=favorite_button_data
        )])

        buttons.append([InlineKeyboardButton(
            text="🏁 Отметить как пройденный",
            callback_data=f"complete_{route_id}"
        )])

        route_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_reply_markup(reply_markup=route_keyboard)


@router.callback_query(lambda c: c.data == "stats_details_all")
async def show_all_completed_details(callback: types.CallbackQuery):
    """Показать подробную информацию обо всех пройденных маршрутах"""
    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, callback.from_user.id))
        user = q.scalars().first()

        if not user:
            await callback.answer("Пользователь не найден")
            return

        completed_q = await session.execute(
            select(CompletedRoute).where(CompletedRoute.user_id == user.id)
        )
        completed = completed_q.scalars().all()

        if not completed:
            await callback.answer("У вас нет пройденных маршрутов")
            return

        completed_ids = [comp.route_id for comp in completed]
        routes_q = await session.execute(
            select(Route).where(Route.id.in_(completed_ids))
        )
        routes = routes_q.scalars().all()

        await callback.message.edit_text(
            f"📖 <b>Подробная информация о пройденных маршрутах ({len(routes)})</b>\n\n"
            "Ниже вы найдете детальную информацию о каждом маршруте:",
            reply_markup=back_to_main_menu
        )
        await callback.answer()

        for route in routes:
            completion_date_q = await session.execute(
                select(CompletedRoute.completed_at).where(
                    CompletedRoute.user_id == user.id,
                    CompletedRoute.route_id == route.id
                )
            )
            completion_date = completion_date_q.scalar()
            date_str = completion_date.strftime("%d %B %Y") if completion_date else "Неизвестно"

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

            season_names = {
                "winter": "❄️ Зима",
                "spring": "🌸 Весна",
                "summer": "☀️ Лето",
                "autumn": "🍁 Осень"
            }
            seasons_display = [season_names.get(s, s) for s in seasons]

            details_text = (
                f"📋 <b>Подробная информация о маршруте</b>\n\n"
                f"🏔️ <b>Название:</b> {route.title}\n\n"
                f"<i>{route.description}</i>\n\n"
                f"📅 <b>Дата прохождения:</b> {date_str}\n"
                f"📏 <b>Длина:</b> {route.length_km} км\n"
                f"⚡ <b>Сложность:</b> {route.difficulty}\n"
                f"💰 <b>Цена:</b> {route.price_estimate} руб\n"
                f"📈 <b>Популярность:</b> {route.popularity}/100\n\n"
                f"🏷️ <b>Теги:</b> {', '.join(tags)}\n"
                f"📅 <b>Сезоны:</b> {', '.join(seasons_display)}\n"
                f"🚗 <b>Транспорт:</b> {', '.join(transports)}\n"
            )

            if route.link:
                actual_link = route.link
                if isinstance(actual_link, list) and len(actual_link) > 0:
                    actual_link = actual_link[0]
                if isinstance(actual_link, str) and actual_link.strip():
                    if not actual_link.startswith(('http://', 'https://')):
                        actual_link = 'https://' + actual_link
                    details_text += f"\n🔗 <b>Ссылка:</b> <a href='{actual_link}'>{actual_link}</a>"

            await bot.send_message(callback.message.chat.id, details_text, parse_mode='HTML',
                                   disable_web_page_preview=False,
                                   reply_markup=back_to_main_menu)


async def show_statistics(message: types.Message, user_id: int = None):
    """Функция для показа статистики"""
    if user_id is None:
        user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        q = await session.execute(select_user_by_tg(session, user_id))
        user = q.scalars().first()

        if not user:
            if isinstance(message, types.Message):
                await message.answer("Пользователь не найден.", reply_markup=inline_main_menu)
            else:
                await message.edit_text("Пользователь не найден.", reply_markup=inline_main_menu)
            return

        completed_q = await session.execute(
            select(CompletedRoute).where(CompletedRoute.user_id == user.id)
        )
        completed = completed_q.scalars().all()

        favorites_q = await session.execute(
            select(Favorite).where(Favorite.user_id == user.id)
        )
        favorites = favorites_q.scalars().all()

        total_routes_q = await session.execute(select(Route.id))
        total_routes = len(total_routes_q.scalars().all())

        if not completed:
            stats_text = (
                "📊 <b>Ваша статистика</b>\n\n"
                "У вас пока нет пройденных маршрутов.\n\n"
                f"<b>Всего маршрутов в базе:</b> {total_routes}\n"
                f"<b>В избранном:</b> {len(favorites)}\n"
                f"<b>Пройдено:</b> 0 (0%)\n\n"
                "Чтобы отметить маршрут как пройденный, найдите маршруты через кнопку "
                "<i>'Найти маршруты'</i> и нажмите кнопку 🏁 под понравившимся маршрутом."
            )

            if isinstance(message, types.Message):
                await message.answer(stats_text, parse_mode='HTML', reply_markup=inline_main_menu)
            else:
                await message.edit_text(stats_text, parse_mode='HTML', reply_markup=inline_main_menu)
            return

        completed_ids = [comp.route_id for comp in completed]
        routes_q = await session.execute(
            select(Route).where(Route.id.in_(completed_ids))
        )
        routes = routes_q.scalars().all()

        total_length = sum(route.length_km or 0 for route in routes)
        total_cost = sum(route.price_estimate or 0 for route in routes)
        percentage = round((len(completed) / total_routes) * 100, 1) if total_routes > 0 else 0

        routes_list = [route.title for route in routes]

        stats_text = (
            f"📊 <b>Ваша статистика</b>\n\n"
            f"<b>Всего маршрутов в базе:</b> {total_routes}\n"
            f"<b>В избранном:</b> {len(favorites)}\n"
            f"<b>Пройдено:</b> {len(completed)} ({percentage}%)\n\n"
            f"<b>Общая пройденная дистанция:</b> {total_length:.1f} км\n"
            f"<b>Общая стоимость:</b> {total_cost:.0f} руб\n\n"
            f"<b>Пройденные маршруты ({len(routes)}):</b>\n"
        )

        for i, title in enumerate(routes_list, 1):
            stats_text += f"{i}. {title}\n"

        if isinstance(message, types.Message):
            await message.answer(stats_text, parse_mode='HTML', reply_markup=stats_with_details)
        else:
            await message.edit_text(stats_text, parse_mode='HTML', reply_markup=stats_with_details)