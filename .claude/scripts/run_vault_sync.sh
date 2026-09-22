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

# Pull remote changes; note which Memory/ files changed.
#
# Stash-wrap the pull -- added 2026-09-22 after a real ~30-hour outage: a deploy
# from the dev machine writes changed .py files straight onto the VPS filesystem
# (it does not commit them there), which leaves those files locally modified in
# the VPS's git tree. The next vault-sync cycle's plain `git pull` then refused
# to merge ("local changes would be overwritten"), and because that line had no
# `|| true` guard, `set -e` above killed the whole script right there -- every
# cycle, silently, before it ever reached the git push at the bottom. Commits
# kept piling up locally on the VPS for a day and a half with nothing ever
# reaching GitHub, and nothing logged an error anyone would notice. Stashing any
# leftover modified-tracked-file state before the pull (and restoring it after)
# means a same-cycle deploy collision self-heals automatically in the common
# case (the stashed content and the incoming commit are the same change) instead
# of wedging the whole sync pipeline.
STASH_OUT=$(git stash push -m "vault-sync-autostash $(date '+%Y-%m-%d %H:%M')" 2>&1) || true
echo "$STASH_OUT" >> "$LOG"
STASHED=0
if [[ "$STASH_OUT" != *"No local changes to save"* ]]; then
    STASHED=1
fi

BEFORE=$(git rev-parse HEAD)
git pull --no-rebase >> "$LOG" 2>&1 || echo "pull failed (non-fatal) -- see error above" >> "$LOG"
AFTER=$(git rev-parse HEAD)

if [ "$STASHED" = "1" ]; then
    if ! git stash pop >> "$LOG" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] stash pop conflict after pull -- needs manual" \
             "resolution (git status / git stash list on the VPS)" >> "$LOG"
    fi
fi

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
