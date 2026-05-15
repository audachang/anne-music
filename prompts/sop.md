# 操作 SOP — Anne 2026 暑期管樂團/管樂營 維護

> 此文件為 cron 觸發的 Claude Code agent 的執行手冊。每次執行請完整讀過。

## 1. 目標

為 Anne 維護 2026 暑期可參加的管樂團/管樂營活動清單,範圍以**北北桃 (臺北市、新北市、桃園市)** 為主,結果寫入 `data/state.json`。HTML 由 `scripts/render.py` 從 state.json 自動渲染,**不需手動編輯 HTML**。

頁面已改為主題分頁:既有 `included_north` / `included_other` / `pending` 是預設「音樂／管樂」分頁；戲劇表演、音樂劇等其他主題放在 `topic_tabs`。

對象:**國小高年級、單簧管學習約一年**。

## 2. 篩選條件

### 納入 (`included_north`)
- 地區在臺北市、新北市、桃園市
- 2026 / 民國 115 年暑期或暑假相關活動
- 內容與管樂、管樂團、管樂營、木管/銅管合奏、樂團新生募集或暑期集訓相關;或為民間樂團/協會主辦的暑期音樂營,含木管編制可收單簧管者
- 適合國小高年級,或至少沒有明顯排除一年管樂經驗者
- **必須**確認活動日期
- **必須**確認報名日期或報名截止日
- **必須**有可連結的報名頁、公告頁、報名表或附件頁
- 報名尚未截止,或仍有明確候補/遞補管道

### 納入但地區不符 (`included_other`)
- 中南東部同類型營隊,其他條件全部符合,但**樂器條件不符 Anne 也保留為附表參考**

### 待查 (`pending`)
- 主辦單位已宣告開放報名,但缺活動日期或報名截止日

### 排除 (`excluded`)
- 已過期年份 (2025、114 年暑期)
- 沒有活動日期或報名日期
- 只是音樂會、成果發表、甄選結果、學校例行社團介紹
- 只適合高中、大學生、專業團體,或要求高階能力
- 國樂團、弦樂團、合唱、一般音樂營若沒有管樂主軸**且**樂團未明確開放單簧管
- 政府補助申請入口或活動彙整入口若沒有具體管樂活動 (歸 `category: portal_recheck`,定期重查)
- 報名截止日已過且實際表單已關閉

## 3. 執行步驟

每次跑時,**依序執行**:

### Step A — 讀取既有狀態
1. 讀 `data/state.json`,記下:
   - `included_north` / `included_other` / `pending` 中各 entry 的 `id`
   - `excluded` 中的 organizer / url (避免重新評估)
2. 讀 `prompts/output_contract.md` (寫入規則)

### Step B — 重跑搜尋查詢
**通用 (北北桃為主)**:
- `115 暑期 管樂團 新生募集 台北 國小 報名`
- `115 暑期 管樂團 新生募集 新北 國小 報名`
- `115 暑期 管樂團 新生募集 桃園 國小 報名`
- `2026 暑期 管樂營 國小 台北 新北 桃園 報名`
- `"115年度" "暑期管樂育樂營"`
- `"2026" "暑期管樂營" "國小" "報名" "台北"`
- `"2026" "暑期管樂營" "國小" "報名" "新北"`
- `site:ntpc.edu.tw 115 暑期 管樂團 營隊 報名`
- `site:tyc.edu.tw 115 暑期 管樂團 營隊 報名`
- `site:tp.edu.tw 115 暑期 管樂團 營隊 報名`

**民間樂團/協會**:
- `愛樂 青少年 管弦樂團 2026 暑期 音樂營 國小 報名 北部`
- `台北愛樂少年管樂團 2026 暑期 音樂營 招生 報名 簡章`
- `"陽光台北交響樂團" 2026 暑期音樂營 國小 木管 弦樂 銅管`
- `台北青年管樂團 TSB 2026 陽光管樂夏令營 第18屆 日期 報名`

**中南東部同類型 (供 `included_other`)**:
- `2026 暑期音樂營 國小 高年級 樂團 木管 報名 台中 高雄 台南 簡章`
- `"管樂團" "暑期" 招生 簡章 2026 國小 中部 南部 報名`

**戲劇表演 / 音樂劇分頁 (供 `topic_tabs`)**:
- `2026 夏令營 戲劇表演 台北 國小 報名`
- `115 夏令營 戲劇 表演 台北 國小 報名`
- `2026 音樂劇 夏令營 台北 國小 報名`
- `115 音樂劇 夏令營 國小 台北 報名`
- `site:tp.edu.tw 115 音樂劇 夏令營 國小 報名`

### Step C — 對每個新候選驗證
1. WebFetch 候選 URL 取得頁面內文 (限制:URL 過長 / Wix 動態頁可能失敗,失敗時改用 WebSearch 摘要)
2. 確認四欄:**舉辦單位、地點、日期 (含活動日期與報名截止日)、報名網頁**
3. 確認是否適合 Anne (國小高年級、一年管樂經驗或可初學、含管樂/單簧管)
4. 對照 `excluded` 清單,若已存在且理由仍然成立 → 跳過
5. 對照 `pending` 清單,若已取得明確日期 → 升級到 `included_*`

### Step D — 已存在 entry 的驗證
對 `included_north` / `included_other` 中的每個 entry:
1. WebFetch 其主要 URL,確認活動仍存在
2. 若報名截止日已過 (`deadline_iso < today`) 且無候補管道 → 移到 `excluded`,`category: out_of_scope_or_closed`
3. 若日期/連結有變動 → 更新欄位,`last_changed = today`

### Step E — 寫入 state.json
- `last_updated = today`
- 新增 entry:`first_seen = last_changed = today`
- 修改 entry:只更 `last_changed = today`,`first_seen` 不動
- 移除 entry:不要直接刪除,移到 `excluded` 區塊保留歷史

## 4. 已知陷阱

1. **URL 含中文編碼** (如弘道國中) — WebFetch 可能不穩,先 WebSearch 確認頁面仍在線
2. **Wix 動態網站** (如 tsb.org.tw) — WebFetch 取到的 HTML 多為骨架,改靠 WebSearch 摘要
3. **長 FB 貼文 URL** — 會被 WebFetch 拒絕 (URL exceeds maximum length),改用主辦單位官網/粉專首頁
4. **年份混淆** — 2025 / 114 年舊資訊不算,務必確認年份
5. **入口型網站** (如 holiday.tp.edu.tw、camp.ntpc.edu.tw、桃園教育局) — 已歸 `category: portal_recheck`,持續重查但不放正式表格,直到看到具體管樂課程
6. **新北 camp.ntpc.edu.tw** 5/19 中午 12:00 開放報名後應特別檢查
7. **TSB 第 18 屆** 在 `pending`,從 FB/官網取得具體日期後升級

## 5. 樂器條件提醒

**衛武營 2026 銅管/打擊組** 已在 `included_other`,但**單簧管不在收錄樂器**;保留僅作同類型結構參考。若使用者要求移除可改放 `excluded`。

## 6. 不要做的事

- 不要編輯 `docs/index.html` (由 render.py 渲染)
- 不要編輯 `prompts/`、`scripts/`、`.github/`、任何 .py / .sh / .j2 檔
- 不要新增其他資料檔
- 不要為 `included_*` 或 `topic_tabs[].included_*` 加入「費用、招生對象、樂器清單、聯絡電話、課程特色」欄位 (這些只能寫進 `_internal_notes`,不會渲染)
