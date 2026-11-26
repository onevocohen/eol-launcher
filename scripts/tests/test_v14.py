"""1.4.0: role-based stakeholders, scheduling, calendar + Slack verification.
All offline: Google/Slack calls are replaced with fakes."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eol_rules  # noqa: E402
import scheduling  # noqa: E402
import create_calendar  # noqa: E402
import create_slack_channel  # noqa: E402

UTC = timezone.utc
# Wed 25 Nov 2026, 08:00 UTC -> search starts Thu 26 Nov
NOW = datetime(2026, 11, 25, 8, 0, tzinfo=UTC)
CFG = {"meeting_minutes": 30, "meeting_days": ["Mon", "Tue", "Wed", "Thu"],
       "working_hours": ["09:00", "17:00"], "search_working_days": 10,
       "default_time_zone": "Asia/Jerusalem"}

BASE = {"product_name": "Legacy Vault Appliance", "eol_type": "product",
        "pm_name": "Dana PM", "contact": "dana@example.com"}


def p(email, tzname="Asia/Jerusalem", busy=(), required=True):
    return {"email": email, "required": required, "time_zone": tzname,
            "busy": None if busy is None else list(busy)}


# ── Role-based stakeholders ───────────────────────────────────────────────────

class RoleBasedStakeholders(unittest.TestCase):
    def test_no_person_is_hardcoded_in_logic(self):
        src = Path(eol_rules.__file__).read_text()
        for name in ("Amir", "Yael", "Orit", "aaviad", "ygershongob", "onevocohen"):
            self.assertNotIn(name, src, name)

    def test_every_participant_has_a_reason(self):
        d = eol_rules.apply(BASE)
        for person in d["_stakeholders"]["participants"]:
            self.assertTrue(person["why"].strip(), person)
        for role in d["_stakeholders"]["suggested"]:
            self.assertTrue(role["why"].strip(), role)

    def test_owner_change_is_one_edit_in_the_map(self):
        smap = json.loads(Path(eol_rules.STAKEHOLDER_FILE).read_text())
        for r in smap["roles"]:
            if r["id"] == "sku_pricing":
                r["owner"] = {"name": "New Pricing Owner", "email": "new.pricing@example.com"}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(smap, f)
        try:
            with patch.object(eol_rules, "STAKEHOLDER_FILE", f.name):
                d = eol_rules.apply(BASE)
                emails = eol_rules.participant_emails(d)
                self.assertIn("new.pricing@example.com", emails)
                self.assertNotIn("aaviad@paloaltonetworks.com", emails)
                # feature without commercial impact: the role (whoever owns it) is not invited
                f2 = eol_rules.apply(dict(BASE, eol_type="feature"))
                self.assertNotIn("new.pricing@example.com", eol_rules.participant_emails(f2))
        finally:
            os.unlink(f.name)

    def test_pm_named_owner_for_a_role_is_required_and_invited(self):
        """The Yanai bug: an owner the PM names must reach the invite."""
        d = eol_rules.apply(dict(BASE, stakeholders=[
            {"name": "Yanai Owner", "email": "yanai@example.com", "role": "rd_lead"}]))
        yanai = next(x for x in d["_stakeholders"]["participants"] if x["email"] == "yanai@example.com")
        self.assertTrue(yanai["required"])
        self.assertIn("R&D lead", yanai["roles"])
        self.assertIn("yanai@example.com", eol_rules.participant_emails(d, required_only=True))
        self.assertNotIn("R&D lead", [r["role"] for r in d["_stakeholders"]["suggested"]])

    def test_named_owner_overrides_default_role_owner_for_this_eol(self):
        d = eol_rules.apply(dict(BASE, stakeholders=[
            {"name": "Deputy", "email": "deputy@example.com", "role": "sku_pricing"}]))
        emails = eol_rules.participant_emails(d)
        self.assertIn("deputy@example.com", emails)
        self.assertNotIn("aaviad@paloaltonetworks.com", emails)

    def test_missing_owner_email_is_reported_not_dropped(self):
        d = eol_rules.apply(dict(BASE, stakeholders=[{"name": "No Email", "role": "rd_lead"}]))
        self.assertTrue(any("R&D lead" in u for u in d["_stakeholders"]["unresolved"]))


# ── Scheduling ────────────────────────────────────────────────────────────────

class Scheduling(unittest.TestCase):
    def test_monday_to_thursday_only(self):
        r = scheduling.find_slots([p("a@x.com")], now=NOW, config=CFG, want=40)
        days = {s["start"].astimezone(scheduling.tz("Asia/Jerusalem")).strftime("%a") for s in r["slots"]}
        self.assertTrue(days <= {"Mon", "Tue", "Wed", "Thu"}, days)

    def test_does_not_book_over_existing_meeting(self):
        first = scheduling.find_slots([p("a@x.com")], now=NOW, config=CFG)["slots"][0]
        busy = [(first["start"], first["start"] + timedelta(hours=3))]
        nxt = scheduling.find_slots([p("a@x.com", busy=busy)], now=NOW, config=CFG)["slots"][0]
        self.assertGreaterEqual(nxt["start"], busy[0][1])

    def test_israel_and_us_overlap_is_inside_both_working_days(self):
        people = [p("il@x.com"), p("us@x.com", "America/New_York")]
        s = scheduling.find_slots(people, now=NOW, config=CFG)["slots"][0]
        il = s["start"].astimezone(scheduling.tz("Asia/Jerusalem"))
        ny = s["start"].astimezone(scheduling.tz("America/New_York"))
        self.assertTrue(9 <= ny.hour and (ny + timedelta(minutes=30)).hour <= 17, ny)
        self.assertTrue(9 <= il.hour and (il + timedelta(minutes=30)) <= il.replace(hour=17, minute=0), il)
        self.assertIn(ny.strftime("%a"), ["Mon", "Tue", "Wed", "Thu"])  # US day too

    def test_west_coast_has_no_overlap_and_suggests_widening(self):
        people = [p("il@x.com"), p("sf@x.com", "America/Los_Angeles")]
        r = scheduling.find_slots(people, now=NOW, config=CFG)
        self.assertEqual(r["slots"], [])
        self.assertIn("no overlap", r["reason"])

    def test_no_common_availability_gives_alternatives_and_books_nothing(self):
        far = NOW + timedelta(days=60)
        people = [p("a@x.com", busy=[(NOW, far)]), p("b@x.com")]
        r = scheduling.find_slots(people, now=NOW, config=CFG)
        self.assertEqual(r["slots"], [])
        self.assertTrue(r["alternatives"])
        self.assertTrue(all("a@x.com" in a["conflicts"] for a in r["alternatives"]))

    def test_optional_participant_does_not_block(self):
        far = NOW + timedelta(days=60)
        people = [p("a@x.com"), p("opt@x.com", busy=[(NOW, far)], required=False)]
        s = scheduling.find_slots(people, now=NOW, config=CFG)["slots"][0]
        self.assertEqual(s["optional_conflicts"], ["opt@x.com"])

    def test_pm_preferred_hours_respected(self):
        # 09:00-10:00 New York = 16:00-17:00 Israel: inside both working days
        pref = {"time_zone": "America/New_York", "start": "09:00", "end": "10:00"}
        people = [p("il@x.com"), p("us@x.com", "America/New_York")]
        s = scheduling.find_slots(people, now=NOW, config=CFG, preference=pref)["slots"][0]
        self.assertEqual(s["start"].astimezone(scheduling.tz("America/New_York")).hour, 9)

    def test_preference_outside_someones_hours_finds_nothing(self):
        # 10:00-11:00 New York = 17:00-18:00 Israel: after Israeli working hours
        pref = {"time_zone": "America/New_York", "start": "10:00", "end": "11:00"}
        people = [p("il@x.com"), p("us@x.com", "America/New_York")]
        self.assertEqual(scheduling.find_slots(people, now=NOW, config=CFG, preference=pref)["slots"], [])

    def test_unreadable_calendar_is_unknown_not_free(self):
        r = scheduling.find_slots([p("a@x.com"), p("hidden@x.com", busy=None)], now=NOW, config=CFG)
        self.assertEqual(r["unknown"], ["hidden@x.com"])

    def test_declined_and_free_events_are_not_busy(self):
        items = [
            {"start": {"dateTime": "2026-11-26T09:00:00+02:00"}, "end": {"dateTime": "2026-11-26T10:00:00+02:00"},
             "attendees": [{"self": True, "responseStatus": "declined"}]},
            {"start": {"dateTime": "2026-11-26T11:00:00+02:00"}, "end": {"dateTime": "2026-11-26T12:00:00+02:00"},
             "transparency": "transparent"},
            {"start": {"dateTime": "2026-11-26T13:00:00+02:00"}, "end": {"dateTime": "2026-11-26T14:00:00+02:00"}},
        ]
        self.assertEqual(len(scheduling.busy_from_events(items)), 1)


# ── Calendar script (fake Google) ─────────────────────────────────────────────

class FakeGoogle:
    def __init__(self, zones=None, busy=None, drop_attendee=None, unreadable=()):
        self.zones, self.busy = zones or {}, busy or {}
        self.drop, self.unreadable, self.created = drop_attendee, set(unreadable), None

    def __call__(self, url, method="GET", body=None):
        from urllib.parse import unquote
        if "/events?" in url and method == "GET":
            email = unquote(url.split("/calendars/")[1].split("/")[0])
            if email in self.unreadable:
                raise create_calendar.ApiError(404, "not found")
            return {"timeZone": self.zones.get(email, "Asia/Jerusalem"), "items": self.busy.get(email, [])}
        if method == "POST":
            ev = dict(body, id="E1", htmlLink="https://cal/E1",
                      organizer={"email": "dana@example.com"},
                      conferenceData={"entryPoints": [{"entryPointType": "video", "uri": "https://meet/x"}]})
            if self.drop:
                ev["attendees"] = [a for a in ev["attendees"] if a["email"] != self.drop]
            self.created = ev
            return ev
        return self.created


def run_calendar(data, fake, extra_args=()):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(data, f)
    out, code = io.StringIO(), None
    with patch.object(create_calendar, "google_api", fake), \
            patch.object(sys, "argv", ["x", f.name, "DECK", "ASANA", *extra_args]), redirect_stdout(out):
        try:
            create_calendar.main()
        except SystemExit as e:
            code = e.code
    os.unlink(f.name)
    return code, json.loads(out.getvalue())


class Calendar(unittest.TestCase):
    def test_invite_matches_deck_participants_including_named_owner(self):
        data = dict(BASE, stakeholders=[{"name": "Yanai Owner", "email": "yanai@example.com", "role": "rd_lead"}])
        fake = FakeGoogle()
        code, out = run_calendar(data, fake)
        self.assertEqual(code, 0, out)
        invited = {a["email"] for a in fake.created["attendees"]}
        deck = set(eol_rules.participant_emails(eol_rules.apply(data)))
        self.assertEqual(invited, deck)
        self.assertIn("yanai@example.com", invited)

    def test_verification_flags_attendee_missing_after_creation(self):
        code, out = run_calendar(BASE, FakeGoogle(drop_attendee="ygershongob@paloaltonetworks.com"))
        self.assertEqual(code, 5)
        self.assertEqual(out["status"], "partial")
        self.assertIn("ygershongob@paloaltonetworks.com", " ".join(out["issues"]))

    def test_no_slot_books_nothing(self):
        far = (NOW + timedelta(days=90)).isoformat()
        busy = {"ygershongob@paloaltonetworks.com": [{"start": {"dateTime": "2026-01-01T00:00:00Z"},
                                                     "end": {"dateTime": far}}]}
        fake = FakeGoogle(busy=busy)
        code, out = run_calendar(BASE, fake)
        self.assertEqual(code, 6)
        self.assertFalse(out["booked"])
        self.assertIsNone(fake.created)
        self.assertTrue(out["alternatives"])

    def test_given_start_that_conflicts_is_refused(self):
        sun = "2026-11-29T10:00:00+02:00"  # Sunday: not a meeting day
        fake = FakeGoogle()
        code, out = run_calendar(BASE, fake, [sun])
        self.assertEqual(code, 7)
        self.assertIsNone(fake.created)

    def test_us_participant_gets_reasonable_local_time(self):
        data = dict(BASE, stakeholders=[{"name": "US PM", "email": "us@example.com"}])
        code, out = run_calendar(data, FakeGoogle(zones={"us@example.com": "America/New_York"}))
        self.assertEqual(code, 0, out)
        ny = datetime.fromisoformat(out["start"]).astimezone(scheduling.tz("America/New_York"))
        self.assertGreaterEqual(ny.hour, 9)

    def test_unreadable_calendar_reported(self):
        code, out = run_calendar(BASE, FakeGoogle(unreadable={"aaviad@paloaltonetworks.com"}))
        self.assertEqual(code, 0)
        self.assertTrue(any("aaviad" in g for g in out["availability_gaps"]))


# ── Slack script (fake Slack) ─────────────────────────────────────────────────

class FakeSlack:
    def __init__(self, create_error=None, taken=(), mine=(), unknown_users=(), public=False):
        self.create_error, self.taken, self.mine = create_error, set(taken), set(mine)
        self.unknown, self.public = set(unknown_users), public
        self.members, self.created, self.posted = {"UME"}, None, False

    def __call__(self, url, method="GET", body=None):
        from urllib.parse import urlparse, parse_qs
        ep = urlparse(url).path.rsplit("/", 1)[-1]
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        if ep == "conversations.create":
            if self.create_error:
                return {"ok": False, "error": self.create_error}
            if body["name"] in self.taken or body["name"] in self.mine:
                return {"ok": False, "error": "name_taken"}
            self.created = body
            return {"ok": True, "channel": {"id": "C1", "name": body["name"]}}
        if ep == "users.conversations":
            return {"ok": True, "channels": [{"id": "COLD", "name": n} for n in self.mine]}
        if ep == "conversations.info":
            return {"ok": True, "channel": {"id": q["channel"], "is_private": not self.public, "context_team_id": "T1"}}
        if ep == "auth.test":
            return {"ok": True, "user_id": "UME"}
        if ep == "users.lookupByEmail":
            e = q["email"]
            return {"ok": False, "error": "users_not_found"} if e in self.unknown else {"ok": True, "user": {"id": "U_" + e}}
        if ep == "conversations.invite":
            self.members.add(body["users"])
            return {"ok": True}
        if ep == "conversations.members":
            return {"ok": True, "members": sorted(self.members)}
        if ep == "chat.postMessage":
            self.posted = True
            return {"ok": True}
        return {"ok": False, "error": "unexpected_" + ep}


def run_slack(data, fake, kind="user"):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(data, f)
    out, code = io.StringIO(), None
    with patch.object(create_slack_channel, "slack_api", fake), \
            patch.object(create_slack_channel, "slack_token_kind", lambda: kind), \
            patch.object(sys, "argv", ["x", f.name, "ASANA", "DECK"]), redirect_stdout(out):
        try:
            create_slack_channel.main()
        except SystemExit as e:
            code = e.code
    os.unlink(f.name)
    return code, json.loads(out.getvalue())


class Slack(unittest.TestCase):
    def test_creates_private_channel_and_verifies_members(self):
        fake = FakeSlack()
        code, out = run_slack(BASE, fake)
        self.assertEqual(code, 0, out)
        self.assertTrue(fake.created["is_private"])
        self.assertTrue(out["private_verified"])
        self.assertEqual(set(out["added"]), set(eol_rules.participant_emails(eol_rules.apply(BASE))))
        self.assertTrue(out["channel_url"].startswith("https://app.slack.com/client/T1/"))

    def test_missing_permission_is_explained_not_reported_done(self):
        for err in ("missing_scope", "restricted_action"):
            code, out = run_slack(BASE, FakeSlack(create_error=err))
            self.assertEqual(code, 1)
            self.assertEqual(out["status"], "failed")
            self.assertIsNone(out["channel_url"])
            self.assertTrue(out["fix"])

    def test_no_token_is_explained(self):
        code, out = run_slack(BASE, FakeSlack(), kind=None)
        self.assertEqual(code, 1)
        self.assertIn("pm-claude-code-setup", out["fix"])

    def test_name_taken_by_invisible_channel_uses_suffix(self):
        """Root cause of the earlier failure: name_taken + channel not visible."""
        code, out = run_slack(BASE, FakeSlack(taken={"eol-legacy-vault-appliance"}))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["channel_name"], "eol-legacy-vault-appliance-2")

    def test_name_taken_by_own_channel_is_reused(self):
        code, out = run_slack(BASE, FakeSlack(mine={"eol-legacy-vault-appliance"}))
        self.assertTrue(out["reused_existing"])
        self.assertEqual(out["channel_id"], "COLD")

    def test_public_channel_is_rejected(self):
        code, out = run_slack(BASE, FakeSlack(public=True))
        self.assertEqual(code, 1)
        self.assertFalse(out["private_verified"])

    def test_unknown_user_gives_partial_with_reason(self):
        data = dict(BASE, stakeholders=[{"name": "Ghost", "email": "ghost@example.com"}])
        code, out = run_slack(data, FakeSlack(unknown_users={"ghost@example.com"}))
        self.assertEqual(code, 5)
        self.assertEqual(out["not_added"][0]["email"], "ghost@example.com")


if __name__ == "__main__":
    unittest.main()
