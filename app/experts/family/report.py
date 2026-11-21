"""A member's weekly report as plain text for WhatsApp: health score with its parts, today's intake against their own
targets, today's doses, the goal bar and the checkups to ask the doctor about. Facts and estimates only; it passes
safety.check() like every health text (AGENTS.md rule 9) and the human chooses where to send it."""
import urllib.parse

from app.core import safety
from app.experts.family import checkups
from app.experts.family import meds as M
from app.experts.family import score as S
from app.experts.kitchen import pantry

PART = {"food": "Food", "medicines": "Medicines", "movement": "Movement", "checkins": "Check-in calls"}


def text(store, hh, m, daily_hour=None):
    h = S.score(store, m, daily_hour)
    t = pantry.today(store, hh, m["key"], goal=m["targets"])
    tot, tg = t["total"], t["targets"]
    pct = lambda v, g: f"{round(v / g * 100) if g else 0}%"
    who = f"{m['name']}" + (f", {m['age']}" if m.get("age") else "")
    rows = [f"*Pathya report: {who}*",
            f"Health score: {h['score'] if h['score'] is not None else '–'}/100 ({h['label']}). Habits over the last 7 days, "
            "not a medical test."]
    rows += [f"• {PART[p['part']]}: {p['percent']}%. {p['detail']}" for p in h["parts"]]
    rows.append(f"Today: {tot['kcal']:.0f}/{tg['kcal']} kcal ({pct(tot['kcal'], tg['kcal'])}), protein {tot['protein_g']:.0f}/"
                f"{tg['protein_g']} g ({pct(tot['protein_g'], tg['protein_g'])}), fibre {tot['fibre_g']:.0f}/{tg['fibre_g']} g, "
                f"added sugar {tot.get('sugar_g', 0):.0f} g (limit {tg.get('sugar_g', '-')} g).")
    if t["meals"]:
        rows.append("Meals: " + "; ".join(x["text"] for x in t["meals"][:6]))
    doses = M.today(store, m["key"])
    if doses:
        rows.append("Medicines today (as written): " + "; ".join(
            f"{d['slot']} {', '.join(d['meds'])}: {d['taken'] or 'not answered'}" for d in doses))
    g = m.get("goal_progress")
    if g:
        rows.append(f"Goal: {g['start']} → {g['target']} kg, {g['percent']}% of the way ({g['left_kg']} kg to go).")
    ups = checkups.for_member(m)
    if ups:
        rows.append(f"Checkups usually offered at {m['age']}+ (ask the doctor): " + ", ".join(c["what"] for c in ups))
    rows.append(f"Targets: {m['targets']['source']}")
    verdict = safety.check("\n".join(rows))
    return {"text": verdict.text, "safety": verdict.status,
            "wa": "https://wa.me/?text=" + urllib.parse.quote(verdict.text), "health": h}
