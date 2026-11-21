"""Kitchen planner: household memory (what this family buys), weekly meal plans and a nutrition picture.
It plans and estimates; it never gives medical or diet advice. The doctor's written advice is used only to choose
between dishes and products (e.g. low salt). Nutrition numbers are estimates, compared with targets the family or
their nutritionist set in household.yaml, or with a general reference (ICMR-NIN 2020) when none are set."""
import os
import re
import time

from agents import Agent, Runner
from pydantic import BaseModel

MODEL = os.getenv("OPENAI_MODEL")
LINE = re.compile(r"^(?P<name>.+?)\s+x(?P<qty>\d+)(?:\s+-\s+Rs\s+(?P<price>[\d.]+))?\s*$")

# General reference, not a prescription: ICMR-NIN 2020 RDA for a sedentary adult (average of man and woman).
REFERENCE = {"source": "ICMR-NIN 2020, sedentary adult (general reference)",
             "kcal": 1885, "protein_g": 50, "carbs_g": 260, "fat_g": 55, "fibre_g": 30}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def parse_line(line):
    """'Amul Taaza Milk 1 Ltr x2 - Rs 122' -> ('Amul Taaza Milk 1 Ltr', 2, 122.0)."""
    m = LINE.match(str(line).strip())
    if not m:
        return str(line).strip(), 1, None
    return m["name"].strip(), int(m["qty"]), float(m["price"]) if m["price"] else None


# ---------- household memory ----------
def remember_order(store, lines, store_name, when=None):
    """Every placed order teaches QuickPick what this home buys: bought:<item> = count, quantity, last seen."""
    when = when or time.time()
    for line in lines:
        name, qty, price = parse_line(line)
        key = f"bought:{slug(name)}"
        old = next((f["value"] for f in store.facts("home", key)), None) or {}
        store.remember("home", key, {"name": name, "count": old.get("count", 0) + 1, "qty": old.get("qty", 0) + qty,
                                     "last_qty": qty, "price": price or old.get("price"), "store": store_name,
                                     "first": old.get("first", when), "last": when}, "order")


def usuals(store, limit=12):
    """Most often bought first, then most recent. Each with a typical quantity and how many days since last time."""
    rows = [f["value"] for f in store.facts("home", "bought:")]
    rows.sort(key=lambda v: (-v.get("count", 0), -v.get("last", 0)))
    now = time.time()
    return [dict(v, days_ago=round((now - v["last"]) / 86400, 1),
                 typical=max(1, round(v.get("qty", 1) / max(1, v.get("count", 1))))) for v in rows[:limit]]


# ---------- meal plan ----------
class Meal(BaseModel):
    slot: str
    dish: str


class Day(BaseModel):
    day: str
    meals: list[Meal]
    kcal: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fibre_g: int


class Ingredient(BaseModel):
    item: str
    quantity: str
    have_it: bool


class MealPlan(BaseModel):
    days: list[Day]
    ingredients: list[Ingredient]
    notes: str


PLAN = """You plan home meals for an Indian family. You are not a doctor or dietitian: never give medical or diet
advice, never prescribe calories, never mention diseases.
Household: {people} people. Diet: {diet}. Cuisine: {cuisine}. Weekly grocery budget: Rs {budget}.
Doctor's written advice in this home (use it ONLY to choose between dishes, e.g. less salt; never add claims): {advice}
Recently bought (assume still at home unless perishable and older than 3 days): {bought}
Family's notes: {notes}
Plan {days} day(s) of breakfast, lunch and dinner the cook can make (simple, everyday dishes; reuse ingredients).
For each day give ESTIMATED nutrition per person (kcal, protein, carbs, fat, fibre in grams).
List the ingredients for the whole plan with practical shop quantities (e.g. "1 kg", "500 g", "2 litres");
set have_it=true only when it is clearly in the recently bought list. Keep notes to one or two lines."""


async def meal_plan(hh, store, days=3, notes=""):
    k = hh.get("kitchen") or {}
    advice = "; ".join(str(f["value"]) for f in store.facts(prefix="advice:")) or "none"
    bought = ", ".join(f"{u['name']} ({u['days_ago']} days ago)" for u in usuals(store, 25)) or "nothing recorded"
    agent = Agent(name="Meal planner", output_type=MealPlan,
                  instructions=PLAN.format(people=k.get("people", len(hh["people"]) + 1), diet=k.get("diet", "vegetarian"),
                                           cuisine=k.get("cuisine", "Telugu home food"), budget=k.get("budget_week", 3000),
                                           advice=advice, bought=bought, notes=notes or "none", days=days),
                  **({"model": MODEL} if MODEL else {}))
    run = await Runner.run(agent, f"Plan {days} days.", max_turns=1)
    return run.final_output.model_dump()


# ---------- nutrition ----------
class Estimate(BaseModel):
    item: str
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float


class Estimates(BaseModel):
    items: list[Estimate]


ESTIMATE = """Estimate the nutrition of ONE pack of each grocery item as sold (use the pack size in the name, e.g.
"1 Ltr", "500 g"). Typical Indian values. Return one entry per item, same names, numbers only. These are estimates."""


async def estimate_packs(names):
    if not names:
        return {}
    agent = Agent(name="Nutrition estimator", instructions=ESTIMATE, output_type=Estimates,
                  **({"model": MODEL} if MODEL else {}))
    run = await Runner.run(agent, "\n".join(names), max_turns=1)
    return {e.item: e.model_dump() for e in run.final_output.items}


def targets(hh):
    t = hh.get("nutrition_targets")
    return ({**REFERENCE, **t, "source": t.get("source", "targets set by the family / nutritionist")}
            if isinstance(t, dict) else dict(REFERENCE))


async def nutrition(store, hh, days=7, estimate=estimate_packs):
    """What the household bought in the last `days`, as estimated nutrition per person per day."""
    since = time.time() - days * 86400
    orders = [o for o in store.orders(limit=200) if o["placed"] >= since]
    lines = [(parse_line(l), o["store"]) for o in orders for l in o["items"]]
    cached = {f["key"][6:]: f["value"] for f in store.facts("home", "nutri:")}
    missing = sorted({name for (name, _, _), _ in lines if slug(name) not in cached})
    if missing:
        for name, est in (await estimate(missing)).items():
            store.remember("home", f"nutri:{slug(name)}", est, "estimate")
            cached[slug(name)] = est
    people = (hh.get("kitchen") or {}).get("people", len(hh["people"]) + 1)
    total = {k: 0.0 for k in ("kcal", "protein_g", "carbs_g", "fat_g", "fibre_g")}
    for (name, qty, _), _ in lines:
        est = cached.get(slug(name))
        if est:
            for k in total:
                total[k] += est.get(k, 0) * qty
    per_day = {k: round(v / people / days, 1) for k, v in total.items()}
    energy = per_day["protein_g"] * 4 + per_day["carbs_g"] * 4 + per_day["fat_g"] * 9
    split = {k: round(per_day[g] * m / energy * 100) if energy else 0
             for k, g, m in (("protein", "protein_g", 4), ("carbs", "carbs_g", 4), ("fat", "fat_g", 9))}
    return {"days": days, "people": people, "orders": len(orders), "dry_runs": sum(o["store"] == "dry run" for o in orders),
            "per_person_day": per_day, "split": split, "targets": targets(hh), "estimated": True}


def brief_text(hh, plan, nut):
    """One page for the nutritionist: facts and estimates only, no advice."""
    t, p = nut["targets"], nut["per_person_day"]
    rows = [f"Nutrition brief: {hh['user']['name']}'s household ({nut['people']} people)",
            f"From groceries bought in the last {nut['days']} days ({nut['orders']} orders), estimated per person per day: "
            f"{p['kcal']:.0f} kcal, protein {p['protein_g']:.0f} g, carbs {p['carbs_g']:.0f} g, fat {p['fat_g']:.0f} g, "
            f"fibre {p['fibre_g']:.0f} g.",
            f"Reference used: {t['source']} ({t['kcal']} kcal, protein {t['protein_g']} g, fibre {t['fibre_g']} g)."]
    if plan:
        rows.append("Planned meals: " + " | ".join(
            f"{d['day']}: " + ", ".join(m["dish"] for m in d["meals"]) for d in plan.get("days", [])[:3]))
    rows.append("We would like your guidance on what to change. All numbers are estimates from shopping data.")
    return "\n".join(rows)
