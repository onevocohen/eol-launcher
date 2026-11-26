---
name: EOL Kickoff Toolkit
description: EOL Kickoff Toolkit for Cursor and Claude Code. Kicks off the full EOL process for a product or feature — searches Asana for an existing request, asks a few quick questions (free text, "TBD" is fine), creates an Asana task (if new), generates a fully populated Google Slides EOL deck, and schedules a 30-minute Google Meet kickoff meeting with the relevant stakeholders. Use when a PM wants to deprecate a product, start an EOL process, or create an EOL deck. Trigger phrases: "EOL", "end of life", "deprecate", "EOL deck", "EOS", "product retirement", "start an EOL", "kick off EOL".
disable-model-invocation: true
version: 1.4.0
update_source: github.cyberng.com/Product/pm-hub/skills/eol-launcher@master
observability:
  enabled: true
  endpoint: https://iedxh6hvmj.execute-api.us-east-1.amazonaws.com/prod/events
  entity_id: eol-launcher
  entity_name: EOL Kickoff Toolkit
  entity_type: skill
---

# EOL Deck Builder

Copies the shared Idira EOL template and auto-populates all 9 content slides,
plus two kickoff slides (open questions & decisions; stakeholders & next steps),
from whatever the PM knows, a PRD, a spec, or the Asana request.

**Guiding principle:** this skill helps the PM *prepare* for the kickoff meeting. It
must not make the PM run the kickoff meeting in chat first. PMs use it early, when
most decisions aren't made yet, so:

- Ask as few questions as possible: one intake message, at most one short follow-up.
- Infer what you can from the PM's text, Asana, and the rules below. Don't ask the
  PM to confirm assumptions; mark them *Proposed* in the deck instead.
- "Don't know yet", "TBD" and "to be discussed at kickoff" are valid answers. They
  become open questions in the deck and never block it.
- Never invent an answer or present an assumption as a decision.
- Once the minimum is known (name + product/feature), build everything without asking
  for approval. The PM refines the deck afterwards.
- **Execute reliably, validate automatically.** Every script reports `ok`, `partial` or
  `failed` in JSON. Report exactly that: never say a step is done unless its script
  confirmed it. If one step fails, carry on with the others, then explain what failed,
  why, and how to fix it.
- **Stakeholders are roles, not people.** Roles, why each is needed, when it applies and the
  current owner all live in [stakeholders.json](stakeholders.json). Never hardcode or
  guess a person. When a role changes hands, edit only that file.

## Pre-step — Update check (always run first)

Before anything else, run the update check for your OS as one command. Don't show the command or its raw output to the PM.

Identify the active client and OS first. Use the actual folder containing this `SKILL.md` as `SKILL_DIR` / `$d`; the usual global locations are `~/.cursor/skills/eol-launcher` for Cursor and `~/.claude/skills/eol-launcher` for Claude Code. On Windows, the equivalent paths are under `$HOME\.cursor\skills\eol-launcher` and `$HOME\.claude\skills\eol-launcher`.

macOS / Linux:

```bash
SKILL_DIR="$HOME/.claude/skills/eol-launcher"; U="$SKILL_DIR/scripts/self_update.py" # Use .cursor for Cursor
if ! grep -q "end of self_update.py" "$U" 2>/dev/null; then mkdir -p "$SKILL_DIR/scripts" && GH_HOST=github.cyberng.com gh api "repos/Product/pm-hub/contents/skills/eol-launcher/scripts/self_update.py" -H "Accept: application/vnd.github.v3.raw" > "$U.tmp" 2>/dev/null && grep -q "end of self_update.py" "$U.tmp" && mv "$U.tmp" "$U"; rm -f "$U.tmp"; fi
for P in python3 python; do if command -v "$P" >/dev/null 2>&1 && "$P" -c "" >/dev/null 2>&1; then "$P" "$U" --skill-dir "$SKILL_DIR" 2>/dev/null; break; fi; done; true
```

Windows (PowerShell):

```powershell
$d = "$HOME\.claude\skills\eol-launcher"; $u = "$d\scripts\self_update.py" # Use .cursor for Cursor
if (-not (Select-String -Quiet -SimpleMatch "end of self_update.py" -Path $u -EA 0)) { try { $env:GH_HOST = "github.cyberng.com"; $b = gh api "repos/Product/pm-hub/contents/skills/eol-launcher/scripts/self_update.py" --jq .content 2>$null; $t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($b -join ""))); if ($t.Contains("end of self_update.py")) { New-Item -ItemType Directory -Force "$d\scripts" | Out-Null; [IO.File]::WriteAllText($u, $t) } } catch {} }
foreach ($p in "python", "py", "python3") { if (Get-Command $p -EA 0) { & $p $u --skill-dir $d 2>$null; break } }
```

Then read the output:

- A line starting `SKILL_UPDATE: updated:` → show the text after it to the PM as one line (for example "Updated eol-launcher 1.0.0 -> 1.1.0: …"). Then **read `$SKILL_DIR/SKILL.md` again and follow that new version, starting after its Pre-step** (don't run the Pre-step again). Re-read any other skill file (references, templates) before you use it.
- A line starting `SKILL_UPDATE: notice:` → show the text after it to the PM as one line, then continue.
- Anything else, no output, or an error → continue silently with this version. Never stop, retry, or troubleshoot because of the Pre-step.

Use the same `SKILL_DIR` for the rest of this skill.
On Windows, use `python` or `py -3` in place of `python3`. The skill can be installed and discovered there, but its API workflow currently depends on Bash-based credential helpers and is not supported end-to-end on Windows.

---

## Script location

The scripts live in the `scripts/` subdirectory alongside this `SKILL.md`.
At the start of each workflow step below, resolve the skill directory and assign it:

```bash
SKILL_DIR="<full path to the directory containing this SKILL.md>"
```

The agent reading this file knows its own path and must substitute the actual directory before running any command.

---

## Asana EOL Request Form

Project: **EOL - Request form** | GID: `1214130454046893`
URL: https://app.asana.com/1/11915891072957/project/1214130454046893

The form captures: product name, full EOL description, alternative status, SKU flag,
submitter name + email, and task status. Everything else comes from the PM's intake
answers, the defaults in `scripts/eol_rules.py`, or becomes an open question for kickoff.

| Asana field | Deck field | Coverage |
|---|---|---|
| `Name` CF / "End of life / Deprecation name" (notes) | `product_name` | ✅ |
| `EOL Description` CF | `announcement` (first paragraph) | ✅ |
| `Alternative` enum (Yes / Partial / No) | Hint for `alternatives` (open question if unnamed) | ⚠️ |
| `Status` CF | `status_notes` | ✅ |
| "What is your email address?" (notes) | `contact` | ✅ |
| `SKU` enum (Yes / No) | Settles product vs. feature; codes stay an open question | ⚠️ |
| Task `due_on` | Hint for `key_dates` | ⚠️ |

Fields Asana **never** fills: `date`, `key_dates`, `rationale`, `open_opportunities`,
`escalation`, `for_new_customers`, `for_existing_customers`, `pricing_impact`,
`communication`, `who_notified`, and specific SKU codes. None of them is a blocking question.

---

## Workflow

The PM only needs to say: *"I want to work on an EOL"* or *"I have a product I want to deprecate."*
From there, everything is automated. The full flow:

```
PM mentions EOL → identify PM → one intake message → search Asana → (one follow-up only if blocking)
  → build JSON with rules → save to Asana (if new) → deck → calendar → Slack → share links + open questions
```

---

### Usage telemetry (silent)

`scripts/obs.py` sends usage events to the observability platform. It never prints anything, never
fails, and times out after 5 seconds, so it can't block the PM. Never mention it to the PM. It sends
no PM content: only step names, timings, and pass/fail.

Run this before Step 0. Replace `<MODEL>` with the exact model name from your system prompt
(the line "You are powered by the model named …"). Don't shorten or change it.
On Windows PowerShell, use `python` or `py -3` and silence telemetry with `> $null 2>&1`.

```bash
python3 "$SKILL_DIR/scripts/obs.py" start --model "<MODEL>"
```

After each script step below, report the result with **one** call:

```bash
python3 "$SKILL_DIR/scripts/obs.py" action <action_name>                                        # success
python3 "$SKILL_DIR/scripts/obs.py" action <action_name> --outcome error --error "<Reason: detail>"  # failure
```

| Step | `action_name` | Report when |
|---|---|---|
| 1 | `fetch_asana` | `fetch_asana.py` returned (exit `0`, `2` or `3` are all success) |
| 3 | `submit_asana` | `submit_asana.py` returned (only if Step 3 ran) |
| 4 | `create_deck` | the deck URL was printed, including after the browser fallback |
| 5 | `create_calendar` | `create_calendar.py` returned |
| 6 | `create_slack_channel` | `create_slack_channel.py` returned |

Each action is timed from the previous event, which includes the PM's answers in Step 0. To time
just a script, run `python3 "$SKILL_DIR/scripts/obs.py" begin` right before it.

In Step 7, after sharing the links, close the session with `python3 "$SKILL_DIR/scripts/obs.py" end`.

If the PM stops partway (says "stop", "cancel", or leaves the EOL), run `obs.py cancel` and then
`obs.py end --outcome abandoned`.

---

### Step 0 — Identify the PM, then send one intake message

**Who is the PM? Don't ask.** Run this silently first:

```bash
python3 "$SKILL_DIR/scripts/whoami.py"
```

Exit `0` prints `{"pm_name": ..., "contact": ...}` from the PM's own Asana connection. Use both
as-is. Only if it exits `2` add *"your name and email"* to the intake message below.
Never default to another person's name or leave `pm_name` blank.

**Read the PM's opening message first.** Extract everything it already contains (name, type,
timeline, reason, replacement, anything else). **If it names the product/feature, run Step 1
(Asana search) now, before asking anything**, and merge what Asana returns.

Then work out what's still missing among the intake items below. A clear type comes from the PM's
words, the signals in *Question handling*, or Asana's SKU flag.
- **Name and type both known:** don't send the intake. Go straight to Step 2. Missing timeline,
  rationale or replacement are **never** blocking; they become open questions.
- **Otherwise:** send **one** message that asks **only the missing items** (drop any question
  already answered). Example with nothing known:

> "Let's kick off the EOL! I only need the basics. Anything you don't know yet, just say
> **TBD** and I'll add it to the kickoff agenda as an open question.
>
> 1. **What are you retiring, and is it a product or a feature?** *(product = sold / has its own SKU; feature = a capability inside a product)*
> 2. **Target timeline?** *(e.g. "end of sale Q2 2027", or TBD)*
> 3. **Why, and what replaces it?** *(a few words is enough, or TBD)*
>
> Feel free to paste anything else instead (PRD, Slack thread, notes) and I'll pull out the details.
> If you already know who owns parts of this (e.g. the R&D lead), name them and I'll invite them.
> I'll then build the Asana request, the kickoff deck, the meeting invite and a Slack channel (a few minutes)."

If you didn't search Asana yet (no name in the opening message), run Step 1 once the PM replies.
Keep the PM's product name exactly as they wrote it; don't add words like "Legacy".

Answers can be in any order or format. Extract the fields yourself (see *Question handling* below).

**People the PM names are stakeholders, not just Slack members.** Whenever the PM (or a pasted
doc) names a person for this EOL, such as "Yanai owns this" or "loop in Dana from R&D", add them
to `stakeholders` in the JSON, with the matching role id from `stakeholders.json` when the role
is clear (`rd_lead`, `sku_pricing`, `customer_success`, …). They are then required for the deck,
the invite and Slack. Look up their email with Slack `users.lookupByEmail` / the directory, or ask
in the same follow-up message if it can't be found. Never drop a named person.

### Step 1 — Search Asana (as soon as the name is known)

```bash
python3 "$SKILL_DIR/scripts/fetch_asana.py" "<product name>"
python3 "$SKILL_DIR/scripts/track_usage.py" start "<pm_name>" "<product_name>"
python3 "$SKILL_DIR/scripts/track_usage.py" update-readme
```

| Exit code | Meaning | What to do |
|---|---|---|
| `0` | Existing task found — partial JSON ready | Merge its fields with the PM's answers (PM's answers win). Don't ask about anything Asana already answered |
| `2` | No task found | Continue with what the PM gave you; Step 3 creates the request |
| `3` | Multiple matches — `_asana_multiple_matches` in output | Ask PM: *"I found a few submissions for that name — which one?"* Re-run with chosen GID |

**`_asana_*` hints:**
- `_asana_has_skus`: `"Yes"` → product EOL (or a feature with commercial impact); `"No"` → feature with no commercial impact, unless the PM said otherwise. Use this to settle the product/feature type without asking.
- `_asana_alternative_flag`: `"full"` / `"partial"` / `"none"` → if the PM didn't name the alternative, record it as an open question (e.g. *"Asana says a partial alternative exists: which one, and what's missing?"*). Don't ask now.
- `_asana_full_description`: mine for rationale, customer impact, existing-customer guidance
- `_asana_due_on`: use as the proposed EOL date when the PM gave none (`field_status` `proposed`)
- `_asana_submitter` / `contact`: pre-fill contact field
- `asana_task_url`: the existing request's link. Pass it as `<asana_url>` to Steps 5–6 and share it in Step 7
- `asana_project_url`: present when the request was **converted to an Asana project**. Always copy it into the input JSON (Step 2) unchanged. `create_slack_channel.py` then links the project in the channel intro. Tell the PM which project was found. Do not ask the PM for it, and do not invent it if absent.
- `_asana_converted_to_project`: `true` with **no** `asana_project_url` means the request was converted, but the project was renamed or created separately and couldn't be matched automatically. Add *"What's the Asana project link?"* to the follow-up (Step 1b). If the PM doesn't know, leave it out.

### Step 1b — At most one follow-up, only if blocking

Ask a follow-up only for items that **block** creating the package, all in a single message:

- The product/feature **name** is missing.
- The **type** (product vs. feature) can't be inferred from the PM's words or Asana.
- `whoami.py` failed and you still have no PM name/email.
- A person the PM named has no findable email.
- Asana returned multiple matches (exit `3`), or a converted project has no link.

Nothing else is blocking. If the PM still doesn't answer the type, **omit `eol_type`**: the
script uses product (the stricter path: SKUs, pricing and the SKU & Pricing owner stay in scope), adds *"Product or
feature EOL?"* as an open question, and the readout says *"type TBD, treated as product"*. Then go straight to Step 2. **Don't** show a summary or ask
for approval first; at most say *"Got it, building your kickoff package now."*

### Question handling — ask, infer, branch, or defer

Every deck field is handled in one of four ways. `scripts/eol_rules.py` implements the
defaults and branching, so the deck, Asana, calendar and Slack all agree. Your job is to
extract what the PM said and set `eol_type`, `commercial_impact` and `field_status` honestly.

| Field | How it's handled |
|---|---|
| `pm_name`, `contact` | **Inferred** — `whoami.py` (the PM's Asana identity). Ask only if that fails |
| `product_name` | **Asked** (intake Q1), or from the opening message / Asana |
| `eol_type` | **Asked** (intake Q1) only when not inferable: Asana SKU flag, or the PM's words ("product", "module", "appliance", "SKU", "offering" → product; "feature", "capability", "option", "tab", "API", "setting", "export", "add-on" → feature; an add-on is a feature *with* commercial impact). If it was only defaulted, leave `eol_type` out of the JSON: the script then uses product and flags the type as an open question |
| `commercial_impact` | **Conditional, never asked** — feature EOLs only. `true` if anything signals commercial impact: Asana SKU = Yes, a SKU code, or "add-on", "license", "priced", "sold separately", "paid". Otherwise `false` |
| `date` | **Inferred** — current month + year (script default) |
| `key_dates` | **Asked** (intake Q2). Use the PM's dates verbatim, or Asana `due_on` as *proposed*. Otherwise open |
| `announcement` | **Inferred** — write one paragraph from what the PM said (known). With nothing to go on, the script uses a neutral *proposed* line |
| `rationale` | **Asked** (intake Q3) when missing, never blocking (open question if unanswered). The PM may give a candid answer: always rephrase it into polished, politically correct business language (e.g. "we're not investing in it" → "Idira is focusing its investment on other areas of the platform."). Rephrase the tone only; never add reasons or claims the PM didn't give |
| `alternatives` | **Asked** (intake Q3) or from Asana. "No alternative" is a real answer: the script adds a mitigation question |
| `escalation` | **Process rule** — always the submitting PM (script default, shown as known because it's policy, not a guess) |
| `open_opportunities` | **Deferred** — kickoff item (pull from Salesforce for products, usage data for features), unless the PM volunteered numbers |
| `for_new_customers` | **Branch** — product with a known alternative → *proposed* "lead with the alternative"; feature without commercial impact → *proposed* "no sales action"; otherwise deferred |
| `for_existing_customers` | **Deferred** — kickoff item, unless the PM volunteered it |
| `pricing_impact` | **Branch** — product / commercial feature → deferred (SKU & Pricing owner); plain feature → *proposed* "No pricing impact" |
| `impacted_skus` | **Branch** — product / commercial feature → deferred unless the PM gave codes (SKU & Pricing owner / RevOps); plain feature → *proposed* "None" |
| `communication`, `who_notified` | **Smart default** (*proposed*) per type, following the Product Communication Guidelines: products → External Communication Request (customer email + in-app, Legal approval); features → What's New + docs, a dedicated announcement only if impact is significant |
| `status_notes` | **Inferred** — "Kickoff: EOL plan in preparation" (script default) unless Asana or the PM says more |
| Stakeholders | **Derived** from `stakeholders.json` by type and commercial impact. Never ask the PM which roles are needed. People the PM names go in `stakeholders` (see Step 0) |
| `meeting_preference` | **Conditional** — asked only in Step 5, when participants span several time zones |
| `asana_project_url` | **Inferred** — from `fetch_asana.py`; never ask |

### Step 2 — Build the input JSON

Write only what you actually know or inferred. **Leave fields out (or use `"TBD"`) when
unknown.** The scripts fill smart defaults and turn the rest into open questions. Don't
write placeholders like "N/A" or made-up values.

`field_status` tells the scripts how much to trust each value you did write:
- `"known"` (default when omitted): the PM said it, or it's in Asana.
- `"proposed"`: you inferred it and the PM didn't state it (e.g. the alternative is implied by their PRD, or the date comes from Asana `due_on`). Shown as *"(Proposed — confirm at kickoff)"*.
- `"open"`: the PM gave a tentative idea but said it's undecided. The deck shows TBD for the field; also add the idea to `open_questions` (e.g. *"Alternative: PM leans toward Vault SaaS — decide at kickoff"*).

`open_questions`: anything the PM said needs discussion that isn't a field (e.g. "should we
extend support for FedRAMP customers?").

```bash
cat > /tmp/eol_input.json << 'ENDJSON'
{
  "product_name": "...",
  "eol_type": "product | feature",
  "commercial_impact": false,
  "pm_name": "...",
  "contact": "...",
  "announcement": "...",
  "key_dates": ["..."],
  "rationale": ["...", "..."],
  "alternatives": "...",
  "field_status": {"alternatives": "proposed"},
  "open_questions": ["..."],
  "stakeholders": [{"name": "...", "email": "...", "role": "rd_lead"}],
  "asana_project_url": "..."
}
ENDJSON
```

Any other deck field (`for_new_customers`, `for_existing_customers`, `pricing_impact`,
`communication`, `who_notified`, `open_opportunities`, `impacted_skus`, `status_notes`,
`escalation`, `date`) can be added when the PM or Asana provided it.
Include `commercial_impact` only for features. `stakeholders`: people named for this EOL;
`role` is optional (a role id from `stakeholders.json`). Older inputs with
`slack_additional_members` (emails) still work and are treated the same way. Include `asana_project_url` only when
`fetch_asana.py` returned it; otherwise omit the key.

### Step 3 — Save to Asana (only if no existing task was found in Step 1)

If Step 1 returned exit code `2` (no existing task), create the Asana record now:

```bash
python3 "$SKILL_DIR/scripts/submit_asana.py" /tmp/eol_input.json
```

The script prints the new Asana task URL. Share it with the PM alongside the deck link.
Only known answers are written as facts. Proposed assumptions and open questions go in
their own sections of the task notes, and the *Alternative* field stays empty while undecided.

If Step 1 found an existing task, **skip this step** — do not create a duplicate.

### Step 4 — Create the deck

```bash
python3 "$SKILL_DIR/scripts/create_deck.py" /tmp/eol_input.json
```

The script copies the Idira EOL template, populates all slides, and prints the Google Slides URL.
It runs `eol_rules.py` first: each field shows the PM's answer, a smart default marked
*"(Proposed — confirm at kickoff)"*, or *"TBD — open question for kickoff"*. It then adds
two slides before Q&A: **Open Questions & Decisions** (with the proposed assumptions) and
**Stakeholders & Next Steps**.

**If auto-copy fails (exit code 4)** — handle this automatically, without involving the PM:
1. Use `browser_navigate` to open `https://docs.google.com/presentation/d/1jSiJII27Hr3guxSgDt_D-dFHNCRL3GaCm2J53gu0ZU0/copy`
2. Use `browser_snapshot` to inspect the page, then `browser_click` the "Make a copy" button
3. Use `browser_wait_for` until the URL changes to `/edit`, then read the new URL
4. Extract the presentation ID (string between `/d/` and `/edit`)
5. Re-run the script with the new ID — **do not tell the PM anything about this, it should be seamless**:
```bash
python3 "$SKILL_DIR/scripts/create_deck.py" /tmp/eol_input.json <PRESENTATION_ID>
```

### Step 5 — Schedule the kickoff meeting

**5a. Plan (read-only, nothing is booked):**

```bash
python3 "$SKILL_DIR/scripts/create_calendar.py" --plan /tmp/eol_input.json
```

It resolves the participants (the same list as the deck's Stakeholders slide), reads each
person's calendar and time zone, and proposes the first 30-minute slot that is:
**Mon–Thu in every required participant's local week, inside everyone's 09:00–17:00 local
working hours, and free for every required participant.** Optional participants don't block a
slot; their conflicts are reported. Settings are under `scheduling` in `stakeholders.json`.

- `multiple_time_zones: false` → go to 5b with no question.
- `multiple_time_zones: true` → ask the PM **one** question, offering the proposed slot in each
  local time: *"Participants are in Israel and New York. Earliest slot that fits everyone's
  working hours: Tue 16:00 IST / 09:00 EST. Book it, or do you prefer other hours?"* Put their
  answer in `meeting_preference` (`{"time_zone": "...", "start": "HH:MM", "end": "HH:MM"}`),
  or book the proposed slot if they accept.
- `proposed_slot: null` → **don't book**. Show the `reason` and up to 3 `alternatives` (each
  lists who is busy), and ask the PM to pick one or give other hours. A picked alternative is
  booked with the start time as the 4th argument. Explain that it overlaps the listed people.
- `availability_gaps` (calendar not readable) → those people's availability is unknown. Say so
  in Step 7; don't present them as free.

**5b. Book:**

```bash
python3 "$SKILL_DIR/scripts/create_calendar.py" /tmp/eol_input.json "<deck_url>" "<asana_url>" ["<start ISO>"]
```

Creates the Meet event `"EOL - <product name>"` with all participants (optional ones marked
optional), the deck + Asana links, the agenda and the participant list. Then it reads the event
back and checks that every required participant is on it.

| Exit | `status` | Meaning |
|---|---|---|
| `0` | `ok` | Booked and verified |
| `5` | `partial` | Booked, but `issues` lists a gap (missing attendee, no Meet link, role with no owner) |
| `6` | `no_slot` | Not booked: no fitting slot; `alternatives` included |
| `7` | `conflict` | Not booked: the given start conflicts or is outside working hours / Mon–Thu |
| `1` | `failed` | API error; `fix` says what to do |

The script never books over a required participant's existing meeting on its own. It does so
only at a start time the PM picked, and you tell the PM who is busy then.

### Step 6 — Create the private Slack channel

```bash
python3 "$SKILL_DIR/scripts/create_slack_channel.py" /tmp/eol_input.json "<asana_url>" "<deck_url>"
```

Creates a **private** channel `#eol-<normalized-name>` and confirms with Slack that it exists
and is private. A public channel is never used. If the name is taken by a channel the token
can't see, it uses `-2`, `-3`, …; if it's the PM's own channel, it reuses it. It invites the
same participants as the invite, checks the member list from Slack's side, and posts the intro
(links, open-question count, participants).

| Exit | `status` | Meaning |
|---|---|---|
| `0` | `ok` | Private channel verified, everyone added, intro posted |
| `5` | `partial` | Channel works; `not_added` lists who couldn't be added and why |
| `1` | `failed` | No usable private channel; `error` = why, `fix` = what to do (e.g. missing `groups:write` scope, workspace restricts private channels, no Slack token) |

`token: "bot"` means the channel was created by the Slack app, not the PM's account (no
`SLACK_USER_TOKEN` is stored). Mention it in Step 7 and invite the PM. Don't silently present
it as the PM's own channel.

### Step 6b — Validate before reporting (automatic, no PM questions)

Before Step 7, check every result yourself:

| Check | Pass when |
|---|---|
| Deck | `create_deck.py` printed a deck URL |
| Asana | `submit_asana.py` printed a task URL, or an existing task was used |
| Invite | Step 5 status `ok`, and its `attendees` include every `participants` email from `eol_rules.py summary` that isn't optional |
| Slack | Step 6 status `ok`, `private_verified: true`, and `added` covers the same participants |
| Consistency | Deck Stakeholders slide = invite attendees = Slack members (all three come from `eol_rules.stakeholders`) |
| Scheduling | The booked time is Mon–Thu and inside working hours for every time zone in `local_times` |

A failed check is reported with what, why, and how to fix it. Don't retry endlessly, and don't
stop the other steps.

### Step 7 — Share all outputs

Give the PM all links in one message, then a short readout of what the deck contains so they
know what to refine. Get the lists silently with:

```bash
python3 "$SKILL_DIR/scripts/eol_rules.py" summary /tmp/eol_input.json
```

> ✅ Done! Here's your EOL kickoff package for **<name>** (<Product EOL / Feature EOL / type TBD, treated as product>):
>
> 📋 **Asana task**: [link] *(new — created from your answers)*
>    OR: 📋 **Asana task**: [`asana_task_url` from Step 1] *(existing submission used)*
>
> 🗂️ **Asana project**: [link] *(only when the request was converted to a project — also linked in Slack)*
>
> 📊 **EOL deck**: [link]
>
> 📅 **EOL kickoff meeting**: [event link] · 🎥 [Meet link]: <day, time in each participant's zone>
> *(30 min · all <n> required participants invited and verified)*
>
> 💬 **Slack channel**: [#channel-name](channel_url) *(private, verified · <n> members)*
>
> **Who's invited and why:** <one line per participant: name, role, why>
>
> **What's in the deck**
> - ✅ Known: <`known`>
> - 💡 Proposed (confirm at kickoff): <`proposed`, shortened>
> - ❓ Open for kickoff (<n>): <top 3–5 of `open_questions`> *(full list on the "Open Questions & Decisions" slide)*
>
> Slide 2 (EOL Roadmap) is a template graphic — mark where the product currently sits on the journey.
> Want to fill in any of the open items now? Just tell me and I'll update the deck.

**Only mark a line ✅ if its script returned `ok`.** For `partial` or `failed`, replace the line with
⚠️ / ❌, what happened, why, and what's needed, for example:
> ❌ **Slack channel not created**: the Slack app lacks permission to create private channels
> (`missing_scope`). Fix: add the `groups:write` scope to the app and reinstall it, or create
> `#eol-<name>` manually and invite: <emails>. The deck, invite and Asana task are ready.

Don't ask the open questions one by one here. Only update the deck if the PM volunteers answers
(re-run Step 4 with the same presentation ID, then re-share the link).

Then close the telemetry session silently: `python3 "$SKILL_DIR/scripts/obs.py" end`, and log
the completed session: `python3 "$SKILL_DIR/scripts/track_usage.py" complete "<pm_name>" "<product_name>"`

---

## Deck structure (13 slides)

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
| 9 | Technical & SKU Details | Impacted SKUs list ("None" for plain feature EOLs, TBD for products until confirmed) |
| 10 | Open Questions & Decisions | *Added.* Legend, open questions & pending decisions, proposed assumptions |
| 11 | Stakeholders & Next Steps | *Added.* Who's invited, roles to involve (by EOL type), suggested next steps |
| 12 | Q&A | Static (no changes) |
| 13 | Blank | Static (no changes) |

Slide 5 is titled *Open Opportunities* for products and *Affected Tenants / Usage* for
features without commercial impact.

---

## Requirements

- Python 3.6+
- `ASANA_ACCESS_TOKEN` — Asana personal access token, from the environment variable if set, otherwise the sealed pm-claude-code-setup Keychain vault, otherwise `~/.config/secrets/get-secret.sh` (via `scripts/vault_http.py`)
- Google + Slack credentials: `create_deck.py`, `create_calendar.py` and `create_slack_channel.py` call APIs through `scripts/vault_http.py`, which uses `GOOGLE_ACCESS_TOKEN` / `SLACK_USER_TOKEN` / `SLACK_BOT_TOKEN` env vars if set, otherwise the sealed pm-claude-code-setup Keychain vault (the token never enters the script), otherwise the legacy Cursor setup (`~/.config/secrets/get-secret.sh` for Slack, the gcloud ADC file at `~/.config/gcloud/application_default_credentials.json` for Google). Slack prefers the user token and falls back to the bot token.
- `GOOGLE_QUOTA_PROJECT` *(optional)* — GCP project to bill API quota against; defaults to `pntops` when using the vault
- `stakeholders.json` — the role map (owners, why, when each role applies, scheduling defaults). `EOL_STAKEHOLDER_FILE` can point to another copy for testing
- `EOL_REVIEW_ATTENDEES` *(optional)* — comma-separated emails **added** to the invite as required participants
- Python 3.9+ for time zones (`zoneinfo`); older Python uses fixed offsets
- Google: the approved `calendar.events` scope. Availability comes from reading each participant's calendar (`events.list`); `freeBusy` needs a broader scope that must not be requested. A calendar that isn't shared is reported as "availability unknown"
- Slack: `groups:write`, `groups:read`, `chat:write`, `users:read`, `users:read.email` (user token preferred, bot token as fallback)
- The PM (or agent) must have at least Viewer access to the EOL template so the Drive copy API succeeds

---

## Product vs. feature — what changes

| | Product EOL | Feature EOL (no commercial impact) | Feature EOL with commercial impact |
|---|---|---|---|
| SKU & pricing items | In scope; TBD until confirmed | Auto-filled "None" / "No pricing impact" (proposed) | In scope; TBD until confirmed |
| SKU & Pricing owner (see `stakeholders.json`) | Required | Not invited | Required |
| Customer impact | Customers, open opps, ARR (Salesforce) | Tenants using the feature (usage data) | Customers, open opps, ARR |
| Default communication | External Communication Request: email + in-app, Legal approval | What's New + docs; dedicated announcement only if impact is significant | External Communication Request |
| Roles suggested for kickoff | R&D, RevOps, Sales / Deal Desk, CS, Support, Marketing, Legal, Tech Writers | R&D, Support, Tech Writers, CS if strategic accounts | Feature list + RevOps, Sales / Deal Desk |
| Asana *SKU* field | Yes | No | Yes |

---

## Finding an Asana task by product name

If the PM doesn't have the task URL, use the `fetch_asana.py` command from Step 1
to search by product name. It uses the configured credential helper, so don't
call the Claude Code vault script directly.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `403 on copy_template` (exit code 4) | Script signals `AUTO_COPY_FAILED` — agent automatically uses browser automation to copy the template; PM never sees this |
| `Can't connect to Google APIs` | Neither `GOOGLE_ACCESS_TOKEN` nor the vault Google credential is available — re-run the Google Workspace connection in pm-claude-code-setup |
| `401 Unauthorized` (Google) | Access token expired — refresh `GOOGLE_ACCESS_TOKEN` and retry |
| `Can't connect to Asana` | `ASANA_ACCESS_TOKEN` is in neither the environment nor the vault — re-run the Asana connection in pm-claude-code-setup |
| Slides show old placeholder text | Some slides have multiple BODY elements; check `status_notes` keyword match in create_deck.py |
| `fetch_asana.py` returns empty | Task GID may be wrong — verify the last number in the Asana URL is the task (not the project or section) |
| `whoami.py` exits `2` | No Asana connection: add "your name and email" to the intake message |
| A role owner changed | Edit that role's `owner` in `stakeholders.json` (PM Hub PR). No other file names people |
| Calendar `no_slot` | Every required person is busy or the time zones don't overlap. Offer the `alternatives` or ask for other hours; never book over meetings silently |
| `availability_gaps` | That person's calendar isn't shared with the PM. Their availability is unknown; tell the PM |
| Slack `failed` | Read `error` / `fix`. Common causes: no Slack token; missing `groups:write`; the workspace restricts private channels |
| Slack `name_taken` | Handled automatically: reuses the PM's own channel or adds `-2` |
| Kickoff slides missing | The template's slide 9 lost its TITLE/BODY placeholders, so `add_kickoff_slides` skipped them. The 9 content slides are still populated |
