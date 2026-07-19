# Deploy latest changes to DigitalOcean VPS
# Run after git push: .\scripts\deploy.ps1

$VPS = "secondbrain@137.184.102.104"
$REMOTE_DIR = "/home/secondbrain/second-brain"

# Determine current local branch to deploy the same one to VPS
$BRANCH = git rev-parse --abbrev-ref HEAD

Write-Host "Stopping heartbeat timer..."
ssh $VPS "sudo systemctl stop second-brain-heartbeat.timer"
ssh $VPS "sudo systemctl stop second-brain-mytrader-monitor.timer 2>/dev/null || true"

Write-Host "Pulling latest changes (branch: $BRANCH)..."
ssh $VPS "cd $REMOTE_DIR && git add Memory/ && git stash && git fetch origin && git checkout $BRANCH && git pull --no-rebase origin $BRANCH && git stash pop || true"

Write-Host "Restarting heartbeat timer..."
ssh $VPS "sudo systemctl start second-brain-heartbeat.timer"
ssh $VPS "sudo systemctl start second-brain-mytrader-monitor.timer 2>/dev/null || true"

Write-Host "Done."
