---
name: EOL Kickoff Toolkit
description: Kicks off the full EOL process for a product or feature — searches Asana for an existing request, asks the PM questions one at a time, creates an Asana task (if new), generates a fully populated Google Slides EOL deck, and schedules a 30-minute Google Meet kickoff meeting with the relevant stakeholders. Use when a PM wants to deprecate a product, start an EOL process, or create an EOL deck. Trigger phrases: "EOL", "end of life", "deprecate", "EOL deck", "EOS", "product retirement", "start an EOL", "kick off EOL".
disable-model-invocation: true
---

# EOL Deck Builder

Copies the shared Idira EOL template and auto-populates all 9 content slides
from a PRD, feature spec, or any product context the PM provides.

## Script

```
/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-launcher/scripts/create_deck.py
```

## Asana EOL Request Form

Project: **EOL - Request form** | GID: `1214130454046893`
URL: https://app.asana.com/1/11915891072957/project/1214130454046893

The form captures: product name, full EOL description, alternative status, SKU flag,
submitter name + email, and task status. Everything else must come from the PM.

| Asana field | Deck field | Coverage |
|---|---|---|
| `Name` CF / "End of life / Deprecation name" (notes) | `product_name` | ✅ |
| `EOL Description` CF | `announcement` (first paragraph) | ✅ |
| `Alternative` enum (Yes / Partial / No) | Hint for `alternatives` follow-up | ⚠️ |
| `Status` CF | `status_notes` | ✅ |
| "What is your email address?" (notes) | `contact` | ✅ |
| `SKU` enum (Yes / No) | Flag — need actual codes if Yes | ⚠️ |
| Task `due_on` | Hint for `key_dates` | ⚠️ |

Fields Asana **never** fills: `date`, `key_dates`, `rationale`, `open_opportunities`,
`escalation`, `for_new_customers`, `for_existing_customers`, `pricing_impact`,
`communication`, `who_notified`, and specific SKU codes.

---

## Workflow

The PM only needs to say: *"I want to work on an EOL"* or *"I have a product I want to deprecate."*
From there, everything is automated. The full flow:

```
PM mentions EOL → search Asana → found? use it : ask questions → save to Asana (if new) → create deck → share both links
```

---

### Step 0 — Get the product name, then search Asana

Ask the PM: **"What is the product or feature name?"**

Then immediately search Asana:

```bash
python3 "/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-launcher/scripts/fetch_asana.py" "<product name>"
```

| Exit code | Meaning | What to do |
|---|---|---|
| `0` | Existing task found — partial JSON ready | Pre-fill fields from it, go to Step 1 for gaps |
| `2` | No task found | Ask PM all missing questions, then go to Step 1 |
| `3` | Multiple matches — `_asana_multiple_matches` in output | Ask PM: *"I found a few submissions for that name — which one?"* Re-run with chosen GID |

**`_asana_*` hints for smarter follow-ups:**
- `_asana_alternative_flag`: `"full"` → ask for product name; `"partial"` → ask what's missing; `"none"` → flag gap
- `_asana_has_skus`: `"Yes"` → ask for specific codes; `"No"` → set `impacted_skus: []`
- `_asana_full_description`: mine for rationale, customer impact, existing-customer guidance
- `_asana_due_on`: anchor for key dates
- `_asana_submitter` / `contact`: pre-fill contact field

### Step 1 — Collect remaining context

Ask the PM one question at a time in a natural, conversational flow. Wait for each answer before asking the next. This keeps the interaction engaging and lets the PM answer thoughtfully rather than filling out a form.
Also accept any PRD, spec, or doc the PM wants to share to reduce questions further.

| Field | What to look for |
|---|---|
| `product_name` | Exact product/feature name being EOLed |
| `date` | Auto-filled from current month+year (e.g. "October 2026") — never ask the PM for this |
| `announcement` | One paragraph: what is being EOLed and when |
| `key_dates` | Ask only: "When do you want the EOL date?" — use the answer as the single key date |
| `rationale` | Bullet list: business/strategic reasons for EOL |
| `open_opportunities` | Skip — do not ask the PM for this |
| `escalation` | Auto-fill: always the submitting PM (use `pm_name` + `contact` fields) — never ask |
| `for_new_customers` | What sales should do for new inquiries |
| `for_existing_customers` | What to offer existing customers (migration, bridge) |
| `alternatives` | Replacement product(s) and key value props |
| `pricing_impact` | Pricing changes, migration offer, discounts |
| `communication` | Channels and timeline for customer communications |
| `who_notified` | Which customer segments receive notice |
| `contact` | Email / Slack for EOL questions |
| `impacted_skus` | List of affected SKU codes / names |
| `status_notes` | (Optional) Current status for the roadmap slide |

**Do not leave any field blank or use "TBD" — ask the PM for missing info before running the script.**

If context is incomplete, ask the remaining questions one at a time, conversationally. Do not dump all questions at once.

### Step 2 — Build the input JSON

Assemble the extracted fields into a JSON object and write it to a temp file:

```bash
cat > /tmp/eol_input.json << 'ENDJSON'
{
  "product_name": "...",
  "pm_name": "...",
  "date": "...",
  "announcement": "...",
  "key_dates": ["...", "..."],
  "rationale": ["...", "...", "..."],
  "open_opportunities": "...",
  "escalation": "...",
  "for_new_customers": "...",
  "for_existing_customers": "...",
  "alternatives": "...",
  "pricing_impact": "...",
  "communication": "...",
  "who_notified": "...",
  "contact": "...",
  "impacted_skus": ["...", "..."],
  "status_notes": "..."
}
ENDJSON
```

### Step 3 — Save to Asana (only if no existing task was found in Step 0)

If Step 0 returned exit code `2` (no existing task), create the Asana record now:

```bash
python3 "/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-launcher/scripts/submit_asana.py" /tmp/eol_input.json
```

The script prints the new Asana task URL. Share it with the PM alongside the deck link.

If Step 0 found an existing task, **skip this step** — do not create a duplicate.

### Step 4 — Create the deck

```bash
python3 "/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-launcher/scripts/create_deck.py" /tmp/eol_input.json
```

The script copies the Idira EOL template, populates all slides, and prints the Google Slides URL.

**If auto-copy fails** (rare — when ADC doesn't have Drive access to the template):
1. Ask the PM to open this URL to copy the template manually:
   `https://docs.google.com/presentation/d/1jSiJII27Hr3guxSgDt_D-dFHNCRL3GaCm2J53gu0ZU0/copy`
2. Ask for the new presentation ID (string between `/d/` and `/edit` in the URL)
3. Re-run with the ID as a second argument:
```bash
python3 "/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-launcher/scripts/create_deck.py" /tmp/eol_input.json <PRESENTATION_ID>
```

### Step 5 — Create the calendar invite

```bash
python3 "/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-launcher/scripts/create_calendar.py" /tmp/eol_input.json "<deck_url>" "<asana_url>"
```

The script creates a **30-minute Google Meet event** titled `"EOL - <product name>"`, invites the PM + Yael Gershon (`ygershongob@paloaltonetworks.com`) + Amir Aviad (`aaviad@paloaltonetworks.com`), and embeds the deck + Asana links in the description.

- If the `calendar.readonly` scope is available: the script auto-finds the first free 30-min slot (Israel working hours, Sun–Thu 9am–5pm).
- If not (403 on FreeBusy): defaults to the next working-day at 09:00 Israel time. The PM can reschedule from the invite if needed.

The script prints JSON with `event_link` and `meet_link`.

### Step 6 — Share all outputs

Give the PM all three links in one message:

> ✅ Done! Here's your full EOL package:
>
> 📋 **Asana task**: [link] *(new — created from your answers)*
>    OR: 📋 **Asana task**: [link] *(existing submission used)*
>
> 📊 **EOL deck**: [link]
>
> 📅 **EOL review meeting**: [calendar event link] · 🎥 [Google Meet link]
> *(30 min · Yael & Amir invited · deck + Asana links in the invite)*
>
> Slide 2 (EOL Roadmap) is a template graphic — mark where the product currently sits on the journey. All other slides are populated.

---

## Deck structure (11 slides)

| # | Slide title | What the script populates |
|---|---|---|
| 1 | Cover | Date subtitle |
| 2 | EOL Roadmap | Status & Updates note (optional) |
| 3 | Announcement & Timeline | Announcement paragraph + key dates |
| 4 | Business Rationale | Bullet list of reasons |
| 5 | Customer Impact | Open opps + escalation path |
| 6 | Sales & Renewals Guidance | New customer / existing customer guidance |
| 7 | Alternatives & Pricing | Alternative products + pricing impact |
| 8 | Communication Plan | Channels, who gets notified, contact |
| 9 | Technical & SKU Details | Impacted SKUs list |
| 10 | Q&A | Static (no changes) |
| 11 | Blank | Static (no changes) |

---

## Requirements

- Python 3.6+
- Google ADC at `~/.config/gcloud/application_default_credentials.json` with Drive + Slides scopes
- The PM (or agent) must have at least Viewer access to the EOL template so the Drive copy API succeeds (template is shared with all Idira staff)

---

## PM Interview Questions

Use these questions to fill any gaps after Step 0 (Asana) and Step 1 (docs/context).
Questions marked **✅ Asana** are usually already answered from the form submission.
Ask questions **one at a time**, in a natural conversation. Wait for each answer before moving to the next.

---

### 🗂️ Basics (Cover slide)

1. ✅ Asana — **What is the exact name of the product or feature being EOLed?**
   *(From `Name` CF or "End of life / Deprecation name" in notes. Confirm if the task name differs.)*

2. **When will this EOL session be presented?**
   *(This becomes the deck date, e.g. "Q2 2026" or "March 2026".)*

---

### 📢 Announcement & Timeline (Slide 3)

3. ✅ Asana — **In 2–3 sentences, what exactly is being EOLed?**
   *(From `EOL Description` CF. Edit or expand before using in the deck.)*

4. **When do you want the EOL date?**
   *(e.g. "Q2 2027" or "December 31, 2026")*

---

### 💼 Business Rationale (Slide 4)

5. **Why is this product being EOLed?** *(PM will give a candid answer — always rephrase into polished, politically correct business language before writing to the deck. E.g. "we're not investing in it" → "Idira is strategically reallocating resources toward higher-impact, next-generation capabilities.")*
   *(List the main business or strategic reasons — e.g., low adoption, superseded by a new offering, high maintenance cost, market shift.)*

---

### 👥 Customer Impact (Slide 5)

6. **How many open opportunities or active customers are affected?**
   *(Include deal count and ARR if available, e.g., "12 open deals totaling $1.8M ARR".)*

7. **Who should sales reps escalate affected deals to?**
   *(Name, title, email, or Slack channel — whoever owns EOL deal exceptions.)*

---

### 🤝 Sales & Renewals Guidance (Slide 6)

8. **What should sales tell a new prospect who asks about this product?**
   *(What's the redirect message? Which product should they be pointed to instead?)*

9. **What transition offer or path exists for existing customers?**
   *(e.g., migration incentive, pricing bridge, extended support window, dedicated CSM outreach)*

---

### 🔄 Alternatives & Pricing (Slide 7)

10. ⚠️ Asana hint — **What is the recommended alternative product or solution?**
    *(Asana tells us if there's a full / partial / no alternative. Ask for the product name and 2–3 key reasons it replaces the EOLed product.)*

11. **Will there be any pricing changes, migration discounts, or bridge offers?**
    *(Even a rough answer helps — e.g., "20% discount for migrating within 6 months".)*

---

### 📣 Communication Plan (Slide 8)

12. **How and when will Idira communicate this EOL to customers?**
    *(Channels: email, in-app banner, partner portal, direct CSM call, etc. Include expected timing.)*

13. **Which customer segments will receive the EOL notice?**
    *(e.g., all customers on the SKU, active users only, partners, prospects in pipeline)*

14. ✅ Asana — **Who is the primary point of contact for EOL questions from the field?**
    *(Pre-filled from the submitter's email in the form. Confirm whether this is the right field contact or if a team alias is more appropriate.)*

---

### 🔧 Technical & SKU Details (Slide 9)

15. ⚠️ Asana hint — **What are the specific SKU codes or names being retired?**
    *(Asana tells us if SKUs are impacted (Yes/No). If Yes, ask for the exact codes — e.g., "PAM-ENT-VAULT", "PAM-ENT-CPM". If unsure, check the product catalog or ask RevOps.)*

---

### 📍 EOL Roadmap Status (Slide 2 — optional)

16. ✅ Asana — **What is the current status of the EOL process?**
    *(Pre-filled from `Status` CF if set to something other than "New". Ask the PM to elaborate if a richer status note is needed for the slide.)*

---

## Finding an Asana task by product name

If the PM doesn't have the task URL, search the EOL project by name:

```bash
TOKEN=$(bash ~/.config/secrets/get-secret.sh ASANA_ACCESS_TOKEN)
curl -s "https://app.asana.com/api/1.0/projects/1214130454046893/tasks?opt_fields=name,gid,completed" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import json,sys,re
term=input('Product name to search: ').lower()
for t in json.load(sys.stdin).get('data',[]):
    if term in t['name'].lower():
        print(t['gid'], t['name'], '(completed)' if t.get('completed') else '')
"
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `403 on copy_template` | PM needs at least View access to the template; open the template link and request access |
| `ADC file not found` | Run: `gcloud auth application-default login` with the required scopes |
| `401 Unauthorized` | ADC token expired — re-run `gcloud auth application-default login` |
| Slides show old placeholder text | Some slides have multiple BODY elements; check `status_notes` keyword match in create_deck.py |
| `fetch_asana.py` returns empty | Task GID may be wrong — verify the last number in the Asana URL is the task (not the project or section) |
