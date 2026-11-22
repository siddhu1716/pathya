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
from app.experts.family import meds as M, profiles as P, score as S
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
    assert "ICMR-NIN" in P.targets({"goal": "maintain"})["source"] and P.targets({"goal": "maintain"})["kcal"] == 1885
    man = P.targets({"sex": "male", "goal": "bulk"})                              # no measurements: still per goal
    assert man["kcal"] == 2110 + 300 and man["protein_g"] == round(65 * 1.6)
    assert P.targets({"sex": "female", "goal": "cut"})["kcal"] == 1660 - 400
    amma = P.targets({"age": 62, "sex": "female", "height_cm": 155, "weight_kg": 60, "goal": "maintain"})
    assert amma["protein_g"] == 60 and "(60+)" in amma["source"]                  # 1.0 g/kg from 60
    lean = P.targets({**base, "goal": "maintain", "body": {"body_fat_pct": 20}})
    assert lean["kcal"] == round((370 + 21.6 * 56) * 1.2) and "Katch-McArdle" in lean["source"]
    assert P.targets({**base, "goal": "maintain", "body": {"bmr_kcal": 1600}})["kcal"] == 1920
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
    assert m["conditions"] == ["sugar (diabetes)", "BP"] and "Mifflin" in m["targets"]["source"] and m["elder"]
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


def test_food_log_per_person_and_health_score_from_habits_only():
    from datetime import datetime
    store = Store(":memory:")
    for text in ("2 idli", "rice, pappu", "2 chapati, dal"):
        asyncio.run(pantry.log_meal(store, text, "", who="amma", estimate=meal(600, protein=20, fibre=9)))
    asyncio.run(pantry.log_meal(store, "upma", "", who="me", estimate=meal(300)))
    assert pantry.today(store, HH, "amma")["total"]["kcal"] == 1800 and len(pantry.today(store, HH, "me")["meals"]) == 1
    now = datetime.now(M.IST).replace(hour=22, minute=0, second=0, microsecond=0).timestamp()
    store.remember("amma", "meds", [{"name_as_written": "Tab. X", "night": True, "start": now - 10 * 86400}], "t")
    M.log_dose(store, "amma", "night", "yes", "vesukunnanu", ts=now - 3600)
    M.log_dose(store, "amma", "night", "yes", "", ts=now - 86400 - 3600)
    store.remember("amma", f"activity:{M.day_key(now)}", {"steps": 7200, "active_kcal": 200, "source": "watch"}, "t")
    amma = S.score(store, P.member(HH, store, "amma"), now=now)
    parts = {p["part"]: p for p in amma["parts"]}
    assert set(parts) == {"food", "medicines", "movement"} and amma["missing"] == ["checkins"]   # no daily call yet
    assert parts["medicines"]["detail"].startswith("2 of 7 doses") and parts["movement"]["percent"] == 100
    assert amma["score"] == round((40 * 1 / 7 + 30 * 2 / 7 + 15) / 85 * 100) and amma["label"] == "Room to grow"
    assert any("Log meals every day" in t for t in parts["food"]["tips"])
    assert S.score(store, P.member(HH, store, "me"), now=now)["score"] is not None              # one meal logged
    assert S.score(Store(":memory:"), P.member(HH, store, "me"), now=now)["score"] is None       # nothing: no score
    assert "never count" in amma["about"] and set(S.WEIGHTS) == {"food", "medicines", "movement", "checkins"}


def test_check_in_part_never_expects_fewer_days_than_were_answered():
    from datetime import datetime
    store = Store(":memory:")
    now = datetime.now(M.IST).replace(hour=10, minute=0, second=0, microsecond=0).timestamp()
    store.remember("amma", "call:1", {"summary": "yesterday"}, "t")
    store.remember("amma", "call:2", {"summary": "today"}, "t")
    store.remember("amma", "daily", {"hour": 19}, "t")
    store.db.execute("UPDATE facts SET updated=? WHERE key='call:1'", (now - 86400,))
    store.db.execute("UPDATE facts SET updated=? WHERE key IN ('call:2','daily')", (now - 3600,))
    part = S.checkins(store, P.member(HH, store, "amma"), S._days(now), 19, now)
    assert part["value"] == 1 and part["detail"] == "Answered check-in calls on 2 of the last 2 days."


def test_parents_get_the_daily_check_in_by_default_unless_switched_off():
    store = Store(":memory:")
    home = HomeExpert(store, HH)
    assert len(home.default_daily()) == 1 and home.daily_hour("amma") == 20 and home.daily_hour("me") is None
    assert home.default_daily() == []                                           # never twice
    home.turn_off_daily("amma")
    assert home.default_daily() == [] and home.daily_hour("amma") is None      # the family's "off" sticks
    home.daily(19, "amma")
    assert home.daily_hour("amma") == 19 and not store.facts("amma", "daily_off")


def test_goal_weight_progress():
    store = Store(":memory:")
    P.save(store, HH, "me", {"weight_kg": 60, "goal": "bulk", "target_weight_kg": 66})
    assert P.member(HH, store, "me")["goal_progress"]["percent"] == 0
    store.remember("me", "weight:2026-12-01", {"kg": 63, "ts": time.time() + 10}, "t")
    store.remember("me", "profile", {**P.profile(store, "me"), "weight_kg": 63}, "t")
    g = P.member(HH, store, "me")["goal_progress"]
    assert g["percent"] == 50 and g["left_kg"] == 3
    assert P.member(HH, store, "amma")["goal_progress"] is None                 # maintain: no goal bar


def test_booking_saved_clinic_or_find_then_add_to_household(tmp_path, monkeypatch):
    from app.experts.health import finder
    from app.experts.health.expert import HealthExpert
    assert finder.e164("040 2345 6789") == "+914023456789" and finder.e164("+91-98480-22338") == "+919848022338"
    assert finder.e164("12345") == ""
    yml = tmp_path / "household.yaml"
    yml.write_text("user:\n  name: Shiva\nclinics:\n  rao:   # a comment stays\n    doctor: Dr. Rao\n"
                   "    clinic: Sunrise Clinic\n    phone: '+919800000003'\npeople: {}\n", encoding="utf-8")
    hh = {**HH, "clinics": dict(HH["clinics"])}
    store = Store(":memory:")
    h = HealthExpert(store, hh, path=str(yml))
    card = h.request_card({"patient": "Amma", "hospital": "Sunrise", "reason": "knee pain", "from": "2026-12-01",
                           "to": "2026-12-03", "part": "morning"})
    assert card.kind == "bookreq" and card.choices[0]["id"] == "book" and card.payload["clinic"] == "rao"
    job = store.job(asyncio.run(h.execute(card.to_dict(), "book"))["jobs"][0])
    assert job["kind"] == "book" and job["payload"]["window_start"] == "2026-12-01T00:00" and job["payload"]["part"] == "morning"
    new = h.request_card({"patient": "Amma", "hospital": "Care Hospitals", "doctor": "Dr. Kumar", "area": "Banjara Hills"})
    assert new.choices[0]["id"] == "find"
    assert "to be assigned" not in " ".join(h.request_card({"patient": "Amma", "hospital": "Yashoda", "doctor": "Doctor to be assigned"}).lines)
    monkeypatch.setattr(finder, "find_clinic", lambda *a, **k: {"clinic": "CARE Hospitals Banjara Hills", "doctor": "Dr. Kumar",
                                                              "phone": "040 6165 6565", "phone_e164": "+914061656565",
                                                              "address": "Road No. 1", "source": "https://example.org"})
    async def find_now():
        out = await h.execute(new.to_dict(), "find")
        await asyncio.gather(*h.background)                                           # the search runs in the background
        return out
    out = asyncio.run(find_now())
    found = store.cards()[0]["card"]
    assert out["ok"] and "about a minute" in out["message"]
    assert found["kind"] == "clinic" and "Phone: 040 6165 6565" in found["lines"]
    assert not any(c.get("phone") == "+914061656565" for c in hh["clinics"].values())     # nothing added before the tap
    added = asyncio.run(h.execute(found, "add"))
    text = yml.read_text(encoding="utf-8")
    assert "# a comment stays" in text and "+914061656565" in text and "care-hospitals-banjara-hills" in hh["clinics"]
    assert store.job(added["jobs"][0])["payload"]["to"] == "+914061656565"


def test_intake_call_asks_and_proposes_a_booking():
    from app.experts.health.expert import HealthExpert
    store = Store(":memory:")
    h = HealthExpert(store, HH)
    job = store.job(h.intake("me"))
    plan = h.call_plan(job)
    assert job["payload"]["to"] == HH["user"]["phone"] and "Never diagnose" in plan.instructions and "108" in plan.instructions
    t = {f.__name__: f for f in plan.tools}
    t["save_request"]("Amma", "BP review", "", "Dr. Rao", "", "2026-12-02", "2026-12-04", "evening", "")
    card = asyncio.run(h.after_call(job, plan.saved))
    assert card.kind == "bookreq" and card.payload["clinic"] == "rao" and card.payload["request"]["patient_key"] == "amma"


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


def test_age_checkups_and_elder_intake_watch_never_diagnose():
    from app.experts.family import checkups
    assert checkups.for_member({"age": 25}) == []
    amma = [c["what"] for c in checkups.for_member({"age": 66, "sex": "female"})]
    assert "Blood sugar check" in amma and "Cervical cancer screening" in amma and "Bone density (osteoporosis)" in amma
    assert "Bone density (osteoporosis)" not in [c["what"] for c in checkups.for_member({"age": 66, "sex": "male"})]
    assert all(c["source"] for c in checkups.for_member({"age": 66, "sex": "female"}))
    store = Store(":memory:")
    m = P.save(store, HH, "amma", {"age": 66, "sex": "female", "weight_kg": 58})
    assert checkups.watch(store, m) == []                                       # nothing logged: no conclusion
    now = time.time()
    for back in (1, 2):
        asyncio.run(pantry.log_meal(store, "1 idli", "", who="amma", estimate=meal(300, protein=6), now=now - back * 86400))
    notes = checkups.watch(store, m, now=now)
    assert len(notes) == 2 and "energy reference" in notes[0] and "good" not in " ".join(notes) + "bad"
    assert checkups.watch(store, P.save(store, HH, "me", {"age": 30}), now=now) == []   # only for 60+
    plan = HomeExpert(store, HH).call_plan(store.job(HomeExpert(store, HH).call("amma")))
    assert "Amma is 66: speak slowly" in plan.instructions and "The family noticed" in plan.instructions
    assert plan.max_minutes == 8


def test_plate_guard_flags_from_the_members_own_notes_only():
    from app.experts.family import guard

    class Run:
        def __init__(self):
            self.input = None

        async def __call__(self, agent, text, max_turns=1):
            self.input = text
            out = guard.Flags(flags=[guard.Flag(item="Haldiram Gulab Jamun 1 kg x1", who="Amma", note="doctor: sugar"),
                                     guard.Flag(item="Milk x1", who="Stranger", note="x")])
            return type("R", (), {"final_output": out})()
    store = Store(":memory:")
    plain = P.member(HH, store, "me")
    run = Run()
    assert asyncio.run(guard.check(["Milk x1"], [plain], runner=run)) == [] and run.input is None   # no notes, no call
    amma = P.save(store, HH, "amma", {"goal": "less_sugar", "conditions": "sugar"})
    flags = asyncio.run(guard.check(["Haldiram Gulab Jamun 1 kg x1", "Milk x1"], [amma, plain], runner=run))
    assert flags == [{"item": "Haldiram Gulab Jamun 1 kg x1", "who": "Amma", "note": "doctor: sugar"}]
    assert "Amma: less sugar; doctor: sugar" in run.input
    assert guard.warnings(flags)[0].endswith("You decide before approving.")
    plan = HomeExpert(store, HH).call_plan(store.job(HomeExpert(store, HH).call("amma")))
    assert "Their own notes: less sugar, doctor: sugar" in plan.instructions and "BEFORE adding it" in plan.instructions and "never as your own" in plan.instructions


def test_portions_plus_minus_and_fit_to_target():
    plan = {"days": [{"day": "Mon", "people": [{"who": "Nanna", "plate": "half rice"}], "meals": [
        {"slot": "lunch", "dish": "Rice, dal", "parts": [
            {"food": "Rice", "unit": "cup", "kcal": 200, "protein_g": 4, "carbs_g": 45, "fat_g": 0, "fibre_g": 1, "sugar_g": 0},
            {"food": "Dal", "unit": "katori", "kcal": 150, "protein_g": 9, "carbs_g": 20, "fat_g": 3, "fibre_g": 4, "sugar_g": 0}],
         "portions": [{"who": "Nanna (father, 62)", "qty": [1, 1]}, {"who": "Shiva", "qty": [2, 2]}]}]}], "ingredients": [], "notes": ""}
    pl.fill(plan)
    nanna = plan["days"][0]["people"][0]
    assert nanna["kcal"] == 350 and nanna["protein_g"] == 13 and plan["days"][0]["kcal"] == 525    # average plate
    pl.set_qty(plan, 0, 0, 0, "Nanna", 0.5)
    assert plan["days"][0]["people"][0]["kcal"] == 250 and plan["days"][0]["people"][0]["plate"] == "half rice"
    pl.fit(plan, 0, "Shiva", 1400)
    assert plan["days"][0]["meals"][0]["portions"][1]["qty"] == [4.0, 4.0]
    assert pl.plate_text(plan["days"][0], "Nanna") == "Rice 0.5 cup, Dal 1 katori"


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
    assert r.status_code == 200 and "Mifflin" in r.json()["targets"]["source"]
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
    assert nanna["today"]["total"]["kcal"] == 400 and "Mifflin" in nanna["today"]["targets"]["source"]
    assert nanna["health"]["score"] == 4 and nanna["health"]["label"] == "Room to grow" and fam["star"]
    assert c.post("/api/family/amma/call?via=browser").json()["job"]
    assert c.delete("/api/family/amma").status_code == 409 and c.delete("/api/family/nanna").json()["ok"]


def test_scan_wearable_dose_and_plan_api(client, monkeypatch):
    from app.experts.family import scan
    c, store = client
    photo = {"photo": ("x.jpg", b"jpg", "image/jpeg")}
    seen = {"kind": "meal", "note": "a plate", "medicines": [], "report": None,
            "meal": {"description": "2 rotis, 1 katori dal", "kcal": 420, "protein_g": 15, "carbs_g": 60, "fat_g": 10,
                     "fibre_g": 8, "sugar_g": 0}}
    monkeypatch.setattr(scan, "look", lambda image, mime, hint="": seen)
    r = c.post("/api/scan", data={"who": "amma"}, files=photo).json()
    assert r["kind"] == "meal" and r["entry"]["kcal"] == 420 and pantry.today(store, HH, "amma")["meals"][0]["text"] == "2 rotis, 1 katori dal"
    M.add(store, "amma", "Tab. Glycomet 500", "1", ["night"])
    seen.update(kind="medicine", medicines=[{"name_as_printed": "GLYCOMET 500 SR", "strength": "500 mg", "form": "tablet", "unclear": False}])
    r = c.post("/api/scan", data={"who": "amma"}, files=photo).json()
    assert r["matches"] == ["Tab. Glycomet 500"] and M.listed(store, "amma")[0]["name_as_written"] == "Tab. Glycomet 500"
    seen.update(kind="body_report", report={"date": "2026-11-20", "weight_kg": 58, "height_cm": None, "body_fat_pct": 31,
                                           "skeletal_muscle_kg": 20, "fat_mass_kg": 18, "bmr_kcal": 1210, "visceral_fat_level": 8})
    r = c.post("/api/scan", data={"who": "amma"}, files=photo).json()
    assert r["kind"] == "body_report" and P.profile(store, "amma").get("body") is None        # saved only on confirm
    v = c.put("/api/family/amma", json={"weight_kg": 58, "body": r["report"]}).json()
    assert v["body"]["bmr_kcal"] == 1210 and "BMR from the body composition report" in v["targets"]["source"]
    assert c.post("/api/family/amma/dose", json={"slot": "night", "taken": "yes"}).json()["doses"][0]["taken"] == "yes"
    assert c.post("/api/family/amma/dose", json={"slot": "noon"}).status_code == 400
    base = c.get("/api/family").json()["members"][1]["today"]["targets"]["kcal"]
    assert c.post("/api/activity/amma", json={"steps": 8000, "active_kcal": 250, "source": "Apple Watch"}).json()["ok"]
    amma = c.get("/api/family").json()["members"][1]
    assert amma["activity"]["steps"] == 8000 and amma["today"]["targets"]["kcal"] == base + 250
    assert "Apple Watch" in amma["today"]["targets"]["source"]
    assert any(p["part"] == "movement" and p["percent"] == 100 for p in amma["health"]["parts"])
    assert c.post("/api/kitchen/mealplan/fit", json={"day": 0, "who": "Amma"}).status_code == 409   # no plan yet


def test_photo_time_sets_the_meal_photos_are_kept_and_unclear_prescription_lines_wait_for_a_check(client, monkeypatch,
                                                                                                    tmp_path):
    from datetime import datetime
    from app.experts.family import scan
    from app.experts.health import rx as R
    c, store = client
    monkeypatch.setenv("PHOTOS_DIR", str(tmp_path))
    seen = {"kind": "meal", "note": "a plate", "medicines": [], "report": None,
            "meal": {"description": "2 idli, sambar", "kcal": 300, "protein_g": 9, "carbs_g": 50, "fat_g": 6,
                     "fibre_g": 4, "sugar_g": 0}}
    monkeypatch.setattr(scan, "look", lambda image, mime, hint="": seen)
    yesterday_8am = datetime.now(M.IST).replace(hour=8, minute=15, second=0, microsecond=0).timestamp() - 86400
    r = c.post("/api/scan", data={"who": "amma", "taken": str(int(yesterday_8am * 1000))},
               files={"photo": ("x.jpg", b"jpeg bytes", "image/jpeg")}).json()
    assert r["entry"]["meal"] == "breakfast" and r["entry"]["ts"] == yesterday_8am and r["entry"]["photo"] == r["photo"]
    assert r["entry"]["id"].startswith(f"meal:{pantry.today_key(yesterday_8am)}:")     # on the day it was eaten
    assert c.get(f"/api/photos/{r['photo']}").content == b"jpeg bytes" and c.get("/api/photos/..%2Fx").status_code == 404
    assert c.put("/api/kitchen/meal", json={"who": "amma", "id": r["entry"]["id"], "meal": "lunch"}).json()["meal"] == "lunch"
    assert c.put("/api/kitchen/meal", json={"who": "amma", "id": r["entry"]["id"], "meal": "brunch"}).status_code == 400
    old = c.post("/api/scan", data={"who": "amma", "taken": "1000"}, files={"photo": ("x.jpg", b"j", "image/jpeg")}).json()
    assert abs(old["entry"]["ts"] - time.time()) < 60                                    # an old photo counts as now

    seen.update(kind="prescription")
    monkeypatch.setattr(R, "read_prescription", lambda image, mime: {
        "doctor": "Dr. Rao", "date": None, "review_after_days": None, "unreadable_parts": [], "advice_as_written": [],
        "meds": [{"name_as_written": "Simvotin 10mg", "strength": None, "dose": "one", "morning": False, "afternoon": False,
                  "night": False, "food": None, "days": None, "unclear": True}]})
    r = c.post("/api/scan", data={"who": "amma"}, files={"photo": ("rx.jpg", b"rx", "image/jpeg")}).json()
    card = store.card(r["card"])
    assert card["card"]["payload"]["photo"] == r["photo"] and r["count"] == 1
    out = c.post(f"/api/cards/{r['card']}/tap", json={"choice": "confirm"}).json()["result"]
    assert "1 need a check" in out["message"]
    med = c.get("/api/family").json()["members"][1]["meds"][0]
    assert med["name_as_written"] == "Simvotin 10mg" and med["unclear"] and med["photo"] == r["photo"]   # kept as written
    assert M.today(store, "amma") == []                                                    # but never read out yet
    health = c.app.state.experts["health"]
    assert health.meds("amma") == []                                                       # nor on a check-in call
    assert c.post("/api/health/pharmacy", json={"who": "amma", "area": "Madhapur"}).status_code == 400  # nor to a pharmacy
    assert c.put("/api/family/amma/meds/0", json={"times": []}).status_code == 400
    amma = c.put("/api/family/amma/meds/0", json={"times": ["night"]}).json()
    assert not amma["meds"][0]["unclear"] and amma["doses"][0]["meds"] == ["Simvotin 10mg one"]
    assert [m["name_as_written"] for m in health.meds("amma")] == ["Simvotin 10mg"]
    r = c.post("/api/scan", data={"who": "amma"}, files={"photo": ("rx.jpg", b"rx2", "image/jpeg")}).json()
    assert c.get(f"/api/photos/{r['photo']}").status_code == 200
    assert c.post(f"/api/cards/{r['card']}/reject").json()["ok"]
    assert c.get(f"/api/photos/{r['photo']}").status_code == 404                          # skipped: photo deleted
    r = c.post("/api/scan", data={"who": "amma"}, files={"photo": ("rx.jpg", b"rx3", "image/jpeg")}).json()
    c.post(f"/api/cards/{r['card']}/tap", json={"choice": "discard"})
    assert c.get(f"/api/photos/{r['photo']}").status_code == 404                          # discarded: deleted too
    seen.update(kind="medicine", medicines=[{"name_as_printed": "X", "strength": None, "form": None, "unclear": False}])
    assert "photo" not in c.post("/api/scan", data={"who": "amma"}, files={"photo": ("s.jpg", b"s", "image/jpeg")}).json()


def test_a_household_with_no_doctor_yet_still_works():
    from app.concierge import make_concierge
    from app.experts.health.expert import HealthExpert
    hh = {**HH, "clinics": {}, "people": {k: {kk: vv for kk, vv in v.items() if kk != "clinic"} for k, v in HH["people"].items()}}
    store = Store(":memory:")
    h = HealthExpert(store, hh)
    agent = make_concierge(store, hh, None, h)
    assert "book_doctor" not in [t.name for t in agent.tools] and "none saved yet" in agent.instructions
    follow = {"expert": "health", "kind": "followup", "title": "Review due", "lines": [], "choices": [],
              "payload": {"patient": "amma", "doctor": "Dr. X", "after_days": 14}}
    out = asyncio.run(h.execute(follow, "book"))
    assert out["ok"] is False and "Add a doctor" in out["error"]
    store.remember("amma", "checkin:j1", {"feeling": "ok", "her_words": "baagunnanu", "summary_en": "fine"}, "t")
    brief = h.brief_card("amma")
    assert brief.payload["wa"].startswith("https://wa.me/?text=") and brief.payload["consult"]["name"] == "PharmEasy"
