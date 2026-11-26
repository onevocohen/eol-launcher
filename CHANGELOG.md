# Changelog

One section per release, newest first. The first line under each heading is shown to PMs when they get the update.

## 1.4.0 — 2026-11-26

Reliable execution: role-based stakeholders, real calendar availability across time zones, a verified private Slack channel, and honest status for every step.

- Stakeholders are roles in `stakeholders.json` (owner, why, when). No person is hardcoded in the logic; when a role changes hands, edit one file
- People the PM names (e.g. a responsible owner) now reach the calendar invite, not just Slack. The invite is checked against the deck's participant list after booking
- Scheduling: Mon–Thu only, each person's own time zone and working hours, real availability read from their calendars, never books over meetings; offers alternatives when nothing fits; asks for preferred hours only when people span time zones
- Slack: private channel confirmed with Slack; handles a taken name without failing; members confirmed from Slack's side; clear reason and fix when it can't be created
- Every step returns ok / partial / failed and the summary only marks confirmed steps as done
- Fixes: Israel time was a fixed UTC+3 (an hour off in winter); Sunday was allowed; a failed availability check silently booked 09:00 next day

## 1.3.0 — 2026-11-26

Faster kickoff: a few questions in one message, "TBD" welcome, and the deck is built right away with open questions for the kickoff meeting.

- Replaces the one-question-at-a-time interview with a single free-text intake (name + product/feature, timeline, why + replacement) and at most one follow-up
- Identifies the PM from their Asana connection instead of asking for a name
- Product vs. feature logic: products always include SKU, pricing and Amir; features skip them unless there's commercial impact
- "Don't know yet" / "TBD" no longer block the deck. Items are marked Known, Proposed or TBD
- Two new slides: Open Questions & Decisions; Stakeholders & Next Steps
- Fixes: the calendar invite no longer adds Amir to plain feature EOLs; Asana no longer records an undecided alternative as "full alternative" or unknown product SKUs as "No"

## 1.2.0 — 2026-11-25

Makes the skill installable and discoverable in Cursor and Claude Code on macOS and Windows. Windows API automation is not yet supported.

- Adds install instructions for both clients on macOS/Linux and Windows
- Fixes Claude Code telemetry detection for Windows paths

## 1.1.0 — 2026-11-18

Adds automatic updates: the skill now checks PM Hub on start and updates itself.

## 1.0.0

First tracked version.
