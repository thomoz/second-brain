# Run a my-trader / briefs-finance CLI command on the VPS over SSH.
# investments.db lives only on the VPS now (see .agent/plans/investments-db-ssh-single-source.md) --
# this wrapper is how local Claude Code sessions interact with it.
#
# Usage:
#   .\scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker VRTX"
#   .\scripts\invoke_investments.ps1 -Package briefs-finance -Command "assess --ticker KGC --output markdown"
#   .\scripts\invoke_investments.ps1 -Package goat -Command "scan-sectors"
#   .\scripts\invoke_investments.ps1 -Package fourteen-signals -Command "daily-check"
#
# goat/fourteen-signals share the same VPS-only investments.db as my-trader/briefs-
# finance -- never run them via a local `uv run --directory investments/goat ...`;
# that would silently create a fresh, empty local investments.db (init_db() creates
# on first open) and reintroduce the split this wrapper exists to avoid.
#
# Known limitation: -Command is reconstructed and re-parsed by the remote bash, so
# double-quoted segments follow bash quoting rules -- a literal "$" inside one (e.g.
# --notes "worth $340") gets bash-expanded to empty rather than preserved literally.
# Avoid "$", backticks, and backslashes inside quoted argument values.

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("my-trader", "briefs-finance", "goat", "fourteen-signals")]
    [string]$Package,

    [Parameter(Mandatory=$true)]
    [string]$Command
)

$VPS = "secondbrain@137.184.102.104"
$REMOTE_DIR = "/home/secondbrain/second-brain"

$PACKAGES = @{
    "my-trader"        = @{ Dir = "my-trader"; Module = "mytrader.main" }
    "briefs-finance"   = @{ Dir = "briefs-finance"; Module = "scripts.main" }
    "goat"             = @{ Dir = "goat"; Module = "goat.main" }
    "fourteen-signals" = @{ Dir = "fourteen-crash-signals-daily-check"; Module = "fourteen_crash_signals_daily_check.main" }
}

$pkg = $PACKAGES[$Package]
$remoteCommand = "cd $REMOTE_DIR/investments/$($pkg.Dir) && $REMOTE_DIR/investments/.venv/bin/python -m $($pkg.Module) $Command"

# The command string crosses two shells (local PowerShell -> ssh -> remote bash).
# Base64-encoding it end to end avoids any quoting mismatch between the two --
# arguments like --notes "some text" survive intact instead of being mangled by
# PowerShell 5.1's native-command argument passing.
$bytes = [System.Text.Encoding]::UTF8.GetBytes($remoteCommand)
$encoded = [Convert]::ToBase64String($bytes)

$output = ssh -o ConnectTimeout=10 $VPS "echo $encoded | base64 -d | bash"
$exitCode = $LASTEXITCODE
$output | ForEach-Object { Write-Host $_ }

if ($exitCode -ne 0) {
    Write-Host "ERROR: remote command failed (exit $exitCode): $remoteCommand" -ForegroundColor Red
    exit $exitCode
}
