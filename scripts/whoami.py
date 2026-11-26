#!/usr/bin/env python3
"""
whoami.py — Identify the PM running the skill, so the skill doesn't have to ask.

Reads the signed-in Asana user (the PM's own Asana connection) and prints
{"pm_name": "...", "contact": "<email>"} as JSON.

Usage:
    python3 whoami.py

Exit codes:
    0  — identity printed
    2  — not available (no Asana connection, or the call failed): ask the PM
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vault_http import asana_api  # noqa: E402


def main():
    try:
        me = asana_api("https://app.asana.com/api/1.0/users/me?opt_fields=name,email",
                       "GET").get("data", {})
    except BaseException:  # noqa: B036 — SystemExit from a missing token too
        sys.exit(2)
    name, email = (me.get("name") or "").strip(), (me.get("email") or "").strip()
    if not (name or email):
        sys.exit(2)
    print(json.dumps({"pm_name": name, "contact": email}, ensure_ascii=False))


if __name__ == "__main__":
    main()
