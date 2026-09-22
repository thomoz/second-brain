#!/usr/bin/env bash
# VPS vault sync — called by second-brain-vaultsync.service
# Must be run from project root.

set -euo pipefail
shopt -s nullglob  # so investments/*/*.md globs vanish (not literal-match-fail) if a dir is ever empty
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON="$PROJECT_ROOT/.claude/scripts/.venv/bin/python"
LOG="$PROJECT_ROOT/.claude/scripts/vault_sync_runs.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] vault sync start" >> "$LOG"

# Stage and commit any local Memory/ changes, plus every investments/ package's
# auto-generated report .md files (investments.db itself is deliberately excluded --
# binary SQLite conflicts get resolved manually via additive-union merges, see
# deploy.ps1's Show-ConflictHelp). Scoped on both the diff check and the commit
# itself so this never sweeps up unrelated staged changes into a mislabeled
# "vault sync" commit -- anything else staged stays staged, untouched.
#
# NOTE: this list does not auto-discover new investments/ packages -- a new
# package's report .md files silently never get synced until its glob is added
# here (found 2026-09-22: superinvestor-filings, ai-resistant-moat-scanner, and
# fourteen-crash-signals-daily-check had been missing since each was built,
# report files piling up uncommitted on the VPS with no error). Add a new
# package's `investments/<pkg>/*.md` glob here as soon as it starts writing a
# report file, not after someone notices it's stale.
SYNC_PATHS=(
    Memory/
    investments/goat/*.md
    investments/my-trader/*.md
    investments/superinvestor-filings/*.md
    investments/ai-resistant-moat-scanner/*.md
    investments/fourteen-crash-signals-daily-check/*.md
)
git add "${SYNC_PATHS[@]}"
if ! git diff --quiet --cached -- "${SYNC_PATHS[@]}"; then
    git commit -m "vault sync $(date '+%Y-%m-%d %H:%M')" -- "${SYNC_PATHS[@]}" >> "$LOG" 2>&1
fi

# Pull remote changes; note which Memory/ files changed
BEFORE=$(git rev-parse HEAD)
git pull --no-rebase >> "$LOG" 2>&1
AFTER=$(git rev-parse HEAD)

# Re-index only if Memory/ changed in the pull
if [ "$BEFORE" != "$AFTER" ]; then
    CHANGED=$(git diff --name-only "$BEFORE" "$AFTER" | grep "^Memory/" || true)
    if [ -n "$CHANGED" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Memory/ changed — reindexing..." >> "$LOG"
        cd "$PROJECT_ROOT/.claude/scripts"
        "$PYTHON" memory_index.py >> "$LOG" 2>&1 || echo "reindex failed (non-fatal)" >> "$LOG"
        cd "$PROJECT_ROOT"
    fi
fi

git push origin HEAD >> "$LOG" 2>&1 || echo "push failed (non-fatal)" >> "$LOG"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] vault sync done" >> "$LOG"
