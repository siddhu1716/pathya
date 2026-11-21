"""Home line, pantry and food log: the user's own calls, what is at home, today's meals, the app key."""
import asyncio
import os
import sys
import time

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import tracker
from app.core.store import Store
from app.experts.base import Card
from app.experts.home.expert import HomeExpert
from app.experts.kitchen import pantry
from app.main import build_app
from tests.test_api import HH, FakeKitchen


def test_pantry_shelf_life_running_low_and_used_up():
    store = Store(":memory:")
    now = time.time()
    pantry.stock(store, ["Arokya Toned Milk 500 ml x2 - Rs 64", "Tata Toor Dal 1 kg x1 - Rs 180",
                         "Fresh Veggies Mix x1"], "swiggy", "O1", when=now - 2 * 86400)
    shelf = {i["name"]: i for i in pantry.items(store, now)}
    assert shelf["Arokya Toned Milk 500 ml"]["low"] and shelf["Arokya Toned Milk 500 ml"]["qty"] == 2   # 2-day item
    assert not shelf["Tata Toor Dal 1 kg"]["low"] and shelf["Fresh Veggies Mix"]["days"] == 5         # not "egg"
    assert pantry.items(store, now)[0]["low"]                                                          # low first
    assert pantry.reorder_line(shelf["Arokya Toned Milk 500 ml"]) == "2 x Arokya Toned Milk 500 ml"
    assert pantry.used_up(store, ["toor dal"]) == ["Tata Toor Dal 1 kg"]
    assert len(pantry.items(store)) == 2


def test_delivery_stocks_the_pantry_once_and_dry_runs_too():
    store = Store(":memory:")
    tracker.record(store, "c1", {"lines": ["Curd 500 g x1"], "total": "₹52", "payload": {"address_id": "a"}},
                   {"order": {"orderId": "O9"}})
    assert pantry.items(store) == []                                   # placed, not delivered yet
    assert tracker.mark_delivered(store, "O9") and not tracker.mark_delivered(store, "O9")
    assert [i["name"] for i in pantry.items(store)] == ["Curd 500 g"] and store.order("O9")["delivered"]
    tracker.record(store, "c2", {"lines": ["Bread x1"], "payload": {}}, {"dry_run": True})
    assert {i["name"] for i in pantry.items(store)} == {"Curd 500 g", "Bread"}


def test_food_log_today():
    store = Store(":memory:")

    async def fake(text):
        return {"kcal": 450, "protein_g": 14.0, "carbs_g": 70.0, "fat_g": 10.0, "fibre_g": 6.0}
    asyncio.run(pantry.log_meal(store, "2 idli, sambar", "breakfast", estimate=fake))
    asyncio.run(pantry.log_meal(store, "rice, pappu, perugu", "lunch", estimate=fake))
    t = pantry.today(store, HH)
    assert t["total"]["kcal"] == 900 and len(t["meals"]) == 2 and t["targets"]["kcal"] == 1885


def env(monkeypatch=None):
    from app.experts.doorstep.expert import DoorstepExpert
    from app.experts.health.expert import HealthExpert
    store = Store(":memory:")
    app = build_app()
    kitchen = FakeKitchen(store)
    app.state.store, app.state.household = store, HH
    app.state.experts = {"kitchen": kitchen, "health": HealthExpert(store, HH), "doorstep": DoorstepExpert(store, HH),
                         "home": HomeExpert(store, HH, kitchen)}
    return app, store, kitchen


def test_my_number_gets_the_home_line_in_telugu_and_a_cart_after(monkeypatch):
    from app.main import _answer_incoming
    app, store, kitchen = env()
    seen = []

    async def handle(text, ref=None, who=None):
        seen.append(text)
        return Card("kitchen", "order", "Swiggy Instamart cart", [text])
    kitchen.handle = handle

    async def fake(text):
        return {"kcal": 300, "protein_g": 9.0, "carbs_g": 50.0, "fat_g": 6.0, "fibre_g": 4.0}
    monkeypatch.setattr(pantry, "estimate_meal", fake)
    pantry.stock(store, ["Basmati Rice 1 kg x1"], "swiggy", "O1")
    from app.experts.family import meds as M
    M.add(store, "me", "Tab. Vitamin D3 60K", "1", ["morning", "afternoon", "night"])
    jid = _answer_incoming(app.state, "+91 98000 00000", "CA1")              # the user's own number
    home = app.state.experts["home"]
    job = store.job(jid)
    assert job["expert"] == "home" and job["person"] == "me" and store.upcoming() == []
    plan = home.call_plan(job)
    assert "నమస్కారం Shiva" in plan.greeting and "AI" in plan.greeting      # Telugu by default, says it is an AI
    assert "Basmati Rice 1 kg" in plan.instructions and "never suggest, start, stop or change" in plan.instructions
    assert "Tab. Vitamin D3 60K 1" in plan.instructions                       # read exactly as written
    t = {f.__name__: f for f in plan.tools}
    t["set_order"](["2 litres milk", "1 kg tomatoes"])
    t["log_food"]("lunch", "rice and pappu")
    t["ran_out"](["rice"])
    t["medicine_taken"]("yes", "yes, took it after breakfast")
    t["end_call"]("Ordered milk and tomatoes", True, "all_done")
    card = asyncio.run(home.after_call(job, plan.saved))
    assert card.kind == "order" and seen == ["2 litres milk, 1 kg tomatoes"]            # still needs a tap
    assert pantry.today(store, HH)["total"]["kcal"] == 300 and pantry.items(store) == []
    log = store.facts("me", "medlog:")[0]["value"]
    assert log["taken"] == "yes" and log["words"].endswith("after breakfast")
    jid2 = _answer_incoming(app.state, "+919800000001", "CA2")                 # Amma: the Family line, as herself
    assert store.job(jid2)["expert"] == "home" and store.job(jid2)["person"] == "amma"
    jid3 = _answer_incoming(app.state, "+919800000002", "CA3")                 # the cook: the Kitchen list call
    assert store.job(jid3)["expert"] == "kitchen"


def test_daily_check_in_reschedules_and_stops():
    app, store, _ = env()
    home = app.state.experts["home"]
    first = home.daily(20)
    assert home.daily_hour() == 20 and store.job(first)["payload"]["to"] == HH["user"]["phone"]
    home.dialled(store.job(first))                                             # placed (answered or not)
    assert len([j for j in store.upcoming() if j["expert"] == "home"]) == 2    # tomorrow's call queued
    home.stop_daily()
    assert home.daily_hour() is None and [j for j in store.upcoming() if j["expert"] == "home"] == []


def test_ring_in_browser_override_and_failed_call_card(monkeypatch):
    from app.main import make_dialer
    app, store, _ = env()
    home = app.state.experts["home"]
    dialled = []
    monkeypatch.setattr("app.core.caller.make_dial", lambda client: lambda to, jid: dialled.append(to) or "CA77")
    dial = make_dialer(store, twilio_client=object())
    assert dial("+919800000000", home.call_me(via="browser")) == "browser" and dialled == []
    jid = home.call_me()
    assert dial("+919800000000", jid) == "CA77" and dialled == ["+919800000000"]
    store.start_job(jid)
    store.end_job(jid, True, {"call_sid": "CA77"})
    with TestClient(app) as client:
        client.post("/calls/status", data={"CallSid": "CA77", "CallStatus": "failed", "CallDuration": "0"})
    card = store.cards()[0]["card"]
    assert "ringing in the app" in card["title"] and "Jio" in card["lines"][0]             # your phone refused it
    again = [j for j in store.upcoming() if j["person"] == "me"][-1]
    assert again["payload"]["via"] == "browser" and again["kind"] == "home"
    assert dial("+919800000000", home.call_me()) == "browser" and len(dialled) == 1          # next calls ring the app
    amma = home.call("amma")
    assert dial("+919800000001", amma) == "CA77"                                           # others still get phone calls
    store.start_job(amma)
    store.end_job(amma, True, {"call_sid": "CA78"})
    with TestClient(app) as client:
        client.post("/calls/status", data={"CallSid": "CA78", "CallStatus": "failed", "CallDuration": "0"})
        fwd = client.get("/api/setup/forwarding").json()
    assert any("did not connect" in c["card"]["title"] and "Amma" in c["card"]["title"] for c in store.cards())
    from app.main import _check_stream_started
    asyncio.run(_check_stream_started(app.state, jid, "Shiva", wait=0))          # completed, but no audio stream
    assert any("press" in c["card"]["title"] and "trial" in c["card"]["lines"][0] for c in store.cards())


def test_swiggy_offline_falls_back_to_zepto_or_keeps_the_list(monkeypatch):
    from app.experts.kitchen import zepto as zp
    from app.experts.kitchen.expert import KitchenExpert
    store = Store(":memory:")

    async def build(z, items, hint=None, advice=""):
        assert items == ["2 litres milk", "1 kg tomatoes"]
        return {"id": "z1", "addressLine": "RMZ The Loft"}, {"cart": {"items": [{"name": "Milk 1 L", "quantity": 2, "price": 6400}]},
                                                             "total": 140.0, "cod": True}, []
    monkeypatch.setattr(zp, "build", build)
    card = asyncio.run(KitchenExpert(store, HH, None, None, zepto=object()).handle("2 litres milk, 1 kg tomatoes"))
    assert card.title == "Zepto cart (Instamart offline)" and card.payload["store"] == "zepto"
    assert card.total == "₹140" and card.address == "RMZ The Loft" and card.choices == [{"id": "COD", "label": "Cash on delivery"}]
    assert "proceed with placing this order to this address" in card.question            # rule 4 on the fallback too
    none = KitchenExpert(store, HH, None, None, None)
    info = asyncio.run(none.handle("2 litres milk, 1 kg tomatoes"))
    assert info.kind == "info" and info.lines == ["2 litres milk", "1 kg tomatoes"]       # nothing said on a call is lost
    assert asyncio.run(none.execute(info.to_dict(), "ok")) == {"ok": True}                # an info tap never orders


def test_card_from_an_unregistered_expert_taps_ok():
    app, store, _ = env()
    aid = store.add_card(Card("caller", "info", "Call to Amma did not connect", ["x"], question="",
                              choices=[{"id": "ok", "label": "OK"}]).to_dict())
    with TestClient(app) as client:
        assert client.post(f"/api/cards/{aid}/tap", json={"choice": "ok"}).json()["status"] == "done"


def test_every_call_follows_the_language_and_wraps_up_before_ending():
    from app.core import convo
    from app.experts.kitchen.expert import KitchenExpert
    app, store, _ = env()
    ex = app.state.experts
    kitchen = KitchenExpert(store, HH, None, None)
    jobs = [(kitchen, store.job(kitchen.weekly_call("amma"))),
            (kitchen, store.job(kitchen.menu_call("lakshmi", {"day": "Mon", "meals": []}))),
            (ex["health"], store.job(ex["health"].checkin("amma", "hi"))),
            (ex["health"], store.job(ex["health"].book("amma", "rao", "2026-11-24T00:00", "2026-11-25T00:00", None, "BP"))),
            (ex["home"], store.job(ex["home"].call_me())),
            (ex["doorstep"], store.job(ex["doorstep"].answered("CA1", "1234")))]
    for expert, job in jobs:
        plan = expert.call_plan(job)
        text = convo.instructions(plan)
        assert plan.language == "Telugu" and text.startswith("LANGUAGE: open in Telugu") and "BEFORE ENDING" in text
        end = {f.__name__: f for f in plan.tools}["end_call"]
        assert end("x", False, "all_done").startswith("Not yet") and "summary" not in plan.saved
        assert convo.ends_call("end_call", end("x", False, "person_said_goodbye")) and plan.saved["summary"] == "x"


def test_app_key_guards_the_api(monkeypatch):
    app, store, _ = env()
    with TestClient(app) as client:
        assert client.get("/api/state").status_code == 200
        monkeypatch.setenv("APP_KEY", "s3cret-key-123")
        assert client.get("/api/state").status_code == 401
        assert client.get("/api/state", headers={"X-QuickPick-Key": "s3cret-key-123"}).status_code == 200
        assert client.get("/api/state?key=s3cret-key-123").json()["user"] == "Shiva"
        r = client.post("/api/orders/nope/delivered", headers={"X-QuickPick-Key": "s3cret-key-123"})
        assert r.status_code == 404


def test_one_check_in_call_also_takes_notes_for_the_doctor(monkeypatch):
    app, store, kitchen = env()
    home = app.state.experts["home"]
    job = store.job(home.call("amma"))
    plan = home.call_plan(job)
    t = {f.__name__: f for f in plan.tools}
    assert "note_for_doctor" in t and "how they are feeling" in plan.instructions and "Never judge" in plan.instructions
    t["note_for_doctor"]("knees hurt more", ["knee pain"], "3 days", ["BP 140/90 this morning"], ["Can I walk daily?"],
                         "mokallu noppi ekkuva ga undi")
    t["end_call"]("Checked in", True, "all_done")
    asyncio.run(home.after_call(job, plan.saved))
    brief = next(c["card"] for c in store.cards() if c["card"]["kind"] == "brief")
    text = "\n".join(brief["lines"])
    assert "mokallu noppi" in text and "BP 140/90 this morning" in text and "Can I walk daily?" in text


def test_forwarding_setup(monkeypatch):
    app, store, _ = env()
    monkeypatch.setenv("EXOTEL_NUMBER", "09513886363")
    monkeypatch.setenv("EXOTEL_STREAM_SECRET", "s" * 32)
    monkeypatch.setenv("PUBLIC_HOST", "abc.trycloudflare.com")
    with TestClient(app) as client:
        f = client.get("/api/setup/forwarding").json()
    assert f["number"] == "9513886363" and f["codes"][0]["on"] == "*403*9513886363#" and f["off_all"] == "##002#"
    assert f["voicebot_url"] == "wss://quickpick:" + "s" * 32 + "@abc.trycloudflare.com/exotel"
