"""Family line: QuickPick's calls with family members themselves (the user is "me").
- Check-in call (kind "home"), when a member phones in or QuickPick calls them (now or every day): take a grocery order
  (a cart card that still needs a tap), note what they ate (estimated calories, logged under that person), ask whether
  they took today's medicines AS WRITTEN (their answer recorded in their words, never judged), mark things that ran out,
  and suggest a simple dish from what is at home that fits their goal and plate notes.
- Medicine reminder call (kind "meds"): at the dose time, reads that time's medicines exactly as written and asks
  whether they were taken. "Not yet" becomes a card for the user. Never advice (AGENTS.md rule 9).
Only members with a phone in household.yaml are called (rule 8)."""
import time
from datetime import datetime, timedelta
from typing import Literal

from app.core import convo, lang, safety
from app.experts.base import CallPlan, Card, Expert
from app.experts.family import checkups, guard
from app.experts.family import meds as M
from app.experts.family import profiles as P
from app.experts.health.expert import NO_ADVICE
from app.experts.kitchen import pantry

HOME_CALL = """You are QuickPick, the family's AI assistant (set up by {user}). You are on the phone with {name}.
Your first sentence: "{greeting}" {speak} Keep every reply short (one or two sentences).
{why}
What you know (use it when it helps; never read it all out):
- About {name}: {about}
- {name}'s medicines due today, exactly as written: {meds}
- {name} has eaten today: {eaten}
- At home now: {at_home}
- Running low: {low}
- {name}'s plate notes in the family meal plan: {plate}
What you can do:
- Groceries: when they want something (or agree to reorder what is running low), call set_order with EVERY item and
  quantity so far (each call replaces the list). Read it back, at most three items at a time. Say the cart goes to
  {user}'s phone to approve with one tap; nothing is ordered before that tap. Never discuss payment details.
- Food: when they say what they ate, call log_food once per meal, in their words with amounts.
- Medicines: only if medicines are due today, ask once whether they took them, reading names exactly as written, and
  call medicine_taken with taken (yes, no or not_sure) and their answer in their words. {no_advice}
- Ran out: when they say something is finished, call ran_out with those items, and offer to add them to the order.
- Meal ideas: if asked what to eat or cook, suggest one or two simple home dishes from what is at home that fit their
  goal and plate notes (for example less sugar: no sweets, tea without sugar). Ideas only: never mention illnesses,
  numbers or targets, and never give medical or diet advice.
- Their own notes: {notes}. If they ask for something that clashes with a note (for example sweets with "less sugar"),
  gently remind them of the note in its own words, as the doctor's or family's, never as your own opinion, and offer a
  better swap (sugar-free, roasted, fruit). If they still want it, add it: {user} sees it flagged before approving.
{elder}Never read out order numbers or IDs. {emergency}
Finish with end_call."""

MEDS_CALL = """You are QuickPick, the family's AI assistant (set up by {user}), calling {name} with a medicine reminder.
Your first sentence: "{greeting}" {speak} Speak simply, warmly and slowly.
Then say it is time for the {slot} medicines, exactly as written: {meds}. Read at most three at a time. Never change a
name or a dose, and never add advice.
Ask whether they have taken them, and call dose_taken with taken (yes, no or not_sure) and their answer in their words.
If not yet, say gently that you will let {user} know; do not insist. {no_advice}
{emergency}
Finish with end_call."""

WHY_IN = "{name} phoned you. Ask how you can help: groceries, noting a meal, medicines, or what is at home."
WHY_OUT = "This is {name}'s check-in call: {purpose}"
CHECKIN = ("ask one thing at a time: (1) only if medicines are due today, whether they took them; (2) what they ate "
           "today; (3) whether to reorder what is running low; then offer one dish idea for tomorrow from what is "
           "at home.")
EMERGENCY = ("If they mention chest pain, breathlessness, fainting, sudden weakness on one side, heavy bleeding, or say "
             "it is an emergency: tell them calmly to call 108 now, call alert_family, and end the call (why=emergency).")


class HomeExpert(Expert):
    name, title = "home", "Family line"
    handles = "calls with family members: check-ins, groceries, food log, medicine reminders"
    call_kinds = {"home", "meds"}

    def __init__(self, store, household, kitchen=None):
        self.store, self.hh, self.kitchen = store, household, kitchen

    def member(self, key):
        return P.member(self.hh, self.store, key)

    def phone(self, key):
        """Only household.yaml numbers (rule 8)."""
        return self.hh["user"].get("phone") if key == "me" else (self.hh["people"].get(key) or {}).get("phone")

    # ---- entry points ----
    def call(self, who="me", purpose="", run_at=None, daily_hour=None, via=None):
        to = self.phone(who)
        if not to:
            raise ValueError(f"{self.member(who)['name']} has no phone number in household.yaml, so QuickPick can't call.")
        payload = {"who": who, "to": to, "purpose": purpose or CHECKIN, **({"via": via} if via else {})}
        if daily_hour is not None:
            payload["daily_hour"] = daily_hour
        return self.store.add_job(self.name, "home", who, payload, run_at)

    def call_me(self, purpose="", run_at=None, daily_hour=None, via=None):
        return self.call("me", purpose, run_at, daily_hour, via)

    def answered(self, call_sid, who="me"):
        """A family member phoned QuickPick: a call that has already 'run' (never dialled)."""
        jid = self.store.add_job(self.name, "home", who, {"who": who, "direction": "inbound"}, run_at=4102444800)
        self.store.start_job(jid)
        self.store.end_job(jid, True, {"call_sid": call_sid})
        return jid

    def daily(self, hour, who="me"):
        """One check-in call every day at `hour` (IST). Replaces any earlier schedule."""
        self.stop_daily(who)
        self.store.remember(who, "daily", {"hour": hour}, "app")
        return self.call(who, run_at=M.next_at(hour).timestamp(), daily_hour=hour)

    def stop_daily(self, who="me"):
        self.store.forget(who, "daily")
        for j in self.store.upcoming():
            if j["expert"] == self.name and j["kind"] == "home" and j["person"] == who and "daily_hour" in j["payload"]:
                self.store.cancel(j["id"])

    def daily_hour(self, who="me"):
        f = [x for x in self.store.facts(who, "daily") if x["key"] == "daily"]
        return f[0]["value"]["hour"] if f else None

    def dialled(self, job):
        """Called by the scheduler once a call is placed: the next daily check-in / tomorrow's dose reminder."""
        who, p = job["person"], job["payload"]
        later = datetime.now(M.IST) + timedelta(minutes=1)
        if job["kind"] == "meds":
            return M.schedule_next(self.store, self.phone(who), who, p["slot"], after=later)
        if p.get("daily_hour") is not None and self.daily_hour(who) == p["daily_hour"]:
            return self.call(who, run_at=M.next_at(p["daily_hour"], later).timestamp(), daily_hour=p["daily_hour"])
        return None

    # ---- the calls ----
    def _greeting(self, who, language):
        user = self.hh["user"]["name"]
        return lang.greet(language, "self", user) if who == "me" else lang.greet(language, "calling", user,
                                                                                    self.member(who)["name"])

    def call_plan(self, job):
        return self._meds_plan(job) if job["kind"] == "meds" else self._home_plan(job)

    def _home_plan(self, job):
        who, p = job["person"], job["payload"]
        m, user = self.member(who), self.hh["user"]["name"]
        language = m["language"]
        greeting = self._greeting(who, language)
        shelf = pantry.items(self.store)
        eaten = pantry.today(self.store, self.hh, who)
        due = M.today(self.store, who)
        about = f"goal: {P.GOALS.get(m['goal'], m['goal'])}; food: {m.get('food') or 'veg'}" + \
                (f"; never include (allergy): {m['allergies']}" if m.get("allergies") else "") + \
                (f"; the doctor told the family: {', '.join(m['conditions'])} (for choosing dishes only; never mention it)"
                 if m["conditions"] else "")
        why = (WHY_IN if p.get("direction") == "inbound" else WHY_OUT).format(name=m["name"], purpose=p.get("purpose") or CHECKIN)
        plan = CallPlan(HOME_CALL.format(
            user=user, name=m["name"], greeting=greeting, speak=lang.speak(language), why=why, about=about,
            meds="; ".join(f"{d['slot']}: {', '.join(d['meds'])}" for d in due) or "none",
            eaten="; ".join(x["text"] for x in eaten["meals"]) or "nothing noted yet",
            at_home=", ".join(i["name"] for i in shelf[:25]) or "nothing recorded",
            low=", ".join(i["name"] for i in shelf if i["low"]) or "nothing", plate=self.plate(m) or "none",
            notes=", ".join(guard.notes_of(m)) or "none", elder=self._elder(m),
            no_advice=NO_ADVICE, emergency=EMERGENCY), greeting, max_minutes=8 if m["elder"] else 6, language=language)
        s = plan.saved

        def set_order(items: list[str]) -> str:
            """The full grocery list so far, one entry per item with quantity. Each call replaces the list."""
            s["items"] = items
            return f"Saved. Read it back, at most three items at a time; the cart needs {user}'s tap in the app."

        def log_food(meal: str, what: str) -> str:
            """One meal they ate today (breakfast, lunch, dinner or snack), in their words with amounts."""
            s.setdefault("meals", []).append({"meal": meal, "what": what})
            return "Noted."

        def medicine_taken(taken: Literal["yes", "no", "not_sure"], their_words: str) -> str:
            """Whether they took today's medicines as written, and their answer in their words. Do not judge it."""
            s["meds"] = {"taken": taken, "words": their_words}
            return "Noted. Do not comment on it."

        def ran_out(items: list[str]) -> str:
            """Items that are finished at home."""
            s["ran_out"] = sorted(set(s.get("ran_out", []) + items))
            return "Noted. Offer to add them to the order."

        plan.tools = [set_order, log_food, medicine_taken, ran_out, self._alert(m, s), convo.end_call_tool(s)]
        return plan

    def _meds_plan(self, job):
        who, slot = job["person"], job["payload"]["slot"]
        m, user = self.member(who), self.hh["user"]["name"]
        language = m["language"]
        greeting = self._greeting(who, language)
        due = [M.line(x) for x in M.active(M.listed(self.store, who), slot)] or ["(nothing listed any more)"]
        plan = CallPlan(MEDS_CALL.format(user=user, name=m["name"], greeting=greeting, speak=lang.speak(language),
                                         slot=slot, meds="; ".join(due), no_advice=NO_ADVICE, emergency=EMERGENCY),
                        greeting, max_minutes=3, language=language)
        s = plan.saved

        def dose_taken(taken: Literal["yes", "no", "not_sure"], their_words: str) -> str:
            """Whether they took this time's medicines as written, and their answer in their words. Do not judge it."""
            s["meds"] = {"taken": taken, "words": their_words, "slot": slot}
            return "Noted. Do not comment on it."

        plan.tools = [dose_taken, self._alert(m, s), convo.end_call_tool(s)]
        return plan

    def _elder(self, m):
        """Older members: slower, gentler, and alert the family on the signs ICOPE asks about (no judging, no advice)."""
        if not m["elder"]:
            return ""
        watch = " ".join(checkups.watch(self.store, m))
        return (f"- {m['name']} is {m['age']}: speak slowly, one short question at a time, and repeat back what you "
                "understood. Ask gently whether they are eating enough and having some dal, curd, milk, eggs or paneer. If "
                "they say they skipped meals, ate very little, feel weak or dizzy, or had a fall, call alert_family with "
                "their words (no judging, no advice)." + (f" The family noticed: {watch}" if watch else "") + "\n")

    def _alert(self, m, s):
        def alert_family(reason: str) -> str:
            """Use at once if they describe an emergency or urgently ask for their family."""
            s["alert"] = reason
            self.store.add_card(Card(self.name, "alert", f"Urgent: {m['name']} needs you",
                                     [reason, f"Call now: {self.phone(m['key']) or ''}"], question="",
                                     choices=[{"id": "ok", "label": "I'm calling"}]).to_dict())
            return "Family alerted. Tell them calmly to call 108 now if it is an emergency."
        return alert_family

    def plate(self, m):
        plan = next((f["value"] for f in self.store.facts("home", "mealplan") if f["key"] == "mealplan"), None) or {}
        for day in (plan.get("days") or [])[:1]:
            for p in day.get("people") or []:
                if str(p.get("who", "")).lower() in (m["name"].lower(), m["key"]):
                    return p.get("plate")
        return None

    # ---- after the call ----
    async def after_call(self, job, saved):
        who = job["person"]
        m, lines = self.member(who), []
        for meal in saved.get("meals") or []:
            try:
                e = await pantry.log_meal(self.store, meal["what"], meal.get("meal", ""), who=who)
                lines.append(f"{(meal.get('meal') or 'Meal').title()}: {meal['what']} (about {e['kcal']} kcal, "
                             f"protein {e['protein_g']:.0f} g)")
            except Exception as err:
                lines.append(f"Could not estimate {meal['what']}: {err}")
        relay = None
        if saved.get("meds"):
            d = saved["meds"]
            words = safety.check(d.get("words") or "").text                       # every health text (rule 9)
            hour = datetime.now(M.IST).hour
            due = M.today(self.store, who)
            slots = [d["slot"]] if d.get("slot") else (
                [x["slot"] for x in due if x["hour"] <= hour + 1 and not x["taken"]] or [x["slot"] for x in due[:1]])
            for slot in slots:
                M.log_dose(self.store, who, slot, d.get("taken", "not_sure"), words)
            lines.append(f"Medicines ({', '.join(slots) or 'today'}): {d.get('taken')} - \"{words}\" (their words)")
            if d.get("taken") != "yes" and who != "me" and slots:
                due = [x for x in M.today(self.store, who) if x["slot"] in slots]
                relay = Card(self.name, "relay", f"{m['name']}: medicines not taken yet",
                             [f"In {m['name']}'s words: \"{words}\""] + [f"{x['slot']}: {', '.join(x['meds'])}" for x in due],
                             question="QuickPick only reminds. Talk to them if you need to.",
                             choices=[{"id": "call", "label": f"Call {m['name']} again"}, {"id": "ok", "label": "OK"}],
                             payload={"who": who})
        if saved.get("ran_out"):
            gone = pantry.used_up(self.store, saved["ran_out"])
            lines.append("Finished at home: " + ", ".join(saved["ran_out"]) + (f" ({len(gone)} off the shelf)" if gone else ""))
        for line in lines:
            self.store.log(self.name, job["id"], line)
        if relay:
            self.store.add_card(relay.to_dict())
        items = saved.get("items") or []
        if items and self.kitchen is not None:
            return await self.kitchen.handle(", ".join(items), ref=job["id"], who=who)   # flagged against their notes
        if items:
            lines.append("Wanted: " + ", ".join(items) + " (no store connected, so no cart yet)")
        if job["kind"] == "meds" or (not lines and not saved.get("summary")):
            return None
        title = "Your call with QuickPick" if who == "me" else f"QuickPick's call with {m['name']}"
        return Card(self.name, "info", title, [saved.get("summary") or "Call ended."] + lines, question="",
                    choices=[{"id": "ok", "label": "OK"}])

    async def execute(self, card, choice):
        if card["kind"] == "relay" and choice == "call":
            return {"ok": True, "jobs": [self.call(card["payload"]["who"])]}
        return {"ok": True}
