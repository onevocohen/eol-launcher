#!/usr/bin/env python3
"""
fetch_asana.py — Pull an EOL submission from the Asana "EOL - Request form" project.

Accepts a product name, task URL, or task GID. When given a name it searches
the EOL project automatically — no URL needed.

Usage:
    python3 fetch_asana.py "Remote Access"          # search by product name
    python3 fetch_asana.py <task_url_or_gid>        # fetch directly by URL / GID

Exit codes:
    0  — success, JSON printed to stdout
    2  — no matching task found (AI should fall back to PM questions)
    3  — multiple matches found, JSON list printed to stdout (AI picks one)

Output: JSON to stdout (_asana_* keys are metadata for the AI)
"""

import json
import re
import sys
import os
import subprocess
import urllib.request

ASANA_API       = "https://app.asana.com/api/1.0"
SECRET_SCRIPT   = os.path.expanduser("~/.config/secrets/get-secret.sh")
EOL_PROJECT_GID = "1214130454046893"   # "EOL - Request form" project

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


# ── Project search ────────────────────────────────────────────────────────────

def score_match(task, term):
    """Return a match score (higher = better). 0 = no match."""
    t = term.lower()
    task_name = task.get("name", "").lower()
    name_cf   = ""
    for cf in task.get("custom_fields", []):
        if cf.get("gid") == CF_NAME:
            name_cf = (cf.get("display_value") or cf.get("text_value") or "").lower()

    # Exact match scores highest
    if t == task_name or t == name_cf:
        return 3
    # One fully contains the other
    if t in task_name or t in name_cf:
        return 2
    if task_name in t or name_cf in t:
        return 1
    # Word-level overlap
    term_words  = set(t.split())
    target_words = set((task_name + " " + name_cf).split())
    overlap = term_words & target_words
    if overlap:
        return len(overlap)
    return 0


def search_project(term, token):
    """
    Search the EOL project for tasks matching the product name.
    Returns a list of (score, task) sorted best-first.
    """
    FIELDS = (
        "name,gid,completed,"
        "custom_fields.gid,custom_fields.name,"
        "custom_fields.display_value,custom_fields.text_value"
    )
    tasks = asana_get(f"/projects/{EOL_PROJECT_GID}/tasks?opt_fields={FIELDS}", token)
    if not isinstance(tasks, list):
        tasks = []

    scored = [(score_match(t, term), t) for t in tasks]
    scored = [(s, t) for s, t in scored if s >= 2]   # require at least substring match
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


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


# ── Task fetcher ──────────────────────────────────────────────────────────────

TASK_FIELDS = (
    "name,notes,due_on,created_at,completed,"
    "custom_fields.gid,custom_fields.name,custom_fields.display_value,"
    "custom_fields.text_value,custom_fields.enum_value"
)

def fetch_task(gid, token):
    task = asana_get(f"/tasks/{gid}?opt_fields={TASK_FIELDS}", token)
    if not task or not task.get("gid"):
        return None
    return task


# ── Build output dict ─────────────────────────────────────────────────────────

def build_output(task, gid):
    notes  = task.get("notes", "")
    parsed = parse_notes(notes)

    out = {}

    out["product_name"] = (
        get_cf(task, CF_NAME)
        or parsed.get("End of life / Deprecation name", "")
        or task.get("name", "")
    ).strip()

    eol_desc = (
        get_cf(task, CF_EOL_DESC)
        or parsed.get("Please provide a description of the EOL", "")
    ).strip()
    if eol_desc:
        paras = [p.strip() for p in eol_desc.split("\n\n") if p.strip()]
        out["announcement"] = paras[0] if paras else eol_desc

    submitter_email = parsed.get("What is your email address", "").strip()
    if submitter_email:
        out["contact"] = submitter_email

    status = get_cf(task, CF_STATUS)
    if status and status not in ("New", ""):
        out["status_notes"] = status

    alt_value = get_cf(task, CF_ALTERNATIVE)
    alt_map   = {
        "Yes, we have full alternative": "full",
        "No, we don't have alternative": "none",
        "We have partial alternative":   "partial",
    }
    out["_asana_alternative_flag"] = alt_map.get(alt_value, "")
    out["_asana_has_skus"]         = get_cf(task, CF_SKU)
    out["_asana_submitter"]        = get_cf(task, CF_SUBMITTER) or parsed.get("Who are you", "")
    out["_asana_comments"]         = get_cf(task, CF_COMMENTS)
    out["_asana_due_on"]           = task.get("due_on", "")
    out["_asana_status"]           = get_cf(task, CF_STATUS)
    out["_asana_full_description"] = eol_desc
    out["_asana_task_gid"]         = gid
    out["_asana_task_name"]        = task.get("name", "")

    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fetch_asana.py \"<product name or task URL/GID>\"",
              file=sys.stderr)
        sys.exit(1)

    arg   = sys.argv[1].strip()
    token = get_token()

    # ── Route: URL / bare GID → fetch directly ────────────────────────────────
    gid = extract_gid(arg)
    if gid:
        print(f"Fetching Asana task {gid}…", file=sys.stderr)
        task = fetch_task(gid, token)
        if not task:
            print(f"Task {gid} not found or not accessible.", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(build_output(task, gid), indent=2, ensure_ascii=False))
        return

    # ── Route: product name → search project ─────────────────────────────────
    print(f"Searching EOL project for \"{arg}\"…", file=sys.stderr)
    results = search_project(arg, token)

    if not results:
        print(f"No Asana task found matching \"{arg}\".", file=sys.stderr)
        print("Proceeding without Asana data — PM will be asked for all fields.",
              file=sys.stderr)
        sys.exit(2)

    if len(results) == 1 or results[0][0] > results[1][0] + 1:
        # Clear single best match
        score, task = results[0]
        gid  = task["gid"]
        print(f"Found: \"{task['name']}\" (GID {gid}, score {score})", file=sys.stderr)
        full_task = fetch_task(gid, token)
        if not full_task:
            sys.exit(2)
        print(json.dumps(build_output(full_task, gid), indent=2, ensure_ascii=False))
        return

    # Multiple close matches — let the AI pick
    print(f"Multiple matches found for \"{arg}\":", file=sys.stderr)
    matches = []
    for score, task in results[:5]:
        print(f"  [{score}] {task['name']} (GID {task['gid']})", file=sys.stderr)
        matches.append({"gid": task["gid"], "name": task["name"],
                        "completed": task.get("completed", False)})
    print(json.dumps({"_asana_multiple_matches": matches}, indent=2))
    sys.exit(3)

if __name__ == "__main__":
    main()
