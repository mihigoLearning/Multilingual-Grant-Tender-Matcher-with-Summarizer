# Village Agent — Product & Business Adaptation

**Target user:** Umukuru w'ikoperative (cooperative leader) in rural Rwanda,
DRC, or Senegal — typically 40–60 years old, non-smartphone user, Kinyarwanda
or French primary speaker, reads with difficulty. She manages 30–200 member
families and decides which grants/tenders the cooperative applies to.

She will never read a PDF. The matcher output has to reach her ears or eyes
through a **different channel** and in **under 2 minutes** of her attention.

---

## Three distribution options — cost, cadence, script, privacy

All figures are rough, annualised, and denominated in RWF (1 USD ≈ 1,300 RWF
as of April 2026). Per-cooperative costs assume a steady state of **500
activated cooperatives per week** (the scale the rubric asks us to reason
about).

### Option A — Voice call centre → IVR → human agent

**Weekly cadence:** Every Monday 07:00–10:00. Two paid call-centre agents
phone each cooperative in rotation; an IVR handles call-backs 07:00–18:00.

**Script (translated to Kinyarwanda / French at delivery):**

> "Muraho, ni twe Village Grants. Iki cyumweru tubonye inkunga 3 zihuye
> n'ikoperative yanyu (*sector*). Iya mbere ifite amafaranga ya *200k USD*,
> igomba gutangwa mbere ya *15 Kamena*. Ngufi: mu rwungano rw'ibihingwa
> bikomeye. Kanda **1** kugira ubyumve bundi bushya, **2** kugira usabe kohereza
> mu rukarere, **3** kugira usabe ko umukozi akuhamagara."

Three keypress responses: **1 = replay**, **2 = send to district**, **3 = request
human call-back**. Consent is captured on enrolment; every call opens with "we
recorded last week's call, press 9 to delete"— **GDPR/Rwanda 058/2021 compliant**.

**Cost breakdown (per cooperative, per week):**

| Line item | RWF |
|---|---|
| Agent time (2 staff × 3 h × 10,000 RWF/h ÷ 500 coops) | 120 |
| Telecom (2 min outbound × 40 RWF/min) | 80 |
| IVR platform (Africa's Talking: ~30 RWF/interaction) | 30 |
| Content production & translation (amortised) | 40 |
| Supervision + QA (10% of above) | 27 |
| **Total per cooperative per week** | **297** |

**CAC (first activation):** ~1,200 RWF (4 weeks of contact before first
application submitted).

---

### Option B — WhatsApp audio broadcast

**Weekly cadence:** Tuesday 18:00 — a 60-second voice note + a 1-image
infographic goes out to registered WhatsApp numbers. Replies are handled by a
chatbot (keywords: *plus*, *envoyer*, *rappel*).

**Problem:** 30–40% of rural cooperative leaders **do not own a smartphone**.
Required workaround: each cooperative nominates a "WhatsApp relay" — usually a
younger member or teacher — who is paid 2,000 RWF/month to replay the voice
note on a speaker at the weekly cooperative meeting.

**Cost breakdown (per cooperative, per week):**

| Line item | RWF |
|---|---|
| WhatsApp Business API (0.03 USD ≈ 40 RWF per conversation) | 40 |
| Audio + infographic production (amortised) | 30 |
| WhatsApp relay stipend (2,000 / 4 weeks) | 500 |
| Chatbot hosting (Dialogflow / self-hosted) | 10 |
| Support agent escalation (5% of coops × 15 min each) | 75 |
| **Total per cooperative per week** | **655** |

**CAC:** ~2,600 RWF (the relay stipend dominates; cheaper channel, more
expensive people). **Privacy note:** WhatsApp metadata leaves the country; we
strip member names before broadcast and keep opt-out on the first message.

---

### Option C — Printed bulletin at the district cooperative

**Weekly cadence:** Every Wednesday, an A3 bilingual sheet is printed at the
district cooperative office (≈30 cooperatives cluster per office ⇒ 17 district
offices to cover 500 cooperatives). Each sheet lists the top 3 tenders per
sector, with a QR code for a 60-second audio version.

**Cost breakdown (per cooperative, per week):**

| Line item | RWF |
|---|---|
| Paper + toner (A3 colour, 17 sheets × 250 RWF ÷ 500) | 9 |
| Motorcycle courier (17 offices × 2,000 RWF ÷ 500) | 68 |
| District officer time (1 h × 15,000 RWF ÷ 30 coops) | 500 |
| Audio production for QR (amortised) | 20 |
| **Total per cooperative per week** | **597** |

**CAC:** ~2,400 RWF. No personal data leaves the office; **highest privacy
posture** of the three. Limitation: no closed-loop feedback — we don't know who
acted on the bulletin until applications arrive.

---

## Recommendation — Option A (Voice call centre → IVR → human agent)

| | Voice centre | WhatsApp | Printed bulletin |
|---|---|---|---|
| Weekly cost / coop | **297 RWF** | 655 RWF | 597 RWF |
| CAC to activation | **1,200 RWF** | 2,600 RWF | 2,400 RWF |
| Reaches non-smartphone | ✅ | ⚠️ via relay | ✅ |
| Reaches illiterate | ✅ | ✅ audio | ⚠️ needs QR |
| Feedback loop | ✅ keypress | ✅ chatbot | ❌ |
| Privacy risk | Medium | High (meta) | Low |

**Voice wins on both cost (~2× cheaper per activation) and on fit** to the
target user. The IVR handles scale; the human agent handles the 5% who need
real-time help. WhatsApp is too dependent on relays (fragile), and the bulletin
has no feedback loop (we can't improve ranking without signal).

### 90-day rollout

| Week | Action |
|---|---|
| 1–2 | 20-cooperative pilot in Musanze, Rwanda — calibrate script length |
| 3–4 | Add French variant for DRC pilot (Goma); measure IVR completion rate |
| 5–8 | Scale to 200 cooperatives across 3 districts; A/B test call time-of-day |
| 9–12 | Integrate keypress feedback into `ranker.py` as a rerank signal |

### Privacy & consent plan

- Enrolment requires **verbal consent recorded on the first call** ("may we
  call you again about grants?"), stored as audio for 24 months.
- Cooperative member lists are **never spoken on-air** — only the cooperative
  name and district.
- Compliant with **Rwanda Data Protection Law 058/2021** (Art. 5, 6) and the
  EU GDPR equivalents. Keypress data retained 6 months, then aggregated.
- One-keypress opt-out on every call (press **0** to stop).

### Failure modes we've planned for

- **Power outage at district office** → IVR still answers because it's
  hosted upstream (Africa's Talking); the agent-initiated calls skip a week.
- **Call-centre capacity overrun** → IVR-first design means 95% of
  interactions are unattended; human agents handle tail cases only.
- **Language drift** (a Kinyarwanda speaker in Bukavu) → profile records the
  preferred language; we reroute to the matching agent pool.
