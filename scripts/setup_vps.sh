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
mkdir -p "$PROJECT_ROOT/.claude/data/state" "$PROJECT_ROOT/.claude/data/models"
echo "Dirs OK"

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
