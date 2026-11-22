# Builders 2026: Hackathon Setup Guide

**OpenAI × Equal AI, powered by AWS · Equal AI HQ, Hyderabad · 21–22 November 2026**
Prepared for Shiva Nampalli · facts checked 21 Nov 2026, just after midnight IST

> This file covers getting ready to build. The companion file **02_Builders_Ideas_README.md** covers what to build.
> Product names and availability change quickly, so re-check the doc links in section 15 if something behaves differently.

---

## Contents

1. The 60-second version
2. Event facts
3. Tonight's checklist (stop at 1:30 AM)
4. Packing list
5. Accounts, keys and access
6. Toolchain and smoke tests
7. Reference architecture (reuse it for any idea)
8. Starter repo layout
9. Hour-by-hour plan
10. Questions to ask at kickoff
11. Demo and pitch kit
12. Making the hiring signal count
13. If things break
14. Rules, consent and safety
15. Official docs and sources

---

## 1. The 60-second version

- **Be at the venue before 8:00 AM on Saturday.** The build runs through Saturday night and finishes around 9 PM on Sunday.
- **Tonight:** get your keys working, run one voice "hello world", push a repo skeleton, pack, then sleep.
- **Saturday:** lock the idea by about 10:30, have an end-to-end slice by lunch, and deploy on AWS by evening.
- **Sunday:** polish, record a backup video, freeze features early, and rehearse the 3-minute pitch until it feels routine.
- **Every demo should show four things:**
  - a real action
  - a guardrail stopping a bad action
  - the audit trail
  - an Indian-language moment

---

## 2. Event facts

| Item | Detail |
|---|---|
| Event | Builders, presented by OpenAI × Equal AI and powered by AWS |
| Field | 100 builders shortlisted from close to 10,000 applications. You are named in Equal AI's shortlist post. |
| Venue | Equal AI HQ, 3rd Floor, RMZ The Loft, Raidurg, Serilingampally, Hyderabad 500032 · https://maps.app.goo.gl/fs2NwoyF96QcZZm78 |
| Report time | 8:00 AM, Saturday 21 November |
| Format | Solo build. Problems are revealed on site, with no take-home work. Non-stop through Saturday night: the invite says 38 hours, LinkedIn says 48, so plan around the invite. Couches are available for naps. |
| Wrap-up | Around 9 PM, Sunday 22 November. Book return travel for after 10 PM. |
| Prizes | ₹35 lakh in cash plus credits. 1st place ₹20 lakh, 2nd ₹10 lakh, 3rd ₹5 lakh. |
| Provided | OpenAI credits, an AWS account, all meals, snacks, coffee and energy drinks |
| Hiring | Equal AI says it is hiring from this room. Its team and industry leaders will be watching how you think, build and ship. |
| Contacts | Hackathon format: Sai Ganesh, 8309479055. Travel or arrival: Bala, 8978699425. |
| Asked of you | Follow Equal AI on LinkedIn and repost the Builders posts |

---

## 3. Tonight's checklist (stop at 1:30 AM)

Work from the top down. If something still fails after 10 minutes, write it down and leave it for the morning.

- [ ] **Use only your personal kit.**
  - Use your personal laptop and personal accounts for GitHub, OpenAI and AWS. Keep work devices, accounts and code out of it.
  - If your employment contract has outside-work or IP clauses, read them. Ask the organizers who owns code written at the event.
- [ ] **Set up the OpenAI platform.**
  - Use your personal organization. Create a new project, an API key and a monthly budget cap.
  - Note your **Org ID**, because credit top-ups usually need it.
  - In-country processing in India needs a separate project with India selected for both storage and processing. You only need this if you pitch data residency.
- [ ] **Try GPT-Live.**
  - Run the WebRTC quickstart: browser mic, then GPT-Live voice, then a backend agent.
  - Real phone calls over SIP need GPT-Live SIP enabled on your project. Ask the OpenAI team at the venue.
- [ ] **Prepare AWS.**
  - Install AWS CLI v2. You will receive an event account tomorrow, so know how to paste temporary credentials or run `aws configure sso`.
  - Default region: `ap-south-1` (Mumbai). Hyderabad (`ap-south-2`) also serves OpenAI models in-country.
- [ ] **Set up GitHub.**
  - Use a personal account, not a work-managed one. Add your SSH key and create an empty repo, `builders-2026`.
- [ ] **Get Razorpay test keys.**
  - In the Dashboard, switch to Test mode and open API keys.
  - Test keys need no website. Live keys need website verification or KYC, so they are not an overnight option.
- [ ] **Optional, for Pathya Kitchen:**
  - Connect the Instamart MCP server from Swiggy Builders Club on localhost (sign in with phone and OTP).
  - Search with the venue address to check that delivery reaches RMZ The Loft.
- [ ] **Run the smoke tests** in section 6.
- [ ] **Finish up:** pack the bag, charge every device, set an alarm, and **sleep**.

---

## 4. Packing list

**From the invite:**
- laptop and charger
- extension cord
- government photo ID
- toothbrush
- a change of clothes

**Add these:**
- Phone charger and a power bank. Calls and hotspot use drain batteries fast.
- Earphones with a mic.
- A **second phone**, or a friend on standby, to play the other side of live call demos.
- A USB-C or HDMI adapter for the projector.
- A mobile data pack, in case you need a backup hotspot.
- A hoodie or shawl (offices get cold at night), a water bottle and any medicines.
- An eye mask and earplugs for naps, plus a small towel and deodorant.
- A notebook and pen for the idea scorecard and the demo beats.
- An offline copy of both guides.

---

## 5. Accounts, keys and access

| Service | Why | Get it to this state tonight | Notes |
|---|---|---|---|
| OpenAI API | Brain and voice | Key works, budget cap set, Org ID noted | Voice: GPT-Live. Backend reasoning: GPT-6.1 Sol. Fast steps: GPT-6 Luna. Use the Agents SDK in Python. |
| GPT-Live over SIP | Real phone calls | Know the steps | Trunk from a SIP provider (Twilio, Telnyx and others) to `sip:$PROJECT_ID@sip-in.api.openai.com;transport=tls` for SIP hosts in India. Signalling uses TLS and audio uses SRTP. SIP must be enabled on the project. |
| AWS event account | Hosting, data, scheduling, Bedrock, AgentCore | CLI installed | Use Mumbai (`ap-south-1`) or Hyderabad (`ap-south-2`) |
| OpenAI models on Bedrock | "OpenAI on AWS, data stays in India" | Check model access tomorrow | India profiles `in.openai.gpt-5.6-terra` and `in.openai.gpt-5.6-luna` keep inference inside India (Mumbai plus Hyderabad). Supports the Responses, Chat Completions and Converse APIs. |
| Bedrock Managed Agents, powered by OpenAI | Optional extra | None | Public preview in US regions only. Do not build your core demo on it. |
| Amazon Bedrock AgentCore | Agent runtime, memory, gateway, identity, policy, evaluations | Skim the quickstart | Mumbai lists the harness, runtime, memory, gateway, identity, built-in tools, observability, policy and evaluations. The Web Search tool and AgentCore payments are **not** in Mumbai. |
| Amazon Nova 2 Sonic | AWS-native voice fallback | None | Hindi and Indian English, code-switching, telephony audio at 8 kHz and tool calling. Connections are limited to 8 minutes. No Telugu. |
| Telephony provider | PSTN calls in the demo | Trial account, only if you need it | Call only consenting numbers, such as your second phone |
| Razorpay | Payments | Test keys | MCP server at https://mcp.razorpay.com/mcp. Creating a payment link during a voice call is a supported pattern. |
| Swiggy Builders Club (MCP) | Grocery and food actions | OAuth on localhost | Production access is reviewed and needs a demo video. Confirm whether localhost orders are live or staging before you order. |
| Zepto MCP | Groceries | Optional | Official. Sign in with phone and OTP. |

---

## 6. Toolchain and smoke tests

**Install whatever you don't already have:**
- Python 3.11+ with `uv` (or pip), Node.js 20+, Git and AWS CLI v2.
- A tunnel for webhooks: `cloudflared` or `ngrok`.
- An editor with a coding agent: VS Code with Codex (CLI or extension). Add Kiro if you want to show AWS's own tooling.
- Docker (optional).

**Bootstrap the project:**

```bash
mkdir builders-2026 && cd builders-2026
uv init backend && cd backend
uv add openai openai-agents fastapi "uvicorn[standard]" python-dotenv httpx boto3 razorpay
cd .. && npm create vite@latest web -- --template react-ts
```

**Smoke test 1: backend agent with a tool (OpenAI Agents SDK)**

```python
# backend/smoke_agent.py
from agents import Agent, Runner
from agents.decorators import tool   # on older SDK versions: from agents import function_tool

@tool
def spend_limit(user: str) -> int:
    """Return the user's approved weekly spend limit in rupees."""
    return 3000

agent = Agent(
    name="Household agent",
    instructions="Reply in the user's language. Never suggest spending above the limit.",
    tools=[spend_limit],
)
print(Runner.run_sync(agent, "What is my weekly limit? Reply in Telugu.").final_output)
```

**Smoke test 2: voice.**
- Run the **GPT-Live WebRTC quickstart** (browser mic, then GPT-Live, then a Responses backend). Say "Namaste" and ask something that needs a tool.
- Alternative: an Agents SDK realtime agent on `gpt-realtime-2.1`, running server-side over WebSocket.
- Note that GPT-Live is billed per second of voice, and backend model usage is billed separately.

**Smoke test 3: an OpenAI model on AWS, processed in India.** Run this tomorrow, once the event account has model access.

```python
import boto3

brt = boto3.client("bedrock-runtime", region_name="ap-south-2")  # Hyderabad
resp = brt.converse(
    modelId="in.openai.gpt-5.6-luna",
    messages=[{"role": "user", "content": [{"text": "Say hello in Telugu."}]}],
)
print(resp["output"]["message"]["content"][0]["text"])
```

**Smoke test 4: a Razorpay test order**

```python
import os, razorpay

rzp = razorpay.Client(auth=(os.environ["RZP_KEY_ID"], os.environ["RZP_KEY_SECRET"]))
print(rzp.order.create({"amount": 100, "currency": "INR", "receipt": "smoke-1"}))  # amount is in paise
```

**Smoke test 5: AWS identity.** Run this tomorrow with the event credentials:

```bash
aws sts get-caller-identity
```

**`.env.example`**

```
OPENAI_API_KEY=
AWS_REGION=ap-south-1
RZP_KEY_ID=
RZP_KEY_SECRET=
PUBLIC_BASE_URL=     # tunnel or AWS URL that receives webhooks
DEMO_MODE=false      # true = replay recorded connector responses if a live service fails
```

---

## 7. Reference architecture (reuse it for any idea)

```
 User or caller (browser mic or phone)
        |  WebRTC (browser)  or  SIP trunk -> OpenAI India SIP endpoint (phone)
        v
 +--------------+   delegation   +--------------------------------------------+
 |  GPT-Live    | -------------> | Backend agent (Agents SDK / Responses API)  |
 |  full-duplex | <------------- | GPT-6.1 Sol for reasoning, Luna for speed   |
 |  voice       |    results     +-----------+--------------------+-----------+
 +--------------+                            | tools / MCP        |
                         +-------------------+                    +------------------+
                         v                                                           v
           Rules engine (plain code)                                    Action connectors
           limits, allow-lists, quiet hours,                            outbound calls, payment links,
           consent, velocity checks                                     grocery MCP, computer use (mock portals)
                         |
                         v
           Approval card (above limit or irreversible) ---> Audit log + live activity feed

 AWS: AgentCore Runtime or Lambda | DynamoDB (profiles, audit) | S3 (transcripts)
      EventBridge Scheduler (proactive calls) | Secrets Manager | CloudWatch | Mumbai or Hyderabad
```

**Five design rules that land with all three sponsors**

1. **Voice is the interface, and the backend does the work.**
   - Keep the GPT-Live prompt short: tone, plus when to delegate.
   - Put business rules, tools and workflows in the backend agent.
2. **Money and irreversible actions go through code, not the model.**
   - Keep limits and allow-lists in `rules.py`, with unit tests.
   - Require approval above the limit.
   - AgentCore Policy (Cedar rules, which you can write in plain language) can also enforce tool rules at the gateway.
3. **Show your work.** Every action writes an audit entry recording:
   - who asked
   - what the agent did
   - which rule allowed it
4. **Speak the way India speaks.**
   - Write prompts in code-mixed Telugu, Hindi and English.
   - Test numbers, names and prices out loud.
   - GPT-Live has a Hindi voice (`nira`), and prompt-to-voice can generate a regional voice.
   - Test Telugu early.
5. **Consent first, data in India.**
   - Announce at "hello" that it is an AI and the call is recorded.
   - Call only numbers that have agreed.
   - Use India-region processing (an OpenAI India project or Bedrock `in.` profiles) as your privacy story.

---

## 8. Starter repo layout

```
builders-2026/
├── README.md        pitch, diagram, how to run, what was pre-built vs built on site
├── .env.example
├── backend/
│   ├── app.py       FastAPI: /session, /approve, /webhooks/{telephony,payments,orders}
│   ├── agent.py     agents, tools, handoffs
│   ├── rules.py     limits, allow-lists, quiet hours (pure functions with tests)
│   ├── tools/       calls.py · payments.py · commerce_mcp.py · computer_use.py
│   ├── store.py     DynamoDB in prod, SQLite in dev
│   └── tests/
├── web/             mic button · live transcript · approval card · activity feed · KPI tiles
├── infra/           deploy notes, EventBridge schedules, IAM policy
└── demo/            seed data · demo script · recorded connector responses · backup video link
```

**Prepare tonight versus build on site**
- Tonight, prepare only generic plumbing: this layout, a mic page, an approval-card component and logging.
- Build all idea-specific logic on site.
- List anything pre-built in the README, and ask at kickoff whether even that is allowed.

**Deploy options on AWS, simplest first**
1. One small EC2 or Lightsail instance in Mumbai or Hyderabad running the backend and web app, with HTTPS.
2. The agent on AgentCore Runtime (it works with the OpenAI Agents SDK), with webhooks on Lambda.
3. Frontend on Amplify Hosting or S3 with CloudFront. DynamoDB for data, EventBridge Scheduler for proactive calls.

---

## 9. Hour-by-hour plan (shift it to the official submission time)

**Saturday 21 November**

| Time | Goal | Done when |
|---|---|---|
| 07:45 | Arrive. Sort power and Wi-Fi, and test your hotspot. | Laptop on mains, repo cloned |
| 08:00–09:30 | Kickoff, brief and rules | You have answers to the section 10 questions |
| 09:30–10:30 | Choose the idea using the scorecard in the Ideas README | One-liner, five demo beats and a "not building" list written down |
| 10:30–13:30 | Thin end-to-end slice | Voice in, agent, one real action, result on screen. Pushed. |
| 13:30–14:00 | Lunch, plus a two-minute chat with an Equal AI engineer about your idea | One insight noted |
| 14:00–19:00 | Core loop: rules engine, approval card, memory, a second action | v0 deployed on AWS by 19:00 |
| 19:00–20:00 | Dinner. Get one outside reaction. | Fix list written |
| 20:00–01:00 | The "wow": a live phone call, an Indian-language flow, a proactive scheduled call | The wow works three times in a row |
| 01:00–05:00 | Sleep in a real block, not just micro-naps | None |

**Sunday 22 November**

| Time | Goal | Done when |
|---|---|---|
| 05:00–09:00 | Bugs, edge cases, seeded demo data, README and diagram | A fresh clone runs |
| 09:00–12:00 | Polish the UI, latency, the guardrail moment and the second language | The full demo runs in under two minutes |
| 12:00–13:00 | Record the backup video | Video uploaded and linked in the README |
| 13:00 | Feature freeze, or earlier if submission is earlier | Only bug fixes after this |
| 13:00–16:00 | Five-slide deck, timed pitch rehearsals, Q&A drill | The pitch fits in 3:00 five times in a row |
| Afternoon to evening | Submit, judging, networking | Submitted before the deadline |

---

## 10. Questions to ask at kickoff

1. What is the exact submission deadline, and what is the format: repo, video, deck, and how long is the live demo?
2. What are the judging criteria and their weights, and who are the judges?
3. Is boilerplate prepared before the event allowed if you disclose it?
4. Is deploying on AWS required or scored?
   - Is Bedrock access already enabled for OpenAI models and Nova 2 Sonic?
   - Does the event account have any service or region limits?
5. Which OpenAI models and features do the credits cover (GPT-Live, GPT-Live SIP, the Agents API, computer use), and what are the rate limits?
6. Are real phone calls and small real payments allowed in demos?
7. Who owns the IP of code written at the event?
8. Is there a backup network if the Wi-Fi fails?

---

## 11. Demo and pitch kit

**The 3-minute pitch**

| Segment | Time | Content |
|---|---|---|
| Hook | 0:00–0:20 | One real person and one painful moment, with a number, a name and a Hyderabad place |
| Live demo | 0:20–1:50 | The five beats, including one guardrail refusal and the audit trail |
| How it works | 1:50–2:20 | One diagram: GPT-Live, backend agent, rules engine, AWS India regions |
| Why it matters | 2:20–2:45 | An impact metric, and why Equal (or any company) could ship it next quarter |
| Close | 2:45–3:00 | What you would build in the next 30 days, and thank you |

**Demo rules**
- A live demo beats a video, but always have the video.
- Before you go on:
  - Seed the data and rehearse the exact sentences you will speak.
  - Use big fonts, turn notifications off and pre-open your tabs.
- Keep a `DEMO_MODE` switch that replays recorded connector responses if a live service fails. If you use it, say so honestly.
- Use test-mode payments. Never use real money on stage.
- Keep the second phone ready, with the volume up and on a charger.

**Q&A drill: have a one-line answer to each**
- **What does one task cost?** Measure tokens plus voice seconds on Saturday night and show the rupee figure.
- **What about latency?** Show your measured time to first word.
- **What stops the agent from going rogue?** The rules engine, approval step, audit trail and limits are enforced in code and infrastructure.
- **Privacy and consent?** AI disclosure, explicit consent, minimal data and India-region processing.
- **Why won't Truecaller, Google or Swiggy just build this?** Your wedge, plus distribution through Equal.
- **How does it scale?** Serverless on AWS, scale to zero, per-user limits.
- **What's the business model?** Per task, a subscription, or B2B per-call pricing.

**The five slides**
1. Problem
2. Demo (screenshot plus a QR code to the repo)
3. How it works
4. Impact and business
5. Next 30 days

---

## 12. Making the hiring signal count

- **Treat the repo as your portfolio.** Equal AI says it is hiring from this room, so give it a clear README, tests for the rules engine, traces and clean commits.
- **Clean your public GitHub before you leave:**
  - Pin your best repos.
  - Keep virtual environments and `__pycache__/` folders out of the repository.
  - Fix the licence mismatch: the README says MIT, but GitHub shows Apache-2.0.
- **Have a short intro ready.** Update your LinkedIn headline, and practise one line such as: "ML engineer in Hyderabad, building voice agents that take real actions safely."
- **Ask Equal's engineers real questions.**
  - How do they handle code-mixed speech?
  - Which call types break?
  - How do they measure call outcomes?
  Listening well is itself a signal.
- **Repost the Builders posts**, as the organizers asked.

---

## 13. If things break

| Problem | Fallback |
|---|---|
| Wi-Fi drops | Phone hotspot, and keep `DEMO_MODE` ready |
| OpenAI rate limit or outage | Move fast steps to Luna, or call OpenAI models through Bedrock, which has a separate quota |
| GPT-Live SIP not enabled | Demo the voice in the browser over WebRTC, and simulate the "other phone" in a second browser tab |
| Telugu speech is weak | Run the live demo in Hindi or English, show Telugu in the recorded clip, and call it roadmap |
| Grocery or payment OAuth fails | Replay recorded responses, clearly labelled as sandbox |
| Laptop trouble | Push every hour, and keep the deck and video in the cloud |
| Exhaustion | A 20-minute nap beats two hours of bad code |

---

## 14. Rules, consent and safety

- **Disclose** anything you built before the event.
- **Use official APIs and MCP servers.** Don't scrape sites whose terms forbid it.
- **On calls:**
  - Say that it is an AI and that the call is recorded.
  - Call only people who have agreed.
  - India regulates unsolicited commercial calls.
- **With personal data:**
  - Collect the minimum and get consent.
  - Keep real third-party data off the screen.
  - India's DPDP Act applies.
- **In demos, keep away from real systems.** No real government portals, bank accounts or live money. Use mocks and test modes.
- **Label AI-generated voices**, and never imitate a real person's voice.

---

## 15. Official docs and sources

**OpenAI**
- GPT-Live, getting started: https://developers.openai.com/api/docs/guides/live
- Telephony and SIP (includes the India SIP endpoint): https://developers.openai.com/api/docs/guides/voice-sip
- Prompting GPT-Live for languages and accents (Hindi voice `nira`): https://developers.openai.com/blog/prompting-multilingual-voice-agents
- Agents SDK quickstart: https://openai.github.io/openai-agents-python/quickstart/
- Realtime agents quickstart: https://openai.github.io/openai-agents-python/realtime/quickstart/
- Packaging a ChatGPT/Codex plugin: https://developers.openai.com/plugins/build/plugins
- Submitting a plugin: https://developers.openai.com/plugins/deploy/submission
- DevDay 2026 recap: https://openai.com/index/devday-2026-recap/

**AWS**
- OpenAI models on Bedrock with in-country inference in India: https://aws.amazon.com/blogs/machine-learning/introducing-openai-models-on-amazon-bedrock-for-in-country-inferencing-in-india/
- OpenAI model list on Bedrock: https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards-openai.html
- Bedrock Managed Agents, powered by OpenAI (preview): https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-managed-agents-openai.html
- AgentCore features by region: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html
- AgentCore harness and CLI: https://aws.amazon.com/blogs/machine-learning/get-to-your-first-working-agent-in-minutes-announcing-new-features-in-amazon-bedrock-agentcore/
- Policy in AgentCore: https://aws.amazon.com/about-aws/whats-new/2026/03/policy-amazon-bedrock-agentcore-generally-available/
- Nova 2 Sonic speech-to-speech: https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-conversational-speech.html

**Commerce and payments**
- Swiggy Builders Club quickstart: https://mcp.swiggy.com/builders/docs/start/developer/
- Swiggy Instamart MCP tools: https://mcp.swiggy.com/builders/docs/reference/instamart/
- Razorpay MCP server: https://razorpay.com/docs/mcp-server
- Razorpay API keys (test vs live): https://razorpay.com/docs/payments/dashboard/account-settings/api-keys
- Razorpay agentic payments for voice: https://razorpay.com/blog/razorpay-agentic-payments-voice-ai/
- Zepto on shopping through AI: https://blog.zepto.com/how-zepto-enables-seamless-shopping-through-ai-fcc7d2e43c7b

**Event**
- Builders announcement and prizes (Equal AI on LinkedIn): https://www.linkedin.com/posts/builders-equalai-openai-share-7524453279146246146-IcsU
- Shortlist post (Equal AI on LinkedIn): https://www.linkedin.com/posts/builders-openai-equalai-share-7528437093090402304-__38
- Event listing: https://eventopia.in/event/builders-pan-india-ai-builders-hackathon-2026-11-21-h3v
