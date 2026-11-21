"""Camera: one photo, and the vision model works out what it is. It copies; it never interprets (AGENTS.md rule 9).
- meal: what is on the plate with portions, and estimated nutrition (logged for that person straight away)
- medicine: a strip, bottle or box, names and strengths exactly as printed (the human picks the times and adds it)
- prescription: read by health/rx.py into a card that a human confirms before anything is scheduled
- body_report: a body composition report (InBody and similar), numbers exactly as printed (the human saves them)"""
import base64
import os
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

SEE = """This photo comes from an Indian family's nutrition app. Say what it is and copy what matters:
- kind=meal: food or a plate. Describe it in simple words with portions (for example "2 rotis, 1 katori dal, 1 cup
  rice, cucumber salad") and estimate the whole plate's nutrition. sugar_g is added sugar only.
- kind=medicine: a medicine strip, bottle or box. Copy each name and strength exactly as printed; never correct, expand
  or substitute; unclear=true if you are not certain.
- kind=prescription: a doctor's prescription (handwritten or printed).
- kind=body_report: a body composition report (InBody, Tanita, a gym or clinic report). Copy the numbers exactly as
  printed: weight kg, height cm, body fat %, skeletal muscle mass kg, body fat mass kg, BMR kcal, visceral fat level,
  date. Leave anything not printed empty. Never interpret or say whether a number is good or bad.
- kind=other: anything else.
note: one short neutral line about what you saw."""


class MealSeen(BaseModel):
    description: str
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float
    sugar_g: float


class MedSeen(BaseModel):
    name_as_printed: str
    strength: str | None
    form: str | None
    unclear: bool


class BodySeen(BaseModel):
    date: str | None
    weight_kg: float | None
    height_cm: float | None
    body_fat_pct: float | None
    skeletal_muscle_kg: float | None
    fat_mass_kg: float | None
    bmr_kcal: float | None
    visceral_fat_level: float | None


class Seen(BaseModel):
    kind: Literal["meal", "medicine", "prescription", "body_report", "other"]
    meal: MealSeen | None
    medicines: list[MedSeen]
    report: BodySeen | None
    note: str


def look(image: bytes, mime="image/jpeg", hint="") -> dict:
    data = base64.b64encode(image).decode()
    prompt = SEE + (f"\nThe family says it is: {hint}." if hint else "")
    r = OpenAI().responses.parse(
        model=os.getenv("VISION_MODEL", "gpt-5-mini"),
        input=[{"role": "user", "content": [{"type": "input_text", "text": prompt},
                                            {"type": "input_image", "image_url": f"data:{mime};base64,{data}"}]}],
        text_format=Seen)
    return r.output_parsed.model_dump()


def matches(medicines, listed):
    """Indexes of already-listed medicines whose written name matches a scanned one (so the app can offer 'taken')."""
    out = []
    for i, m in enumerate(listed):
        name = str(m.get("name_as_written", "")).lower()
        words = [w for w in name.replace(".", " ").split() if len(w) > 3 and w not in ("tab", "tablet", "caps", "capsule")]
        if any(w in s["name_as_printed"].lower() for s in medicines for w in words):
            out.append(i)
    return out
