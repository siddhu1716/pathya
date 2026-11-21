"""QuickPick v2 web app: a JSON API for the phone-first UI in web/, plus the scheduler.
Tap = store.claim -> expert.execute -> store.finish. Nothing is committed without a human tap.
Run: uvicorn app.main:app --reload --port 8000   (UI dev server: cd web && npm run dev)"""
import asyncio
import logging
import os
import re
import time
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")                      # before the Experts read env vars at import time

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from app.core import jobs as J
from app.core.lang import default as lang_default, of as lang_of
from app.core.store import Store
from app.experts.base import REGISTRY, register

log = logging.getLogger("quickpick")
RINGING_WINDOW = 30 * 60                        # browser calls stay answerable for 30 minutes


def load_household(path=None):
    path = Path(path or os.getenv("HOUSEHOLD", ROOT / "household.yaml"))
    if not path.exists():
        raise RuntimeError(f"{path} not found. Copy household.example.yaml to household.yaml and fill it in.")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def twilio_ready():
    """CALL_MODE=twilio and real-looking credentials (not the .env.example placeholders)."""
    sid, token = os.getenv("TWILIO_ACCOUNT_SID", ""), os.getenv("TWILIO_AUTH_TOKEN", "")
    return (os.getenv("CALL_MODE", "browser") == "twilio" and re.fullmatch(r"AC[0-9a-fA-F]{32}", sid)
            and len(token) >= 32 and re.fullmatch(r"\+\d{8,15}", os.getenv("TWILIO_FROM", ""))
            and "." in os.getenv("PUBLIC_HOST", "") and "xxxx" not in os.getenv("PUBLIC_HOST", ""))


def make_dialer(store, twilio_client=None):
    """Real phone calls with a Twilio client (CALL_MODE=twilio and valid settings); otherwise calls ring in the browser."""
    if twilio_client is not None:
        from app.core.caller import make_dial
        return make_dial(twilio_client)
    if os.getenv("CALL_MODE") == "twilio":
        store.log("caller", "setup", "CALL_MODE=twilio but the Twilio settings in .env are incomplete; using browser calls")

    def ring_in_browser(to, job_id):
        store.log("caller", job_id, "ringing in the browser (/call/<job>)")
        return "browser"
    return ring_in_browser


# ---------- request bodies ----------
class Text(BaseModel):
    text: str


class Tap(BaseModel):
    choice: str


class Booking(BaseModel):
    patient: str
    clinic: str
    window_start: str
    window_end: str
    part: str = "any"
    reason: str


class Checkin(BaseModel):
    purpose: str = "A friendly check-in: how she feels and what she wants to ask the doctor."


# ---------- routes ----------
api = APIRouter(prefix="/api")


def _st(request: Request):
    return request.app.state


def _expert(request, name):
    e = _st(request).experts.get(name)
    if not e:
        raise HTTPException(503, f"The {name} Expert is not running.")
    return e


def _kitchen_ready(request):
    k = _expert(request, "kitchen")
    if getattr(k, "ops", None) is None:
        raise HTTPException(503, "Swiggy is not connected. Run: npx -y mcp-remote https://mcp.swiggy.com/im")
    return k


@api.get("/state")
def state(request: Request):
    st = _st(request)
    store, hh = st.store, st.household
    waiting = sorted(store.cards("waiting"), key=lambda c: c["card"]["kind"] != "alert")   # urgent cards on top
    called = {f["key"][5:] for f in store.facts(prefix="call:")}
    ringing = [j for j in store.recent_jobs(time.time() - RINGING_WINDOW)
               if isinstance(j.get("result"), dict) and j["result"].get("call_sid") == "browser"
               and j["id"] not in called]
    return {
        "dry_run": os.getenv("DRY_RUN", "1") == "1",
        "swiggy": getattr(st.experts.get("kitchen"), "ops", None) is not None,
        "zepto": getattr(st.experts.get("kitchen"), "zepto", None) is not None,
        "phone": st.twilio is not None,
        "phone_number": os.getenv("TWILIO_FROM") if st.twilio is not None else None,
        "exotel": len(os.getenv("EXOTEL_STREAM_SECRET", "")) >= 16,
        "user": hh["user"]["name"],
        "language": lang_default(hh),
        "daily_call": getattr(st.experts.get("home"), "daily_hour", lambda: None)(),
        "people": [{"key": k, "name": v["name"], "role": v.get("role", ""), "language": lang_of(hh, v)}
                   for k, v in hh["people"].items()],
        "clinics": [{"key": k, "doctor": v["doctor"], "clinic": v["clinic"]} for k, v in hh["clinics"].items()],
        "cards": waiting,
        "recent": store.recent_cards(),
        "jobs": store.upcoming(),
        "ringing": ringing,
        "live": [{"id": jid, **{k: v for k, v in c.items() if k != "lines"}, "lines": c["lines"][-8:]}
                 for jid, c in st.live.items()],
        "orders": [dict(o, journey=_journey(store, o)) for o in store.orders(limit=10)],
        "timeline": store.timeline(limit=30),
    }


def _who(hh, key):
    if key == "me":
        return hh["user"]["name"]
    p = hh["people"].get(key) or hh["clinics"].get(key) or {}
    return p.get("name") or p.get("clinic") or ("Unknown caller" if key == "caller" else key)


@api.get("/calls")
def calls(request: Request):
    """Finished calls, newest first: who, what for, how long, the transcript and what the Expert saved."""
    st = _st(request)
    out = []
    for f in reversed(st.store.facts(prefix="call:")):
        jid, job = f["key"][5:], st.store.job(f["key"][5:])
        v = f["value"] if isinstance(f["value"], dict) else {}
        out.append({"id": jid, "who": _who(st.household, f["person"]), "kind": (job or {}).get("kind"),
                    "expert": (job or {}).get("expert"), "direction": (job or {}).get("payload", {}).get("direction", "outbound"),
                    "source": f["source"], "ended": f["updated"], "seconds": v.get("seconds"),
                    "transcript": v.get("transcript", []), "saved": v.get("saved", {})})
    return out[:30]


def _journey(store, o):
    """Timestamps for one order's journey: call -> card -> tap -> placed -> delivered (slide 4's numbers)."""
    j = {"placed": o["placed"], "delivered": o.get("delivered")}
    card = store.card(o["card"]) if o.get("card") else None
    if card:
        j["card_ready"], j["tapped"] = card["created"], card["updated"]
    call = store.facts(prefix=f"call:{o['ref']}") if o.get("ref") else []
    if call:
        secs = (call[0]["value"] or {}).get("seconds") or 0
        j["call_ended"], j["call_started"] = call[0]["updated"], call[0]["updated"] - secs
    return j


@api.get("/orders")
def orders(request: Request):
    store = _st(request).store
    return [dict(o, journey=_journey(store, o)) for o in store.orders(limit=30)]


@api.post("/ask")
async def ask(body: Text, request: Request):
    from agents import Runner
    from app.concierge import make_concierge
    st = _st(request)
    st.store.log("concierge", "ask", body.text)
    agent = make_concierge(st.store, st.household, _kitchen_ready(request), _expert(request, "health"))
    try:
        run = await Runner.run(agent, body.text, max_turns=10)
    except Exception as err:
        raise HTTPException(502, f"QuickPick could not finish that: {err}")
    st.store.log("concierge", "ask", f"reply: {run.final_output}")
    return {"reply": run.final_output}


@api.post("/kitchen/plan")
async def kitchen_plan(body: Text, request: Request):
    kitchen = _kitchen_ready(request)
    try:
        card = await kitchen.handle(body.text)
    except Exception as err:
        raise HTTPException(502, f"Could not build the cart: {err}")
    return {"card": _st(request).store.add_card(card.to_dict())}


def _person(request, person):
    if person not in _st(request).household["people"]:
        raise HTTPException(404, f"{person} is not in household.yaml. Only people listed there are called.")


@api.post("/kitchen/call/{person}")
def kitchen_call(person: str, request: Request):
    _person(request, person)
    return {"job": _expert(request, "kitchen").weekly_call(person)}


class Reorder(BaseModel):
    items: list[str]


class PlanAsk(BaseModel):
    days: int = 3
    notes: str = ""


@api.get("/kitchen/overview")
def kitchen_overview(request: Request):
    from app.experts.kitchen import pantry
    from app.experts.kitchen import planner as pl
    st = _st(request)
    fact = lambda key: next((f["value"] for f in st.store.facts("home", key)), None)
    cook = st.experts["kitchen"].cook() if "kitchen" in st.experts else None
    k = st.household.get("kitchen") or {}
    return {"usuals": pl.usuals(st.store), "plan": fact("mealplan"), "nutrition": fact("nutrition"),
            "pantry": pantry.items(st.store), "today": pantry.today(st.store, st.household),
            "targets": pl.targets(st.household), "nutritionist": (st.household.get("nutritionist") or {}).get("name"),
            "cook": st.household["people"][cook]["name"] if cook else None,
            "prefs": {"people": k.get("people", len(st.household["people"]) + 1), "diet": k.get("diet", "vegetarian"),
                      "cuisine": k.get("cuisine", "Telugu home food")}}


@api.post("/kitchen/reorder")
async def kitchen_reorder(body: Reorder, request: Request):
    kitchen = _kitchen_ready(request)
    if not body.items:
        raise HTTPException(400, "Pick at least one item.")
    try:
        card = await kitchen.handle(", ".join(body.items[:30]))
    except Exception as err:
        raise HTTPException(502, f"Could not build the cart: {err}")
    return {"card": _st(request).store.add_card(card.to_dict())}


@api.post("/kitchen/mealplan")
async def kitchen_mealplan(body: PlanAsk, request: Request):
    from app.experts.kitchen import planner as pl
    st = _st(request)
    days = max(1, min(body.days, 7))
    try:
        plan = await pl.meal_plan(st.household, st.store, days, body.notes)
    except Exception as err:
        raise HTTPException(502, f"Could not plan meals: {err}")
    st.store.remember("home", "mealplan", {**plan, "made": time.time(), "for_days": days}, "meal planner")
    aid = st.store.add_card(_expert(request, "kitchen").plan_card(plan, days).to_dict())
    return {"card": aid, "plan": plan}


@api.post("/kitchen/nutrition")
async def kitchen_nutrition(request: Request):
    from app.experts.kitchen import planner as pl
    st = _st(request)
    try:
        nut = await pl.nutrition(st.store, st.household)
    except Exception as err:
        raise HTTPException(502, f"Could not estimate nutrition: {err}")
    st.store.remember("home", "nutrition", {**nut, "made": time.time()}, "nutrition estimate")
    return nut


@api.post("/kitchen/nutrition/share")
def kitchen_nutrition_share(request: Request):
    st = _st(request)
    fact = lambda key: next((f["value"] for f in st.store.facts("home", key)), None)
    nut = fact("nutrition")
    if not nut:
        raise HTTPException(409, "Work out the nutrition picture first.")
    card = _expert(request, "kitchen").nutrition_card(fact("mealplan"), nut)
    return {"card": st.store.add_card(card.to_dict())}


class Used(BaseModel):
    key: str


@api.post("/kitchen/pantry/used")
def pantry_used(body: Used, request: Request):
    """'This is finished': off the shelf (it then shows up for reordering under the usuals)."""
    if not _st(request).store.forget("home", f"pantry:{body.key}"):
        raise HTTPException(404, "Not on the shelf.")
    return {"ok": True}


class Meal(BaseModel):
    text: str
    meal: str = ""


@api.post("/kitchen/meal")
async def log_meal(body: Meal, request: Request):
    from app.experts.kitchen import pantry
    if not body.text.strip():
        raise HTTPException(400, "Say what you ate.")
    try:
        return await pantry.log_meal(_st(request).store, body.text.strip()[:300], body.meal)
    except Exception as err:
        raise HTTPException(502, f"Could not estimate that meal: {err}")


@api.post("/orders/{oid}/delivered")
def order_delivered(oid: str, request: Request):
    """The 'Got it' button: delivered now, items on the pantry shelf (if the tracker has not seen it yet)."""
    from app.core.tracker import mark_delivered
    store = _st(request).store
    if not store.order(oid):
        raise HTTPException(404, "No such order.")
    mark_delivered(store, oid)
    return store.order(oid)


class Daily(BaseModel):
    hour: int | None = None


@api.post("/home/call")
def home_call(request: Request):
    """QuickPick phones the user now (check-in: medicines they listed, meals, reorders)."""
    return {"job": _expert(request, "home").call_me()}


@api.post("/home/daily")
def home_daily(body: Daily, request: Request):
    home = _expert(request, "home")
    if body.hour is None:
        home.stop_daily()
        return {"ok": True, "hour": None}
    if not 6 <= body.hour <= 22:
        raise HTTPException(400, "Pick an hour between 6 and 22.")
    return {"ok": True, "hour": body.hour, "job": home.daily(body.hour)}


@api.post("/health/book")
def health_book(body: Booking, request: Request):
    hh = _st(request).household
    _person(request, body.patient)
    if body.clinic not in hh["clinics"]:
        raise HTTPException(404, f"{body.clinic} is not in household.yaml.")
    jid = _expert(request, "health").book(body.patient, body.clinic, body.window_start, body.window_end,
                                          None if body.part == "any" else body.part, body.reason)
    return {"job": jid}


@api.post("/health/checkin/{person}")
def health_checkin(person: str, body: Checkin, request: Request):
    if person != "me":
        _person(request, person)
    return {"job": _expert(request, "health").checkin(person, body.purpose)}


@api.post("/health/rx")
async def health_rx(request: Request, patient: str = Form(...), photo: UploadFile = File(...)):
    from app.experts.health.rx import read_prescription
    if patient != "me":
        _person(request, patient)
    try:
        rx = await asyncio.to_thread(read_prescription, await photo.read(), photo.content_type or "image/jpeg")
    except Exception as err:
        raise HTTPException(502, f"Could not read the prescription: {err}")
    card = _expert(request, "health").meds_card(patient, rx)
    return {"card": _st(request).store.add_card(card.to_dict())}


@api.get("/cards/{aid}")
def get_card(aid: str, request: Request):
    row = _st(request).store.card(aid)
    if not row:
        raise HTTPException(404, "No such card.")
    return row


async def _settle_upi(st, aid, kitchen, result):
    """UPI: wait for the payment inside Swiggy's window, then finish the card with Swiggy's message."""
    try:
        ok, msg = await kitchen.settle(result["order"])
        result.update(paid=ok, message=msg)
        if ok:
            result["eta"] = await kitchen.etas(result["order"], result.get("address_id", ""))
        st.store.finish(aid, ok, result)
        if ok:
            from app.core.tracker import record
            record(st.store, aid, st.store.card(aid)["card"], result)
    except Exception as err:
        st.store.finish(aid, False, {**result, "ok": False, "error": f"Payment check failed: {err}"})


@api.post("/cards/{aid}/tap")
async def tap(aid: str, body: Tap, request: Request):
    st = _st(request)
    row = st.store.card(aid)
    if not row:
        raise HTTPException(404, "No such card.")
    if body.choice not in {c["id"] for c in row["card"].get("choices", [])}:
        raise HTTPException(400, "That choice is not on this card.")
    card = st.store.claim(aid, body.choice)                 # waiting -> running exactly once
    if card is None:
        return st.store.card(aid)                           # double tap: nothing runs again
    expert = st.experts.get(card["expert"])
    try:
        result = await expert.execute(card, body.choice)
    except Exception as err:                                # a failed card never reopens: no silent retry
        st.store.finish(aid, False, {"ok": False, "error": str(err)})
        return st.store.card(aid)
    if result.get("pay_url"):
        result["address_id"] = card["payload"].get("address_id")
        st.store.note(aid, result)
        st.store.log(card["expert"], aid, "waiting for UPI payment")
        st.tasks.add(t := asyncio.create_task(_settle_upi(st, aid, expert, result)))
        t.add_done_callback(st.tasks.discard)
    else:
        ok = bool(result.get("ok", True))
        st.store.finish(aid, ok, result)
        if ok and card["kind"] == "order":
            from app.core.tracker import record
            record(st.store, aid, card, result)
    return st.store.card(aid)


@api.post("/cards/{aid}/reject")
def reject(aid: str, request: Request):
    if not _st(request).store.reject(aid):
        raise HTTPException(409, "This card was already handled.")
    return {"ok": True}


@api.get("/cards/{aid}/ics")
def card_ics(aid: str, request: Request):
    row = _st(request).store.card(aid)
    ics = row and row["card"].get("payload", {}).get("ics")
    if not ics:
        raise HTTPException(404, "This card has no calendar file.")
    return PlainTextResponse(ics, media_type="text/calendar",
                             headers={"Content-Disposition": f'attachment; filename="quickpick-{aid}.ics"'})


@api.post("/jobs/{jid}/run-now")
def run_now(jid: str, request: Request):
    if not _st(request).store.run_now(jid):
        raise HTTPException(409, "That job is not scheduled any more.")
    return {"ok": True}


# ---------- browser calls (OpenAI Realtime over WebRTC; the phone line comes later) ----------
class ToolCall(BaseModel):
    name: str
    arguments: str = "{}"


class CallEnd(BaseModel):
    transcript: list[dict] = []


def _call_job(request, jid):
    job = _st(request).store.job(jid)
    if not job:
        raise HTTPException(404, "No such call.")
    expert = _st(request).experts.get(job["expert"])
    if not expert or job["kind"] not in expert.call_kinds:
        raise HTTPException(400, "That job is not a phone call.")
    return job, expert


def _live(request, jid):
    call = _st(request).calls.get(jid)
    if not call:
        raise HTTPException(409, "This call has not been answered.")
    return call


@api.get("/calls/{jid}")
def call_info(jid: str, request: Request):
    job, expert = _call_job(request, jid)
    hh = _st(request).household
    who = hh["people"].get(job["person"]) or hh["clinics"].get(job["person"]) or {}
    done = bool(_st(request).store.facts(prefix=f"call:{jid}"))
    return {"id": jid, "kind": job["kind"], "expert": expert.title, "done": done,
            "who": who.get("name") or who.get("clinic") or job["person"], "user": hh["user"]["name"]}


@api.post("/calls/{jid}/sdp")
async def call_sdp(jid: str, request: Request):
    """The browser 'answers': its SDP offer becomes a Realtime session running this job's CallPlan."""
    from app.core.browser_call import Call, answer_sdp, session_config
    st = _st(request)
    job, expert = _call_job(request, jid)
    if st.store.facts(prefix=f"call:{jid}"):
        raise HTTPException(409, "This call already ended.")
    offer = (await request.body()).decode()
    if not offer.strip():
        raise HTTPException(400, "An SDP offer is required.")
    plan = expert.call_plan(job)
    try:
        answer = await answer_sdp(offer, session_config(plan))
    except Exception as err:
        st.store.log(expert.name, jid, f"call could not start: {err}")
        raise HTTPException(502, str(err))
    st.calls[jid] = Call(job, expert, plan)
    _go_live(st, st.calls[jid], [])
    st.store.log(expert.name, jid, f"call answered (browser), limit {plan.max_minutes} min")
    return PlainTextResponse(answer, media_type="application/sdp")


def _go_live(st, call, lines):
    """In-progress calls with their transcript so far (the UI shows them live)."""
    job = call.job
    st.live[job["id"]] = {"who": _who(st.household, job["person"]), "kind": job["kind"], "expert": call.expert.title,
                          "direction": job["payload"].get("direction", "outbound"), "started": call.started,
                          "lines": lines}


class Line(BaseModel):
    role: str
    text: str


@api.post("/calls/{jid}/line")
def call_line(jid: str, body: Line, request: Request):
    live = _st(request).live.get(jid)
    if live is not None and body.role in ("ai", "them", "tool"):
        live["lines"].append({"role": body.role, "text": body.text[:500]})
    return {"ok": True}


@api.get("/calls/{jid}/greeting")
def call_greeting(jid: str, request: Request):
    call = _live(request, jid)
    return {"greeting": call.plan.greeting, "max_minutes": call.plan.max_minutes}


@api.post("/calls/{jid}/tool")
async def call_tool(jid: str, body: ToolCall, request: Request):
    call = _live(request, jid)
    out = await call.run_tool(body.name, body.arguments)
    _st(request).store.log(call.expert.name, jid, f"{body.name} -> {out}")   # refusals show on the timeline
    return {"output": out, "end": body.name == "end_call"}


async def _after_call(st, call, jid):
    try:
        card = await call.expert.after_call(call.job, call.plan.saved)
        if card:
            st.store.add_card(card.to_dict())
        else:
            st.store.log(call.expert.name, jid, "call ended without anything to approve")
    except Exception as err:
        st.store.log(call.expert.name, jid, f"after the call failed: {err}")


def _finish_call(st, call, jid, transcript, source):
    """Browser or phone: save the transcript once, then let the Expert turn the call into a card."""
    if call.ended:
        return
    call.ended = True
    secs = int(time.time() - call.started)
    st.store.remember(call.job["person"], f"call:{jid}",
                      {"transcript": transcript[-200:], "saved": call.plan.saved, "seconds": secs}, source)
    st.store.log(call.expert.name, jid, f"call ended after {secs} s")
    st.tasks.add(t := asyncio.create_task(_after_call(st, call, jid)))     # e.g. building the cart takes ~30 s
    t.add_done_callback(st.tasks.discard)
    st.calls.pop(jid, None)
    st.live.pop(jid, None)


@api.post("/calls/{jid}/end")
async def call_end(jid: str, body: CallEnd, request: Request):
    st = _st(request)
    call = st.calls.get(jid)
    if call:
        _finish_call(st, call, jid, body.transcript, "browser call")
    elif not st.store.facts(prefix=f"call:{jid}"):
        raise HTTPException(409, "This call has not been answered.")
    return {"ok": True}


def _phone_call_for_start(st, msg, lines=None):
    """Only streams for calls we dialled or answered: the job exists, is a call kind, and Twilio's CallSid matches."""
    from app.core.browser_call import Call
    from app.core.caller import job_id_from_start
    jid = job_id_from_start(msg)
    job = jid and st.store.job(jid)
    expert = job and st.experts.get(job["expert"])
    if not job or not expert or job["kind"] not in expert.call_kinds:
        raise RuntimeError(f"Unknown call stream for job {jid!r}")
    if not isinstance(job.get("result"), dict) or job["result"].get("call_sid") != msg["start"].get("callSid"):
        raise RuntimeError(f"Call SID does not match job {jid}")
    if jid in st.calls or st.store.facts(prefix=f"call:{jid}"):
        raise RuntimeError(f"Job {jid} already has a call")
    call = Call(job, expert, expert.call_plan(job))
    st.calls[jid] = call
    _go_live(st, call, lines if lines is not None else [])
    st.store.log(expert.name, jid, f"{_who(st.household, job['person'])} on the phone, limit {call.plan.max_minutes} min")
    return call


def _digits(n):
    return "".join(c for c in str(n or "") if c.isdigit())[-10:]


def _person_by_phone(hh, number):
    return next((k for k, p in hh["people"].items() if _digits(p.get("phone")) and _digits(p.get("phone")) == _digits(number)),
                None)


def _answer_incoming(st, caller, call_sid):
    """Someone phoned QuickPick: the user gets their Home line, household members the Kitchen list call,
    anyone else the Doorstep Expert."""
    if "home" in st.experts and _digits(caller) and _digits(caller) == _digits(st.household["user"].get("phone")):
        jid = st.experts["home"].answered(call_sid)
        st.store.log("caller", jid, f"incoming call from {st.household['user']['name']} (Home line)")
        return jid
    person = _person_by_phone(st.household, caller)
    if person and "kitchen" in st.experts:
        jid = st.experts["kitchen"].answered(person, call_sid)
    else:
        jid = st.experts["doorstep"].answered(call_sid, "".join(c for c in str(caller or "") if c.isdigit())[-4:])
    st.store.log("caller", jid, f"incoming call from {_who(st.household, person) if person else 'an unknown number'}")
    return jid


def exotel_auth_ok(header):
    """Exotel's Voicebot applet sends the user:pass from its wss://user:pass@host URL as HTTP Basic auth."""
    import base64
    import hmac
    secret = os.getenv("EXOTEL_STREAM_SECRET", "")
    if len(secret) < 16 or not (header or "").startswith("Basic "):
        return False
    try:
        given = base64.b64decode(header[6:]).decode()
    except Exception:
        return False
    return hmac.compare_digest(given, f"quickpick:{secret}")


# ---------- app ----------
def build_app(lifespan=None) -> FastAPI:
    import hmac
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    app = FastAPI(title="QuickPick Experts", lifespan=lifespan)
    app.include_router(api)

    @app.middleware("http")
    async def need_key(request: Request, call_next):
        """APP_KEY set (phone mode sets it): the app's API needs it, so a public tunnel URL alone is not enough.
        Twilio and Exotel routes have their own checks (signature, Basic auth)."""
        key = os.getenv("APP_KEY", "")
        if key and request.url.path.startswith("/api/") and request.method != "OPTIONS":
            given = request.headers.get("x-quickpick-key") or request.query_params.get("key") or ""
            if not hmac.compare_digest(given.encode(), key.encode()):
                return JSONResponse({"detail": "QuickPick key needed."}, status_code=401)
        return await call_next(request)

    # The UI may be hosted elsewhere (Vercel) and call this server through the tunnel.
    app.add_middleware(CORSMiddleware, allow_origin_regex=os.getenv("CORS_ORIGINS", r"https://[a-z0-9-]+\.vercel\.app"),
                       allow_methods=["*"], allow_headers=["*"])

    @app.post("/calls/status")
    async def call_status(request: Request):
        form = await request.form()
        store = request.app.state.store
        store.log("caller", form.get("CallSid", ""), f"call {form.get('CallStatus', '')} "
                                                    f"({form.get('CallDuration', '0')} s)")
        return PlainTextResponse("")

    @app.post("/calls/incoming")
    async def call_incoming(request: Request):
        """Twilio voice webhook for the QuickPick number. Household members get the Kitchen list call;
        anyone else (usually the delivery partner) gets the Doorstep Expert. Only Twilio-signed requests."""
        from twilio.request_validator import RequestValidator
        from app.core.caller import stream_twiml
        st = request.app.state
        form = dict(await request.form())
        if st.twilio is None:
            raise HTTPException(503, "Phone calls are not configured.")
        url = f"https://{os.environ['PUBLIC_HOST']}/calls/incoming"
        if not RequestValidator(os.environ["TWILIO_AUTH_TOKEN"]).validate(url, form, request.headers.get("X-Twilio-Signature", "")):
            raise HTTPException(403, "Not signed by Twilio.")
        caller, sid = form.get("From", ""), form.get("CallSid", "")
        jid = _answer_incoming(st, caller, sid)
        return PlainTextResponse(stream_twiml(os.environ["PUBLIC_HOST"], jid), media_type="text/xml")

    @app.websocket("/exotel")
    async def exotel_stream(ws: WebSocket):
        """Exotel Voicebot applet (bidirectional). Every call here is incoming, e.g. Jio forwarding to the ExoPhone."""
        from app.core.call_session import phone_bridge
        from app.core.carriers import Exotel
        st = ws.app.state
        if not exotel_auth_ok(ws.headers.get("authorization")):
            await ws.close(code=1008)
            st.store.log("caller", "exotel", "refused an Exotel stream without the right credentials")
            return
        await ws.accept()
        jid, lines = {}, []

        def call_for_start(msg):
            info = Exotel().start(msg)
            job_id = _answer_incoming(st, info["from"], info["call"])
            call = _phone_call_for_start(st, {"event": "start", "start": {"callSid": info["call"],
                                                                         "customParameters": {"job_id": job_id}}}, lines)
            jid["id"] = job_id
            return call

        async def finish(call, transcript):
            _finish_call(st, call, call.job["id"], transcript, "phone call")

        async def hang_up(call_sid):
            await ws.close()                                # Exotel moves to the next applet (Hangup)

        try:
            await phone_bridge(ws, call_for_start, finish, hang_up,
                               lambda what: st.store.log("caller", jid.get("id", "exotel"), what),
                               transcript=lines, carrier=Exotel())
        except Exception as err:
            st.store.log("caller", jid.get("id", "exotel"), f"Exotel stream failed: {err}")
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    @app.websocket("/media-stream")
    async def media_stream(ws: WebSocket):
        from app.core.call_session import phone_bridge
        st = ws.app.state
        await ws.accept()
        jid = {}
        lines = []

        def call_for_start(msg):
            call = _phone_call_for_start(st, msg, lines)
            jid["id"] = call.job["id"]
            return call

        async def finish(call, transcript):
            _finish_call(st, call, call.job["id"], transcript, "phone call")

        def hang_up(call_sid):
            from app.core.caller import hang_up as twilio_hang_up
            twilio_hang_up(st.twilio, call_sid)

        try:
            await phone_bridge(ws, call_for_start, finish, hang_up,
                               lambda what: st.store.log("caller", jid.get("id", "stream"), what), transcript=lines)
        except Exception as err:
            st.store.log("caller", jid.get("id", "stream"), f"phone stream failed: {err}")
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    dist = ROOT / "web" / "dist"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "No such API route.")
        if not dist.exists():
            raise HTTPException(404, "UI not built. Run: cd web && npm run build (or npm run dev on :5173)")
        f = (dist / path).resolve()
        if path and f.is_file() and dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(dist / "index.html")

    app.state.tasks = set()
    app.state.calls = {}
    app.state.live = {}
    app.state.twilio = None
    return app


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.experts.health.expert import HealthExpert
    from app.experts.kitchen import swiggy as sw
    from app.experts.kitchen.expert import KitchenExpert

    hh = load_household()
    store = Store(os.getenv("DB_PATH", str(ROOT / "quickpick.db")))
    async with AsyncExitStack() as stack:
        agent_im = ops = None
        try:
            agent_im = await stack.enter_async_context(sw.bridge("im-agent", sw.AGENT_TOOLS))
            ops = await stack.enter_async_context(sw.bridge("im-ops"))
            store.log("app", "swiggy", "Swiggy Instamart connected")
        except Exception as err:                            # the app still runs; Kitchen routes return 503
            log.exception("Swiggy connection failed")
            store.log("app", "swiggy", f"Swiggy not connected: {err}")
        zepto = None
        if os.getenv("ZEPTO_BACKUP", "1") == "1":
            from app.experts.kitchen import zepto as zp
            try:
                zepto = await stack.enter_async_context(zp.bridge())
                store.log("app", "zepto", "Zepto connected (backup for items Instamart can't supply)")
            except Exception as err:
                store.log("app", "zepto", f"Zepto not connected: {err}")
        REGISTRY.clear()                                    # uvicorn --reload re-runs the lifespan
        register(KitchenExpert(store, hh, agent_im, ops, zepto))
        register(HealthExpert(store, hh))
        from app.experts.doorstep.expert import DoorstepExpert
        from app.experts.home.expert import HomeExpert
        register(DoorstepExpert(store, hh))
        register(HomeExpert(store, hh, REGISTRY["kitchen"]))
        app.state.store, app.state.household, app.state.experts = store, hh, REGISTRY
        if twilio_ready():
            from twilio.rest import Client
            app.state.twilio = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
            store.log("caller", "setup", f"phone calls via Twilio {os.environ['TWILIO_FROM']} "
                                         f"(stream: wss://{os.environ['PUBLIC_HOST']}/media-stream)")
        dispatch = J.make_dispatch(store, REGISTRY, make_dialer(store, app.state.twilio))
        scheduler = asyncio.create_task(J.run_forever(store, dispatch, every=5))
        from app.core import tracker
        tracking = asyncio.create_task(tracker.run_forever(store, REGISTRY["kitchen"], every=60))
        store.log("app", "start", f"QuickPick started (DRY_RUN={os.getenv('DRY_RUN', '1')})")
        try:
            yield
        finally:
            scheduler.cancel()
            tracking.cancel()
            for t in list(app.state.tasks):
                t.cancel()


app = build_app(lifespan)
