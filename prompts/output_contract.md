# 寫入規則 (Output Contract)

> 違反此合約會被 review 拒絕。`refresh.sh` 只 `git add data/state.json docs/index.html`,其他變動不會被 commit,但會在下次 `git pull` 時造成 conflict。

## 唯一可寫檔案

- `data/state.json`

不准動的:
- `docs/*` (HTML 由 render.py 自動產生,你寫了也會被覆蓋)
- `prompts/*`
- `scripts/*`
- `.github/*`
- `README.md`
- 根目錄任何 `.md` / `.sh` / `.py`

## state.json schema

```jsonc
{
  "last_updated": "YYYY-MM-DD",        // 每次跑都更新為 today
  "included_north": [Entry, ...],       // 北北桃符合
  "included_other": [Entry, ...],       // 其他地區同類型參考
  "pending": [PendingEntry, ...],       // 待查
  "excluded": [ExcludedEntry, ...]      // 已查並排除 (給未來避免重評估)
}
```

### Entry (`included_*`)

```jsonc
{
  "id": "kebab-case-stable-id",         // 不可變;新增時取一個穩定的 id
  "organizer": "舉辦單位全稱",
  "location_lines": ["第一行地點", "第二行地點", ...],
  "activity_lines": ["活動:YYYY/M/D – YYYY/M/D ...", "成果展演:..."],
  "registration_line": "報名:即日起至 YYYY/M/D ...",
  "deadline_iso": "YYYY-MM-DD",         // 報名截止日 ISO 格式 (給 should_run.py 與 cleanup 用)
  "links": [
    {"label": "公告頁", "url": "https://..."},
    {"label": "Google 報名表單", "url": "https://..."}
  ],
  "first_seen": "YYYY-MM-DD",           // 第一次加入清單的日期,不可變
  "last_changed": "YYYY-MM-DD",         // 任何欄位有實質變動就更新
  "_internal_notes": "agent 內部判斷依據,不會渲染到 HTML"
}
```

### PendingEntry (`pending`)

```jsonc
{
  "id": "kebab-case",
  "title": "活動完整名稱",
  "region_note": "地區: ...",
  "body_lines": ["說明第一段", "說明第二段"],
  "links": [{"label": "...", "url": "..."}],
  "first_seen": "YYYY-MM-DD",
  "last_changed": "YYYY-MM-DD"
}
```

### ExcludedEntry (`excluded`)

```jsonc
{
  "organizer": "...",
  "url": "...",                          // 若無可填空字串
  "reason": "排除原因 (一句話)",
  "category": "no_2026_camp | out_of_scope_or_closed | no_winds_focus | portal_recheck | no_dates | wrong_year",
  "last_checked": "YYYY-MM-DD"
}
```

## 變動規則

1. **新增 entry**:`first_seen = last_changed = today`
2. **修改既有 entry**:只更 `last_changed = today`,`first_seen` 保持不動
3. **無實質變動**:`last_changed` 不要動 (避免無意義的 badge 出現)
4. **降級 (移到 excluded)**:從原區塊 `pop` 後,推入 `excluded`,寫上 reason、category、last_checked
5. **升級 (pending → included)**:從 pending pop,以新 schema 推入 `included_*`,`first_seen` 用 pending 的 `first_seen`,`last_changed = today`
6. **portal_recheck 類別** (政府入口):每次跑都重查,但更新 `last_checked` 而非建立新 entry

## 輸出

最後步驟:**用 Edit/Write 寫回 `data/state.json`,JSON 格式必須有效 (能被 `python -m json.tool` 解析)**。
