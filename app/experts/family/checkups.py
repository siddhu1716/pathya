"""Age-based checkups to ask the doctor about, and an intake watch for older family members.
This never diagnoses (AGENTS.md rule 9): it lists what public programmes routinely offer people of this age and sex,
with the source, and points to the doctor. Conditions a member already has are only what the family entered."""
import time
from datetime import datetime, timedelta

from app.experts.family.meds import IST

# (min age, sex or "" for all, what to ask about, why, source)
CHECKUPS = [
    (30, "", "Blood pressure check", "High BP is common after 30 and often has no symptoms.",
     "India NP-NCD: free screening for adults 30+"),
    (30, "", "Blood sugar check", "Diabetes is common after 30 and often has no symptoms.",
     "India NP-NCD: free screening for adults 30+"),
    (30, "", "Mouth check (oral cancer screening)", "Offered to every adult 30+.", "India NP-NCD"),
    (30, "female", "Breast examination", "Offered to women 30+.", "India NP-NCD"),
    (30, "female", "Cervical cancer screening", "Offered to women 30+.", "India NP-NCD"),
    (60, "", "Memory", "Changes in memory are worth mentioning early.", "WHO ICOPE checks for older people"),
    (60, "", "Walking, balance and falls", "Falls are a common risk after 60.", "WHO ICOPE"),
    (60, "", "Appetite and weight loss", "Eating less or losing weight without trying needs a doctor's look.",
     "WHO ICOPE"),
    (60, "", "Eyesight", "Vision often changes after 60.", "WHO ICOPE"),
    (60, "", "Hearing", "Hearing often changes after 60.", "WHO ICOPE"),
    (60, "", "Mood and sleep", "Low mood is easy to miss in older people.", "WHO ICOPE"),
    (65, "female", "Bone density (osteoporosis)", "Recommended for women 65+.", "USPSTF"),
]


def for_member(m):
    age, sex = m.get("age"), str(m.get("sex") or "").lower()
    if not age:
        return []
    return [{"what": what, "why": why, "source": src} for lo, s, what, why, src in CHECKUPS
            if age >= lo and (not s or s == sex)]


def watch(store, m, days=2, now=None, share=0.6):
    """Older members only: facts for the family, never a judgement. If meals were logged on each of the last `days`
    days and energy or protein stayed under `share` of their own target, say so (the family decides what to do)."""
    if not m.get("elder"):
        return []
    now = now or time.time()
    t = m["targets"]
    low_kcal = low_protein = 0
    for back in range(1, days + 1):
        day = (datetime.fromtimestamp(now, IST) - timedelta(days=back)).strftime("%Y-%m-%d")
        meals = [f["value"] for f in store.facts(m["key"], f"meal:{day}:")]
        if not meals:
            return []                                            # nothing logged: no conclusion at all
        low_kcal += sum(x.get("kcal", 0) for x in meals) < share * t["kcal"]
        low_protein += sum(x.get("protein_g", 0) for x in meals) < share * t["protein_g"]
    notes = []
    if low_kcal == days:
        notes.append(f"Logged meals came to under {int(share * 100)}% of {m['name']}'s energy reference on each of the "
                     f"last {days} days.")
    if low_protein == days:
        notes.append(f"Logged protein was under {int(share * 100)}% of {m['name']}'s reference on each of the last "
                     f"{days} days.")
    return notes
