# Feature: Phase 9 — Deployment (Windows Task Scheduler + VPS + Vault Sync)

The following plan should be complete, but validate codebase patterns and task sanity before
implementing. Pay special attention to entry-point paths, uv venv location on VPS, and the
`SB_AGENT_BACKEND` env var that controls which LLM backend runs.

## Feature Description

Automate the Second Brain on two machines: Windows (local) and a DigitalOcean VPS (24/7).
Windows Task Scheduler handles local automation until the VPS is live, then hands off.
Vault sync via git keeps `Memory/` in sync between both machines every 2 minutes using a
custom `concat-both` merge driver that prevents merge conflicts in append-only daily logs.
After VPS handoff, only the VaultSync task remains on Windows.

## User Story

As Shaun running a 5-business Second Brain,
I want the heartbeat, reflection, and WhatsApp bot running 24/7 without manual intervention,
So that the brain monitors email/calendar and surfaces insights even when my laptop is off.

## Problem Statement

Currently all scripts run only when manually triggered in a Claude Code session.
The brain goes dark whenever the session ends. Daily logs accumulate only during active
work sessions, and there's no vault sync between machines — so starting the VPS means
losing the accumulated Memory/ history, or accepting manual copying.

## Solution Statement

1. **Windows Task Scheduler** — registers heartbeat (every 30 min, 7am–10pm AEST), reflection
   (daily 8am), and WhatsApp bot (on login) as background tasks. Runs while waiting for VPS.
2. **VPS (DigitalOcean Ubuntu 24.04)** — systemd timers/services replace Task Scheduler
   permanently. Brain runs 24/7 at $6/month.
3. **Git vault sync** — `Memory/` commits and pushes every 2 minutes on both machines.
   Custom `concat-both` merge driver concatenates daily log additions from both sides instead
   of conflicting. memory_index.py re-indexes after pulls that touch `Memory/`.
4. **Secrets handoff** — Gmail tokens auto-refresh silently via google-auth. Outlook MSAL
   token uses SerializableTokenCache with `acquire_token_silent` — headless-safe after
   initial copy. GREEN-API credentials are env vars in `.env` — copy once via scp.

## Feature Metadata

**Feature Type**: New Capability (deployment infrastructure)
**Estimated Complexity**: Medium
**Primary Systems Affected**: New `scripts/` directory, `.gitattributes`, VPS systemd units
**Dependencies**: GitHub private repo (prerequisite), DigitalOcean droplet, Pi CLI or Claude CLI on VPS

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `.claude/scripts/config.py` (lines 109–184) — `PROJECT_ROOT`, `BOT_LOCK_FILE`,
  `HEARTBEAT_INTERVAL_MINUTES`, `ensure_directories()`. VPS systemd `WorkingDirectory` must be
  the project root, not `.claude/scripts/`, because PROJECT_ROOT is derived from `__file__`.
- `.claude/chat/main.py` (lines 1–137) — Bot entry point; does its own sys.path manipulation
  so it can be run as `python .claude/chat/main.py` from project root.
- `.claude/scripts/heartbeat.py` (lines 1–80) — `sys.path.insert(0, str(Path(__file__).resolve().parent))`
  so heartbeat can be run as `python .claude/scripts/heartbeat.py` from project root.
- `.claude/scripts/memory_reflect.py` (lines 1–40) — Same pattern as heartbeat.
- `.claude/scripts/memory_index.py` (lines 1–30) — `uv run python memory_index.py` for
  incremental re-index (no `--rebuild` needed after vault sync — incremental is correct).
- `.claude/scripts/integrations/outlook.py` (lines 65–104) — `acquire_token_silent` handles
  headless token refresh. Device code flow only fires when NO cached token exists. Safe on VPS
  after initial `scp`. If it ever fails (90-day refresh token expiry), re-scp from Windows.
- `.claude/scripts/sdk_compat.py` (lines 31–34) — `SB_AGENT_BACKEND` env var selects backend.
  Default is `claude`. VPS must have this set to `pi` (or `claude` if Claude CLI installed).
- `.gitignore` (lines 1–44) — `.claude/data/` already covers `memory.db` and `chat.db`.
  Token files and `.env` already excluded. No changes needed for database handling.

### New Files to Create

**Local (committed to repo):**
- `.gitattributes` — registers `concat-both` merge driver + enforces LF on shell scripts
- `scripts/git-merge-concat` — bash merge driver: concatenates daily log entries from both sides
- `scripts/setup_vps.sh` — one-shot VPS bootstrap (install deps, clone, sync, set up environment)
- `scripts/setup_scheduler_windows.ps1` — register 4 Windows Task Scheduler tasks
- `scripts/sync_vault.ps1` — Windows vault sync (2-min loop: add, commit, pull, push)
- `scripts/systemd/second-brain-heartbeat.service`
- `scripts/systemd/second-brain-heartbeat.timer`
- `scripts/systemd/second-brain-reflect.service`
- `scripts/systemd/second-brain-reflect.timer`
- `scripts/systemd/second-brain-whatsapp.service`
- `scripts/systemd/second-brain-vaultsync.service`
- `scripts/systemd/second-brain-vaultsync.timer`
- `.claude/scripts/run_vault_sync.sh` — VPS vault sync (called by systemd; includes reindex)

### Patterns to Follow

**Python entry-point invocation** (from `config.py` and script preambles):
- All scripts add their own dir to `sys.path` via `Path(__file__).resolve().parent`
- Run from project root: `python .claude/scripts/heartbeat.py`
- VPS: use full venv path — `.claude/scripts/.venv/bin/python .claude/scripts/heartbeat.py`

**BOT_LOCK_FILE pattern** (`config.py` line 170, `main.py` lines 111–112):
- Bot writes `BOT_LOCK_FILE` (`.claude/data/state/whatsapp-bot.lock`) with its PID on start
- Bot removes it on exit via `finally`
- Heartbeat checks for this file before any WhatsApp polling
- `.claude/data/` is gitignored — lock file is machine-local, never syncs. Correct.

**Systemd `WorkingDirectory`**: must be project root (`/home/secondbrain/second-brain`),
not `.claude/scripts/`, because scripts resolve paths from `__file__` location (not CWD).

**uv venv location**: after `cd .claude/scripts && uv sync`, venv lives at
`.claude/scripts/.venv/` (gitignored). VPS systemd ExecStart uses full venv python path.

---

## IMPLEMENTATION PLAN

### Phase 1: Local Files (All Committed to Repo)

Foundation files that must exist in the repo before the VPS can clone and use them.

### Phase 2: Register Merge Driver Locally

One `git config` command on Windows to enable the driver before first push.

### Phase 3: GitHub Setup + Push

Prerequisite user action (create private repo, add remote, push).

### Phase 4: VPS Bootstrap

SSH into droplet, run `setup_vps.sh`, copy secrets, enable services.

### Phase 5: Windows Task Scheduler + Handoff

Register Windows tasks; after VPS is confirmed live, disable automation tasks (keep VaultSync).

---

## STEP-BY-STEP TASKS

### Task 1 — CREATE `.gitattributes`

- **IMPLEMENT**: New file at repo root
- **PURPOSE**: (1) Register `concat-both` merge driver for daily logs. (2) Force LF line
  endings on bash scripts so they run correctly on the Linux VPS (Windows git uses CRLF).
- **CONTENT**:
```
# Prevent merge conflicts in append-only daily logs
Memory/daily/*.md merge=concat-both

# Force LF on shell scripts executed on Linux VPS
scripts/git-merge-concat text eol=lf
scripts/setup_vps.sh text eol=lf
.claude/scripts/run_vault_sync.sh text eol=lf
```
- **GOTCHA**: The merge driver name (`concat-both`) must match exactly in `.gitattributes`,
  the `git config` command (Task 9), and any documentation. One typo = silent fallback to
  default merge.
- **VALIDATE**: `git check-attr merge Memory/daily/2026-06-08.md` → should show `merge: concat-both`

---

### Task 2 — CREATE `scripts/git-merge-concat`

- **IMPLEMENT**: New bash script (no `.sh` extension — git calls it as-is)
- **GOTCHA**: Must be executable. After creating: `git add scripts/git-merge-concat` then on
  VPS run `chmod +x scripts/git-merge-concat`. Windows git doesn't preserve execute bit —
  document in setup_vps.sh.
- **GOTCHA**: Uses `grep -vFxf` which is POSIX — works on Linux VPS. Windows git-bash can
  run it too for local testing but it's the VPS that matters.
- **CONTENT**:
```bash
#!/usr/bin/env bash
# Custom merge driver for append-only daily logs.
# Git calls: driver %O %A %B
#   $1 = %O (ancestor/base)  $2 = %A (local — also output file)  $3 = %B (remote)
# Exit 0 = merge succeeded.

ANCESTOR="$1"
LOCAL="$2"
REMOTE="$3"

# No common ancestor: both sides created the file fresh — concat and deduplicate
if [ ! -s "$ANCESTOR" ]; then
    cat "$LOCAL" "$REMOTE" | awk '!seen[$0]++' > "${LOCAL}.merged"
    mv "${LOCAL}.merged" "$LOCAL"
    exit 0
fi

# Lines LOCAL added that aren't in ANCESTOR (local-only new entries)
grep -vFxf "$ANCESTOR" "$LOCAL" > "${LOCAL}.local_additions" 2>/dev/null || true

# Start from REMOTE as base (keeps remote's entries in position)
cp "$REMOTE" "${LOCAL}.merged"

# Append local-only additions not already present in REMOTE
if [ -s "${LOCAL}.local_additions" ]; then
    while IFS= read -r line; do
        if ! grep -qFx "$line" "${LOCAL}.merged"; then
            echo "$line" >> "${LOCAL}.merged"
        fi
    done < "${LOCAL}.local_additions"
fi

mv "${LOCAL}.merged" "$LOCAL"
rm -f "${LOCAL}.local_additions"
exit 0
```
- **VALIDATE**: `bash scripts/git-merge-concat /dev/null /tmp/a.md /tmp/b.md` (create test files first)

---

### Task 3 — CREATE `.claude/scripts/run_vault_sync.sh`

- **IMPLEMENT**: VPS-side vault sync (called by systemd vaultsync service every 2 min)
- **KEY DECISION**: Conditionally re-runs `memory_index.py` only if the pull actually changed
  files in `Memory/` — avoids 720 pointless reindex runs per day.
- **CONTENT**:
```bash
#!/usr/bin/env bash
# VPS vault sync — called by second-brain-vaultsync.service
# Must be run from project root.

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON="$PROJECT_ROOT/.claude/scripts/.venv/bin/python"
LOG="$PROJECT_ROOT/.claude/scripts/vault_sync_runs.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] vault sync start" >> "$LOG"

# Stage and commit any local Memory/ changes
git add Memory/
if ! git diff --quiet --cached; then
    git commit -m "vault sync $(date '+%Y-%m-%d %H:%M')" >> "$LOG" 2>&1
fi

# Pull remote changes; note which Memory/ files changed
BEFORE=$(git rev-parse HEAD)
git pull --no-rebase origin HEAD >> "$LOG" 2>&1
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
```
- **GOTCHA**: `set -euo pipefail` is intentional but the push/reindex failures are made
  non-fatal (`|| echo`). Push failure (e.g., network hiccup) must never abort the service.
- **VALIDATE**: `bash .claude/scripts/run_vault_sync.sh` (run from project root after GitHub remote is set up)

---

### Task 4 — CREATE `scripts/sync_vault.ps1`

- **IMPLEMENT**: Windows vault sync script registered with Task Scheduler (repeats every 2 min)
- **CONTENT**:
```powershell
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
```
- **GOTCHA**: `$ProjectPath` default must be updated to Shaun's actual repo path before
  registering with Task Scheduler. The `setup_scheduler_windows.ps1` passes it explicitly.
- **VALIDATE**: `powershell -ExecutionPolicy Bypass -File scripts\sync_vault.ps1` from repo root

---

### Task 5 — CREATE `scripts/systemd/` directory with 7 unit file templates

Each file references `/home/secondbrain/second-brain` as `WorkingDirectory`. The `setup_vps.sh`
copies these to `/etc/systemd/system/` and enables them.

**VENV PATH on VPS**: `.claude/scripts/.venv/bin/python` (relative to WorkingDirectory)

**`scripts/systemd/second-brain-heartbeat.service`**:
```ini
[Unit]
Description=Second Brain Heartbeat
After=network.target

[Service]
Type=oneshot
User=secondbrain
WorkingDirectory=/home/secondbrain/second-brain
ExecStart=/home/secondbrain/second-brain/.claude/scripts/.venv/bin/python /home/secondbrain/second-brain/.claude/scripts/heartbeat.py
EnvironmentFile=/home/secondbrain/second-brain/.claude/scripts/.env
Environment=AGENT_INVOKED_BY=heartbeat
StandardOutput=append:/home/secondbrain/second-brain/.claude/scripts/heartbeat_runs.log
StandardError=append:/home/secondbrain/second-brain/.claude/scripts/heartbeat_runs.log
```

**`scripts/systemd/second-brain-heartbeat.timer`**:
```ini
[Unit]
Description=Second Brain Heartbeat Timer
Requires=second-brain-heartbeat.service

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

**`scripts/systemd/second-brain-reflect.service`**:
```ini
[Unit]
Description=Second Brain Daily Reflection
After=network.target

[Service]
Type=oneshot
User=secondbrain
WorkingDirectory=/home/secondbrain/second-brain
ExecStart=/home/secondbrain/second-brain/.claude/scripts/.venv/bin/python /home/secondbrain/second-brain/.claude/scripts/memory_reflect.py
EnvironmentFile=/home/secondbrain/second-brain/.claude/scripts/.env
Environment=AGENT_INVOKED_BY=reflection
StandardOutput=append:/home/secondbrain/second-brain/.claude/scripts/reflection_runs.log
StandardError=append:/home/secondbrain/second-brain/.claude/scripts/reflection_runs.log
```

**`scripts/systemd/second-brain-reflect.timer`**:
```ini
[Unit]
Description=Second Brain Reflection Timer
Requires=second-brain-reflect.service

[Timer]
OnCalendar=*-*-* 22:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```
NOTE: 22:00 UTC = 08:00 AEDT (UTC+10). Adjust for AEST/AEDT seasonally, or use
`TZ=Australia/Sydney OnCalendar=*-*-* 08:00:00` if systemd version ≥ 248 supports it.

**`scripts/systemd/second-brain-whatsapp.service`**:
```ini
[Unit]
Description=Second Brain WhatsApp Bot
After=network.target

[Service]
Type=simple
User=secondbrain
WorkingDirectory=/home/secondbrain/second-brain
ExecStart=/home/secondbrain/second-brain/.claude/scripts/.venv/bin/python /home/secondbrain/second-brain/.claude/chat/main.py
EnvironmentFile=/home/secondbrain/second-brain/.claude/scripts/.env
Environment=AGENT_INVOKED_BY=chat
Restart=always
RestartSec=10
StandardOutput=append:/home/secondbrain/second-brain/.claude/scripts/whatsapp_runs.log
StandardError=append:/home/secondbrain/second-brain/.claude/scripts/whatsapp_runs.log

[Install]
WantedBy=multi-user.target
```
GOTCHA: `Restart=always` with `RestartSec=10` handles GREEN-API connection drops gracefully.
The bot writes `BOT_LOCK_FILE` on start and removes it on exit — heartbeat won't WA-poll
while this service is running.

**`scripts/systemd/second-brain-vaultsync.service`**:
```ini
[Unit]
Description=Second Brain Vault Sync

[Service]
Type=oneshot
User=secondbrain
WorkingDirectory=/home/secondbrain/second-brain
ExecStart=/bin/bash /home/secondbrain/second-brain/.claude/scripts/run_vault_sync.sh
```

**`scripts/systemd/second-brain-vaultsync.timer`**:
```ini
[Unit]
Description=Second Brain Vault Sync Timer
Requires=second-brain-vaultsync.service

[Timer]
OnCalendar=*:0/2
Persistent=true

[Install]
WantedBy=timers.target
```
- **VALIDATE** (after VPS setup): `systemctl list-timers | grep second-brain`

---

### Task 6 — CREATE `scripts/setup_scheduler_windows.ps1`

- **IMPLEMENT**: Registers 4 Windows Task Scheduler tasks. Run once as Administrator.
- **CONTENT**:
```powershell
# Register Second Brain Windows Task Scheduler tasks.
# Run as Administrator: powershell -ExecutionPolicy Bypass -File scripts\setup_scheduler_windows.ps1

param(
    [string]$ProjectPath = "O:\AI\Dynamous\Courses\second-brain-workshop"
)

$python = Join-Path $ProjectPath ".claude\scripts\.venv\Scripts\python.exe"

# Heartbeat — every 30 min, 7am–10pm AEST (run all day, active-hours gate is in the script)
$hbAction = New-ScheduledTaskAction -Execute $python `
    -Argument (Join-Path $ProjectPath ".claude\scripts\heartbeat.py") `
    -WorkingDirectory $ProjectPath
$hbTrigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -Once -At "07:00" -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName "SecondBrain-Heartbeat" -Action $hbAction `
    -Trigger $hbTrigger -RunLevel Limited -Force
Write-Output "Registered: SecondBrain-Heartbeat"

# Reflection — daily at 8 AM
$refAction = New-ScheduledTaskAction -Execute $python `
    -Argument (Join-Path $ProjectPath ".claude\scripts\memory_reflect.py") `
    -WorkingDirectory $ProjectPath
$refTrigger = New-ScheduledTaskTrigger -Daily -At "08:00"
Register-ScheduledTask -TaskName "SecondBrain-Reflection" -Action $refAction `
    -Trigger $refTrigger -RunLevel Limited -Force
Write-Output "Registered: SecondBrain-Reflection"

# WhatsApp bot — on login
$waAction = New-ScheduledTaskAction -Execute $python `
    -Argument (Join-Path $ProjectPath ".claude\chat\main.py") `
    -WorkingDirectory $ProjectPath
$waTrigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "SecondBrain-WhatsAppBot" -Action $waAction `
    -Trigger $waTrigger -RunLevel Limited -Force
Write-Output "Registered: SecondBrain-WhatsAppBot"

# Vault sync — every 2 minutes (keep running even after VPS goes live)
$vsAction = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$(Join-Path $ProjectPath 'scripts\sync_vault.ps1')`" -ProjectPath `"$ProjectPath`"" `
    -WorkingDirectory $ProjectPath
$vsTrigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 2) `
    -Once -At (Get-Date) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName "SecondBrain-VaultSync" -Action $vsAction `
    -Trigger $vsTrigger -RunLevel Limited -Force
Write-Output "Registered: SecondBrain-VaultSync"

Write-Output "`nAll tasks registered. View in Task Scheduler (taskschd.msc)"
Write-Output "After VPS is live, disable Heartbeat, Reflection, WhatsAppBot (keep VaultSync):"
Write-Output "  Disable-ScheduledTask -TaskName 'SecondBrain-Heartbeat'"
Write-Output "  Disable-ScheduledTask -TaskName 'SecondBrain-Reflection'"
Write-Output "  Disable-ScheduledTask -TaskName 'SecondBrain-WhatsAppBot'"
```
- **GOTCHA**: Must run as Administrator (Task Scheduler requires elevated permissions)
- **GOTCHA**: `$python` path assumes `uv sync` has been run in `.claude/scripts/` first. If venv
  doesn't exist yet, run `cd .claude/scripts && uv sync` before this script.
- **VALIDATE**: `Get-ScheduledTask | Where-Object TaskName -like "SecondBrain-*" | Select-Object TaskName, State`

---

### Task 7 — CREATE `scripts/setup_vps.sh`

- **IMPLEMENT**: One-shot bootstrap script. Run via SSH after cloning the repo on VPS.
- **RUN AS**: `secondbrain` user (not root), from project root.
- **CONTENT**:
```bash
#!/usr/bin/env bash
# VPS bootstrap for Second Brain.
# Run ONCE after cloning the repo:
#   chmod +x scripts/setup_vps.sh && bash scripts/setup_vps.sh
#
# Prerequisites (done as root before running this):
#   adduser secondbrain && usermod -aG sudo secondbrain
#   apt update && apt install -y python3.12 python3-pip git ufw nodejs npm
#   ufw allow OpenSSH && ufw allow 8765/tcp && ufw enable

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "=== Second Brain VPS Bootstrap ==="
echo "Project root: $PROJECT_ROOT"

# 1. Install uv (Python package manager)
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 2. Install Python dependencies
echo "--- Installing Python dependencies..."
cd "$PROJECT_ROOT/.claude/scripts"
uv sync
echo "Python deps installed."

# 3. Pre-download FastEmbed model (runs on first index, better to do now)
echo "--- Pre-downloading embedding model (~80MB, one-time)..."
uv run python -c "from embeddings import get_model; get_model(); print('Model ready.')" || \
    echo "WARNING: embedding model download failed — will retry on first heartbeat"

# 4. Register git merge driver
echo "--- Registering concat-both merge driver..."
cd "$PROJECT_ROOT"
chmod +x scripts/git-merge-concat
git config merge.concat-both.driver "scripts/git-merge-concat %O %A %B"
echo "Merge driver registered."

# 5. Create .claude/data/ directories
echo "--- Creating runtime directories..."
uv run --project "$PROJECT_ROOT/.claude/scripts" python "$PROJECT_ROOT/.claude/scripts/config.py" -c \
    "import sys; sys.path.insert(0,'$PROJECT_ROOT/.claude/scripts'); from config import ensure_directories; ensure_directories(); print('Dirs OK')" || \
    mkdir -p "$PROJECT_ROOT/.claude/data/state" "$PROJECT_ROOT/.claude/data/models"

# 6. Install systemd unit files
echo "--- Installing systemd unit files..."
sudo cp "$PROJECT_ROOT"/scripts/systemd/*.service /etc/systemd/system/
sudo cp "$PROJECT_ROOT"/scripts/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
echo "Systemd units installed."

# 7. Enable all services/timers
echo "--- Enabling services..."
sudo systemctl enable --now second-brain-heartbeat.timer
sudo systemctl enable --now second-brain-reflect.timer
sudo systemctl enable --now second-brain-whatsapp.service
sudo systemctl enable --now second-brain-vaultsync.timer
echo "Services enabled."

echo ""
echo "=== Bootstrap complete ==="
echo "NEXT STEPS:"
echo "  1. Copy secrets from Windows:  (run these from Windows)"
echo "     scp .claude/scripts/.env secondbrain@VPS_IP:/home/secondbrain/second-brain/.claude/scripts/.env"
echo "     scp .claude/scripts/integrations/google_credentials.json secondbrain@VPS_IP:/home/secondbrain/second-brain/.claude/scripts/integrations/"
echo "     scp .claude/scripts/integrations/token_gmail_*.json secondbrain@VPS_IP:/home/secondbrain/second-brain/.claude/scripts/integrations/"
echo "     scp .claude/scripts/integrations/outlook_token.json secondbrain@VPS_IP:/home/secondbrain/second-brain/.claude/scripts/integrations/"
echo "  2. Lock down permissions:  chmod 600 .claude/scripts/.env .claude/scripts/integrations/*.json"
echo "  3. Ensure .env has SB_AGENT_BACKEND=pi (or claude if Claude CLI installed)"
echo "  4. Test: systemctl status second-brain-heartbeat.timer"
echo "  5. Force a test run: sudo systemctl start second-brain-heartbeat.service"
echo "  6. Check logs: tail -f .claude/scripts/heartbeat_runs.log"
```
- **GOTCHA**: `setup_vps.sh` runs as `secondbrain` user; the `sudo cp` and `sudo systemctl`
  lines require that user to be in the sudoers group (done via `usermod -aG sudo secondbrain`).
- **GOTCHA**: `SB_AGENT_BACKEND` in `.env` must be set to either `pi` (requires `pi` CLI installed
  via `npm install -g @earendil-works/pi-coding-agent`) or `claude` (requires Claude Code CLI).
  Pi is the primary backend per CLAUDE.md architecture rule.
- **VALIDATE**: Run the script end-to-end: `bash scripts/setup_vps.sh`

---

### Task 8 — REGISTER merge driver locally (Windows)

- **IMPLEMENT**: Single git config command on Windows machine (not a file — local git config)
- **COMMAND**:
```powershell
git config merge.concat-both.driver "scripts/git-merge-concat %O %A %B"
```
- **GOTCHA**: This is a local git config (stored in `.git/config`). Must be re-run on any
  machine that clones the repo. `setup_vps.sh` handles this on VPS automatically.
- **VALIDATE**: `git config merge.concat-both.driver` → should print the driver command

---

### Task 9 — UPDATE CLAUDE.md — Phase 9 section

- **IMPLEMENT**: Add Phase 9 to the `## Completed Phases` section and add deployment commands
  to `## Build Commands`.
- **ADD to Build Commands**:
```markdown
# Windows Task Scheduler (run as Administrator once)
powershell -ExecutionPolicy Bypass -File scripts\setup_scheduler_windows.ps1

# Register vault merge driver (run once per machine)
git config merge.concat-both.driver "scripts/git-merge-concat %O %A %B"

# Check Windows scheduled tasks
Get-ScheduledTask | Where-Object TaskName -like "SecondBrain-*" | Select-Object TaskName, State

# After VPS live — disable Windows automation tasks
Disable-ScheduledTask -TaskName "SecondBrain-Heartbeat"
Disable-ScheduledTask -TaskName "SecondBrain-Reflection"
Disable-ScheduledTask -TaskName "SecondBrain-WhatsAppBot"

# VPS management (SSH in first)
sudo systemctl status second-brain-heartbeat.timer
sudo systemctl status second-brain-whatsapp.service
tail -f .claude/scripts/heartbeat_runs.log
tail -f .claude/scripts/vault_sync_runs.log
```
- **ADD to Completed Phases**:
```markdown
### Phase 9: Deployment (Windows + VPS + Vault Sync) (2026-06-XX)
Windows Task Scheduler (4 tasks) + DigitalOcean VPS systemd (5 units) + git vault sync
with concat-both merge driver for daily logs. Secrets copied via scp; Gmail tokens
auto-refresh headlessly; Outlook MSAL SerializableTokenCache is headless-safe after
initial copy. GREEN-API polling mutex via BOT_LOCK_FILE (machine-local, gitignored).
After VPS live: disable Heartbeat, Reflection, WhatsAppBot Windows tasks; keep VaultSync.
```
- **VALIDATE**: Read CLAUDE.md — Phase 9 section present and complete

---

### Task 10 — COMMIT all Phase 9 files

- **IMPLEMENT**: Stage and commit all new files before pushing to GitHub
- **FILES**:
  - `.gitattributes`
  - `scripts/git-merge-concat`
  - `scripts/setup_vps.sh`
  - `scripts/setup_scheduler_windows.ps1`
  - `scripts/sync_vault.ps1`
  - `scripts/systemd/` (7 files)
  - `.claude/scripts/run_vault_sync.sh`
  - `CLAUDE.md` (updated)
- **VALIDATE**: `git status` shows all files staged; `git log --oneline -1` shows commit

---

### Task 11 — GITHUB SETUP (user action + assisted push)

**User does (manual, one-time):**
1. github.com → New repository → name: `second-brain` → Private → no README
2. Back in terminal: tell Claude the remote URL

**Claude assists:**
```powershell
git remote add origin git@github.com:<username>/second-brain.git
git push -u origin phase-2-pi-foundation
```
- **GOTCHA**: Push the existing `phase-2-pi-foundation` branch (not main — no main branch yet).
  The VPS will clone this branch.
- **GOTCHA**: VPS SSH deploy key needs **write access** (GitHub → repo → Settings → Deploy keys →
  check "Allow write access"). Read-only deploy key = vault sync push fails silently.
- **VALIDATE**: `git remote -v` shows `origin`; `git push` succeeds without errors

---

### Task 12 — VPS BOOTSTRAP (when IP provided)

**Prerequisites (run as root via SSH):**
```bash
ssh root@VPS_IP
adduser secondbrain
usermod -aG sudo secondbrain
apt update && apt install -y python3.12 python3-pip git ufw nodejs npm
ufw allow OpenSSH && ufw allow 8765/tcp && ufw enable
# Disable password SSH (optional but recommended):
# Edit /etc/ssh/sshd_config → PasswordAuthentication no → systemctl restart sshd
# Generate deploy key for GitHub:
su - secondbrain
ssh-keygen -t ed25519 -C "second-brain-vps"
cat ~/.ssh/id_ed25519.pub   # Add this to GitHub repo → Settings → Deploy keys
```

**Clone and bootstrap (as secondbrain user):**
```bash
ssh-T git@github.com  # verify GitHub SSH access
git clone git@github.com:<username>/second-brain.git ~/second-brain
cd ~/second-brain
chmod +x scripts/setup_vps.sh
bash scripts/setup_vps.sh
```

**Copy secrets (from Windows):**
```powershell
scp .claude\scripts\.env secondbrain@VPS_IP:/home/secondbrain/second-brain/.claude/scripts/.env
scp .claude\scripts\integrations\google_credentials.json secondbrain@VPS_IP:/home/secondbrain/second-brain/.claude/scripts/integrations/
scp .claude\scripts\integrations\token_gmail_*.json secondbrain@VPS_IP:/home/secondbrain/second-brain/.claude/scripts/integrations/
scp .claude\scripts\integrations\outlook_token.json secondbrain@VPS_IP:/home/secondbrain/second-brain/.claude/scripts/integrations/
```

**Lock down on VPS:**
```bash
chmod 600 ~/second-brain/.claude/scripts/.env
chmod 600 ~/second-brain/.claude/scripts/integrations/*.json
```

**Set LLM backend in .env on VPS** (Pi is primary per CLAUDE.md):
```bash
echo "SB_AGENT_BACKEND=pi" >> ~/second-brain/.claude/scripts/.env
# Then install Pi CLI:
npm install -g @earendil-works/pi-coding-agent
# OR: if using Claude Code CLI instead:
# npm install -g @anthropic-ai/claude-code
# echo "SB_AGENT_BACKEND=claude" >> .../.env
```
- **VALIDATE**: `systemctl status second-brain-heartbeat.timer` → Active (waiting)

---

### Task 13 — VALIDATE VPS (after bootstrap)

```bash
# 1. Timer status
systemctl list-timers | grep second-brain

# 2. Force a heartbeat test run (dry-run, no LLM)
cd ~/second-brain/.claude/scripts
uv run python heartbeat.py --dry-run --force

# 3. Check vault sync
tail -20 ~/second-brain/.claude/scripts/vault_sync_runs.log

# 4. Check WhatsApp bot
systemctl status second-brain-whatsapp.service
tail -20 ~/second-brain/.claude/scripts/whatsapp_runs.log

# 5. Trigger a real heartbeat (costs one LLM call)
sudo systemctl start second-brain-heartbeat.service
journalctl -u second-brain-heartbeat.service -n 30
```
- **VALIDATE**: Heartbeat dry-run completes with no import errors; vault sync log shows
  successful push; WhatsApp service shows `Active: active (running)`

---

### Task 14 — DISABLE Windows automation tasks (after VPS confirmed live)

Run from Windows PowerShell:
```powershell
Disable-ScheduledTask -TaskName "SecondBrain-Heartbeat"
Disable-ScheduledTask -TaskName "SecondBrain-Reflection"
Disable-ScheduledTask -TaskName "SecondBrain-WhatsAppBot"
# Keep VaultSync running on Windows — both machines sync independently
```
- **GOTCHA**: Do NOT disable VaultSync. Both machines must vault-sync independently for the
  `concat-both` merge driver to work in both directions.
- **VALIDATE**: `Get-ScheduledTask | Where-Object TaskName -like "SecondBrain-*"` shows
  Heartbeat/Reflection/WhatsApp as Disabled, VaultSync as Ready.

---

## TESTING STRATEGY

### Unit Tests
Phase 9 is infrastructure-only — no new Python modules. No unit tests added.
Existing test suite must still pass (no regressions from `.gitattributes` or new scripts).

### Integration / Smoke Tests

1. **Merge driver smoke test**: Create two conflicting daily log edits, commit on each "machine"
   (use a temp git clone), attempt merge — verify both sides' entries appear in result.
2. **Vault sync round-trip**: Write a test entry to `Memory/daily/` on Windows, let VaultSync
   commit and push; SSH to VPS, verify entry appears after next sync cycle.
3. **Heartbeat dry-run on VPS**: `uv run python heartbeat.py --dry-run --force` — must complete
   with no import errors and no missing credentials errors (token files were copied).
4. **WhatsApp bot test mode**: `uv run python .claude/chat/main.py --test` — must pass all
   config checks and print "All checks passed".

### Edge Cases
- Empty `Memory/daily/` file on one side — merge driver `! -s "$ANCESTOR"` branch handles it
- Pull with no Memory/ changes — reindex skipped (confirmed by checking vault_sync_runs.log)
- Push failure (network drop) — non-fatal, next sync cycle retries
- Outlook MSAL token expiry — fails silently; Outlook section shows no emails; document that
  re-scp from Windows fixes it (90-day refresh token lifetime)
- GREEN-API split polling — impossible after Task 14 disables Windows WhatsApp bot;
  BOT_LOCK_FILE prevents it even if both run simultaneously

---

## VALIDATION COMMANDS

### Level 1 — Local file syntax
```powershell
# Verify bash scripts have correct shebang
Select-String -Path "scripts\git-merge-concat","scripts\setup_vps.sh",".claude\scripts\run_vault_sync.sh" -Pattern "^#!/"
# Verify .gitattributes merge rule
git check-attr merge Memory/daily/2026-06-08.md
# Verify merge driver registered locally
git config merge.concat-both.driver
```

### Level 2 — PowerShell script syntax check
```powershell
# Syntax check (no execution)
powershell -Command "& { [System.Management.Automation.Language.Parser]::ParseFile('scripts\setup_scheduler_windows.ps1', [ref]$null, [ref]$null) }"
powershell -Command "& { [System.Management.Automation.Language.Parser]::ParseFile('scripts\sync_vault.ps1', [ref]$null, [ref]$null) }"
```

### Level 3 — Existing test suite (no regressions)
```powershell
cd .claude\scripts
uv run pytest tests/ -v
```

### Level 4 — Windows scheduler validation
```powershell
# After running setup_scheduler_windows.ps1
Get-ScheduledTask | Where-Object TaskName -like "SecondBrain-*" | Select-Object TaskName, State
```

### Level 5 — VPS validation
```bash
# On VPS after bootstrap
systemctl list-timers | grep second-brain
cd ~/second-brain/.claude/scripts && uv run python heartbeat.py --dry-run --force
tail -20 vault_sync_runs.log
```

---

## ACCEPTANCE CRITERIA

- [ ] `.gitattributes` registers `concat-both` driver for `Memory/daily/*.md` + LF for scripts
- [ ] `scripts/git-merge-concat` exists, correctly concatenates both sides, exits 0
- [ ] Merge driver registered locally: `git config merge.concat-both.driver` returns value
- [ ] `scripts/sync_vault.ps1` commits + pulls + pushes + conditionally reindexes
- [ ] `scripts/setup_scheduler_windows.ps1` registers 4 tasks (Heartbeat, Reflection, WhatsApp, VaultSync)
- [ ] All 7 systemd unit files exist in `scripts/systemd/`
- [ ] `.claude/scripts/run_vault_sync.sh` pulls, conditionally reindexes, pushes
- [ ] `scripts/setup_vps.sh` installs uv, syncs deps, registers merge driver, installs systemd units
- [ ] CLAUDE.md updated with Phase 9 build commands and completed phase entry
- [ ] All files committed and pushed to GitHub
- [ ] VPS: all 4 timers/services show Active in systemctl
- [ ] VPS: heartbeat dry-run completes with no errors
- [ ] VPS: vault sync log shows successful push
- [ ] Existing test suite: all 155+ tests still pass

---

## COMPLETION CHECKLIST

- [ ] Task 1 — `.gitattributes` created and validated
- [ ] Task 2 — `scripts/git-merge-concat` created
- [ ] Task 3 — `.claude/scripts/run_vault_sync.sh` created
- [ ] Task 4 — `scripts/sync_vault.ps1` created
- [ ] Task 5 — `scripts/systemd/` (7 unit files) created
- [ ] Task 6 — `scripts/setup_scheduler_windows.ps1` created
- [ ] Task 7 — `scripts/setup_vps.sh` created
- [ ] Task 8 — Merge driver registered locally (`git config`)
- [ ] Task 9 — CLAUDE.md updated
- [ ] Task 10 — All files committed
- [ ] Task 11 — GitHub remote added + pushed (user creates repo first)
- [ ] Task 12 — VPS bootstrap complete (when IP provided)
- [ ] Task 13 — VPS validated (dry-run + vault sync working)
- [ ] Task 14 — Windows Heartbeat/Reflection/WhatsApp tasks disabled

---

## NOTES

**Process ownership model** (critical — avoid split-brain):

| Process | Windows (pre-VPS) | Windows (post-VPS) | VPS |
|---------|-------------------|--------------------|-----|
| Heartbeat | On | **Disabled** | Always on |
| Reflection | On | **Disabled** | Always on |
| WhatsApp bot | On | **Disabled** | Always on |
| VaultSync | On | **On** | Always on |

**Outlook token headless safety**: MSAL `SerializableTokenCache` stores a refresh token.
`acquire_token_silent` exchanges it for a new access token silently. Works on VPS indefinitely
unless the refresh token expires (90 days of inactivity). If Outlook stops working on VPS:
re-run `setup_auth.py` on Windows and `scp outlook_token.json` to VPS again.

**`chat.db` stays local** (already gitignored via `.claude/data/`): After Phase 9, only VPS
runs the WhatsApp bot so `chat.db` only accumulates there. Windows sessions don't need it.

**`memory.db` stays local** (already gitignored): Rebuilt from `Memory/` (which syncs).
The vault sync scripts conditionally run `memory_index.py` after pulls that touch `Memory/`
so the index stays current on both machines without a full rebuild.

**LLM backend on VPS**: `SB_AGENT_BACKEND=pi` is the primary backend (per CLAUDE.md architecture
rule). Pi CLI must be installed: `npm install -g @earendil-works/pi-coding-agent`. Alternative:
`SB_AGENT_BACKEND=claude` with Claude Code CLI (`npm install -g @anthropic-ai/claude-code`).
Set in `.claude/scripts/.env` on VPS after secrets copy.

**Confidence Score: 8.5/10** — All patterns are well-established, entry points confirmed,
gitignore verified. The two risks: (1) Pi CLI installation on VPS may need npm/node version
management; (2) systemd `OnCalendar` timezone syntax varies by systemd version — the UTC
offset approach (22:00 UTC = 08:00 AEDT) is safer than `TZ=Australia/Sydney` which requires
systemd ≥ 248.
