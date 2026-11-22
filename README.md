# Pathya

*Pathya (పథ్య / पथ्य): the diet that suits a particular person.*

**Family nutrition, from a phone call to the plate.**

Every family member has a different need: Nanna is told to cut sugar, Amma takes BP tablets, you want to bulk.
Nobody follows a diet chart, and you can't check on everyone every day. Pathya phones them in their own language
(Telugu first), asks what they ate and whether they took their medicines, plans one menu with a plate for each person,
and turns what is missing into a Swiggy Instamart cart you approve with one tap.

## What it does

- **Family:** a profile per member (age, height, weight, activity, food type, allergies, what the doctor said, and a
  goal: bulk, cut, less sugar, more protein or less salt). Each member gets personal daily targets: a standard formula,
  labelled as a general reference; a nutritionist's numbers override it.
- **Calls:** check-in and medicine reminder calls (OpenAI Realtime) to anyone with a number in `household.yaml`,
  on Twilio, Exotel or right in the browser.
  - Calls open in Telugu and follow whatever language the person speaks. When the words come back in another script
    (Hindi, Telugu, Tamil...), the call is told to switch.
  - A call never hangs up while something is pending.
  - Pathya's own calls always go out on Twilio. If the phone network refuses one (Jio refuses Twilio's US number),
    it rings in the app instead and a card says why.
  - Family members can also call in. The cook gets the grocery-list call.
  - Calls your phone forwards to the Exotel number get the Doorstep Expert: it guides the delivery partner in from
    your delivery instructions, alerts you, and takes a message from anyone else.
- **Voice:** More > Pathya's voice, for every call.
  - Pick one of the 10 OpenAI voices and hear a sample.
  - Choose an Indian or neutral accent and a pace.
  - Set how long Pathya waits when someone pauses, and whether people can talk over it.
  - Add your own instructions on how to speak. They sit below Pathya's rules and can't override them; the hard rules
    are also enforced in code.
  - Members 60+ get the slow, patient setting.
  - "See the full prompt" shows exactly what Pathya is told on a check-in call.
- **Meals:** pick who is eating and add guests. You get one menu for the cook, and each person's plate food by food
  with quantities ("rice 0.5 cup, dal 1.5 katori").
  - +/- changes their totals exactly, and "Fit to target" scales a plate to that person's energy target.
  - The cook hears the quantities on the menu call.
- **Camera:** one photo, read by a vision model. The photo is kept (gitignored `photos/`) and shown next to what was
  read, so you can look at it again.
  - A plate is logged with estimated calories and protein, as breakfast, lunch, snack or dinner by when the photo was
    taken (its EXIF time, else the file time; within the last 7 days). Change it with one tap.
  - A medicine strip, a prescription or a body composition report (InBody) is copied exactly as printed and saved only
    after you confirm. A report's BMR or lean mass then sets that person's energy target.
- **Age and elders:** checkups people that age are usually offered, with their source (India's NP-NCD screening, WHO
  ICOPE for older people, USPSTF), shown as "ask the doctor". It never diagnoses.
  - From 60: protein 1.0 g/kg, slower and gentler calls, and a factual note when logged meals stay low for two days.
- **Own notes:** a cart item that clashes with someone's own notes (less sugar, a doctor's note, an allergy) is flagged
  on the card. On calls, Pathya reminds them of that note in its own words and offers a swap.
- **Watch:** an Apple Watch sends steps and active energy through an iPhone Shortcut (`POST /api/activity/<member>`).
  Today's energy target then follows what the watch measured.
- **Food log:** meals said on a call or typed in the app, with estimated calories, protein, fibre and added sugar per
  person.
- **Medicines:**
  - kept exactly as written, entered by hand or from a prescription photo you confirm. Every line is saved; lines the
    reader was unsure of, or without a time, are flagged and left out of reminder calls until you tap "Matches the
    paper";
  - daily reminder calls for the length of the course;
  - a missed dose becomes a card for you.
- **Orders:** Swiggy Instamart MCP (Zepto MCP for missing items, or the whole list when Instamart is offline).
  The cart, total, address and payment are shown; nothing is placed without your tap. `DRY_RUN=1` is the default; a
  dry run is listed as "DRY RUN: not placed" and never stocks At home, the buy-again memory or the nutrition estimate.
- **At home:** delivered orders stock a pantry with shelf-life estimates. When something is running low, a reorder is
  one tap away. Groceries asks for the cook's number if it isn't saved yet, so menu calls can reach them.
- **Nutrition brief** (Meals > Household nutrition > Share): the shopping estimate, each member's targets and the meal
  plan, facts only. Send it on WhatsApp (to your saved nutritionist, or pick a contact), or tap "Share with a doctor
  on PharmEasy": the brief is copied and PharmEasy's online consultation opens, ready to paste. The doctor brief for a
  booking works the same way.
- **Health score:** 0-100 per person over the last 7 days, built from habits only:
  - food 40: meals logged and close to their own targets;
  - medicines 30: doses taken as written;
  - movement 15: steps from a watch;
  - check-in calls 15: calls answered.

  Tap it for the breakdown and what would raise it. Readings and weight never count; it is not a medical test.
- **Goal bars:** every target shows the percentage reached. Bulk or cut with a goal weight shows how far along it is.
- **Parents:** the evening check-in call is on by default for parents and members 60+ with a phone.
- **Book a doctor:**
  - "Doctors": your doctors as profiles (specialty, clinic, who in the family sees them). Tap Book, pick who, the week
    and the time of day, and Pathya phones the clinic. "Add a doctor" saves one into `household.yaml`. A new
    household starts with no doctors; add your own here.
  - "Find a specialist near you": pick a specialty (or name a hospital) and the area.
  - "Plan by call": Pathya calls you, asks who it's for, the reason in their words, the place and the days, and shows
    a card.
  - "Online now": PharmEasy and Apollo 24|7 online consultations open on their own sites (their doctors and fees stay
    there; nothing is copied).

  A clinic that isn't saved yet is looked up on the web (number and source shown). It is added to `household.yaml`
  and phoned only after your tap.
- **Order medicines** (Family > person > Medicines). No pharmacy MCP is usable yet: Tata 1mg's `mcp.1mg.com` does not
  resolve, and Apollo 24|7 and PharmEasy have none. So:
  - share your location (or type the area) and Pathya finds up to 3 pharmacies nearby, each with its number and
    source;
  - after your tap the pharmacy goes into `household.yaml` (`pharmacies:`), and Pathya phones it to ask what they
    have, the total and home delivery. It reads the names exactly as written, never accepts a substitute and never
    orders;
  - the result card opens WhatsApp with the list and shares the prescription photo, so you place the order;
  - or order them all yourself: one tap opens Tata 1mg, Apollo 24|7 or PharmEasy's "order with prescription" page
    to upload the prescription photo (no prices fetched).
- **Sign in:** with your phone number and a code by SMS or a voice call (Twilio Verify). Only the user's and family
  members' numbers in `household.yaml` can sign in. The `?key=` link still works.

Pathya never diagnoses and never suggests, starts, stops or changes a medicine or dose (see [AGENTS.md](AGENTS.md)).

UI: dark, minimal and phone-first. Motion uses only transform and opacity and stops for "reduce motion"; there is no
glow. It follows the parts of the premium-frontend-ui Copilot skill that suit a phone app: type scale, staggered
entrances, press feedback, frosted bars, grain and skeleton loading.

## Run

```bash
cp .env.example .env               # add OPENAI_API_KEY
cp household.example.yaml household.yaml
npx -y mcp-remote https://mcp.swiggy.com/im    # sign in to Swiggy once
./run.sh                           # http://localhost:8000, calls ring in the browser
./run.sh phone                     # public tunnel: real phone calls + the app on your phone (prints the link and key)
```

Tests: `python tests/test_swiggy_flow.py && python tests/test_v2.py && pytest -q`

**Phone app.**
- iPhone and Android: open the link in the browser and choose "Add to Home Screen" or "Install app".
- Android also has an APK. Build it with `mobile/build-apk.ps1` (JDK 21, Android SDK 36), then download it from
  More > Android app (`/pathya.apk`).
- The APK is a small launcher: it asks once for your Pathya link (the one with `?key=`) and opens it.
- When the tunnel restarts, paste the new link (More > Change server link).

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
- `app/core/`: store, scheduler, call bridges (Twilio and Exotel), languages, call rules, voice settings
- `web/`: the phone-first app (Home, Family, Meals, Orders, More)
- `mobile/`: the Android app (Capacitor launcher for your Pathya link)
