#!/usr/bin/env python3
"""
fetch_asana.py — Pull an EOL submission from the Asana "EOL - Request form" project.

Accepts a task URL or GID, fetches all fields, and outputs a partial JSON
with deck fields pre-populated from Asana data. _asana_* keys are metadata
for the AI — strip them before passing to create_deck.py.

Usage:
    python3 fetch_asana.py <task_url_or_gid>

Output: JSON to stdout
"""

import json
import re
import sys
import os
import subprocess
import urllib.request

ASANA_API     = "https://app.asana.com/api/1.0"
SECRET_SCRIPT = os.path.expanduser("~/.config/secrets/get-secret.sh")

# Known custom field GIDs for the EOL - Request form project
CF_SUBMITTER    = "1209733082440836"
CF_EOL_DESC     = "1215528244472423"
CF_ALTERNATIVE  = "1215528244472425"
CF_NAME         = "1215924922501010"
CF_STATUS       = "1215924922501012"
CF_SKU          = "1215960352578631"
CF_COMMENTS     = "1205617554352324"


# ── Auth ─────────────────────────────────────────────────────────────────────

def get_token():
    result = subprocess.run(
        ["bash", SECRET_SCRIPT, "ASANA_ACCESS_TOKEN"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


# ── API ───────────────────────────────────────────────────────────────────────

def asana_get(path, token):
    req = urllib.request.Request(
        f"{ASANA_API}{path}",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp).get("data", {})


# ── URL / GID parsing ─────────────────────────────────────────────────────────

def extract_gid(raw):
    """Return task GID from a URL or a bare GID string.

    Asana URL shapes:
      .../project/<proj>/list/<task_gid>
      .../0/<proj>/<task_gid>
    Strategy: prefer the segment after /list/; otherwise take the LAST
    long numeric segment in the URL.
    """
    raw = raw.strip().rstrip('/')

    # Explicit /list/<gid> pattern (new Asana URL format)
    m = re.search(r'/list/(\d+)', raw)
    if m:
        return m.group(1)

    # Fallback: all long numeric segments, take the last one
    all_ids = re.findall(r'/(\d{10,})', raw)
    if all_ids:
        return all_ids[-1]

    # Bare number
    if re.match(r'^\d+$', raw):
        return raw

    return None


# ── Notes parser ──────────────────────────────────────────────────────────────

def parse_notes(notes: str) -> dict:
    """
    Parse the structured Q&A block written by the Asana form into a dict.
    Format:
        Question label:
        Answer text (possibly multi-line)
    """
    result = {}
    if not notes:
        return result

    lines    = notes.splitlines()
    cur_key  = None
    cur_val  = []

    for line in lines:
        stripped = line.strip()
        # A label line: short, ends with ":", not a URL, not blank
        is_label = (
            stripped.endswith(':')
            and len(stripped) <= 100
            and not stripped.startswith('http')
            and stripped != ':'
        )
        if is_label:
            if cur_key is not None:
                result[cur_key] = '\n'.join(cur_val).strip()
            cur_key  = stripped[:-1].strip()   # strip trailing ":"
            cur_val  = []
        elif cur_key is not None:
            cur_val.append(line)

    if cur_key is not None:
        result[cur_key] = '\n'.join(cur_val).strip()

    return result


# ── Field extraction ──────────────────────────────────────────────────────────

def get_cf(task, gid):
    """Return the display value of a custom field by GID, or ''."""
    for cf in task.get("custom_fields", []):
        if cf.get("gid") == gid:
            return (
                cf.get("display_value")
                or cf.get("text_value")
                or (cf.get("enum_value") or {}).get("name")
                or ""
            )
    return ""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fetch_asana.py <task_url_or_gid>", file=sys.stderr)
        sys.exit(1)

    gid = extract_gid(sys.argv[1])
    if not gid:
        print(f"Could not extract task GID from: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching Asana task {gid}…", file=sys.stderr)
    token = get_token()
    task  = asana_get(
        f"/tasks/{gid}"
        "?opt_fields=name,notes,due_on,created_at,completed,"
        "custom_fields.gid,custom_fields.name,custom_fields.display_value,"
        "custom_fields.text_value,custom_fields.enum_value",
        token
    )

    if not task or not task.get("gid"):
        print(f"Task {gid} not found or not accessible.", file=sys.stderr)
        sys.exit(1)

    notes  = task.get("notes", "")
    parsed = parse_notes(notes)

    # ── Map to deck fields ────────────────────────────────────────────────────
    out = {}

    # product_name
    out["product_name"] = (
        get_cf(task, CF_NAME)
        or parsed.get("End of life / Deprecation name", "")
        or task.get("name", "")
    ).strip()

    # announcement — first paragraph of EOL description
    eol_desc = (
        get_cf(task, CF_EOL_DESC)
        or parsed.get("Please provide a description of the EOL", "")
    ).strip()
    if eol_desc:
        paras = [p.strip() for p in eol_desc.split("\n\n") if p.strip()]
        out["announcement"] = paras[0] if paras else eol_desc

    # contact — submitter email from notes
    submitter_email = parsed.get("What is your email address", "").strip()
    if submitter_email:
        out["contact"] = submitter_email

    # status_notes — from Status CF
    status = get_cf(task, CF_STATUS)
    if status and status not in ("New", ""):
        out["status_notes"] = status

    # ── Asana metadata (AI uses these to ask smarter follow-up questions) ─────
    alt_value = get_cf(task, CF_ALTERNATIVE)
    alt_map   = {
        "Yes, we have full alternative": "full",
        "No, we don't have alternative": "none",
        "We have partial alternative":   "partial",
    }
    out["_asana_alternative_flag"] = alt_map.get(alt_value, "")
    out["_asana_has_skus"]         = get_cf(task, CF_SKU)          # "Yes" / "No"
    out["_asana_submitter"]        = get_cf(task, CF_SUBMITTER) or parsed.get("Who are you", "")
    out["_asana_comments"]         = get_cf(task, CF_COMMENTS)
    out["_asana_due_on"]           = task.get("due_on", "")
    out["_asana_status"]           = get_cf(task, CF_STATUS)
    out["_asana_full_description"] = eol_desc                       # full text for AI to mine
    out["_asana_task_gid"]         = gid
    out["_asana_task_name"]        = task.get("name", "")

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
