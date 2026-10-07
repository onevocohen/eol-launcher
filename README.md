# EOL Package — Cursor Agent Skill

Handles the full End-of-Life process from a single conversation in Cursor.
Tell the AI you're deprecating a product — it takes care of everything: the Asana task, the deck, and the calendar invite.

---

## What gets done for you

| | Output | Where |
|---|---|---|
| 📋 | EOL request logged | [Asana — EOL Request form](https://app.asana.com/1/11915891072957/project/1214130454046893) |
| 📊 | Session deck, fully populated | Google Slides (copy of the Idira EOL template) |
| 📅 | 30-minute EOL review meeting | Google Calendar + Google Meet |

All three are created automatically in one flow. You don't open Asana, you don't touch the Slides template, you don't create a calendar invite.

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
Ask only for gaps          (one at a time, conversationally)
     ↓                           ↓
                    Create Asana task (if new)
                           ↓
                    Create Google Slides deck
                           ↓
          Create 30-min Google Meet invite
          → Invites you, Yael, and Amir automatically
          → Deck + Asana links included in the invite
                           ↓
              Share all links with you
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

## The calendar invite

- **Title:** EOL - [product name]
- **Duration:** 30 minutes
- **Format:** Google Meet
- **Attendees:** You (the PM) + Yael Gershon + Amir Aviad
- **Description:** includes a direct link to the deck and the Asana task
- **Timing:** next available Israel working-day slot (Sun–Thu, 9am–5pm)

---

## What the AI pulls from Asana automatically

If you (or a teammate) already submitted the EOL request form, the AI finds and uses it — no link needed.

| Pulled from Asana | Still asks you for |
|---|---|
| Product name | Key milestone / EOL date |
| EOL description | Business rationale |
| Whether an alternative exists | Actual alternative product name |
| Submitter contact email | New / existing customer guidance |
| Task status | Pricing & migration offer |
| Whether SKUs are impacted | Actual SKU codes (if flagged) |
| | Communication plan |

---

## Questions you may be asked

Questions are asked **one at a time** — conversational, not a form dump.

| Topic | What's asked |
|---|---|
| **Announcement** | What's being EOLed and when (EOL date) |
| **Rationale** | Why is this happening? *(rephrased to polished business language)* |
| **Sales guidance** | Message for new prospects · Transition offer for existing customers |
| **Alternatives** | Replacement product + reasons |
| **Pricing** | Migration offer or pricing changes |
| **Communication** | Channels & timing · Who gets notified |
| **SKUs** | Specific SKU codes being retired |

> **Auto-filled — never asked:**
> - Deck date → current month + year
> - Escalation contact → you (the submitting PM)

---

## Requirements

- Cursor with your Google account connected (ADC configured with Drive + Slides + Calendar scopes)
- Access to the shared Idira EOL Google Slides template
- Asana access (for reading/creating the EOL request form task)

---

## Files

```
eol-launcher/
├── README.md                  ← you are here
├── SKILL.md                   ← AI instructions (technical)
└── scripts/
    ├── fetch_asana.py         ← searches Asana by product name, returns form data
    ├── submit_asana.py        ← creates a new Asana task from PM answers
    ├── create_deck.py         ← copies the Idira EOL template + populates all slides
    └── create_calendar.py     ← creates a 30-min Google Meet invite with deck + Asana links
```
