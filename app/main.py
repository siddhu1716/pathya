"""Pathya v2 web app: a JSON API for the phone-first UI in web/, plus the scheduler.
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
APK = ROOT / "mobile" / "pathya.apk"
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
    hh = yaml.safe_load(path.read_text(encoding="utf-8"))
    hh["pharmacies"] = hh.get("pharmacies") or {}         # added in the app after a tap (health/pharmacy.py)
    return hh


def twilio_ready():
    """CALL_MODE=twilio and real-looking credentials (not the .env.example placeholders)."""
    sid, token = os.getenv("TWILIO_ACCOUNT_SID", ""), os.getenv("TWILIO_AUTH_TOKEN", "")
    return (os.getenv("CALL_MODE", "browser") == "twilio" and re.fullmatch(r"AC[0-9a-fA-F]{32}", sid)
            and len(token) >= 32 and re.fullmatch(r"\+\d{8,15}", os.getenv("TWILIO_FROM", ""))
            and "." in os.getenv("PUBLIC_HOST", "") and "xxxx" not in os.getenv("PUBLIC_HOST", ""))


def make_dialer(store, twilio_client=None):
    """Real phone calls with a Twilio client (CALL_MODE=twilio and valid settings); otherwise calls ring in the browser.
    A job with payload via=browser always rings in the browser (the UI's "Ring: this browser"). Pathya's own calls
    always go out on Twilio; only if the phone network refuses one does it ring in the app instead (call_status)."""
    if twilio_client is None and os.getenv("CALL_MODE") == "twilio":
        store.log("caller", "setup", "CALL_MODE=twilio but the Twilio settings in .env are incomplete; using browser calls")

    def ring_in_browser(to, job_id):
        store.log("caller", job_id, "ringing in the browser (/call/<job>)")
        return "browser"

    if twilio_client is None:
        return ring_in_browser
    from app.core.caller import make_dial
    phone = make_dial(twilio_client)

    def dial(to, job_id):
        job = store.job(job_id)
        if job and job["payload"].get("via") == "browser":
            return ring_in_browser(to, job_id)
        return phone(to, job_id)
    return dial


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
    if getattr(k, "ops", None) is None and getattr(k, "zepto", None) is None:
        raise HTTPException(503, "No store is connected (Swiggy and Zepto are both offline). Try again in a few minutes.")
    return k


@api.get("/state")
def state(request: Request):
    st = _st(request)
    store, hh = st.store, st.household
    waiting = sorted(store.cards("waiting"), key=lambda c: c["card"]["kind"] != "alert")   # urgent cards on top
    called = {f["key"][5:] for f in store.facts(prefix="call:")} | {f["key"][9:] for f in store.facts(prefix="declined:")}
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
        "android_apk": APK.is_file(),
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
    p = hh["people"].get(key) or hh["clinics"].get(key) or (hh.get("pharmacies") or {}).get(key) or {}
    return p.get("name") or p.get("clinic") or ("Unknown caller" if key == "caller" else key)


# ---------- phone sign-in (app/core/auth.py) ----------
OPEN_PATHS = {"/api/auth/status", "/api/auth/start", "/api/auth/check"}
CODE_EVERY = 30                                   # seconds between codes to one number


class SignIn(BaseModel):
    phone: str
    code: str = ""
    channel: str = "sms"                      # sms, or call: Twilio reads the code out


@api.get("/auth/status")
def auth_status(request: Request):
    """Open: whether this server can text sign-in codes (Twilio on) and whether a key or sign-in is needed."""
    return {"phone_sign_in": _st(request).twilio is not None, "needed": bool(os.getenv("APP_KEY"))}


@api.post("/auth/start")
def auth_start(body: SignIn, request: Request):
    from app.core import auth
    st = _st(request)
    if st.twilio is None:
        raise HTTPException(503, "Phone sign-in needs Twilio (CALL_MODE=twilio). Use your Pathya link instead.")
    found = auth.who_has(st.household, body.phone)
    if not found:
        raise HTTPException(403, "That number is not in your family's list. Ask whoever runs Pathya to add it "
                                 "(Family > person > Phone).")
    number, now = found[2], time.time()                 # always the stored household number
    sent = st.sign_in_sent
    if now - sent.get(number, 0) < CODE_EVERY:
        raise HTTPException(429, f"A code was just sent. Wait {int(CODE_EVERY - (now - sent[number])) + 1} seconds.")
    try:
        auth.send_code(st.twilio, st.store, number, body.channel)
    except Exception as err:
        msg = str(err)
        raise HTTPException(502, "Twilio's trial only texts verified numbers: verify this number in Family > Phone > "
                                 "Verify first." if "unverified" in msg.lower() else f"Could not send the code: {msg[:200]}")
    sent[number] = now
    st.store.log("auth", found[0], f"sign-in code ({'call' if body.channel == 'call' else 'SMS'}) to …{_digits(number)[-4:]}")
    return {"sent": True, "to": f"…{_digits(number)[-4:]}", "channel": "call" if body.channel == "call" else "sms"}


@api.post("/auth/check")
def auth_check(body: SignIn, request: Request):
    from app.core import auth
    st = _st(request)
    found = auth.who_has(st.household, body.phone)
    if st.twilio is None or not found:
        raise HTTPException(403, "That number can't sign in here.")
    try:
        ok = auth.code_ok(st.twilio, st.store, found[2], body.code)
    except Exception as err:
        raise HTTPException(502, f"Could not check the code: {str(err)[:200]}")
    if not ok:
        raise HTTPException(401, "That code is not right, or it expired. Ask for a new one.")
    token = auth.start_session(st.store, found[0], found[1], found[2])
    st.store.log("auth", found[0], f"{found[1]} signed in with …{_digits(found[2])[-4:]}")
    return {"token": token, "who": found[0], "name": found[1]}


@api.get("/auth/me")
def auth_me(request: Request):
    from app.core import auth
    given = request.headers.get("x-quickpick-key") or request.query_params.get("key") or ""
    s = auth.session(_st(request).store, given)
    if s:
        return {"via": "phone", **s}
    return {"via": "link" if os.getenv("APP_KEY") else "open", "who": "me", "name": _st(request).household["user"]["name"]}


@api.post("/auth/signout")
def auth_signout(request: Request):
    from app.core import auth
    auth.end_session(_st(request).store, request.headers.get("x-quickpick-key") or "")
    return {"ok": True}


@api.get("/setup/forwarding")
def forwarding(request: Request):
    """'Answer my calls': forward the user's own phone (when busy / unanswered) to an Indian number that runs Pathya.
    Jio cannot forward to Twilio's US number, so it is the Exotel number (Voicebot applet -> wss://.../exotel)."""
    number = re.sub(r"\D", "", os.getenv("EXOTEL_NUMBER", ""))[-10:]
    host, secret = os.getenv("PUBLIC_HOST", ""), os.getenv("EXOTEL_STREAM_SECRET", "")
    return {"number": number or None,
            "voicebot_url": f"wss://quickpick:{secret}@{host}/exotel" if number and len(secret) >= 16 and "." in host else None,
            "codes": [{"when": "Not answered", "on": f"*403*{number}#", "off": "##403#"},
                      {"when": "Busy", "on": f"*405*{number}#", "off": "##405#"},
                      {"when": "Unreachable", "on": f"*409*{number}#", "off": "##409#"}] if number else [],
            "off_all": "##002#", "other_networks": f"**61*+91{number}# (not answered), **67*+91{number}# (busy)" if number else ""}


def _voice_for(st, job):
    """This call's voice settings: the family's choice; members aged 60+ get the slower, patient turn-taking."""
    from app.core import voice
    from app.experts.family import profiles as P
    try:
        m = P.member(st.household, st.store, job["person"])
    except KeyError:                                   # clinics, delivery partners, unknown callers
        m = None
    return voice.for_member(voice.get(st.store), m)


class VoiceIn(BaseModel):
    voice: str | None = None
    accent: str | None = None
    pace: str | None = None
    patience: str | None = None
    interrupt: bool | None = None
    elders_slow: bool | None = None
    notes: str | None = None


def _voice_view(s):
    from app.core import voice as V
    return {"settings": s, "voices": [{"id": k, "about": v} for k, v in V.VOICES.items()], "accents": list(V.ACCENTS),
            "paces": list(V.PACES), "patience": list(V.PATIENCE), "notes_max": V.NOTES_MAX, "call_ends": V.CALL_ENDS}


@api.get("/voice")
def voice_settings(request: Request):
    from app.core import voice as V
    return _voice_view(V.get(_st(request).store))


@api.put("/voice")
def voice_save(body: VoiceIn, request: Request):
    """How Pathya sounds on every call from now on (browser, Twilio and Exotel)."""
    from app.core import voice as V
    st = _st(request)
    try:
        s = V.save(st.store, body.model_dump())
    except ValueError as err:
        raise HTTPException(400, str(err))
    st.store.log("caller", "voice", f"voice: {s['voice']}, {s['accent']} accent, {s['pace']} pace, {s['patience']} "
                                    f"turn-taking, interruptions {'on' if s['interrupt'] else 'off'}")
    return _voice_view(s)


@api.post("/voice/preview")
async def voice_preview(body: VoiceIn, request: Request):
    """A few seconds of a voice saying how a call opens (OpenAI text-to-speech has the same voice names)."""
    from fastapi.responses import Response
    from openai import AsyncOpenAI
    from app.core import voice as V
    from app.core.lang import greet
    st = _st(request)
    try:
        s = V.clean(body.model_dump(), V.get(st.store))
    except ValueError as err:
        raise HTTPException(400, str(err))
    language = lang_default(st.household)
    text = f"{greet(language, 'self', st.household['user']['name'])} {V.SAMPLES.get(language, V.SAMPLES['English'])}"
    cache = st.voice_cache
    k = (s["voice"], s["accent"], s["pace"], text)
    if k not in cache:
        try:
            r = await AsyncOpenAI().audio.speech.create(model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"), voice=s["voice"],
                                                        input=text, instructions=V.preview_instructions(s),
                                                        response_format="mp3")
        except Exception as err:
            raise HTTPException(502, f"Could not make the sample: {err}")
        if len(cache) > 40:
            cache.clear()
        cache[k] = r.content
    return Response(cache[k], media_type="audio/mpeg")


@api.get("/voice/prompt")
def voice_prompt(request: Request, who: str = "me"):
    """Read-only: the exact instructions Pathya gets on a check-in call with this person, with the voice settings."""
    from app.core import convo
    st = _st(request)
    home = _expert(request, "home")
    m = _member(request, who)
    job = {"id": "preview", "expert": "home", "kind": "home", "person": who, "payload": {"direction": "outbound"}}
    plan = home.call_plan(job)
    plan.voice = _voice_for(st, job)
    return {"who": m["name"], "greeting": plan.greeting, "prompt": convo.instructions(plan),
            "tools": [f.__name__ for f in plan.tools], "max_minutes": plan.max_minutes, "voice": plan.voice}


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
        raise HTTPException(502, f"Pathya could not finish that: {err}")
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


def _via(request):
    """?via=browser: ring this call in the app even when real phone calls are on."""
    return "browser" if request.query_params.get("via") == "browser" else None


@api.post("/kitchen/call/{person}")
def kitchen_call(person: str, request: Request):
    _person(request, person)
    via = _via(request)
    kitchen = _expert(request, "kitchen")
    return {"job": kitchen.weekly_call(person, via=via) if via else kitchen.weekly_call(person)}


class Reorder(BaseModel):
    items: list[str]


class PlanAsk(BaseModel):
    days: int = 3
    notes: str = ""
    eaters: list[str] | None = None                  # family member keys; None = everyone
    guests: int = 0


@api.get("/kitchen/overview")
def kitchen_overview(request: Request):
    from app.experts.kitchen import pantry
    from app.experts.kitchen import planner as pl
    st = _st(request)
    fact = lambda key: next((f["value"] for f in st.store.facts("home", key)), None)
    cook = st.experts["kitchen"].cook() if "kitchen" in st.experts else None
    k = st.household.get("kitchen") or {}
    from app.experts.family import profiles as P
    return {"usuals": pl.usuals(st.store), "plan": fact("mealplan"), "nutrition": fact("nutrition"),
            "pantry": pantry.items(st.store), "today": pantry.today(st.store, st.household),
            "targets": P.average(P.members(st.household, st.store)),
            "nutritionist": (st.household.get("nutritionist") or {}).get("name"),
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
    days, guests = max(1, min(body.days, 7)), max(0, min(body.guests, 20))
    eaters = None if body.eaters is None else [_member(request, k) for k in body.eaters]
    if eaters is not None and not eaters and not guests:
        raise HTTPException(400, "Pick who is eating.")
    try:
        plan = await pl.meal_plan(st.household, st.store, days, body.notes, eaters=eaters, guests=guests)
    except Exception as err:
        raise HTTPException(502, f"Could not plan meals: {err}")
    count = (len(eaters) if eaters is not None else None, guests)
    st.store.remember("home", "mealplan", {**plan, "made": time.time(), "for_days": days,
                                           "eaters": body.eaters, "guests": guests}, "meal planner")
    aid = st.store.add_card(_expert(request, "kitchen").plan_card(plan, days, count).to_dict())
    return {"card": aid, "plan": plan}


class PortionIn(BaseModel):
    day: int
    meal: int
    part: int
    who: str
    qty: float


def _plan(st):
    plan = next((f["value"] for f in st.store.facts("home", "mealplan") if f["key"] == "mealplan"), None)
    if not plan:
        raise HTTPException(409, "Make a meal plan first.")
    return plan


@api.post("/kitchen/mealplan/portion")
def mealplan_portion(body: PortionIn, request: Request):
    """+/- on one food for one person: the plan and their totals update (the cook hears the new quantities)."""
    from app.experts.kitchen import planner as pl
    st = _st(request)
    plan = _plan(st)
    try:
        plan = pl.set_qty(plan, body.day, body.meal, body.part, body.who, body.qty)
    except (IndexError, KeyError):
        raise HTTPException(404, "That part of the plan does not exist.")
    st.store.remember("home", "mealplan", plan, "family")
    return plan


class FitIn(BaseModel):
    day: int
    who: str


@api.post("/kitchen/mealplan/fit")
def mealplan_fit(body: FitIn, request: Request):
    """Scale one person's quantities for a day to their own energy target."""
    from app.experts.family import profiles as P
    from app.experts.kitchen import planner as pl
    st = _st(request)
    plan = _plan(st)
    m = next((x for x in P.members(st.household, st.store) if x["name"] == body.who), None)
    if not m or not 0 <= body.day < len(plan.get("days", [])):
        raise HTTPException(404, "No such person or day in this plan.")
    plan = pl.fit(plan, body.day, body.who, m["targets"]["kcal"])
    st.store.remember("home", "mealplan", plan, "family")
    return plan


@api.post("/kitchen/nutrition")
async def kitchen_nutrition(request: Request):
    from app.experts.kitchen import planner as pl
    st = _st(request)
    try:
        nut = await pl.nutrition(st.store, st.household)
    except Exception as err:
        raise HTTPException(502, f"Could not estimate nutrition: {err}")
    from app.experts.family import profiles as P
    nut["targets"] = P.average(P.members(st.household, st.store))      # each member's own targets, not one reference
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
    who: str = "me"


@api.post("/kitchen/meal")
async def log_meal(body: Meal, request: Request):
    from app.experts.kitchen import pantry
    _member(request, body.who)
    if not body.text.strip():
        raise HTTPException(400, "Say what was eaten.")
    try:
        return await pantry.log_meal(_st(request).store, body.text.strip()[:300], body.meal, who=body.who)
    except Exception as err:
        raise HTTPException(502, f"Could not estimate that meal: {err}")


class MealSlot(BaseModel):
    who: str = "me"
    id: str
    meal: str


@api.put("/kitchen/meal")
def meal_slot(body: MealSlot, request: Request):
    """Change which meal a logged entry was (breakfast, lunch, snack or dinner)."""
    from app.experts.kitchen import pantry
    _member(request, body.who)
    entry = pantry.set_meal(_st(request).store, body.who, body.id, body.meal)
    if not entry:
        raise HTTPException(404 if body.meal in pantry.MEALS else 400, "No such meal, or not breakfast, lunch, snack or dinner.")
    return entry


@api.get("/photos/{pid}")
def photo(pid: str):
    """A scanned photo (key-protected like the rest of /api; <img> tags pass the key as ?key=)."""
    from app.core import photos
    found = photos.find(pid)
    if not found:
        raise HTTPException(404, "No such photo.")
    return FileResponse(found[0], media_type=found[1], headers={"Cache-Control": "private, max-age=86400"})


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
    """Pathya phones the user now (check-in: medicines they listed, meals, reorders)."""
    return {"job": _expert(request, "home").call_me(via=_via(request))}


@api.post("/home/daily")
def home_daily(body: Daily, request: Request):
    return family_daily("me", body, request)


# ---------- family: members, profiles, targets, medicines, check-ins, leaderboard ----------
def _member(request, key):
    from app.experts.family import profiles as P
    st = _st(request)
    try:
        return P.member(st.household, st.store, key)
    except KeyError:
        raise HTTPException(404, "No such family member.")


def _family_view(st, m):
    from app.experts.family import checkups, meds as M
    from app.experts.family import score as health_score
    from app.experts.family import profiles as P
    from app.experts.kitchen import pantry
    home = st.experts.get("home")
    goal, act = m["targets"], activity_today(st.store, m["key"])
    if act and act.get("active_kcal") and not m.get("override"):     # a wearable replaces the activity guess
        base = P.targets({**m, "activity": "sedentary"})
        goal = {**goal, "kcal": round(base["kcal"] + act["active_kcal"]),
                "source": goal["source"] + f" Today: sedentary base + {act['active_kcal']:.0f} active kcal from {act['source']}."}
    phone = m.get("phone") or ""
    verified = twilio_verified(st)
    return {**{k: v for k, v in m.items() if k != "phone"},              # numbers stay on the server
            "phone_hint": f"…{_digits(phone)[-4:]}" if phone else None,
            "verified": None if verified is None or not phone else _digits(phone) in verified,
            "today": pantry.today(st.store, st.household, m["key"], goal=goal), "activity": act,
            "meds": M.listed(st.store, m["key"]), "doses": M.today(st.store, m["key"]),
            "reminders": M.reminders_on(st.store, m["key"]), "daily_hour": home.daily_hour(m["key"]) if home else None,
            "checkups": checkups.for_member(m), "watch": checkups.watch(st.store, m),
            "health": health_score.score(st.store, m, home.daily_hour(m["key"]) if home else None)}


def twilio_verified(st, ttl=60):
    """Numbers a Twilio trial account may call (its verified caller IDs), cached for a minute. None without Twilio."""
    if getattr(st, "twilio", None) is None:
        return None
    cache = getattr(st, "_verified", None)
    if cache and time.time() - cache[0] < ttl:
        return cache[1]
    try:
        nums = {_digits(c.phone_number) for c in st.twilio.outgoing_caller_ids.list(limit=50)}
    except Exception:
        return None
    st._verified = (time.time(), nums)
    return nums


class PhoneIn(BaseModel):
    phone: str


@api.put("/family/{key}/phone")
def family_phone(key: str, body: PhoneIn, request: Request):
    """Add or change a phone number: written into household.yaml (only numbers there are ever called, rule 8)."""
    from app.core.household import set_phone
    st = _st(request)
    m = _member(request, key)
    path = getattr(st, "household_path", None)
    if not path:
        raise HTTPException(503, "household.yaml is not available to edit.")
    try:
        number = set_phone(path, st.household, key, body.phone, m["name"], m.get("relation") or "")
    except ValueError as err:
        raise HTTPException(400, str(err))
    st._verified = None
    st.store.log("family", key, f"phone for {m['name']} set to …{number[-4:]} in household.yaml")
    if "home" in st.experts:
        st.experts["home"].default_daily()
    return _family_view(st, _member(request, key))


@api.post("/family/{key}/verify")
def family_verify(key: str, request: Request):
    """Twilio trial accounts only call verified numbers: Twilio rings the number and asks for this code."""
    st = _st(request)
    m = _member(request, key)
    if st.twilio is None:
        raise HTTPException(503, "Phone calls are not configured.")
    if not m.get("phone"):
        raise HTTPException(400, "Add a phone number first.")
    try:
        v = st.twilio.validation_requests.create(phone_number=m["phone"], friendly_name=f"Pathya {m['name']}")
    except Exception as err:
        raise HTTPException(502, f"Twilio could not start the check: {err}")
    st._verified = None
    return {"code": v.validation_code, "phone_hint": f"…{_digits(m['phone'])[-4:]}"}


@api.get("/family/{key}/report")
def family_report(key: str, request: Request):
    from app.experts.family import report
    st = _st(request)
    m = _member(request, key)
    home = st.experts.get("home")
    return report.text(st.store, st.household, m, home.daily_hour(key) if home else None)


def activity_today(store, key):
    from app.experts.family.meds import day_key
    return next((f["value"] for f in store.facts(key, f"activity:{day_key()}") if f["key"] == f"activity:{day_key()}"), None)


@api.get("/family")
def family(request: Request):
    from app.experts.family import profiles as P
    st = _st(request)
    members = [_family_view(st, m) for m in P.members(st.household, st.store)]
    scored = sorted((v for v in members if v["health"]["score"] is not None), key=lambda v: -v["health"]["score"])
    return {"members": members, "star": scored[0]["name"] if scored else None,
            "about": members[0]["health"]["about"] if members else "", "goals": P.GOALS, "activity": list(P.ACTIVITY)}


class NewMember(BaseModel):
    name: str
    relation: str = ""


@api.post("/family")
def family_add(body: NewMember, request: Request):
    from app.experts.family import profiles as P
    st = _st(request)
    try:
        m = P.add(st.store, st.household, body.name, body.relation)
    except ValueError as err:
        raise HTTPException(400, str(err))
    st.store.log("family", m["key"], f"added {m['name']} to the family")
    return _family_view(st, m)


@api.put("/family/{key}")
def family_save(key: str, body: dict, request: Request):
    from app.experts.family import profiles as P
    st = _st(request)
    _member(request, key)
    try:
        m = P.save(st.store, st.household, key, body)
    except (ValueError, TypeError) as err:
        raise HTTPException(400, str(err))
    if "home" in st.experts:
        st.experts["home"].default_daily()                 # e.g. an age of 60+ was just entered
    return _family_view(st, m)


@api.delete("/family/{key}")
def family_remove(key: str, request: Request):
    from app.experts.family import meds as M
    from app.experts.family import profiles as P
    st = _st(request)
    if not P.remove(st.store, key):
        raise HTTPException(409, "Only members added in the app can be removed; edit household.yaml for the others.")
    M.set_reminders(st.store, None, key, False)
    return {"ok": True}


class MedIn(BaseModel):
    name: str
    dose: str = ""
    times: list[str]
    days: int | None = None
    food: str = ""


@api.post("/family/{key}/meds")
def family_med_add(key: str, body: MedIn, request: Request):
    """A medicine exactly as written on the strip or paper. Pathya only reminds (AGENTS.md rule 9)."""
    from app.experts.family import meds as M
    st = _st(request)
    _member(request, key)
    try:
        M.add(st.store, key, body.name, body.dose, body.times, body.days, body.food)
    except ValueError as err:
        raise HTTPException(400, str(err))
    phone = _expert(request, "home").phone(key)
    for slot in body.times:
        if slot in M.SLOTS:
            M.schedule_next(st.store, phone, key, slot)
    return _family_view(st, _member(request, key))


@api.delete("/family/{key}/meds/{index}")
def family_med_remove(key: str, index: int, request: Request):
    from app.experts.family import meds as M
    st = _st(request)
    _member(request, key)
    if not M.remove(st.store, key, index):
        raise HTTPException(404, "No such medicine.")
    return _family_view(st, _member(request, key))


class MedCheck(BaseModel):
    times: list[str]
    name: str | None = None
    dose: str | None = None
    days: int | None = None
    food: str | None = None


@api.put("/family/{key}/meds/{index}")
def family_med_check(key: str, index: int, body: MedCheck, request: Request):
    """'Matches the paper': the family checked a prescription line and set its times; reminders may now include it."""
    from app.experts.family import meds as M
    st = _st(request)
    m = _member(request, key)
    try:
        med = M.check(st.store, key, index, body.times, body.name, body.dose, body.days, body.food)
    except ValueError as err:
        raise HTTPException(400, str(err))
    if med is None:
        raise HTTPException(404, "No such medicine.")
    st.store.log("family", key, f"{m['name']}: {med['name_as_written']} checked against the paper")
    phone = _expert(request, "home").phone(key)
    if phone and M.reminders_on(st.store, key):
        for slot in body.times:
            if slot in M.SLOTS:
                M.schedule_next(st.store, phone, key, slot)
    return _family_view(st, _member(request, key))


class OnOff(BaseModel):
    on: bool


@api.post("/family/{key}/reminders")
def family_reminders(key: str, body: OnOff, request: Request):
    from app.experts.family import meds as M
    st = _st(request)
    m = _member(request, key)
    phone = _expert(request, "home").phone(key)
    if body.on and not phone:
        raise HTTPException(400, f"{m['name']} has no phone number in household.yaml, so Pathya can't call.")
    jobs = M.set_reminders(st.store, phone, key, body.on)
    return {"ok": True, "on": body.on, "jobs": jobs}


class DoseIn(BaseModel):
    slot: str
    taken: str = "yes"
    words: str = ""


@api.post("/family/{key}/dose")
def family_dose(key: str, body: DoseIn, request: Request):
    """Mark a dose from the app (or after scanning the strip): recorded as the family said it, never judged."""
    from app.experts.family import meds as M
    st = _st(request)
    _member(request, key)
    if body.slot not in M.SLOTS or body.taken not in ("yes", "no", "not_sure"):
        raise HTTPException(400, "slot must be morning, afternoon or night; taken yes, no or not_sure.")
    M.log_dose(st.store, key, body.slot, body.taken, body.words[:200] or "marked in the app")
    return _family_view(st, _member(request, key))


class ActivityIn(BaseModel):
    steps: int = 0
    active_kcal: float = 0
    source: str = "wearable"


@api.post("/activity/{key}")
def activity(key: str, body: ActivityIn, request: Request):
    """Today's activity from a wearable (Apple Watch via an iPhone Shortcut, or any app that can POST JSON)."""
    from app.experts.family.meds import day_key
    st = _st(request)
    _member(request, key)
    if not (0 <= body.steps <= 150000 and 0 <= body.active_kcal <= 8000):
        raise HTTPException(400, "Those numbers look wrong.")
    st.store.remember(key, f"activity:{day_key()}", {"steps": body.steps, "active_kcal": body.active_kcal,
                                                     "source": body.source[:40], "ts": time.time()}, body.source[:40])
    return {"ok": True}


def _taken_at(taken, now=None):
    """When the photo was taken (ms since epoch, from the phone: EXIF or the file's time). Within the last 7 days,
    else now (so a wrong clock or an old gallery photo never lands on a strange day)."""
    now = now or time.time()
    try:
        ts = float(taken) / 1000
    except (TypeError, ValueError):
        return now
    return ts if now - 7 * 86400 <= ts <= now + 600 else now


@api.post("/scan")
async def scan_photo(request: Request, who: str = Form("me"), hint: str = Form(""), taken: str = Form(""),
                     photo: UploadFile = File(...)):
    """One photo: a meal is logged for that person (as breakfast, lunch, snack or dinner from when the photo was taken);
    a medicine, prescription or body report comes back for a human to confirm (nothing is scheduled or saved from it
    until they do). The photo is kept so the family can look at it again."""
    from app.core import photos
    from app.experts.family import meds as M
    from app.experts.family import scan
    from app.experts.kitchen import pantry
    st = _st(request)
    _member(request, who)
    image, mime = await photo.read(), photo.content_type or "image/jpeg"
    if len(image) > 12 * 1024 * 1024:
        raise HTTPException(413, "That photo is too large (12 MB max).")
    try:
        seen = await asyncio.to_thread(scan.look, image, mime, hint[:40])
    except Exception as err:
        raise HTTPException(502, f"Could not read the photo: {err}")
    pid = photos.save(image, mime) if seen["kind"] in ("meal", "prescription") else None
    st.store.log("family", who, f"scanned a photo: {seen['kind']}")
    if seen["kind"] == "meal" and seen.get("meal"):
        meal = seen["meal"]

        async def as_seen(text):
            return {k: meal[k] for k in ("kcal", "protein_g", "carbs_g", "fat_g", "fibre_g", "sugar_g")}
        entry = await pantry.log_meal(st.store, meal["description"][:300], "", who=who, estimate=as_seen,
                                      now=_taken_at(taken), photo=pid)
        return {"kind": "meal", "entry": entry, "note": seen["note"], "photo": pid}
    if seen["kind"] == "medicine":
        listed = M.listed(st.store, who)
        return {"kind": "medicine", "medicines": seen["medicines"], "note": seen["note"],
                "matches": [listed[i]["name_as_written"] for i in scan.matches(seen["medicines"], listed)],
                "due": M.today(st.store, who)}
    if seen["kind"] == "prescription":
        from app.experts.health.rx import read_prescription
        try:
            rx = await asyncio.to_thread(read_prescription, image, mime)
        except Exception as err:
            photos.delete(pid)
            raise HTTPException(502, f"Could not read the prescription: {err}")
        card = _expert(request, "health").meds_card(who, rx, pid)
        return {"kind": "prescription", "card": st.store.add_card(card.to_dict()), "note": seen["note"], "photo": pid,
                "count": len(rx.get("meds", []))}
    if seen["kind"] == "body_report" and seen.get("report"):
        return {"kind": "body_report", "report": seen["report"], "note": seen["note"]}
    return {"kind": "other", "note": seen["note"]}


@api.post("/family/{key}/call")
def family_call(key: str, request: Request):
    """Check-in call now: medicines as written, meals, groceries, one dish idea."""
    _member(request, key)
    try:
        return {"job": _expert(request, "home").call(key, via=_via(request))}
    except ValueError as err:
        raise HTTPException(400, str(err))


@api.post("/family/{key}/daily")
def family_daily(key: str, body: Daily, request: Request):
    home = _expert(request, "home")
    _member(request, key)
    if body.hour is None:
        home.turn_off_daily(key)
        return {"ok": True, "hour": None}
    if not 6 <= body.hour <= 22:
        raise HTTPException(400, "Pick an hour between 6 and 22.")
    try:
        return {"ok": True, "hour": body.hour, "job": home.daily(body.hour, key)}
    except ValueError as err:
        raise HTTPException(400, str(err))


@api.post("/health/book")
def health_book(body: Booking, request: Request):
    hh = _st(request).household
    _person(request, body.patient)
    if body.clinic not in hh["clinics"]:
        raise HTTPException(404, f"{body.clinic} is not in household.yaml.")
    jid = _expert(request, "health").book(body.patient, body.clinic, body.window_start, body.window_end,
                                          None if body.part == "any" else body.part, body.reason, via=_via(request))
    return {"job": jid}


@api.post("/health/intake/{who}")
def health_intake(who: str, request: Request):
    """Hand it over: Pathya calls and asks what is needed, then proposes the booking (one tap before any clinic call)."""
    _member(request, who)
    try:
        return {"job": _expert(request, "health").intake(who, via=_via(request))}
    except ValueError as err:
        raise HTTPException(400, str(err))


class BookRequest(BaseModel):
    patient: str = "me"
    hospital: str = ""
    doctor: str = ""
    area: str = ""
    reason: str = ""
    from_date: str = ""
    to_date: str = ""
    part: str = "any"


@api.post("/health/request")
def health_request(body: BookRequest, request: Request):
    """'I know where': a hospital or doctor by name (saved or not). Saved ones are phoned after a tap; others are found
    on the web first, and added to household.yaml only after another tap."""
    m = _member(request, body.patient)
    card = _expert(request, "health").request_card({**body.model_dump(), "patient": m["name"], "patient_key": m["key"],
                                                    "from": body.from_date, "to": body.to_date})
    return {"card": _st(request).store.add_card(card.to_dict())}


@api.post("/health/checkin/{person}")
def health_checkin(person: str, body: Checkin, request: Request):
    if person != "me":
        _person(request, person)
    return {"job": _expert(request, "health").checkin(person, body.purpose, via=_via(request))}


@api.post("/health/rx")
async def health_rx(request: Request, patient: str = Form(...), photo: UploadFile = File(...)):
    from app.core import photos
    from app.experts.health.rx import read_prescription
    _member(request, patient)
    image, mime = await photo.read(), photo.content_type or "image/jpeg"
    try:
        rx = await asyncio.to_thread(read_prescription, image, mime)
    except Exception as err:
        raise HTTPException(502, f"Could not read the prescription: {err}")
    card = _expert(request, "health").meds_card(patient, rx, photos.save(image, mime))
    return {"card": _st(request).store.add_card(card.to_dict())}


class PharmacyFind(BaseModel):
    who: str = "me"
    lat: float | None = None
    lng: float | None = None
    area: str = ""
    meds: list[int] | None = None          # indexes into the member's medicines; None = all
    via: str | None = None                 # "browser": the pharmacy call rings in the app (Calls ring on: This browser)


@api.post("/health/pharmacy")
async def health_pharmacy(body: PharmacyFind, request: Request):
    """Pharmacies near the family's location (shared once in the app) for this member's medicines, as a card. Pathya
    phones one only after a tap, and only asks: it never orders, never accepts a substitute (rule 9)."""
    from app.experts.family import meds as M
    from app.experts.health import pharmacy
    st = _st(request)
    m = _member(request, body.who)
    listed = M.listed(st.store, body.who)
    chosen = [x for i, x in enumerate(listed) if (body.meds is None or i in body.meds) and not x.get("unclear")]
    if not chosen:
        raise HTTPException(400, f"No medicines to order for {m['name']}: scan the prescription, or check the flagged "
                                 "lines against the paper first.")
    if (body.lat is None or body.lng is None) and not body.area.strip():
        raise HTTPException(400, "Share your location, or type the area.")
    photo = next((x.get("photo") for x in chosen if x.get("photo")), None)
    meds = [M.line(x) for x in chosen]

    async def search():
        """In the background: a careful web search takes about a minute (longer than a tunnel waits for a reply)."""
        try:
            found = await asyncio.to_thread(pharmacy.find, body.lat, body.lng, body.area.strip()[:80],
                                            st.household.get("city", "Hyderabad"))
        except Exception as err:
            found, why = None, f"The search failed: {str(err)[:200]}"
        else:
            why = f"No pharmacy with a listed phone number near {found['area']}. Try typing the area."
        if found and found["pharmacies"]:
            st.store.add_card(_expert(request, "health").pharmacies_card(body.who, found, meds, photo,
                                                                          "browser" if body.via == "browser" else None).to_dict())
            st.store.log("health", body.who, f"found {len(found['pharmacies'])} pharmacies near {found['area']}")
        else:
            _call_problem(st.store, "No pharmacy found", why)
    st.tasks.add(t := asyncio.create_task(search()))
    t.add_done_callback(st.tasks.discard)
    st.store.log("health", body.who, f"looking for pharmacies for {m['name']}'s medicines")
    return {"searching": True, "medicines": len(meds)}


@api.get("/health/pharmacy/links")
def health_pharmacy_links(request: Request, who: str = "me"):
    """Order it yourself: a search link per medicine in Tata 1mg, Apollo 24|7 and PharmEasy (no prices fetched)."""
    from app.experts.family import meds as M
    from app.experts.health import pharmacy
    _member(request, who)
    return pharmacy.links(M.listed(_st(request).store, who))


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
        result = await expert.execute(card, body.choice) if expert else {"ok": True}   # e.g. "call did not connect"
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
    from app.core import photos
    st = _st(request)
    row = st.store.card(aid)
    if not st.store.reject(aid):
        raise HTTPException(409, "This card was already handled.")
    if row and row["card"]["kind"] == "meds":                 # a prescription nobody confirmed: its photo goes too
        photos.delete(row["card"]["payload"].get("photo"))
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
    who = hh["people"].get(job["person"]) or hh["clinics"].get(job["person"]) or (hh.get("pharmacies") or {}).get(job["person"]) or {}
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
    plan.voice = _voice_for(st, job)
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
                          "phone": (job.get("result") or {}).get("call_sid") not in (None, "browser"),
                          "lines": lines}


class Line(BaseModel):
    role: str
    text: str


@api.post("/calls/{jid}/line")
def call_line(jid: str, body: Line, request: Request):
    """A line of a browser call's transcript (the home screen shows it live). For the person's lines, a note to send
    into the call when they switched language (app/core/lang.py)."""
    st = _st(request)
    live = st.live.get(jid)
    if live is not None and body.role in ("ai", "them", "tool"):
        live["lines"].append({"role": body.role, "text": body.text[:500]})
    call = st.calls.get(jid)
    return {"ok": True, "note": call.follow.note(body.text) if call and body.role == "them" else None}


@api.get("/calls/{jid}/greeting")
def call_greeting(jid: str, request: Request):
    call = _live(request, jid)
    return {"greeting": call.plan.greeting, "max_minutes": call.plan.max_minutes}


@api.post("/calls/{jid}/tool")
async def call_tool(jid: str, body: ToolCall, request: Request):
    call = _live(request, jid)
    out = await call.run_tool(body.name, body.arguments)
    _st(request).store.log(call.expert.name, jid, f"{body.name} -> {out}")   # refusals show on the timeline
    from app.core.convo import ends_call
    return {"output": out, "end": ends_call(body.name, out)}


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


@api.post("/calls/{jid}/hangup")
async def call_hangup(jid: str, request: Request):
    """The red button for a phone call shown live in the app: Twilio by REST, Exotel by closing its stream."""
    st = _st(request)
    job = st.store.job(jid)
    if not job or jid not in st.live:
        raise HTTPException(409, "That call is not live.")
    sid = (job.get("result") or {}).get("call_sid")
    closer = st.hangups.get(jid)
    if closer:
        await closer()
    elif st.twilio is not None and sid and sid != "browser":
        from app.core.caller import hang_up
        await asyncio.to_thread(hang_up, st.twilio, sid)
    else:
        raise HTTPException(409, "Browser calls end on their own call screen.")
    st.store.log("caller", jid, "hung up from the app")
    return {"ok": True}


@api.post("/calls/{jid}/decline")
def call_decline(jid: str, request: Request):
    """Decline a call ringing in the app: it stops ringing (it does not count as answered)."""
    st = _st(request)
    if not st.store.job(jid):
        raise HTTPException(404, "No such call.")
    st.store.remember("app", f"declined:{jid}", True, "app")
    st.store.log("caller", jid, "declined in the app")
    return {"ok": True}


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
    plan = expert.call_plan(job)
    plan.voice = _voice_for(st, job)
    call = Call(job, expert, plan)
    st.calls[jid] = call
    _go_live(st, call, lines if lines is not None else [])
    st.store.log(expert.name, jid, f"{_who(st.household, job['person'])} on the phone, limit {call.plan.max_minutes} min")
    return call


def _digits(n):
    return "".join(c for c in str(n or "") if c.isdigit())[-10:]


def _person_by_phone(hh, number):
    return next((k for k, p in hh["people"].items() if _digits(p.get("phone")) and _digits(p.get("phone")) == _digits(number)),
                None)


def _answer_forwarded(st, caller, call_sid):
    """A call to the user's own phone that their phone forwarded to the Exotel number: the Doorstep Expert answers
    (it is there for the delivery partner). Someone from household.yaml is greeted by name and leaves a message."""
    person = _person_by_phone(st.household, caller)
    name = st.household["people"][person]["name"] if person else None
    jid = st.experts["doorstep"].answered(call_sid, _digits(caller)[-4:], name)
    st.store.log("caller", jid, f"forwarded call from {name or 'an unknown number'} (Doorstep)")
    return jid


def _answer_incoming(st, caller, call_sid):
    """Someone phoned Pathya: the user and family members get the Family line (orders, food, medicines), the cook
    the Kitchen list call, anyone else the Doorstep Expert."""
    if "home" in st.experts and _digits(caller) and _digits(caller) == _digits(st.household["user"].get("phone")):
        jid = st.experts["home"].answered(call_sid)
        st.store.log("caller", jid, f"incoming call from {st.household['user']['name']} (Family line)")
        return jid
    person = _person_by_phone(st.household, caller)
    if person and "home" in st.experts and st.household["people"][person].get("role") != "cook":
        jid = st.experts["home"].answered(call_sid, person)
    elif person and "kitchen" in st.experts:
        jid = st.experts["kitchen"].answered(person, call_sid)
    else:
        jid = st.experts["doorstep"].answered(call_sid, "".join(c for c in str(caller or "") if c.isdigit())[-4:])
    st.store.log("caller", jid, f"incoming call from {_who(st.household, person) if person else 'an unknown number'}")
    return jid


def _call_problem(store, title, hint):
    from app.experts.base import Card
    store.add_card(Card("caller", "info", title, [hint], question="", choices=[{"id": "ok", "label": "OK"}]).to_dict())


TRIAL_HINT = ("The call connected but the AI never started. On a Twilio trial account the person hears a trial message "
              "and must press any key before Pathya speaks. Add funds to Twilio to remove it.")


async def _check_stream_started(st, jid, who, wait=5):
    """Twilio says 'completed' but no audio stream ever reached us: almost always the trial key press."""
    await asyncio.sleep(wait)
    if jid not in st.calls and not st.store.facts(prefix=f"call:{jid}"):
        _call_problem(st.store, f"Call to {who}: nobody pressed a key", TRIAL_HINT)


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

    app = FastAPI(title="Pathya Experts", lifespan=lifespan)
    app.include_router(api)

    @app.middleware("http")
    async def need_key(request: Request, call_next):
        """APP_KEY set (phone mode sets it): the app's API needs it, or a phone sign-in session (app/core/auth.py),
        so a public tunnel URL alone is not enough. Signing in itself is open. Twilio and Exotel routes have their own
        checks (signature, Basic auth)."""
        from app.core import auth
        key = os.getenv("APP_KEY", "")
        path = request.url.path
        if key and path.startswith("/api/") and request.method != "OPTIONS" and path not in OPEN_PATHS:
            given = request.headers.get("x-quickpick-key") or request.query_params.get("key") or ""
            if not hmac.compare_digest(given.encode(), key.encode()) and not auth.session(request.app.state.store, given):
                return JSONResponse({"detail": "Pathya key needed."}, status_code=401)
        return await call_next(request)

    # The UI may be hosted elsewhere (Vercel) and call this server through the tunnel.
    app.add_middleware(CORSMiddleware, allow_origin_regex=os.getenv("CORS_ORIGINS", r"https://[a-z0-9-]+\.vercel\.app"),
                       allow_methods=["*"], allow_headers=["*"])

    @app.post("/calls/status")
    async def call_status(request: Request):
        form = await request.form()
        st = request.app.state
        store = st.store
        status, sid = form.get("CallStatus", ""), form.get("CallSid", "")
        store.log("caller", sid, f"call {status} ({form.get('CallDuration', '0')} s)")
        job = next((j for j in store.recent_jobs(time.time() - 3600)
                    if isinstance(j.get("result"), dict) and j["result"].get("call_sid") == sid), None)
        if not job:
            return PlainTextResponse("")
        who = _who(st.household, job["person"])
        if status == "failed" and job["person"] == "me" and job["payload"].get("via") != "browser":
            again = store.add_job(job["expert"], job["kind"], "me", {**job["payload"], "via": "browser"})
            _call_problem(store, f"Your phone (…{_digits(job['payload'].get('to'))[-4:]}) refused the call, so it is ringing in the app",
                          "Jio does not take calls from Twilio's US number. Tap Answer in the app this time. For real "
                          "phone calls, put a non-Jio number (Airtel, Vi, BSNL) in Family > You > Phone.")
            store.log("caller", again, "re-ringing in the app after the phone refused")
            return PlainTextResponse("")
        if status in ("failed", "busy", "no-answer", "canceled"):          # say so in the app, not only in the log
            hint = ("The phone network refused the call. Jio blocks international numbers; try another number, "
                    "or set 'Calls ring on: This browser'.") if status == "failed" else "Nobody answered."
            _call_problem(store, f"Call to {who} did not connect ({status})", hint)
        elif status == "completed":
            st.tasks.add(t := asyncio.create_task(_check_stream_started(st, job["id"], who)))
            t.add_done_callback(st.tasks.discard)
        return PlainTextResponse("")

    @app.post("/calls/incoming")
    async def call_incoming(request: Request):
        """Twilio voice webhook for the Pathya number. Household members get the Kitchen list call;
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
        st.store.log("caller", "exotel", "Exotel stream connected")
        jid, lines = {}, []

        def call_for_start(msg):
            info = Exotel().start(msg)
            st.store.log("caller", "exotel", f"Exotel call from …{_digits(info['from'])[-4:]}")
            job_id = _answer_forwarded(st, info["from"], info["call"])
            call = _phone_call_for_start(st, {"event": "start", "start": {"callSid": info["call"],
                                                                         "customParameters": {"job_id": job_id}}}, lines)
            jid["id"] = job_id
            st.hangups[job_id] = ws.close                       # the app's red button
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
            st.hangups.pop(jid.get("id"), None)
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
    import mimetypes
    mimetypes.add_type("application/manifest+json", ".webmanifest")

    @app.get("/pathya.apk", include_in_schema=False)
    def android_app():
        """The Android app: a launcher that opens this server's link (no key or secret inside). mobile/build-apk.ps1."""
        if not APK.is_file():
            raise HTTPException(404, "The Android app is not built yet: run mobile/build-apk.ps1.")
        return FileResponse(APK, media_type="application/vnd.android.package-archive", filename="Pathya.apk")

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
    app.state.hangups = {}
    app.state.voice_cache = {}
    app.state.sign_in_sent = {}
    app.state.household_path = None
    return app


async def _keep_trying_swiggy(store, kitchen, delay=90):
    """Swiggy refused at start-up (often HTTP 429): retry in the background instead of staying offline until a restart.
    The bridges live in this task, so they are opened and closed by the same task."""
    from app.experts.kitchen import swiggy as sw
    while kitchen.ops is None:
        await asyncio.sleep(delay)
        try:
            async with sw.bridge("im-agent", sw.AGENT_TOOLS) as agent_im, sw.bridge("im-ops") as ops:
                kitchen.agent_im, kitchen.ops = agent_im, ops
                store.log("app", "swiggy", "Swiggy Instamart connected (retry)")
                try:
                    await asyncio.Event().wait()
                finally:
                    kitchen.agent_im = kitchen.ops = None
        except asyncio.CancelledError:
            raise
        except Exception as err:
            store.log("app", "swiggy", f"Swiggy still not connected: {str(err)[:120]}")
            delay = min(delay * 2, 600)


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
        if ops is None:
            app.state.tasks.add(asyncio.create_task(_keep_trying_swiggy(store, REGISTRY["kitchen"])))
        register(HealthExpert(store, hh, os.getenv("HOUSEHOLD", str(ROOT / "household.yaml"))))
        from app.experts.doorstep.expert import DoorstepExpert
        from app.experts.home.expert import HomeExpert
        register(DoorstepExpert(store, hh))
        register(HomeExpert(store, hh, REGISTRY["kitchen"]))
        REGISTRY["home"].default_daily()                    # parents: evening check-in on unless switched off
        app.state.store, app.state.household, app.state.experts = store, hh, REGISTRY
        app.state.household_path = os.getenv("HOUSEHOLD", str(ROOT / "household.yaml"))
        if twilio_ready():
            from twilio.rest import Client
            app.state.twilio = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
            store.log("caller", "setup", f"phone calls via Twilio {os.environ['TWILIO_FROM']} "
                                         f"(stream: wss://{os.environ['PUBLIC_HOST']}/media-stream)")
        dispatch = J.make_dispatch(store, REGISTRY, make_dialer(store, app.state.twilio))
        scheduler = asyncio.create_task(J.run_forever(store, dispatch, every=5))
        from app.core import tracker
        tracking = asyncio.create_task(tracker.run_forever(store, REGISTRY["kitchen"], every=60))
        store.log("app", "start", f"Pathya started (DRY_RUN={os.getenv('DRY_RUN', '1')})")
        try:
            yield
        finally:
            scheduler.cancel()
            tracking.cancel()
            for t in list(app.state.tasks):
                t.cancel()


app = build_app(lifespan)
