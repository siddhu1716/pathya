# Builders 2026: Ideas README

**What to build so that OpenAI, AWS and Equal AI all lean in**
Researched 21 Nov 2026 for Shiva Nampalli · Builders hackathon, Equal AI HQ, Hyderabad

> The brief is revealed on site. This README covers:
> 1. What each sponsor wants right now.
> 2. Where those wants overlap.
> 3. A ranked idea catalogue, each idea with its demo moment.
> 4. A brief-to-idea map and a 10-minute scorecard.
>
> Use it together with **01_Builders_Setup_Guide.md**, which has the architecture, setup and timeline.

---

## TL;DR

- **The sweet spot is a voice-first agent that takes real, consented actions for Indian users.** Money and risk are held by rules written in code, and it runs on OpenAI models and AWS India regions.
- **Prepare three ideas in your head:**
  - **Kaam Ho Gaya** makes the calls for you.
  - **Scam Kavach** guards your parents' phones.
  - **QuickPick Kitchen** plans, shops and pays within limits.
- **Strong alternates:** COD Confirm, Yojana Saathi, AgentPay Guard and Voice Agent QA Lab.
- **Every demo needs four things:**
  - one real action
  - one guardrail refusal
  - a visible audit trail
  - one Indian-language moment

---

## Contents

1. What each sponsor wants now
2. The overlap: where to aim
3. Market signals (YC and India data)
4. Idea catalogue (Tier A, B, C)
5. Brief-to-idea map
6. How each idea earns sponsor credit
7. The 10-minute scorecard
8. Ideas to avoid or reframe
9. Pitch lines
10. Sources

---

## 1. What each sponsor wants now

### OpenAI: agents that work for you, by voice, everywhere

| Signal | What it means for your build |
|---|---|
| **DevDay 2026 (29 Sep):**<br>• Always-on agents ("dots")<br>• GPT-6.1 Sol, strong at agentic coding and computer use, at about a fifth of Astra's token price<br>• Agents API in public beta: hosted execution, memory, tools, multi-agent and computer use<br>• Decisions API in limited preview, for fast classification and routing<br>• Plugins built on MCP<br>• Sign in with ChatGPT | Build an agent that *does* things, using tools, memory and computer use. A chatbot is not enough. |
| **GPT-Live:** full-duplex voice that keeps talking while a backend agent works (called delegation). Also:<br>• SIP telephony, with an endpoint for SIP hosts in India<br>• A Hindi voice (`nira`)<br>• Prompt-to-voice | Voice plus delegation is OpenAI's newest primitive. Using it well is a strong signal. |
| **ChatGPT Wallet (13 Nov):** agents pay with tokenised cards and a security check on every purchase. OpenAI expects spending limits, categories and time windows later. US Pro users only for now. | Approval plus limits is OpenAI's own design pattern, so mirror it. |
| **India:**<br>• 100M+ weekly ChatGPT users (Feb 2026)<br>• OpenAI for India: Tata data centres, plus partners such as PhonePe, CRED, Pine Labs and MakeMyTrip<br>• In-country API processing for GPT-6 Luna (12 Nov) | Stories about India-scale use, Indian languages and India data residency land well. |
| **DevDay session on cost:** measure cost per completed task | Know your rupee cost per task. |

### AWS: OpenAI on AWS, agents in production, data kept in India

| Signal | What it means for your build |
|---|---|
| **OpenAI models on Bedrock:** the partnership expanded on 28 Apr 2026, and the models became generally available in June–July 2026. The GPT-6 and GPT-5.6 families are listed. | You can call OpenAI models *through* AWS. |
| **In-country processing in India** for GPT-5.6 Terra and Luna, from the Mumbai and Hyderabad regions (Aug 2026) | Say "your data never leaves India" and show the region. |
| **AgentCore covers the whole agent stack:**<br>• Harness (agents defined by config, built on Strands)<br>• Runtime, memory, a gateway for MCP, and identity<br>• Policy (Cedar rules you can write in plain language)<br>• Evaluations and observability<br>• AgentCore payments: agents pay for APIs and content within limits enforced by the infrastructure | Deploy the agent on AgentCore, and enforce guardrails at the infrastructure layer. |
| **Bedrock Managed Agents, powered by OpenAI:** public preview, US regions only | Mention it as roadmap. Don't depend on it. |
| **Nova 2 Sonic:** speech-to-speech with Hindi, Indian English, code-switching and telephony audio | An AWS-native voice fallback |

### Equal AI: India's AI assistant for everyday needs, starting with calls

| Signal | What it means for your build |
|---|---|
| **Product:** it answers unknown calls, finds out why the caller is calling, and shows the reason with quick replies (for example, delivery instructions). It records, transcribes and summarises calls in 10+ Indian languages, including code-mixed speech. | Your idea should live on the phone call. |
| **Traction:** 1M+ monthly and 300K+ daily users after its October 2025 launch. $30M Series B in June 2026, co-led by Prosus Ventures and Tomales Bay Capital. | They need features that scale to millions of users. |
| **Public roadmap:**<br>• Screening known numbers<br>• Proactive actions, such as texting your address to a delivery person with consent<br>• Outbound calls to book appointments<br>• An iOS app and a paid tier<br>• Expansion into communications, financial services, shopping, lifestyle and concierge | Build the next feature they would ship. |
| **Roots:** Equal started as consent-driven identity and data-sharing infrastructure for 350+ banks, insurers and telecom companies. | Consent, verification and trust are home ground for them. |
| **Strategy:** built on calls and its own app, to avoid depending on another platform (the lesson from WhatsApp's bans on third-party bots) | Don't make WhatsApp your only channel. |
| **The founder's framing:** people want AI that "listens, understands, and acts" | Your demo must *act*. |

---

## 2. The overlap: where to aim

```
        OpenAI                        AWS                         Equal AI
  voice + agents that act     agents in production,        phone calls, Indian
  (GPT-Live, Agents API)      data in India, guardrails    languages, trust, consent
             \                          |                          /
              v                         v                         v
        +----------------------------------------------------------------+
        |  A voice-first agent that takes a real, consented action for   |
        |  an Indian user, with limits enforced in code, an audit trail, |
        |  and OpenAI models running on AWS India regions                |
        +----------------------------------------------------------------+
```

**Design principle to quote in your pitch.** At Global Fintech Fest 2026, NPCI's chairman said: *"AI may recommend, but authentication and final settlement must follow deterministic auditable rules."*

**A formula that turns any brief into a sponsor-friendly product:**
- Phone or voice in Indian languages (Equal)
- An agent that delegates and acts (GPT-Live with the Agents SDK or Agents API)
- Rules, approval and an audit trail, enforced in code and on AWS (AgentCore Policy, DynamoDB)
- Data kept in India (Bedrock `in.` profiles, or an OpenAI India project)
- **One measurable outcome:** rupees saved, calls avoided, or fraud stopped

---

## 3. Market signals

### YC's latest Requests for Startups, translated to India

| YC request (batch, partner) | The core idea | India version | Idea in this README |
|---|---|---|---|
| Plaid for Government Benefits (Winter 2027, Gustaf Alströmer) | Pull verified records with consent: verify once, apply everywhere | Welfare schemes, scholarships and pensions, using documents shared with consent | Yojana Saathi |
| The $15-an-Hour Expert (Winter 2027, Brad Flora) | AI turns ordinary workers into experts in benefits, taxes, insurance claims and medical billing | Hospital insurance desks, Common Service Centre (CSC) operators, bank correspondents | Claim Saathi |
| AI for City Hall (Winter 2027, Gustaf Alströmer) | Permits, 311 (non-emergency city services), public records, licensing, inspections | Municipal grievances and permits | Civic call desk (a variant of Yojana Saathi) |
| Proving You're Human (Fall 2026, Max Kolysh) | Rebuild trust on calls and messages as deepfakes spread | Digital-arrest and voice-clone scams | Scam Kavach |
| AI for the Aging Population (Fall 2026, Max Kolysh) | Voice interfaces for seniors, and coordination for caregivers | Parents living far from their children | Amma Care Calls |
| AI-Powered Consumer Products for 1 Billion People (Fall 2026, Raphael Schaad) | Agents are now good and cheap enough for mass consumer products | Voice-first India | Kaam Ho Gaya, QuickPick Kitchen |
| Multiplayer AI (Fall 2026, Aaron Epstein) | Shared, live agent sessions | A household agent the whole family shares | A feature in QuickPick Kitchen |
| AI-Native Compliance Infrastructure (Fall 2026, Daivik Goel) | Monitoring, audit trails and reporting done by AI | Audit trails and limits for agents that spend money | AgentPay Guard |
| The Primer (Fall 2026, Andrew Miklas) | An adaptive tutor for young children | A mother-tongue tutor over a phone call | Padhai Call |
| Own Your Intelligence, and AI for the Air-Gapped Economy (Winter 2027) | Control where models run and where data lives | Data residency in India | A pitch angle for any idea |

### India data points worth quoting

- **Voice AI is real in India.**
  - YC-backed Bolna handles 1.3M+ calls a day across 22+ Indian languages.
  - It raised a $6.3M seed round led by General Catalyst in January 2026.
  - Its CEO says voice AI today mostly means collections calls and lead qualification. Consumer and trust use cases are still open.
- **Agentic payments are arriving on UPI.**
  - UPI carried 24.51 billion transactions worth ₹29.82 lakh crore in August 2026.
  - NPCI's Unified Agent Protocol builds on UPI Circle (delegated spending) and Reserve Pay (funds blocked for later debits). Users set limits, and the protocol adds audit trails and identity checks.
  - Groceries are expected to be among the first use cases.
  - Pilots were shown at Global Fintech Fest in September 2026, but the wider rollout needs RBI approval. Pine Labs' P3P protocol is already live.
- **Fraud is the biggest trust problem.**
  - Reported cyber-fraud losses for 2025 range from ₹19,812.96 crore (I4C, January 2026) to ₹22,495 crore (MHA data given to Parliament, provisional).
  - Seniors filed 4.3% of complaints but bore 18% of losses.
  - Digital-arrest scams were about 8% of losses.
  - Telangana lost ₹1,372 crore, putting it in the top five states. It also registered the most cybercrime cases of any state in 2024.
- **Cash on delivery (COD) burns money.**
  - COD orders are returned to the seller about 26% of the time, against under 2% for prepaid orders (Shipway, FY25).
  - COD is still roughly 60–65% of e-commerce orders (2024 estimate).
  - Each return costs about ₹180–240 in logistics.
  - Festive-season COD return rates have been reported as high as about 58%.
- **Calls overwhelm people.** Equal's founder says buying car insurance can bring about 20 calls a week.

---

## 4. Idea catalogue

### Tier A: prepare these, because they fit all three sponsors

#### A1. Kaam Ho Gaya: "You speak once. It makes the calls. You approve one."

**Who it's for:** busy families, and anyone who hates phone queues.

**What it does:**
- You say what you need in Telugu, Hindi or English, for example "AC service tomorrow, under ₹800, near Kondapur."
- The agent finds three to five providers and calls them in parallel. It asks about price, slot and warranty, then compares the answers.
- It books only after you approve, adds the slot to your calendar, and calls you back the day before.

**Why now:**
- Outbound calls to book appointments are on Equal's public roadmap.
- GPT-Live can keep talking while the backend works, and it can dial out over SIP.

**Demo moment:**
- Two phones on the desk ring at once, and live transcripts stream side by side.
- A card pops up: "₹650 at 11 AM (4.6★) · ₹700 at 2 PM · ₹900 tomorrow. Approve ₹650?"
- You tap, and a confirmation call follows.

**38-hour scope:**
- **MVP:**
  - voice request and planner
  - one real outbound call plus two simulated ones
  - quotes extracted as structured data
  - approval card and booking confirmation
- **Stretch:** Telugu, parallel real calls, a reminder call through the scheduler, and memory of providers and ratings.

**Stack:**
- **OpenAI:** GPT-Live for voice and outbound SIP calls, plus the Agents SDK for a planner and one call worker per provider.
- **AWS:** AgentCore Runtime or Lambda, DynamoDB for quotes and the audit log, and EventBridge Scheduler for reminders, all in Mumbai or Hyderabad.

**Sponsor fit:** OpenAI ★★★★★ · AWS ★★★★ · Equal ★★★★★

**Risks and fixes:**
- **Telephony setup:** start with a callee simulated in the browser.
- **Consent:** call only friends or your second phone, and disclose the AI when the call is answered.
- **Latency:** keep prompts short, and use Luna for extraction.

#### A2. Scam Kavach: "The first voice a scammer meets on Amma's phone is an AI that knows every script."

**Who it's for:** seniors and their children.

**What it does:**
- Screens unknown calls and spots scam patterns live:
  - fake police and "digital arrest"
  - KYC and OTP requests
  - parcels "held at customs"
  - investment tips
- Warns the parent in their own language and alerts a family member.
- Prepares a report for the 1930 helpline or cybercrime.gov.in within the golden hour.
- Uses a family code word to catch voice clones.

**Why now:**
- It matches YC's "Proving You're Human" request.
- Seniors suffer outsized losses, and Telangana has a heavy caseload.
- Call screening is Equal's core product.

**Demo moment:**
- A friend calls, pretending to be a CBI officer.
- Within seconds a risk meter turns red, and the AI says in Telugu: "Real police never arrest anyone on a video call. I'm ending this call."
- The son's phone buzzes with a summary, and a draft 1930 report appears.
- Then a genuine bank call passes through, showing that it doesn't block everything.

**38-hour scope:**
- **MVP:**
  - inbound call, over SIP or in the browser
  - streaming transcript
  - scam classifier using rules plus Luna or the Decisions API
  - spoken warning, family alert and report pack
- **Stretch:** the code-word challenge, a shared block list, and a "pause before UPI transfer" nudge.

**Stack:**
- **OpenAI:** GPT-Live as the screening voice, plus a classifier built on the Decisions API or Luna.
- **AWS:** Lambda or AgentCore, DynamoDB for incidents, SNS for alerts and S3 for evidence, with data kept in India.

**Sponsor fit:** OpenAI ★★★★ · AWS ★★★★ · Equal ★★★★★

**Risks and fixes:**
- **False positives:** warn first, and end the call only at high confidence.
- **Recording consent:** announce the recording when the call starts.
- **Over-promising:** never claim it can recover lost money.

#### A3. QuickPick Kitchen (your QuickPick, rebuilt): "Sunday night, your week's food is planned, bought, and the cook is briefed, all within the limit you set."

**Who it's for:** working families with a cook, or with a busy kitchen.

**What it does:**
- Plans the week by voice, taking in the number of people, the budget, diets and fasts.
- Builds the cart through the official Instamart and Zepto MCP servers.
- Pays within a pre-set limit, and asks for approval above it.
- Calls the cook every morning in Telugu with the day's menu.

**Why now:**
- Groceries are expected to be one of NPCI's first agentic-payment use cases.
- ChatGPT Wallet shows the pattern: approval first, limits later.
- Swiggy and Zepto have official MCP servers, and shopping and concierge are on Equal's roadmap.

**Demo moment:**
- You say: "4 people, ₹3,000, Amma is diabetic, Thursday fast."
- A plan and a cart appear, and an item over the limit triggers an approval.
- The order is placed (sandbox or real).
- The second phone rings, and the cook hears tomorrow's menu in Telugu.

**38-hour scope:**
- **MVP:**
  - voice plan and cart through MCP
  - rules for budget and diet
  - approval step
  - Razorpay test payment for your service fee
  - scheduled call to the cook
- **Stretch:** compare Instamart and Zepto prices, family approvals (the "multiplayer" idea), and a fridge photo that updates the pantry.

**Sponsor fit:** OpenAI ★★★★ · AWS ★★★ · Equal ★★★★

**Risks and fixes:**
- **Not novel enough:** Swiggy lists Dietary Planner and Auto-Restock among its own starter ideas, so lead with the cook call and the family limits.
- **Live or staging?** Confirm which kind of order you are placing.
- **Money flow:** never route grocery money through your own account.

#### A4. COD Confirm: "Every COD order gets a 60-second call in the buyer's language, and a reason to pay now."

**Who it's for:** direct-to-consumer brands and online sellers.

**What it does:**
- Calls COD buyers right after they order.
- Confirms their intent and address (landmark and pincode).
- Offers a small prepaid incentive through a UPI payment link.
- Flags risky orders before dispatch, and calls again if a delivery fails.

**Why now:**
- COD orders come back about 26% of the time, against under 2% for prepaid.
- Each return costs about ₹180–240.
- Razorpay supports sending payment links during voice calls.

**Demo moment:**
- You place a COD order on a demo store, and your phone rings. You answer in Hindi.
- The agent fixes the landmark and sends a UPI link, and you pay in test mode.
- The dashboard flips the order from COD to PREPAID, and the "return risk" tile drops.

**38-hour scope:**
- **MVP:**
  - order webhook
  - outbound call and address fix
  - Razorpay test link and payment webhook
  - dashboard
- **Stretch:** a risk score, repeat calls after failed deliveries, and analytics for the merchant.

**Sponsor fit:** OpenAI ★★★★ · AWS ★★★★ · Equal ★★★ (pitch it as the merchant side of Equal's delivery calls)

**Risks and fixes:** the space is crowded, since logistics platforms already automate COD confirmation. Stand out with natural voice in Indian languages, and by converting orders to prepaid.

#### A5. Yojana Saathi: "Verify once, apply everywhere, on a phone call."

**Who it's for:** families who qualify for government schemes but never apply.

**What it does:**
- A phone agent in Telugu or Hindi asks a few questions and finds the schemes the family probably qualifies for.
- It gathers documents with consent.
- It fills in the application on a mock portal using computer use.
- It calls back with the status.

**Why now:**
- It matches YC's "Plaid for Government Benefits" and "AI for City Hall" requests.
- Equal's roots are in consent-based identity.
- OpenAI's Agents API now supports computer use.

**Demo moment:**
- A caller asks about a scholarship, and the agent asks five questions.
- It gives a shortlist with reasons, then shows a consent screen.
- On screen, the agent fills in a mock portal form while still talking.
- It ends with an SMS summary and a scheduled callback.

**38-hour scope:**
- **MVP:**
  - five to ten schemes encoded as rules, with sources
  - an eligibility engine
  - voice Q&A
  - computer use on a portal that you build
- **Stretch:** extracting details from document photos, and status-check callbacks.

**Sponsor fit:** OpenAI ★★★★★ · AWS ★★★★ · Equal ★★★★

**Risks and fixes:**
- **Wrong eligibility:** use a small, verified set of schemes, and show which rule was applied.
- **Real systems:** never touch real government systems in the demo.

### Tier B: strong alternates

| Idea | One-liner | Demo moment | Best when the brief is about |
|---|---|---|---|
| **B1. Amma Care Calls** | Daily check-in calls to elderly parents: medicines, mood and symptoms. It alerts the children and books doctor slots. | A scheduled call rings, and the parent says (in Telugu) that the BP tablets have run out. The daughter gets an alert and a pharmacy reorder to approve. | Health, the elderly, family, proactive agents |
| **B2. Hold-For-Me** | Calls banks, telecom companies and airlines for you. It navigates phone menus, waits on hold, files the complaint and saves the reference number. | On a mock phone menu you built, the agent presses 2, then 4, waits, argues politely and returns "Ticket #…". | Customer service, concierge |
| **B3. Kirana Receptionist** | Answers a shop's missed calls in the local language, takes orders, sends a UPI link and updates the credit ledger (khata). | A customer calls and orders five items, then gets a payment link. The owner's dashboard updates. | Small businesses, Bharat, commerce |
| **B4. AgentPay Guard** | Limits, allow-lists, velocity checks, approvals and a tamper-evident audit trail for any agent that spends money | Two agents try to buy things. The guard approves one and blocks the other, with reasons. | Payments, infrastructure, safety |
| **B5. Voice Agent QA Lab** | Simulated Indian callers (accents, code-mixing, noise, anger) stress-test a voice agent and score it | 20 synthetic calls run and a leaderboard ranks the failures. You fix one, re-run, and the score goes up. | Developer tools, reliability, evaluations |
| **B6. Claim Saathi** | A copilot for hospital insurance desks and CSC operators. It reads documents, checks policy rules, drafts claims and calls for status. | Upload a discharge summary, get a drafted claim pack, then watch a status call to a mock third-party administrator (TPA). | Work and enterprise; YC's "$15-an-Hour Expert" |

### Tier C: wildcards

| Idea | What it is | When to use it |
|---|---|---|
| **Padhai Call** | A phone tutor in the child's mother tongue (YC's "The Primer") | Education briefs |
| **Kisan Voice** | Crop-photo diagnosis, market (mandi) prices and scheme eligibility, by phone call | Rural or agriculture briefs. It is common at hackathons, so differentiate hard or skip it. |
| **ChatGPT plugin version** | Package any idea above as a plugin (an MCP server plus skills), so it can reach ChatGPT's 100M+ weekly users in India | When the brief says "build on the ChatGPT platform" |

---

## 5. Brief-to-idea map

| If the brief is about… | Lead with | Backup |
|---|---|---|
| Voice agents, calls, making phones more useful | Kaam Ho Gaya | Hold-For-Me |
| Trust, safety, fraud, spam | Scam Kavach | AgentPay Guard |
| Commerce, payments, shopping, concierge | QuickPick Kitchen | COD Confirm |
| Small businesses, Bharat | Kirana Receptionist | COD Confirm |
| Public good, government, financial inclusion | Yojana Saathi | Claim Saathi |
| Health, the elderly, family | Amma Care Calls | Scam Kavach |
| Developer tools, infrastructure, agent reliability | Voice Agent QA Lab | AgentPay Guard |
| Education | Padhai Call | Yojana Saathi (scholarships) |
| Anything, as long as it uses OpenAI and AWS | Kaam Ho Gaya | Scam Kavach |
| Building on the ChatGPT platform or plugins | QuickPick Kitchen as a plugin | Kirana Receptionist as a plugin |

**Adapting when nothing fits:** keep the reusable core (voice loop, delegation backend, rules engine, approval, audit trail, scheduler). Swap only the action connector and the domain rules.

---

## 6. How each idea earns sponsor credit

| Layer | OpenAI | AWS | Equal angle |
|---|---|---|---|
| Voice | GPT-Live over WebRTC or SIP, the Hindi voice, prompt-to-voice | Nova 2 Sonic as a fallback | Phone-native and code-mixed |
| Reasoning and actions | Agents SDK or Agents API: tools, MCP, computer use, the Decisions API | AgentCore runtime or harness, the Gateway for MCP, OpenAI models on Bedrock in India | Quick replies and proactive actions |
| Safety | Guardrails, human approval in the loop | AgentCore Policy and Identity; audit in DynamoDB and CloudWatch | Consent is in their DNA |
| Data | An OpenAI project with India in-country processing | Bedrock `in.openai.*` profiles in Mumbai or Hyderabad | User data stays in India |
| Operations | Traces and cost per task | Observability, Evaluations, EventBridge, scale to zero | Works for millions of users |

---

## 7. The 10-minute scorecard

Score each idea from 1 to 5 on every row. Multiply by the weight and add up the totals.

| Criterion | Weight | Idea 1 | Idea 2 |
|---|---|---|---|
| Fits the brief | ×3 | | |
| The "wow" can be shown live | ×3 | | |
| Buildable solo in the time | ×3 | | |
| Uses OpenAI and AWS deeply | ×2 | | |
| Equal could ship it | ×2 | | |
| Real-world impact (rupees, time or safety) | ×2 | | |
| Different from what the other 99 will build | ×1 | | |

**Tie-break:** pick the one you can demo live without needing any luck.

---

## 8. Ideas to avoid or reframe

| Idea | Why to avoid it or reframe it |
|---|---|
| Chat-with-PDF and RAG bots, generic travel planners, generic meal planners | Everyone builds these |
| Resume screeners and candidate rankers | Crowded, and ethically fraught |
| Price comparison built on scraping | Breaks terms of service. Use official MCP servers instead. |
| Railway Tatkal or booking bots | Against platform rules |
| Medical diagnosis claims | Position it as reminders and escalation instead |
| Moving real money without approval | Use test mode, limits and an approval step |
| A WhatsApp bot as your only channel | Equal's lesson about depending on another platform |

---

## 9. Pitch lines

| Idea | Pitch line |
|---|---|
| Kaam Ho Gaya | "You speak once. It makes five calls. You approve one." |
| Scam Kavach | "The first voice a scammer meets on Amma's phone is an AI that knows every script." |
| QuickPick Kitchen | "Sunday 8 PM: the week's food is planned, bought, and the cook is briefed, all within the limit you set." |
| COD Confirm | "Every COD order gets a 60-second call in the buyer's language, and a reason to pay now." |
| Yojana Saathi | "Verify once, apply everywhere, on a phone call." |
| AgentPay Guard | "Let agents spend. Never let them overspend." |
| Voice Agent QA Lab | "A thousand angry Hyderabad callers before your agent meets its first real one." |

---

## 10. Sources

**Sponsors**

*OpenAI*
- DevDay 2026 recap: https://openai.com/index/devday-2026-recap/
- DevDay 2026 announcements thread: https://community.openai.com/t/devday-2026-announcements-and-developer-resources/1402006
- GPT-Live, getting started: https://developers.openai.com/api/docs/guides/live
- Telephony and SIP: https://developers.openai.com/api/docs/guides/voice-sip
- Prompting GPT-Live for languages and accents: https://developers.openai.com/blog/prompting-multilingual-voice-agents
- Introducing ChatGPT Wallet: https://openai.com/index/introducing-chatgpt-wallet/
- OpenAI for India: https://openai.com/index/openai-for-india/
- In-country API processing in India: https://www.thehindubusinessline.com/info-tech/openaiannounceslocalaiprocessinginindiawithapi-inferenceresidency/article71692832.ece

*AWS*
- OpenAI models on Amazon Bedrock: https://www.aboutamazon.com/news/aws/bedrock-openai-models?lp=h1m
- OpenAI models on Bedrock, in-country processing in India: https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-bedrock-openai-india-v1/
- AgentCore new features: https://aws.amazon.com/about-aws/whats-new/2026/04/agentcore-new-features-to-build-agents-faster/
- AgentCore features by region: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html
- AgentCore payments: https://aws.amazon.com/about-aws/whats-new/2026/08/bedrock-agentcore-payments-ga/
- Policy in AgentCore: https://aws.amazon.com/about-aws/whats-new/2026/03/policy-amazon-bedrock-agentcore-generally-available/
- Nova 2 Sonic: https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-conversational-speech.html

*Equal AI*
- TechCrunch on Equal's $30M round: https://techcrunch.com/2026/06/11/equal-ai-raises-30m-to-screen-calls-so-indians-dont-have-to/
- Economic Times on Equal's round: https://economictimes.indiatimes.com/tech/funding/keshav-reddys-equal-ai-raises-30-million-in-round-led-by-prosus-tomales-bay-capital/articleshow/131674910.cms
- Times of India on Equal's round: https://timesofindia.indiatimes.com/city/hyderabad/gvk-group-scions-equal-ai-raises-30m-in-series-b-round-led-by-prosus-ventures-tomales-bay-capital/articleshow/131688039.cms

**YC**
- Requests for Startups: https://www.ycombinator.com/rfs
- YC-funded AI startups in India: https://www.ycombinator.com/companies/industry/ai/india

**India market data**

*Voice AI*
- Bolna (Symphony 2026): https://www.bolna.ai/newsroom/bolna-brings-indias-voice-ai-ecosystem-together-at-symphony-2026-in-bengaluru
- TechCrunch on Bolna: https://techcrunch.com/2026/01/20/bolna-nabs-6-3-million-from-general-catalyst-for-its-india-focused-voice-orchestration-platform/

*UPI and agentic payments*
- Reuters on agentic payments on UPI: https://www.reuters.com/world/india/india-preparing-rollout-agentic-payments-upi-sources-say-2026-09-01/
- NPCI's Unified Agent Protocol at Global Fintech Fest (source of the NPCI chairman quote): https://www.revrag.ai/resources/blog/npci-unified-agent-protocol-banking-apps

*Cyber fraud*
- Economic cost of cyber crimes in India: https://tjaindia.com/2026/10/economic-cost-of-cyber-crimes-in-india/
- I4C 2025 figures: https://the420.in/india-cyber-fraud-losses-i4c-data-statewise-investment-scams/

*COD and returns*
- Shipway ShipNotes on COD returns: https://mediabrief.com/shipnotes-reveals-26-rto-rate-on-cod-orders-across-india/
- India D2C return benchmarks: https://www.hootmonk.com/blog/india-rto-benchmarks-2025/
- RTO rate benchmarks for India: https://teraads.co/blog/rto-rate-benchmarks-india

**Commerce building blocks**
- Swiggy Builders Club: https://mcp.swiggy.com/builders/docs/start/developer/
- Razorpay MCP server: https://razorpay.com/docs/mcp-server
- Razorpay agentic payments for voice: https://razorpay.com/blog/razorpay-agentic-payments-voice-ai/
- Zepto on shopping through AI: https://blog.zepto.com/how-zepto-enables-seamless-shopping-through-ai-fcc7d2e43c7b
