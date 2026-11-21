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

    def answered(self, person, call_sid):
        jid = self.store.add_job(self.name, "list", person, {"person": person, "direction": "inbound"}, 4102444800)
        self.store.start_job(jid)
        self.store.end_job(jid, True, {"call_sid": call_sid})
        return jid


@pytest.fixture
def env():
    from app.experts.doorstep.expert import DoorstepExpert
    store = Store(":memory:")
    app = build_app()
    kitchen = FakeKitchen(store)
    app.state.store, app.state.household = store, HH
    app.state.experts = {"kitchen": kitchen, "health": HealthExpert(store, HH), "doorstep": DoorstepExpert(store, HH)}
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


def test_exotel_stream_needs_secret_and_routes_caller(env, monkeypatch):
    import base64
    import app.core.call_session as cs
    from starlette.websockets import WebSocketDisconnect
    client, store, _ = env
    monkeypatch.setenv("EXOTEL_STREAM_SECRET", "s" * 32)
    bad = {"Authorization": "Basic " + base64.b64encode(b"quickpick:wrong").decode()}
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/exotel", headers=bad) as ws:
            ws.receive_text()
    seen = {}

    async def fake_bridge(ws, call_for_start, finish, hang_up, log, transcript=None, carrier=None):
        import json as _j
        msg = _j.loads(await ws.receive_text())
        call = call_for_start(msg)
        seen["job"] = call.job
        await finish(call, [{"role": "them", "text": "hello"}])
    monkeypatch.setattr(cs, "phone_bridge", fake_bridge)
    from app.experts.kitchen.expert import KitchenExpert
    client.app.state.experts["kitchen"] = KitchenExpert(store, HH, None, object())
    good = {"Authorization": "Basic " + base64.b64encode(("quickpick:" + "s" * 32).encode()).decode()}
    with client.websocket_connect("/exotel", headers=good) as ws:
        ws.send_text(json.dumps({"event": "start", "stream_sid": "S1",
                                 "start": {"stream_sid": "S1", "call_sid": "X7", "from": "09800000001"}}))
    assert seen["job"]["expert"] == "kitchen" and seen["job"]["person"] == "amma"     # 0-prefixed Indian number
    assert store.facts("amma", f"call:{seen['job']['id']}")


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


def test_tap_records_orders_and_tracker_logs_changes(env):
    import asyncio
    from app.core import tracker
    client, store, _ = env
    aid = client.post("/api/kitchen/plan", json={"text": "2 milk"}).json()["card"]
    client.post(f"/api/cards/{aid}/tap", json={"choice": "COD"})
    assert client.get("/api/orders").json() == []                       # the fake order came back without an id
    tracker.record(store, "c1", {"lines": ["Milk x2"], "total": "₹99", "address": "Loft",
                                 "payload": {"address_id": "a1"}}, {"order": {"orderId": "O1"}, "eta": {"O1": "12 mins"}})
    tracker.record(store, "c2", {"lines": [], "payload": {}}, {"dry_run": True})
    assert [o["id"] for o in store.orders(active=True)] == ["O1"]       # dry runs are never tracked

    class K:
        def __init__(self, answers): self.answers = answers
        async def track(self, o):
            a = self.answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a
    changed = asyncio.run(tracker.tick(store, K([("Out for delivery", "5 mins", {}, False)])))
    assert changed == ["O1"] and store.order("O1")["eta"] == "5 mins"
    state = {}
    assert asyncio.run(tracker.tick(store, K([RuntimeError("HTTP 429 Too Many Requests")]), state=state)) == []
    assert asyncio.run(tracker.tick(store, K([]), state=state)) == []   # paused: no calls at all
    asyncio.run(tracker.tick(store, K([("Delivered", None, {}, True)]), now=state["paused_until"] + 1))
    assert store.orders(active=True) == [] and any("Delivered" in e["what"] for e in store.timeline(ref="O1"))
    assert client.get("/api/state").json()["orders"][0]["id"] in ("O1", "dry-c2")


def test_incoming_calls_route_by_caller_and_need_twilio_signature(env, monkeypatch):
    from twilio.request_validator import RequestValidator
    client, store, _ = env
    monkeypatch.setenv("PUBLIC_HOST", "abc.trycloudflare.com")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "t" * 32)
    client.app.state.twilio = object()
    url = "https://abc.trycloudflare.com/calls/incoming"

    def ring(frm, sid, signed=True):
        form = {"From": frm, "CallSid": sid, "To": "+16180000000"}
        sig = RequestValidator("t" * 32).compute_signature(url, form) if signed else "bad"
        return client.post("/calls/incoming", data=form, headers={"X-Twilio-Signature": sig})

    assert ring("+919800000001", "CA1", signed=False).status_code == 403
    r = ring("+91 98000 00001", "CA1")                                  # Amma, formatted differently
    assert r.status_code == 200 and "<Stream" in r.text
    amma = [j for j in store.recent_jobs(0) if j["result"] == {"call_sid": "CA1"}][0]
    assert amma["expert"] == "kitchen" and amma["person"] == "amma" and amma["payload"]["direction"] == "inbound"
    ring("+918888812345", "CA2")                                        # unknown: the delivery partner
    door = [j for j in store.recent_jobs(0) if j["result"] == {"call_sid": "CA2"}][0]
    assert door["expert"] == "doorstep" and door["payload"]["caller"] == "…2345"
    assert store.upcoming() == []                                       # answered calls are never dialled


def test_doorstep_guides_without_ids_or_otp(env):
    import asyncio
    client, store, _ = env
    d = client.app.state.experts["doorstep"]
    store.add_order("254220219978762", "swiggy", "c1", None, ["Milk x2", "Curd x1"], "₹149", "Loft", "a1", "Out for delivery", "5 mins")
    plan = d.call_plan(store.job(d.answered("CA9", "1234")))
    assert plan.greeting.startswith("Hello, I am QuickPick, an AI assistant")
    assert "254220219978762" not in plan.instructions and "2 item(s)" in plan.instructions
    assert "Never share an OTP" in plan.instructions
    tools = {f.__name__: f for f in plan.tools}
    tools["notify_owner"]("Partner is at the security desk")
    assert store.cards()[0]["card"]["kind"] == "alert"
    tools["end_call"]("Guided the partner to the 3rd floor")
    assert asyncio.run(d.after_call(store.job(d.answered("CA10", "1234")), plan.saved)).lines[0].startswith("Guided")


def test_live_transcript_and_call_history(env, monkeypatch):
    import app.core.browser_call as bc
    client, store, kitchen = env

    async def fake_answer(offer, config, **kw):
        return "v=0 answer"
    monkeypatch.setattr(bc, "answer_sdp", fake_answer)
    jid = kitchen.weekly_call("lakshmi")
    store.start_job(jid)
    store.end_job(jid, True, {"call_sid": "browser"})
    from app.experts.kitchen.expert import KitchenExpert
    client.app.state.experts["kitchen"] = KitchenExpert(store, HH, None, object())
    client.post(f"/api/calls/{jid}/sdp", content="v=0 offer")
    client.post(f"/api/calls/{jid}/line", json={"role": "them", "text": "rendu litres paalu"})
    live = client.get("/api/state").json()["live"]
    assert live[0]["who"] == "Lakshmi garu" and live[0]["lines"][-1]["text"] == "rendu litres paalu"
    client.post(f"/api/calls/{jid}/end", json={"transcript": [{"role": "them", "text": "rendu litres paalu"}]})
    assert client.get("/api/state").json()["live"] == []
    hist = client.get("/api/calls").json()
    assert hist[0]["who"] == "Lakshmi garu" and hist[0]["transcript"][0]["text"] == "rendu litres paalu"
