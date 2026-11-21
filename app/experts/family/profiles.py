"""Family members, their profiles and personal daily targets.
Members: the user ("me"), the household.yaml people (except the cook) and members added in the app. Only people with
a phone number in household.yaml are ever called; members added in the app have no phone here (AGENTS.md rule 8).
Conditions are stored exactly as the family says the doctor told them; nothing is ever diagnosed (rule 9).
Targets: a nutritionist's numbers when set; else a formula (body composition report, or Mifflin-St Jeor, x activity,
adjusted for the goal the family chose); else the ICMR-NIN reference for their sex. Always labelled as a general
reference, not a prescription."""
import re

from app.core import lang

GOALS = {"maintain": "Maintain", "bulk": "Bulk up", "cut": "Cut (lose fat)", "less_sugar": "Less sugar",
         "more_protein": "More protein", "less_salt": "Less salt"}
ACTIVITY = {"sedentary": 1.2, "light": 1.375, "active": 1.55}
REFERENCE = {"source": "ICMR-NIN 2020 general reference (sedentary adult)",
             "kcal": 1885, "protein_g": 50, "carbs_g": 260, "fat_g": 55, "fibre_g": 30, "sugar_g": 47, "salt_g": 5}
TEXT = ("name", "relation", "sex", "activity", "food", "allergies", "goal")
NUMBERS = {"age": (1, 120), "height_cm": (50, 230), "weight_kg": (3, 250)}
TARGET_KEYS = ("kcal", "protein_g", "carbs_g", "fat_g", "fibre_g", "sugar_g", "salt_g")
RESERVED = {"me", "family", "home", "caller", "clinic"}
ELDER_AGE = 60
# ICMR-NIN 2020 RDA, sedentary adults (reference body weights 65 kg man, 55 kg woman).
SEX_REFERENCE = {"male": {"kcal": 2110, "weight_kg": 65}, "female": {"kcal": 1660, "weight_kg": 55},
                 "": {"kcal": 1885, "weight_kg": 60}}
BODY = {"body_fat_pct": (2, 75), "skeletal_muscle_kg": (5, 80), "fat_mass_kg": (1, 150), "bmr_kcal": (500, 4000),
        "visceral_fat_level": (1, 60)}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:30] or "member"


def profile(store, key):
    return next((f["value"] for f in store.facts(key, "profile") if f["key"] == "profile"), None) or {}


def keys(hh, store):
    """Family members in order: me, household.yaml people (not the cook), then members added in the app."""
    people = [k for k, p in hh["people"].items() if p.get("role") != "cook"]
    added = [f["person"] for f in store.facts(prefix="profile") if f["key"] == "profile"
             and (f["value"] or {}).get("added") and f["person"] not in people and f["person"] != "me"]
    return ["me"] + people + added


def member(hh, store, key):
    """Everything the app knows about one member. The phone is only ever taken from household.yaml."""
    prof = profile(store, key)
    if key == "me":
        who = hh["user"]
        base = {"name": who["name"], "relation": "me", "phone": who.get("phone")}
    elif key in hh["people"]:
        who = hh["people"][key]
        base = {"name": who["name"], "relation": who.get("relation") or who.get("role") or "", "phone": who.get("phone"),
                "age": who.get("age")}
    elif prof.get("added"):
        who, base = {}, {"name": prof.get("name", key), "relation": "", "phone": None}
    else:
        raise KeyError(key)
    m = {**base, **{k: v for k, v in prof.items() if v not in (None, "") and k not in ("phone", "added")}}
    m.update(key=key, added=bool(prof.get("added")), has_phone=bool(base.get("phone")), language=lang.of(hh, who),
             conditions=list(prof.get("conditions") or []), goal=prof.get("goal") or "maintain",
             override=prof.get("override") or {}, body=prof.get("body") or {})
    m["elder"] = bool(m.get("age") and m["age"] >= ELDER_AGE)
    m["targets"] = targets(m)
    return m


def members(hh, store):
    return [member(hh, store, k) for k in keys(hh, store)]


def save(store, hh, key, data):
    """Update a profile with validated fields only. Conditions are kept as the family wrote them."""
    member(hh, store, key)                                           # KeyError if unknown
    prof = dict(profile(store, key))
    for k in TEXT:
        if k in data:
            prof[k] = str(data[k] or "").strip()[:120]
    for k, (lo, hi) in NUMBERS.items():
        if k in data:
            if data[k] in (None, ""):
                prof.pop(k, None)
                continue
            v = float(data[k])
            if not lo <= v <= hi:
                raise ValueError(f"{k} must be between {lo} and {hi}.")
            prof[k] = int(v) if k == "age" else round(v, 1)
    if "conditions" in data:
        items = data["conditions"] if isinstance(data["conditions"], list) else str(data["conditions"] or "").split(",")
        prof["conditions"] = [str(c).strip()[:60] for c in items if str(c).strip()][:10]
    if "body" in data:                                               # a body composition report, as printed
        b = data["body"] or {}
        prof["body"] = {k: float(b[k]) for k, (lo, hi) in BODY.items() if b.get(k) not in (None, "") and lo <= float(b[k]) <= hi}
        if b.get("date"):
            prof["body"]["date"] = str(b["date"])[:20]
    if "override" in data:
        t = data["override"] or {}
        prof["override"] = {k: float(t[k]) for k in TARGET_KEYS if t.get(k) not in (None, "")}
    if prof.get("goal") and prof["goal"] not in GOALS:
        raise ValueError(f"goal must be one of: {', '.join(GOALS)}.")
    if prof.get("activity") and prof["activity"] not in ACTIVITY:
        raise ValueError(f"activity must be one of: {', '.join(ACTIVITY)}.")
    if key == "me" or key in hh["people"]:
        prof.pop("name", None)                                       # names of yaml people come from household.yaml
    store.remember(key, "profile", prof, "family")
    return member(hh, store, key)


def add(store, hh, name, relation=""):
    name = str(name).strip()[:40]
    if not name:
        raise ValueError("A name is needed.")
    taken = set(keys(hh, store)) | set(hh["people"]) | set(hh.get("clinics") or {}) | RESERVED
    key, n = slug(name), 2
    while key in taken:
        key, n = f"{slug(name)}-{n}", n + 1
    store.remember(key, "profile", {"name": name, "relation": str(relation).strip()[:40], "added": True}, "family")
    return member(hh, store, key)


def remove(store, key):
    """Only members added in the app can be removed (household.yaml people are edited there)."""
    return bool(profile(store, key).get("added")) and store.forget(key, "profile")


def targets(m):
    """Daily targets for one member, with where every part came from. Energy: BMR from a body composition report
    (as printed, or from lean mass), else Mifflin-St Jeor from age, height and weight, else the ICMR-NIN reference for
    their sex; then x activity and the goal (cut -400, bulk +300). Protein per kg: 0.8 (ICMR-NIN), 1.0 from 60 (ESPEN
    guidance for older adults), 1.6 for bulk/cut/more protein (1.2 from 60)."""
    age, h, w = m.get("age"), m.get("height_cm"), m.get("weight_kg")
    sex = str(m.get("sex") or "").lower()
    goal, body = m.get("goal") or "maintain", m.get("body") or {}
    child, elder = bool(age and age < 18), bool(age and age >= ELDER_AGE)
    act = ACTIVITY.get(m.get("activity") or "sedentary", 1.2)
    lean = w * (1 - body["body_fat_pct"] / 100) if w and body.get("body_fat_pct") else None
    if child:
        kcal, how = REFERENCE["kcal"], "ICMR-NIN adult reference; for children, ask your paediatrician"
    elif body.get("bmr_kcal"):
        kcal, how = body["bmr_kcal"] * act, "BMR from the body composition report x activity"
    elif lean:
        kcal, how = (370 + 21.6 * lean) * act, "lean mass from the body composition report (Katch-McArdle) x activity"
    elif age and h and w:
        offset = {"male": 5, "female": -161}.get(sex, -78)
        kcal, how = (10 * w + 6.25 * h - 5 * age + offset) * act, "age, height and weight (Mifflin-St Jeor) x activity"
    else:
        kcal = SEX_REFERENCE.get(sex, SEX_REFERENCE[""])["kcal"] * act / 1.2
        how = "ICMR-NIN 2020 reference for " + (f"{sex}s" if sex in ("male", "female") else "adults") + \
              "; add age, height and weight for a personal estimate"
    if not child:
        kcal += {"cut": -400, "bulk": 300}.get(goal, 0)
    per_kg = 1.6 if goal in ("bulk", "cut", "more_protein") else 0.8
    if elder:
        per_kg = 1.2 if goal in ("bulk", "cut", "more_protein") else 1.0
    weight = w or SEX_REFERENCE.get(sex, SEX_REFERENCE[""])["weight_kg"]
    protein = round(weight * per_kg)
    kcal = round(kcal)
    fat = round(kcal * 0.25 / 9)
    goal_note = {"cut": ", -400 kcal to cut", "bulk": ", +300 kcal to bulk"}.get(goal, "")
    out = {"kcal": kcal, "protein_g": protein, "fat_g": fat, "carbs_g": max(0, round((kcal - protein * 4 - fat * 9) / 4)),
           "fibre_g": 30, "sugar_g": round(kcal * (0.05 if goal == "less_sugar" else 0.10) / 4), "salt_g": 5,
           "source": f"Energy from {how}{goal_note}; protein {per_kg} g per kg" + (" (60+)" if elder else "") +
                     (f" of {weight:g} kg" if w else f" of a {weight} kg reference") +
                     ". A general reference, not a prescription."}
    if m.get("override"):
        out.update({k: v for k, v in m["override"].items() if k in TARGET_KEYS})
        out["source"] = "Set by your nutritionist"
    return out


def average(members):
    """The household's per-person reference: the mean of every member's own targets."""
    if not members:
        return dict(REFERENCE)
    out = {k: round(sum(m["targets"][k] for m in members) / len(members)) for k in TARGET_KEYS}
    return {**out, "source": f"average of {len(members)} family members' own targets"}


def describe(m):
    """One line for prompts: who eats, what they want, their limits (conditions as the doctor told the family)."""
    bits = [f"{m['name']} ({m['relation'] or 'family'}" + (f", {m['age']}" if m.get("age") else "") + ")",
            f"goal: {GOALS.get(m['goal'], m['goal'])}", f"food: {m.get('food') or 'veg'}"]
    if m.get("allergies"):
        bits.append(f"allergies (never include): {m['allergies']}")
    if m["conditions"]:
        bits.append("doctor told the family: " + ", ".join(m["conditions"]))
    t = m["targets"]
    bits.append(f"about {t['kcal']} kcal, protein {t['protein_g']} g, added sugar under {t['sugar_g']} g a day")
    return "; ".join(bits)
