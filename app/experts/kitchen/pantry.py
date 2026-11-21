"""What is at home, and what was eaten today.
Pantry: every delivered order (and every dry run, so the demo shows something) stocks the shelf. Each item gets a
rough shelf life from its name (milk 2 days, dal 30 days ...); items close to the end are "running low" and the
family is asked whether to reorder. Nothing is ordered from here: a reorder is a cart card that needs a tap.
Food log: meals said on a call or typed in the app, with ESTIMATED calories and macros (not dietary advice)."""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

from agents import Agent, Runner
from pydantic import BaseModel

from app.experts.kitchen.planner import parse_line, slug, targets

MODEL = os.getenv("OPENAI_MODEL")
IST = timezone(timedelta(hours=5, minutes=30))
LOW_AT = 0.25                                         # running low when a quarter (or less) of the shelf life is left

# First match wins. Days an item usually lasts in an Indian home after delivery.
SHELF = [
    (("milk", "paalu", "doodh"), 2), (("curd", "dahi", "perugu", "yogurt", "buttermilk", "majjiga"), 3),
    (("paneer", "tofu"), 4), (("bread", "pav", "bun"), 4), (("ghee", "neyyi"), 120), (("butter", "cheese"), 20),
    (("coriander", "kottimeera", "dhaniya", "mint", "pudina", "spinach", "palak", "methi",
      "curry leaves", "karivepaku", "leaves"), 3),
    (("banana", "arati"), 4), (("tomato",), 5), (("onion", "potato", "garlic", "ginger"), 20),
    (("apple", "orange", "pomegranate", "fruit"), 8),
    (("chilli", "chili", "mirchi", "lemon", "beans", "carrot", "cabbage", "capsicum", "brinjal", "okra", "bhindi",
      "gourd", "cucumber", "vegetable", "veggie", "beetroot", "cauliflower"), 5),
    (("egg",), 12),
    (("rice", "atta", "flour", "dal", "pappu", "oil", "sugar", "salt", "jaggery", "bellam", "masala", "powder",
      "tea", "coffee", "rava", "sooji", "poha", "besan", "millet", "oats", "biscuit", "noodles", "pasta"), 30),
]
DEFAULT_SHELF = 10


def shelf_days(name):
    n = name.lower()
    return next((days for words, days in SHELF if any(w in n for w in words)), DEFAULT_SHELF)


# ---------- pantry ----------
def stock(store, lines, store_name, order_id="", when=None):
    """A delivered order (or a dry run) goes on the shelf. Buying an item again refreshes it."""
    when = when or time.time()
    for line in lines:
        name, qty, _ = parse_line(line)
        store.remember("home", f"pantry:{slug(name)}", {"name": name, "qty": qty, "added": when,
                                                         "days": shelf_days(name), "store": store_name,
                                                         "order": order_id}, "delivery")


def items(store, now=None):
    """What is at home, running low first. left = rough share of the shelf life remaining (0..1)."""
    now = now or time.time()
    out = []
    for f in store.facts("home", "pantry:"):
        v = f["value"]
        age = (now - v["added"]) / 86400
        left = max(0.0, 1 - age / max(1, v["days"]))
        out.append(dict(v, key=f["key"][7:], left=round(left, 2), days_left=max(0, round(v["days"] - age, 1)),
                        low=left <= LOW_AT))
    out.sort(key=lambda v: (not v["low"], v["left"]))
    return out


def low(store, now=None):
    return [i for i in items(store, now) if i["low"]]


def used_up(store, words):
    """'We ran out of rice' -> remove pantry items whose name contains the words. Returns the names removed."""
    gone = []
    for w in words:
        s = slug(w)
        for i in items(store):
            if s and (s in i["key"] or i["key"] in s):
                store.forget("home", f"pantry:{i['key']}")
                gone.append(i["name"])
    return gone


def reorder_line(item):
    return f"{item.get('qty') or 1} x {item['name']}"


# ---------- food log ----------
class MealEstimate(BaseModel):
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float


MEAL = """Estimate the nutrition of this meal, as eaten by one adult in an Indian home. Use typical home portions
when amounts are missing (1 katori dal, 2 rotis, 1 cup rice ...). The text may be Telugu, Hindi or English.
Numbers only. These are estimates."""


async def estimate_meal(text):
    agent = Agent(name="Meal estimator", instructions=MEAL, output_type=MealEstimate, **({"model": MODEL} if MODEL else {}))
    run = await Runner.run(agent, text, max_turns=1)
    return run.final_output.model_dump()


def today_key(now=None):
    return datetime.fromtimestamp(now or time.time(), IST).strftime("%Y-%m-%d")


async def log_meal(store, text, meal="", who="me", estimate=None, now=None):
    now = now or time.time()
    est = await (estimate or estimate_meal)(text)
    entry = {"text": text, "meal": meal, "ts": now, **est}
    store.remember(who, f"meal:{today_key(now)}:{int(now * 1000)}-{uuid.uuid4().hex[:4]}", entry, "food log")
    return entry


def today(store, hh, who="me", now=None):
    """Today's food log (IST day) against the person's daily reference."""
    meals = [f["value"] for f in store.facts(who, f"meal:{today_key(now)}:")]
    keys = ("kcal", "protein_g", "carbs_g", "fat_g", "fibre_g")
    total = {k: round(sum(m.get(k, 0) for m in meals), 1) for k in keys}
    return {"meals": meals, "total": total, "targets": targets(hh), "estimated": True}
