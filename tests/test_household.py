"""Editing household.yaml from the app, the WhatsApp report, and hang-up / decline from the app."""
import asyncio
import os
import sys
import time

import pytest
import yaml
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.household import normalize, set_phone
from app.experts.family import profiles as P
from tests.test_home import env

YAML = """# Who Pathya works for.
user:
  name: Shiva
  phone: "+919800000000"   # my own phone
people:
  amma:
    name: Amma
    phone: "+919800000001"
  lakshmi:
    name: Lakshmi garu
    role: cook
    phone: "+919800000002"
clinics:
  rao:
    doctor: Dr. Rao
    clinic: Sunrise Clinic
    phone: "+919800000003"
"""


def test_normalize_numbers():
    assert normalize("098480 22338") == "+919848022338" and normalize("+91-98480-22338") == "+919848022338"
    assert normalize("9848022338") == "+919848022338" and normalize("+1 (415) 555-0100") == "+14155550100"
    assert normalize("12345") == "" and normalize("1234567890") == ""          # Indian mobiles start 6-9


def test_set_phone_keeps_comments_and_adds_people(tmp_path):
    path = tmp_path / "household.yaml"
    path.write_text(YAML, encoding="utf-8")
    hh = yaml.safe_load(YAML)
    set_phone(path, hh, "me", "+91 70000 11111")
    set_phone(path, hh, "amma", "07000022222")
    set_phone(path, hh, "nanna", "9000033333", "Nanna", "father")
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert "# my own phone" in text and "# Who Pathya works for." in text
    assert data["user"]["phone"] == "+917000011111" == hh["user"]["phone"]
    assert data["people"]["amma"]["phone"] == "+917000022222" and data["people"]["lakshmi"]["role"] == "cook"
    assert data["people"]["nanna"] == {"name": "Nanna", "relation": "father", "phone": "+919000033333"} == hh["people"]["nanna"]
    assert data["clinics"]["rao"]["phone"] == "+919800000003"
    with pytest.raises(ValueError):
        set_phone(path, hh, "amma", "abc")


def test_phone_from_the_app_report_and_call_buttons(tmp_path, monkeypatch):
    app, store, _ = env()
    path = tmp_path / "household.yaml"
    path.write_text(YAML, encoding="utf-8")
    app.state.household = hh = yaml.safe_load(YAML)
    for e in app.state.experts.values():
        e.hh = hh
    app.state.household_path = str(path)
    with TestClient(app) as c:
        c.post("/api/family", json={"name": "Nanna", "relation": "father"})
        assert c.post("/api/family/nanna/call").status_code == 400                   # no phone yet
        v = c.put("/api/family/nanna/phone", json={"phone": "90000 33333"}).json()
        assert v["has_phone"] and v["phone_hint"] == "…3333" and "phone" not in v
        assert "+919000033333" in path.read_text(encoding="utf-8")
        assert c.post("/api/family/nanna/call?via=browser").json()["job"]            # now Pathya can call him
        assert c.put("/api/family/nanna/phone", json={"phone": "1"}).status_code == 400
        r = c.get("/api/family/amma/report").json()
        assert r["text"].startswith("*Pathya report: Amma") and "not a medical test" in r["text"]
        assert r["wa"].startswith("https://wa.me/?text=") and r["safety"] == "unchecked"
        jid = app.state.experts["home"].call_me(via="browser")
        store.start_job(jid)
        store.end_job(jid, True, {"call_sid": "browser"})
        assert [j["id"] for j in c.get("/api/state").json()["ringing"]] == [jid]
        assert c.post(f"/api/calls/{jid}/decline").json()["ok"]
        assert c.get("/api/state").json()["ringing"] == []                          # declined: stops ringing
        assert c.post(f"/api/calls/{jid}/hangup").status_code == 409                # not live
        closed = []

        async def close():
            closed.append(True)
        app.state.live[jid] = {"who": "Shiva", "lines": []}
        app.state.hangups[jid] = close
        assert c.post(f"/api/calls/{jid}/hangup").json()["ok"] and closed == [True]


def test_pharmacy_found_near_you_is_added_only_after_a_tap_and_the_call_never_orders(tmp_path, monkeypatch):
    import asyncio
    from app.experts.family import meds as M
    from app.experts.health import pharmacy
    app, store, _ = env()
    path = tmp_path / "household.yaml"
    path.write_text(YAML + "pharmacies: {}\n", encoding="utf-8")
    app.state.household = hh = yaml.safe_load(path.read_text(encoding="utf-8"))
    for e in app.state.experts.values():
        e.hh = hh
    health = app.state.experts["health"]
    health.path = str(path)
    M.add(store, "amma", "Tab. Simvotin 10mg", "1", ["night"])
    seen = {}

    def find(lat, lng, area, city):
        seen.update(lat=lat, lng=lng, area=area)
        return {"area": "Madhapur", "pharmacies": [
            {"name": "Apollo Pharmacy Madhapur", "phone": "040 2311 2345", "phone_e164": "+914023112345",
             "address": "Ayyappa Society", "delivers": True, "source": "https://www.apollopharmacy.in/"}]}
    monkeypatch.setattr(pharmacy, "find", find)
    with TestClient(app) as c:
        assert c.post("/api/health/pharmacy", json={"who": "amma"}).status_code == 400          # no location, no area
        assert c.post("/api/health/pharmacy", json={"who": "me", "area": "Madhapur"}).status_code == 400   # no medicines
        r = c.post("/api/health/pharmacy", json={"who": "amma", "lat": 17.4486, "lng": 78.3908}).json()
        assert r == {"searching": True, "medicines": 1}
        for _ in range(50):                                                                     # found in the background
            found = [x for x in store.cards() if x["card"]["kind"] == "pharmacies"]
            if found:
                break
            time.sleep(0.1)
        assert seen["lat"] == 17.4486 and found and "Apollo Pharmacy Madhapur" in found[0]["card"]["lines"][0]
        r["card"] = found[0]["id"]
        assert "apollo" not in path.read_text(encoding="utf-8").lower()                          # nothing added yet
        links = c.get("/api/health/pharmacy/links?who=amma").json()
        assert [a["name"] for a in links["apps"]] == ["Tata 1mg", "Apollo 24|7", "PharmEasy"]   # one link each, for all
        assert links["list"] == "Simvotin 10mg"
        out = c.post(f"/api/cards/{r['card']}/tap", json={"choice": "call:0"}).json()["result"]
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["pharmacies"]["apollo-pharmacy-madhapur"]["phone"] == "+914023112345"       # rule 8: listed first
        assert "# Who Pathya works for." in path.read_text(encoding="utf-8")
    job = store.job(out["jobs"][0])
    assert job["kind"] == "pharmacy" and job["payload"]["to"] == "+914023112345" and job["payload"]["meds"] == ["Tab. Simvotin 10mg 1"]
    plan = health.call_plan(job)
    assert "Do not place the order" in plan.instructions and "Tab. Simvotin 10mg 1" in plan.instructions
    tools = {f.__name__: f for f in plan.tools}
    tools["save_answer"](["Tab. Simvotin 10mg"], [], ["Simcard 10"], "Rs 180", True, "2 hours", "98480 22338", "")
    card = asyncio.run(health.after_call(job, plan.saved))
    assert card.kind == "pharmacy_answer" and "1 of 1 available" in card.title
    assert any("not accepted" in l and "Simcard 10" in l for l in card.lines)
    assert card.payload["wa"].startswith("https://wa.me/919848022338?text=") and "Simvotin" in card.payload["share_text"]
    assert card.payload["safety"] == "unchecked"                                                # passed safety.check
    assert pharmacy.add_to_household(str(path), hh, {"name": "Apollo again", "phone_e164": "+914023112345"}) == \
        "apollo-pharmacy-madhapur"                                                                  # same number: reused


def test_family_adds_a_doctor_profile_and_books_from_it(tmp_path):
    app, store, _ = env()
    path = tmp_path / "household.yaml"
    path.write_text(YAML, encoding="utf-8")
    app.state.household = hh = yaml.safe_load(YAML)
    hh["people"]["amma"]["clinic"] = "rao"
    for e in app.state.experts.values():
        e.hh = hh
    app.state.household_path = str(path)
    with TestClient(app) as c:
        d = c.get("/api/doctors").json()
        assert d["saved"][0]["sees"] == ["Amma"] and d["saved"][0]["phone_hint"] == "…0003" and "phone" not in d["saved"][0]
        assert {o["name"] for o in d["online"]} == {"PharmEasy", "Apollo 24|7"} and "Diabetologist" in d["specialties"]
        assert c.post("/api/doctors", json={"doctor": "Dr. Meera", "clinic": "Care", "phone": "12"}).status_code == 400
        new = c.post("/api/doctors", json={"doctor": "Dr. Meera Rao", "clinic": "Care Clinic, Madhapur",
                                          "phone": "040 2311 2345", "specialty": "Diabetologist"}).json()
        assert new["specialty"] == "Diabetologist" and new["phone_hint"] == "…2345"
        saved = yaml.safe_load(path.read_text(encoding="utf-8"))["clinics"][new["key"]]
        assert saved == {"doctor": "Dr. Meera Rao", "clinic": "Care Clinic, Madhapur", "phone": "+914023112345",
                         "specialty": "Diabetologist"}                                          # rule 8: listed first
        assert any(x["specialty"] == "Diabetologist" for x in c.get("/api/state").json()["clinics"])
        job = c.post("/api/health/book", json={"patient": "amma", "clinic": new["key"], "window_start": "2026-12-01T00:00",
                                               "window_end": "2026-12-03T23:59", "part": "morning", "reason": "sugar review"}).json()
        assert store.job(job["job"])["payload"]["to"] == "+914023112345"
