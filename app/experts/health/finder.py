"""Finding a hospital or doctor the family named, and adding it to household.yaml once a human confirms.
The web lookup only proposes a number with its source; Pathya calls it only after the human taps "Add" (which writes it
into household.yaml, AGENTS.md rule 8: only numbers in household.yaml are called).
Online consultations are links to the providers' own booking pages: their doctors' profiles stay on their sites
(nothing is scraped or copied)."""
import json
import os
import re
from pathlib import Path

import yaml
from openai import OpenAI

ONLINE = [
    {"name": "PharmEasy", "url": "https://pharmeasy.in/doctor-consultation/general-info?step=1",
     "about": "Video consultation with a doctor, 20+ specialties, any time of day."},
    {"name": "Apollo 24|7", "url": "https://www.apollo247.com/specialties",
     "about": "Video, audio or chat consultation with Apollo doctors, by specialty."},
]
SPECIALTIES = ["General physician", "Diabetologist", "Cardiologist", "Orthopedic", "Gynecologist", "Dermatologist",
               "Eye specialist", "ENT", "Pediatrician", "Dietitian"]

FIND = """Find the appointment (reception) phone number for this place in India and return JSON only, no prose:
{{"clinic": "<hospital or clinic name>", "doctor": "<doctor's name if found, else the one asked for>",
"phone": "<appointment number as listed>", "address": "<short address>", "source": "<the web page URL you used>"}}
Use the official website or a well-known listing. If you cannot find a number, use "" for phone. Do not guess.
Looking for: hospital or clinic "{hospital}", doctor "{doctor}", area "{area}", city "{city}"."""


def e164(phone):
    """Indian numbers as listed ('040 2345 6789', '098480 22338', '+91-98480-22338') -> '+914023456789'."""
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    digits = digits.lstrip("0")
    return f"+91{digits}" if len(digits) == 10 else ""


def find_clinic(hospital, doctor="", area="", city="Hyderabad", client=None):
    r = (client or OpenAI()).responses.create(
        model=os.getenv("SEARCH_MODEL", os.getenv("VISION_MODEL", "gpt-5-mini")), tools=[{"type": "web_search"}],
        input=FIND.format(hospital=hospital or "any", doctor=doctor or "any", area=area or "any", city=city))
    text = r.output_text
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("The search did not return a clinic.")
    found = json.loads(m.group(0))
    if str(found.get("doctor") or "").strip().lower() in ("any", "none", "n/a", "unknown"):
        found["doctor"] = ""
    found["phone_e164"] = e164(found.get("phone"))
    return found


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower())[:40].strip("-") or "clinic"


def add_to_household(path, hh, clinic):
    """Insert the clinic under clinics: in household.yaml (comments kept), then into the live household dict."""
    key, n = slug(clinic["clinic"]), 2
    while key in hh["clinics"]:
        key, n = f"{slug(clinic['clinic'])}-{n}", n + 1
    entry = {"doctor": clinic.get("doctor") or "the doctor", "clinic": clinic["clinic"], "phone": clinic["phone_e164"],
             **({"specialty": clinic["specialty"]} if clinic.get("specialty") else {})}
    if path:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        block = (f"  {key}:                      # added in the app after a human confirmed; source: "
                 f"{str(clinic.get('source') or 'web')[:80]}\n"
                 + "".join(f"    {k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in entry.items()))
        new = re.sub(r"(?m)^clinics:[^\n]*\n", lambda m: m.group(0) + block, text, count=1) if re.search(r"(?m)^clinics:", text) \
            else text.rstrip() + "\nclinics:\n" + block
        if yaml.safe_load(new)["clinics"].get(key) != entry:
            raise RuntimeError("Could not add the clinic to household.yaml safely.")
        p.write_text(new, encoding="utf-8")
    hh["clinics"][key] = entry
    return key
