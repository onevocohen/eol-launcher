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

If the request was converted to an Asana project, the output includes
asana_project_url (pass it through to create_slack_channel.py via the JSON).

Output: JSON to stdout (_asana_* keys are metadata for the AI)
"""

import json
import re
import sys
import os
import urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_http import asana_api  # noqa: E402

ASANA_API       = "https://app.asana.com/api/1.0"
EOL_PROJECT_GID = "1214130454046893"   # "EOL - Request form" project

# Known custom field GIDs for the EOL - Request form project
CF_SUBMITTER    = "1209733082440836"
CF_EOL_DESC     = "1215528244472423"
CF_ALTERNATIVE  = "1215528244472425"
CF_NAME         = "1215924922501010"
CF_STATUS       = "1215924922501012"
CF_SKU          = "1215960352578631"
CF_COMMENTS     = "1205617554352324"

CONVERTED_PREFIX = "[Converted to project]"


# ── API ───────────────────────────────────────────────────────────────────────

def get_token():
    return None  # kept for call-site compatibility; vault_http resolves auth
                 # (ASANA_ACCESS_TOKEN env var, else the sealed Keychain vault)


def asana_get(path, token):
    return asana_api(f"{ASANA_API}{path}").get("data", {})


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

    # When a request is converted to a project, Asana leaves a completed
    # "[Converted to project] <name>" stub next to the original. Treat the pair
    # as one submission: keep the stub only if no non-stub task has its name.
    live_names = {t.get("name", "").strip().lower() for t in tasks
                  if not t.get("name", "").startswith(CONVERTED_PREFIX)}
    tasks = [t for t in tasks
             if not (t.get("name", "").startswith(CONVERTED_PREFIX)
                     and strip_converted(t["name"]).lower() in live_names)]

    scored = [(score_match(t, term), t) for t in tasks]
    scored = [(s, t) for s, t in scored if s >= 2]   # require at least substring match
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def strip_converted(name):
    return name[len(CONVERTED_PREFIX):].strip() if name.startswith(CONVERTED_PREFIX) else name.strip()


# ── Converted-project lookup ──────────────────────────────────────────────────

def _ts(value):
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None


def find_converted_project(base_name, token):
    """
    Return (converted, project). converted is True if the request has a
    "[Converted to project]" stub; project is {"gid", "name", "url"} for the
    Asana project it was converted to, or None if it can't be identified.

    Asana does not link a converted request to its project. Conversion leaves a
    completed "[Converted to project] <name>" stub in the EOL project and
    creates a project named <name> seconds earlier. Match on that: same name
    (case-insensitive) and created within 10 minutes of the stub's completion.
    """
    tasks = asana_get(
        f"/projects/{EOL_PROJECT_GID}/tasks?opt_fields=name,completed_at", token)
    stubs = [t for t in (tasks if isinstance(tasks, list) else [])
             if t.get("name", "").startswith(CONVERTED_PREFIX)
             and strip_converted(t["name"]).lower() == base_name.lower()]
    if not stubs:
        return False, None

    workspace = asana_get(f"/projects/{EOL_PROJECT_GID}?opt_fields=workspace.gid",
                          token).get("workspace", {}).get("gid")
    if not workspace:
        return True, None
    query = urllib.parse.quote(base_name)
    projects = asana_get(
        f"/workspaces/{workspace}/typeahead?resource_type=project&count=20"
        f"&query={query}&opt_fields=name,created_at,permalink_url", token)

    for stub in stubs:
        done = _ts(stub.get("completed_at"))
        for p in projects if isinstance(projects, list) else []:
            if p.get("gid") == EOL_PROJECT_GID:
                continue
            if p.get("name", "").strip().lower() != base_name.lower():
                continue
            created = _ts(p.get("created_at"))
            if done and created and abs((done - created).total_seconds()) > 600:
                continue
            return True, {"gid": p["gid"], "name": p["name"],
                          "url": p.get("permalink_url")
                          or f"https://app.asana.com/0/{p['gid']}"}
    return True, None


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


def emit(task, gid, token):
    out = build_output(task, gid)
    try:
        converted, project = find_converted_project(
            strip_converted(task.get("name", "")), token)
    except Exception as e:  # never block the workflow on this lookup
        print(f"Warning: converted-project lookup failed: {e}", file=sys.stderr)
        converted, project = False, None
    out["_asana_converted_to_project"] = converted
    if converted and not project:
        print("Request was converted to a project, but the project could not be "
              "identified by name — ask the PM for its link.", file=sys.stderr)
    if project:
        print(f"Request was converted to project: {project['url']}", file=sys.stderr)
        out["asana_project_url"] = project["url"]
        out["_asana_project_name"] = project["name"]
    print(json.dumps(out, indent=2, ensure_ascii=False))


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
        emit(task, gid, token)
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
        emit(full_task, gid, token)
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
