"""Phone sign-in. A family member types their number (it must be the user's or a family member's phone in
household.yaml, not the cook's or a clinic's), Twilio Verify texts a code, and the app keeps a session token instead
of the ?key= link (which keeps working for the owner). Tokens are stored only as SHA-256 hashes and last 30 days."""
import hashlib
import os
import re
import secrets
import time

from app.core.household import normalize

SESSION_DAYS = 30
PREFIX = "pathya_"


def _digits(n):
    return re.sub(r"\D", "", str(n or ""))[-10:]


def who_has(hh, phone):
    """(member key, name) for a number in household.yaml that may sign in, else None."""
    d = _digits(normalize(phone))
    if not d:
        return None
    if d == _digits(hh["user"].get("phone")):
        return "me", hh["user"]["name"]
    for k, p in hh["people"].items():
        if p.get("role") != "cook" and _digits(p.get("phone")) == d:
            return k, p["name"]
    return None


def verify_sid(client, store):
    """The Twilio Verify service: TWILIO_VERIFY_SID, else one created once (named Pathya) and remembered."""
    sid = os.getenv("TWILIO_VERIFY_SID") or next(
        (f["value"] for f in store.facts("app", "verify_sid") if f["key"] == "verify_sid"), None)
    if not sid:
        sid = client.verify.v2.services.create(friendly_name="Pathya", code_length=6).sid
        store.remember("app", "verify_sid", sid, "twilio")
    return sid


def send_code(client, store, phone):
    return client.verify.v2.services(verify_sid(client, store)).verifications.create(to=normalize(phone), channel="sms").status


def code_ok(client, store, phone, code):
    if not re.fullmatch(r"\d{4,10}", str(code or "").strip()):
        return False
    r = client.verify.v2.services(verify_sid(client, store)).verification_checks.create(to=normalize(phone),
                                                                                         code=str(code).strip())
    return r.status == "approved"


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(store, who, name, phone):
    token = PREFIX + secrets.token_urlsafe(24)
    store.remember("app", f"session:{_hash(token)}", {"who": who, "name": name, "phone_end": _digits(phone)[-4:],
                                                     "created": time.time()}, "phone sign-in")
    return token


def session(store, token, now=None):
    """The session for a token (who, name, phone_end), or None when unknown or older than SESSION_DAYS."""
    if not str(token or "").startswith(PREFIX):
        return None
    key = f"session:{_hash(token)}"
    row = next((f for f in store.facts("app", key) if f["key"] == key), None)
    if not row or (now or time.time()) - row["value"].get("created", 0) > SESSION_DAYS * 86400:
        return None
    return row["value"]


def end_session(store, token):
    if str(token or "").startswith(PREFIX):
        store.forget("app", f"session:{_hash(token)}")
