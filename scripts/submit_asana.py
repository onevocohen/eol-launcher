#!/usr/bin/env python3
"""
submit_asana.py — Create a new EOL task in the Asana "EOL - Request form" project.

Called when the PM provides EOL details through Cursor and no existing Asana
task was found. Creates the task as the system-of-record entry.

Usage:
    python3 submit_asana.py /tmp/eol_input.json

Input JSON: same schema as create_deck.py (the 16 deck fields).
Additional optional field:
    pm_name   (str) — name of the PM submitting the request

Output: prints the new Asana task URL to stdout.
"""

import json
import sys
import os
import subprocess
import urllib.request
import urllib.parse

ASANA_API       = "https://app.asana.com/api/1.0"
SECRET_SCRIPT   = os.path.expanduser("~/.config/secrets/get-secret.sh")
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


# ── Auth ─────────────────────────────────────────────────────────────────────

def get_token():
    result = subprocess.run(
        ["bash", SECRET_SCRIPT, "ASANA_ACCESS_TOKEN"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


# ── API ───────────────────────────────────────────────────────────────────────

def asana_post(path, token, body):
    data = json.dumps({"data": body}).encode()
    req  = urllib.request.Request(
        f"{ASANA_API}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp).get("data", {})
    except urllib.error.HTTPError as e:
        print(f"Asana API error {e.code}: {e.read().decode()}", file=sys.stderr)
        raise


# ── Helpers ───────────────────────────────────────────────────────────────────

def bullets(items):
    if isinstance(items, list):
        return "\n".join(f"• {item}" for item in items)
    return str(items or "")


def build_notes(d, pm_name, pm_email):
    """Build the Q&A-style notes that mirror the Asana form format."""
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
    lines.append("Please provide a description of the EOL:")
    lines.append(d.get("announcement", ""))

    # Append additional context as extra sections
    if d.get("key_dates"):
        lines.append("")
        lines.append("Key Dates:")
        lines.append(bullets(d.get("key_dates", [])))

    if d.get("rationale"):
        lines.append("")
        lines.append("Business Rationale:")
        lines.append(bullets(d.get("rationale", [])))

    if d.get("for_new_customers") or d.get("for_existing_customers"):
        lines.append("")
        lines.append("Sales Guidance:")
        if d.get("for_new_customers"):
            lines.append(f"New customers: {d['for_new_customers']}")
        if d.get("for_existing_customers"):
            lines.append(f"Existing customers: {d['for_existing_customers']}")

    if d.get("alternatives"):
        lines.append("")
        lines.append("Alternative:")
        lines.append(d["alternatives"])

    if d.get("communication"):
        lines.append("")
        lines.append("Communication Plan:")
        lines.append(d["communication"])

    return "\n".join(lines)


def map_alternative(d):
    """Map alternatives field to Asana enum option GID."""
    alt = (d.get("alternatives") or "").lower()
    skus = d.get("impacted_skus", [])

    # Infer from content
    if not alt or "no alternative" in alt or "no replacement" in alt:
        return ALT_NONE
    if "partial" in alt or "phase" in alt:
        return ALT_PARTIAL
    return ALT_FULL


def map_sku(d):
    """Map impacted_skus to Yes/No enum GID."""
    skus = d.get("impacted_skus", [])
    if isinstance(skus, list) and len(skus) > 0:
        return SKU_YES
    return SKU_NO


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 submit_asana.py <input.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    pm_name  = data.get("pm_name", "")
    pm_email = data.get("contact", "")
    product  = data.get("product_name", "EOL Request")

    print(f"Creating Asana task for \"{product}\"…", file=sys.stderr)
    token = get_token()

    # Build the task body
    notes      = build_notes(data, pm_name, pm_email)
    eol_desc   = data.get("announcement", "")
    due_on     = None  # Could be inferred from key_dates if needed

    # Extract last EOL date from key_dates for due_on
    key_dates = data.get("key_dates", [])
    if key_dates:
        import re
        # Look for a year in the last date entry
        last = key_dates[-1]
        m = re.search(r'\b(202[5-9]|203\d)\b', last)
        # Only use if we can parse a real date — skip for safety

    task_body = {
        "name":    product,
        "notes":   notes,
        "projects": [EOL_PROJECT_GID],
        "custom_fields": {
            CF_NAME:        product,
            CF_EOL_DESC:    eol_desc,
            CF_SUBMITTER:   pm_name or pm_email,
            CF_ALTERNATIVE: map_alternative(data),
            CF_STATUS:      STATUS_NEW,
            CF_SKU:         map_sku(data),
        }
    }

    task = asana_post("/tasks", token, task_body)
    task_gid = task.get("gid", "")
    task_url = f"https://app.asana.com/0/{EOL_PROJECT_GID}/{task_gid}"

    print(f"✅ Asana task created: {task_url}")
    return task_url


if __name__ == "__main__":
    main()
