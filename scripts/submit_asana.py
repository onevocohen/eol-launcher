#!/usr/bin/env python3
"""
submit_asana.py — Create a new EOL task in the Asana "EOL - Request form" project.

Called when the PM provides EOL details through Cursor and no existing Asana
task was found. Creates the task as the system-of-record entry.

Usage:
    python3 submit_asana.py /tmp/eol_input.json

Input JSON: same schema as create_deck.py. Missing / TBD fields are allowed:
only known answers are written as facts; the rest go under open questions.
Additional optional field:
    pm_name   (str) — name of the PM submitting the request

Output: prints the new Asana task URL to stdout.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_http import ApiError, asana_api  # noqa: E402
import eol_rules  # noqa: E402

ASANA_API       = "https://app.asana.com/api/1.0"
EOL_PROJECT_GID = "1214130454046893"

# Custom field GIDs
CF_SUBMITTER   = "1209733082440836"
CF_EOL_DESC    = "1215528244472423"
CF_ALTERNATIVE = "1215528244472425"
CF_NAME        = "1215924922501010"
CF_STATUS      = "1215924922501012"
CF_SKU         = "1215960352578631"
CF_COMMENTS    = "1205617554352324"

# Enum option GIDs
ALT_FULL    = "1215528244472426"   # "Yes, we have full alternative"
ALT_NONE    = "1215528244472427"   # "No, we don't have alternative"
ALT_PARTIAL = "1215528244472428"   # "We have partial alternative"
STATUS_NEW  = "1215924922501016"   # "New"
SKU_YES     = "1215960352578632"   # "Yes"
SKU_NO      = "1215960352578633"   # "No"


# ── API ───────────────────────────────────────────────────────────────────────

def get_token():
    return None  # kept for call-site compatibility; vault_http resolves auth
                 # (ASANA_ACCESS_TOKEN env var, else the sealed Keychain vault)


def asana_post(path, token, body):
    try:
        return asana_api(f"{ASANA_API}{path}", "POST", {"data": body}).get("data", {})
    except ApiError as e:
        print(f"Asana API error {e.status}: {e.body}", file=sys.stderr)
        raise


# ── Helpers ───────────────────────────────────────────────────────────────────

def bullets(items):
    if isinstance(items, list):
        return "\n".join(f"• {item}" for item in items)
    return str(items or "")


def build_notes(d, pm_name, pm_email):
    """Build the Q&A-style notes that mirror the Asana form format.
    Only known answers go in the main sections; proposed defaults and open
    questions are listed separately so the record never shows guesses as facts."""
    status = d.get("_status") or {}
    known = lambda f: status.get(f, "known") == "known" and not eol_rules.is_unknown(d.get(f))  # noqa: E731
    lines = []
    lines.append("Who are you?:")
    lines.append(pm_name or d.get("contact", ""))
    lines.append("")
    lines.append("What is your email address?:")
    lines.append(pm_email or d.get("contact", ""))
    lines.append("")
    lines.append("End of life / Deprecation name:")
    lines.append(d.get("product_name", ""))
    lines.append("")
    lines.append("EOL type:")
    kind = eol_rules.eol_type(d).capitalize()
    if eol_rules.eol_type(d) == "feature":
        kind += " (commercial impact)" if eol_rules.is_commercial(d) else " (no SKU / pricing impact)"
    lines.append(kind)
    lines.append("")
    lines.append("Please provide a description of the EOL:")
    lines.append(d.get("announcement", ""))

    sections = [("key_dates", "Key Dates"), ("rationale", "Business Rationale"),
                ("alternatives", "Alternative"), ("communication", "Communication Plan")]
    for field, title in sections:
        if known(field):
            lines += ["", f"{title}:", eol_rules.bullets(d[field])]
    if known("for_new_customers") or known("for_existing_customers"):
        lines += ["", "Sales Guidance:"]
        if known("for_new_customers"):
            lines.append(f"New customers: {d['for_new_customers']}")
        if known("for_existing_customers"):
            lines.append(f"Existing customers: {d['for_existing_customers']}")

    if d.get("_assumptions"):
        lines += ["", "Proposed assumptions (to confirm at kickoff):",
                  eol_rules.bullets(d["_assumptions"])]
    if d.get("_open_questions"):
        lines += ["", "Open questions for the EOL kickoff:",
                  eol_rules.bullets(d["_open_questions"])]

    return "\n".join(lines)


def map_alternative(d):
    """Map alternatives to the Asana enum. Unknown -> None (field left empty,
    so the form never claims a replacement exists before it's decided)."""
    alt = d.get("alternatives")
    if eol_rules.is_unknown(alt) or (d.get("_status") or {}).get("alternatives") == "open":
        return None
    text = str(alt).lower()
    if eol_rules.no_alternative(alt):
        return ALT_NONE
    if "partial" in text:
        return ALT_PARTIAL
    return ALT_FULL


def map_sku(d):
    """Map SKU impact to the Yes/No enum.
    Product EOLs and commercial feature EOLs -> Yes, even when the codes are
    still TBD (the codes are an open question, not a "No"). Plain feature -> No."""
    return SKU_YES if eol_rules.is_commercial(d) else SKU_NO


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 submit_asana.py <input.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = eol_rules.apply(json.load(f))

    pm_name  = data.get("pm_name", "")
    pm_email = data.get("contact", "")
    product  = data.get("product_name", "EOL Request")

    print(f"Creating Asana task for \"{product}\"…", file=sys.stderr)
    token = get_token()

    # Build the task body
    notes      = build_notes(data, pm_name, pm_email)
    eol_desc   = data.get("announcement", "")
    task_body = {
        "name":    product,
        "notes":   notes,
        "projects": [EOL_PROJECT_GID],
        "custom_fields": {
            CF_NAME:        product,
            CF_EOL_DESC:    eol_desc,
            CF_SUBMITTER:   pm_name or pm_email,
            CF_STATUS:      STATUS_NEW,
            CF_SKU:         map_sku(data),
        }
    }

    alternative = map_alternative(data)
    if alternative:
        task_body["custom_fields"][CF_ALTERNATIVE] = alternative

    task = asana_post("/tasks", token, task_body)
    task_gid = task.get("gid", "")
    task_url = f"https://app.asana.com/0/{EOL_PROJECT_GID}/{task_gid}"

    print(f"✅ Asana task created: {task_url}")
    return task_url


if __name__ == "__main__":
    main()
