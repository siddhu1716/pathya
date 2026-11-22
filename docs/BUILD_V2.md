# Pathya v2 — Experts

**Build document · Builders '26 (OpenAI × Equal AI, powered by AWS) · Track 1: Build Creative**
Shiva Nampalli · Equal AI HQ, Hyderabad · Sat 21 – Sun 22 Nov 2026 · **Code freeze: Sunday 2:00 PM**

> **One line:** Pathya Experts phone your family and your clinic in Telugu, turn what they say into a Swiggy order or a doctor's appointment, and wait for your one tap before anything is committed.

---

## 0. The one-page version

**What you are building.** A household AI made of **Experts**. Each Expert owns one job: its tools, its phone persona and its follow-ups. All Experts share one platform: phone calls, cards to approve, memory, a scheduler and a safety check.

| Expert | What it does | Real integration | When |
|---|---|---|---|
| **Kitchen** | Calls the cook or Amma for the grocery list → Swiggy Instamart cart → you tap → order (cash on delivery or Swiggy's own UPI) | Swiggy Builders Club MCP (Instamart) | Now → Saturday evening |
| **Health** | Phones the clinic and books inside your window → calendar + reminder calls → check-in with Amma → doctor brief → prescription photo → reminders → follow-up booking | Phone calls, calendar file, AWS Bedrock Guardrails | Saturday night → Sunday morning |
| Next | Restaurant food, Dineout, bills, home services | Swiggy Food / Dineout MCP and others | Slide 5 only |

**Three rules the code enforces (say them on stage):**

1. **Experts prepare; humans commit.** Orders, bookings outside your window and reminders start only after a tap.
2. **Limits live in code, not in prompts.** Cart cap, total re-checked before checkout, no checkout retries, booking window, double-tap guard.
3. **The Health Expert never gives medical advice.** It schedules, reminds and relays. Every health text passes Bedrock Guardrails.

**Build order and go/no-go gates** (times computed for Sat 21 → Sun 22 Nov):

| Phase | What | From | To | Hours | Gate |
|---|---|---|---|---|---|
| 0 | Setup: repo, Codex, Swiggy sign-in, Twilio, Guardrail | Sat 12:30 | Sat 13:00 | 0.5 |  |
| 1 | Kitchen: first real Swiggy order (COD) | Sat 13:00 | Sat 14:30 | 1.5 | GATE: order placed? |
| 2 | Platform + Approvals page | Sat 14:30 | Sat 17:30 | 3 |  |
| 3 | Phone calls: call the cook → cart card | Sat 17:30 | Sat 21:30 | 4 | GATE: call → card works? |
| 4 | Health Expert: booking call, reminders, check-in, doctor brief | Sat 21:30 | Sun 02:00 | 4.5 |  |
| – | Sleep | Sun 02:00 | Sun 05:30 | 3.5 |  |
| 5 | Prescriptions, memory, reorders, polish | Sun 05:30 | Sun 09:30 | 4 | Feature freeze 9:30 |
| 6 | Demo video, slides, README | Sun 09:30 | Sun 12:00 | 2.5 |  |
| 7 | Buffer and submit (by 1:30 PM) | Sun 12:00 | Sun 14:00 | 2 | Code freeze 2:00 PM |
| | **Total to code freeze** | Sat 12:30 | Sun 14:00 | **25.5** | 22 h building, 3.5 h sleep |

**Judges score:** a working end-to-end demo, AI-native, presentation and craft. **Submit:** code repository, working demo (deployed link or recording), 4–5 slides (problem, what you built, how it works, what's next).

---

## 1. Why this idea fits this room

- **Track 1 brief:** personal context turned into an everyday AI product, shown as a working journey from raw input to a useful outcome. Raw input here: a Telugu phone call, a prescription photo. Outcome: groceries delivered, an appointment booked, reminders running.
- **Equal AI (the hosts, hiring from this room)** runs an AI call assistant for India that handles 10+ languages and code-mixed speech. Its stated next steps are an assistant that acts for the user, including **outbound calls to book appointments** (TechCrunch, 11 Jun 2026), and a **concierge layer for shopping and everyday tasks** (Economic Times, 12 Jun 2026). The Health Expert's booking call is exactly that outbound call; the Experts model is that concierge layer.
- **OpenAI:** Realtime voice on real phone calls, the Agents SDK with MCP tools and tracing, vision for prescriptions.
- **AWS:** Bedrock Guardrails as the Health Expert's safety layer (ApplyGuardrail on every health text); the AWS account for hosting later.
- **Swiggy:** the official Builders Club MCP supports AI agents. No scraping anywhere.

---

## 2. What you have and what each is for

| You have | Use it for | Watch out |
|---|---|---|
| OpenAI API credits ($250) | Agents SDK (Concierge, Kitchen cart builder), Realtime voice for calls, vision for prescriptions | Realtime calls are likely your biggest spend: every call has a time limit, rehearse short, set a budget alert on the project |
| ChatGPT Pro | **Codex** as your coding agents: the CLI in the repo plus cloud tasks in parallel; slide copy | Read every diff that touches ordering or health rules yourself |
| AWS (Bedrock via CLI + the hackathon account) | **Bedrock Guardrails** for health texts; hosting after the demo works | Don't move the voice path to AWS during the build |
| Dots | Read here as **dots.ocr**, the open-source (MIT) document parser from rednote-hilab: a second prescription and lab-report reader if you have a GPU endpoint. Otherwise use the OpenAI vision reader in Appendix B | If "Dots" is something else, it fits in as an optional tool. Don't block on it |
| Swiggy Builders Club MCP | Instamart: addresses, search, cart, payment options, checkout, payment status, confirm, delivery status, past orders | No scraping, no price comparison; show Swiggy's success message as-is |
| Twilio | Outbound phone calls bridged to OpenAI Realtime | A trial account is too restricted; upgrade first (§5.4) |
| Open source | openai-agents-python `examples/realtime/twilio`, `mcp-remote` | Keep dependency setup documented in the README |

---

## 3. Product: how the Experts work

### 3.1 The household

`household.yaml` (Appendix C) lists you (the approver), Amma (Telugu, her clinic), Lakshmi garu (the cook), the clinics, and the delivery address hint. For the demo, a friend plays the clinic receptionist. **Only people who agreed to AI calls go in this file.**

### 3.2 Journeys (each one is a demo beat)

| # | Journey | Raw input → useful outcome |
|---|---|---|
| K1 | Call to order | Lakshmi garu tells the AI the list in Telugu → Swiggy cart card → tap cash or UPI → order + ETA |
| K2 | Type to order | "2 litres milk, curd, kottimeera" → the same card |
| K3 | Usual list | Recent orders + go-to items → suggested weekly list (Phase 5) |
| H1 | Book by phone | "Amma's BP review with Dr. Rao this week, mornings" → AI phones the clinic → books only inside the window → calendar file + reminder calls |
| H2 | Asking the doctor | Day-before call to Amma: how she feels, readings, her questions → one-page doctor brief in her words → WhatsApp draft to the clinic |
| H3 | After the visit | Prescription photo → lines to confirm → reminder calls at 9 AM / 2 PM / 9 PM → offer to book the review when it is due |
| X1 | Experts share memory | The doctor wrote "low salt diet" → the next Kitchen cart picks low-sodium salt, and the agent's note says why |

### 3.3 What each Expert never does

- **Kitchen:** never places an order without a tap, never retries a failed checkout, never asks for a UPI ID.
- **Health:** never diagnoses, never suggests or changes medicines or doses, never says whether a reading is good or bad, and never shares more than name, age, reason and callback number with a clinic. If Amma describes an emergency, it tells her to call 108 and raises an urgent card for you at once.

---

## 4. Architecture

```
          Web app (phone-first): Home · Ask Pathya · Cards to tap · Upcoming calls (Run now) · Timeline
                                                   │
                                       FastAPI (your Pathya repo)
  ┌────────────────────────────────────────────────┼─────────────────────────────────────────────┐
  │ Concierge agent (Agents SDK). Experts are its tools: order_groceries · book_doctor ·         │
  │                                                      check_in · call_for_list                │
  │ Kitchen Expert ── swiggy.py ── mcp-remote ── Swiggy Instamart MCP                            │
  │ Health Expert ─── booking window · calendar file · doctor brief · prescription reader        │
  │ Shared: Caller (Twilio ⇄ OpenAI Realtime) · Cards (approvals) · Jobs (scheduler)             │
  │         Facts (household memory) · Events (timeline) · Safety (Bedrock Guardrails)           │
  └──────────────────────────────────────────────────────────────────────────────────────────────┘

 A phone call: jobs.tick → caller.dial (Twilio REST; TwiML <Connect><Stream> with <Parameter job_id>)
   → wss /media-stream → expert.call_plan(job) → RealtimeAgent(instructions, tools)
   → tools fill plan.saved → call ends → expert.after_call(job, saved) → Card → you tap → expert.execute(card, choice)
```

The **Concierge** (`app/concierge.py`) routes requests to the appropriate Expert. Ordering uses official MCP integrations, never scraping.

### 4.1 The Expert contract (`app/experts/base.py`)

| Member | Called by | Returns |
|---|---|---|
| `call_plan(job)` | Caller, when the person answers | `CallPlan`: persona, greeting (says it is an AI), tools, `saved` |
| `after_call(job, saved)` | Caller, when the call ends | a `Card` to tap, or nothing |
| `run_task(job)` | Scheduler, for jobs that are not calls | a `Card`, or nothing |
| `execute(card, choice)` | Card route, **only after a tap** | the result (order, calendar file, new jobs) |
| `call_kinds` | Scheduler | which job kinds are phone calls |

Adding an Expert means one folder plus `register(MyExpert(...))`. **Time how long the Health Expert takes to add; that number goes on slide 3.**

### 4.2 Data: one SQLite file (`app/core/store.py`)

| Table | Holds | Used for |
|---|---|---|
| approvals | cards; status waiting → running → done / failed / rejected | one-tap commits, double-tap guard, no silent retry |
| jobs | calls and tasks with a run time | reminders, follow-ups, the weekly list, **Run now** |
| facts | household memory: medicines, doctor's advice, check-ins, usual items | Experts sharing context |
| events | timestamped log | the journey timeline on stage |

### 4.3 Routes to build (FastAPI)

| Route | Does |
|---|---|
| `GET /` | Home: waiting cards, upcoming jobs with **Run now**, timeline, Ask box |
| `POST /ask` | Concierge (`app/concierge.py`) |
| `POST /kitchen/plan` · `POST /kitchen/call/{person}` | Kitchen K2 / K1 |
| `POST /health/book` · `POST /health/checkin/{person}` · `POST /health/rx` | Health H1 / H2 / H3 (photo upload → reader → medicines card) |
| `GET /cards/{id}` · `POST /cards/{id}/tap` · `POST /cards/{id}/reject` · `GET /cards/{id}/ics` | Tap = `store.claim` → `expert.execute` → `store.finish`. UPI: open `pay_url`, run `kitchen.settle` in the background, then show Swiggy's message and the ETA |
| `POST /jobs/{id}/run-now` | Demo time-travel |
| `POST /calls/status` · `WS /media-stream` | Twilio status callback; the Realtime bridge |

**Lifespan:** open the two Swiggy connections with an `AsyncExitStack`: `bridge("im-agent", AGENT_TOOLS)` for the model and `bridge("im-ops")` for your own code. Then build the Store and the Experts, `register` them, and start `jobs.run_forever`.

### 4.4 Rules enforced in code (already in Appendix B; keep them)

| Rule | Where |
|---|---|
| The model can fill the cart but can never check out | tool filter `AGENT_TOOLS` in `swiggy.py` |
| Cart re-read before checkout; refused if the total changed or is over the cap | `swiggy.place` |
| Checkout never retried; on error, active orders are listed | `swiggy.place` |
| UPI: poll inside Swiggy's window; confirm only when needed; never after a failure | `swiggy.finish_upi` |
| Swiggy's question, address line and success message shown as-is | `KitchenExpert.card` / `execute` |
| `DRY_RUN=1` by default: no real orders while building | `KitchenExpert.execute` |
| One tap = one execution | `Store.claim` |
| Booking only inside the family's window | `HealthExpert` `book_slot` → `fits` |
| Nothing scheduled from a prescription until a human confirms | `meds_card` → `execute` |
| Health texts pass Bedrock Guardrails | `safety.check` in `brief_card` |
| Every call has a time limit | `caller.make_dial` (`time_limit`) |

---

## 5. Setup (first 30 minutes)

### 5.1 Repo and coding agents

```bash
cd pathya && git status                                 # clean tree first
git checkout -b v2-experts
# The repo contains app/, scripts/, tests/, infra/, docs/BUILD_V2.md,
# AGENTS.md, .env.example and household.example.yaml.
npm i -g @openai/codex mcp-remote                       # Codex CLI + Swiggy's bridge, preinstalled
codex                                                   # first run: sign in with your ChatGPT Pro account
```

- Codex reads `AGENTS.md` (Appendix A), so the hard rules travel with every task.
- Run 2–3 Codex cloud tasks in parallel on independent parts (UI templates, Health routes, Caller), each on its own branch. Merge after the tests pass.
- Read ordering and health-rule diffs yourself before merging.

### 5.2 Python

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install openai-agents openai fastapi "uvicorn[standard]" jinja2 python-multipart pyyaml twilio boto3 pytest
python tests/test_swiggy_flow.py && python tests/test_v2.py     # both must print PASSED
cp .env.example .env && cp household.example.yaml household.yaml # then fill them in
```

Also install anything else the realtime Twilio example's README lists.

### 5.3 Swiggy

```bash
npx -y mcp-remote https://mcp.swiggy.com/im             # phone + OTP in the browser, then Ctrl+C
```

Save the venue (RMZ The Loft, Raidurg) as an address in the Swiggy app and keep `ADDRESS_HINT=Loft`.

### 5.4 Twilio (do this early: it gates Phase 3)

- **Upgrade the account.** A trial can only call verified numbers, only within your own country, blocks some TwiML verbs, and caps each call at 10 minutes and the whole trial at 75 minutes.
- Buy a **US voice number**. Twilio's India guidelines require calls into India to come from an international number.
- Voice → Settings → **Geo permissions** → enable India.
- `ngrok http 8000` → put the host, without `https://`, in `PUBLIC_HOST`.
- Only call people who agreed: you, Amma, Lakshmi garu and the friend playing the clinic. The agent says it is an AI in its first sentence.

### 5.5 AWS Bedrock Guardrail (10 minutes)

```bash
export AWS_REGION=us-east-1          # or the region where your Bedrock access is enabled
aws bedrock create-guardrail --region "$AWS_REGION" --name qp-health \
  --description "Pathya Health Expert: no diagnosis, no medicine advice, no reading results" \
  --topic-policy-config file://infra/guardrail_topics.json \
  --content-policy-config file://infra/guardrail_content.json \
  --sensitive-information-policy-config file://infra/guardrail_pii.json \
  --blocked-input-messaging "Pathya can't help with that. Please ask the doctor." \
  --blocked-outputs-messaging "Held for review: Pathya doesn't give medical advice. Please ask the doctor."
aws bedrock create-guardrail-version --region "$AWS_REGION" --guardrail-identifier <guardrailId from above>
```

Put `GUARDRAIL_ID` and `GUARDRAIL_VERSION=1` in `.env`. The default (CLASSIC) topic tier understands English, French and Spanish, so the check runs on English text: the brief is in English, with Amma's Telugu words quoted inside it.

### 5.6 OpenAI

Create a project for Builders, an API key and a budget alert. Put the realtime and vision model names your dashboard lists into `.env`.

---

## 6. Build plan, phase by phase

Each phase has a goal, a Codex prompt to paste as-is, a "done when" check and an "if stuck" exit. The prompts point Codex at this document, which the starter zip already places at `docs/BUILD_V2.md`.

### Phase 0: Setup (Sat 12:30–13:00, 0.5 h)

**Done when:** both test files print PASSED, Swiggy sign-in is done, Twilio is upgraded with a US number, `.env` and `household.yaml` are filled, and the Guardrail exists.

### Phase 1: First real Kitchen order (Sat 13:00–14:30, 1.5 h) · GATE

```bash
python scripts/first_order.py "2 packets milk, 1 curd, half kg tomatoes"
```

Answer **no** the first time (rehearsal). Then run it again and answer **yes** and cash.

- **Done when:** Swiggy prints its own success message and an ETA, and you film the delivery arriving (demo proof).
- **If stuck:** the venue isn't serviceable → deliver to an address where someone can receive it. Swiggy refuses sign-in from your code → §10.

### Phase 2: Platform and the Approvals page (Sat 14:30–17:30, 3 h)

> **Codex prompt:** Read AGENTS.md and docs/BUILD_V2.md §4. Build the FastAPI app in app/main.py with the routes in §4.3, using Jinja2 templates and HTMX, mobile-first, with Pico.css from a CDN. Use app/core/store.py, app/core/jobs.py and the Experts in app/experts exactly as they are; do not change swiggy.py. Load household.yaml. Open the two Swiggy connections in the lifespan as §4.3 says. Card page: title, lines, "To pay", "Your order will be delivered to: <address>", warnings in amber, the card's question, one button per choice (hx-disabled-elt), and a result area that shows Swiggy's message exactly as returned plus the cancel line. Show a red DRY RUN banner when DRY_RUN=1. Home shows waiting cards, upcoming jobs with Run now, and the last 20 timeline events. Unhook the old scraper routes. Add tests with stand-in Experts.

- **Done when:** a list typed on Home becomes a real Swiggy cart card; tapping cash in DRY_RUN shows the dry-run line; a second tap does nothing.

### Phase 3: Phone calls (Sat 17:30–21:30, 4 h) · GATE

> **Codex prompt:** Copy examples/realtime/twilio from openai-agents-python into app/core/call_session.py, keeping its licence header, audio settings and Twilio signature check. Change it so that it: (1) reads job_id from Twilio's "start" message with app.core.caller.job_id_from_start; (2) loads the job from the Store and the Expert from REGISTRY; (3) builds RealtimeAgent(name=expert.title, instructions=plan.instructions, tools=[function_tool(f) for f in plan.tools]) from expert.call_plan(job), with the model from REALTIME_MODEL; (4) once end_call has run, waits 3 seconds and calls caller.hang_up; (5) when the stream closes, saves the transcript to facts as "call:<job_id>" and adds the card from expert.after_call(job, plan.saved). Dialling is app.core.caller.make_dial with a twilio Client, triggered by jobs.run_forever. Add POST /calls/status. Log every step to the events table.

Test order: call your own phone first in English, then Lakshmi garu in Telugu.

- **Done when:** Run now → her phone rings → the AI says it is an AI → she gives 4 items → it reads them back, at most 3 at a time → hangs up → a Swiggy cart card appears.
- **If stuck:** Telugu sounds poor → let the persona follow her language (a Telugu-English mix is fine) and speak slower. Twilio blocked → **Phase 3b**: a "Record voice note" button → transcription → `kitchen.handle(text)`; same card, same demo.

### Phase 4: Health Expert (Sat 21:30–02:00, 4.5 h)

Order: H1 booking call → booking card, calendar file, reminder jobs → H2 check-in call → doctor brief with Guardrails → urgent card.

> **Codex prompt:** Read docs/BUILD_V2.md §7. Wire app/experts/health/expert.py into the app: a "Book a doctor" form (patient, clinic, from and to dates, part of day, reason) calling HealthExpert.book; a "Check in now" button calling HealthExpert.checkin; GET /cards/{id}/ics returning the card's payload.ics as text/calendar. Booking cards show slot, clinic, fee and what to bring. Brief cards show a "Safety: passed / held / off" badge from payload.safety and open payload.wa for "WhatsApp draft". Urgent cards are red and stay at the top. Register HealthExpert in the lifespan. Do not change the prompts, fits() or the tools' refusal rules.

- **Done when:** the friend's phone (the clinic) rings → the AI asks for slots → a slot outside the window is refused by code (visible in the timeline) → a morning slot is booked → card → "Calendar + reminder calls" → Run now on the reminder → Amma's call in Telugu → brief card with the safety badge.
- **If stuck:** keep H1 and the brief; drop H3 to slides.

### Phase 5: Prescriptions, memory, reorders (Sun 05:30–09:30, 4 h)

1. `POST /health/rx`: photo → `rx.read_prescription` → `meds_card` → confirm → reminder jobs, advice facts and a follow-up job.
2. The Kitchen already reads advice facts in `KitchenExpert.handle`: demo X1.
3. Usual list: `get_orders` (last 15 days) and `your_go_to_items` → facts `usual:*` → mentioned on the weekly call, plus a "Reorder usual" button.
4. Stretch: a 3-day meal plan from facts (doctor's advice, Amma's likes, the cook's dishes) → ingredients → `kitchen.handle`.

- **Done when:** a photo of a hand-written test prescription becomes a card, confirming it creates reminders, and the next cart's agent note mentions low-sodium salt.

### Phase 6: Demo, slides, README (Sun 09:30–12:00, 2.5 h)

- Record every demo segment on video by 10:00 AM, as the backup if a live call fails.
- README: what it is, the architecture picture, how to run, and the implemented features.

### Phase 7: Buffer and submit (Sun 12:00–14:00, 2 h)

Submit by **1:30 PM**: repo link, demo video (or deployed link) and slides. Code freeze is 2:00 PM.

---

## 7. Health Expert, in detail

### 7.1 Booking call (H1)

- **Input:** patient, clinic, window start and end (IST), part of day (morning 7–12, afternoon 12–17, evening 17–21), reason.
- **The window is your approval.** `book_slot` refuses anything outside it. A slot outside the window becomes `hold_slot` → hold card → "confirm" calls back for that exact slot.
- **Shares only** name, age, reason and your callback number. No payment talk on calls.
- **After the call:** booking card → "Calendar + reminder calls" (the evening before at 7 PM, and 3 hours after the visit) or "Calendar only".
- **Tools:** `offer_slots(slots)`, `book_slot(slot, doctor, fee, bring)`, `hold_slot(slot, note)`, `end_call(summary)`.

### 7.2 Check-in call and the doctor brief (H2: "asking the doctor")

- One question at a time: how she feels, anything new and since when, any readings she has, medicines taken, and her questions for the doctor.
- `save_checkin` stores her words plus an English summary. `alert_family` raises an urgent card at once, and the AI tells her to call 108.
- **The brief** holds her words, readings as she said them, medicines as listed by the family and her questions, with no interpretation. It is Guardrails-checked and shows a badge. "WhatsApp draft" opens a pre-filled message to the clinic; you press send.

### 7.3 Prescription → reminders (H3)

- The reader copies and never interprets (`READ_RX` in `rx.py`): names exactly as written, 1-0-1 notation, unclear lines flagged, advice copied verbatim, review date.
- Nothing is scheduled until you confirm the card. Unclear lines say "check with the pharmacist".
- **Confirm** → reminder calls at 9 AM / 2 PM / 9 PM for the times on the prescription; advice saved for the Kitchen Expert; a follow-up job 3 days before the review → "Book the review?" card → booking call.

### 7.4 Guardrail (files in Appendix C)

Denied topics: Diagnosis, Medication advice, Result interpretation. Plus misconduct and prompt-attack filters, card numbers blocked, and Aadhaar-like numbers masked.
Test it with three sentences that must be held ("She probably has diabetes", "Give her one more tablet", "150 by 95 is fine") and one that must pass (a real brief). If a real brief is held, tighten the topic definitions.

### 7.5 Privacy and consent

- Health data stays in the local SQLite file. Never commit `quickpick.db`, recordings or `.env`.
- Keep sensitive data out of traces for health runs (Agents SDK `RunConfig(trace_include_sensitive_data=False)`), or turn tracing off for them.
- Only call people who agreed. The AI identifies itself first. Add a "Forget this person" button that deletes their facts.

---

## 8. Demo script (about 3 minutes)

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:20 | Problem | "At home, groceries and doctor visits run on phone calls in Telugu, and I'm the switchboard." |
| 0:20–1:20 | Kitchen live (K1) | Run now → Lakshmi garu's phone on speaker → Telugu call → card with the real Swiggy cart, address line and cash option → tap → Swiggy's message → timeline with timestamps → clip of this afternoon's delivery at the venue |
| 1:20–2:20 | Health live (H1 + H2) | Ask: "Book Amma's BP review with Dr. Rao this week, mornings" → the friend's phone rings → 4 PM refused by code (timeline) → 10:30 booked → card → calendar + reminders → Run now → Amma's call → doctor brief with "Safety: passed" |
| 2:20–2:40 | Experts share memory (H3 + X1) | Prescription photo → confirm → the next cart's agent note: low-sodium salt, because of the doctor's advice |
| 2:40–3:00 | Close | Architecture slide: "Experts prepare, humans commit. Adding the Health Expert took [N] hours on the same platform." |

**Live-demo safety:** set `DRY_RUN=0` only for the live Kitchen order. Keep the recorded clips ready, phones charged and on speaker, and a hotspot as Wi-Fi backup.

---

## 9. Slides (5)

1. **Problem:** Indian homes run on phone calls: the cook's list, Amma's appointments, reminders. One person is the switchboard.
2. **What we built:** Pathya Experts. Kitchen is live on Swiggy Instamart; Health handles bookings, check-ins, doctor briefs and reminders. Screenshot of a card.
3. **How it works:** the architecture diagram, the Expert contract, and "Health Expert added in [N] hours".
4. **Trust and results:** the human tap, limits in code, Bedrock Guardrails; measured journey times from the timeline (call → cart → order → delivered).
5. **What's next:** more Experts (Swiggy Food, Dineout, bills, home services); pre-approved budgets with UPI Reserve Pay (Swiggy's payment options already carry `reservePay` and `agenticPaymentEligible`); consented health records; Experts behind an incoming-call assistant like Equal AI's.

---

## 10. Risks and fallbacks

| Risk | Early sign | Fallback |
|---|---|---|
| Swiggy refuses sign-in from your own code | auth error on the first run | (a) Zepto's MCP: list its tools, adapt `place()`; (b) ask builders@swiggy.in for staging access, with a short video of the flow; (c) a stand-in server built from Swiggy's published schemas, plus a real order recorded through a supported AI client from Swiggy's "Connect your AI client" page |
| Instamart doesn't serve the venue | address warning on the card | Deliver where someone can receive it, and film it |
| Twilio can't reach Indian numbers | call fails or geo error | Recheck the upgrade and geo permissions; else Phase 3b (voice note) or a browser "Talk to Pathya" page using Realtime over WebRTC |
| Telugu voice quality | the first test call | Follow the speaker's language; shorter sentences; read back at most 3 items |
| The model calls update_cart more than once | odd cart lines | `place()` re-reads the cart anyway, and the card shows the real cart before any tap |
| Guardrail holds a harmless brief | "held" badge | Tighten topic definitions; the card still shows, with a review warning |
| Credits run low | usage page | Call time limits, short rehearsals, the budget alert |
| Fatigue | — | Keep the sleep block; feature freeze at 9:30 AM |

---

## 11. After Builders: the next Experts

- **Health, deeper:** hospital booking where hospitals offer APIs; consented records through India's digital health stack (ABDM); a lab-report reader (dots.ocr) that leaves interpretation to the doctor; insurance paperwork.
- **Food:** Swiggy Food and Dineout MCP for dinner orders and table bookings.
- **Home:** bills, gas cylinder, household staff schedules, repairs.
- **Payments:** pre-approved monthly budgets (UPI Reserve Pay), so routine reorders under a limit need no tap.

---

## Appendix A: AGENTS.md (copy to the repo root; the starter zip has it)

```markdown
# AGENTS.md: Pathya v2 (Experts)

Pathya Experts phone a family's people (the cook, Amma) and their clinic, turn what they say into a Swiggy Instamart order or a doctor's appointment, and wait for a human tap before anything is committed. Read docs/BUILD_V2.md before any task.

## Hard rules: never break them, never "simplify" them away
1. Only `swiggy.place()` may call Swiggy `checkout`, and only from a card the human tapped. Never retry checkout; on error, list active orders and stop.
2. The model's Swiggy connection is filtered to `AGENT_TOOLS` (no checkout, no payment tools). Keep it that way.
3. Never set `confirmDuplicate`. Never ask for, store or log a UPI ID. Show Swiggy's success message exactly as returned.
4. Before checkout, the card shows the cart, "To pay", "Your order will be delivered to: <address>", the payment options and the question "Do you want to proceed with placing this order to this address?".
5. `update_cart` replaces the whole cart: one call with every item.
6. `DRY_RUN=1` is the default. Never change the default; only the human sets `DRY_RUN=0`.
7. No scraping, no price comparison, no benchmarking of Swiggy or Zepto.
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
```

## Appendix B: Starter code

All of it is in the starter zip. The ordering, approvals, scheduler, caller, safety, Kitchen and Health logic passed the two test files with stand-ins for Swiggy, Twilio and Bedrock: no network, no real orders, no real calls. `rx.py` and `concierge.py` are reference code that compiles but needs the real packages. `call_session.py` and `main.py` are for Codex to write (Phases 2–3).

**`app/experts/base.py`**

```python
"""Pathya v2 - the Expert contract. One folder per Expert; the platform
(caller, approvals, jobs, memory, safety) is shared by all of them."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable


@dataclass
class CallPlan:
    """How the phone agent behaves on one call. Tools write what they capture into `saved`."""
    instructions: str                     # persona prompt: says it is an AI, and who it calls for
    greeting: str                         # first sentence once the person answers
    tools: list[Callable] = field(default_factory=list)   # plain functions; the caller wraps them
    max_minutes: int = 5
    saved: dict = field(default_factory=dict)


@dataclass
class Card:
    """What the human sees before anything is committed (money, bookings, reminders)."""
    expert: str
    kind: str                             # order | booking | hold | brief | meds | alert | info | followup
    title: str
    lines: list[str]
    total: str | None = None
    address: str | None = None
    question: str = "Approve?"
    choices: list[dict] = field(default_factory=lambda: [{"id": "approve", "label": "Approve"}])
    warnings: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)        # what execute() needs; never shown

    def to_dict(self) -> dict:
        return asdict(self)


class Expert:
    name = "base"
    title = "Expert"
    handles = ""                          # one line the Concierge uses to route requests
    call_kinds: set = set()               # job kinds that are phone calls; the rest are tasks

    def call_plan(self, job: dict) -> CallPlan:
        raise NotImplementedError

    async def after_call(self, job: dict, saved: dict) -> Card | None:
        return None

    async def run_task(self, job: dict) -> Card | None:
        return None

    async def execute(self, card: dict, choice: str) -> dict:
        """Runs ONLY after a human tapped `choice` on this card."""
        raise NotImplementedError


REGISTRY: dict = {}


def register(expert: Expert) -> Expert:
    if expert.name in REGISTRY:
        raise ValueError(f"Expert {expert.name!r} registered twice")
    REGISTRY[expert.name] = expert
    return expert
```

**`app/core/store.py`**

```python
"""One SQLite file for the household: approvals (human taps), jobs (calls and tasks that run later),
facts (memory shared by all Experts) and events (the journey timeline shown in the demo)."""
import json
import sqlite3
import time
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, expert TEXT, card TEXT, status TEXT,
    choice TEXT, result TEXT, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, expert TEXT, kind TEXT, person TEXT,
    payload TEXT, run_at REAL, status TEXT, result TEXT, created REAL);
CREATE TABLE IF NOT EXISTS facts(person TEXT, key TEXT, value TEXT, source TEXT, updated REAL,
    PRIMARY KEY (person, key));
CREATE TABLE IF NOT EXISTS events(ts REAL, expert TEXT, ref TEXT, what TEXT);
"""


def _new_id():
    return uuid.uuid4().hex[:10]


class Store:
    def __init__(self, path="quickpick.db"):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- events: what happened, when (the demo timeline) ----
    def log(self, expert, ref, what):
        self.db.execute("INSERT INTO events VALUES (?,?,?,?)", (time.time(), expert, ref, what))

    def timeline(self, ref=None, limit=50):
        q, args = "SELECT * FROM events", []
        if ref:
            q, args = q + " WHERE ref=?", [ref]
        return [dict(r) for r in self.db.execute(q + " ORDER BY ts DESC LIMIT ?", args + [limit])]

    # ---- approvals: nothing is committed without a human tap ----
    def add_card(self, card):
        aid, now = _new_id(), time.time()
        self.db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?)",
                        (aid, card["expert"], json.dumps(card), "waiting", None, None, now, now))
        self.log(card["expert"], aid, f"card: {card['title']}")
        return aid

    def claim(self, aid, choice):
        """waiting -> running exactly once; a second tap gets None (double-tap guard)."""
        cur = self.db.execute("UPDATE approvals SET status='running', choice=?, updated=? "
                              "WHERE id=? AND status='waiting'", (choice, time.time(), aid))
        if cur.rowcount != 1:
            return None
        self.log("approvals", aid, f"tapped: {choice}")
        return json.loads(self.db.execute("SELECT card FROM approvals WHERE id=?", (aid,)).fetchone()[0])

    def finish(self, aid, ok, result):
        """running -> done | failed. A failed card never returns to waiting: no silent retries."""
        self.db.execute("UPDATE approvals SET status=?, result=?, updated=? WHERE id=? AND status='running'",
                        ("done" if ok else "failed", json.dumps(result, default=str), time.time(), aid))
        self.log("approvals", aid, "done" if ok else f"failed: {result}")

    def reject(self, aid):
        return self.db.execute("UPDATE approvals SET status='rejected', updated=? WHERE id=? AND status='waiting'",
                               (time.time(), aid)).rowcount == 1

    def card(self, aid):
        r = self.db.execute("SELECT * FROM approvals WHERE id=?", (aid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["card"] = json.loads(d["card"])
        d["result"] = json.loads(d["result"]) if d["result"] else None
        return d

    def cards(self, status="waiting"):
        rows = self.db.execute("SELECT id FROM approvals WHERE status=? ORDER BY created DESC", (status,)).fetchall()
        return [self.card(r["id"]) for r in rows]

    # ---- jobs: calls and tasks that run later ----
    def add_job(self, expert, kind, person, payload, run_at=None):
        jid = _new_id()
        self.db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                        (jid, expert, kind, person, json.dumps(payload),
                         time.time() if run_at is None else run_at, "scheduled", None, time.time()))
        self.log(expert, jid, f"scheduled {kind} for {person}")
        return jid

    def job(self, jid):
        r = self.db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        if not r:
            return None
        return dict(r, payload=json.loads(r["payload"]), result=json.loads(r["result"]) if r["result"] else None)

    def due(self, now=None):
        now = time.time() if now is None else now
        rows = self.db.execute("SELECT id FROM jobs WHERE status='scheduled' AND run_at<=? ORDER BY run_at",
                               (now,)).fetchall()
        return [self.job(r["id"]) for r in rows]

    def upcoming(self):
        rows = self.db.execute("SELECT id FROM jobs WHERE status='scheduled' ORDER BY run_at").fetchall()
        return [self.job(r["id"]) for r in rows]

    def start_job(self, jid):
        return self.db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='scheduled'",
                               (jid,)).rowcount == 1

    def end_job(self, jid, ok, result=None):
        self.db.execute("UPDATE jobs SET status=?, result=? WHERE id=?",
                        ("done" if ok else "failed", json.dumps(result, default=str), jid))

    def run_now(self, jid):
        """Demo button: a scheduled job becomes due immediately."""
        return self.db.execute("UPDATE jobs SET run_at=? WHERE id=? AND status='scheduled'",
                               (time.time(), jid)).rowcount == 1

    # ---- facts: household memory shared by all Experts ----
    def remember(self, person, key, value, source):
        self.db.execute("INSERT INTO facts VALUES (?,?,?,?,?) ON CONFLICT(person, key) DO UPDATE SET "
                        "value=excluded.value, source=excluded.source, updated=excluded.updated",
                        (person, key, json.dumps(value, default=str), source, time.time()))

    def facts(self, person=None, prefix=""):
        q, args = "SELECT * FROM facts WHERE key LIKE ?", [prefix + "%"]
        if person:
            q, args = q + " AND person=?", args + [person]
        return [dict(r, value=json.loads(r["value"])) for r in self.db.execute(q + " ORDER BY updated", args)]
```

**`app/core/jobs.py`**

```python
"""The scheduler: every few seconds, start the jobs that are due. Phone-call jobs go to the
Caller; everything else goes to the Expert's run_task, whose result becomes a card to tap."""
import asyncio


def make_dispatch(store, experts, dial):
    async def dispatch(job):
        expert = experts[job["expert"]]
        if job["kind"] in expert.call_kinds:
            sid = await asyncio.to_thread(dial, job["payload"]["to"], job["id"])
            store.log(expert.name, job["id"], f"calling {job['person']}")
            return {"call_sid": sid}
        card = await expert.run_task(job)
        return {"card": store.add_card(card.to_dict())} if card else {}
    return dispatch


async def tick(store, dispatch, now=None):
    """Start every due job exactly once. Returns the ids started."""
    started = []
    for job in store.due(now):
        if not store.start_job(job["id"]):
            continue
        started.append(job["id"])
        try:
            store.end_job(job["id"], True, await dispatch(job))
        except Exception as err:              # one bad job never stops the loop
            store.end_job(job["id"], False, str(err))
            store.log(job["expert"], job["id"], f"failed: {err}")
    return started


async def run_forever(store, dispatch, every=10):
    while True:
        await tick(store, dispatch)
        await asyncio.sleep(every)
```

**`app/core/caller.py`**

```python
"""Outbound calls. Twilio dials the person, then streams the call audio to our /media-stream
WebSocket, where the Realtime agent (adapted from openai-agents-python examples/realtime/twilio)
runs the Expert's CallPlan. The job id travels as a <Parameter> inside <Stream>."""
import os
from xml.sax.saxutils import quoteattr


def stream_twiml(public_host, job_id):
    url = f"wss://{public_host}/media-stream"
    return ("<Response><Connect>"
            f"<Stream url={quoteattr(url)}><Parameter name=\"job_id\" value={quoteattr(job_id)} /></Stream>"
            "</Connect></Response>")


def make_dial(twilio_client, from_number=None, public_host=None, max_minutes=None):
    host = public_host or os.environ["PUBLIC_HOST"]          # e.g. abcd-1234.ngrok-free.app (no https://)
    sender = from_number or os.environ["TWILIO_FROM"]        # your Twilio number in E.164 (+1...)
    limit = int(max_minutes or os.getenv("CALL_MAX_MINUTES", "6")) * 60

    def dial(to, job_id):
        call = twilio_client.calls.create(
            to=to, from_=sender, twiml=stream_twiml(host, job_id),
            time_limit=limit,                                # hard stop for cost and runaway calls
            status_callback=f"https://{host}/calls/status",
            status_callback_event=["completed"])
        return call.sid
    return dial


def job_id_from_start(message):
    """Twilio's 'start' message carries our <Parameter> values in start.customParameters."""
    if message.get("event") != "start":
        return None
    return ((message.get("start") or {}).get("customParameters") or {}).get("job_id")


def hang_up(twilio_client, call_sid):
    """After end_call: wait about 3 seconds so the goodbye plays, then hang up."""
    twilio_client.calls(call_sid).update(status="completed")
```

**`app/core/safety.py`**

```python
"""Health safety net: every health text Pathya sends or saves passes Amazon Bedrock
Guardrails (ApplyGuardrail) first. Denied topics: diagnosis, medicine advice, result reading."""
import os
from dataclasses import dataclass


@dataclass
class Verdict:
    status: str      # passed | blocked | unchecked
    text: str        # the text to use (the guardrail's replacement when blocked)


_client = None


def check(text, source="OUTPUT", client=None):
    gid = os.getenv("GUARDRAIL_ID")
    if not gid:
        return Verdict("unchecked", text)
    global _client
    if client is None:
        if _client is None:
            import boto3
            _client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        client = _client
    r = client.apply_guardrail(guardrailIdentifier=gid, guardrailVersion=os.getenv("GUARDRAIL_VERSION", "1"),
                               source=source, content=[{"text": {"text": text}}])
    if r.get("action") == "GUARDRAIL_INTERVENED":
        outs = r.get("outputs") or []
        return Verdict("blocked", outs[0].get("text", "") if outs else "")
    return Verdict("passed", text)
```

**`app/experts/kitchen/swiggy.py`**

```python
"""Pathya Kitchen - Swiggy Instamart core (Phase 1).
The model can look things up and fill the cart. It cannot place an order:
checkout is plain code, called only after a human says yes to the exact cart."""
import asyncio, json, os, re, time

from agents import Agent, Runner
from agents.mcp import MCPServerStdio, create_static_tool_filter

IM_URL = os.getenv("INSTAMART_MCP_URL", "https://mcp.swiggy.com/im")
MODEL = os.getenv("OPENAI_MODEL")                # empty = SDK default
CAP = float(os.getenv("CART_CAP", "1000"))       # our own safety cap, in rupees
CANCEL = "To cancel your order, please call Swiggy customer care at 080-67466729."
AGENT_TOOLS = ["get_addresses", "your_go_to_items", "search_products", "update_cart", "get_cart"]


def bridge(name, allowed=None):
    """Swiggy's documented mcp-remote bridge; sign-in is cached after the first run."""
    return MCPServerStdio(
        name=name,
        params={"command": "npx", "args": ["-y", "mcp-remote", IM_URL]},
        client_session_timeout_seconds=60,       # check_payment_status holds ~19 s
        cache_tools_list=True,
        tool_filter=create_static_tool_filter(allowed_tool_names=allowed) if allowed else None,
    )


def read(result):
    """Return (data, message). Data comes from structuredContent; failures raise."""
    text = next((c.text for c in (result.content or []) if getattr(c, "type", "") == "text"), "")
    sc = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None) or {}
    if not sc and text.lstrip().startswith("{"):
        try:
            sc = json.loads(text)
        except ValueError:
            sc = {}
    failed = getattr(result, "isError", False) or getattr(result, "is_error", False)
    if failed or (isinstance(sc, dict) and sc.get("success") is False):
        err = sc.get("error") if isinstance(sc, dict) else None
        raise RuntimeError(err.get("message") if isinstance(err, dict) else (err or text or "Swiggy call failed"))
    message = sc.get("message", "") if isinstance(sc, dict) else ""
    if isinstance(sc, dict) and isinstance(sc.get("data"), dict):
        sc = {**{k: v for k, v in sc.items() if k not in ("success", "data", "message")}, **sc["data"]}
    return sc, (message or text)


async def call(server, tool, args=None):
    return read(await server.call_tool(tool, args or {}))


def rupees(value):
    return float(re.sub(r"[^\d.]", "", str(value)) or 0)


async def pick_address(ops, hint=None):
    hint = (hint if hint is not None else os.getenv("ADDRESS_HINT", "")).lower()
    d, _ = await call(ops, "get_addresses")
    addrs = d.get("addresses", [])
    default_id = (d.get("resolution") or {}).get("defaultAddressId")
    hit = lambda a: hint and hint in f"{a.get('addressCategory', '')} {a.get('addressLine', '')}".lower()
    a = (next((a for a in addrs if hit(a)), None)
         or next((a for a in addrs if a.get("id") == default_id), None)
         or (addrs[0] if addrs else None))
    if not a:
        raise RuntimeError("No saved Swiggy address. Add one in the Swiggy app first.")
    return a


RULES = """You fill a Swiggy Instamart cart for an Indian household. You cannot place orders.
Delivery addressId: {aid}. Keep the total under Rs {cap:.0f}.
1. Call your_go_to_items first and prefer the family's usual products.
2. For anything else, call search_products with a short English query.
   Lists may be Telugu, Hindi or English: paalu = milk, perugu = curd, kandi pappu = toor dal,
   ullipayalu = onions, tamatalu = tomatoes, kottimeera = coriander.
3. Choose in-stock variations closest to the size asked for.
4. update_cart REPLACES the whole cart: send every item in ONE call with selectedAddressId
   and items [{{spinId, skuId, quantity}}].
5. Call get_cart, then reply in one or two lines: anything missing or substituted."""


async def build_cart(agent_im, shopping_list, address_id):
    agent = Agent(name="Kitchen cart builder",
                  instructions=RULES.format(aid=address_id, cap=CAP),
                  mcp_servers=[agent_im],
                  **({"model": MODEL} if MODEL else {}))
    run = await Runner.run(agent, shopping_list, max_turns=25)
    return run.final_output


def summary(cart, address, pay):
    rows = [f"  {i.get('itemName')} {i.get('itemVariant') or ''} x{i.get('quantity')}  Rs {i.get('discountedFinalPrice')}"
            for i in cart.get("items", [])]
    where = (cart.get("selectedAddressDetails") or {}).get("address") or address.get("addressLine")
    notes = [cart.get("addressWarning"), (cart.get("cartWarning") or {}).get("message")]
    notes += [f"Not available here: {i.get('itemName')}" for i in cart.get("unserviceableItems") or []]
    methods = [m.get("displayName") or m.get("id") for m in pay.get("allMethods", [])]
    return "\n".join(["Swiggy Instamart cart", *rows,
                      f"To pay: {cart['billBreakdown']['toPay']['value']}",
                      f"Your order will be delivered to: {where}",
                      f"Payment options: {', '.join(methods) or 'none returned'}",
                      *[f"Note: {n}" for n in notes if n]])


async def place(ops, address_id, approved_total, upi_app=None):
    """Call ONLY after the human said yes to this exact cart and address."""
    cart, _ = await call(ops, "get_cart")                     # stock and prices can change
    total = rupees(cart["billBreakdown"]["toPay"]["value"])
    if abs(total - approved_total) > 0.5:
        raise RuntimeError(f"Cart changed to Rs {total:.0f}. Show it again before placing.")
    if total > CAP:
        raise RuntimeError(f"Cart is Rs {total:.0f}, over the Rs {CAP:.0f} cap.")
    # Cash on delivery: get_payment_options labels it "COD", but checkout only accepts "Cash".
    args = {"addressId": address_id, "paymentMethod": "UPI" if upi_app else "Cash"}
    if upi_app:
        args["intentApp"] = upi_app                           # id copied exactly from get_payment_options
    try:
        return await call(ops, "checkout", args)
    except Exception as err:                                  # checkout is NOT idempotent: never retry blindly
        active, _ = await call(ops, "get_orders", {"activeOnly": True, "count": 3})
        ids = [o.get("orderId") for o in active.get("orders", [])]
        raise RuntimeError(f"Checkout failed ({err}). Active orders now: {ids}. Check them before trying again.")


async def finish_upi(ops, order):
    """Poll gently inside Swiggy's window; confirm only when Swiggy hasn't already."""
    deadline = time.monotonic() + order.get("maxTimeToPollForInMs", 300_000) / 1000
    ids = {"paasId": order["paasId"], "orderId": order["orderId"]}
    status, msg = {}, ""
    while time.monotonic() < deadline:
        status, msg = await call(ops, "check_payment_status", ids)
        if status.get("terminal"):
            break
        await asyncio.sleep(order.get("pollingIntervalInMs", 5000) / 1000)
    if status.get("terminal") and not status.get("isTerminalSuccess"):
        return False, msg or "Payment did not go through. Nothing was placed."
    if status.get("confirmed"):
        return True, msg
    done, msg = await call(ops, "confirm_order", ids)        # success not yet confirmed, or window ran out
    return done.get("result") == "success", msg


async def eta(ops, order_id, address_id):
    s, msg = await call(ops, "get_delivery_status", {"orderId": order_id, "addressId": address_id})
    return s.get("etaText") or s.get("statusText") or msg
```

**`app/experts/kitchen/expert.py`**

```python
"""Kitchen Expert: a list (from a call, a voice note or typing) -> Swiggy Instamart cart
-> one human tap -> order. Ordering rules live in swiggy.py (tested); this file wires them in."""
import os

from app.experts.base import CallPlan, Card, Expert
from app.experts.kitchen import swiggy as sw

LIST_CALL = """You are Pathya, an AI assistant, calling {who} for {user}'s family to take this week's grocery list.
Your first sentence: "{greeting}" Speak {lang}, simply and politely.
Ask what the kitchen needs this week; ask for quantities when missing.
You may remind them of at most three usual items: {usual}.
Call save_list with one entry per item, quantity included, in their words (for example "2 litres paalu").
Read the list back, at most three items at a time, fix corrections, then call save_list again with the final list.
Never discuss prices or payment. Finish with end_call."""


def dry_run():
    return os.getenv("DRY_RUN", "1") == "1"          # default: no real checkout while building


class KitchenExpert(Expert):
    name, title = "kitchen", "Kitchen Expert"
    handles = "groceries, milk, vegetables, kitchen supplies, the weekly list, reorders, meal-plan ingredients"
    call_kinds = {"list"}

    def __init__(self, store, household, agent_im, ops):
        self.store, self.hh, self.agent_im, self.ops = store, household, agent_im, ops

    def weekly_call(self, person, run_at=None):
        p = self.hh["people"][person]
        return self.store.add_job(self.name, "list", person, {"person": person, "to": p["phone"]}, run_at)

    def call_plan(self, job):
        p, user = self.hh["people"][job["payload"]["person"]], self.hh["user"]["name"]
        usual = [str(f["value"]) for f in self.store.facts(prefix="usual:")][:3]
        greeting = f"Namaskaram {p['name']}, I am Pathya, an AI assistant calling for {user} about this week's groceries."
        plan = CallPlan(LIST_CALL.format(who=p["name"], user=user, greeting=greeting,
                                         lang=p.get("language", "Telugu"), usual=", ".join(usual) or "none"),
                        greeting, max_minutes=5)

        def save_list(items: list[str], notes: str) -> str:
            """Save the grocery list: one entry per item, with quantity, in the person's words."""
            plan.saved.update(items=items, notes=notes)
            return "Saved. Read it back, at most three items at a time."

        def end_call(summary: str) -> str:
            """Finish the call with a one-line English summary."""
            plan.saved["summary"] = summary
            return "Say goodbye now."

        plan.tools = [save_list, end_call]
        return plan

    async def after_call(self, job, saved):
        items = saved.get("items") or []
        return await self.handle(", ".join(items), ref=job["id"]) if items else None

    async def handle(self, text, ref=None):
        advice = [str(f["value"]) for f in self.store.facts(prefix="advice:")]
        if advice:
            text += ("\nDoctor's advice in this home (use it only to choose between products, "
                     "for example low-sodium salt; never add items because of it): " + "; ".join(advice))
        addr = await sw.pick_address(self.ops, self.hh.get("address_hint"))
        note = await sw.build_cart(self.agent_im, text, addr["id"])
        cart, _ = await sw.call(self.ops, "get_cart")
        pay, _ = await sw.call(self.ops, "get_payment_options")
        return self.card(cart, pay, addr, note, ref)

    def card(self, cart, pay, addr, note="", ref=None):
        total = cart["billBreakdown"]["toPay"]["value"]
        choices = [{"id": "COD", "label": "Cash on delivery"}] if (pay.get("cod") or {}).get("available") else []
        for m in ((pay.get("platforms") or {}).get("mobile") or {}).get("methods", []):
            choices.append({"id": "UPI:" + m["id"], "label": "UPI - " + (m.get("displayName") or m["id"])})
        warnings = [w for w in (cart.get("addressWarning"), (cart.get("cartWarning") or {}).get("message")) if w]
        warnings += [f"Not available here: {i.get('itemName')}" for i in cart.get("unserviceableItems") or []]
        stores = {i.get("storeId") for i in cart.get("items", []) if i.get("storeId")}
        if len(stores) > 1:
            warnings.append(f"This cart comes from {len(stores)} stores and will arrive as {len(stores)} orders.")
        if not choices:
            warnings.append("Swiggy returned no payment options for this cart.")
        if note:
            warnings.append(f"Agent: {note}")
        lines = [" ".join(str(x) for x in (i.get("itemName"), i.get("itemVariant"), f"x{i.get('quantity')}",
                                            f"- Rs {i.get('discountedFinalPrice')}") if x) for i in cart.get("items", [])]
        where = (cart.get("selectedAddressDetails") or {}).get("address") or addr.get("addressLine")
        return Card(self.name, "order", "Swiggy Instamart cart", lines, total=total, address=where,
                    question="Do you want to proceed with placing this order to this address?",
                    choices=choices, warnings=warnings,
                    payload={"address_id": addr["id"], "approved_total": sw.rupees(total), "ref": ref})

    async def execute(self, card, choice):
        p = card["payload"]
        upi_app = choice.split(":", 1)[1] if choice.startswith("UPI:") else None
        if dry_run():
            return {"ok": True, "dry_run": True,
                    "message": f"DRY RUN: would place {card['total']} by {'UPI' if upi_app else 'cash on delivery'}."}
        order, msg = await sw.place(self.ops, p["address_id"], p["approved_total"], upi_app)
        out = {"ok": True, "message": msg, "order": order, "cancel": sw.CANCEL}   # show msg exactly as sent
        if order.get("status") == "PENDING_PAYMENT":
            out["pay_url"] = order["bridgeUrl"]       # open it; run settle() in the background
        return out

    async def settle(self, order):
        """UPI only: wait for the payment inside Swiggy's window; confirm only if needed."""
        return await sw.finish_upi(self.ops, order)

    async def eta(self, order_id, address_id):
        return await sw.eta(self.ops, order_id, address_id)
```

**`app/experts/health/expert.py`**

```python
"""Health Expert: books clinic appointments by phone, checks in with Amma, prepares a doctor
brief, and turns a confirmed prescription into reminder calls. It never gives medical advice:
it schedules, reminds and relays. It books only inside the family's window (enforced here)."""
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from app.core import safety
from app.experts.base import CallPlan, Card, Expert

IST = timezone(timedelta(hours=5, minutes=30))             # India has no daylight saving
PARTS = {"morning": (7, 12), "afternoon": (12, 17), "evening": (17, 21)}
DOSE_HOURS = {"morning": 9, "afternoon": 14, "night": 21}   # reminder call times, IST

NO_ADVICE = ("You never give medical advice: never suggest, start, stop or change a medicine or dose, and never "
             "say whether a symptom or reading is good or bad. If asked, say you will add it to the questions "
             "for the doctor.")
EMERGENCY = ("If she mentions chest pain, breathlessness, fainting, sudden weakness on one side, heavy bleeding, "
             "or says it is an emergency: call alert_family at once, tell her calmly to call 108 now, and end the call.")

CLINIC_CALL = """You are Pathya, an AI assistant, phoning {clinic} for {user} to book an appointment
for {patient} (age {age}) with {doctor}. Your first sentence: "{greeting}"
Speak the receptionist's language (Telugu, Hindi or English), in short sentences. Never pretend to be human.
Share only the patient's name and age, the reason "{reason}" and the callback number {callback}.
Wanted: {window}. Ask which slots are free and call offer_slots with them (ISO 8601, e.g. 2026-11-24T10:30).
Then call book_slot with one slot; it refuses anything outside the family's window. If none fit, ask them to
hold the earliest slot and call hold_slot. After booking, repeat date, time, doctor and what to bring once.
Never discuss payment details. Finish with end_call."""

CHECKIN_CALL = """You are Pathya, an AI assistant, calling {patient} for {user}. Speak simple, warm {lang},
slowly. Your first sentence: "{greeting}"
Purpose: {purpose}
Ask one thing at a time: how she feels; anything new and since when; today's BP or sugar reading if she has
one; whether she took {meds}; what she wants to ask the doctor. Then call save_checkin with her words and a
short English summary. {no_advice}
{emergency}
End warmly and call end_call."""


def to_ist(text):
    dt = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    return dt.replace(tzinfo=IST) if dt.tzinfo is None else dt.astimezone(IST)


def fits(slot, start, end, part=None):
    """The family's window, enforced in code rather than trusted to the model."""
    if not start <= slot < end:
        return False
    lo, hi = PARTS.get(part or "", (0, 24))
    return lo <= slot.hour < hi


def _esc(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def make_ics(uid, start, minutes, title, location, notes=""):
    utc = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Pathya//Experts//EN", "BEGIN:VEVENT",
            f"UID:{uid}@quickpick", f"DTSTAMP:{utc(datetime.now(timezone.utc))}", f"DTSTART:{utc(start)}",
            f"DTEND:{utc(start + timedelta(minutes=minutes))}", f"SUMMARY:{_esc(title)}",
            f"LOCATION:{_esc(location)}", f"DESCRIPTION:{_esc(notes)}", "BEGIN:VALARM", "TRIGGER:-PT2H",
            "ACTION:DISPLAY", "DESCRIPTION:Reminder", "END:VALARM", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(rows) + "\r\n"


def wa_link(phone, text):
    """A WhatsApp draft; the human presses send."""
    return f"https://wa.me/{''.join(c for c in str(phone) if c.isdigit())}?text={urllib.parse.quote(text)}"


def next_at(hour, now=None):
    now = (now or datetime.now(IST)).astimezone(IST)
    t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return t if t > now else t + timedelta(days=1)


class HealthExpert(Expert):
    name, title = "health", "Health Expert"
    handles = ("doctor appointments, clinic bookings, check-in calls, questions for the doctor, "
               "prescriptions, medicine reminders, follow-ups")
    call_kinds = {"book", "checkin"}

    def __init__(self, store, household):
        self.store, self.hh = store, household

    # ---- entry points: the Concierge's tools and the UI forms call these ----
    def book(self, patient, clinic, window_start, window_end, part, reason, run_at=None):
        """The window IS the family's approval: the phone agent can only book inside it."""
        payload = {"patient": patient, "clinic": clinic, "window_start": window_start, "window_end": window_end,
                   "part": part, "reason": reason, "to": self.hh["clinics"][clinic]["phone"]}
        return self.store.add_job(self.name, "book", clinic, payload, run_at)

    def checkin(self, patient, purpose, run_at=None):
        payload = {"patient": patient, "purpose": purpose, "to": self.hh["people"][patient]["phone"]}
        return self.store.add_job(self.name, "checkin", patient, payload, run_at)

    def meds(self, patient):
        rows = self.store.facts(patient, "meds")
        return rows[-1]["value"] if rows else []

    # ---- phone calls ----
    def call_plan(self, job):
        p = job["payload"]
        pat, user = self.hh["people"][p["patient"]], self.hh["user"]
        if job["kind"] == "book":
            return self._booking_plan(p, pat, user)
        return self._checkin_plan(p, pat, user)

    def _booking_plan(self, p, pat, user):
        c = self.hh["clinics"][p["clinic"]]
        start, end = to_ist(p["window_start"]), to_ist(p["window_end"])
        greeting = (f"Hello, I am Pathya, an AI assistant calling for {user['name']} "
                    f"to book an appointment with {c['doctor']}.")
        window = f"{p.get('part') or 'any time'}, {start:%a %d %b %H:%M} to {end:%a %d %b %H:%M}"
        plan = CallPlan(CLINIC_CALL.format(clinic=c["clinic"], user=user["name"], patient=pat["name"],
                                           age=pat.get("age", ""), doctor=c["doctor"], greeting=greeting,
                                           reason=p["reason"], callback=user["phone"], window=window),
                        greeting, max_minutes=6)
        s = plan.saved

        def ok(slot):
            try:
                return fits(to_ist(slot), start, end, p.get("part"))
            except ValueError:
                return False

        def offer_slots(slots: list[str]) -> str:
            """Record the free slots the clinic offered, as ISO 8601 date-times."""
            s["offered"] = slots
            good = [x for x in slots if ok(x)]
            return (f"These fit the family's window: {good}. Book one." if good else
                    "None fit the family's window. Ask for other slots, or ask them to hold the earliest one.")

        def book_slot(slot: str, doctor: str, fee: str, bring: str) -> str:
            """Book this exact slot (ISO 8601). Refused outside the family's window."""
            if s.get("booked"):
                return "Already booked. Repeat the details and end the call."
            if not ok(slot):
                return "Refused: outside the family's window. Ask for another slot, or ask them to hold one."
            s["booked"] = {"slot": to_ist(slot).isoformat(), "doctor": doctor or c["doctor"], "fee": fee, "bring": bring}
            return "Booked. Repeat the details once, thank them and end the call."

        def hold_slot(slot: str, note: str) -> str:
            """The clinic holds a slot outside the window until the family confirms."""
            s["held"] = {"slot": slot, "note": note}
            return "Noted. Tell them the family will call back to confirm."

        def end_call(summary: str) -> str:
            """Finish the call with a one-line English summary."""
            s["summary"] = summary
            return "Say goodbye now."

        plan.tools = [offer_slots, book_slot, hold_slot, end_call]
        return plan

    def _checkin_plan(self, p, pat, user):
        meds = ", ".join(m.get("name_as_written", "") for m in self.meds(p["patient"])) or "her usual medicines"
        greeting = f"Namaskaram {pat['name']}, I am Pathya, an AI assistant calling for {user['name']}."
        plan = CallPlan(CHECKIN_CALL.format(patient=pat["name"], user=user["name"], lang=pat.get("language", "Telugu"),
                                            greeting=greeting, purpose=p["purpose"], meds=meds,
                                            no_advice=NO_ADVICE, emergency=EMERGENCY),
                        greeting, max_minutes=5)
        s = plan.saved

        def save_checkin(feeling: str, new_symptoms: list[str], since: str, readings: list[str],
                         meds_taken: str, questions: list[str], her_words: str, summary_en: str) -> str:
            """Save what she said, in her words. Do not judge or interpret anything."""
            s["checkin"] = {"feeling": feeling, "new_symptoms": new_symptoms, "since": since, "readings": readings,
                            "meds_taken": meds_taken, "questions": questions, "her_words": her_words,
                            "summary_en": summary_en}
            return "Saved. Thank her and end the call."

        def alert_family(reason: str) -> str:
            """Use at once if she describes an emergency or urgently asks for her family."""
            s["alert"] = reason
            self.store.add_card(Card(self.name, "alert", f"Urgent: {pat['name']} needs you",
                                     [reason, f"Call her now: {pat.get('phone', '')}"], question="",
                                     choices=[{"id": "ok", "label": "I'm calling her"}]).to_dict())
            return "Family alerted. Tell her calmly to call 108 now if it is an emergency."

        def end_call(summary: str) -> str:
            """Finish the call with a one-line English summary."""
            s["summary"] = summary
            return "Say goodbye now."

        plan.tools = [save_checkin, alert_family, end_call]
        return plan

    async def after_call(self, job, saved):
        p = job["payload"]
        if job["kind"] == "book":
            if saved.get("booked"):
                return self._booked_card(p, saved["booked"])
            if saved.get("held"):
                h = saved["held"]
                return Card(self.name, "hold", "The clinic is holding a slot",
                            [h["slot"], h.get("note") or "", saved.get("summary") or ""],
                            question="Call back and confirm this slot?",
                            choices=[{"id": "confirm", "label": "Yes, confirm it"}, {"id": "skip", "label": "No"}],
                            payload={"request": p, "slot": h["slot"]})
            return Card(self.name, "info", "No appointment booked",
                        [saved.get("summary") or "No free slot inside the window."], question="",
                        choices=[{"id": "ok", "label": "OK"}])
        if saved.get("checkin"):
            self.store.remember(p["patient"], f"checkin:{job['id']}", saved["checkin"], "phone check-in")
            return self.brief_card(p["patient"])
        return None

    def _booked_card(self, p, b):
        c, pat = self.hh["clinics"][p["clinic"]], self.hh["people"][p["patient"]]
        when = to_ist(b["slot"])
        ics = make_ics(f"{p['patient']}-{when:%Y%m%d%H%M}", when, 30, f"{pat['name']} - {b['doctor']}", c["clinic"],
                       f"Reason: {p['reason']}. Booked by Pathya.")
        return Card(self.name, "booking", "Appointment booked",
                    [f"{when:%a %d %b, %I:%M %p} - {b['doctor']}", c["clinic"],
                     f"Fee: {b.get('fee') or 'not mentioned'}", f"Bring: {b.get('bring') or 'not mentioned'}"],
                    question="Add it to the calendar and set reminder calls for her?",
                    choices=[{"id": "remind", "label": "Calendar + reminder calls"},
                             {"id": "calendar", "label": "Calendar only"}],
                    payload={"patient": p["patient"], "clinic": p["clinic"], "slot": when.isoformat(),
                             "doctor": b["doctor"], "ics": ics})

    def brief_card(self, patient):
        """'Asking the doctor': what she said since the last visit, in her words, plus her questions."""
        pat = self.hh["people"][patient]
        checks = [f["value"] for f in self.store.facts(patient, "checkin:")]
        said = [c.get("her_words") or c.get("summary_en") for c in checks if c]
        readings = [r for c in checks for r in c.get("readings") or []]
        questions = [q for c in checks for q in c.get("questions") or []]
        meds = [m.get("name_as_written", "") for m in self.meds(patient)]
        text = "\n".join([f"Doctor brief: {pat['name']}, {pat.get('age', '')}",
                          "What she reported (her words): " + (" | ".join(x for x in said if x) or "nothing new"),
                          "Readings she gave: " + (", ".join(readings) or "none"),
                          "Medicines (as listed by the family): " + (", ".join(meds) or "not recorded"),
                          "Her questions for the doctor: " + ("; ".join(questions) or "none")])
        verdict = safety.check(text)
        warnings = {"blocked": ["The safety check held part of this brief. Review it before sharing."],
                    "unchecked": ["Safety check is off (set GUARDRAIL_ID)."]}.get(verdict.status, [])
        phone = self.hh["clinics"].get(pat.get("clinic", ""), {}).get("phone")
        return Card(self.name, "brief", f"Doctor brief for {pat['name']}", verdict.text.split("\n"),
                    question="Share it with the clinic?",
                    choices=[{"id": "share", "label": "WhatsApp draft"}, {"id": "ok", "label": "Keep"}],
                    warnings=warnings,
                    payload={"text": verdict.text, "safety": verdict.status,
                             "wa": wa_link(phone, verdict.text) if phone else None})

    def meds_card(self, patient, rx):
        """rx is the prescription reader's output. Nothing is scheduled until a human confirms."""
        lines, warnings = [], []
        for m in rx.get("meds", []):
            when = "/".join(k for k in DOSE_HOURS if m.get(k)) or "timing unclear"
            days = f"for {m['days']} days" if m.get("days") else ""
            lines.append(" ".join(str(x) for x in (m.get("name_as_written"), m.get("strength"), m.get("dose"),
                                                  when, m.get("food"), days) if x))
            if m.get("unclear") or when == "timing unclear":
                warnings.append(f"Check with the pharmacist: {m.get('name_as_written')}")
        warnings += [f"Could not read: {u}" for u in rx.get("unreadable_parts", [])]
        return Card(self.name, "meds", "Prescription" + (f" - {rx['doctor']}" if rx.get("doctor") else ""), lines,
                    question="Does this match the paper exactly? Reminders start only after you confirm.",
                    choices=[{"id": "confirm", "label": "Matches - set reminders"}, {"id": "discard", "label": "Discard"}],
                    warnings=warnings, payload={"patient": patient, "rx": rx})

    async def run_task(self, job):
        if job["kind"] == "followup":
            p = job["payload"]
            return Card(self.name, "followup", f"Review due with {p.get('doctor') or 'the doctor'}",
                        [f"The prescription said: review after {p['after_days']} days."],
                        question="Phone the clinic to book it (mornings, next 7 days)?",
                        choices=[{"id": "book", "label": "Yes, book it"}, {"id": "skip", "label": "Not now"}],
                        payload=p)
        return None

    async def execute(self, card, choice):
        kind, p = card["kind"], card["payload"]
        if kind == "booking":
            out = {"ok": True, "ics": p["ics"]}
            if choice == "remind":
                when = to_ist(p["slot"])
                clinic = self.hh["clinics"][p["clinic"]]["clinic"]
                eve = (when - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
                out["jobs"] = [
                    self.checkin(p["patient"], f"Remind her of tomorrow's appointment, {when:%a %d %b %I:%M %p}, "
                                 f"with {p['doctor']} at {clinic}. Ask what she wants to ask the doctor.",
                                 run_at=max(eve.timestamp(), time.time() + 60)),
                    self.checkin(p["patient"], f"After today's visit with {p['doctor']}: ask how it went and "
                                 "what the doctor said.", run_at=(when + timedelta(hours=3)).timestamp())]
            return out
        if kind == "hold" and choice == "confirm":
            r, slot = p["request"], to_ist(p["slot"])
            return {"ok": True, "jobs": [self.book(r["patient"], r["clinic"], slot.isoformat(),
                                                   (slot + timedelta(minutes=1)).isoformat(), None, r["reason"])]}
        if kind == "meds" and choice == "confirm":
            return self._start_reminders(p["patient"], p["rx"])
        if kind == "followup" and choice == "book":
            start = next_at(7)
            return {"ok": True, "jobs": [self.book(p["patient"], self.hh["people"][p["patient"]]["clinic"],
                                                   start.isoformat(), (start + timedelta(days=7)).isoformat(),
                                                   "morning", f"Review visit with {p.get('doctor') or 'the doctor'}")]}
        if kind == "brief" and choice == "share":
            return {"ok": True, "open": p.get("wa")}
        return {"ok": True}

    def _start_reminders(self, patient, rx):
        source = f"prescription {rx.get('doctor') or ''} {rx.get('date') or ''}".strip()
        self.store.remember(patient, "meds", rx.get("meds", []), source)
        for n, advice in enumerate(rx.get("advice_as_written", [])):
            self.store.remember(patient, f"advice:{n}", advice, source)    # the Kitchen Expert reads these
        jobs = []
        for part, hour in DOSE_HOURS.items():
            names = [m.get("name_as_written") for m in rx.get("meds", []) if m.get(part)]
            if names:
                jobs.append(self.checkin(patient, f"Medicine reminder ({part}): {', '.join(names)}. "
                                         "Ask if she has taken them.", run_at=next_at(hour).timestamp()))
        if rx.get("review_after_days"):
            due = time.time() + max(0, rx["review_after_days"] - 3) * 86400
            jobs.append(self.store.add_job(self.name, "followup", patient,
                                           {"patient": patient, "doctor": rx.get("doctor"),
                                            "after_days": rx["review_after_days"]}, due))
        return {"ok": True, "jobs": jobs}
```

**`app/experts/health/rx.py`**

```python
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
```

**`app/concierge.py`**

```python
"""Concierge: one sentence from the family -> the right Experts. Experts are TOOLS here (not
handoffs), so one request can start several ("Amma's BP review this week, and we're out of milk").
Reference code: build it per request so 'now' is fresh."""
import os
from datetime import datetime, timedelta, timezone

from agents import Agent, function_tool

IST = timezone(timedelta(hours=5, minutes=30))

CONCIERGE = """You run a household's Experts for {user}. Now: {now} (IST).
People: {people}. Clinics: {clinics}.
Turn the request into Expert actions and call the tools; one request may need several.
Dates for book_doctor are ISO 8601 in IST; "this week" means from now until Sunday 23:59.
Never give medical advice. Reply in one or two short lines saying what you started."""


def make_concierge(store, hh, kitchen, health):
    @function_tool
    async def order_groceries(items: str) -> str:
        """Groceries or kitchen supplies. Builds a Swiggy Instamart cart for the family to approve."""
        card = await kitchen.handle(items)
        return f"Cart ready for approval (card {store.add_card(card.to_dict())})."

    @function_tool
    def book_doctor(patient: str, clinic: str, window_start: str, window_end: str, part: str, reason: str) -> str:
        """Phone a clinic and book inside this window. part: morning, afternoon, evening or any."""
        jid = health.book(patient, clinic, window_start, window_end, None if part == "any" else part, reason)
        return f"Calling the clinic now (job {jid})."

    @function_tool
    def check_in(patient: str, purpose: str) -> str:
        """Phone a family member to check in: how they feel and what to ask the doctor."""
        return f"Calling now (job {health.checkin(patient, purpose)})."

    @function_tool
    def call_for_list(person: str) -> str:
        """Phone the cook (or anyone at home) to take this week's grocery list."""
        return f"Calling now (job {kitchen.weekly_call(person)})."

    people = ", ".join(f"{k} ({v['name']})" for k, v in hh["people"].items())
    clinics = ", ".join(f"{k} ({v['doctor']}, {v['clinic']})" for k, v in hh["clinics"].items())
    return Agent(name="Pathya",
                 instructions=CONCIERGE.format(user=hh["user"]["name"], people=people, clinics=clinics,
                                               now=datetime.now(IST).strftime("%a %d %b %Y %H:%M")),
                 tools=[order_groceries, book_doctor, check_in, call_for_list],
                 **({"model": os.environ["OPENAI_MODEL"]} if os.getenv("OPENAI_MODEL") else {}))
```

**`scripts/first_order.py`**

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""Phase 1 gate: one real Instamart order from your own code.
python scripts/first_order.py "2 packets milk, 1 curd, half kg tomatoes"   (answer 'no' the first time)"""
import asyncio, sys
from app.experts.kitchen.swiggy import (AGENT_TOOLS, CANCEL, bridge, build_cart, call, eta, finish_upi,
                     pick_address, place, rupees, summary)

YES = {"yes", "y", "confirm", "proceed"}


async def main(shopping):
    async with bridge("im-agent", AGENT_TOOLS) as agent_im, bridge("im-ops") as ops:
        addr = await pick_address(ops)
        print("Agent is building the cart...")
        note = await build_cart(agent_im, shopping, addr["id"])
        cart, _ = await call(ops, "get_cart")
        pay, _ = await call(ops, "get_payment_options")
        print(summary(cart, addr, pay), "\nAgent:", note)
        if input("Do you want to proceed with placing this order to this address? (yes/no) ").strip().lower() not in YES:
            return print("Not placed.")
        apps = ((pay.get("platforms") or {}).get("mobile") or {}).get("methods", [])
        cod = (pay.get("cod") or {}).get("available")
        upi_app = None
        if input(f"Pay with {'[c]ash on delivery or ' if cod else ''}[u]PI? ").strip().lower().startswith("u") or not cod:
            if not apps:
                return print("No UPI apps returned for this cart.")
            for n, a in enumerate(apps):
                print(f"  {n}: {a.get('displayName') or a['id']}")
            upi_app = apps[int(input("UPI app number: "))]["id"]
        order, msg = await place(ops, addr["id"], rupees(cart["billBreakdown"]["toPay"]["value"]), upi_app)
        ok = True
        if order.get("status") == "PENDING_PAYMENT":
            print("Pay here (scan on the laptop, or open on your phone):", order["bridgeUrl"])
            ok, msg = await finish_upi(ops, order)
        print(msg)                                            # Swiggy's own words, as-is
        if ok:
            for o in order.get("orders") or [order]:          # multi-store carts come back as several orders
                if o.get("orderId"):
                    print(o["orderId"], "-", await eta(ops, o["orderId"], addr["id"]))
        print(CANCEL)


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "2 packets milk, 1 curd, half kg tomatoes"))
```

**`tests/test_swiggy_flow.py`**

```python
import os
import sys, types, asyncio, json
ag = types.ModuleType("agents"); ag.Agent = object; ag.Runner = object
mcp = types.ModuleType("agents.mcp"); mcp.MCPServerStdio = object; mcp.create_static_tool_filter = lambda **k: k
sys.modules["agents"] = ag; sys.modules["agents.mcp"] = mcp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.experts.kitchen import swiggy as k

class T:  # text block
    def __init__(s, t): s.type, s.text = "text", t
class R:  # CallToolResult stand-in
    def __init__(s, sc=None, text="", err=False): s.structuredContent, s.content, s.isError = sc, [T(text)], err

CART = {"items": [{"itemName": "Heritage Toned Milk", "itemVariant": "500 ml", "quantity": 2, "discountedFinalPrice": 56}],
        "billBreakdown": {"toPay": {"label": "To pay", "value": "₹131"}},
        "selectedAddressDetails": {"address": "RMZ The Loft, Raidurg"}, "cartWarning": {"statusCode": 1, "message": "Min order ₹99"}}
class Fake:
    def __init__(s, script): s.script, s.calls = script, []
    async def call_tool(s, name, args):
        s.calls.append((name, args)); v = s.script[name]
        return v.pop(0) if isinstance(v, list) else v

async def run():
    # read(): envelope unwrapping + error raising
    d, m = k.read(R(text=json.dumps({"success": True, "data": {"a": 1}, "message": "Instamart order placed successfully"})))
    assert d == {"a": 1} and m == "Instamart order placed successfully"
    try: k.read(R(sc={"success": False, "error": {"message": "Address not serviceable"}})); assert False
    except RuntimeError as e: assert "serviceable" in str(e)
    assert k.rupees("₹1,031.50") == 1031.5
    print(k.summary(CART, {"addressLine": "x"}, {"allMethods": [{"id": "cod", "displayName": "Cash"}]}))
    # COD path
    f = Fake({"get_cart": R(sc=CART), "checkout": R(sc={"orderId": "O1", "status": "PLACED", "paymentMethod": "COD"}, text="Instamart order placed successfully")})
    d, m = await k.place(f, "A1", 131); assert d["orderId"] == "O1" and m.startswith("Instamart")
    assert f.calls[-1] == ("checkout", {"addressId": "A1", "paymentMethod": "Cash"})
    # cart changed since approval -> refuse
    try: await k.place(Fake({"get_cart": R(sc=CART)}), "A1", 120); assert False
    except RuntimeError as e: assert "changed" in str(e)
    # over cap -> refuse
    big = json.loads(json.dumps(CART)); big["billBreakdown"]["toPay"]["value"] = "₹1,200"
    try: await k.place(Fake({"get_cart": R(sc=big)}), "A1", 1200); assert False
    except RuntimeError as e: assert "cap" in str(e)
    # checkout error -> looks up active orders, no retry
    f = Fake({"get_cart": R(sc=CART), "checkout": R(sc={"success": False, "error": {"message": "502"}}), "get_orders": R(sc={"orders": [{"orderId": "O9"}]})})
    try: await k.place(f, "A1", 131); assert False
    except RuntimeError as e: assert "O9" in str(e) and [c[0] for c in f.calls].count("checkout") == 1
    # UPI: pending -> success, already confirmed by Swiggy -> no confirm_order call
    order = {"orderId": "O2", "paasId": "P2", "pollingIntervalInMs": 10, "maxTimeToPollForInMs": 2000}
    f = Fake({"check_payment_status": [R(sc={"terminal": False}), R(sc={"terminal": True, "isTerminalSuccess": True, "confirmed": True}, text="Instamart order placed successfully")]})
    ok, m = await k.finish_upi(f, order); assert ok and "confirm_order" not in [c[0] for c in f.calls]
    # UPI: success but not confirmed -> confirm once with orderId + paasId
    f = Fake({"check_payment_status": R(sc={"terminal": True, "isTerminalSuccess": True}), "confirm_order": R(sc={"orderId": "O2", "result": "success"}, text="Instamart order placed successfully")})
    ok, m = await k.finish_upi(f, order); assert ok and f.calls[-1] == ("confirm_order", {"paasId": "P2", "orderId": "O2"})
    # UPI: failed -> never confirm
    f = Fake({"check_payment_status": R(sc={"terminal": True, "isTerminalFailure": True, "status": "failed"})})
    ok, m = await k.finish_upi(f, order); assert not ok and "confirm_order" not in [c[0] for c in f.calls]
    # UPI: window runs out while pending -> confirm once
    f = Fake({"check_payment_status": R(sc={"terminal": False}), "confirm_order": R(sc={"result": "pending"})})
    ok, m = await k.finish_upi(f, {**order, "maxTimeToPollForInMs": 50}); assert not ok and [c[0] for c in f.calls].count("confirm_order") == 1
    print("ALL FLOW CHECKS PASSED")
asyncio.run(run())
```

**`tests/test_v2.py`**

```python
"""Logic checks for the v2 platform with stand-ins (no network, no real orders, no real calls)."""
import asyncio, os, sys, time, types
from datetime import datetime, timedelta, timezone

ag = types.ModuleType("agents"); ag.Agent = object; ag.Runner = object
mcp = types.ModuleType("agents.mcp"); mcp.MCPServerStdio = object; mcp.create_static_tool_filter = lambda **k: k
sys.modules.setdefault("agents", ag); sys.modules.setdefault("agents.mcp", mcp)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import caller as C, jobs as J, safety as S
from app.core.store import Store
from app.experts.base import Card, register
from app.experts.health.expert import IST, HealthExpert, make_ics
from app.experts.kitchen import swiggy as sw
from app.experts.kitchen.expert import KitchenExpert

HH = {"user": {"name": "Shiva", "phone": "+919800000000"},
      "people": {"amma": {"name": "Amma", "language": "Telugu", "phone": "+919800000001", "age": 60, "clinic": "rao"},
                 "lakshmi": {"name": "Lakshmi garu", "language": "Telugu", "phone": "+919800000002"}},
      "clinics": {"rao": {"doctor": "Dr. Rao", "clinic": "Sunrise Clinic, Gachibowli", "phone": "+919800000003"}},
      "address_hint": "Loft"}
tools = lambda plan: {f.__name__: f for f in plan.tools}
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M")

# 1. approvals: double tap, failed never reopens
st = Store(":memory:")
aid = st.add_card(Card("kitchen", "order", "Cart", ["milk"]).to_dict())
c1, c2 = st.claim(aid, "COD"), st.claim(aid, "COD")
assert c1["title"] == "Cart" and c2 is None
st.finish(aid, False, "boom")
assert st.card(aid)["status"] == "failed" and st.claim(aid, "COD") is None and not st.reject(aid)

# 2. jobs + scheduler + dispatch
health = HealthExpert(st, HH)
fid = st.add_job("health", "followup", "amma", {"patient": "amma", "doctor": "Dr. Rao", "after_days": 14}, time.time() + 3600)
assert st.due() == [] and st.run_now(fid) and [j["id"] for j in st.due()] == [fid]
dialed = []
dispatch = J.make_dispatch(st, {"health": health}, lambda to, job_id: dialed.append((to, job_id)) or "CA1")
assert asyncio.run(J.tick(st, dispatch)) == [fid] and st.job(fid)["status"] == "done"
assert any(c["card"]["kind"] == "followup" for c in st.cards())
cid = health.checkin("amma", "test call")
asyncio.run(J.tick(st, dispatch))
assert dialed == [("+919800000001", cid)] and st.job(cid)["result"] == {"call_sid": "CA1"}
bad = st.add_job("nobody", "x", "y", {}, 0)
asyncio.run(J.tick(st, dispatch))
assert st.job(bad)["status"] == "failed"

# 3. caller
tw = C.stream_twiml("abc.ngrok-free.app", "job42")
assert '<Stream url="wss://abc.ngrok-free.app/media-stream">' in tw and '<Parameter name="job_id" value="job42" />' in tw
class Calls:
    def create(self, **kw): self.kw = kw; return types.SimpleNamespace(sid="CA9")
tc = types.SimpleNamespace(calls=Calls())
assert C.make_dial(tc, "+15550001111", "abc.ngrok-free.app", 4)("+919800000001", "job42") == "CA9"
assert tc.calls.kw["time_limit"] == 240 and tc.calls.kw["from_"] == "+15550001111" and "job42" in tc.calls.kw["twiml"]
assert C.job_id_from_start({"event": "start", "start": {"customParameters": {"job_id": "job42"}}}) == "job42"
assert C.job_id_from_start({"event": "media"}) is None

# 4. safety
os.environ.pop("GUARDRAIL_ID", None)
assert S.check("hello").status == "unchecked"
class G:
    def __init__(self, act): self.act = act
    def apply_guardrail(self, **kw):
        self.kw = kw
        return {"action": self.act, "outputs": [{"text": "Held for review: please ask the doctor."}]}
os.environ["GUARDRAIL_ID"] = "gr-1"
g = G("NONE"); v = S.check("Amma said she feels dizzy", client=g)
assert v.status == "passed" and g.kw["source"] == "OUTPUT" and g.kw["content"][0]["text"]["text"].startswith("Amma")
v = S.check("Take two tablets", client=G("GUARDRAIL_INTERVENED"))
assert v.status == "blocked" and v.text.startswith("Held")
os.environ.pop("GUARDRAIL_ID")

# 5. health: booking window enforced in code
st2 = Store(":memory:"); h = HealthExpert(st2, HH)
base = (datetime.now(IST) + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
good = (base + timedelta(days=1)).replace(hour=10, minute=30)
late, outside = good.replace(hour=16), (base + timedelta(days=6)).replace(hour=10)
jid = h.book("amma", "rao", base.isoformat(), (base + timedelta(days=5)).isoformat(), "morning", "BP review")
job = st2.job(jid); plan = h.call_plan(job); t = tools(plan)
assert job["payload"]["to"] == "+919800000003" and "AI assistant" in plan.instructions and "Sunrise Clinic" in plan.instructions
assert t["offer_slots"]([iso(late), iso(outside)]).startswith("None fit")
assert iso(good) in t["offer_slots"]([iso(good), iso(late)])
assert t["book_slot"](iso(late), "", "", "").startswith("Refused")
assert t["book_slot"]("tomorrow 10", "", "", "").startswith("Refused")
assert t["book_slot"](iso(good), "Dr. Rao", "Rs 500", "old reports").startswith("Booked")
assert t["book_slot"](iso(outside), "", "", "").startswith("Already")
card = asyncio.run(h.after_call(job, plan.saved))
assert card.kind == "booking" and card.lines[0].startswith(good.strftime("%a %d %b, %I:%M %p"))
assert "DTSTART:" + good.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") in card.payload["ics"]
assert "LOCATION:Sunrise Clinic\\, Gachibowli" in card.payload["ics"]
out = asyncio.run(h.execute(card.to_dict(), "remind"))
j1, j2 = (st2.job(x) for x in out["jobs"])
assert abs(j1["run_at"] - (good - timedelta(days=1)).replace(hour=19, minute=0).timestamp()) < 1
assert abs(j2["run_at"] - (good + timedelta(hours=3)).timestamp()) < 1 and j1["kind"] == "checkin"

# 6. health: hold -> call back for that exact slot
hold = asyncio.run(h.after_call(job, {"held": {"slot": iso(late), "note": "only 4 pm"}, "summary": "x"}))
o3 = asyncio.run(h.execute(hold.to_dict(), "confirm")); t3 = tools(h.call_plan(st2.job(o3["jobs"][0])))
assert t3["book_slot"](iso(good), "", "", "").startswith("Refused") and t3["book_slot"](iso(late), "", "", "").startswith("Booked")

# 7. health: check-in, emergency alert, doctor brief (no advice, her words)
cj = st2.job(h.checkin("amma", "Remind her of the appointment")); cp = h.call_plan(cj); ct = tools(cp)
assert "never give medical advice" in cp.instructions and "108" in cp.instructions
ct["save_checkin"]("okay", ["headache"], "2 days", ["BP 150/95"], "yes", ["Can I walk in the morning?"],
                   "Talanoppi rendu rojula nunchi", "Headache for two days")
ct["alert_family"]("She says she feels faint")
assert any(c["card"]["kind"] == "alert" for c in st2.cards())
brief = asyncio.run(h.after_call(cj, cp.saved)); text = "\n".join(brief.lines)
assert brief.kind == "brief" and "Talanoppi" in text and "BP 150/95" in text and "Can I walk" in text
assert brief.payload["safety"] == "unchecked" and brief.payload["wa"].startswith("https://wa.me/919800000003?text=")

# 8. health: prescription -> confirm -> reminders, advice for the Kitchen, follow-up booking
rx = {"doctor": "Dr. Rao", "date": "2026-11-24", "review_after_days": 14, "unreadable_parts": ["line 3"],
      "advice_as_written": ["Low salt diet"],
      "meds": [{"name_as_written": "Tab. ABC 40", "strength": "40 mg", "dose": "1", "morning": True, "afternoon": False,
                "night": False, "food": "after food", "days": 30, "unclear": False},
               {"name_as_written": "Tab. ???", "strength": None, "dose": None, "morning": False, "afternoon": False,
                "night": False, "food": None, "days": None, "unclear": True}]}
mc = h.meds_card("amma", rx)
assert any("pharmacist" in w for w in mc.warnings) and any("Could not read" in w for w in mc.warnings)
assert st2.facts("amma", "meds") == []
out = asyncio.run(h.execute(mc.to_dict(), "confirm"))
assert [f["value"] for f in st2.facts("amma", "advice:")] == ["Low salt diet"]
assert sorted(st2.job(j)["kind"] for j in out["jobs"]) == ["checkin", "followup"]
fj = next(st2.job(j) for j in out["jobs"] if st2.job(j)["kind"] == "followup")
fc = asyncio.run(h.run_task(fj)); bj = st2.job(asyncio.run(h.execute(fc.to_dict(), "book"))["jobs"][0])
assert bj["kind"] == "book" and bj["payload"]["part"] == "morning" and bj["payload"]["to"] == "+919800000003"

# 9. kitchen: card follows Swiggy's rules; DRY_RUN never checks out; real path checks out once
class T:
    def __init__(self, x): self.type, self.text = "text", x
class R:
    def __init__(self, sc=None, x=""): self.structuredContent, self.content, self.isError = sc, [T(x)], False
class Ops:
    def __init__(self, script): self.script, self.calls = script, []
    async def call_tool(self, name, args):
        self.calls.append((name, args)); v = self.script[name]
        return v.pop(0) if isinstance(v, list) else v
CART = {"items": [{"itemName": "Heritage Toned Milk", "itemVariant": "500 ml", "quantity": 2, "discountedFinalPrice": 56, "storeId": "s1"},
                  {"itemName": "Tata Salt Lite", "itemVariant": "1 kg", "quantity": 1, "discountedFinalPrice": 45, "storeId": "s2"}],
        "billBreakdown": {"toPay": {"value": "\u20b9131"}}, "selectedAddressDetails": {"address": "RMZ The Loft, Raidurg"}}
PAY = {"cod": {"available": True}, "platforms": {"mobile": {"methods": [{"id": "gpay", "displayName": "Google Pay"}]}}}
seen = {}
async def fake_build(agent_im, text, address_id): seen["text"] = text; return "All found."
async def fake_pick(ops, hint=None): seen["hint"] = hint; return {"id": "addr1", "addressLine": "RMZ The Loft"}
sw.build_cart, sw.pick_address = fake_build, fake_pick
st3 = Store(":memory:"); st3.remember("amma", "advice:0", "Low salt diet", "prescription")
ops = Ops({"get_cart": R(CART), "get_payment_options": R(PAY),
           "checkout": R({"orderId": "O1", "status": "CONFIRMED"}, "Instamart order placed successfully")})
k = KitchenExpert(st3, HH, None, ops)
card = asyncio.run(k.handle("2 milk, 1 salt"))
assert "Low salt diet" in seen["text"] and seen["hint"] == "Loft"
assert card.question == "Do you want to proceed with placing this order to this address?"
assert [c["id"] for c in card.choices] == ["COD", "UPI:gpay"] and card.address == "RMZ The Loft, Raidurg"
assert card.lines[0] == "Heritage Toned Milk 500 ml x2 - Rs 56" and any("2 stores" in w for w in card.warnings)
assert card.payload["approved_total"] == 131
os.environ["DRY_RUN"] = "1"
assert asyncio.run(k.execute(card.to_dict(), "COD"))["dry_run"] and not [n for n, _ in ops.calls if n == "checkout"]
os.environ["DRY_RUN"] = "0"
res = asyncio.run(k.execute(card.to_dict(), "COD"))
assert res["message"] == "Instamart order placed successfully" and "080-67466729" in res["cancel"]
assert [a for n, a in ops.calls if n == "checkout"] == [{"addressId": "addr1", "paymentMethod": "Cash"}]
lp = k.call_plan(st3.job(k.weekly_call("lakshmi")))
assert "Lakshmi garu" in lp.greeting and "AI assistant" in lp.instructions
tools(lp)["save_list"](["2 litres paalu", "1 kg kandi pappu"], "")
assert asyncio.run(k.after_call({"id": "j1"}, lp.saved)).kind == "order" and "paalu" in seen["text"]

# 10. registry
register(k)
try:
    register(k); raise AssertionError("duplicate allowed")
except ValueError:
    pass
print("ALL V2 CHECKS PASSED")
```


## Appendix C: Configuration

**`household.example.yaml`**

```yaml
# Who Pathya works for. Phone numbers in E.164. Only people who agreed to AI calls.
user:
  name: Shiva
  phone: "+91XXXXXXXXXX"
people:
  amma:
    name: Amma
    language: Telugu
    age: 60                  # placeholder
    phone: "+91XXXXXXXXXX"
    clinic: rao
  lakshmi:
    name: Lakshmi garu
    role: cook
    language: Telugu
    phone: "+91XXXXXXXXXX"
clinics:
  rao:                       # for the demo, a friend plays the receptionist
    doctor: "Dr. Rao (placeholder)"
    clinic: "Sunrise Clinic, Gachibowli (placeholder)"
    phone: "+91XXXXXXXXXX"
address_hint: Loft
```

**`.env.example`**

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=                      # empty = Agents SDK default
REALTIME_MODEL=gpt-realtime        # use the realtime model your dashboard lists
VISION_MODEL=gpt-5-mini            # any vision-capable model your dashboard lists

# Swiggy Instamart (sign in once: npx -y mcp-remote https://mcp.swiggy.com/im)
INSTAMART_MCP_URL=https://mcp.swiggy.com/im
ADDRESS_HINT=Loft
CART_CAP=1000
DRY_RUN=1                          # 1 = never place real orders. Set 0 only for a real order.

# Twilio (upgraded account, US number, India enabled in Voice geo permissions)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM=+1...
PUBLIC_HOST=xxxx.ngrok-free.app    # no https://
CALL_MAX_MINUTES=6

# AWS Bedrock Guardrails (Health Expert safety)
AWS_REGION=us-east-1
GUARDRAIL_ID=
GUARDRAIL_VERSION=1
```

**`infra/guardrail_topics.json`**

```json
{
  "topicsConfig": [
    {
      "name": "Diagnosis",
      "type": "DENY",
      "definition": "Saying what illness or condition a person has or may have, based on symptoms, readings or reports.",
      "examples": [
        "She probably has high blood pressure",
        "These symptoms mean diabetes",
        "This sounds like a heart problem"
      ]
    },
    {
      "name": "Medication advice",
      "type": "DENY",
      "definition": "Recommending, starting, stopping, changing or dosing any medicine, supplement or home remedy.",
      "examples": [
        "She can take one more tablet tonight",
        "Stop the BP tablet if she feels dizzy",
        "Give her a painkiller"
      ]
    },
    {
      "name": "Result interpretation",
      "type": "DENY",
      "definition": "Saying whether a reading, lab value or scan result is normal, high, low, good or bad.",
      "examples": [
        "150 by 95 is too high",
        "Her sugar of 180 is fine",
        "The report shows nothing serious"
      ]
    }
  ]
}
```

**`infra/guardrail_content.json`**

```json
{
  "filtersConfig": [
    {
      "type": "MISCONDUCT",
      "inputStrength": "HIGH",
      "outputStrength": "HIGH"
    },
    {
      "type": "PROMPT_ATTACK",
      "inputStrength": "HIGH",
      "outputStrength": "NONE"
    }
  ]
}
```

**`infra/guardrail_pii.json`**

```json
{
  "piiEntitiesConfig": [
    {
      "type": "CREDIT_DEBIT_CARD_NUMBER",
      "action": "BLOCK"
    }
  ],
  "regexesConfig": [
    {
      "name": "Aadhaar",
      "description": "12-digit Aadhaar-like number",
      "pattern": "\\b\\d{4}\\s?\\d{4}\\s?\\d{4}\\b",
      "action": "ANONYMIZE"
    }
  ]
}
```

**`.gitignore` additions** (also in `gitignore_additions.txt`)

```
.env
household.yaml
quickpick.db
*.db
recordings/
__pycache__/
.venv/
```

