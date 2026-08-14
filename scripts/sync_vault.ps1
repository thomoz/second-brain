# Windows vault sync -- runs every 2 minutes via Task Scheduler
# Update PROJECT_PATH to your actual repo path.
param(
    [string]$ProjectPath = "O:\AI\Dynamous\Courses\second-brain-workshop"
)

Set-Location $ProjectPath
$log = Join-Path $ProjectPath ".claude\scripts\vault_sync_runs.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

Add-Content -Path $log -Value "[$timestamp] vault sync start"

git add Memory/
$staged = git diff --cached --name-only -- Memory/
if ($staged) {
    # Scoped to Memory/ so this never sweeps up unrelated staged changes (e.g. a
    # `git mv`/`git add` left uncommitted elsewhere in the repo when this timer fires
    # every 2 minutes) into a mislabeled "vault sync" commit. Anything else staged
    # stays staged, untouched, for whoever/whatever staged it to commit deliberately.
    git commit -m "vault sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -- Memory/ 2>&1 | Add-Content -Path $log
}

$before = git rev-parse HEAD
git pull --no-rebase 2>&1 | Add-Content -Path $log
$after = git rev-parse HEAD

# Reindex only if Memory/ changed
if ($before -ne $after) {
    $changed = git diff --name-only $before $after | Where-Object { $_ -match "^Memory/" }
    if ($changed) {
        Add-Content -Path $log -Value "[$timestamp] Memory/ changed - reindexing..."
        $python = Join-Path $ProjectPath ".claude\scripts\.venv\Scripts\python.exe"
        & $python (Join-Path $ProjectPath ".claude\scripts\memory_index.py") 2>&1 | Add-Content -Path $log
    }

    # Handoff toast fires immediately off this same pull instead of waiting for the
    # hourly SecondBrain-HandoffCheck task -- that task stays registered as a
    # fallback in case this sync itself stalls (see handoff_check.py docstring).
    $handoffChanged = $changed | Where-Object { $_ -eq "Memory/whatsapp-handoff-messages-for-local-session.md" }
    if ($handoffChanged) {
        Add-Content -Path $log -Value "[$timestamp] handoff file changed - checking for new entries..."
        $python = Join-Path $ProjectPath ".claude\scripts\.venv\Scripts\python.exe"
        & $python (Join-Path $ProjectPath ".claude\scripts\handoff_check.py") 2>&1 | Add-Content -Path $log
    }
}

git push origin HEAD 2>&1 | Add-Content -Path $log
Add-Content -Path $log -Value "[$timestamp] vault sync done"
