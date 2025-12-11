# utils.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Установить предпочтения")],
        [KeyboardButton(text="Посмотреть предпочтения")],
        [KeyboardButton(text="Найти маршруты")],
    ],
    resize_keyboard=True,
)

season_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Зима", callback_data="season_winter"),
            InlineKeyboardButton(text="Весна", callback_data="season_spring"),
        ],
        [
            InlineKeyboardButton(text="Лето", callback_data="season_summer"),
            InlineKeyboardButton(text="Осень", callback_data="season_autumn"),
        ],
    ]
)

difficulty_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="easy", callback_data="diff_easy"),
            InlineKeyboardButton(text="moderate", callback_data="diff_moderate"),
            InlineKeyboardButton(text="hard", callback_data="diff_hard"),
        ]
    ]
)

transport_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="car", callback_data="trans_car"),
            InlineKeyboardButton(text="4x4", callback_data="trans_4x4"),
            InlineKeyboardButton(text="minibus", callback_data="trans_minibus"),
        ],
        [
            InlineKeyboardButton(text="boat", callback_data="trans_boat"),
            InlineKeyboardButton(text="on_foot", callback_data="trans_on_foot"),
        ],
    ]
)

tags_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="nature", callback_data="tag_nature"),
            InlineKeyboardButton(text="adventure", callback_data="tag_adventure"),
            InlineKeyboardButton(text="family", callback_data="tag_family"),
        ],
        [
            InlineKeyboardButton(text="trekking", callback_data="tag_trekking"),
            InlineKeyboardButton(text="culture", callback_data="tag_culture"),
            InlineKeyboardButton(text="city", callback_data="tag_city"),
        ],
        [
            InlineKeyboardButton(text="history", callback_data="tag_history"),
            InlineKeyboardButton(text="food", callback_data="tag_food"),
            InlineKeyboardButton(text="hiking", callback_data="tag_hiking"),
        ],
        [
            InlineKeyboardButton(text="Готово", callback_data="tags_done"),
        ],
    ]
)
