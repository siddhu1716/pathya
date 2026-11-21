"""Weekly family leaderboard (Monday to Sunday, IST). Points for habits only: logging meals, eating close to your own
targets, medicines taken as written, answering check-in calls. Never for readings (BP, sugar) or body weight."""
import time
from datetime import datetime, timedelta

from app.experts.family import profiles
from app.experts.family.meds import IST

POINTS = {"meal": 5, "on_target": 10, "protein": 5, "fibre": 5, "dose": 10, "checkin": 5, "steps": 5, "streak": 10}
RULES = ["+5 a meal logged (3 a day)", "+10 a day within 10% of your energy target", "+5 protein target reached",
         "+5 fibre 80% reached", "+10 a medicine dose taken as written", "+5 a call answered",
         "+5 a day with 7,000 steps (from a wearable)", "+10 a 3-day logging streak"]


def week_start(now=None):
    d = datetime.fromtimestamp(now or time.time(), IST)
    return (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def score(store, m, now=None):
    now = now or time.time()
    start = week_start(now)
    t = m["targets"]
    pts = dict.fromkeys(POINTS, 0)
    run = best = 0
    day = start
    while day.timestamp() <= now:
        meals = [f["value"] for f in store.facts(m["key"], f"meal:{day:%Y-%m-%d}:")]
        moved = next((f["value"] for f in store.facts(m["key"], f"activity:{day:%Y-%m-%d}")), None) or {}
        if moved.get("steps", 0) >= 7000:
            pts["steps"] += POINTS["steps"]
        if meals:
            pts["meal"] += POINTS["meal"] * min(3, len(meals))
            total = lambda k: sum(x.get(k, 0) for x in meals)
            if abs(total("kcal") - t["kcal"]) <= 0.1 * t["kcal"]:
                pts["on_target"] += POINTS["on_target"]
            if total("protein_g") >= t["protein_g"]:
                pts["protein"] += POINTS["protein"]
            if total("fibre_g") >= 0.8 * t["fibre_g"]:
                pts["fibre"] += POINTS["fibre"]
            run += 1
            best = max(best, run)
        else:
            run = 0
        day += timedelta(days=1)
    since = start.timestamp()
    pts["dose"] = POINTS["dose"] * sum(1 for f in store.facts(m["key"], "medlog:")
                                       if f["value"].get("ts", 0) >= since and f["value"].get("taken") == "yes")
    pts["checkin"] = POINTS["checkin"] * sum(1 for f in store.facts(m["key"], "call:") if f["updated"] >= since)
    pts["streak"] = POINTS["streak"] if best >= 3 else 0
    return {"key": m["key"], "name": m["name"], "points": sum(pts.values()), "breakdown": pts, "streak": best}


def board(store, hh, now=None):
    rows = sorted((score(store, m, now) for m in profiles.members(hh, store)), key=lambda r: -r["points"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"week_of": week_start(now).strftime("%d %b"), "rows": rows, "rules": RULES}
