#!/usr/bin/env python3
"""
create_slack_channel.py  —  EOL Kickoff Toolkit helper
Creates a private Slack channel for the EOL and invites relevant members.

Usage:
  python3 create_slack_channel.py <eol_input.json> <asana_url> <deck_url>

Outputs JSON with channel_id, channel_name, channel_url.
"""

import json, sys, os, urllib.parse, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_http import slack_api  # noqa: E402

FIXED_MEMBERS = [
    "ygershongob@paloaltonetworks.com",   # Yael
]
# Pricing stakeholders — invited only when pricing is relevant, i.e. SKUs are
# impacted. Feature deprecations with no SKU skip them.
PRICING_MEMBERS = [
    "aaviad@paloaltonetworks.com",         # Amir
]
SLACK_API = "https://slack.com/api"


def get_token():
    return None  # kept for call-site compatibility; vault_http resolves auth
                 # (SLACK_USER_TOKEN by default, SLACK_BOT_TOKEN as fallback)


def slack_post(endpoint, token, payload):
    return slack_api(f"{SLACK_API}/{endpoint}", "POST", payload)


def slack_get(endpoint, token, params=None):
    url = f"{SLACK_API}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return slack_api(url)


def normalize_channel_name(product_name):
    """Convert product name to a valid Slack channel name (lowercase, hyphens, max 80 chars)."""
    name = product_name.lower()
    name = re.sub(r"[^a-z0-9\s\-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    if not name.startswith("eol-"):
        name = "eol-" + name
    return name[:80]


def lookup_user(email, token):
    """Return the Slack user ID for an email, or None if not found."""
    try:
        result = slack_get("users.lookupByEmail", token, {"email": email})
        if result.get("ok"):
            return result["user"]["id"]
        return None
    except Exception:
        return None


def find_existing_channel(name, token):
    """Find a private channel by name (searches up to 500 channels)."""
    cursor = None
    for _ in range(5):
        params = {"types": "private_channel", "limit": "100", "exclude_archived": "true"}
        if cursor:
            params["cursor"] = cursor
        result = slack_get("conversations.list", token, params)
        for ch in result.get("channels", []):
            if ch["name"] == name:
                return ch["id"]
        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


def main():
    if len(sys.argv) < 4:
        print("Usage: create_slack_channel.py <eol_input.json> <asana_url> <deck_url>",
              file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        d = json.load(f)

    asana_url  = sys.argv[2]
    deck_url   = sys.argv[3]
    product    = d.get("product_name", "EOL")
    # Split contact field in case it contains multiple comma-separated emails
    raw_contact = d.get("contact", "")
    pm_emails   = [e.strip() for e in raw_contact.split(",") if "@" in e.strip()]
    extra       = d.get("slack_additional_members", [])

    token = get_token()

    # ── 1. Create private channel ──────────────────────────────────────────────
    channel_name = normalize_channel_name(product)
    result = slack_post("conversations.create", token, {
        "name":       channel_name,
        "is_private": True,
    })

    if result.get("ok"):
        channel_id = result["channel"]["id"]
    elif result.get("error") == "name_taken":
        print(f"Channel #{channel_name} already exists — reusing it.", file=sys.stderr)
        channel_id = find_existing_channel(channel_name, token)
        if not channel_id:
            print(f"ERROR: Could not locate existing channel #{channel_name}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"ERROR creating channel: {result.get('error')}", file=sys.stderr)
        sys.exit(1)

    # ── 2. Resolve user IDs ────────────────────────────────────────────────────
    pricing_relevant = bool(d.get("impacted_skus"))
    all_emails = list(dict.fromkeys(
        FIXED_MEMBERS + (PRICING_MEMBERS if pricing_relevant else [])
        + pm_emails + (extra or [])
    ))
    user_ids = []
    for email in all_emails:
        uid = lookup_user(email, token)
        if uid:
            user_ids.append(uid)
        else:
            print(f"WARNING: Could not find Slack user for {email}", file=sys.stderr)

    # ── 3. Invite members ──────────────────────────────────────────────────────
    if user_ids:
        invite = slack_post("conversations.invite", token, {
            "channel": channel_id,
            "users":   ",".join(user_ids),
        })
        if not invite.get("ok") and invite.get("error") != "already_in_channel":
            print(f"WARNING: Invite issue: {invite.get('error')}", file=sys.stderr)

    # ── 4. Post intro message ──────────────────────────────────────────────────
    intro = (
        f":wave: *EOL Kickoff: {product}*\n\n"
        f"📋 Asana task: {asana_url}\n"
        f"📊 Deck: {deck_url}\n\n"
        f"_This channel is the home for all coordination around this EOL._"
    )
    slack_post("chat.postMessage", token, {"channel": channel_id, "text": intro})

    print(json.dumps({
        "channel_id":   channel_id,
        "channel_name": channel_name,
        "channel_url":  f"https://app.slack.com/client/{channel_id}",
    }))


if __name__ == "__main__":
    main()
