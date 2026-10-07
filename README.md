# EOL Deck Builder

Automatically generates a Idira End-of-Life session deck in Google Slides.
Give the AI your Asana task, a PRD, or just a description — it builds the deck and hands you a link.

---

## What you get

A fully populated copy of the Idira EOL template (11 slides), ready to review and present:

| Slide | Content |
|---|---|
| 1 | Cover — product name + date |
| 2 | EOL Roadmap — current status on the journey |
| 3 | Announcement & Timeline — what's being EOLed + key dates |
| 4 | Business Rationale — why it's happening |
| 5 | Customer Impact — open deals + escalation path |
| 6 | Sales & Renewals Guidance — new vs. existing customer playbook |
| 7 | Alternatives & Pricing — replacement product + pricing impact |
| 8 | Communication Plan — channels, segments, contact |
| 9 | Technical & SKU Details — impacted SKU codes |
| 10 | Q&A |

---

## How to use it

**Say any of these to the AI in Cursor:**

> *"Create an EOL deck"*
> *"Build an end-of-life presentation for [product]"*
> *"Make an EOS session deck"*

Then give the AI the product name — that's it. It will:

1. **Search Asana automatically** for your EOL request form submission
2. Pull everything it can from there
3. Ask you only for what's still missing

You can also optionally share a PRD, spec, or any additional context to reduce the follow-up questions further.

---

## The Asana connection

The skill is connected to the [EOL - Request form](https://app.asana.com/1/11915891072957/project/1214130454046893) project in Asana.

The AI searches it automatically by product name — **you never need to find or share the task link**. When it finds your submission, it automatically extracts:

| Extracts automatically | Still asks you for |
|---|---|
| Product name | Deck date |
| EOL description / announcement | Key milestone dates |
| Whether an alternative exists | Business rationale |
| Submitter's contact email | Open pipeline / ARR affected |
| Task status | Escalation contact |
| Whether SKUs are impacted | Actual SKU codes (if flagged) |
| | New / existing customer guidance |
| | Pricing & migration offer |
| | Communication plan |

---

## What the AI will ask you (if it can't find the answer)

Questions are sent **in one batch** — not one at a time. Here's what to expect:

### Basics
1. What is the exact name of the product or feature being EOLed?
2. When will this EOL session be presented? *(becomes the deck date)*

### Announcement & Timeline
3. In 2–3 sentences, what exactly is being EOLed? *(scope + effective date)*
4. What are the key milestone dates? *(announcement, stop-sell, EOS, EOL)*

### Business Rationale
5. Why is this product being EOLed? *(list the main reasons)*

### Customer Impact
6. How many open opportunities or active customers are affected? *(count + ARR)*
7. Who should sales escalate affected deals to?

### Sales & Renewals
8. What should sales tell a new prospect who asks about this product?
9. What transition offer or path exists for existing customers?

### Alternatives & Pricing
10. What is the recommended alternative product? *(name + 2–3 key reasons)*
11. Are there pricing changes, migration discounts, or bridge offers?

### Communication Plan
12. How and when will Idira communicate this EOL to customers?
13. Which customer segments will receive the notice?
14. Who is the primary contact for EOL questions from the field?

### SKU Details
15. What are the specific SKU codes or names being retired?

### Roadmap Status *(optional)*
16. What is the current status of the EOL process? *(what has already happened)*

---

## Requirements

- Cursor with your Google account connected (ADC set up)
- Access to the shared Idira EOL Google Slides template
- Asana access *(optional — only needed if pulling from the request form)*

---

## Files

```
eol-deck-builder/
├── README.md              ← you are here
├── SKILL.md               ← AI instructions (technical)
└── scripts/
    ├── fetch_asana.py     ← pulls data from the Asana EOL form
    └── create_deck.py     ← copies the template + populates slides
```
