#!/usr/bin/env python3
"""Best-effort usage telemetry for this skill (observability schema v2.0).

Fire-and-forget: every failure is swallowed, nothing is printed, and each POST
times out after 5 seconds, so telemetry can never block or confuse the PM.
Entity identity and version come from this skill's SKILL.md frontmatter.
No prompt text or PM content is ever sent.

Usage (run from the skill's own steps):
  python3 obs.py start  --model "<model name from your system prompt>"
  python3 obs.py begin                      # start the timer before a step's work
  python3 obs.py action <action_name> [--outcome success|error] [--error "<short reason>"]
                        [--intent creation|modification|query|analysis|error_fix]
                        [--creation new|same] [--iterate]
  python3 obs.py cancel                     # PM abandoned the in-progress step
  python3 obs.py end    [--outcome completed|abandoned]
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import time
import urllib.request
import uuid

ENDPOINT = "https://iedxh6hvmj.execute-api.us-east-1.amazonaws.com/prod/events"
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _frontmatter():
    meta = {}
    try:
        text = open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8").read()
        block = text.split("---", 2)[1]
        for key in ("name", "version", "entity_id", "entity_name"):
            m = re.search(r"^\s*%s:\s*(.+?)\s*$" % key, block, re.M)
            if m:
                meta[key] = m.group(1).strip().strip("'\"")
    except Exception:
        pass
    return meta


META = _frontmatter()
ENTITY_ID = META.get("entity_id") or os.path.basename(SKILL_DIR)
ENTITY_NAME = META.get("entity_name") or META.get("name") or ENTITY_ID
VERSION = META.get("version", "unknown")
STATE_FILE = os.path.expanduser("~/.obs-%s-session.json" % ENTITY_ID)


def _now_ms():
    return int(time.time() * 1000)


def _iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _platform():
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude-code"
    parts = {part.lower() for part in re.split(r"[/\\]+", SKILL_DIR)}
    if ".claude" in parts:
        return "claude-code"
    return "cursor"


def _user_hash():
    path = os.path.expanduser("~/.observability-identity")
    try:
        if os.path.exists(path):
            value = open(path).read().strip()
            if value:
                return value
    except Exception:
        pass
    email = ""
    try:
        email = subprocess.check_output(["git", "config", "user.email"],
                                        stderr=subprocess.DEVNULL, timeout=3).decode().strip()
    except Exception:
        pass
    value = os.environ.get("USER") or os.environ.get("USERNAME") or email or "unknown"
    try:
        with open(path, "w") as f:
            f.write(value)
    except Exception:
        pass
    return value


def _load():
    try:
        return json.load(open(STATE_FILE))
    except Exception:
        return None


def _save(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def _send(state, event_type, **extra):
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "entity_type": "skill",
        "entity_id": ENTITY_ID,
        "entity_name": ENTITY_NAME,
        "entity_version": VERSION,
        "session_id": state["session_id"],
        "received_at": _iso(),
        "platform": state.get("platform") or _platform(),
        "llm_model": state.get("llm_model") or "unavailable",
        "llm_provider": "anthropic",
        "token_source": "unavailable",
        "user_hash": state.get("user_hash") or "unknown",
        "identity_persistence": "persistent",
    }
    event.update({k: v for k, v in extra.items() if v is not None})
    try:
        req = urllib.request.Request(ENDPOINT, data=json.dumps(event).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass


def _new_state(model):
    return {
        "session_id": str(uuid.uuid4()),
        "session_start_ms": _now_ms(),
        "user_hash": _user_hash(),
        "llm_model": model or "unavailable",
        "platform": _platform(),
        "actions_completed": 0,
        "actions_failed": 0,
        "actions_cancelled": 0,
        "action_id": "",
        "action_start_ms": 0,
        "creation_id": "",
        "iteration_number": 0,
    }


def _ensure(model=None):
    state = _load()
    if state is None:  # start was skipped: open a session so events still link up
        state = _new_state(model)
        _send(state, "session_start")
        _save(state)
    return state


def cmd_start(a):
    state = _new_state(a.model)
    _send(state, "session_start")
    state["action_id"] = str(uuid.uuid4())
    state["action_start_ms"] = state["session_start_ms"]
    _save(state)


def cmd_begin(a):
    state = _ensure()
    state["action_id"] = str(uuid.uuid4())
    state["action_start_ms"] = _now_ms()
    _save(state)


def cmd_action(a):
    state = _ensure()
    start = state.get("action_start_ms") or state["session_start_ms"]
    extra = {
        "outcome": a.outcome,
        "action_id": state.get("action_id") or str(uuid.uuid4()),
        "action_name": a.name,
        "duration_ms": max(0, _now_ms() - start),
        "prompt_intent": a.intent if a.outcome == "success" else None,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    if a.creation == "new" or (a.creation == "same" and not state.get("creation_id")):
        state["creation_id"] = str(uuid.uuid4())
        state["iteration_number"] = 1
    elif a.creation == "same" and a.iterate:
        state["iteration_number"] = int(state.get("iteration_number") or 0) + 1
    if a.creation:
        extra["creation_id"] = state["creation_id"]
        extra["iteration_number"] = state["iteration_number"]
    if a.outcome == "error":
        reason = (a.error or "Error: unspecified")
        extra["error_type"] = reason[:100]
        extra["error_type_raw"] = reason[:1000]
        state["actions_failed"] += 1
    else:
        state["actions_completed"] += 1
    _send(state, "action", **extra)
    # the next action is timed from here unless `begin` is called again
    state["action_id"] = str(uuid.uuid4())
    state["action_start_ms"] = _now_ms()
    _save(state)


def cmd_cancel(a):
    state = _ensure()
    start = state.get("action_start_ms") or state["session_start_ms"]
    _send(state, "action_cancel", action_id=state.get("action_id") or str(uuid.uuid4()),
          cancel_reason="user_initiated", cancel_trigger="user_interrupt",
          duration_ms=max(0, _now_ms() - start))
    state["actions_cancelled"] += 1
    _save(state)


def cmd_end(a):
    state = _load()
    if state is None:
        return
    _send(state, "session_end",
          session_duration_ms=max(0, _now_ms() - state["session_start_ms"]),
          actions_completed=state["actions_completed"],
          actions_failed=state["actions_failed"],
          actions_cancelled=state["actions_cancelled"],
          session_outcome=a.outcome)
    try:
        os.remove(STATE_FILE)
    except Exception:
        pass


def main():
    class _Quiet(argparse.ArgumentParser):
        def error(self, message):
            raise SystemExit(0)

    p = _Quiet(add_help=False)
    sub = p.add_subparsers(dest="cmd", parser_class=_Quiet)
    s = sub.add_parser("start"); s.add_argument("--model", default="")
    sub.add_parser("begin")
    s = sub.add_parser("action"); s.add_argument("name")
    s.add_argument("--outcome", choices=["success", "error"], default="success")
    s.add_argument("--error")
    s.add_argument("--intent", choices=["creation", "modification", "query", "analysis", "error_fix"])
    s.add_argument("--creation", choices=["new", "same"])
    s.add_argument("--iterate", action="store_true")
    sub.add_parser("cancel")
    s = sub.add_parser("end"); s.add_argument("--outcome", choices=["completed", "abandoned"], default="completed")
    try:
        a = p.parse_args()
        {"start": cmd_start, "begin": cmd_begin, "action": cmd_action,
         "cancel": cmd_cancel, "end": cmd_end}.get(a.cmd, lambda _a: None)(a)
    except BaseException:
        pass


if __name__ == "__main__":
    main()
