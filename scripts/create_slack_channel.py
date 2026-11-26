#!/usr/bin/env python3
"""
create_slack_channel.py  —  EOL Kickoff Toolkit helper
Creates a PRIVATE Slack channel for the EOL, invites the kickoff participants
(the same list as the deck and the calendar invite), posts the intro, and
verifies each step.

Usage:
  python3 create_slack_channel.py <eol_input.json> <asana_url> <deck_url>

If the input JSON has asana_project_url, the intro message links it too.

Always prints one JSON object on stdout. Exit codes:
  0  "ok"       private channel created (or reused), everyone added, intro posted
  5  "partial"  channel is usable, but some people couldn't be added / intro failed
  1  "failed"   no usable private channel; "error" and "fix" say why and what to do

Never reports success for a step that wasn't confirmed by Slack.
"""

import json, sys, os, urllib.parse, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_http import slack_api, slack_token_kind  # noqa: E402
import eol_rules  # noqa: E402

SLACK_API = "https://slack.com/api"

# Slack error -> (plain explanation, what to do)
FIXES = {
    "missing_scope": ("the Slack app is missing a permission (scope)",
                      "Add the groups:write (create private channels) and users:read.email scopes to the Slack app, reinstall it, then re-run this step."),
    "restricted_action": ("the workspace only lets admins or certain members create private channels",
                          "Ask a Slack admin to allow private channel creation for this app/user, or create the channel manually."),
    "not_authed": ("no valid Slack token", "Re-run the Slack connection in pm-claude-code-setup."),
    "invalid_auth": ("the Slack token is invalid or revoked", "Re-run the Slack connection in pm-claude-code-setup."),
    "token_revoked": ("the Slack token was revoked", "Re-run the Slack connection in pm-claude-code-setup."),
    "account_inactive": ("the Slack account behind the token is deactivated", "Reconnect Slack with an active account."),
    "team_access_not_granted": ("the Slack app isn't installed in this workspace",
                                "Install the app in the workspace (Enterprise Grid: grant it workspace access)."),
    "ratelimited": ("Slack rate limit", "Wait a minute and re-run this step."),
}


def call(endpoint, payload=None, method="POST"):
    url = f"{SLACK_API}/{endpoint}"
    try:
        if method == "GET":
            if payload:
                url += "?" + urllib.parse.urlencode(payload)
            return slack_api(url)
        return slack_api(url, "POST", payload or {})
    except SystemExit as e:  # no token at all
        return {"ok": False, "error": "not_authed", "detail": str(e)}
    except Exception as e:  # network / vault failure
        return {"ok": False, "error": "request_failed", "detail": str(e)[:300]}


def explain(err, detail=""):
    why, fix = FIXES.get(err, (f"Slack returned '{err}'", "Check the Slack connection and re-run this step."))
    return why + (f" ({detail})" if detail else ""), fix


def normalize_channel_name(product_name):
    """Valid Slack channel name: lowercase letters, digits, hyphens, max 80 chars."""
    name = (product_name or "").lower()
    name = re.sub(r"[^a-z0-9\s\-_]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name.startswith("eol-"):
        name = "eol-" + name if name else "eol-kickoff"
    return name[:80].rstrip("-")


def lookup_user(email):
    r = call("users.lookupByEmail", {"email": email}, "GET")
    return (r["user"]["id"], None) if r.get("ok") else (None, r.get("error", "unknown"))


def find_my_private_channel(name):
    """Private channel with this name that the token's user/bot is a member of."""
    cursor = None
    for _ in range(20):
        params = {"types": "private_channel", "limit": "200", "exclude_archived": "true"}
        if cursor:
            params["cursor"] = cursor
        r = call("users.conversations", params, "GET")
        if not r.get("ok"):
            return None
        for ch in r.get("channels", []):
            if ch.get("name") == name:
                return ch["id"]
        cursor = (r.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return None
    return None


def create_private(base):
    """Create a private channel; on name_taken reuse ours, else try -2, -3 …
    Returns (channel_id, name, reused, error, detail)."""
    for i in range(1, 6):
        name = base if i == 1 else f"{base[:76]}-{i}"
        r = call("conversations.create", {"name": name, "is_private": True})
        if r.get("ok"):
            return r["channel"]["id"], name, False, None, None
        if r.get("error") != "name_taken":
            return None, name, False, r.get("error"), r.get("detail", "")
        mine = find_my_private_channel(name)
        if mine:
            return mine, name, True, None, None
        # Taken by a channel we can't see (archived, public, or someone else's private one)
    return None, base, False, "name_taken", "every name up to -5 is taken"


def main():
    if len(sys.argv) < 4:
        print("Usage: create_slack_channel.py <eol_input.json> <asana_url> <deck_url>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        d = eol_rules.apply(json.load(f))
    asana_url, deck_url = sys.argv[2], sys.argv[3]
    product = d.get("product_name", "EOL")
    kind = slack_token_kind()  # "user" | "bot" | None
    result = {"status": "failed", "token": kind, "channel_name": None, "channel_url": None,
              "private_verified": False, "added": [], "not_added": [], "intro_posted": False, "issues": []}

    def fail(err, detail=""):
        why, fix = explain(err, detail)
        result.update(error=why, fix=fix)
        print(json.dumps(result, indent=1, ensure_ascii=False))
        sys.exit(1)

    if not kind:
        fail("not_authed", "neither SLACK_USER_TOKEN nor SLACK_BOT_TOKEN is available")

    # ── 1. Create (or reuse) the private channel ───────────────────────────────
    channel_id, name, reused, err, detail = create_private(normalize_channel_name(product))
    if not channel_id:
        fail(err, detail)
    result.update(channel_id=channel_id, channel_name=name, reused_existing=reused)

    # ── 2. Verify it exists and is private ─────────────────────────────────────
    info = call("conversations.info", {"channel": channel_id}, "GET")
    ch = info.get("channel", {}) if info.get("ok") else {}
    if not ch:
        fail(info.get("error", "channel_not_found"), "the channel couldn't be read back after creation")
    if not ch.get("is_private"):
        fail("not_private", f"#{name} exists but is not private; it was not used")
    result["private_verified"] = True
    team = ch.get("context_team_id") or ""
    result["channel_url"] = (f"https://app.slack.com/client/{team}/{channel_id}" if team
                             else f"https://app.slack.com/client/{channel_id}")

    # ── 3. Invite participants (same list as deck + calendar) ──────────────────
    me = call("auth.test")
    my_id = me.get("user_id")
    emails = eol_rules.participant_emails(d)
    targets = {}
    for email in emails:
        uid, lerr = lookup_user(email)
        if uid:
            targets[email] = uid
        else:
            result["not_added"].append({"email": email, "reason": "no Slack user with this email" if lerr == "users_not_found" else lerr})
    for email, uid in targets.items():
        if uid == my_id:
            result["added"].append(email)  # the creator is already a member
            continue
        r = call("conversations.invite", {"channel": channel_id, "users": uid})
        if r.get("ok") or r.get("error") == "already_in_channel":
            result["added"].append(email)
        else:
            result["not_added"].append({"email": email, "reason": r.get("error", "invite failed")})

    # ── 4. Verify membership from Slack's side ─────────────────────────────────
    members, cursor = set(), None
    for _ in range(10):
        params = {"channel": channel_id, "limit": "500", **({"cursor": cursor} if cursor else {})}
        m = call("conversations.members", params, "GET")
        if not m.get("ok"):
            result["issues"].append("couldn't read the member list back: " + m.get("error", ""))
            members = None
            break
        members.update(m.get("members", []))
        cursor = (m.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    if members is not None:
        for email in list(result["added"]):
            if targets.get(email) not in members:
                result["added"].remove(email)
                result["not_added"].append({"email": email, "reason": "invite accepted but not in the member list"})
    if kind == "bot":
        result["issues"].append("created with the bot token: the bot owns the channel; the PM is invited as a member")

    # ── 5. Intro message ───────────────────────────────────────────────────────
    project_url = (d.get("asana_project_url") or "").strip()
    who = "\n".join(f"• {p['name']} ({' / '.join(p['roles'])})" for p in d["_stakeholders"]["participants"])
    intro = (f":wave: *EOL Kickoff: {product}*\n\n"
             f"📋 Asana task: {asana_url}\n"
             + (f"🗂️ Asana project: {project_url} _(track EOL execution tasks there)_\n" if project_url else "")
             + f"📊 Deck: {deck_url}\n"
             f"❓ Open questions for kickoff: {len(d['_open_questions'])} _(see the \"Open Questions & Decisions\" slide)_\n\n"
             f"*Participants*\n{who}\n\n_This channel is the home for all coordination around this EOL._")
    if not reused:
        post = call("chat.postMessage", {"channel": channel_id, "text": intro})
        result["intro_posted"] = bool(post.get("ok"))
        if not post.get("ok"):
            result["issues"].append("intro message not posted: " + post.get("error", ""))
    else:
        result["issues"].append(f"reused the existing private channel #{name}; intro not re-posted")

    if result["not_added"]:
        result["issues"].append("not added: " + ", ".join(f"{x['email']} ({x['reason']})" for x in result["not_added"]))
    result["status"] = "partial" if (result["not_added"] or (not result["intro_posted"] and not reused)) else "ok"
    print(json.dumps(result, indent=1, ensure_ascii=False))
    sys.exit(5 if result["status"] == "partial" else 0)


if __name__ == "__main__":
    main()
