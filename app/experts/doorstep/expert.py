"""Doorstep Expert: answers calls to the household's QuickPick number from people who are not in household.yaml,
usually the delivery partner. It knows only what is on the way and the family's own delivery instructions,
guides the partner in, never shares an OTP, payment detail or ID, and leaves the family a card."""
from app.core import convo, lang
from app.experts.base import CallPlan, Card, Expert

DOORSTEP_CALL = """You are QuickPick, an AI assistant answering {user}'s phone. Your first sentence: "{greeting}"
{speak} Use short, friendly sentences. Never pretend to be human.
Most callers are delivery partners. What you know:
- On the way to {user}: {orders}
- {user}'s delivery instructions: {instructions}
Help a delivery partner reach {user} using only those instructions. Never read out order numbers or IDs.
If they ask for an OTP, say {user} will share it at the door. Never share an OTP, payment or card details,
never agree to pay anything, and never change or cancel an order.
If they are outside, lost or need {user} now, call notify_owner. If the caller is not a delivery partner, take a short
message with take_message. Keep the call under two minutes. Finish with end_call."""

DEFAULT_INSTRUCTIONS = "Please call again; the family will come down to collect it."


class DoorstepExpert(Expert):
    name, title = "doorstep", "Doorstep Expert"
    handles = "incoming calls from delivery partners and unknown callers"
    call_kinds = {"doorstep"}

    def __init__(self, store, household):
        self.store, self.hh = store, household

    def answered(self, call_sid, caller_last4):
        """An incoming call becomes a job that has already 'run' (so the scheduler never dials it)."""
        jid = self.store.add_job(self.name, "doorstep", "caller",
                                 {"direction": "inbound", "caller": f"…{caller_last4}"}, run_at=4102444800)
        self.store.start_job(jid)
        self.store.end_job(jid, True, {"call_sid": call_sid})
        return jid

    def on_the_way(self):
        rows = self.store.orders(active=True)
        if not rows:
            return "nothing we know of"
        return "; ".join(f"a {o['store'].title()} order of {len(o['items'])} item(s)"
                         + (f", status {o['status']}" if o.get("status") else "")
                         + (f", ETA {o['eta']}" if o.get("eta") else "") for o in rows[:3])

    def call_plan(self, job):
        user = self.hh["user"]["name"]
        language = lang.default(self.hh)
        greeting = lang.greet(language, "phone", user)
        plan = CallPlan(DOORSTEP_CALL.format(user=user, greeting=greeting, orders=self.on_the_way(), speak=lang.speak(language),
                                             instructions=self.hh.get("delivery_instructions") or DEFAULT_INSTRUCTIONS),
                        greeting, max_minutes=3, language=language)
        s = plan.saved

        def notify_owner(reason: str) -> str:
            """Tell the family right now, e.g. the delivery partner is at the gate."""
            s["notified"] = reason
            self.store.add_card(Card(self.name, "alert", f"Delivery: {reason}"[:80],
                                     [reason, "The delivery partner is on the line with QuickPick."],
                                     question="", choices=[{"id": "ok", "label": "On my way"}]).to_dict())
            return f"{user} has been told. Ask them to wait a minute."

        def take_message(message: str, caller_name: str) -> str:
            """A short message for the family from a caller who is not a delivery partner."""
            s["message"] = {"from": caller_name, "text": message}
            return "Saved. Thank them and end the call."

        end_call = convo.end_call_tool(s)

        plan.tools = [notify_owner, take_message, end_call]
        return plan

    async def after_call(self, job, saved):
        lines = [saved.get("summary") or "The caller hung up."]
        if saved.get("message"):
            lines.append(f"Message from {saved['message'].get('from') or 'the caller'}: {saved['message']['text']}")
        caller = job["payload"].get("caller", "")
        return Card(self.name, "info", f"QuickPick answered a call {caller}".strip(), lines, question="",
                    choices=[{"id": "ok", "label": "OK"}])

    async def execute(self, card, choice):
        return {"ok": True}
