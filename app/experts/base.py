"""QuickPick v2 - the Expert contract. One folder per Expert; the platform
(caller, approvals, jobs, memory, safety) is shared by all of them."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable


@dataclass
class CallPlan:
    """How the phone agent behaves on one call. Tools write what they capture into `saved`."""
    instructions: str                     # persona prompt: says it is an AI, and who it calls for
    greeting: str                         # first sentence once the person answers
    tools: list[Callable] = field(default_factory=list)   # plain functions; the caller wraps them
    max_minutes: int = 5
    saved: dict = field(default_factory=dict)
    language: str = ""                    # the call opens in this language (app/core/lang.py); then follows the person


@dataclass
class Card:
    """What the human sees before anything is committed (money, bookings, reminders)."""
    expert: str
    kind: str                             # order | booking | hold | brief | meds | alert | info | followup
    title: str
    lines: list[str]
    total: str | None = None
    address: str | None = None
    question: str = "Approve?"
    choices: list[dict] = field(default_factory=lambda: [{"id": "approve", "label": "Approve"}])
    warnings: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)        # what execute() needs; never shown

    def to_dict(self) -> dict:
        return asdict(self)


class Expert:
    name = "base"
    title = "Expert"
    handles = ""                          # one line the Concierge uses to route requests
    call_kinds: set = set()               # job kinds that are phone calls; the rest are tasks

    def call_plan(self, job: dict) -> CallPlan:
        raise NotImplementedError

    async def after_call(self, job: dict, saved: dict) -> Card | None:
        return None

    async def run_task(self, job: dict) -> Card | None:
        return None

    async def execute(self, card: dict, choice: str) -> dict:
        """Runs ONLY after a human tapped `choice` on this card."""
        raise NotImplementedError


REGISTRY: dict = {}


def register(expert: Expert) -> Expert:
    if expert.name in REGISTRY:
        raise ValueError(f"Expert {expert.name!r} registered twice")
    REGISTRY[expert.name] = expert
    return expert
