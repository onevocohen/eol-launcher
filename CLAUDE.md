# Project instructions

This repository automates an EOL kickoff workflow. `SKILL.md` describes the workflow; `scripts/` contains the Asana, Google Slides/Calendar, Slack, and usage-tracking integrations. Scripts exchange EOL data as JSON and use Python's standard library.

## Build, test, and run

- Requires Python 3.6+; no dependency installation or build step is configured.
- Syntax check: `python3 -m py_compile scripts/*.py`
- Unit tests: `python3 -m unittest discover -s scripts/tests` (offline; no live calls).
- Run the workflow by following `SKILL.md`. It invokes live external services; do not run it as a test.

## Conventions

- Keep script inputs and outputs compatible with the JSON fields in `SKILL.md`.
- Keep workflow instructions in `SKILL.md` and integration behavior in the corresponding script.
- Use `scripts/track_usage.py` for usage logging and generated README statistics; do not hand-edit generated statistics.

## Never

- Never hard-code, log, or commit credentials; use the documented environment variables.
- Never invent missing EOL details. Ask only the few blocking intake questions in `SKILL.md`; anything else unknown becomes an open question in the deck (see `scripts/eol_rules.py`).
- Never create an Asana task when an existing matching task is being used.
- Never trigger live Asana, Google, or Slack actions as a test or without user authorization.
