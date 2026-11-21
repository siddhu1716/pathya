"""API checks for app/main.py with stand-in Experts (no Swiggy, no calls, no real orders)."""
import json
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.store import Store
from app.experts.base import Card, Expert
from app.experts.health.expert import HealthExpert
from app.main import build_app

HH = {"user": {"name": "Shiva", "phone": "+919800000000"},
      "people": {"amma": {"name": "Amma", "language": "Telugu", "phone": "+919800000001", "age": 60, "clinic": "rao"},
                 "lakshmi": {"name": "Lakshmi garu", "role": "cook", "phone": "+919800000002"}},
      "clinics": {"rao": {"doctor": "Dr. Rao", "clinic": "Sunrise Clinic", "phone": "+919800000003"}}}


class FakeKitchen(Expert):
    name, title, call_kinds = "kitchen", "Kitchen Expert", {"list"}

    def __init__(self, store, connected=True):
        self.store, self.ops, self.executed = store, (object() if connected else None), []

    async def handle(self, text):
        return Card("kitchen", "order", "Swiggy Instamart cart", [text], total="₹99", address="Loft",
                    question="Do you want to proceed with placing this order to this address?",
                    choices=[{"id": "COD", "label": "Cash"}, {"id": "UPI:gpay", "label": "UPI - Google Pay"}],
                    payload={"address_id": "a1", "approved_total": 99})

    async def execute(self, card, choice):
        self.executed.append(choice)
        if choice == "boom":
            raise RuntimeError("checkout failed")
        if choice.startswith("UPI"):
            return {"ok": True, "pay_url": "https://pay.example", "order": {"orderId": "O2"}}
        return {"ok": True, "message": "Instamart order placed successfully"}

    async def settle(self, order):
        return True, "Instamart order placed successfully"

    async def etas(self, order, address_id):
        return {"O2": "12 mins"}

    def weekly_call(self, person):
        return self.store.add_job(self.name, "list", person, {"person": person, "to": "+919800000002"})


@pytest.fixture
def env():
    store = Store(":memory:")
    app = build_app()
    kitchen = FakeKitchen(store)
    app.state.store, app.state.household = store, HH
    app.state.experts = {"kitchen": kitchen, "health": HealthExpert(store, HH)}
    with TestClient(app) as client:
        yield client, store, kitchen


def test_tap_runs_once_and_validates_choice(env):
    client, store, kitchen = env
    aid = client.post("/api/kitchen/plan", json={"text": "2 milk"}).json()["card"]
    assert client.post(f"/api/cards/{aid}/tap", json={"choice": "SwiggyPay"}).status_code == 400
    assert client.post(f"/api/cards/{aid}/tap", json={"choice": "COD"}).json()["status"] == "done"
    second = client.post(f"/api/cards/{aid}/tap", json={"choice": "COD"}).json()
    assert second["status"] == "done" and kitchen.executed == ["COD"]
    assert second["result"]["message"] == "Instamart order placed successfully"
    assert client.post(f"/api/cards/{aid}/reject").status_code == 409


def test_failed_execute_never_reopens(env):
    client, store, kitchen = env
    aid = store.add_card(Card("kitchen", "order", "Cart", ["x"], choices=[{"id": "boom", "label": "Go"}]).to_dict())
    row = client.post(f"/api/cards/{aid}/tap", json={"choice": "boom"}).json()
    assert row["status"] == "failed" and "checkout failed" in row["result"]["error"]
    client.post(f"/api/cards/{aid}/tap", json={"choice": "boom"})
    assert kitchen.executed == ["boom"]


def test_upi_waits_for_payment_then_finishes(env):
    client, store, kitchen = env
    aid = client.post("/api/kitchen/plan", json={"text": "curd"}).json()["card"]
    row = client.post(f"/api/cards/{aid}/tap", json={"choice": "UPI:gpay"}).json()
    assert row["result"]["pay_url"] == "https://pay.example"
    for _ in range(50):
        row = client.get(f"/api/cards/{aid}").json()
        if row["status"] != "running":
            break
        time.sleep(0.05)
    assert row["status"] == "done" and row["result"]["paid"] and row["result"]["eta"] == {"O2": "12 mins"}


def test_calls_only_household_people_and_run_now(env):
    client, store, _ = env
    assert client.post("/api/kitchen/call/stranger").status_code == 404
    jid = store.add_job("kitchen", "list", "lakshmi", {"person": "lakshmi", "to": "+919800000002"},
                        time.time() + 3600)
    assert client.post(f"/api/jobs/{jid}/run-now").json()["ok"]
    assert client.post("/api/jobs/nope/run-now").status_code == 409


def test_state_alerts_first_and_browser_ringing(env):
    client, store, _ = env
    store.add_card(Card("kitchen", "order", "Cart", ["x"]).to_dict())
    store.add_card(Card("health", "alert", "Urgent: Amma needs you", ["faint"]).to_dict())
    jid = store.add_job("kitchen", "list", "lakshmi", {"person": "lakshmi"}, time.time())
    store.start_job(jid)
    store.end_job(jid, True, {"call_sid": "browser"})
    bad = store.add_job("kitchen", "list", "amma", {"person": "amma"}, time.time())   # failed jobs store a string
    store.start_job(bad)
    store.end_job(bad, False, "dial failed")
    s = client.get("/api/state").json()
    assert s["cards"][0]["card"]["kind"] == "alert" and s["dry_run"] in (True, False)
    assert [j["id"] for j in s["ringing"]] == [jid]
    store.remember("lakshmi", f"call:{jid}", {"transcript": []}, "call")
    assert client.get("/api/state").json()["ringing"] == []


def test_twilio_only_when_opted_in_with_real_settings(monkeypatch):
    from app.main import twilio_ready
    example = {"TWILIO_ACCOUNT_SID": "AC...", "TWILIO_AUTH_TOKEN": "...", "TWILIO_FROM": "+1...",
               "PUBLIC_HOST": "xxxx.ngrok-free.app"}
    real = {"TWILIO_ACCOUNT_SID": "AC" + "a" * 32, "TWILIO_AUTH_TOKEN": "b" * 32, "TWILIO_FROM": "+15550001111",
            "PUBLIC_HOST": "abcd.ngrok-free.app"}
    for k, v in {**example, "CALL_MODE": "twilio"}.items():
        monkeypatch.setenv(k, v)
    assert not twilio_ready()                                   # .env.example placeholders never dial
    for k, v in real.items():
        monkeypatch.setenv(k, v)
    assert twilio_ready()
    monkeypatch.setenv("CALL_MODE", "browser")
    assert not twilio_ready()


def test_kitchen_503_when_swiggy_not_connected(env):
    client, store, _ = env
    client.app.state.experts["kitchen"] = FakeKitchen(store, connected=False)
    assert client.post("/api/kitchen/plan", json={"text": "milk"}).status_code == 503


def test_health_book_and_ics(env):
    client, store, _ = env
    body = {"patient": "amma", "clinic": "rao", "window_start": "2026-11-23T00:00",
            "window_end": "2026-11-27T00:00", "part": "morning", "reason": "BP review"}
    jid = client.post("/api/health/book", json=body).json()["job"]
    assert store.job(jid)["payload"]["to"] == "+919800000003"
    assert client.post("/api/health/book", json={**body, "clinic": "other"}).status_code == 404
    aid = store.add_card(Card("health", "booking", "Booked", ["x"], payload={"ics": "BEGIN:VCALENDAR"}).to_dict())
    r = client.get(f"/api/cards/{aid}/ics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert client.get("/api/nope").status_code == 404


def test_browser_call_runs_expert_tools_and_makes_card(env, monkeypatch):
    from datetime import datetime, timedelta
    import app.core.browser_call as bc
    client, store, _ = env
    seen = {}

    async def fake_answer(offer, config, **kw):
        seen["config"] = config
        return "v=0 answer"
    monkeypatch.setattr(bc, "answer_sdp", fake_answer)

    base = (datetime.now() + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    jid = client.post("/api/health/book", json={
        "patient": "amma", "clinic": "rao", "window_start": base.isoformat(),
        "window_end": (base + timedelta(days=3)).isoformat(), "part": "morning", "reason": "BP review"}).json()["job"]
    assert client.post(f"/api/calls/{jid}/tool", json={"name": "end_call"}).status_code == 409   # not answered yet
    assert client.post(f"/api/calls/{jid}/sdp", content="v=0 offer",
                       headers={"Content-Type": "application/sdp"}).text == "v=0 answer"
    cfg = seen["config"]
    assert "AI assistant" in cfg["instructions"] and {t["name"] for t in cfg["tools"]} >= {"book_slot", "end_call"}
    assert "Hello, I am QuickPick" in client.get(f"/api/calls/{jid}/greeting").json()["greeting"]

    late = (base + timedelta(days=1)).replace(hour=16).strftime("%Y-%m-%dT%H:%M")
    good = (base + timedelta(days=1)).replace(hour=10, minute=30).strftime("%Y-%m-%dT%H:%M")
    tool = lambda name, **a: client.post(f"/api/calls/{jid}/tool", json={"name": name, "arguments": json.dumps(a)}).json()
    assert tool("book_slot", slot=late, doctor="", fee="", bring="")["output"].startswith("Refused")
    assert any("Refused" in e["what"] for e in store.timeline(ref=jid))          # visible on the timeline
    assert tool("book_slot", slot=good, doctor="Dr. Rao", fee="Rs 500", bring="reports")["output"].startswith("Booked")
    assert tool("end_call", summary="Booked 10:30")["end"] is True
    assert client.post(f"/api/calls/{jid}/end", json={"transcript": [{"role": "ai", "text": "hi"}]}).json()["ok"]
    for _ in range(50):
        if any(c["card"]["kind"] == "booking" for c in store.cards()):
            break
        time.sleep(0.05)
    assert any(c["card"]["kind"] == "booking" for c in store.cards())
    assert store.facts("rao", f"call:{jid}")[0]["value"]["transcript"][0]["text"] == "hi"
    assert client.post(f"/api/calls/{jid}/sdp", content="v=0 offer").status_code == 409     # one answer per call
