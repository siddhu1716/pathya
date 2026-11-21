"""Ordering a prescription's medicines. No pharmacy MCP is usable yet (Tata 1mg's mcp.1mg.com does not resolve; Apollo
24|7 and PharmEasy have none), so Pathya does what a family member would: it finds pharmacies near the family's
location, and after a tap phones one to ask whether they have the medicines exactly as written, the total and home
delivery. The family then sends the prescription on WhatsApp to order. Pathya never places the order, never accepts
a substitute and never suggests or changes a medicine (AGENTS.md rule 9). A pharmacy's number is written into
household.yaml (pharmacies:) only after the tap, so Pathya still calls only numbers listed there (rule 8)."""
import json
import os
import re
import urllib.parse
from pathlib import Path

import yaml
from openai import OpenAI

from app.experts.health.finder import e164, slug

FIND = """List up to 3 pharmacies (chemists) near the place below in India, open today, preferring ones that deliver
to homes. Return JSON only, no prose:
{{"area": "<the locality you searched>", "pharmacies": [{{"name": "<pharmacy name and branch>", "phone": "<phone as
listed>", "address": "<short address>", "delivers": <true, false or null if not stated>, "source": "<URL you used>"}}]}}
Use Google Maps, the pharmacy's own store locator (Apollo Pharmacy, MedPlus, Wellness Forever and similar) or a
well-known listing. Only include a phone number you found listed; never guess one. Skip places without a number.
Place: {where}"""

PHARMACY_CALL = """You are Pathya, an AI assistant, phoning {pharmacy} for {user} about medicines for {patient}.
Your first sentence: "{greeting}" {speak} Use short sentences. Never pretend to be human.
The prescription lists, exactly as written: {meds}. Read at most three at a time, exactly as written; never correct,
explain or change a name or a dose.
Ask, one at a time: which of them they have; the total price; whether they deliver to {address} and how soon (or when
it can be collected); and a WhatsApp number to send the prescription photo to.
If they offer another brand or a substitute, do not accept it: note it in their words for the family to check with
the doctor. Do not place the order: say {user} will send the prescription on WhatsApp to confirm. Never discuss payment
details and never read out any ID. {no_advice}
Call save_answer with what they said, then finish with end_call."""

ORDER_YOURSELF = {
    "Tata 1mg": "https://www.1mg.com/search/all?name={q}",
    "Apollo 24|7": "https://www.apollopharmacy.in/search-medicines/{q}",
    "PharmEasy": "https://pharmeasy.in/search/all?name={q}",
}


def search_name(med):
    """The name to search for in a pharmacy app: the written name without 'Tab.' and the like."""
    name = re.sub(r"(?i)^\s*(tab|tablet|cap|caps|capsule|syp|syrup|inj|rx|re\(o\)|reco?)\.?\s+", "",
                  str(med.get("name_as_written") or ""))
    return name.strip()[:60]


def links(meds):
    """Per medicine, a search link in each pharmacy app (the family orders there themselves)."""
    out = []
    for m in meds:
        q = search_name(m)
        if q:
            out.append({"name": m.get("name_as_written"), "links": {k: v.format(q=urllib.parse.quote(q))
                                                                    for k, v in ORDER_YOURSELF.items()}})
    return out


def find(lat=None, lng=None, area="", city="Hyderabad", client=None):
    """Up to 3 pharmacies near the family, each with a listed number (E.164) and its source."""
    where = ", ".join(x for x in (area, city) if x)
    if lat is not None and lng is not None:
        where = f"coordinates {float(lat):.5f}, {float(lng):.5f} (work out the locality first; near {where})"
    r = (client or OpenAI()).responses.create(
        model=os.getenv("SEARCH_MODEL", os.getenv("VISION_MODEL", "gpt-5-mini")),
        tools=[{"type": "web_search", "user_location": {"type": "approximate", "country": "IN", "city": city}}],
        input=FIND.format(where=where))
    m = re.search(r"\{.*\}", r.output_text, re.S)
    if not m:
        raise RuntimeError("The search did not return pharmacies.")
    data = json.loads(m.group(0))
    found = []
    for p in data.get("pharmacies") or []:
        number = e164(p.get("phone"))
        if number and p.get("name") and number not in {f["phone_e164"] for f in found}:
            found.append({**p, "phone_e164": number})
    return {"area": data.get("area") or area or city, "pharmacies": found[:3]}


def add_to_household(path, hh, pharmacy):
    """Insert the pharmacy under pharmacies: in household.yaml (comments kept), then into the live household dict."""
    hh.setdefault("pharmacies", {})
    for k, v in hh["pharmacies"].items():
        if v.get("phone") == pharmacy["phone_e164"]:
            return k
    key, n = slug(pharmacy["name"]), 2
    while key in hh["pharmacies"]:
        key, n = f"{slug(pharmacy['name'])}-{n}", n + 1
    entry = {"name": pharmacy["name"], "phone": pharmacy["phone_e164"], "address": pharmacy.get("address") or ""}
    if path:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^pharmacies:[ \t]*(\{[ \t]*\})?[ \t]*$", "pharmacies:", text)
        block = (f"  {key}:                      # added in the app after a human confirmed; source: "
                 f"{str(pharmacy.get('source') or 'web')[:80]}\n"
                 + "".join(f"    {k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in entry.items()))
        if re.search(r"(?m)^pharmacies:[ \t]*$", text):
            new = re.sub(r"(?m)^pharmacies:[ \t]*\n", lambda m: m.group(0) + block, text, count=1)
        else:
            new = text.rstrip() + "\npharmacies:\n" + block
        if (yaml.safe_load(new).get("pharmacies") or {}).get(key) != entry:
            raise RuntimeError("Could not add the pharmacy to household.yaml safely.")
        p.write_text(new, encoding="utf-8")
    hh["pharmacies"][key] = entry
    return key


def order_text(user, patient, meds, address):
    lines = "\n".join(f"- {m}" for m in meds)
    return (f"Hello, this is {user}. Please deliver these medicines for {patient}, as on the prescription photo I am "
            f"attaching:\n{lines}\nDeliver to: {address}\nPlease confirm the total before sending. Thank you.")
