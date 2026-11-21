"""Plate guard: checks a grocery list against each family member's OWN notes (the goal the family chose, allergies,
and what the doctor told the family). It never makes a health claim of its own and never blocks anything: flagged
items appear on the cart card, in the member's own note's words, and the human who taps decides (AGENTS.md rules 1, 9)."""
import os

from agents import Agent, Runner
from pydantic import BaseModel

from app.experts.family import profiles as P

MODEL = os.getenv("OPENAI_MODEL")

GUARD = """You check a grocery list against each family member's own notes. Flag an item only when it clearly clashes
with a note, for example: sweets, mithai, sugar, jaggery, cola or packaged juice against "less sugar" or a doctor's
note about sugar/diabetes; pickles, papad, chips, namkeen or instant noodles against "less salt" or a doctor's note about
BP; anything containing a listed allergen. note = the member's note it clashes with, in its own words (for example
"less sugar" or "doctor: diabetes"). Never add advice, reasons, warnings or health claims of your own. If nothing clashes,
return no flags."""


class Flag(BaseModel):
    item: str
    who: str
    note: str


class Flags(BaseModel):
    flags: list[Flag]


def notes_of(m):
    bits = []
    if m.get("goal") in ("less_sugar", "less_salt", "cut"):
        bits.append(P.GOALS[m["goal"]].lower())
    if m.get("allergies"):
        bits.append(f"allergy: {m['allergies']}")
    bits += [f"doctor: {c}" for c in m.get("conditions") or []]
    return bits


async def check(items, members, runner=None):
    """Returns [{"item", "who", "note"}]. Members without notes are skipped; no notes at all means no model call."""
    people = [f"- {m['name']}: " + "; ".join(n) for m in members if (n := notes_of(m))]
    if not items or not people:
        return []
    agent = Agent(name="Plate guard", instructions=GUARD, output_type=Flags, **({"model": MODEL} if MODEL else {}))
    run = await (runner or Runner.run)(agent, "Family notes:\n" + "\n".join(people) + "\n\nGrocery list:\n" +
                                       "\n".join(f"- {i}" for i in items), max_turns=1)
    names = {m["name"] for m in members}
    return [f.model_dump() for f in run.final_output.flags if f.who in names and f.item]


def warnings(flags):
    return [f"{f['item']}: clashes with {f['who']}'s note \"{f['note']}\". You decide before approving." for f in flags]
