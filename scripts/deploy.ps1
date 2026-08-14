# Deploy latest changes to DigitalOcean VPS
# Run after git push: .\scripts\deploy.ps1

$VPS = "secondbrain@137.184.102.104"
$REMOTE_DIR = "/home/secondbrain/second-brain"

# Determine current local branch to deploy the same one to VPS
$BRANCH = git rev-parse --abbrev-ref HEAD

# Every timer that touches the repo (git commits/writes files inside it) must be
# stopped for the duration of the deploy — vaultsync runs every 2 minutes and does
# its own git commit/pull/push, so left running it can race the steps below.
# NOTE: investments/ (my-trader + briefs-finance) is deliberately not run on the VPS —
# investment tooling stays local-only. Its systemd unit is stopped/disabled and the
# VPS checkout excludes investments/ via sparse-checkout. Do not re-add its timer here.
$TIMERS = @(
    "second-brain-heartbeat.timer",
    "second-brain-vaultsync.timer",
    "second-brain-reflect.timer"
)

function Invoke-Remote {
    param([string]$Command, [switch]$IgnoreFailure)
    $output = ssh $VPS $Command
    $output | ForEach-Object { Write-Host $_ }
    if (-not $IgnoreFailure -and $LASTEXITCODE -ne 0) {
        Write-Host "ERROR: remote command failed (exit $LASTEXITCODE): $Command" -ForegroundColor Red
        Write-Host "Timers are left stopped. Investigate on the VPS before restarting them." -ForegroundColor Red
        exit 1
    }
    return $output
}

function Stop-Timers {
    Write-Host "Stopping timers..."
    foreach ($t in $TIMERS) {
        ssh $VPS "sudo systemctl stop $t 2>/dev/null || true"
    }
}

function Start-Timers {
    Write-Host "Restarting timers..."
    foreach ($t in $TIMERS) {
        ssh $VPS "sudo systemctl start $t 2>/dev/null || true"
    }
}

function Show-ConflictHelp {
    Write-Host ""
    Write-Host "=======================================================" -ForegroundColor Red
    Write-Host "CONFLICT: git stash pop failed on the VPS during deploy." -ForegroundColor Red
    Write-Host "Timers are left STOPPED so nothing runs against a" -ForegroundColor Red
    Write-Host "conflicted working tree. The stash was NOT dropped." -ForegroundColor Red
    Write-Host ""
    Write-Host "To resolve:" -ForegroundColor Yellow
    Write-Host "  ssh $VPS"
    Write-Host "  cd $REMOTE_DIR"
    Write-Host "  git status"
    Write-Host "  # for each unmerged file, compare 'git show :2:<file>' (pushed)"
    Write-Host "  # against 'git show :3:<file>' (VPS's stashed local state) before"
    Write-Host "  # picking a side, especially for the binary investments.db"
    Write-Host "  git add <resolved files>"
    Write-Host "  git commit"
    Write-Host "  git stash drop"
    Write-Host "  git push origin $BRANCH"
    Write-Host "Then restart timers manually or re-run deploy.ps1:"
    foreach ($t in $TIMERS) { Write-Host "  sudo systemctl start $t" }
    Write-Host "=======================================================" -ForegroundColor Red
}

Stop-Timers

Write-Host "Committing any pending Memory/ changes on VPS..."
Invoke-Remote "cd $REMOTE_DIR && git add Memory/"

Write-Host "Stashing any uncommitted local changes on VPS..."
$stashOutput = Invoke-Remote "cd $REMOTE_DIR && git stash"
$hadStash = -not ($stashOutput -match "No local changes to save")

Write-Host "Fetching + pulling latest changes (branch: $BRANCH)..."
Invoke-Remote "cd $REMOTE_DIR && git fetch origin"
Invoke-Remote "cd $REMOTE_DIR && git checkout $BRANCH"
Invoke-Remote "cd $REMOTE_DIR && git pull --no-rebase origin $BRANCH"

if ($hadStash) {
    Write-Host "Reapplying stashed local changes..."
    ssh $VPS "cd $REMOTE_DIR && git stash pop"
    if ($LASTEXITCODE -ne 0) {
        Show-ConflictHelp
        exit 1
    }
}

Start-Timers
Write-Host "Done."
