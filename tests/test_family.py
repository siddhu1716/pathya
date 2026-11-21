"""Family nutrition: profiles, personal targets, medicines and reminder calls, per-person food log, meal plans by who is
eating, the weekly leaderboard, and the family API."""
import asyncio
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.store import Store
from app.experts.family import board, meds as M, profiles as P
from app.experts.home.expert import HomeExpert
from app.experts.kitchen import pantry, planner as pl
from app.experts.kitchen.expert import KitchenExpert
from tests.test_api import HH


def meal(kcal, protein=10.0, fibre=5.0, sugar=0.0):
    async def est(text):
        return {"kcal": kcal, "protein_g": protein, "carbs_g": 50.0, "fat_g": 10.0, "fibre_g": fibre, "sugar_g": sugar}
    return est


def test_targets_formula_goal_reference_and_nutritionist_override():
    base = {"age": 30, "sex": "male", "height_cm": 175, "weight_kg": 70, "activity": "sedentary"}
    t = P.targets({**base, "goal": "maintain"})
    assert t["kcal"] == round((10 * 70 + 6.25 * 175 - 5 * 30 + 5) * 1.2) and t["protein_g"] == 56
    assert "not a prescription" in t["source"]
    bulk = P.targets({**base, "goal": "bulk"})
    assert bulk["kcal"] == t["kcal"] + 300 and bulk["protein_g"] == 112
    assert P.targets({**base, "goal": "cut"})["kcal"] == t["kcal"] - 400
    assert P.targets({**base, "goal": "less_sugar"})["sugar_g"] < t["sugar_g"]
    assert P.targets({"goal": "maintain"})["source"].startswith("ICMR") and P.targets({"goal": "maintain"})["kcal"] == 1885
    assert "paediatrician" in P.targets({"age": 10, "height_cm": 140, "weight_kg": 30})["source"]
    own = P.targets({**base, "goal": "maintain", "override": {"kcal": 1700.0}})
    assert own["kcal"] == 1700 and own["source"] == "Set by your nutritionist" and own["protein_g"] == 56


def test_members_added_in_the_app_have_no_phone_and_are_never_called():
    store = Store(":memory:")
    assert P.keys(HH, store) == ["me", "amma"]                                   # the cook cooks; she is not listed
    dad = P.add(store, HH, "Nanna", "father")
    assert dad["key"] == "nanna" and not dad["has_phone"] and P.keys(HH, store)[-1] == "nanna"
    m = P.save(store, HH, "nanna", {"age": 62, "sex": "male", "height_cm": 170, "weight_kg": 78, "goal": "less_sugar",
                                    "conditions": "sugar (diabetes), BP", "allergies": "peanuts"})
    assert m["conditions"] == ["sugar (diabetes)", "BP"] and m["targets"]["source"].startswith("Formula")
    assert "never include" in P.describe(m) and "doctor told the family: sugar (diabetes), BP" in P.describe(m)
    with pytest.raises(ValueError):
        P.save(store, HH, "nanna", {"goal": "detox"})
    with pytest.raises(ValueError):
        HomeExpert(store, HH).call("nanna")                                      # rule 8: only household.yaml numbers
    assert M.schedule_next(store, None, "nanna", "morning") is None
    assert not P.remove(store, "amma") and P.remove(store, "nanna") and P.keys(HH, store) == ["me", "amma"]


def test_reminders_daily_for_the_course_then_stop_and_off_cancels():
    store = Store(":memory:")
    home = HomeExpert(store, HH)
    M.add(store, "amma", "Tab. Glycomet 500", "1 tablet", ["morning", "night"], days=2, food="after food")
    jobs = M.set_reminders(store, home.phone("amma"), "amma", True)
    assert sorted(store.job(j)["payload"]["slot"] for j in jobs) == ["morning", "night"]
    assert all(store.job(j)["payload"]["to"] == HH["people"]["amma"]["phone"] for j in jobs)
    morning = next(store.job(j) for j in jobs if store.job(j)["payload"]["slot"] == "morning")
    store.cancel(morning["id"])
    assert home.dialled(morning) is not None                                     # tomorrow's, scheduled when dialled
    later = store.job([j for j in store.upcoming() if j["payload"].get("slot") == "morning"][0]["id"])
    store.cancel(later["id"])
    from datetime import datetime, timedelta
    assert M.schedule_next(store, home.phone("amma"), "amma", "morning",
                           after=datetime.now(M.IST) + timedelta(days=3)) is None   # the 2-day course is over
    M.set_reminders(store, home.phone("amma"), "amma", False)
    assert [j for j in store.upcoming() if j["kind"] == "meds"] == []


def test_reminder_call_reads_as_written_and_relays_a_missed_dose():
    store = Store(":memory:")
    home = HomeExpert(store, HH)
    M.add(store, "amma", "Tab. Glycomet 500", "1 tablet", ["night"], food="after food")
    M.set_reminders(store, home.phone("amma"), "amma", True)
    job = [j for j in store.upcoming() if j["kind"] == "meds"][0]
    plan = home.call_plan(job)
    assert "Tab. Glycomet 500 1 tablet after food" in plan.instructions and "never suggest" in plan.instructions
    t = {f.__name__: f for f in plan.tools}
    t["dose_taken"]("no", "inka tinaledu, tarvata vesukuntanu")
    t["end_call"]("Reminded", True, "all_done")
    assert asyncio.run(home.after_call(job, plan.saved)) is None
    relay = store.cards()[0]["card"]
    assert relay["kind"] == "relay" and "Amma" in relay["title"] and "inka tinaledu" in relay["lines"][0]
    assert M.today(store, "amma")[0]["taken"] == "no"
    out = asyncio.run(home.execute(relay, "call"))
    assert store.job(out["jobs"][0])["kind"] == "home" and store.job(out["jobs"][0])["person"] == "amma"


def test_food_log_per_person_and_leaderboard_counts_habits_only():
    store = Store(":memory:")
    for text in ("2 idli", "rice, pappu", "2 chapati, dal"):
        asyncio.run(pantry.log_meal(store, text, "", who="amma", estimate=meal(600, protein=20, fibre=9)))
    asyncio.run(pantry.log_meal(store, "upma", "", who="me", estimate=meal(300)))
    assert pantry.today(store, HH, "amma")["total"]["kcal"] == 1800 and len(pantry.today(store, HH, "me")["meals"]) == 1
    M.log_dose(store, "amma", "night", "yes", "vesukunnanu")
    M.log_dose(store, "me", "night", "no", "marchipoyanu")
    rows = {r["key"]: r for r in board.board(store, HH)["rows"]}
    a = rows["amma"]["breakdown"]
    assert a["meal"] == 15 and a["on_target"] == 10 and a["protein"] == 5 and a["fibre"] == 5 and a["dose"] == 10
    assert rows["me"]["breakdown"]["dose"] == 0 and board.board(store, HH)["rows"][0]["key"] == "amma"
    assert set(a) == set(board.POINTS)                                            # no points for readings or weight


def test_plan_prompt_has_each_eater_and_guests_and_plates_reach_the_cook():
    store = Store(":memory:")
    P.add(store, HH, "Nanna", "father")
    P.save(store, HH, "nanna", {"goal": "less_sugar", "conditions": ["sugar"], "allergies": "peanuts"})
    eaters = [P.member(HH, store, k) for k in ("me", "nanna")]
    text = pl.plan_prompt(HH, store, 1, "", eaters, guests=2)
    assert "(4 people, including 2 guest(s))" in text and "Nanna (father)" in text and "never include): peanuts" in text
    assert "Amma" not in text and "never mention diseases" in text
    plan = {"days": [{"day": "Mon", "meals": [{"slot": "lunch", "dish": "Pappu, rice"}], "kcal": 600, "protein_g": 20,
                      "carbs_g": 80, "fat_g": 15, "fibre_g": 8,
                      "people": [{"who": "Nanna", "plate": "half rice, extra dal, tea without sugar", "kcal": 1700,
                                  "protein_g": 60, "fibre_g": 30, "sugar_g": 10}]}],
            "ingredients": [], "notes": ""}
    k = KitchenExpert(store, HH, None, object())
    card = k.plan_card(plan, 1, (2, 2))
    assert card.title.endswith("for 4 people (2 guests)") and any(l.startswith("Nanna's plate: half rice") for l in card.lines)
    job = store.job(k.menu_call("lakshmi", plan["days"][0]))
    assert "Nanna: half rice, extra dal, tea without sugar" in k.call_plan(job).instructions
    home = HomeExpert(store, HH)
    store.remember("home", "mealplan", plan, "t")
    assert home.plate(P.member(HH, store, "nanna")) == "half rice, extra dal, tea without sugar"


def test_store_is_safe_across_threads():
    from concurrent.futures import ThreadPoolExecutor
    store = Store(":memory:")

    def work(n):
        for i in range(150):
            store.remember(f"p{n}", f"k{i % 5}", {"i": i}, "t")
            store.facts(prefix="k")
            store.log("t", str(n), "x")
        return True
    with ThreadPoolExecutor(8) as pool:                                          # FastAPI's thread pool + the loop
        assert all(pool.map(work, range(8)))
    assert len(store.facts(prefix="k")) == 40


@pytest.fixture
def client():
    from app.experts.doorstep.expert import DoorstepExpert
    from app.experts.health.expert import HealthExpert
    from app.main import build_app
    store = Store(":memory:")
    app = build_app()
    app.state.store, app.state.household = store, HH
    app.state.experts = {"health": HealthExpert(store, HH), "doorstep": DoorstepExpert(store, HH),
                         "home": HomeExpert(store, HH)}
    with TestClient(app) as c:
        yield c, store


def test_family_api(client, monkeypatch):
    c, store = client
    fam = c.get("/api/family").json()
    assert [m["key"] for m in fam["members"]] == ["me", "amma"] and "phone" not in fam["members"][0]
    assert c.post("/api/family", json={"name": "Nanna", "relation": "father"}).json()["has_phone"] is False
    r = c.put("/api/family/nanna", json={"age": 62, "height_cm": 170, "weight_kg": 78, "sex": "male", "goal": "less_sugar"})
    assert r.status_code == 200 and r.json()["targets"]["source"].startswith("Formula")
    assert c.put("/api/family/nanna", json={"age": 500}).status_code == 400
    assert c.post("/api/family/nanna/reminders", json={"on": True}).status_code == 400     # no phone: never called
    assert c.post("/api/family/nanna/call").status_code == 400
    v = c.post("/api/family/amma/meds", json={"name": "Tab. Amlong 5", "dose": "1", "times": ["morning"], "days": 30}).json()
    assert v["meds"][0]["name_as_written"] == "Tab. Amlong 5" and v["doses"][0]["slot"] == "morning"
    assert c.post("/api/family/amma/meds", json={"name": "X", "times": []}).status_code == 400
    assert c.post("/api/family/amma/reminders", json={"on": True}).json()["jobs"]
    monkeypatch.setattr(pantry, "estimate_meal", meal(400))
    assert c.post("/api/kitchen/meal", json={"text": "2 dosa", "who": "nanna"}).json()["kcal"] == 400
    assert c.post("/api/kitchen/meal", json={"text": "2 dosa", "who": "ghost"}).status_code == 404
    fam = c.get("/api/family").json()
    nanna = next(m for m in fam["members"] if m["key"] == "nanna")
    assert nanna["today"]["total"]["kcal"] == 400 and nanna["today"]["targets"]["source"].startswith("Formula")
    assert any(r["key"] == "nanna" and r["points"] == 5 for r in fam["board"]["rows"])
    assert c.post("/api/family/amma/call?via=browser").json()["job"]
    assert c.delete("/api/family/amma").status_code == 409 and c.delete("/api/family/nanna").json()["ok"]
