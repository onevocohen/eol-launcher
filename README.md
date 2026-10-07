# EOL Package — Cursor Agent Skill

Handles the full End-of-Life process from a single conversation in Cursor.
Tell the AI you're deprecating a product — it takes care of the paperwork and the deck.

---

## What gets done for you

| | Output | Where |
|---|---|---|
| 📋 | EOL request logged | [Asana — EOL Request form](https://app.asana.com/1/11915891072957/project/1214130454046893) |
| 📊 | Session deck, fully populated | Google Slides (copy of the Idira EOL template) |

Both are created in one flow. You don't open Asana, you don't touch the Slides template.

---

## How to start

**Say any of these in Cursor:**

> *"I want to work on an EOL"*
> *"I have a product I want to deprecate"*
> *"Start an EOL for [product name]"*

### What happens next

```
You mention EOL
     ↓
AI asks: "What's the product name?"
     ↓
AI searches Asana automatically
     ↓
   Found?                    Not found?
     ↓                           ↓
Use existing data          Ask you the questions
Ask only for gaps          (all at once, one message)
     ↓                           ↓
                    Create Asana task
                           ↓
                    Create Google Slides deck
                           ↓
              Share both links with you
```

---

## The deck (11 slides)

| Slide | Content |
|---|---|
| 1 | Cover — product name + date |
| 2 | EOL Roadmap — where things stand on the journey |
| 3 | Announcement & Timeline — what's EOLed + key dates |
| 4 | Business Rationale — why it's happening |
| 5 | Customer Impact — open deals + escalation path |
| 6 | Sales & Renewals Guidance — new vs. existing customer playbook |
| 7 | Alternatives & Pricing — replacement product + pricing |
| 8 | Communication Plan — channels, segments, contact |
| 9 | Technical & SKU Details — impacted SKU codes |
| 10 | Q&A |

---

## What the AI pulls from Asana automatically

If you (or a teammate) already submitted the EOL request form, the AI finds and uses it — no link needed.

| Pulled from Asana | Still asks you for |
|---|---|
| Product name | Deck presentation date |
| EOL description | Key milestone dates |
| Whether an alternative exists | Business rationale |
| Submitter contact email | Open pipeline / ARR affected |
| Task status | Escalation contact |
| Whether SKUs are impacted | Actual SKU codes (if flagged) |
| | New / existing customer guidance |
| | Pricing & migration offer |
| | Communication plan |

---

## Questions you may be asked

Sent in **one batch** — not one at a time.

| Topic | Questions |
|---|---|
| **Basics** | Product name · Deck date |
| **Announcement** | What's being EOLed (scope + date) · Key milestone dates |
| **Rationale** | Why is this happening? |
| **Customer impact** | Open deals / ARR · Escalation contact |
| **Sales guidance** | Message for new prospects · Transition offer for existing customers |
| **Alternatives** | Replacement product + reasons · Pricing / migration offer |
| **Communication** | Channels & timing · Who gets notified · Field contact |
| **SKUs** | Specific SKU codes being retired |
| **Status** *(optional)* | What has already happened in the EOL process |

---

## Requirements

- Cursor with your Google account connected (ADC configured)
- Access to the shared Idira EOL Google Slides template
- Asana access (for reading/creating the EOL request form task)

---

## Files

```
eol-launcher/
├── README.md              ← you are here
├── SKILL.md               ← AI instructions (technical)
└── scripts/
    ├── fetch_asana.py     ← searches Asana by product name, returns form data
    ├── submit_asana.py    ← creates a new Asana task from PM answers
    └── create_deck.py     ← copies the Idira EOL template + populates all slides
```
