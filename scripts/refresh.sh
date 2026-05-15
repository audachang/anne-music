#!/bin/bash
# refresh.sh — cron entrypoint. Pulls, gates, runs Claude Code to refresh
# data/state.json, re-renders docs/index.html, commits + pushes if changed.
#
# Cron line (server, every day 01:00 UTC = 09:00 Asia/Taipei):
#   0 1 * * * /home/aclexp/anne-music/scripts/refresh.sh >> /home/aclexp/anne-music/.cron.log 2>&1
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

TODAY="$(date -I)"
echo "===== refresh start $TODAY ====="

# 1. Sync remote (in case of manual edits via web UI)
git pull --ff-only origin main || { echo "[err] git pull failed"; exit 1; }

# 2. Gate — run only on Monday or within 7d of a deadline
if ! python3 scripts/should_run.py; then
  echo "===== skipped ====="
  exit 0
fi

# 3. Run Claude Code agent. --dangerously-skip-permissions is required for
# headless cron use; the maintain prompt + output_contract.md restrict the
# agent to writing only data/state.json.
PROMPT_FILE=".maintain-prompt.md"
if ! command -v claude >/dev/null 2>&1; then
  echo "[err] claude CLI not in PATH. Install via: npm i -g @anthropic-ai/claude-code"
  exit 1
fi

# Inject today's date into the prompt
PROMPT_RENDERED="$(sed "s/{{TODAY}}/$TODAY/g" "$PROMPT_FILE")"

echo "----- claude run -----"
claude --dangerously-skip-permissions -p "$PROMPT_RENDERED" || {
  echo "[err] claude run failed"
  exit 1
}

# 4. Re-render HTML deterministically
python3 scripts/render.py

# 5. Commit + push if state.json or index.html changed
if [ -n "$(git status --porcelain data/state.json docs/index.html)" ]; then
  git add data/state.json docs/index.html
  git commit -m "auto: refresh $TODAY"
  git push origin main
  echo "[ok] pushed update for $TODAY"
else
  echo "[ok] no changes for $TODAY"
fi

echo "===== refresh done $TODAY ====="
