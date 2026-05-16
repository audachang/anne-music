#!/usr/bin/env python3
"""Search the web for a user-supplied camp topic and return tab-shaped JSON.

This module is intentionally dependency-free so it can run on the same small
server that already refreshes the static site. It uses DuckDuckGo's HTML
endpoint server-side; browsers should call search_server.py instead of trying
to fetch search engines directly from GitHub Pages.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

USER_AGENT = "anne-music-topic-search/1.0 (+https://audachang.github.io/anne-music/)"
SEARCH_URL = "https://duckduckgo.com/html/"
MAX_RESULTS = 8


class SearchError(RuntimeError):
    """Raised when the upstream search request cannot be completed."""


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_title = False
        self._in_snippet = False
        self._current_url = ""
        self._title_parts: list[str] = []
        self._snippet_parts: list[str] = []
        self._pending_result: tuple[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = set(attr.get("class", "").split())
        if tag == "a" and "result__a" in classes:
            self._in_title = True
            self._current_url = clean_duckduckgo_url(attr.get("href", ""))
            self._title_parts = []
        elif tag in {"a", "div"} and "result__snippet" in classes:
            self._in_snippet = True
            self._snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_snippet:
            self._snippet_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            title = normalize_space(" ".join(self._title_parts))
            if title and self._current_url:
                self._pending_result = (title, self._current_url)
            self._in_title = False
        elif self._in_snippet and tag in {"a", "div"}:
            snippet = normalize_space(" ".join(self._snippet_parts))
            if self._pending_result:
                title, url = self._pending_result
                self.results.append(SearchResult(title=title, url=url, snippet=snippet))
                self._pending_result = None
            self._in_snippet = False


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def clean_duckduckgo_url(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlparse(html.unescape(value))
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    if parsed.scheme in {"http", "https"}:
        return urllib.parse.urlunparse(parsed)
    if value.startswith("//"):
        return "https:" + value
    return value


def make_query(keyword: str) -> str:
    return f"2026 115 夏令營 {keyword} 台北 新北 桃園 國小 報名 日期"


def stable_id(keyword: str) -> str:
    normalized = keyword.lower().encode("utf-8")
    value = 0
    for byte in normalized:
        value = ((value << 5) - value + byte) & 0xFFFFFFFF
    return f"web-{value:x}"


def search_web(keyword: str, max_results: int = MAX_RESULTS) -> list[SearchResult]:
    query = make_query(keyword)
    params = urllib.parse.urlencode({"q": query, "kl": "tw-tzh"})
    request = urllib.request.Request(
        f"{SEARCH_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise SearchError(f"search request failed: {exc}") from exc

    parser = DuckDuckGoHTMLParser()
    parser.feed(body)

    seen: set[str] = set()
    deduped: list[SearchResult] = []
    for result in parser.results:
        if not result.url or result.url in seen:
            continue
        seen.add(result.url)
        deduped.append(result)
        if len(deduped) >= max_results:
            break
    return deduped


def result_to_entry(keyword: str, result: SearchResult, index: int, today: str) -> dict:
    snippet = result.snippet or "搜尋結果未提供摘要；請開啟連結確認活動日期、報名資格與截止日。"
    return {
        "id": f"{stable_id(keyword)}-{index + 1}",
        "organizer": result.title,
        "location_lines": ["搜尋結果，地點待開啟來源確認"],
        "activity_lines": [f"摘要:{snippet}"],
        "registration_line": "報名:請依來源頁面確認",
        "deadline_iso": today,
        "links": [{"label": "搜尋結果來源", "url": result.url}],
        "first_seen": today,
        "last_changed": today,
        "_internal_notes": f"User-triggered web search keyword: {keyword}",
    }


def search_topic(keyword: str, max_results: int = MAX_RESULTS) -> dict:
    clean_keyword = normalize_space(keyword)
    if not clean_keyword:
        raise ValueError("keyword is required")

    today = date.today().isoformat()
    results = search_web(clean_keyword, max_results=max_results)
    entries = [
        result_to_entry(clean_keyword, result, index, today)
        for index, result in enumerate(results)
    ]
    return {
        "id": stable_id(clean_keyword),
        "label": clean_keyword,
        "title": f"Anne 2026 {clean_keyword}夏令營搜尋",
        "subtitle": f"即時網路搜尋「{make_query(clean_keyword)}」；結果需開啟來源頁面確認細節。",
        "included_heading": "即時搜尋結果",
        "other_heading": "其他地區搜尋結果",
        "pending_heading": "待確認結果",
        "included_north": entries,
        "included_other": [],
        "pending": [],
        "searched_at": today,
        "query": make_query(clean_keyword),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("keyword")
    parser.add_argument("--max-results", type=int, default=MAX_RESULTS)
    args = parser.parse_args()

    try:
        payload = search_topic(args.keyword, max_results=args.max_results)
    except (SearchError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
