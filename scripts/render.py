#!/usr/bin/env python3
"""Render data/state.json -> docs/index.html via Jinja2 template.

Deterministic. Run after the agent updates state.json. No external network.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "state.json"
TEMPLATE_DIR = ROOT / "docs"
TEMPLATE_NAME = "_template.html.j2"
OUTPUT_PATH = ROOT / "docs" / "index.html"

RECENT_WINDOW_DAYS = 7


def parse_iso(d: str) -> date | None:
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def make_helpers(today: date):
    cutoff = today - timedelta(days=RECENT_WINDOW_DAYS)

    def is_recent(entry: dict) -> bool:
        d = parse_iso(entry.get("last_changed", ""))
        return d is not None and d >= cutoff

    def is_new(entry: dict) -> bool:
        first = parse_iso(entry.get("first_seen", ""))
        last = parse_iso(entry.get("last_changed", ""))
        return first is not None and last is not None and first == last and last >= cutoff

    def row_class(entry: dict) -> str:
        if is_new(entry):
            return "row-recent"
        if is_recent(entry):
            return "row-updated"
        return ""

    def badge(entry: dict) -> str:
        if is_new(entry):
            return '<span class="badge new">新增</span>'
        if is_recent(entry):
            return '<span class="badge updated">更新</span>'
        return ""

    return is_recent, row_class, badge


def main() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    today = date.today()
    is_recent, row_class, badge = make_helpers(today)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    template = env.get_template(TEMPLATE_NAME)

    music_topic = {
        "id": "music",
        "label": "音樂／管樂",
        "title": "Anne 2026 暑期管樂團／管樂營 (北北桃)",
        "subtitle": "適合國小高年級 · 有確認活動日期與報名日期 · 報名尚未截止",
        "included_heading": "符合條件 (北北桃)",
        "other_heading": "其他條件符合,但地區不在北北桃 (參考)",
        "pending_heading": "待查 (主辦單位已宣告 2026 開放報名,但搜尋尚未取得確切日期)",
        "included_north": state.get("included_north", []),
        "included_other": state.get("included_other", []),
        "pending": state.get("pending", []),
    }
    topic_tabs = [music_topic, *state.get("topic_tabs", [])]

    for topic in topic_tabs:
        topic["recent_changes"] = [
            e
            for e in (
                topic.get("included_north", [])
                + topic.get("included_other", [])
                + topic.get("pending", [])
            )
            if is_recent(e)
        ]

    recent_changes = [e for topic in topic_tabs for e in topic["recent_changes"]]

    html = template.render(
        last_updated=state.get("last_updated", today.isoformat()),
        topic_tabs=topic_tabs,
        recent_changes=recent_changes,
        row_class=row_class,
        badge=badge,
    )
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"[render] wrote {OUTPUT_PATH} ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
