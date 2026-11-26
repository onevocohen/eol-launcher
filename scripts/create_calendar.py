#!/usr/bin/env python3
"""
create_calendar.py  —  EOL Kickoff Toolkit helper
Plans and creates the 30-minute Google Meet kickoff "EOL - <product>".

Usage:
  python3 create_calendar.py --plan <eol_input.json>
      Read-only. Resolves participants, reads each one's calendar + time zone,
      and prints the plan (proposed slot, time zones, availability gaps). Never
      books anything. Use it to decide whether to ask the PM for preferred hours.

  python3 create_calendar.py <eol_input.json> <deck_url> <asana_url> [start_iso]
      Books the first slot that fits, or the given start time after checking it.

Input JSON (on top of the deck fields):
  meeting_preference  optional {"time_zone": "...", "start": "HH:MM", "end": "HH:MM"}

Participants come from eol_rules.stakeholders(): the same list the deck shows
and the Slack channel uses. EOL_REVIEW_ATTENDEES (comma-separated emails), if
set, is ADDED to that list as required participants; it no longer replaces it.

Exit codes (always prints one JSON object on stdout):
  0  booked and verified            {"status": "ok", ...}
  5  booked, but verification found a gap (e.g. an attendee missing)  "partial"
  6  not booked: no slot fits; "alternatives" lists options          "no_slot"
  7  not booked: the given start conflicts / is outside hours        "conflict"
  1  failed (API error)                                              "failed"
"""

import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_http import google_api, ApiError  # noqa: E402
import eol_rules  # noqa: E402
import scheduling  # noqa: E402
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

CAL_API = "https://www.googleapis.com/calendar/v3"


def emit(obj, code):
    print(json.dumps(obj, default=str, ensure_ascii=False, indent=1))
    sys.exit(code)


def participants_for(d):
    st = d["_stakeholders"]
    people = [{"email": p["email"], "name": p["name"], "required": p["required"]}
              for p in st["participants"] if p["email"]]
    extra = [e.strip().lower() for e in os.environ.get("EOL_REVIEW_ATTENDEES", "").split(",") if e.strip()]
    for e in extra:
        if e not in {p["email"] for p in people}:
            people.append({"email": e, "name": e, "required": True})
    return people


def read_calendar(email, time_min, time_max):
    """Busy intervals + time zone via events.list (calendar.events scope).
    Returns (busy or None if unreadable, time_zone or None, error or None)."""
    url = (f"{CAL_API}/calendars/{quote(email)}/events?singleEvents=true&orderBy=startTime"
           f"&maxResults=250&timeMin={quote(time_min.isoformat())}&timeMax={quote(time_max.isoformat())}"
           "&fields=timeZone,items(start,end,status,transparency,eventType,attendees(self,responseStatus))")
    try:
        r = google_api(url)
    except ApiError as e:
        return None, None, f"calendar not readable ({e.status})"
    except SystemExit as e:
        return None, None, str(e)
    zone = r.get("timeZone")
    return scheduling.busy_from_events(r.get("items", []), zone or "UTC"), zone, None


def plan(d, now=None):
    cfg = eol_rules.load_stakeholder_map().get("scheduling", {})
    people = participants_for(d)
    now = now or datetime.now(timezone.utc)
    tmax = now + timedelta(days=int(cfg.get("search_working_days", 10)) * 7 // 4 + 4)
    gaps = []
    for p in people:
        busy, zone, err = read_calendar(p["email"], now, tmax)
        p["busy"], p["time_zone"] = busy, zone or cfg.get("default_time_zone")
        if err:
            gaps.append(f"{p['email']}: {err}; availability unknown")
    zones = sorted({p["time_zone"] for p in people if p["required"]})
    result = scheduling.find_slots(people, now=now, config=cfg, preference=d.get("meeting_preference"))
    return people, zones, gaps, result


def slot_view(slot):
    if not slot:
        return None
    return {"start": slot["start"].isoformat(), "local_times": slot["local"],
            **({"conflicts": slot["conflicts"]} if slot.get("conflicts") else {}),
            **({"optional_conflicts": slot["optional_conflicts"]} if slot.get("optional_conflicts") else {})}


def check_given_start(people, start, cfg):
    dur = timedelta(minutes=int(cfg.get("meeting_minutes", 30)))
    end = start + dur
    problems = []
    for p in people:
        if not p["required"]:
            continue
        z = scheduling.tz(p["time_zone"])
        if not scheduling._within_hours(start, end, z, cfg.get("working_hours", ["09:00", "17:00"]),
                                        cfg.get("meeting_days", scheduling.DAY_NAMES[:4])):
            problems.append(f"{p['email']}: outside Mon–Thu working hours ({start.astimezone(z):%a %H:%M %Z})")
        elif any(bs < end and be > start for bs, be in (p["busy"] or [])):
            problems.append(f"{p['email']}: already busy")
    return problems


def main():
    args = sys.argv[1:]
    planning = args[:1] == ["--plan"]
    if planning:
        args = args[1:]
    if (planning and len(args) != 1) or (not planning and len(args) < 3):
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    with open(args[0]) as f:
        d = eol_rules.apply(json.load(f))
    cfg = eol_rules.load_stakeholder_map().get("scheduling", {})
    people, zones, gaps, result = plan(d)
    unresolved = d["_stakeholders"]["unresolved"]
    slot = result["slots"][0] if result["slots"] else None

    if planning:
        emit({"status": "plan", "participants": [{k: p[k] for k in ("email", "required", "time_zone")} for p in people],
              "time_zones": zones, "multiple_time_zones": len(zones) > 1,
              "proposed_slot": slot_view(slot), "alternatives": [slot_view(a) for a in result["alternatives"]],
              "reason": result["reason"], "availability_gaps": gaps, "unresolved_roles": unresolved}, 0)

    deck_url, asana_url = args[1], args[2]
    if len(args) >= 4:
        start = datetime.fromisoformat(args[3])
        if start.tzinfo is None:
            start = start.replace(tzinfo=scheduling.tz(cfg.get("default_time_zone", "Asia/Jerusalem")))
        problems = check_given_start(people, start, cfg)
        if problems:
            emit({"status": "conflict", "booked": False, "requested_start": start.isoformat(),
                  "problems": problems, "proposed_slot": slot_view(slot),
                  "alternatives": [slot_view(a) for a in result["alternatives"]]}, 7)
        slot = {"start": start, "end": start + timedelta(minutes=int(cfg.get("meeting_minutes", 30))),
                "local": {p["email"]: start.astimezone(scheduling.tz(p["time_zone"])).strftime("%a %d %b %H:%M %Z")
                          for p in people}, "optional_conflicts": []}
    elif not slot:
        emit({"status": "no_slot", "booked": False, "reason": result["reason"],
              "alternatives": [slot_view(a) for a in result["alternatives"]],
              "time_zones": zones, "availability_gaps": gaps}, 6)

    product = d.get("product_name", "Product")
    st = d["_stakeholders"]
    lines = [f"• {p['name']} ({' / '.join(p['roles'])}){'' if p['required'] else ' (optional)'}"
             for p in st["participants"]]
    event = {
        "summary": f"EOL - {product}",
        "description": (
            f"EOL kickoff for {product}\n\n"
            f"📊 Deck: {deck_url}\n📋 Asana task: {asana_url}\n\n"
            f"Agenda: walk through the deck, then resolve the {len(d['_open_questions'])} open "
            f"questions and pending decisions (\"Open Questions & Decisions\" slide) and assign owners.\n\n"
            "Participants:\n" + "\n".join(lines)),
        "start": {"dateTime": slot["start"].isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": slot["end"].isoformat(), "timeZone": "UTC"},
        "attendees": [{"email": p["email"], **({} if p["required"] else {"optional": True})} for p in people],
        "conferenceData": {"createRequest": {
            "requestId": "eol-%s-%d" % ("".join(c for c in product.lower() if c.isalnum())[:30],
                                        int(datetime.now().timestamp())),
            "conferenceSolutionKey": {"type": "hangoutsMeet"}}},
        "reminders": {"useDefault": True},
    }
    try:
        created = google_api(f"{CAL_API}/calendars/primary/events?conferenceDataVersion=1&sendUpdates=all",
                             "POST", event)
    except (ApiError, SystemExit) as e:
        emit({"status": "failed", "booked": False, "error": str(e)[:500],
              "fix": "Check the Google Workspace connection (pm-claude-code-setup) and retry this step."}, 1)

    # ── Verify: read the event back and compare attendees with the plan ──────
    try:
        got = google_api(f"{CAL_API}/calendars/primary/events/{created['id']}")
    except (ApiError, SystemExit):
        got = created
    on_invite = {a.get("email", "").lower() for a in got.get("attendees", [])}
    organizer = (got.get("organizer") or {}).get("email", "").lower()
    missing = [p["email"] for p in people if p["required"] and p["email"] not in on_invite
               and p["email"] != organizer]
    meet = next((ep.get("uri", "") for ep in got.get("conferenceData", {}).get("entryPoints", [])
                 if ep.get("entryPointType") == "video"), "")
    issues = []
    if missing:
        issues.append("required participants missing from the invite: " + ", ".join(missing))
    if not meet:
        issues.append("no Google Meet link was attached")
    if unresolved:
        issues.append("roles with no owner to invite: " + "; ".join(unresolved))
    out = {"status": "partial" if issues else "ok", "booked": True,
           "event_link": got.get("htmlLink", ""), "meet_link": meet, "event_id": created["id"],
           "start": slot["start"].isoformat(), "local_times": slot["local"], "title": event["summary"],
           "attendees": sorted(on_invite | ({organizer} if organizer else set())),
           "optional_conflicts": slot.get("optional_conflicts", []),
           "availability_gaps": gaps, "issues": issues}
    emit(out, 5 if issues else 0)


if __name__ == "__main__":
    main()
