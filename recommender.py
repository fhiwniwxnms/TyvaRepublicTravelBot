# recommender.py
import logging
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import select

from db import AsyncSessionLocal
from models import Route, route_tags, route_seasons, route_transports

logger = logging.getLogger(__name__)

SEASONS_BY_MONTH = {
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
    12: "winter",
}


def score_route(route_row: Dict[str, Any], prefs: Dict[str, Any], current_season: str) -> float:
    score = 0.0
    debug = []

    # SEASON
    if current_season in route_row.get("seasons", []):
        score += 3
        debug.append("season_match_current(+3)")
    if prefs.get("season") in route_row.get("seasons", []):
        score += 1
        debug.append("season_match_pref(+1)")

    # LENGTH
    try:
        pref_len = float(prefs.get("length_km", 0))
        length = float(route_row.get("length_km") or 0)
        add = max(0, 3 - abs(length - pref_len) / 20)
        score += add
        debug.append(f"length_diff({length}-{pref_len})(+{add:.2f})")
    except Exception:
        debug.append("length_skip")

    # PRICE
    try:
        pref_price = float(prefs.get("price_estimate", 0))
        price = float(route_row.get("price_estimate") or 0)
        add = max(0, 3 - abs(price - pref_price) / 3000)
        score += add
        debug.append(f"price_diff({price}-{pref_price})(+{add:.2f})")
    except Exception:
        debug.append("price_skip")

    # DIFFICULTY
    if prefs.get("difficulty"):
        if prefs["difficulty"] == route_row.get("difficulty"):
            score += 2
            debug.append("difficulty_match(+2)")
        else:
            debug.append("difficulty_mismatch")

    # POPULARITY
    try:
        pref_pop = int(prefs.get("popularity", 0))
        pop = int(route_row.get("popularity") or 0)
        add = max(0, 2 - abs(pop - pref_pop) / 30)
        score += add
        debug.append(f"pop_diff({pop}-{pref_pop})(+{add:.2f})")
    except Exception:
        debug.append("pop_skip")

    # TRANSPORT
    pref_trans = prefs.get("transport")
    if pref_trans:
        if pref_trans in route_row.get("transports", []):
            score += 2
            debug.append("transport_ok(+2)")
        else:
            debug.append("transport_no")

    # TAGS
    route_tags_set = set(route_row.get("tags", []))
    prefs_tags = set(prefs.get("tags", []))
    match_count = len(route_tags_set & prefs_tags)
    score += match_count * 2.5
    debug.append(f"tags_matched({match_count})*(+{match_count*2.5:.2f})")
    if prefs_tags:
        overlap_ratio = len(route_tags_set & prefs_tags) / len(prefs_tags)
        add = overlap_ratio * 2
        score += add
        debug.append(f"tags_overlap_ratio({overlap_ratio:.2f})(+{add:.2f})")

    # ДОБАВЛЕНО: Бонус за наличие ссылки
    if route_row.get("link"):
        score += 0.5
        debug.append("has_link(+0.5)")

    # small normalization summary
    logger.debug("SCORE DEBUG for '%s' : score=%.3f | %s", route_row.get("title"), score, "; ".join(debug))
    # also return numeric score
    return score


async def fetch_routes_with_meta(session) -> List[Dict[str, Any]]:
    q = await session.execute(select(Route))
    routes = q.scalars().all()
    result = []
    for r in routes:
        tags_q = await session.execute(select(route_tags.c.tag).where(route_tags.c.route_id == r.id))
        seasons_q = await session.execute(select(route_seasons.c.season).where(route_seasons.c.route_id == r.id))
        transports_q = await session.execute(select(route_transports.c.transport).where(route_transports.c.route_id == r.id))
        d = r.to_dict()
        d.update(
            {
                "tags": [t[0] for t in tags_q.all()],
                "seasons": [s[0] for s in seasons_q.all()],
                "transports": [t[0] for t in transports_q.all()],
            }
        )
        result.append(d)
    return result


async def recommend_routes(session, prefs: Dict[str, Any], limit: int = 10):
    current_season = SEASONS_BY_MONTH[datetime.utcnow().month]
    routes = await fetch_routes_with_meta(session)
    scored = sorted([(score_route(r, prefs, current_season), r) for r in routes], key=lambda x: x[0], reverse=True)
    # prepare debug log items
    top = [{"score": round(s, 3), "route": r} for s, r in scored[:limit]]
    logger.info("Top %s recommendations generated (prefs=%s).", limit, prefs)
    return top