# AGENTS.md: QuickPick v2 (Experts)

QuickPick Experts phone a family's people (the cook, Amma) and their clinic, turn what they say into a Swiggy Instamart order or a doctor's appointment, and wait for a human tap before anything is committed. Read docs/BUILD_V2.md before any task.

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
- app/experts/kitchen/: swiggy.py (ordering rules, tested), expert.py
- app/experts/health/: expert.py, rx.py
- app/templates/, scripts/first_order.py, tests/, infra/

## Commands
- Run: uvicorn app.main:app --reload --port 8000
- Tests: python tests/test_swiggy_flow.py && python tests/test_v2.py && pytest -q
- Tunnel: ngrok http 8000

## Done means
Tests pass; you list the manual check steps; no change to the hard rules above; small, reviewable diffs.
