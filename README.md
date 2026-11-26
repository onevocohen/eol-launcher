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
| 💬 | Private Slack channel created | Slack — PM, Yael & Orit invited (+ Amir for product EOLs and commercial features) |

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
          → Invites you, Yael and Orit (+ Amir for product / commercial EOLs)
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
| Amir Aviad (pricing & SKUs) | Invited | Only with commercial impact |
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

## The Slack channel

- **Name:** `#eol-<normalized-product-name>` *(lowercase, hyphens)*
- **Type:** Private
- **Attendees:** You (the PM) + Yael Gershon + Orit Nevo Cohen + anyone extra you name. Amir Aviad (pricing & SKUs) is added for product EOLs and for feature EOLs with commercial impact. Plain feature deprecations skip him.
- **First message:** intro post with links to the deck and Asana task — plus the Asana **project**, if the EOL request was converted to one

---

## The calendar invite

- **Title:** EOL - [product name]
- **Duration:** 30 minutes
- **Format:** Google Meet
- **Attendees:** You (the PM) + Yael Gershon + Orit Nevo Cohen, plus Amir Aviad for product EOLs and commercial features
- **Description:** includes a direct link to the deck and the Asana task, and a short agenda (resolve the open questions)
- **Timing:** next available Israel working-day slot (Sun–Thu, 9am–5pm)

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
└── scripts/
    ├── fetch_asana.py         ← searches Asana by product name, returns form data
    ├── submit_asana.py        ← creates a new Asana task from PM answers
    ├── create_deck.py         ← copies the Idira EOL template, populates it, adds the kickoff slides
    ├── create_calendar.py     ← creates a 30-min Google Meet invite with deck + Asana links
    ├── create_slack_channel.py ← creates a private Slack channel + invites members
    ├── eol_rules.py           ← product/feature logic, smart defaults, open questions, stakeholders
    ├── whoami.py              ← identifies the PM from their Asana connection
    ├── track_usage.py         ← logs usage events + updates README stats (this repo only)
    ├── vault_http.py          ← shared credential + HTTP helper (vault first, legacy setup fallback)
    ├── obs.py                 ← silent usage telemetry (no PM content sent)
    └── self_update.py         ← automatic updates from PM Hub
```
