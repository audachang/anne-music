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
FETCH_LIMIT = 24
PAGE_TEXT_LIMIT = 50000
DIRECT_INFO_TERMS = [
    "報名",
    "線上報名",
    "立即報名",
    "報名表",
    "活動日期",
    "課程日期",
    "營隊日期",
    "上課日期",
    "活動地點",
    "上課地點",
    "招生對象",
    "參加對象",
]
GENERIC_RESULT_TERMS = [
    "完整攻略",
    "懶人包",
    "總整理",
    "全解析",
    "推薦",
    "比較",
    "怎麼選",
    "入口",
    "平台",
    "搜尋",
    "查詢",
]
PORTAL_PAGE_TERMS = [
    "各營隊內容頁",
    "我的錄取",
    "錄取名單",
    "搜尋營隊",
    "營隊查詢",
]


class SearchError(RuntimeError):
    """Raised when the upstream search request cannot be completed."""


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    page_text: str = ""


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


class PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self.parts.append(data)

    @property
    def text(self) -> str:
        return normalize_space(" ".join(self.parts))


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


def fetch_page_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return ""
            body = response.read(PAGE_TEXT_LIMIT).decode(
                response.headers.get_content_charset() or "utf-8",
                errors="replace",
            )
    except OSError:
        return ""

    parser = PageTextParser()
    parser.feed(body)
    return parser.text


def has_date_signal(text: str) -> bool:
    return bool(
        re.search(r"20[2-3]\d[./年-]\s*\d{1,2}", text)
        or re.search(r"115\s*[./年-]\s*\d{1,2}", text)
        or re.search(r"\d{1,2}\s*/\s*\d{1,2}", text)
    )


def is_generic_result(title: str, snippet: str, page_text: str) -> bool:
    title_snippet = f"{title} {snippet}"
    if any(term in title_snippet for term in GENERIC_RESULT_TERMS):
        return True
    if any(term in page_text[:5000] for term in PORTAL_PAGE_TERMS):
        return True
    if "報名" not in page_text and any(term in page_text[:3000] for term in GENERIC_RESULT_TERMS):
        return True
    return False


def direct_info_score(keyword: str, result: SearchResult) -> int:
    text = f"{result.title} {result.snippet} {result.page_text}"
    if is_generic_result(result.title, result.snippet, result.page_text):
        return 0
    if keyword not in f"{result.title} {result.snippet} {result.page_text[:5000]}":
        return 0

    score = 0
    if keyword in text:
        score += 1
    if "夏令營" in text or "暑期營" in text or "營隊" in text:
        score += 2
    if "報名" in text:
        score += 3
    if has_date_signal(text):
        score += 2
    if any(place in text for place in ["台北", "臺北", "新北", "桃園"]):
        score += 1
    if any(term in text for term in DIRECT_INFO_TERMS):
        score += 2
    return score


def direct_results(keyword: str, max_results: int) -> list[SearchResult]:
    candidates = search_web(keyword, max_results=max(FETCH_LIMIT, max_results * 4))
    accepted: list[SearchResult] = []
    for candidate in candidates:
        candidate.page_text = fetch_page_text(candidate.url)
        if direct_info_score(keyword, candidate) < 7:
            continue
        accepted.append(candidate)
        if len(accepted) >= max_results:
            break
    return accepted


def result_to_entry(keyword: str, result: SearchResult, index: int, today: str) -> dict:
    snippet = result.snippet or excerpt_page_text(result.page_text)
    return {
        "id": f"{stable_id(keyword)}-{index + 1}",
        "organizer": result.title,
        "location_lines": ["直接報名資訊頁，詳細地點請以來源頁面為準"],
        "activity_lines": [f"摘要:{snippet}"],
        "registration_line": "報名:來源頁面含報名資訊，請開啟確認名額與截止日",
        "deadline_iso": today,
        "links": [{"label": "報名資訊頁", "url": result.url}],
        "first_seen": today,
        "last_changed": today,
        "_internal_notes": f"User-triggered direct-info web search keyword: {keyword}",
    }


def excerpt_page_text(page_text: str) -> str:
    if not page_text:
        return "來源頁面含報名相關資訊；請開啟確認活動日期、報名資格與截止日。"
    for marker in ["報名", "活動日期", "課程日期", "營隊日期"]:
        index = page_text.find(marker)
        if index >= 0:
            start = max(0, index - 60)
            return page_text[start : start + 220]
    return page_text[:220]


def search_topic(keyword: str, max_results: int = MAX_RESULTS) -> dict:
    clean_keyword = normalize_space(keyword)
    if not clean_keyword:
        raise ValueError("keyword is required")

    today = date.today().isoformat()
    results = direct_results(clean_keyword, max_results=max_results)
    entries = [
        result_to_entry(clean_keyword, result, index, today)
        for index, result in enumerate(results)
    ]
    return {
        "id": stable_id(clean_keyword),
        "label": clean_keyword,
        "title": f"Anne 2026 {clean_keyword}夏令營搜尋",
        "subtitle": f"即時網路搜尋「{make_query(clean_keyword)}」；已過濾需再自行搜尋的彙整頁，只保留直接報名資訊頁。",
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
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
