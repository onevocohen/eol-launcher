# EOL Kickoff Toolkit — Cursor and Claude Code Skill

> *Deprecating a product is never fun. At least the paperwork can be.*

Sunsetting a product means juggling Asana forms, Slides templates, and calendar invites — before the real work even begins. This skill handles all of that in a single conversation.

Open the EOL Kickoff Toolkit in Cursor or Claude Code and tell it what you're deprecating. The assistant asks a few basics in one message (answer in free text; "TBD" is fine), then takes care of the rest: the Asana request, the kickoff deck, the kickoff meeting invite, and a private Slack channel.

You don't need to have the EOL figured out. The skill prepares you **for** the kickoff meeting. Anything still undecided goes into the deck as an open question for that meeting.

---

Your starting point for kicking off an End-of-Life process — from a single conversation in Cursor or Claude Code.

> **Note:** This toolkit covers the kickoff phase. The full EOL process (legal review, customer communications, product sunset, etc.) continues beyond what this skill automates.

---

## What gets done for you

| | Output | Where |
|---|---|---|
| 📋 | EOL request logged | [Asana — EOL Request form](https://app.asana.com/1/11915891072957/project/1214130454046893) |
| 📊 | Kickoff deck: known info, proposed assumptions, open questions, stakeholders, next steps | Google Slides (copy of the Idira EOL template) |
| 📅 | 30-minute EOL review meeting | Google Calendar + Google Meet |
| 💬 | Private Slack channel, verified | Slack — the same participants as the invite |

All four are created automatically in one flow — giving you everything you need to kick off the EOL process. You don't open Asana, you don't touch the Slides template, you don't create a calendar invite, you don't set up a channel.

---

## 📊 Usage Statistics

<!-- USAGE_STATS_START -->
| Metric | Count |
|---|---|
| 🚀 Times skill used | **1** |
| 👤 Unique PMs | **1** |
| 📦 Unique products | **1** |

*Last updated: November 08, 2026 at 08:38 UTC*

**Per-PM breakdown:**

| PM | EOL sessions |
|---|---|
| Orit | 1 |
<!-- USAGE_STATS_END -->

> Stats are tracked locally in `metrics/usage.json` and updated automatically each time the skill is triggered. To refresh them manually, run: `python3 scripts/track_usage.py update-readme`

---

## How to start

**Start the skill with any of these:**

> *"I want to work on an EOL"*
> *"I have a product I want to deprecate"*
> *"Start an EOL for [product name]"*

### What happens next

```
You mention EOL
     ↓
AI identifies you from your Asana connection (no "what's your name?")
     ↓
AI asks the basics in ONE message, answer in free text, "TBD" is fine:
  1. What are you retiring: a product or a feature?
  2. Target timeline?
  3. Why, and what replaces it?
     ↓
AI searches Asana automatically and merges anything already submitted
     ↓
(One short follow-up only if the name or product/feature type is still unclear)
     ↓
          Create Asana task (if new)
                 ↓
          Create Google Slides kickoff deck
                 ↓
          Create 30-min Google Meet invite
          → Invites the participants for your EOL type (see "Who's invited")
          → Finds a Mon–Thu slot that's free for everyone, in everyone's time zone
          → Deck + Asana links and agenda included
                 ↓
          Create private Slack channel
          → Same people + anyone else you name
                 ↓
          Share all links + what's known / proposed / open
```

No approval round: the deck is created as soon as the basics are known, and you refine it afterwards.

### Product or feature? It changes what's included

| | Product EOL | Feature EOL |
|---|---|---|
| SKU & pricing | Included. Open questions until confirmed | Auto-filled "None" / "No pricing impact" (*proposed*). Switched back on if the feature is sold or priced separately (add-on, license, SKU) |
| SKU & Pricing owner | Required | Only with commercial impact |
| Customer impact | Customers, open opps, ARR | Tenants using the feature |
| Default communication | External Communication Request (email + in-app, Legal approval) | What's New + docs |
| Roles suggested for kickoff | R&D, RevOps, Sales / Deal Desk, CS, Support, Marketing, Legal, Tech Writers | R&D, Support, Tech Writers (+ CS if strategic accounts) |

### Don't know yet? That's expected

Say "TBD", "don't know yet" or "let's discuss at kickoff". In the deck, every item is one of:

- **Known**: what you said, or what's in Asana. Written as-is.
- **Proposed**: a smart default, tagged *"(Proposed — confirm at kickoff)"*. Never presented as a decision.
- **TBD**: shown as *"TBD — open question for kickoff"* and listed on the **Open Questions & Decisions** slide.

---

## The deck (13 slides)

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
| 10 | **Open Questions & Decisions** — open questions, pending decisions, proposed assumptions *(new)* |
| 11 | **Stakeholders & Next Steps** — who's invited, roles to involve, suggested next steps *(new)* |
| 12 | Q&A |

---

## Who's invited, and why

Stakeholders are defined by **role** in [stakeholders.json](stakeholders.json), the one place to
update when someone changes jobs. Each role says why it's needed and when it applies. The deck,
the calendar invite and the Slack channel all use the same resolved list.

| Role | Why | When | Today |
|---|---|---|---|
| EOL owner (PM) | Owns the decision and plan; escalation point | Always | You |
| EOL process review | Checks the plan against EOL governance | Always | per `stakeholders.json` |
| Product Operations | Runs the EOL process and tracking | Always | per `stakeholders.json` |
| SKU & Pricing owner | Retires SKUs, approves migration offers | Product EOLs, and features with commercial impact | per `stakeholders.json` |
| R&D, RevOps, Sales, CS, Support, Marketing, Legal, Tech Writers | Listed on the deck as roles to involve, with the reason for each | By EOL type | Named per EOL |

If you name someone ("Yanai owns this", "add Dana from R&D"), they're added to the invite,
the Slack channel and the deck as a required participant, in the role you gave them.

---

## The calendar invite

- **Title:** EOL - [product name] · 30 minutes · Google Meet
- **Attendees:** the participants above (optional ones marked optional). Checked after booking.
- **Timing:** the first slot that is **Mon–Thu, inside 09:00–17:00 local time for every
  participant, and free on everyone's calendar**. Existing meetings are never overridden.
  With people in several time zones (e.g. Israel + US) you're asked once whether the proposed
  time works or which hours you prefer. If nothing fits, you get alternatives and nothing is booked.

---

## The Slack channel

- **Name:** `#eol-<normalized-product-name>` *(adds `-2` if that name is already taken)*
- **Type:** Private (checked with Slack after creation; a public channel is never used)
- **Members:** same participants as the invite, checked against Slack's member list
- **First message:** links to the deck, Asana task (and project), open questions and participants
- If it can't be created (no token, missing permission, workspace policy), you're told exactly
  why and what's needed. It's never reported as done.

---

## What the AI pulls from Asana automatically

If you (or a teammate) already submitted the EOL request form, the AI finds and uses it — no link needed.
It won't ask you about anything Asana already answers.

| Pulled from Asana | Used for |
|---|---|
| Product name, EOL description | Announcement |
| Whether SKUs are impacted | Product vs. feature, without asking you |
| Whether an alternative exists | Alternatives (the name becomes an open question if missing) |
| Due date | Proposed EOL date |
| Submitter, status | Contact, roadmap status |

---

## What you're asked, and what's handled for you

| | Items |
|---|---|
| **Asked (one message)** | Name + product or feature · Target timeline · Why + replacement · *(optional)* extra Slack members |
| **Inferred, never asked** | Your name & email (Asana) · Deck date · Escalation contact (you) · Roadmap status · Asana project link |
| **Smart default (*proposed*)** | Communication plan & who's notified (per EOL type) · Feature EOLs: no SKU / no pricing / no sales action |
| **Deferred to the kickoff** | Customer & ARR impact · Existing-customer transition · Pricing & SKU codes (products) · anything you answered "TBD" |

---

## Requirements

- Credentials from either the **pm-claude-code-setup** Keychain vault (Claude Code) or the Cursor PM setup (`~/.config/secrets/get-secret.sh` + gcloud ADC with Drive + Slides + Calendar scopes) — the scripts try the vault first
- Access to the shared Idira EOL Google Slides template
- Asana access (for reading/creating the EOL request form task)
- Slack bot token with scopes: `groups:write`, `groups:read`, `users:read`, `users:read.email`, `chat:write`

The skill can be installed and discovered in Cursor and Claude Code on macOS and
Windows. Windows users can discover the skill, but end-to-end API automation is
not yet supported: the current credential helper uses Bash and Unix-style vault
paths.

---

## Install and updates

Install or move an existing copy onto automatic updates. These commands need
`gh` signed in to github.cyberng.com and Python 3. If `python` isn't on Windows
PATH, use `py -3` in its place.

| Client | macOS/Linux | Windows PowerShell |
|---|---|---|
| Cursor | `GH_HOST=github.cyberng.com gh api "repos/Product/pm-hub/contents/skills/_shared/skill-updater/self_update.py" -H "Accept: application/vnd.github.v3.raw" \| python3 - --root "$HOME/.cursor/skills" --install eol-launcher` | `$env:GH_HOST="github.cyberng.com"; gh api "repos/Product/pm-hub/contents/skills/_shared/skill-updater/self_update.py" -H "Accept: application/vnd.github.v3.raw" \| python - --root "$HOME\.cursor\skills" --install eol-launcher` |
| Claude Code | `GH_HOST=github.cyberng.com gh api "repos/Product/pm-hub/contents/skills/_shared/skill-updater/self_update.py" -H "Accept: application/vnd.github.v3.raw" \| python3 - --install eol-launcher` | `$env:GH_HOST="github.cyberng.com"; gh api "repos/Product/pm-hub/contents/skills/_shared/skill-updater/self_update.py" -H "Accept: application/vnd.github.v3.raw" \| python - --install eol-launcher` |

Restart Claude Code or reload the Cursor window after a first install. The
updater may show a Claude Code-specific restart prompt even for Cursor; reload
Cursor instead.

After that, the skill keeps itself up to date. At most once every 6 hours, its first step checks PM Hub for a newer version. If there is one, it installs it and tells you in one line what changed (see [CHANGELOG.md](CHANGELOG.md)). If you're offline or `gh` isn't signed in, it uses your current copy and says so once.

- Your own files in the skill folder are never touched. Only files that ship with the skill are replaced.
- If you edited a skill file, your version is backed up under the client's `.skill-updates/eol-launcher/backups/` folder before the update, and the notice tells you where.
- Details: [skills/_shared/skill-updater](../_shared/skill-updater/README.md).

---

## Usage telemetry

The skill reports usage events (session start/end, which steps ran, how long they took, pass/fail) to the internal observability platform through `scripts/obs.py`. No PM input, product details, or generated content is sent; the user is identified by OS username. Sending is silent, best-effort, and times out after 5 seconds, so it never blocks a run.

Dashboard: https://d2logaj4xs1c79.cloudfront.net

---

## Files

```
eol-launcher/
├── README.md                  ← you are here
├── SKILL.md                   ← AI instructions (technical)
├── CHANGELOG.md               ← what changed in each version
├── stakeholders.json          ← role → owner map, why each role is needed, scheduling defaults
└── scripts/
    ├── fetch_asana.py         ← searches Asana by product name, returns form data
    ├── submit_asana.py        ← creates a new Asana task from PM answers
    ├── create_deck.py         ← copies the Idira EOL template, populates it, adds the kickoff slides
    ├── create_calendar.py     ← creates a 30-min Google Meet invite with deck + Asana links
    ├── create_slack_channel.py ← creates a private Slack channel + invites members
    ├── eol_rules.py           ← product/feature logic, smart defaults, open questions, stakeholders
    ├── whoami.py              ← identifies the PM from their Asana connection
    ├── track_usage.py         ← logs usage events + updates README stats (this repo only)
    ├── scheduling.py          ← finds a slot: Mon–Thu, time zones, real availability
    ├── vault_http.py          ← shared credential + HTTP helper (vault first, legacy setup fallback)
    ├── obs.py                 ← silent usage telemetry (no PM content sent)
    └── self_update.py         ← automatic updates from PM Hub
```
