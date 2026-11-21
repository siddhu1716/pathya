"""Editing household.yaml from the app, the WhatsApp report, and hang-up / decline from the app."""
import asyncio
import os
import sys

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
