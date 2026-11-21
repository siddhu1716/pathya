"""Logic checks for the v2 platform with stand-ins (no network, no real orders, no real calls)."""
import asyncio, os, sys, time, types
from datetime import datetime, timedelta, timezone

ag = types.ModuleType("agents"); ag.Agent = object; ag.Runner = object
mcp = types.ModuleType("agents.mcp"); mcp.MCPServerStdio = object; mcp.create_static_tool_filter = lambda **k: k
sys.modules.setdefault("agents", ag); sys.modules.setdefault("agents.mcp", mcp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import caller as C, jobs as J, safety as S
from app.core.store import Store
from app.experts.base import Card, register
from app.experts.family import meds as M
from app.experts.health.expert import IST, HealthExpert, make_ics
from app.experts.kitchen import swiggy as sw
from app.experts.kitchen.expert import KitchenExpert

HH = {"user": {"name": "Shiva", "phone": "+919800000000"},
      "people": {"amma": {"name": "Amma", "language": "Telugu", "phone": "+919800000001", "age": 60, "clinic": "rao"},
                 "lakshmi": {"name": "Lakshmi garu", "language": "Telugu", "phone": "+919800000002"}},
      "clinics": {"rao": {"doctor": "Dr. Rao", "clinic": "Sunrise Clinic, Gachibowli", "phone": "+919800000003"}},
      "address_hint": "Loft"}
tools = lambda plan: {f.__name__: f for f in plan.tools}
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M")

# 1. approvals: double tap, failed never reopens
st = Store(":memory:")
aid = st.add_card(Card("kitchen", "order", "Cart", ["milk"]).to_dict())
c1, c2 = st.claim(aid, "COD"), st.claim(aid, "COD")
assert c1["title"] == "Cart" and c2 is None
st.finish(aid, False, "boom")
assert st.card(aid)["status"] == "failed" and st.claim(aid, "COD") is None and not st.reject(aid)

# 2. jobs + scheduler + dispatch
health = HealthExpert(st, HH)
fid = st.add_job("health", "followup", "amma", {"patient": "amma", "doctor": "Dr. Rao", "after_days": 14}, time.time() + 3600)
assert st.due() == [] and st.run_now(fid) and [j["id"] for j in st.due()] == [fid]
dialed = []
dispatch = J.make_dispatch(st, {"health": health}, lambda to, job_id: dialed.append((to, job_id)) or "CA1")
assert asyncio.run(J.tick(st, dispatch)) == [fid] and st.job(fid)["status"] == "done"
assert any(c["card"]["kind"] == "followup" for c in st.cards())
cid = health.checkin("amma", "test call")
asyncio.run(J.tick(st, dispatch))
assert dialed == [("+919800000001", cid)] and st.job(cid)["result"] == {"call_sid": "CA1"}
bad = st.add_job("nobody", "x", "y", {}, 0)
asyncio.run(J.tick(st, dispatch))
assert st.job(bad)["status"] == "failed"

# 3. caller
tw = C.stream_twiml("abc.ngrok-free.app", "job42")
assert '<Stream url="wss://abc.ngrok-free.app/media-stream">' in tw and '<Parameter name="job_id" value="job42" />' in tw
class Calls:
    def create(self, **kw): self.kw = kw; return types.SimpleNamespace(sid="CA9")
tc = types.SimpleNamespace(calls=Calls())
assert C.make_dial(tc, "+15550001111", "abc.ngrok-free.app", 4)("+919800000001", "job42") == "CA9"
assert tc.calls.kw["time_limit"] == 240 and tc.calls.kw["from_"] == "+15550001111" and "job42" in tc.calls.kw["twiml"]
assert C.job_id_from_start({"event": "start", "start": {"customParameters": {"job_id": "job42"}}}) == "job42"
assert C.job_id_from_start({"event": "media"}) is None

# 4. safety
os.environ.pop("GUARDRAIL_ID", None)
assert S.check("hello").status == "unchecked"
class G:
    def __init__(self, act): self.act = act
    def apply_guardrail(self, **kw):
        self.kw = kw
        return {"action": self.act, "outputs": [{"text": "Held for review: please ask the doctor."}]}
os.environ["GUARDRAIL_ID"] = "gr-1"
g = G("NONE"); v = S.check("Amma said she feels dizzy", client=g)
assert v.status == "passed" and g.kw["source"] == "OUTPUT" and g.kw["content"][0]["text"]["text"].startswith("Amma")
v = S.check("Take two tablets", client=G("GUARDRAIL_INTERVENED"))
assert v.status == "blocked" and v.text.startswith("Held")
os.environ.pop("GUARDRAIL_ID")

# 5. health: booking window enforced in code
st2 = Store(":memory:"); h = HealthExpert(st2, HH)
base = (datetime.now(IST) + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
good = (base + timedelta(days=1)).replace(hour=10, minute=30)
late, outside = good.replace(hour=16), (base + timedelta(days=6)).replace(hour=10)
jid = h.book("amma", "rao", base.isoformat(), (base + timedelta(days=5)).isoformat(), "morning", "BP review")
job = st2.job(jid); plan = h.call_plan(job); t = tools(plan)
assert job["payload"]["to"] == "+919800000003" and "AI assistant" in plan.instructions and "Sunrise Clinic" in plan.instructions
assert t["offer_slots"]([iso(late), iso(outside)]).startswith("None fit")
assert iso(good) in t["offer_slots"]([iso(good), iso(late)])
assert t["book_slot"](iso(late), "", "", "").startswith("Refused")
assert t["book_slot"]("tomorrow 10", "", "", "").startswith("Refused")
assert t["book_slot"](iso(good), "Dr. Rao", "Rs 500", "old reports").startswith("Booked")
assert t["book_slot"](iso(outside), "", "", "").startswith("Already")
card = asyncio.run(h.after_call(job, plan.saved))
assert card.kind == "booking" and card.lines[0].startswith(good.strftime("%a %d %b, %I:%M %p"))
assert "DTSTART:" + good.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") in card.payload["ics"]
assert "LOCATION:Sunrise Clinic\\, Gachibowli" in card.payload["ics"]
out = asyncio.run(h.execute(card.to_dict(), "remind"))
j1, j2 = (st2.job(x) for x in out["jobs"])
assert abs(j1["run_at"] - (good - timedelta(days=1)).replace(hour=19, minute=0).timestamp()) < 1
assert abs(j2["run_at"] - (good + timedelta(hours=3)).timestamp()) < 1 and j1["kind"] == "checkin"

# 6. health: hold -> call back for that exact slot
hold = asyncio.run(h.after_call(job, {"held": {"slot": iso(late), "note": "only 4 pm"}, "summary": "x"}))
o3 = asyncio.run(h.execute(hold.to_dict(), "confirm")); t3 = tools(h.call_plan(st2.job(o3["jobs"][0])))
assert t3["book_slot"](iso(good), "", "", "").startswith("Refused") and t3["book_slot"](iso(late), "", "", "").startswith("Booked")

# 7. health: check-in, emergency alert, doctor brief (no advice, her words)
cj = st2.job(h.checkin("amma", "Remind her of the appointment")); cp = h.call_plan(cj); ct = tools(cp)
assert "never give medical advice" in cp.instructions and "108" in cp.instructions
ct["save_checkin"]("okay", ["headache"], "2 days", ["BP 150/95"], "yes", ["Can I walk in the morning?"],
                   "Talanoppi rendu rojula nunchi", "Headache for two days")
ct["alert_family"]("She says she feels faint")
assert any(c["card"]["kind"] == "alert" for c in st2.cards())
brief = asyncio.run(h.after_call(cj, cp.saved)); text = "\n".join(brief.lines)
assert brief.kind == "brief" and "Talanoppi" in text and "BP 150/95" in text and "Can I walk" in text
assert brief.payload["safety"] == "unchecked" and brief.payload["wa"].startswith("https://wa.me/919800000003?text=")

# 8. health: prescription -> confirm -> reminders, advice for the Kitchen, follow-up booking
rx = {"doctor": "Dr. Rao", "date": "2026-11-24", "review_after_days": 14, "unreadable_parts": ["line 3"],
      "advice_as_written": ["Low salt diet"],
      "meds": [{"name_as_written": "Tab. ABC 40", "strength": "40 mg", "dose": "1", "morning": True, "afternoon": False,
                "night": False, "food": "after food", "days": 30, "unclear": False},
               {"name_as_written": "Tab. ???", "strength": None, "dose": None, "morning": False, "afternoon": False,
                "night": False, "food": None, "days": None, "unclear": True}]}
mc = h.meds_card("amma", rx)
assert any("pharmacist" in w for w in mc.warnings) and any("Could not read" in w for w in mc.warnings)
assert st2.facts("amma", "meds") == []
out = asyncio.run(h.execute(mc.to_dict(), "confirm"))
assert [f["value"] for f in st2.facts("amma", "advice:")] == ["Low salt diet"]
assert sorted(st2.job(j)["kind"] for j in out["jobs"]) == ["followup", "meds"]      # daily reminder + review
mj = next(st2.job(j) for j in out["jobs"] if st2.job(j)["kind"] == "meds")
assert mj["expert"] == "home" and mj["payload"]["slot"] == "morning"
saved = st2.facts("amma", "meds")[0]["value"]
assert [m["name_as_written"] for m in saved] == ["Tab. ABC 40", "Tab. ???"] and saved[1]["unclear"]   # kept as written
assert [m["name_as_written"] for m in M.active(saved, "morning")] == ["Tab. ABC 40"]      # unclear lines are not scheduled
assert "1 need a check" in out["message"]
fj = next(st2.job(j) for j in out["jobs"] if st2.job(j)["kind"] == "followup")
fc = asyncio.run(h.run_task(fj)); bj = st2.job(asyncio.run(h.execute(fc.to_dict(), "book"))["jobs"][0])
assert bj["kind"] == "book" and bj["payload"]["part"] == "morning" and bj["payload"]["to"] == "+919800000003"

# 9. kitchen: card follows Swiggy's rules; DRY_RUN never checks out; real path checks out once
class T:
    def __init__(self, x): self.type, self.text = "text", x
class R:
    def __init__(self, sc=None, x=""): self.structuredContent, self.content, self.isError = sc, [T(x)], False
class Ops:
    def __init__(self, script): self.script, self.calls = script, []
    async def call_tool(self, name, args):
        self.calls.append((name, args)); v = self.script[name]
        return v.pop(0) if isinstance(v, list) else v
CART = {"items": [{"itemName": "Heritage Toned Milk", "itemVariant": "500 ml", "quantity": 2, "discountedFinalPrice": 56, "storeId": "s1"},
                  {"itemName": "Tata Salt Lite", "itemVariant": "1 kg", "quantity": 1, "discountedFinalPrice": 45, "storeId": "s2"}],
        "billBreakdown": {"toPay": {"value": "\u20b9131"}}, "selectedAddressDetails": {"address": "RMZ The Loft, Raidurg"}}
PAY = {"cod": {"available": True}, "platforms": {"mobile": {"methods": [{"id": "gpay", "displayName": "Google Pay"}]}}}
seen = {}
async def fake_build(agent_im, text, address_id): seen["text"] = text; return "All found."
async def fake_pick(ops, hint=None): seen["hint"] = hint; return {"id": "addr1", "addressLine": "RMZ The Loft"}
sw.build_cart, sw.pick_address = fake_build, fake_pick
st3 = Store(":memory:"); st3.remember("amma", "advice:0", "Low salt diet", "prescription")
ops = Ops({"get_cart": R(CART), "get_payment_options": R(PAY),
           "checkout": R({"orderId": "O1", "status": "CONFIRMED"}, "Instamart order placed successfully")})
k = KitchenExpert(st3, HH, None, ops)
card = asyncio.run(k.handle("2 milk, 1 salt"))
assert "Low salt diet" in seen["text"] and seen["hint"] == "Loft"
assert card.question == "Do you want to proceed with placing this order to this address?"
assert [c["id"] for c in card.choices] == ["COD", "UPI:gpay"] and card.address == "RMZ The Loft, Raidurg"
assert card.lines[0] == "Heritage Toned Milk 500 ml x2 - Rs 56" and any("2 stores" in w for w in card.warnings)
assert card.payload["approved_total"] == 131
os.environ["DRY_RUN"] = "1"
assert asyncio.run(k.execute(card.to_dict(), "COD"))["dry_run"] and not [n for n, _ in ops.calls if n == "checkout"]
os.environ["DRY_RUN"] = "0"
res = asyncio.run(k.execute(card.to_dict(), "COD"))
assert res["message"] == "Instamart order placed successfully" and "080-67466729" in res["cancel"]
assert [a for n, a in ops.calls if n == "checkout"] == [{"addressId": "addr1", "paymentMethod": "Cash"}]
lp = k.call_plan(st3.job(k.weekly_call("lakshmi")))
assert "Lakshmi garu" in lp.greeting and "AI assistant" in lp.instructions
tools(lp)["save_list"](["2 litres paalu", "1 kg kandi pappu"], "")
assert asyncio.run(k.after_call({"id": "j1"}, lp.saved)).kind == "order" and "paalu" in seen["text"]

# 10. registry
register(k)
try:
    register(k); raise AssertionError("duplicate allowed")
except ValueError:
    pass
print("ALL V2 CHECKS PASSED")
