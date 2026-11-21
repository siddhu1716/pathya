"""Concierge: one sentence from the family -> the right Experts. Experts are TOOLS here (not
handoffs), so one request can start several ("Amma's BP review this week, and we're out of milk").
Reference code: build it per request so 'now' is fresh."""
import os
from datetime import datetime, timedelta, timezone

from agents import Agent, function_tool

IST = timezone(timedelta(hours=5, minutes=30))

CONCIERGE = """You run a household's Experts for {user}. Now: {now} (IST).
People: {people}. Clinics: {clinics}.
Turn the request into Expert actions and call the tools; one request may need several.
Dates for book_doctor are ISO 8601 in IST; "this week" means from now until Sunday 23:59.
Never give medical advice. Reply in one or two short lines saying what you started."""


def make_concierge(store, hh, kitchen, health):
    @function_tool
    async def order_groceries(items: str) -> str:
        """Groceries or kitchen supplies. Builds a Swiggy Instamart cart for the family to approve."""
        card = await kitchen.handle(items)
        return f"Cart ready for approval (card {store.add_card(card.to_dict())})."

    @function_tool
    def book_doctor(patient: str, clinic: str, window_start: str, window_end: str, part: str, reason: str) -> str:
        """Phone a clinic and book inside this window. part: morning, afternoon, evening or any."""
        jid = health.book(patient, clinic, window_start, window_end, None if part == "any" else part, reason)
        return f"Calling the clinic now (job {jid})."

    @function_tool
    def check_in(patient: str, purpose: str) -> str:
        """Phone a family member to check in: how they feel and what to ask the doctor."""
        return f"Calling now (job {health.checkin(patient, purpose)})."

    @function_tool
    def call_for_list(person: str) -> str:
        """Phone the cook (or anyone at home) to take this week's grocery list."""
        return f"Calling now (job {kitchen.weekly_call(person)})."

    people = ", ".join(f"{k} ({v['name']})" for k, v in hh["people"].items())
    clinics = ", ".join(f"{k} ({v['doctor']}, {v['clinic']})" for k, v in hh["clinics"].items())
    return Agent(name="QuickPick",
                 instructions=CONCIERGE.format(user=hh["user"]["name"], people=people, clinics=clinics,
                                               now=datetime.now(IST).strftime("%a %d %b %Y %H:%M")),
                 tools=[order_groceries, book_doctor, check_in, call_for_list],
                 **({"model": os.environ["OPENAI_MODEL"]} if os.getenv("OPENAI_MODEL") else {}))
