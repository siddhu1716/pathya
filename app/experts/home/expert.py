"""Home Expert: the user's own line. When the user phones QuickPick (or QuickPick phones them for the evening
check-in) one call can: take a grocery order (a cart card that still needs a tap), note what they ate (estimated
calories), ask whether they took the medicines THEY listed (recorded in their words, never judged), mark things
that ran out, say what is at home and what is running low, and suggest a simple dish from what is at home.
It never gives medical or diet advice and never commits anything."""
import time

from app.core import convo, lang, safety
from app.experts.base import CallPlan, Card, Expert
from app.experts.health.expert import EMERGENCY, NO_ADVICE, next_at
from app.experts.kitchen import pantry

HOME_CALL = """You are QuickPick, {user}'s AI assistant for the home. You are on the phone with {user}.
Your first sentence: "{greeting}" {speak} Keep every reply short (one or two sentences).
{why}
What you know (use it when it helps; never read it all out):
- At home now: {at_home}
- Running low: {low}
- Eaten today so far: {eaten}
- Medicines {user} listed: {meds}
- Today's meal plan: {plan}
What you can do:
- Groceries: when {user} wants something (or agrees to reorder what is running low), call set_order with EVERY item
  and quantity so far (each call replaces the list). Read it back, at most three items at a time. Say the cart will
  be on their phone to approve with one tap; nothing is ordered before that tap. Never discuss payment details.
- Food: when they say what they ate, call log_food once per meal, in their words with amounts.
- Medicines: only if medicines are listed and this is the check-in (or they bring it up), ask once whether they took
  them and call medicine_taken with their answer in their words. {no_advice}
- Ran out: when they say something is finished, call ran_out with those items, and offer to add them to the order.
- Meal ideas: if asked what to eat or cook, suggest one or two simple home dishes from what is at home or today's
  plan. These are ideas, not diet or medical advice: never mention calorie targets or illnesses.
Never read out order numbers or IDs. {emergency}
Finish with end_call."""

WHY_IN = "{user} phoned you. Ask how you can help: groceries, noting a meal, or what is at home."
WHY_OUT = "This is {user}'s check-in call: {purpose}"
CHECKIN = ("ask one thing at a time: (1) only if medicines are listed, whether they took them; (2) what they ate "
           "today; (3) whether to reorder what is running low; then offer one dish idea for tomorrow from what is "
           "at home.")
EMERGENCY_SELF = ("If they mention chest pain, breathlessness, fainting, sudden weakness on one side, heavy bleeding, "
                  "or say it is an emergency: tell them calmly to call 108 now, and end the call (why=emergency).")


class HomeExpert(Expert):
    name, title = "home", "Home line"
    handles = "the user's own calls: groceries, food log, medicine check-ins, what is at home"
    call_kinds = {"home"}

    def __init__(self, store, household, kitchen=None):
        self.store, self.hh, self.kitchen = store, household, kitchen

    # ---- entry points ----
    def call_me(self, purpose="", run_at=None, daily_hour=None, via=None):
        payload = {"to": self.hh["user"]["phone"], "purpose": purpose or CHECKIN, **({"via": via} if via else {})}
        if daily_hour is not None:
            payload["daily_hour"] = daily_hour
        return self.store.add_job(self.name, "home", "me", payload, run_at)

    def answered(self, call_sid):
        """The user phoned QuickPick: a call that has already 'run' (never dialled)."""
        jid = self.store.add_job(self.name, "home", "me", {"direction": "inbound"}, run_at=4102444800)
        self.store.start_job(jid)
        self.store.end_job(jid, True, {"call_sid": call_sid})
        return jid

    def daily(self, hour):
        """One check-in call every day at `hour` (IST). Replaces any earlier schedule."""
        self.stop_daily()
        self.store.remember("me", "daily", {"hour": hour}, "app")
        return self.call_me(run_at=next_at(hour).timestamp(), daily_hour=hour)

    def stop_daily(self):
        self.store.forget("me", "daily")
        for j in self.store.upcoming():
            if j["expert"] == self.name and "daily_hour" in j["payload"]:
                self.store.cancel(j["id"])

    def daily_hour(self):
        f = self.store.facts("me", "daily")
        return f[0]["value"]["hour"] if f else None

    def meds(self):
        """Medicines the user listed in household.yaml (user.meds) or confirmed from a prescription photo."""
        listed = [str(m) for m in self.hh["user"].get("meds") or []]
        rx = next((f["value"] for f in reversed(self.store.facts("me", "meds"))), []) or []
        return listed + [m.get("name_as_written", "") for m in rx if isinstance(m, dict)]

    # ---- the call ----
    def call_plan(self, job):
        user, p = self.hh["user"], job["payload"]
        inbound = p.get("direction") == "inbound"
        language = lang.of(self.hh, user)
        greeting = lang.greet(language, "self", user["name"])
        shelf = pantry.items(self.store)
        eaten = pantry.today(self.store, self.hh)
        plan_fact = next((f["value"] for f in self.store.facts("home", "mealplan")), None) or {}
        first_day = (plan_fact.get("days") or [{}])[0]
        why = (WHY_IN if inbound else WHY_OUT).format(user=user["name"], purpose=p.get("purpose") or CHECKIN)
        plan = CallPlan(HOME_CALL.format(
            user=user["name"], greeting=greeting, speak=lang.speak(language), why=why,
            at_home=", ".join(i["name"] for i in shelf[:25]) or "nothing recorded",
            low=", ".join(i["name"] for i in shelf if i["low"]) or "nothing",
            eaten="; ".join(m["text"] for m in eaten["meals"]) or "nothing noted yet",
            meds=", ".join(self.meds()) or "none listed",
            plan=" · ".join(f"{m['slot']}: {m['dish']}" for m in first_day.get("meals", [])) or "none",
            no_advice=NO_ADVICE, emergency=EMERGENCY_SELF),
            greeting, max_minutes=6, language=language)
        s = plan.saved

        def set_order(items: list[str]) -> str:
            """The full grocery list so far, one entry per item with quantity. Each call replaces the list."""
            s["items"] = items
            return "Saved. Read it back, at most three items at a time; the cart needs their tap in the app."

        def log_food(meal: str, what: str) -> str:
            """One meal they ate today (breakfast, lunch, dinner or snack), in their words with amounts."""
            s.setdefault("meals", []).append({"meal": meal, "what": what})
            return "Noted."

        def medicine_taken(answer: str) -> str:
            """Their answer about the medicines they listed, in their words. Do not judge it."""
            s["meds"] = answer
            return "Noted. Do not comment on it."

        def ran_out(items: list[str]) -> str:
            """Items that are finished at home."""
            s["ran_out"] = sorted(set(s.get("ran_out", []) + items))
            return "Noted. Offer to add them to the order."

        end_call = convo.end_call_tool(s)

        plan.tools = [set_order, log_food, medicine_taken, ran_out, end_call]
        return plan

    async def after_call(self, job, saved):
        lines = []
        for m in saved.get("meals") or []:
            try:
                e = await pantry.log_meal(self.store, m["what"], m.get("meal", ""))
                lines.append(f"{(m.get('meal') or 'Meal').title()}: {m['what']} (about {e['kcal']} kcal, "
                             f"protein {e['protein_g']:.0f} g)")
            except Exception as err:
                lines.append(f"Could not estimate {m['what']}: {err}")
        if saved.get("meds"):
            verdict = safety.check(f"Medicines: {saved['meds']}")
            self.store.remember("me", f"medlog:{pantry.today_key()}",
                                {"answer": verdict.text, "ts": time.time(), "meds": self.meds()}, "phone call")
            lines.append(verdict.text + " (in your words)")
        if saved.get("ran_out"):
            gone = pantry.used_up(self.store, saved["ran_out"])
            lines.append("Finished at home: " + ", ".join(saved["ran_out"]) + (f" ({len(gone)} off the shelf)" if gone else ""))
        hour = job["payload"].get("daily_hour")
        if hour is not None and self.daily_hour() == hour:
            self.call_me(run_at=next_at(hour).timestamp(), daily_hour=hour)       # tomorrow's check-in
        for line in lines:
            self.store.log(self.name, job["id"], line)
        items = saved.get("items") or []
        if items and self.kitchen is not None:
            return await self.kitchen.handle(", ".join(items), ref=job["id"])   # Instamart, else Zepto, else the list
        if items:
            lines.append("Wanted: " + ", ".join(items) + " (Swiggy is offline, so no cart yet)")
        if not lines and not saved.get("summary"):
            return None
        return Card(self.name, "info", "Your call with QuickPick", [saved.get("summary") or "Call ended."] + lines,
                    question="", choices=[{"id": "ok", "label": "OK"}])

    async def execute(self, card, choice):
        return {"ok": True}
