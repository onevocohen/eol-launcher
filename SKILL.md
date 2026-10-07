---
name: eol-deck-builder
description: Creates a Idira End-of-Life (EOL) presentation deck in Google Slides by copying the Idira EOL template and auto-populating it from a PRD or any product context. Use when a PM wants to build an EOL deck, end-of-life session presentation, EOS deck, or product retirement slides. Trigger phrases: "EOL deck", "end of life deck", "EOS session deck", "product retirement slides", "create EOL presentation".
disable-model-invocation: true
---

# EOL Deck Builder

Copies the shared Idira EOL template and auto-populates all 9 content slides
from a PRD, feature spec, or any product context the PM provides.

## Script

```
/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-deck-builder/scripts/create_deck.py
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

### Step 0 — Pull from Asana automatically (always do this first)

As soon as you know the product or EOL name, search Asana automatically — no URL needed:

```bash
python3 "/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-deck-builder/scripts/fetch_asana.py" "<product name>"
```

**Exit code behaviour:**

| Exit code | Meaning | What to do |
|---|---|---|
| `0` | Single match found — JSON output ready | Use the output, proceed to Step 1 |
| `2` | No match found | Skip Asana, go straight to Step 1 |
| `3` | Multiple matches — `_asana_multiple_matches` list in output | Ask PM: *"I found a few EOL submissions for that name — which one?"* then re-run with the chosen GID |

**Read these `_asana_*` metadata fields to ask smarter follow-ups:**

- `_asana_alternative_flag`: `"full"` → ask for the product name; `"partial"` → ask what's missing; `"none"` → flag this gap to the PM
- `_asana_has_skus`: `"Yes"` → ask for the specific SKU codes; `"No"` → set `impacted_skus: []`
- `_asana_full_description`: mine this for rationale, customer impact, and existing-customer guidance
- `_asana_due_on`: use as a key date anchor if present
- `_asana_submitter` / `contact`: pre-fill the contact field

If the PM provides an Asana URL or task GID directly, pass that instead of the product name — the script handles both.

### Step 1 — Collect remaining context

After Step 0, check which of the 16 fields are still empty. Ask the PM for any additional
docs (PRD, spec, etc.) that might fill gaps. Then extract all 16 fields:

| Field | What to look for |
|---|---|
| `product_name` | Exact product/feature name being EOLed |
| `date` | Deck presentation date (e.g. "Q2 2026") |
| `announcement` | One paragraph: what is being EOLed and when |
| `key_dates` | List of milestone dates (announce, stop-sell, EOS, EOL) |
| `rationale` | Bullet list: business/strategic reasons for EOL |
| `open_opportunities` | Active deals / pipeline affected (count, ARR) |
| `escalation` | Who to contact for affected deal escalations |
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

If context is incomplete, ask only the questions that are still unanswered (see **PM Interview Questions** below). Group them in one message, not one at a time.

### Step 2 — Build the input JSON

Assemble the extracted fields into a JSON object and write it to a temp file:

```bash
cat > /tmp/eol_input.json << 'ENDJSON'
{
  "product_name": "...",
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

### Step 3 — Run the script

```bash
python3 "/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-deck-builder/scripts/create_deck.py" /tmp/eol_input.json
```

The script copies the template, populates all slides, and prints the Google Slides URL.

**If auto-copy fails** (rare — when ADC doesn't have Drive access to the template):
1. Ask the PM to open this URL to copy the template manually:
   `https://docs.google.com/presentation/d/1jSiJII27Hr3guxSgDt_D-dFHNCRL3GaCm2J53gu0ZU0/copy`
2. Ask for the new presentation ID (string between `/d/` and `/edit` in the URL)
3. Re-run with the ID as a second argument:
```bash
python3 "/Users/onevocohen/Library/Application Support/Cursor/AgentStores/cursor_agent_stores/7e93e542-cc75-4818-830f-089df36e7650/files/skills/eol-deck-builder/scripts/create_deck.py" /tmp/eol_input.json <PRESENTATION_ID>
```

### Step 4 — Share the result

Give the PM the link and a brief note:

> ✅ Your EOL deck is ready: [link]
> 
> The template's **Slide 2** (EOL Roadmap) is a graphic — review it and mark
> where the product currently sits on the journey. All other slides are
> populated. Recommend sharing with the GTM team before the EOL session.

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
Send all remaining unanswered questions in **one batch** — not one at a time.

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

4. **What are the key milestone dates in the EOL timeline?**
   *(e.g., Announcement date, Last day to sell / stop-sell date, End of Support date, End of Life / sunset date)*

---

### 💼 Business Rationale (Slide 4)

5. **Why is this product being EOLed?**
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
