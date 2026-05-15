# anne-music

自動維護 Anne 2026 暑期管樂團/管樂營清單,結果發佈到 GitHub Pages:
**https://audachang.github.io/anne-music/**

## 架構

```
       ┌──────────────────────────────────────────┐
       │ braina-aclexp (Hetzner)                  │
       │  cron 每天 01:00 UTC                      │
       │   └─ scripts/refresh.sh                  │
       │       ├─ git pull                        │
       │       ├─ should_run.py (gate)            │
       │       ├─ claude --bare (subscription)    │
       │       │    └─ 寫 data/state.json         │
       │       ├─ render.py (state → HTML)        │
       │       └─ git add && commit && push       │
       └──────────────────────────────────────────┘
                          │
                          ▼  push to main
       ┌──────────────────────────────────────────┐
       │ github.com/audachang/anne-music          │
       │  Pages: branch=main, path=/docs          │
       └──────────────────────────────────────────┘
                          │
                          ▼  serve
                https://audachang.github.io/anne-music/
```

**設計要點**
- Agent (Claude Code) **只寫 `data/state.json`**;HTML 由 `render.py` 從 JSON 確定性渲染。
- `should_run.py` 在「非週一 + 7 天內無 deadline」時直接 exit 1,讓 cron 早退。
- 每次 commit message 為 `auto: refresh YYYY-MM-DD`,git log 即變更日誌。

## 檔案

| 路徑 | 用途 |
|---|---|
| `data/state.json` | 唯一可變的資料來源 (agent 寫入) |
| `docs/index.html` | GitHub Pages 提供;由 `render.py` 產生 |
| `docs/_template.html.j2` | Jinja2 模板 |
| `scripts/refresh.sh` | cron entrypoint |
| `scripts/render.py` | state.json → HTML |
| `scripts/should_run.py` | cron gate |
| `prompts/sop.md` | 完整操作 SOP (給 agent) |
| `prompts/output_contract.md` | 寫入規則 (給 agent) |
| `.maintain-prompt.md` | cron 餵給 `claude --bare -p` 的入口 prompt |

## Server bootstrap (一次性)

SSH 到 `aclexp@89.167.10.76`,依序執行:

```bash
# 1. 安裝官方 Claude Code CLI
npm install -g @anthropic-ai/claude-code

# 2. 確認 PATH 包含 ~/.npm-global/bin
echo $PATH | grep -q npm-global || echo 'export PATH=$HOME/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
which claude

# 3. Claude Code OAuth 登入 (subscription)
claude
# → 跟隨指示,把 URL 在本機瀏覽器開啟,登入後把 code 貼回 server terminal
# → 完成後憑證存在 ~/.claude/.credentials.json

# 4. 重新認證 gh CLI — 用既有 PAT 檔
#    PAT 檔在 ~/.ssh/.github_pat_audachang,環境變數格式 (GITHUB_TOKEN=ghp_xxx)
set -a; source ~/.ssh/.github_pat_audachang; set +a
echo "$GITHUB_TOKEN" | gh auth login --with-token
unset GITHUB_TOKEN
gh auth status   # 確認 ✓ Logged in to github.com account audachang
# 之後 git push 會自動透過 ~/.gitconfig 裡的 `gh auth git-credential` helper 取 token,cron 也適用

# 5. 確認 Python 套件
pip3 install --user jinja2

# 6. Clone repo
cd ~
git clone https://github.com/audachang/anne-music.git
cd anne-music

# 7. 測跑一次 (可選,不會 commit 因為今天剛 push 完)
chmod +x scripts/refresh.sh scripts/render.py scripts/should_run.py
./scripts/refresh.sh

# 8. 安裝 cron
crontab -e
# 加入這一行:
# 0 1 * * * /home/aclexp/anne-music/scripts/refresh.sh >> /home/aclexp/anne-music/.cron.log 2>&1
```

## 本地開發 / 手動更新

```bash
# 編輯 data/state.json,然後:
python3 scripts/render.py
# 開啟 docs/index.html 預覽
```

## 監控

`refresh.sh` 失敗會留在 `.cron.log`。要被通知,在 `refresh.sh` 末尾加 webhook:

```bash
# 例:推 ntfy
trap 'curl -d "anne-music refresh failed" ntfy.sh/<your-topic>' ERR
```

## 風險 / 灰色地帶

- **Claude Code subscription on cron** — Anthropic 沒明文禁止 headless 使用,但屬個人帳號自動化的灰區。若 token 失效,cron 會默默失敗,記得監控 `.cron.log`。
- **`--dangerously-skip-permissions`** — 必要 (cron 無互動);agent 受 `output_contract.md` 限制只寫 `data/state.json`,但理論上仍有能力動其他檔案。

## 變更歷史

git log 即變更歷史。`auto: refresh ...` 為自動 commit。
