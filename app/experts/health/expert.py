"""Health Expert: books clinic appointments by phone, checks in with family, prepares a doctor
brief, and turns a confirmed prescription into reminder calls. It never gives medical advice:
it schedules, reminds and relays. It books only inside the family's window (enforced here)."""
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from app.core import convo, lang, safety
from app.experts.base import CallPlan, Card, Expert

IST = timezone(timedelta(hours=5, minutes=30))             # India has no daylight saving
PARTS = {"morning": (7, 12), "afternoon": (12, 17), "evening": (17, 21)}
DOSE_HOURS = {"morning": 9, "afternoon": 14, "night": 21}   # reminder call times, IST

NO_ADVICE = ("You never give medical advice: never suggest, start, stop or change a medicine or dose, and never "
             "say whether a symptom or reading is good or bad. If asked, say you will add it to the questions "
             "for the doctor.")
EMERGENCY = ("If they mention chest pain, breathlessness, fainting, sudden weakness on one side, heavy bleeding, "
             "or say it is an emergency: call alert_family at once, tell them calmly to call 108 now, and end the call (why=emergency).")

CLINIC_CALL = """You are QuickPick, an AI assistant, phoning {clinic} for {user} to book an appointment
for {patient} (age {age}) with {doctor}. Your first sentence: "{greeting}" {speak}
Use short sentences. Never pretend to be human.
Share only the patient's name and age, the reason "{reason}" and the callback number {callback}.
Wanted: {window}. Ask which slots are free and call offer_slots with them (ISO 8601, e.g. 2026-11-24T10:30).
Then call book_slot with one slot; it refuses anything outside the family's window. If none fit, ask them to
hold the earliest slot and call hold_slot. After booking, repeat date, time, doctor and what to bring once.
Never discuss payment details. Finish with end_call."""

CHECKIN_CALL = """You are QuickPick, an AI assistant, calling {patient} for {user}. Your first sentence: "{greeting}"
{speak} Speak simply, warmly and slowly.
Purpose: {purpose}
Ask one thing at a time: how they feel; anything new and since when; today's BP or sugar reading if they have
one; whether they took {meds}; what they want to ask the doctor. Then call save_checkin with their words and a
short English summary. {no_advice}
{emergency}
End warmly and call end_call."""


def to_ist(text):
    dt = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    return dt.replace(tzinfo=IST) if dt.tzinfo is None else dt.astimezone(IST)


def fits(slot, start, end, part=None):
    """The family's window, enforced in code rather than trusted to the model."""
    if not start <= slot < end:
        return False
    lo, hi = PARTS.get(part or "", (0, 24))
    return lo <= slot.hour < hi


def _esc(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def make_ics(uid, start, minutes, title, location, notes=""):
    utc = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//QuickPick//Experts//EN", "BEGIN:VEVENT",
            f"UID:{uid}@quickpick", f"DTSTAMP:{utc(datetime.now(timezone.utc))}", f"DTSTART:{utc(start)}",
            f"DTEND:{utc(start + timedelta(minutes=minutes))}", f"SUMMARY:{_esc(title)}",
            f"LOCATION:{_esc(location)}", f"DESCRIPTION:{_esc(notes)}", "BEGIN:VALARM", "TRIGGER:-PT2H",
            "ACTION:DISPLAY", "DESCRIPTION:Reminder", "END:VALARM", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(rows) + "\r\n"


def wa_link(phone, text):
    """A WhatsApp draft; the human presses send."""
    return f"https://wa.me/{''.join(c for c in str(phone) if c.isdigit())}?text={urllib.parse.quote(text)}"


def next_at(hour, now=None):
    now = (now or datetime.now(IST)).astimezone(IST)
    t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return t if t > now else t + timedelta(days=1)


class HealthExpert(Expert):
    name, title = "health", "Health Expert"
    handles = ("doctor appointments, clinic bookings, check-in calls, questions for the doctor, "
               "prescriptions, medicine reminders, follow-ups")
    call_kinds = {"book", "checkin"}

    def __init__(self, store, household):
        self.store, self.hh = store, household

    def person(self, key):
        """A household member, the user themself ("me"), or a member added in the app (no phone)."""
        if key == "me":
            return self.hh["user"]
        if key in self.hh["people"]:
            return self.hh["people"][key]
        from app.experts.family.profiles import profile
        prof = profile(self.store, key)
        if not prof.get("added"):
            raise KeyError(key)
        return {"name": prof.get("name", key), "age": prof.get("age", "")}

    # ---- entry points: the Concierge's tools and the UI forms call these ----
    def book(self, patient, clinic, window_start, window_end, part, reason, run_at=None, via=None):
        """The window IS the family's approval: the phone agent can only book inside it."""
        payload = {"patient": patient, "clinic": clinic, "window_start": window_start, "window_end": window_end,
                   "part": part, "reason": reason, "to": self.hh["clinics"][clinic]["phone"], **({"via": via} if via else {})}
        return self.store.add_job(self.name, "book", clinic, payload, run_at)

    def checkin(self, patient, purpose, run_at=None, via=None):
        payload = {"patient": patient, "purpose": purpose, "to": self.person(patient)["phone"], **({"via": via} if via else {})}
        return self.store.add_job(self.name, "checkin", patient, payload, run_at)

    def meds(self, patient):
        rows = self.store.facts(patient, "meds")
        return rows[-1]["value"] if rows else []

    # ---- phone calls ----
    def call_plan(self, job):
        p = job["payload"]
        pat, user = self.person(p["patient"]), self.hh["user"]
        if job["kind"] == "book":
            return self._booking_plan(p, pat, user)
        return self._checkin_plan(p, pat, user)

    def _booking_plan(self, p, pat, user):
        c = self.hh["clinics"][p["clinic"]]
        start, end = to_ist(p["window_start"]), to_ist(p["window_end"])
        language = lang.of(self.hh, c)
        greeting = lang.greet(language, "calling", user["name"], c.get("clinic", ""))
        window = f"{p.get('part') or 'any time'}, {start:%a %d %b %H:%M} to {end:%a %d %b %H:%M}"
        plan = CallPlan(CLINIC_CALL.format(clinic=c["clinic"], user=user["name"], patient=pat["name"],
                                           age=pat.get("age", ""), doctor=c["doctor"], greeting=greeting,
                                           speak=lang.speak(language),
                                           reason=p["reason"], callback=user["phone"], window=window),
                        greeting, max_minutes=6, language=language)
        s = plan.saved

        def ok(slot):
            try:
                return fits(to_ist(slot), start, end, p.get("part"))
            except ValueError:
                return False

        def offer_slots(slots: list[str]) -> str:
            """Record the free slots the clinic offered, as ISO 8601 date-times."""
            s["offered"] = slots
            good = [x for x in slots if ok(x)]
            return (f"These fit the family's window: {good}. Book one." if good else
                    "None fit the family's window. Ask for other slots, or ask them to hold the earliest one.")

        def book_slot(slot: str, doctor: str, fee: str, bring: str) -> str:
            """Book this exact slot (ISO 8601). Refused outside the family's window."""
            if s.get("booked"):
                return "Already booked. Repeat the details and end the call."
            if not ok(slot):
                return "Refused: outside the family's window. Ask for another slot, or ask them to hold one."
            s["booked"] = {"slot": to_ist(slot).isoformat(), "doctor": doctor or c["doctor"], "fee": fee, "bring": bring}
            return "Booked. Repeat the details once, thank them and end the call."

        def hold_slot(slot: str, note: str) -> str:
            """The clinic holds a slot outside the window until the family confirms."""
            s["held"] = {"slot": slot, "note": note}
            return "Noted. Tell them the family will call back to confirm."

        end_call = convo.end_call_tool(s)

        plan.tools = [offer_slots, book_slot, hold_slot, end_call]
        return plan

    def _checkin_plan(self, p, pat, user):
        meds = ", ".join(m.get("name_as_written", "") for m in self.meds(p["patient"])) or "their usual medicines"
        language = lang.of(self.hh, pat)
        greeting = (lang.greet(language, "self", user["name"]) if p["patient"] == "me"
                    else lang.greet(language, "calling", user["name"], pat["name"]))
        plan = CallPlan(CHECKIN_CALL.format(patient=pat["name"], user=user["name"], speak=lang.speak(language),
                                            greeting=greeting, purpose=p["purpose"], meds=meds,
                                            no_advice=NO_ADVICE, emergency=EMERGENCY),
                        greeting, max_minutes=5, language=language)
        s = plan.saved

        def save_checkin(feeling: str, new_symptoms: list[str], since: str, readings: list[str],
                         meds_taken: str, questions: list[str], her_words: str, summary_en: str) -> str:
            """Save what they said, in their words. Do not judge or interpret anything."""
            s["checkin"] = {"feeling": feeling, "new_symptoms": new_symptoms, "since": since, "readings": readings,
                            "meds_taken": meds_taken, "questions": questions, "her_words": her_words,
                            "summary_en": summary_en}
            return "Saved. Thank them and end the call."

        def alert_family(reason: str) -> str:
            """Use at once if they describe an emergency or urgently ask for their family."""
            s["alert"] = reason
            self.store.add_card(Card(self.name, "alert", f"Urgent: {pat['name']} needs you",
                                     [reason, f"Call now: {pat.get('phone', '')}"], question="",
                                     choices=[{"id": "ok", "label": "I'm calling"}]).to_dict())
            return "Family alerted. Tell them calmly to call 108 now if it is an emergency."

        end_call = convo.end_call_tool(s)

        plan.tools = [save_checkin, alert_family, end_call]
        return plan

    async def after_call(self, job, saved):
        p = job["payload"]
        if job["kind"] == "book":
            if saved.get("booked"):
                return self._booked_card(p, saved["booked"])
            if saved.get("held"):
                h = saved["held"]
                return Card(self.name, "hold", "The clinic is holding a slot",
                            [h["slot"], h.get("note") or "", saved.get("summary") or ""],
                            question="Call back and confirm this slot?",
                            choices=[{"id": "confirm", "label": "Yes, confirm it"}, {"id": "skip", "label": "No"}],
                            payload={"request": p, "slot": h["slot"]})
            return Card(self.name, "info", "No appointment booked",
                        [saved.get("summary") or "No free slot inside the window."], question="",
                        choices=[{"id": "ok", "label": "OK"}])
        if saved.get("checkin"):
            self.store.remember(p["patient"], f"checkin:{job['id']}", saved["checkin"], "phone check-in")
            return self.brief_card(p["patient"])
        return None

    def _booked_card(self, p, b):
        c, pat = self.hh["clinics"][p["clinic"]], self.person(p["patient"])
        when = to_ist(b["slot"])
        ics = make_ics(f"{p['patient']}-{when:%Y%m%d%H%M}", when, 30, f"{pat['name']} - {b['doctor']}", c["clinic"],
                       f"Reason: {p['reason']}. Booked by QuickPick.")
        return Card(self.name, "booking", "Appointment booked",
                    [f"{when:%a %d %b, %I:%M %p} - {b['doctor']}", c["clinic"],
                     f"Fee: {b.get('fee') or 'not mentioned'}", f"Bring: {b.get('bring') or 'not mentioned'}"],
                    question="Add it to the calendar and set reminder calls?",
                    choices=[{"id": "remind", "label": "Calendar + reminder calls"},
                             {"id": "calendar", "label": "Calendar only"}],
                    payload={"patient": p["patient"], "clinic": p["clinic"], "slot": when.isoformat(),
                             "doctor": b["doctor"], "ics": ics})

    def brief_card(self, patient):
        """'Asking the doctor': what they said since the last visit, in their words, plus their questions."""
        pat = self.person(patient)
        checks = [f["value"] for f in self.store.facts(patient, "checkin:")]
        said = [c.get("her_words") or c.get("summary_en") for c in checks if c]
        readings = [r for c in checks for r in c.get("readings") or []]
        questions = [q for c in checks for q in c.get("questions") or []]
        meds = [m.get("name_as_written", "") for m in self.meds(patient)]
        text = "\n".join([f"Doctor brief: {pat['name']}, {pat.get('age', '')}",
                          "What they reported (their words): " + (" | ".join(x for x in said if x) or "nothing new"),
                          "Readings they gave: " + (", ".join(readings) or "none"),
                          "Medicines (as listed by the family): " + (", ".join(meds) or "not recorded"),
                          "Their questions for the doctor: " + ("; ".join(questions) or "none")])
        verdict = safety.check(text)
        warnings = {"blocked": ["The safety check held part of this brief. Review it before sharing."],
                    "unchecked": ["Safety check is off (set GUARDRAIL_ID)."]}.get(verdict.status, [])
        phone = self.hh["clinics"].get(pat.get("clinic", ""), {}).get("phone")
        return Card(self.name, "brief", f"Doctor brief for {pat['name']}", verdict.text.split("\n"),
                    question="Share it with the clinic?",
                    choices=[{"id": "share", "label": "WhatsApp draft"}, {"id": "ok", "label": "Keep"}],
                    warnings=warnings,
                    payload={"text": verdict.text, "safety": verdict.status,
                             "wa": wa_link(phone, verdict.text) if phone else None})

    def meds_card(self, patient, rx):
        """rx is the prescription reader's output. Nothing is scheduled until a human confirms."""
        lines, warnings = [], []
        for m in rx.get("meds", []):
            when = "/".join(k for k in DOSE_HOURS if m.get(k)) or "timing unclear"
            days = f"for {m['days']} days" if m.get("days") else ""
            lines.append(" ".join(str(x) for x in (m.get("name_as_written"), m.get("strength"), m.get("dose"),
                                                  when, m.get("food"), days) if x))
            if m.get("unclear") or when == "timing unclear":
                warnings.append(f"Check with the pharmacist: {m.get('name_as_written')}")
        warnings += [f"Could not read: {u}" for u in rx.get("unreadable_parts", [])]
        return Card(self.name, "meds", "Prescription" + (f" - {rx['doctor']}" if rx.get("doctor") else ""), lines,
                    question="Does this match the paper exactly? Reminders start only after you confirm.",
                    choices=[{"id": "confirm", "label": "Matches - set reminders"}, {"id": "discard", "label": "Discard"}],
                    warnings=warnings, payload={"patient": patient, "rx": rx})

    async def run_task(self, job):
        if job["kind"] == "followup":
            p = job["payload"]
            return Card(self.name, "followup", f"Review due with {p.get('doctor') or 'the doctor'}",
                        [f"The prescription said: review after {p['after_days']} days."],
                        question="Phone the clinic to book it (mornings, next 7 days)?",
                        choices=[{"id": "book", "label": "Yes, book it"}, {"id": "skip", "label": "Not now"}],
                        payload=p)
        return None

    async def execute(self, card, choice):
        kind, p = card["kind"], card["payload"]
        if kind == "booking":
            out = {"ok": True, "ics": p["ics"]}
            if choice == "remind":
                when = to_ist(p["slot"])
                clinic = self.hh["clinics"][p["clinic"]]["clinic"]
                eve = (when - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
                out["jobs"] = [
                    self.checkin(p["patient"], f"Remind them of tomorrow's appointment, {when:%a %d %b %I:%M %p}, "
                                 f"with {p['doctor']} at {clinic}. Ask what they want to ask the doctor.",
                                 run_at=max(eve.timestamp(), time.time() + 60)),
                    self.checkin(p["patient"], f"After today's visit with {p['doctor']}: ask how it went and "
                                 "what the doctor said.", run_at=(when + timedelta(hours=3)).timestamp())]
            return out
        if kind == "hold" and choice == "confirm":
            r, slot = p["request"], to_ist(p["slot"])
            return {"ok": True, "jobs": [self.book(r["patient"], r["clinic"], slot.isoformat(),
                                                   (slot + timedelta(minutes=1)).isoformat(), None, r["reason"])]}
        if kind == "meds" and choice == "confirm":
            return self._start_reminders(p["patient"], p["rx"])
        if kind == "followup" and choice == "book":
            start = next_at(7)
            return {"ok": True, "jobs": [self.book(p["patient"], self.person(p["patient"]).get("clinic") or next(iter(self.hh["clinics"])),
                                                   start.isoformat(), (start + timedelta(days=7)).isoformat(),
                                                   "morning", f"Review visit with {p.get('doctor') or 'the doctor'}")]}
        if kind == "brief" and choice == "share":
            return {"ok": True, "open": p.get("wa")}
        return {"ok": True}

    def _start_reminders(self, patient, rx):
        """Confirmed prescription: medicines kept as written (same names replace older entries) and daily reminder
        calls at the dose times for the course length (family/meds.py)."""
        from app.experts.family import meds as M
        source = f"prescription {rx.get('doctor') or ''} {rx.get('date') or ''}".strip()
        new = [dict(m, start=time.time(), source=source) for m in rx.get("meds", []) if not m.get("unclear")]
        names = {m.get("name_as_written") for m in new}
        keep = [m for m in M.listed(self.store, patient) if m.get("name_as_written") not in names]
        self.store.remember(patient, "meds", keep + new, source)
        for n, advice in enumerate(rx.get("advice_as_written", [])):
            self.store.remember(patient, f"advice:{n}", advice, source)    # the Kitchen Expert reads these
        jobs = M.set_reminders(self.store, self.person(patient).get("phone"), patient, True)
        if rx.get("review_after_days"):
            due = time.time() + max(0, rx["review_after_days"] - 3) * 86400
            jobs.append(self.store.add_job(self.name, "followup", patient,
                                           {"patient": patient, "doctor": rx.get("doctor"),
                                            "after_days": rx["review_after_days"]}, due))
        return {"ok": True, "jobs": jobs}
