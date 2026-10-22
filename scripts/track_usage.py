#!/usr/bin/env python3
"""
track_usage.py — logs EOL skill usage to metrics/usage.json and updates README stats.

Usage:
  python3 track_usage.py start    "<pm_name>" "<product_name>"
  python3 track_usage.py complete "<pm_name>" "<product_name>"
  python3 track_usage.py report
  python3 track_usage.py update-readme
"""

import sys
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

SKILL_DIR   = Path(__file__).resolve().parent.parent
METRICS_DIR = SKILL_DIR / "metrics"
LOG_FILE    = METRICS_DIR / "usage.json"
README_FILE = SKILL_DIR / "README.md"

STATS_START = "<!-- USAGE_STATS_START -->"
STATS_END   = "<!-- USAGE_STATS_END -->"


# ── I/O helpers ───────────────────────────────────────────────────────────────

def load_log():
    METRICS_DIR.mkdir(exist_ok=True)
    if not LOG_FILE.exists():
        return {"runs": []}
    with open(LOG_FILE) as f:
        return json.load(f)


def save_log(data):
    METRICS_DIR.mkdir(exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Core actions ──────────────────────────────────────────────────────────────

def log_event(event: str, pm_name: str, product_name: str):
    data = load_log()
    data["runs"].append({
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "pm_name":      pm_name,
        "product_name": product_name,
        "event":        event,
    })
    save_log(data)
    print(f"[metrics] '{event}' logged for {pm_name} / {product_name}")


def compute_stats() -> dict:
    data      = load_log()
    runs      = data.get("runs", [])
    completed = [r for r in runs if r.get("event") == "complete"]

    pm_counts = Counter(r["pm_name"] for r in completed)
    products  = sorted(set(r["product_name"] for r in completed))

    return {
        "total_completed":  len(completed),
        "unique_pms":       len(pm_counts),
        "unique_products":  len(products),
        "pm_breakdown":     dict(pm_counts.most_common()),
        "all_products":     products,
    }


def generate_report():
    stats = compute_stats()
    print(f"Total EOL sessions completed : {stats['total_completed']}")
    print(f"Unique PMs                   : {stats['unique_pms']}")
    print(f"Unique products processed    : {stats['unique_products']}")
    if stats["pm_breakdown"]:
        print("\nPer-PM breakdown:")
        for pm, count in stats["pm_breakdown"].items():
            print(f"  {pm}: {count} EOL(s)")
    else:
        print("\nNo completed EOLs yet.")
    return stats


# ── README update ─────────────────────────────────────────────────────────────

def build_stats_block(stats: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    lines = [STATS_START]
    lines += [
        "| Metric | Count |",
        "|---|---|",
        f"| ✅ EOL sessions completed | **{stats['total_completed']}** |",
        f"| 👤 Unique PMs who used this skill | **{stats['unique_pms']}** |",
        f"| 📦 Unique products processed | **{stats['unique_products']}** |",
        "",
        f"*Last updated: {now}*",
        "",
    ]

    if stats["pm_breakdown"]:
        lines += [
            "**Per-PM breakdown:**",
            "",
            "| PM | EOL sessions |",
            "|---|---|",
        ]
        for pm, count in stats["pm_breakdown"].items():
            lines.append(f"| {pm} | {count} |")
    else:
        lines.append("**Per-PM breakdown:** *No completed EOLs yet.*")

    lines.append(STATS_END)
    return "\n".join(lines)


def update_readme(stats: dict):
    if not README_FILE.exists():
        print(f"README.md not found at {README_FILE}", file=sys.stderr)
        sys.exit(1)

    content = README_FILE.read_text()

    if STATS_START not in content or STATS_END not in content:
        print(
            "README.md is missing the <!-- USAGE_STATS_START / END --> markers.",
            file=sys.stderr,
        )
        sys.exit(1)

    pattern  = re.escape(STATS_START) + r".*?" + re.escape(STATS_END)
    new_block = build_stats_block(stats)
    updated   = re.sub(pattern, new_block, content, flags=re.DOTALL)

    README_FILE.write_text(updated)
    print("[metrics] README.md stats section updated.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"

    if cmd == "report":
        generate_report()

    elif cmd in ("start", "complete"):
        if len(sys.argv) < 4:
            print(f"Usage: track_usage.py {cmd} <pm_name> <product_name>",
                  file=sys.stderr)
            sys.exit(1)
        log_event(cmd, sys.argv[2], sys.argv[3])

    elif cmd == "update-readme":
        update_readme(compute_stats())

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
