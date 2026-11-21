"""Editing household.yaml from the app (phone numbers), keeping its comments. Only numbers written here are ever called
(AGENTS.md rule 8), so the app writes them into household.yaml rather than the database."""
import json
import re
from pathlib import Path

import yaml


def normalize(phone):
    """'+91 98480 22338', '098480 22338', '9848022338' -> '+919848022338'; other countries need a leading +."""
    raw = str(phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+") and not digits.startswith("91"):
        return f"+{digits}" if 8 <= len(digits) <= 15 else ""
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    digits = digits.lstrip("0")
    return f"+91{digits}" if len(digits) == 10 and digits[0] in "6789" else ""


def _block(lines, start, indent):
    """Index just past the block that starts at `start` (lines indented deeper than `indent`)."""
    i = start + 1
    while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent
                              or lines[i].lstrip().startswith("#")):
        i += 1
    return i


def _find(lines, key, indent, lo=0, hi=None):
    hi = len(lines) if hi is None else hi
    pat = re.compile(rf"^{' ' * indent}{re.escape(key)}:(\s|$)")
    return next((i for i in range(lo, hi) if pat.match(lines[i])), None)


def _set_field(lines, start, indent, field, value):
    """Set `field: value` inside the mapping that starts at line `start` (children at indent+2)."""
    end = _block(lines, start, indent)
    child = indent + 2
    line = f"{' ' * child}{field}: {json.dumps(value, ensure_ascii=False)}"
    at = _find(lines, field, child, start + 1, end)
    if at is not None:
        comment = lines[at].split("#", 1)[1] if "#" in lines[at] and not lines[at].strip().startswith("#") else ""
        lines[at] = line + (f"   #{comment}" if comment else "")
    else:
        lines.insert(start + 1, line)


def set_phone(path, hh, key, phone, name="", relation=""):
    """The user's (key 'me') or a person's phone. A member added in the app becomes a household.yaml person."""
    number = normalize(phone)
    if not number:
        raise ValueError("That does not look like a phone number. Use +91 and 10 digits (or + and the country code).")
    p = Path(path)
    lines = p.read_text(encoding="utf-8").splitlines()
    if key == "me":
        top = _find(lines, "user", 0)
        if top is None:
            raise ValueError("household.yaml has no user: section.")
        _set_field(lines, top, 0, "phone", number)
    else:
        people = _find(lines, "people", 0)
        if people is None:
            lines += ["people:"]
            people = len(lines) - 1
        if lines[people].rstrip().endswith("{}"):
            lines[people] = "people:"
        end = _block(lines, people, 0)
        at = _find(lines, key, 2, people + 1, end)
        if at is None:
            block = [f"  {key}:                     # added in the app", f"    name: {json.dumps(name or key, ensure_ascii=False)}"]
            if relation:
                block.append(f"    relation: {json.dumps(relation, ensure_ascii=False)}")
            block.append(f"    phone: {json.dumps(number)}")
            lines[people + 1:people + 1] = block
        else:
            _set_field(lines, at, 2, "phone", number)
    text = "\n".join(lines) + "\n"
    data = yaml.safe_load(text)
    got = data["user"]["phone"] if key == "me" else data["people"][key]["phone"]
    if got != number:
        raise RuntimeError("Could not update household.yaml safely.")
    p.write_text(text, encoding="utf-8")
    if key == "me":
        hh["user"]["phone"] = number
    elif key in hh["people"]:
        hh["people"][key]["phone"] = number
    else:
        hh["people"][key] = {k: v for k, v in data["people"][key].items()}
    return number
