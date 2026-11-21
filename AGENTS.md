# AGENTS.md: Pathya v2 (Experts)

Pathya (family nutrition, from a phone call to the plate) phones a family's people (each member, the cook) and their clinic, in their language. It keeps a profile, personal targets, a food log and medicine reminders for every member; plans one menu with a plate per person; turns what people say into a Swiggy Instamart (or Zepto) order or a doctor's appointment; and waits for a human tap before anything is committed. Read docs/BUILD_V2.md before any task.

## Hard rules: never break them, never "simplify" them away
1. Only `swiggy.place()` may call Swiggy `checkout`, and only from a card the human tapped. Never retry checkout; on error, list active orders and stop.
2. The model's Swiggy connection is filtered to `AGENT_TOOLS` (no checkout, no payment tools). Keep it that way.
3. Never set `confirmDuplicate`. Never ask for, store or log a UPI ID. Show Swiggy's success message exactly as returned.
4. Before checkout, the card shows the cart, "To pay", "Your order will be delivered to: <address>", the payment options and the question "Do you want to proceed with placing this order to this address?".
5. `update_cart` replaces the whole cart: one call with every item.
6. `DRY_RUN=1` is the default. Never change the default; only the human sets `DRY_RUN=0`.
7. No scraping, no price comparison, no benchmarking of Swiggy or Zepto. Zepto is only a backup for items Instamart could not supply: the model gets no Zepto tools (code searches; the model only picks from shown results, checked in code), and only `zepto.place()` may call `create_order`, from a tapped card, never retried.
8. Phone calls: the first sentence says it is an AI and who it calls for; never read IDs aloud; read back at most 3 items at a time; every call has a time limit; only call numbers in household.yaml.
9. Health: never diagnose; never suggest, start, stop or change medicines or doses; never say a reading is good or bad. Keep `fits()` and the booking tools' refusals. Nothing is scheduled from a prescription until the human confirms. Every health text passes `safety.check()`.
10. Secrets only in `.env`. Never commit `.env`, `quickpick.db`, recordings or health data.

## Stack
Python 3.11+, FastAPI, Jinja2 + HTMX (Pico.css), SQLite (app/core/store.py), openai-agents (Agents SDK and realtime), mcp-remote for Swiggy, Twilio, boto3 (Bedrock Guardrails), pytest.

## Layout
- app/main.py: routes and lifespan
- app/concierge.py: one sentence to the right Experts
- app/core/: store.py, jobs.py, caller.py, safety.py, call_session.py
- app/experts/base.py: the Expert contract and registry
- app/experts/kitchen/: swiggy.py (ordering rules, tested), zepto.py, planner.py, pantry.py (at home, food log), expert.py
- app/experts/health/: expert.py, rx.py
- app/experts/family/: profiles.py (members, goals, targets), meds.py (as written, daily reminders), board.py (weekly leaderboard), scan.py (camera), checkups.py (age checkups, elder intake watch), guard.py (cart vs each member's own notes)
- app/experts/home/: the Family line: check-in and medicine reminder calls for any member with a household.yaml phone; doorstep/: unknown callers
- app/core/lang.py: call languages (Telugu default; household.yaml `language:` and per-person `language:`)
- app/core/convo.py: every call follows the caller's language and wraps up before end_call (refused until they confirm)
- app/core/voice.py: voice, accent, pace, turn-taking and the family's style notes (placed below the rules, never above)
- web/: the React app (Home, Family, Meals, Orders, More)
- mobile/: Android app (Capacitor launcher that opens the user's Pathya link; build with mobile/build-apk.ps1)
- app/templates/, scripts/first_order.py, tests/, infra/

## Commands
- Run: ./run.sh (local) or ./run.sh phone (tunnel + phone link); or uvicorn app.main:app --reload --port 8000
- Tests: python tests/test_swiggy_flow.py && python tests/test_v2.py && pytest -q
- Tunnel: ./run.sh phone (cloudflared via scripts/phone.py)

## Family nutrition (how rules 8 and 9 apply)
- Conditions are stored as the family says the doctor told them; they only choose dishes, portions and swaps. Nothing is diagnosed.
- Targets are a general reference (formula or ICMR-NIN), labelled as such; a nutritionist's numbers override them.
- Medicines are kept exactly as written; reminder calls only remind and record the answer in the person's words.
- The health score uses habits only (meals logged and near own targets, doses taken, steps, check-ins answered), never readings or weight; it is labelled "not a medical test".
- Booking a clinic that is not in household.yaml: a web lookup proposes the number with its source; it is written into household.yaml and phoned only after a human taps "Add and phone them".
- Members added in the app have no phone and are never called.
- Age checkups list what public programmes offer at that age (NP-NCD, WHO ICOPE, USPSTF), with the source, as "ask the doctor"; never "you have" or "you will get".
- The plate guard and calls only quote a member's own notes (goal, allergy, what the doctor said); the human who taps decides. No health claims of our own.
- Camera: meals are logged; medicines, prescriptions and body reports are copied as printed and saved only after a human confirms.

## Done means
Tests pass; you list the manual check steps; no change to the hard rules above; small, reviewable diffs.
