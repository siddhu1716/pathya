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
    """Every placed order teaches Pathya what this home buys: bought:<item> = count, quantity, last seen."""
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
class Part(BaseModel):
    food: str
    unit: str
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float
    sugar_g: float


class Portion(BaseModel):
    who: str
    qty: list[float]


class Meal(BaseModel):
    slot: str
    dish: str
    parts: list[Part]
    portions: list[Portion]


class PersonDay(BaseModel):
    who: str
    plate: str


class Day(BaseModel):
    day: str
    meals: list[Meal]
    people: list[PersonDay]


class Ingredient(BaseModel):
    item: str
    quantity: str
    have_it: bool


class MealPlan(BaseModel):
    days: list[Day]
    ingredients: list[Ingredient]
    notes: str


PLAN = """You plan home meals for an Indian family: one kitchen and one cook make one menu, but each person gets their
own plate. You are not a doctor or dietitian: never diagnose, never give medical advice, never mention diseases, never
make health claims, never prescribe.
Who eats ({people} people{guests}):
{eaters}
Health notes are only what the family says the doctor told them, and goals are what the family chose. Use them ONLY to
choose dishes, portions and simple swaps on that person's plate (for example "half rice, extra dal", "tea without
sugar", "extra paneer and curd"). Never put an allergy item on that person's plate.
Kitchen: {diet}. Cuisine: {cuisine}. Weekly grocery budget: Rs {budget}.
Doctor's written advice in this home (use it ONLY to choose between dishes, e.g. less salt; never add claims): {advice}
Recently bought (assume still at home unless perishable and older than 3 days): {bought}
Family's notes: {notes}
Plan {days} day(s) of breakfast, lunch and dinner the cook can make (simple, everyday dishes; reuse ingredients).
For each meal give: the dish; its parts, each a food with a household unit (cup, katori, roti, dosa, idli, piece,
glass, tbsp) and the ESTIMATED nutrition of ONE unit (sugar_g = added sugar); and portions: one entry per eater
(who = just their name, without anything in brackets) with the quantity of every part, in the same order (halves allowed, 0 = skip),
chosen so each person's whole day lands close to their own targets and fits their notes. In people, one entry per eater
with a one-line plate note for the day (for example "half rice, extra dal, tea without sugar"). Guests eat the
standard plate.
List the ingredients for the whole plan for {people} people with practical shop quantities (e.g. "1 kg", "500 g",
"2 litres"); set have_it=true only when it is clearly in the recently bought list. Keep notes to one or two lines."""


def plan_prompt(hh, store, days=3, notes="", eaters=None, guests=0):
    """eaters: family member dicts (app/experts/family/profiles.py); None = everyone in the family."""
    from app.experts.family import profiles as P
    k = hh.get("kitchen") or {}
    eaters = P.members(hh, store) if eaters is None else eaters
    advice = "; ".join(str(f["value"]) for f in store.facts(prefix="advice:")) or "none"
    bought = ", ".join(f"{u['name']} ({u['days_ago']} days ago)" for u in usuals(store, 25)) or "nothing recorded"
    who = "\n".join(f"- {P.describe(m)}" for m in eaters) or "- the family (no profiles yet)"
    return PLAN.format(people=max(1, len(eaters) + guests), guests=f", including {guests} guest(s)" if guests else "",
                       eaters=who, diet=k.get("diet", "vegetarian"), cuisine=k.get("cuisine", "Telugu home food"),
                       budget=k.get("budget_week", 3000), advice=advice, bought=bought, notes=notes or "none", days=days)


async def meal_plan(hh, store, days=3, notes="", eaters=None, guests=0):
    agent = Agent(name="Meal planner", output_type=MealPlan,
                  instructions=plan_prompt(hh, store, days, notes, eaters, guests),
                  **({"model": MODEL} if MODEL else {}))
    run = await Runner.run(agent, f"Plan {days} days.", max_turns=1)
    return fill(run.final_output.model_dump())


NUTRIENTS = ("kcal", "protein_g", "carbs_g", "fat_g", "fibre_g", "sugar_g")


def person_day(day, who):
    """One person's day, from the parts x their quantities (so +/- changes the numbers exactly)."""
    total = dict.fromkeys(NUTRIENTS, 0.0)
    for meal in day.get("meals", []):
        portion = next((p for p in meal.get("portions") or [] if p["who"] == who), None)
        for part, q in zip(meal.get("parts") or [], (portion or {}).get("qty") or []):
            for k in NUTRIENTS:
                total[k] += part.get(k, 0) * q
    return {k: round(v) for k, v in total.items()}


def bare(who):
    """'Shiva (me, 30)' -> 'Shiva': the planner sometimes copies the description."""
    return re.sub(r"\s*\(.*\)\s*$", "", str(who)).strip()


def fill(plan):
    """Totals per person per day (people[]) and the average plate (day kcal, protein_g ...) from the quantities."""
    for day in plan.get("days", []):
        for x in [p for m in day.get("meals", []) for p in m.get("portions") or []] + list(day.get("people") or []):
            x["who"] = bare(x["who"])
        names = list(dict.fromkeys(p["who"] for m in day.get("meals", []) for p in m.get("portions") or []))
        if not names:
            continue
        notes = {p["who"]: p.get("plate", "") for p in day.get("people") or []}
        day["people"] = [{"who": n, "plate": notes.get(n, ""), **person_day(day, n)} for n in names]
        for k in NUTRIENTS:
            day[k] = round(sum(p[k] for p in day["people"]) / len(day["people"]))
    return plan


def set_qty(plan, d, m, part, who, qty):
    meal = plan["days"][d]["meals"][m]
    portion = next((p for p in meal["portions"] if p["who"] == who), None)
    if portion is None:
        portion = {"who": who, "qty": [0.0] * len(meal["parts"])}
        meal["portions"].append(portion)
    portion["qty"] += [0.0] * (len(meal["parts"]) - len(portion["qty"]))
    portion["qty"][part] = max(0.0, min(20.0, round(qty * 4) / 4))
    return fill(plan)


def fit(plan, d, who, kcal):
    """Scale one person's quantities for one day so their energy lands near their target (halves, nothing below 0)."""
    now = person_day(plan["days"][d], who)["kcal"]
    if not now or not kcal:
        return plan
    factor = kcal / now
    for meal in plan["days"][d]["meals"]:
        for p in meal.get("portions") or []:
            if p["who"] == who:
                p["qty"] = [max(0.0, round(q * factor * 2) / 2) if q else 0.0 for q in p["qty"]]
    return fill(plan)


def plate_text(day, who):
    """'rice 1.5 cup, dal 1 katori ...' for the cook."""
    out = []
    for meal in day.get("meals", []):
        portion = next((p for p in meal.get("portions") or [] if p["who"] == who), None)
        if portion:
            out += [f"{part['food']} {q:g} {part['unit']}" for part, q in zip(meal["parts"], portion["qty"]) if q]
    return ", ".join(out)


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
    orders = [o for o in store.orders(limit=200) if o["placed"] >= since and o["store"] != "dry run"]   # real orders only
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
    """One page for the nutritionist or doctor: facts and estimates only, no advice. Zero orders are said as such,
    never as "0 kcal a day" (that would read as the family eating nothing)."""
    t, p = nut["targets"], nut["per_person_day"]
    rows = [f"Nutrition brief: {hh['user']['name']}'s household ({nut['people']} people)"]
    if nut.get("orders"):
        rows.append(f"From groceries bought in the last {nut['days']} days ({nut['orders']} orders), estimated per person "
                    f"per day: {p['kcal']:.0f} kcal, protein {p['protein_g']:.0f} g, carbs {p['carbs_g']:.0f} g, "
                    f"fat {p['fat_g']:.0f} g, fibre {p['fibre_g']:.0f} g.")
    else:
        rows.append(f"No groceries were ordered through Pathya in the last {nut['days']} days, so there is no shopping "
                    "estimate yet.")
    rows.append(f"Daily targets used: {t['source']} ({t['kcal']} kcal, protein {t['protein_g']} g, fibre {t['fibre_g']} g).")
    if plan:
        rows.append("Planned meals: " + " | ".join(
            f"{d['day']}: " + ", ".join(m["dish"] for m in d["meals"]) for d in plan.get("days", [])[:3]))
    rows.append("We would like your guidance on what to change. All numbers are estimates"
                + (" from shopping data." if nut.get("orders") else "."))
    return "\n".join(rows)
