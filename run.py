import os
import json
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, Float, Table, ForeignKey, select, func

# --------------------------- Configuration ---------------------------
BOT_TOKEN = ("Здесь_был_токен")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./tuva_travel.db")
ADMIN_IDS = [s.strip() for s in os.getenv("ADMIN_IDS", "").split(',') if s.strip()]

# --------------------------- Database setup ---------------------------
Base = declarative_base()

route_tags = Table("route_tags", Base.metadata, Column("route_id", Integer, ForeignKey("routes.id"), primary_key=True), Column("tag", String, primary_key=True))
route_seasons = Table("route_seasons", Base.metadata, Column("route_id", Integer, ForeignKey("routes.id"), primary_key=True), Column("season", String, primary_key=True))
route_transports = Table("route_transports", Base.metadata, Column("route_id", Integer, ForeignKey("routes.id"), primary_key=True), Column("transport", String, primary_key=True))

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    preferences = Column(Text, nullable=True)  # JSON

class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    length_km = Column(Float, nullable=True)
    difficulty = Column(String, nullable=True)
    price_estimate = Column(Float, nullable=True)
    popularity = Column(Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "title": self.title, "description": self.description, "length_km": self.length_km, "difficulty": self.difficulty, "price_estimate": self.price_estimate, "popularity": self.popularity}

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# --------------------------- Bot setup ---------------------------
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
router = Router()
dp = Dispatcher()
dp.include_router(router)

# --------------------------- Utilities ---------------------------
async def init_db_and_seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        q = await session.execute(select(func.count(Route.id)))
        count = q.scalar_one()
        if count == 0:
            sample_routes = [
                {"title": "Кызыл — озеро Дьенгек", "description": "Лёгкий однодневный маршрут", "length_km": 40.0, "difficulty": "easy", "price_estimate": 10.0, "popularity": 50, "tags": ["nature","family","hiking"], "seasons": ["summer","autumn"], "transports": ["car","minibus"]},
                {"title": "Чадан — курган Чыратас", "description": "Двухдневный маршрут с треккингом", "length_km": 120.0, "difficulty": "moderate", "price_estimate": 50.0, "popularity": 30, "tags": ["adventure","trekking","nature"], "seasons": ["summer"], "transports": ["car"]},
                {"title": "Шашлык тур с гидом", "description": "Короткая экскурсия с дегустацией", "length_km": 10.0, "difficulty": "easy", "price_estimate": 25.0, "popularity": 80, "tags": ["culture","food","family"], "seasons": ["spring","summer","autumn"], "transports": ["car","minibus"]},
            ]
            for r in sample_routes:
                route = Route(title=r["title"], description=r["description"], length_km=r["length_km"], difficulty=r["difficulty"], price_estimate=r["price_estimate"], popularity=r["popularity"])
                session.add(route)
                await session.flush()
                for tag in r["tags"]: await session.execute(route_tags.insert().values(route_id=route.id, tag=tag))
                for s in r["seasons"]: await session.execute(route_seasons.insert().values(route_id=route.id, season=s))
                for t in r["transports"]: await session.execute(route_transports.insert().values(route_id=route.id, transport=t))
            await session.commit()

async def get_user(session: AsyncSession, tg_id: int) -> Optional[User]:
    q = await session.execute(select(User).where(User.tg_id == tg_id))
    return q.scalars().first()

async def upsert_user(session: AsyncSession, tg_id: int, name: Optional[str] = None) -> User:
    user = await get_user(session, tg_id)
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

# --------------------------- Recommendation engine ---------------------------
SEASONS_BY_MONTH = {1:"winter",2:"winter",3:"spring",4:"spring",5:"spring",6:"summer",7:"summer",8:"summer",9:"autumn",10:"autumn",11:"autumn",12:"winter"}

def score_route(route_row: Dict[str, Any], prefs: Dict[str, Any], current_season: str) -> float:
    score = 0.0
    pref_tags = set(prefs.get("tags", []))
    route_tags_set = set(route_row.get("tags", []))
    score += len(pref_tags & route_tags_set) * 2.0
    if current_season in set(route_row.get("seasons", [])): score += 3.0
    if prefs.get("season") in set(route_row.get("seasons", [])): score +=1.0
    score += len(set(prefs.get("transport", [])) & set(route_row.get("transports", []))) * 1.5
    budget = prefs.get("budget")
    price = route_row.get("price_estimate") or 0
    thresholds = {"low":20,"medium":60,"high":1000}
    limit = thresholds.get(budget,60)
    if budget: score += 1.5 if price <= limit else -min((price - limit)/(limit+1),2.0)
    score += min(route_row.get("popularity",0)/100.0,1.0)
    if "family" in pref_tags and route_row.get("length_km",0)<=50: score+=1.0
    if "adventure" in pref_tags and route_row.get("difficulty")=="hard": score+=1.5
    return score

async def fetch_routes_with_meta(session: AsyncSession) -> List[Dict[str, Any]]:
    q = await session.execute(select(Route))
    routes = q.scalars().all()
    result = []
    for r in routes:
        tags_q = await session.execute(select(route_tags.c.tag).where(route_tags.c.route_id==r.id))
        seasons_q = await session.execute(select(route_seasons.c.season).where(route_seasons.c.route_id==r.id))
        transports_q = await session.execute(select(route_transports.c.transport).where(route_transports.c.route_id==r.id))
        d = r.to_dict()
        d.update({"tags":[t[0] for t in tags_q.all()],"seasons":[s[0] for s in seasons_q.all()],"transports":[t[0] for t in transports_q.all()]})
        result.append(d)
    return result

async def recommend_routes(session: AsyncSession, prefs: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    current_season = SEASONS_BY_MONTH[datetime.utcnow().month]
    routes = await fetch_routes_with_meta(session)
    scored = sorted([(score_route(r,prefs,current_season), r) for r in routes], key=lambda x:x[0], reverse=True)
    return [{"score":round(s,3),"route":r} for s,r in scored[:limit]]

# --------------------------- Keyboards ---------------------------
main_menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Установить предпочтения")],[KeyboardButton(text="Посмотреть предпочтения")],[KeyboardButton(text="Найти маршруты")]],resize_keyboard=True)

season_buttons = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Зима", callback_data="season_winter"),InlineKeyboardButton(text="Весна", callback_data="season_spring")],[InlineKeyboardButton(text="Лето", callback_data="season_summer"),InlineKeyboardButton(text="Осень", callback_data="season_autumn")]])

# --------------------------- Handlers ---------------------------
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await upsert_user(AsyncSessionLocal(), message.from_user.id, message.from_user.full_name)
    await message.answer("Привет! Выберите действие:", reply_markup=main_menu)

@router.message()
async def handle_button(message: types.Message):
    text = message.text
    async with AsyncSessionLocal() as session:
        user = await upsert_user(session, message.from_user.id, message.from_user.full_name)
        prefs = json.loads(user.preferences) if user.preferences else {}
        if text == "Установить предпочтения":
            await message.answer("Выберите сезон:", reply_markup=season_buttons)
        elif text == "Посмотреть предпочтения":
            await message.answer(f"Ваши предпочтения:\n<code>{json.dumps(prefs,ensure_ascii=False)}</code>")
        elif text == "Найти маршруты":
            if not prefs:
                await message.answer("Сначала установите предпочтения через кнопку 'Установить предпочтения'.")
                return
            recs = await recommend_routes(session, prefs, limit=5)
            for r in recs:
                route = r['route']
                score = r['score']
                await message.answer(f"<b>{route['title']}</b> (score: {score})\n{route['description']}\nДлина: {route.get('length_km')} км, Сложность: {route.get('difficulty')}, Цена ≈ {route.get('price_estimate')}")

@router.callback_query(lambda c: c.data and c.data.startswith("season_"))
async def choose_season(callback: types.CallbackQuery):
    season = callback.data.split("_")[1]
    async with AsyncSessionLocal() as session:
        user = await upsert_user(session, callback.from_user.id)
        prefs = json.loads(user.preferences) if user.preferences else {}
        prefs['season'] = season
        user.preferences = json.dumps(prefs, ensure_ascii=False)
        session.add(user)
        await session.commit()
    await callback.message.answer(f"Сезон установлен: {season}")
    await callback.answer()

# --------------------------- Startup / Shutdown ---------------------------
@dp.startup.register
async def on_startup():
    print("Bot starting...")
    await init_db_and_seed()

@dp.shutdown.register
async def on_shutdown():
    print("Shutting down...")
    await bot.session.close()

# --------------------------- Run ---------------------------
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")