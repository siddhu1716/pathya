"""Medicines and reminder calls, per family member. Medicines are kept exactly as written (by hand, or from a
prescription photo a human confirmed). QuickPick never suggests, starts, stops or changes a medicine or dose (rule 9):
reminder calls only remind, and record the answer in the person's words.
Each reminder call schedules the next day's when it is dialled, until the course (days as written) ends."""
import time
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
SLOTS = {"morning": 9, "afternoon": 14, "night": 21}            # reminder call times, IST


def next_at(hour, after=None):
    now = (after or datetime.now(IST)).astimezone(IST)
    t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return t if t > now else t + timedelta(days=1)


def day_key(ts=None):
    return datetime.fromtimestamp(ts or time.time(), IST).strftime("%Y-%m-%d")


def listed(store, key):
    rows = store.facts(key, "meds")
    meds = next((f["value"] for f in rows if f["key"] == "meds"), None) or []
    started = next((f["updated"] for f in rows if f["key"] == "meds"), time.time())
    return [dict(m, start=m.get("start") or started) for m in meds if isinstance(m, dict)]


def add(store, key, name, dose="", times=(), days=None, food=""):
    name = str(name).strip()[:80]
    times = [t for t in times if t in SLOTS]
    if not name or not times:
        raise ValueError("Write the medicine name as on the strip or paper, and pick at least one time.")
    med = {"name_as_written": name, "dose": str(dose or "").strip()[:40] or None, "food": str(food or "").strip()[:40] or None,
           "days": int(days) if days else None, "start": time.time(), "source": "entered by family",
           **{s: s in times for s in SLOTS}}
    store.remember(key, "meds", listed(store, key) + [med], "entered by family")
    return med


def remove(store, key, index):
    meds = listed(store, key)
    if not 0 <= index < len(meds):
        return False
    store.remember(key, "meds", meds[:index] + meds[index + 1:], "entered by family")
    return True


def active(meds, slot, now=None):
    """Medicines for this time of day whose course (days as written) has not ended."""
    now = now or time.time()
    return [m for m in meds if m.get(slot) and not (m.get("days") and now > m["start"] + m["days"] * 86400)]


def line(m):
    return " ".join(str(x) for x in (m.get("name_as_written"), m.get("strength"), m.get("dose"), m.get("food")) if x)


def reminders_on(store, key):
    return bool(next((f["value"] for f in store.facts(key, "reminders") if f["key"] == "reminders"), False))


def _scheduled(store, key):
    return [j for j in store.upcoming() if j["expert"] == "home" and j["kind"] == "meds" and j["person"] == key]


def schedule_next(store, phone, key, slot, after=None):
    """The next reminder call for one time of day, if reminders are on and something is still to be taken then."""
    if not phone or not reminders_on(store, key) or any(j["payload"].get("slot") == slot for j in _scheduled(store, key)):
        return None
    at = next_at(SLOTS[slot], after)
    if not active(listed(store, key), slot, at.timestamp()):
        return None
    return store.add_job("home", "meds", key, {"who": key, "slot": slot, "to": phone}, at.timestamp())


def set_reminders(store, phone, key, on):
    store.remember(key, "reminders", bool(on), "family")
    if not on:
        for j in _scheduled(store, key):
            store.cancel(j["id"])
        return []
    return [j for j in (schedule_next(store, phone, key, s) for s in SLOTS) if j]


def log_dose(store, key, slot, taken, words, ts=None):
    ts = ts or time.time()
    store.remember(key, f"medlog:{day_key(ts)}:{slot}", {"slot": slot, "taken": taken, "words": words, "ts": ts},
                   "reminder call")


def today(store, key, now=None):
    """Today's doses: per time of day, what is due (as written) and the answer recorded, if any."""
    now = now or time.time()
    meds = listed(store, key)
    logs = {f["value"]["slot"]: f["value"] for f in store.facts(key, f"medlog:{day_key(now)}:")}
    out = []
    for slot, hour in SLOTS.items():
        due = active(meds, slot, now)
        if due:
            log = logs.get(slot) or {}
            out.append({"slot": slot, "hour": hour, "meds": [line(m) for m in due], "taken": log.get("taken"),
                        "words": log.get("words")})
    return out
