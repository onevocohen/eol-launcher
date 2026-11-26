#!/usr/bin/env python3
"""
scheduling.py — Find a kickoff slot that works for every required participant.

Pure logic (no network) so it can be tested offline. create_calendar.py feeds it
each participant's busy intervals and time zone, read with the approved
calendar.events scope (events.list on the participant's calendar). freeBusy
needs a broader calendar scope that this setup must not request.

Rules (defaults from stakeholders.json -> "scheduling"):
  * Mon–Thu only, in EVERY required participant's own time zone.
  * Inside each required participant's working hours (default 09:00–17:00).
  * Never overlaps a busy block of a required participant. Optional
    participants don't block a slot; conflicts are reported instead.
  * A participant whose calendar can't be read is "unknown", never "free":
    the slot is still allowed, and the gap is reported.
  * Optional PM preference: a time window in a stated time zone.
  * When nothing fits, return alternatives (best partial slots) and book nothing.
"""

from datetime import datetime, timedelta, time, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def tz(name):
    if ZoneInfo:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    # Fallback: fixed offsets for the two common zones (DST not modelled)
    return timezone(timedelta(hours={"Asia/Jerusalem": 2, "America/New_York": -5}.get(name, 0)))


def _hm(s):
    h, m = s.split(":")
    return time(int(h), int(m))


def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def busy_from_events(items, time_zone="UTC"):
    """Calendar events.list items -> [(start, end)] busy intervals.
    Skips free/transparent, cancelled and declined events. All-day events
    count as busy for the whole day only when they are opaque (e.g. OOO)."""
    out = []
    for ev in items or []:
        if ev.get("status") == "cancelled" or ev.get("transparency") == "transparent":
            continue
        if ev.get("eventType") == "workingLocation":
            continue
        declined = any(a.get("self") and a.get("responseStatus") == "declined"
                       for a in ev.get("attendees", []))
        if declined:
            continue
        s, e = ev.get("start", {}), ev.get("end", {})
        if "dateTime" in s:
            out.append((parse_dt(s["dateTime"]), parse_dt(e["dateTime"])))
        elif "date" in s:  # all-day
            z = tz(time_zone)
            ds = datetime.fromisoformat(s["date"]).replace(tzinfo=z)
            de = datetime.fromisoformat(e["date"]).replace(tzinfo=z)
            out.append((ds, de))
    return out


def _within_hours(start, end, zone, hours, days):
    ls, le = start.astimezone(zone), end.astimezone(zone)
    if DAY_NAMES[ls.weekday()] not in days or ls.date() != le.date():
        return False
    return _hm(hours[0]) <= ls.time() and le.time() <= _hm(hours[1])


def find_slots(participants, now=None, config=None, preference=None, want=1, alternatives=3):
    """
    participants: [{"email", "required": bool, "time_zone": str,
                    "busy": [(start, end)] or None (calendar not readable)}]
    preference:   optional {"time_zone": "Asia/Jerusalem", "start": "10:00", "end": "13:00"}
    Returns {"slots": [...], "alternatives": [...], "unknown": [...], "reason": str}
      slot = {"start", "end", "local": {email: "Mon 10:00 IST"}, "optional_conflicts": [...]}
    """
    cfg = {"meeting_minutes": 30, "meeting_days": DAY_NAMES[:4],
           "working_hours": ["09:00", "17:00"], "search_working_days": 10,
           "default_time_zone": "Asia/Jerusalem"}
    cfg.update(config or {})
    dur = timedelta(minutes=int(cfg["meeting_minutes"]))
    days, hours = cfg["meeting_days"], cfg["working_hours"]
    now = now or datetime.now(timezone.utc)

    required = [p for p in participants if p.get("required")]
    optional = [p for p in participants if not p.get("required")]
    unknown = [p["email"] for p in participants if p.get("busy") is None]
    for p in participants:
        p["_tz"] = tz(p.get("time_zone") or cfg["default_time_zone"])
    pref_tz = tz(preference["time_zone"]) if preference and preference.get("time_zone") else None

    def busy_overlap(p, s, e):
        return any(bs < e and be > s for bs, be in (p.get("busy") or []))

    # Candidate starts: every 30 min from the next working day (organizer zone), in UTC.
    base_tz = tz(cfg["default_time_zone"])
    first = (now.astimezone(base_tz) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    horizon_days = int(cfg["search_working_days"]) * 7 // 4 + 3
    slots, near = [], []
    t = first.astimezone(timezone.utc)
    end_search = t + timedelta(days=horizon_days)
    while t < end_search and len(slots) < want:
        s, e = t, t + dur
        t += timedelta(minutes=30)
        if pref_tz and not (_hm(preference["start"]) <= s.astimezone(pref_tz).time()
                            and e.astimezone(pref_tz).time() <= _hm(preference["end"])):
            continue
        out_of_hours = [p["email"] for p in required
                        if not _within_hours(s, e, p["_tz"], hours, days)]
        if out_of_hours:
            continue
        conflicts = [p["email"] for p in required if busy_overlap(p, s, e)]
        local = {p["email"]: s.astimezone(p["_tz"]).strftime("%a %d %b %H:%M %Z") for p in participants}
        if conflicts:
            near.append({"start": s, "end": e, "local": local, "conflicts": conflicts})
            continue
        slots.append({"start": s, "end": e, "local": local,
                      "optional_conflicts": [p["email"] for p in optional if busy_overlap(p, s, e)]})

    if slots:
        return {"slots": slots, "alternatives": [], "unknown": unknown, "reason": ""}

    # No slot for everyone: propose the slots with the fewest required conflicts.
    near.sort(key=lambda x: (len(x["conflicts"]), x["start"]))
    seen, alts = set(), []
    for n in near:
        day = n["start"].date()
        if (day, len(n["conflicts"])) in seen:
            continue
        seen.add((day, len(n["conflicts"])))
        alts.append(n)
        if len(alts) >= alternatives:
            break
    zones = sorted({p.get("time_zone") or cfg["default_time_zone"] for p in required})
    reason = ("No 30-minute slot in the next %s working days where every required participant "
              "is free, Mon–Thu, inside everyone's working hours%s (time zones: %s)."
              % (cfg["search_working_days"], " and your preferred hours" if preference else "",
                 ", ".join(zones)))
    if not near:
        reason += " There is no overlap of working hours at all; widen the hours or pick a time manually."
    return {"slots": [], "alternatives": alts, "unknown": unknown, "reason": reason}
