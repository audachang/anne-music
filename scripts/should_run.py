#!/usr/bin/env python3
"""Gate for cron: exit 0 (run) only on Monday OR within 7 days of any deadline.

Used by refresh.sh — keeps off-day cron invocations cheap when no deadlines loom.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

WINDOW_DAYS = 7
STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "state.json"


def deadline_entries(state: dict) -> list[dict]:
    entries = state.get("included_north", []) + state.get("included_other", [])
    for topic in state.get("topic_tabs", []):
        if topic.get("source") == "legacy_music":
            continue
        entries.extend(topic.get("included_north", []))
        entries.extend(topic.get("included_other", []))
    return entries


def main() -> int:
    today = date.today()

    if today.isoweekday() == 1:
        print(f"[gate] {today} is Monday → run")
        return 0

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    cutoff = today + timedelta(days=WINDOW_DAYS)

    upcoming = []
    for entry in deadline_entries(state):
        ds = entry.get("deadline_iso")
        if not ds:
            continue
        try:
            d = datetime.strptime(ds, "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= d <= cutoff:
            upcoming.append((d, entry.get("organizer", entry.get("id", "?"))))

    if upcoming:
        upcoming.sort()
        for d, name in upcoming:
            print(f"[gate] deadline {d} ≤7d: {name}")
        return 0

    print(f"[gate] {today} not Monday and no deadline within {WINDOW_DAYS}d → skip")
    return 1


if __name__ == "__main__":
    sys.exit(main())
