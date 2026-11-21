"""Kitchen memory, meal plans, the cook's menu call and the nutrition picture (no network: model calls are stand-ins)."""
import asyncio
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import tracker
from app.core.store import Store
from app.experts.kitchen import planner as pl
from app.experts.kitchen.expert import KitchenExpert
from app.main import build_app

HH = {"user": {"name": "Shiva", "phone": "+919800000000"},
      "people": {"amma": {"name": "Amma", "language": "Telugu", "phone": "+919800000001"},
                 "lakshmi": {"name": "Lakshmi garu", "role": "cook", "language": "Telugu", "phone": "+919800000002"}},
      "clinics": {}, "kitchen": {"people": 2}, "nutritionist": {"name": "Dr. Nutri", "phone": "+919800000009"}}

PLAN = {"days": [{"day": "Sun", "meals": [{"slot": "breakfast", "dish": "Idli"}, {"slot": "lunch", "dish": "Pappu"}],
                  "kcal": 1700, "protein_g": 52, "carbs_g": 250, "fat_g": 50, "fibre_g": 28},
                 {"day": "Mon", "meals": [{"slot": "dinner", "dish": "Chapati, dal"}],
                  "kcal": 1800, "protein_g": 58, "carbs_g": 260, "fat_g": 55, "fibre_g": 30}],
        "ingredients": [{"item": "toor dal", "quantity": "1 kg", "have_it": False},
                        {"item": "milk", "quantity": "2 litres", "have_it": True}], "notes": "Less salt."}


def test_memory_learns_what_the_home_buys():
    st = Store(":memory:")
    assert pl.parse_line("Amul Taaza Milk 1 Ltr x2 - Rs 122") == ("Amul Taaza Milk 1 Ltr", 2, 122.0)
    pl.remember_order(st, ["Amul Taaza Milk 1 Ltr x2 - Rs 122", "Onion 1 kg x1 - Rs 66"], "swiggy", time.time() - 86400)
    pl.remember_order(st, ["Amul Taaza Milk 1 Ltr x4 - Rs 244"], "swiggy")
    u = pl.usuals(st)
    assert u[0]["name"] == "Amul Taaza Milk 1 Ltr" and u[0]["count"] == 2 and u[0]["typical"] == 3
    assert u[1]["name"] == "Onion 1 kg" and u[1]["days_ago"] >= 1


def test_tracker_record_feeds_memory_even_for_dry_runs():
    st = Store(":memory:")
    tracker.record(st, "c1", {"lines": ["Curd 500 g x1 - Rs 52"], "payload": {}}, {"dry_run": True})
    assert pl.usuals(st)[0]["store"] == "dry run"


def test_nutrition_per_person_per_day_and_cache():
    st = Store(":memory:")
    st.add_order("O1", "swiggy", None, None, ["Milk 1 Ltr x2 - Rs 122", "Dal 1 kg x1 - Rs 160"], "₹282", "", "a1")
    calls = []

    async def fake(names):
        calls.append(names)
        return {"Milk 1 Ltr": {"kcal": 600, "protein_g": 32, "carbs_g": 48, "fat_g": 30, "fibre_g": 0},
                "Dal 1 kg": {"kcal": 3400, "protein_g": 220, "carbs_g": 600, "fat_g": 15, "fibre_g": 150}}
    n = asyncio.run(pl.nutrition(st, HH, days=7, estimate=fake))
    # (2*600 + 3400) / 2 people / 7 days
    assert n["per_person_day"]["kcal"] == round(4600 / 14, 1) and n["people"] == 2 and n["targets"]["kcal"] == 1885
    assert sum(n["split"].values()) in (99, 100, 101)
    asyncio.run(pl.nutrition(st, HH, days=7, estimate=fake))
    assert len(calls) == 1                                   # estimates are cached per item


def test_plan_card_order_and_menu_call(monkeypatch):
    st = Store(":memory:")
    k = KitchenExpert(st, HH, None, object())
    card = k.plan_card(PLAN, 2)
    assert [c["id"] for c in card.choices] == ["order", "brief", "keep"] and "Idli" in card.lines[0]
    assert card.payload["need"] == [PLAN["ingredients"][0]] and any("not dietary advice" in w for w in card.warnings)
    seen = {}

    async def fake_handle(text, ref=None):
        seen["text"] = text
        from app.experts.base import Card
        return Card("kitchen", "order", "Swiggy Instamart cart", [text])
    monkeypatch.setattr(k, "handle", fake_handle)
    assert asyncio.run(k.execute(card.to_dict(), "order"))["ok"] and seen["text"] == "1 kg toor dal"
    jid = asyncio.run(k.execute(card.to_dict(), "brief"))["jobs"][0]
    job = st.job(jid)
    assert job["kind"] == "menu" and job["payload"]["to"] == "+919800000002" and job["payload"]["menu"]["day"] == "Mon"
    plan = k.call_plan(job)
    assert "AI" in plan.greeting and "QuickPick" in plan.greeting and "Chapati, dal" in plan.instructions
    tools = {f.__name__: f for f in plan.tools}
    tools["save_missing"](["1 kg toor dal"], "")
    assert asyncio.run(k.after_call(job, plan.saved)).kind == "order" and seen["text"] == "1 kg toor dal"
    assert asyncio.run(k.after_call(job, {"missing": [], "summary": "All there"})).kind == "info"


def test_nutrition_brief_is_safety_checked_and_shareable():
    os.environ.pop("GUARDRAIL_ID", None)
    k = KitchenExpert(Store(":memory:"), HH, None, None)
    nut = {"days": 7, "people": 2, "orders": 3, "per_person_day": {"kcal": 1500, "protein_g": 40, "carbs_g": 200,
           "fat_g": 45, "fibre_g": 20}, "split": {}, "targets": pl.targets(HH)}
    card = k.nutrition_card(PLAN, nut)
    assert card.kind == "brief" and card.payload["safety"] == "unchecked" and "protein 40 g" in "\n".join(card.lines)
    assert card.payload["wa"].startswith("https://wa.me/919800000009?text=")
    assert asyncio.run(k.execute(card.to_dict(), "share"))["open"] == card.payload["wa"]


@pytest.fixture
def client(monkeypatch):
    st = Store(":memory:")
    app = build_app()
    app.state.store, app.state.household = st, HH
    app.state.experts = {"kitchen": KitchenExpert(st, HH, None, object())}

    async def fake_plan(hh, store, days=3, notes="", **kw):
        return PLAN
    monkeypatch.setattr(pl, "meal_plan", fake_plan)
    with TestClient(app) as c:
        yield c, st


def test_kitchen_api(client):
    c, st = client
    pl.remember_order(st, ["Milk 1 Ltr x2 - Rs 122"], "swiggy")
    ov = c.get("/api/kitchen/overview").json()
    assert ov["usuals"][0]["name"] == "Milk 1 Ltr" and ov["cook"] == "Lakshmi garu" and ov["targets"]["source"].startswith("average of")
    r = c.post("/api/kitchen/mealplan", json={"days": 9}).json()
    assert st.card(r["card"])["card"]["kind"] == "plan" and c.get("/api/kitchen/overview").json()["plan"]["for_days"] == 7
    assert c.post("/api/kitchen/nutrition/share").status_code == 409
    st.add_order("O1", "swiggy", None, None, ["Milk 1 Ltr x2 - Rs 122"], "₹122", "", "a1")
    st.remember("home", "nutri:milk-1-ltr", {"kcal": 600, "protein_g": 32, "carbs_g": 48, "fat_g": 30, "fibre_g": 0}, "t")
    assert c.post("/api/kitchen/nutrition").json()["per_person_day"]["protein_g"] == round(64 / 2 / 7, 1)
    assert st.card(c.post("/api/kitchen/nutrition/share").json()["card"])["card"]["kind"] == "brief"
