"""Health score: 0-100 per family member over the last 7 days, built from habits only. It never uses readings (BP,
sugar), body weight or any diagnosis (AGENTS.md rule 9), and it is not a medical assessment.
Parts and weights: food 40 (meals logged, near their own targets), medicines 30 (doses taken as written), movement 15
(steps from a watch), check-ins 15 (daily check-in calls answered). A part with no source (no medicines listed, no
watch, no daily call) is left out and the others are re-weighted."""
import time
from datetime import datetime, timedelta

from app.experts.family import meds as M
from app.experts.family import profiles as P
from app.experts.family.meds import IST

WEIGHTS = {"food": 40, "medicines": 30, "movement": 15, "checkins": 15}
DAYS = 7
STEPS = 7000
ABOUT = ("Built from habits over the last 7 days: meals logged and close to their own targets, medicines taken as "
         "written, movement and check-in calls answered. Not a medical test; readings and weight never count.")


def _days(now):
    today = datetime.fromtimestamp(now, IST).replace(hour=0, minute=0, second=0, microsecond=0)
    return [today - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]


def food(store, m, days):
    t = m["targets"]
    hits = dict(logged=0, energy=0, protein=0, fibre=0, sugar=0)
    total = 0.0
    for d in days:
        meals = [f["value"] for f in store.facts(m["key"], f"meal:{d:%Y-%m-%d}:")]
        if not meals:
            continue
        s = lambda k: sum(x.get(k, 0) for x in meals)
        ok = {"energy": abs(s("kcal") - t["kcal"]) <= 0.15 * t["kcal"], "protein": s("protein_g") >= 0.9 * t["protein_g"],
              "fibre": s("fibre_g") >= 0.8 * t["fibre_g"], "sugar": s("sugar_g") <= t["sugar_g"]}
        hits["logged"] += 1
        for k, v in ok.items():
            hits[k] += v
        total += sum(ok.values()) / 4
    tips = []
    if hits["logged"] < DAYS:
        tips.append(f"Log meals every day (logged on {hits['logged']} of {DAYS} days). A photo of the plate is enough.")
    if hits["logged"]:
        if hits["protein"] < hits["logged"]:
            tips.append(f"Protein reached their target on {hits['protein']} of {hits['logged']} logged days: dal, curd, "
                        "paneer, eggs or sprouts help.")
        if hits["fibre"] < hits["logged"]:
            tips.append(f"Fibre reached 80% on {hits['fibre']} of {hits['logged']} days: vegetables, millets, fruit.")
        if hits["sugar"] < hits["logged"]:
            tips.append(f"Added sugar stayed under their limit on {hits['sugar']} of {hits['logged']} days.")
        if hits["energy"] < hits["logged"]:
            tips.append(f"Energy was within 15% of their target on {hits['energy']} of {hits['logged']} days: the meal "
                        "plan's +/- and Fit buttons help.")
    return {"value": total / DAYS, "detail": f"Meals logged on {hits['logged']} of {DAYS} days; protein met on "
            f"{hits['protein']}, fibre on {hits['fibre']}, added sugar in limit on {hits['sugar']}.", "tips": tips}


def medicines(store, m, days, now):
    listed = M.listed(store, m["key"])
    if not listed:
        return None
    due = taken = 0
    for d in days:
        logs = {f["value"]["slot"]: f["value"] for f in store.facts(m["key"], f"medlog:{d:%Y-%m-%d}:")}
        for slot, hour in M.SLOTS.items():
            at = (d + timedelta(hours=hour)).timestamp()
            if at <= now and [x for x in M.active(listed, slot, at) if x["start"] <= at + 3600]:
                due += 1
                taken += (logs.get(slot) or {}).get("taken") == "yes"
    if not due:
        return None
    tips = [] if taken == due else [f"{due - taken} dose(s) were not confirmed. Reminder calls can ask at the dose time."]
    return {"value": taken / due, "detail": f"{taken} of {due} doses confirmed as taken, as written.", "tips": tips}


def movement(store, m, days):
    seen = [next((f["value"] for f in store.facts(m["key"], f"activity:{d:%Y-%m-%d}")), None) for d in days]
    seen = [s for s in seen if s]
    if not seen:
        return None
    value = sum(min(1, s.get("steps", 0) / STEPS) for s in seen) / len(seen)
    good = sum(s.get("steps", 0) >= STEPS for s in seen)
    return {"value": value, "detail": f"{STEPS:,} steps on {good} of {len(seen)} days with watch data.",
            "tips": [] if good == len(seen) else ["A short walk after meals adds up."]}


def checkins(store, m, days, daily_hour, now):
    if daily_hour is None:
        return None
    since = days[0].timestamp()
    answered = {datetime.fromtimestamp(f["updated"], IST).date() for f in store.facts(m["key"], "call:")
                if f["updated"] >= since}
    started = next((f["updated"] for f in store.facts(m["key"], "daily") if f["key"] == "daily"), since)
    expected = max(1, min(DAYS, (datetime.fromtimestamp(now, IST).date() - datetime.fromtimestamp(started, IST).date()).days))
    value = min(1, len(answered) / expected)
    return {"value": value, "detail": f"Answered check-in calls on {len(answered)} of the last {expected} days.",
            "tips": [] if value >= 1 else ["Missed calls ring again the next evening."]}


def label(score):
    if score is None:
        return "Not enough data yet"
    return "Strong week" if score >= 80 else "Steady" if score >= 60 else "Room to grow"


def score(store, m, daily_hour=None, now=None):
    now = now or time.time()
    days = _days(now)
    parts = {"food": food(store, m, days), "medicines": medicines(store, m, days, now), "movement": movement(store, m, days),
             "checkins": checkins(store, m, days, daily_hour, now)}
    used = {k: v for k, v in parts.items() if v is not None}
    weight = sum(WEIGHTS[k] for k in used)
    value = round(sum(WEIGHTS[k] * v["value"] for k, v in used.items()) / weight * 100) if weight else None
    if value == 0 and not any(v["value"] for v in used.values()) and set(used) == {"food"}:
        value = None                                               # nothing logged at all: no score, not "0"
    return {"key": m["key"], "name": m["name"], "score": value, "label": label(value), "about": ABOUT,
            "parts": [{"part": k, "weight": WEIGHTS[k], "percent": round(v["value"] * 100), "detail": v["detail"],
                       "tips": v["tips"]} for k, v in used.items()],
            "missing": [k for k in WEIGHTS if k not in used]}


def board(store, hh, daily=lambda key: None, now=None):
    rows = sorted((score(store, m, daily(m["key"]), now) for m in P.members(hh, store)),
                  key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    star = rows[0] if rows and rows[0]["score"] is not None else None
    return {"rows": rows, "star": star["name"] if star else None, "about": ABOUT}
