#!/usr/bin/env bash
# VPS vault sync — called by second-brain-vaultsync.service
# Must be run from project root.

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON="$PROJECT_ROOT/.claude/scripts/.venv/bin/python"
LOG="$PROJECT_ROOT/.claude/scripts/vault_sync_runs.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] vault sync start" >> "$LOG"

# Stage and commit any local Memory/ changes. Scoped to Memory/ on both the diff
# check and the commit itself so this never sweeps up unrelated staged changes into
# a mislabeled "vault sync" commit — anything else staged stays staged, untouched.
git add Memory/
if ! git diff --quiet --cached -- Memory/; then
    git commit -m "vault sync $(date '+%Y-%m-%d %H:%M')" -- Memory/ >> "$LOG" 2>&1
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
