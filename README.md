# QuickPick

**Family nutrition, from a phone call to the plate.**

Every family member has a different need: Nanna is told to cut sugar, Amma takes BP tablets, you want to bulk.
Nobody follows a diet chart, and you can't check on everyone every day. QuickPick phones them in their own language
(Telugu first), asks what they ate and whether they took their medicines, plans one menu with a plate for each person,
and turns what is missing into a Swiggy Instamart cart you approve with one tap.

## What it does

- **Family:** a profile per member (age, height, weight, activity, food type, allergies, what the doctor said, and a
  goal: bulk, cut, less sugar, more protein or less salt). Each member gets personal daily targets: a standard formula,
  labelled as a general reference; a nutritionist's numbers override it.
- **Calls:** check-in and medicine reminder calls (OpenAI Realtime) to anyone with a number in `household.yaml`,
  on Twilio, Exotel or right in the browser.
  - Calls open in Telugu and follow whatever language the person speaks.
  - A call never hangs up while something is pending.
  - Family members can also call in. The cook gets the grocery-list call; delivery partners get the Doorstep Expert.
- **Meals:** pick who is eating and add guests. You get one menu for the cook, and each person's plate food by food
  with quantities ("rice 0.5 cup, dal 1.5 katori").
  - +/- changes their totals exactly, and "Fit to target" scales a plate to that person's energy target.
  - The cook hears the quantities on the menu call.
- **Camera:** one photo, read by a vision model.
  - A plate is logged with estimated calories and protein.
  - A medicine strip, a prescription or a body composition report (InBody) is copied exactly as printed and saved only
    after you confirm. A report's BMR or lean mass then sets that person's energy target.
- **Age and elders:** checkups people that age are usually offered, with their source (India's NP-NCD screening, WHO
  ICOPE for older people, USPSTF), shown as "ask the doctor". It never diagnoses.
  - From 60: protein 1.0 g/kg, slower and gentler calls, and a factual note when logged meals stay low for two days.
- **Own notes:** a cart item that clashes with someone's own notes (less sugar, a doctor's note, an allergy) is flagged
  on the card. On calls, QuickPick reminds them of that note in its own words and offers a swap.
- **Watch:** an Apple Watch sends steps and active energy through an iPhone Shortcut (`POST /api/activity/<member>`).
  Today's energy target then follows what the watch measured.
- **Food log:** meals said on a call or typed in the app, with estimated calories, protein, fibre and added sugar per
  person.
- **Medicines:**
  - kept exactly as written, entered by hand or from a prescription photo you confirm;
  - daily reminder calls for the length of the course;
  - a missed dose becomes a card for you.
- **Orders:** Swiggy Instamart MCP (Zepto MCP for missing items, or the whole list when Instamart is offline).
  The cart, total, address and payment are shown; nothing is placed without your tap. `DRY_RUN=1` is the default.
- **At home:** delivered orders stock a pantry with shelf-life estimates. When something is running low, a reorder is
  one tap away.
- **Leaderboard:** weekly points for habits (meals logged, close to your own targets, doses taken, calls answered).
  Readings and weight never score.

QuickPick never diagnoses and never suggests, starts, stops or changes a medicine or dose (see [AGENTS.md](AGENTS.md)).

## Run

```bash
cp .env.example .env               # add OPENAI_API_KEY
cp household.example.yaml household.yaml
npx -y mcp-remote https://mcp.swiggy.com/im    # sign in to Swiggy once
./run.sh                           # http://localhost:8000, calls ring in the browser
./run.sh phone                     # public tunnel: real phone calls + the app on your phone (prints the link and key)
```

Tests: `python tests/test_swiggy_flow.py && python tests/test_v2.py && pytest -q`

## How it fits together

```
phone / browser ──► OpenAI Realtime (gpt-realtime) ──► Expert tools (Python, rules enforced in code)
                                                          │
  Family line · Kitchen · Health · Doorstep Experts ──────┤──► cards (one human tap) ──► Swiggy / Zepto MCP
                                                          │
                    SQLite: profiles, food log, medicines, pantry, orders, calls, timeline ──► React app
```

- `app/experts/family/`: profiles and targets, medicines and reminders, leaderboard, camera (scan.py), checkups,
  plate guard
- `app/experts/home/`: check-in and reminder calls (the Family line)
- `app/experts/kitchen/`: Swiggy and Zepto carts, meal planner, pantry and food log
- `app/experts/health/`: clinic booking calls, doctor brief, prescription reader
- `app/core/`: store, scheduler, call bridges (Twilio and Exotel), languages, call rules
- `web/`: the phone-first app (Home, Family, Meals, Orders, More)

## Built before / built at Builders '26

| Before the hackathon | At the hackathon |
|---|---|
| The idea (github.com/siddhu1716/QuickPick); its React UI shell was reused; its scraper backend was dropped | Swiggy and Zepto MCP ordering with tap-to-commit cards (first real order placed) |
| `docs/BUILD_V2.md` starter: store, scheduler, caller, safety check, Swiggy rules, Health Expert | Realtime calls in the browser, Twilio and Exotel, Telugu-first, language following, wrap-up rule |
| | Family profiles, personal targets, per-person plates, food log, medicine reminder calls, leaderboard |
| | Pantry, order tracking, Doorstep Expert, minimal dark phone-first UI, `run.sh` |
