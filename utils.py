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
            InlineKeyboardButton(text="❄️ Зима", callback_data="season_winter"),
            InlineKeyboardButton(text="🌸 Весна", callback_data="season_spring"),
        ],
        [
            InlineKeyboardButton(text="☀️ Лето", callback_data="season_summer"),
            InlineKeyboardButton(text="🍁 Осень", callback_data="season_autumn"),
        ],
    ]
)

difficulty_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Легко", callback_data="diff_легко"),
            InlineKeyboardButton(text="🔴 Сложно", callback_data="diff_сложно"),
        ],
        [
            InlineKeyboardButton(text="🟡 Варьируется", callback_data="diff_варьируется"),
        ]
    ]
)

transport_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🚗 Машина", callback_data="trans_машина"),
            InlineKeyboardButton(text="🚗🚙 4x4", callback_data="trans_4x4"),
        ],
        [
            InlineKeyboardButton(text="🚐 Маршрутка", callback_data="trans_маршрутка"),
        ],
        [
            InlineKeyboardButton(text="🚤 Лодка", callback_data="trans_лодка"),
            InlineKeyboardButton(text="🚶🏻‍♀ Пешком", callback_data="trans_пешком"),
        ],
    ]
)

tags_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🌿 Природа", callback_data="tag_природа"),
            InlineKeyboardButton(text="🚀 Приключение", callback_data="tag_приключение"),
            InlineKeyboardButton(text="🎠 Семейное", callback_data="tag_семейное"),
        ],
        [
            InlineKeyboardButton(text="🏕 Походы", callback_data="tag_походы"),
            InlineKeyboardButton(text="🕌 Культура", callback_data="tag_культура"),
            InlineKeyboardButton(text="🗽 Город", callback_data="tag_город"),
        ],
        [
            InlineKeyboardButton(text="🏰 История", callback_data="tag_история"),
            InlineKeyboardButton(text="🍲 Еда", callback_data="tag_еда"),
            InlineKeyboardButton(text="🥾 Прогулки", callback_data="tag_прогулки"),
        ],
        [
            InlineKeyboardButton(text="✅ Готово", callback_data="tags_done"),
        ],
    ]
)

def get_preferences_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Сбросить все предпочтения", callback_data="reset_prefs")
            ]
        ]
    )

reset_choice_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Сбросить и начать заново", callback_data="reset_and_start"),
        ],
        [
            InlineKeyboardButton(text="✅ Продолжить с текущими", callback_data="continue_current"),        ]
    ]
)