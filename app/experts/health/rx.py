"""Prescription photo -> structured lines for a human to confirm. It copies; it never interprets.
Reference code (needs the openai package and a vision-capable model)."""
import base64
import os

from openai import OpenAI
from pydantic import BaseModel


class Med(BaseModel):
    name_as_written: str
    strength: str | None
    dose: str | None
    morning: bool
    afternoon: bool
    night: bool
    food: str | None
    days: int | None
    unclear: bool


class Rx(BaseModel):
    doctor: str | None
    date: str | None
    meds: list[Med]
    advice_as_written: list[str]
    review_after_days: int | None
    unreadable_parts: list[str]


READ_RX = """Read this prescription photo and copy it into the schema.
Copy medicine names exactly as written; never correct, expand or substitute them.
Fill strength, dose, morning/afternoon/night, before/after food and days only if written
(1-0-1 means morning and night). Set unclear=true for any line you cannot read with certainty.
Copy advice lines exactly (for example "low salt diet"). If a review is written (for example
"review after 2 weeks"), give review_after_days. List unreadable parts. Add, infer or explain nothing."""


def read_prescription(image: bytes, mime: str = "image/jpeg") -> dict:
    data = base64.b64encode(image).decode()
    r = OpenAI().responses.parse(
        model=os.getenv("VISION_MODEL", "gpt-5-mini"),
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": READ_RX},
            {"type": "input_image", "image_url": f"data:{mime};base64,{data}"}]}],
        text_format=Rx)
    return r.output_parsed.model_dump()
