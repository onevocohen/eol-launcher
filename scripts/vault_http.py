#!/usr/bin/env python3
"""
vault_http.py — shared HTTP helper for the EOL scripts.

Credential resolution, in order:
  1. Environment variable (GOOGLE_ACCESS_TOKEN / SLACK_USER_TOKEN / SLACK_BOT_TOKEN),
     if set — the request is made directly.
  2. Otherwise the sealed pm-claude-code-setup vault (macOS Keychain). The vault
     script makes the request itself and returns only the response body, so the
     token never enters this process.
  3. Otherwise the legacy Cursor PM setup: ~/.config/secrets/get-secret.sh for
     Asana/Slack, and the gcloud ADC file for Google.

Raises ApiError(status, body) on non-2xx responses.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

VAULT_DIR = os.path.expanduser("~/.claude/skills/pm-claude-code-setup/scripts")
CRED_VAULT = os.path.join(VAULT_DIR, "credential-vault.sh")
GWS_ADC = os.path.join(VAULT_DIR, "gws-adc.sh")
DEFAULT_QUOTA_PROJECT = "pntops"

# Legacy (Cursor PM setup) credential sources, used only when the vault is absent
LEGACY_SECRET = os.path.expanduser("~/.config/secrets/get-secret.sh")
LEGACY_ADC = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")


class ApiError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:1000]}")
        self.status = status
        self.body = body


def _direct(url, token, method, body, extra_headers):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    headers.update(extra_headers)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, e.read().decode(errors="replace"))


def _sealed(cmd, url, method, body, extra_headers):
    cmd = cmd + ["--action", "Invoke", "--uri", url, "--method", method]
    for name, value in extra_headers.items():
        cmd += ["--extra-header", f"{name}: {value}"]
    if body is not None:
        cmd += ["--body", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        m = re.search(r"status (\d{3})", r.stderr)
        raise ApiError(int(m.group(1)) if m else 0, r.stderr.strip())
    return json.loads(r.stdout or "{}")


def _vault_has(key):
    if not os.path.exists(CRED_VAULT):
        return False
    r = subprocess.run(["bash", CRED_VAULT, "--action", "Test", "--key", key],
                       capture_output=True, text=True)
    return r.returncode == 0


def _legacy_secret(key):
    if not os.path.exists(LEGACY_SECRET):
        return ""
    r = subprocess.run(["bash", LEGACY_SECRET, key], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _legacy_google_token():
    if not os.path.exists(LEGACY_ADC):
        return ""
    with open(LEGACY_ADC) as f:
        creds = json.load(f)
    data = urllib.parse.urlencode({
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type":    "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["access_token"]


# ── Google ────────────────────────────────────────────────────────────────────

def google_api(url, method="GET", body=None):
    quota = os.environ.get("GOOGLE_QUOTA_PROJECT", "").strip()
    token = os.environ.get("GOOGLE_ACCESS_TOKEN", "").strip()
    if token:
        extra = {"X-Goog-User-Project": quota} if quota else {}
        return _direct(url, token, method, body, extra)
    if not os.path.exists(GWS_ADC):
        token = _legacy_google_token()
        if not token:
            raise SystemExit(
                "Error: no Google credential found (GOOGLE_ACCESS_TOKEN, the "
                "pm-claude-code-setup vault, or the gcloud ADC file). "
                "Can't connect to Google APIs.")
        return _direct(url, token, method, body,
                       {"X-Goog-User-Project": quota or DEFAULT_QUOTA_PROJECT})
    extra = {"X-Goog-User-Project": quota or DEFAULT_QUOTA_PROJECT}
    return _sealed(["bash", GWS_ADC], url, method, body, extra)


# ── Asana ─────────────────────────────────────────────────────────────────────

def asana_api(url, method="GET", body=None):
    token = os.environ.get("ASANA_ACCESS_TOKEN", "").strip()
    if token:
        return _direct(url, token, method, body, {})
    if not _vault_has("ASANA_ACCESS_TOKEN"):
        token = _legacy_secret("ASANA_ACCESS_TOKEN")
        if token:
            return _direct(url, token, method, body, {})
        raise SystemExit(
            "Error: ASANA_ACCESS_TOKEN is not in the environment, the "
            "pm-claude-code-setup vault, or ~/.config/secrets. Can't connect to Asana.")
    return _sealed(["bash", CRED_VAULT, "--key", "ASANA_ACCESS_TOKEN"], url, method, body, {})


# ── Slack ─────────────────────────────────────────────────────────────────────

_slack_source = None  # ("env", token) or ("vault", key)


def _resolve_slack():
    global _slack_source
    if _slack_source:
        return _slack_source
    for key in ("SLACK_USER_TOKEN", "SLACK_BOT_TOKEN"):  # user token is the default
        token = os.environ.get(key, "").strip()
        if token:
            _slack_source = ("env", token)
            return _slack_source
    for key in ("SLACK_USER_TOKEN", "SLACK_BOT_TOKEN"):
        if _vault_has(key):
            _slack_source = ("vault", key)
            return _slack_source
    for key, prefix in (("SLACK_USER_TOKEN", "xoxp-"), ("SLACK_BOT_TOKEN", "xoxb-")):
        token = _legacy_secret(key)
        if token.startswith(prefix):
            _slack_source = ("env", token)
            return _slack_source
    raise SystemExit("ERROR: No Slack token found (SLACK_USER_TOKEN or SLACK_BOT_TOKEN) "
                     "in the environment or the vault.")


def slack_token_kind():
    """'user' or 'bot' for the token slack_api() will use, or None if there is none."""
    try:
        kind, value = _resolve_slack()
    except SystemExit:
        return None
    key = value if kind == "vault" else ("SLACK_USER_TOKEN" if str(value).startswith("xoxp-") else "SLACK_BOT_TOKEN")
    return "user" if key == "SLACK_USER_TOKEN" else "bot"


def slack_api(url, method="GET", body=None):
    kind, value = _resolve_slack()
    if kind == "env":
        return _direct(url, value, method, body, {})
    return _sealed(["bash", CRED_VAULT, "--key", value], url, method, body, {})
