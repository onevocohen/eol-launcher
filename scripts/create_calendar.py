#!/usr/bin/env python3
"""
create_calendar.py  —  EOL Launcher helper
Creates a 30-minute Google Meet calendar invite titled "EOL - <product>"
and sends it to the fixed EOL review attendees.

Usage:
  python3 create_calendar.py <eol_input.json> <deck_url> <asana_url> [start_datetime]

  start_datetime: ISO 8601 with offset, e.g. "2026-10-08T09:00:00+03:00"
                  Defaults to next Israel working-day at 09:00 (Sun–Thu, UTC+3).

Outputs: calendar event HTML link + Google Meet URL
"""

import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_http import google_api, ApiError  # noqa: E402
from datetime import datetime, timedelta, timezone

# ── helpers ────────────────────────────────────────────────────────────────────

IL_TZ = timezone(timedelta(hours=3))   # Israel Standard / Daylight (approx)


def get_fixed_attendees():
    """Read EOL_REVIEW_ATTENDEES env var (comma-separated emails) and return a list."""
    val = os.environ.get("EOL_REVIEW_ATTENDEES", "").strip()
    return [e.strip() for e in val.split(",") if e.strip()]

def next_il_working_slot(from_dt=None):
    """Return the next 09:00 Israel time on a working day (Sun–Thu)."""
    now = from_dt or datetime.now(IL_TZ)
    # Advance to next calendar day
    candidate = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now >= candidate:
        candidate += timedelta(days=1)
    # 0=Mon … 6=Sun; Israel works Mon-Thu (0-3) + Sun (6)
    while candidate.weekday() not in (0, 1, 2, 3, 6):
        candidate += timedelta(days=1)
    return candidate

def get_token():
    return None  # kept for call-site compatibility; vault_http resolves auth

def freebusy_query(token, attendees, time_min, time_max):
    """Return a dict {email: [{'start':…,'end':…}, …]} of busy blocks.
    Returns None if the API returns 403 (insufficient scope)."""
    try:
        result = google_api("https://www.googleapis.com/calendar/v3/freeBusy", "POST", {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items":   [{"id": a} for a in attendees],
        })
        return {
            email: cal.get("busy", [])
            for email, cal in result.get("calendars", {}).items()
        }
    except ApiError as e:
        if e.status == 403:
            return None   # scope insufficient — caller falls back to default slot
        raise

def find_first_free_slot(busy_by_email, attendees, duration_min=30):
    """Scan working-day slots 09:00–17:00 IL and return the first 30-min window
    where all attendees are free. Returns a datetime (IL tz) or None."""
    slot_len = timedelta(minutes=duration_min)
    # Flatten all busy intervals into one list (UTC)
    all_busy = []
    for email in attendees:
        for b in busy_by_email.get(email, []):
            s = datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
            e = datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
            all_busy.append((s, e))

    # Check every 30-min slot over the next 7 working days
    now_il = datetime.now(IL_TZ)
    candidate = next_il_working_slot(now_il)
    for _ in range(7 * 16):  # up to 7 days, 8 slots/day
        # Working-hours guard (09:00–17:00 IL)
        if candidate.hour < 9:
            candidate = candidate.replace(hour=9, minute=0)
        if candidate.hour >= 17 or (candidate.hour == 16 and candidate.minute > 30):
            # advance to next working day 09:00
            candidate = next_il_working_slot(candidate.replace(hour=17))
            continue
        end_candidate = candidate + slot_len
        # Check collision
        conflict = any(
            s < end_candidate and e > candidate
            for s, e in all_busy
        )
        if not conflict:
            return candidate
        candidate += slot_len
    return None   # give up — use default

# ── main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 4:
        print("Usage: create_calendar.py <eol_input.json> <deck_url> <asana_url> [start_datetime]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        d = json.load(f)

    deck_url   = sys.argv[2]
    asana_url  = sys.argv[3]
    product    = d.get("product_name", "Product")
    pm_email   = d.get("contact", "")
    pm_name    = d.get("pm_name", "")

    token = get_token()

    # ── resolve start time ──
    if len(sys.argv) >= 5:
        start = datetime.fromisoformat(sys.argv[4])
    else:
        # Try FreeBusy first; fall back to next working slot at 09:00
        fixed_attendees = get_fixed_attendees()
        all_attendees = list(set(fixed_attendees + ([pm_email] if pm_email else [])))
        search_start = next_il_working_slot()
        search_end   = search_start + timedelta(days=7)
        busy = freebusy_query(token, all_attendees, search_start, search_end)
        if busy is not None:
            start = find_first_free_slot(busy, all_attendees) or search_start
        else:
            # FreeBusy not available (scope) — use next working-day 09:00
            start = next_il_working_slot()

    end = start + timedelta(minutes=30)

    # Ensure tz-aware
    if start.tzinfo is None:
        start = start.replace(tzinfo=IL_TZ)
    if end.tzinfo is None:
        end = end.replace(tzinfo=IL_TZ)

    # ── build attendee list ──
    attendee_emails = set(get_fixed_attendees())
    if pm_email:
        attendee_emails.add(pm_email)

    # ── create event ──
    event = {
        "summary": f"EOL - {product}",
        "description": (
            f"EOL Package for {product}\n\n"
            f"📊 Deck: {deck_url}\n"
            f"📋 Asana task: {asana_url}"
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Jerusalem"},
        "end":   {"dateTime": end.isoformat(),   "timeZone": "Asia/Jerusalem"},
        "attendees": [{"email": e} for e in sorted(attendee_emails)],
        "conferenceData": {
            "createRequest": {
                "requestId": f"eol-{product.lower().replace(' ', '-')}-001",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {"useDefault": True},
    }

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1&sendUpdates=all"
    try:
        result = google_api(url, "POST", event)
    except ApiError as e:
        print(f"ERROR creating calendar event: {e.status} {e.body}", file=sys.stderr)
        sys.exit(1)

    html_link = result.get("htmlLink", "")
    meet_link = ""
    for ep in result.get("conferenceData", {}).get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            meet_link = ep.get("uri", "")

    print(json.dumps({
        "event_link": html_link,
        "meet_link":  meet_link,
        "start":      start.isoformat(),
        "title":      event["summary"],
    }))

if __name__ == "__main__":
    main()
