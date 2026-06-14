# Windows vault sync — runs every 2 minutes via Task Scheduler
# Update PROJECT_PATH to your actual repo path.
param(
    [string]$ProjectPath = "O:\AI\Dynamous\Courses\second-brain-workshop"
)

Set-Location $ProjectPath
$log = Join-Path $ProjectPath ".claude\scripts\vault_sync_runs.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

Add-Content -Path $log -Value "[$timestamp] vault sync start"

git add Memory/
$staged = git diff --cached --name-only
if ($staged) {
    git commit -m "vault sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 2>&1 | Add-Content -Path $log
}

$before = git rev-parse HEAD
git pull --no-rebase origin HEAD 2>&1 | Add-Content -Path $log
$after = git rev-parse HEAD

# Reindex only if Memory/ changed
if ($before -ne $after) {
    $changed = git diff --name-only $before $after | Where-Object { $_ -match "^Memory/" }
    if ($changed) {
        Add-Content -Path $log -Value "[$timestamp] Memory/ changed — reindexing..."
        $python = Join-Path $ProjectPath ".claude\scripts\.venv\Scripts\python.exe"
        & $python (Join-Path $ProjectPath ".claude\scripts\memory_index.py") 2>&1 | Add-Content -Path $log
    }
}

git push origin HEAD 2>&1 | Add-Content -Path $log
Add-Content -Path $log -Value "[$timestamp] vault sync done"
