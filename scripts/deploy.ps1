# Deploy latest changes to DigitalOcean VPS
# Run after git push: .\scripts\deploy.ps1

$VPS = "secondbrain@137.184.102.104"
$REMOTE_DIR = "/home/secondbrain/second-brain"

Write-Host "Stopping heartbeat timer..."
ssh $VPS "sudo systemctl stop second-brain-heartbeat.timer"

Write-Host "Pulling latest changes..."
ssh $VPS "cd $REMOTE_DIR && chmod +x scripts/git-merge-concat && git stash && git pull && git stash pop"

Write-Host "Restarting heartbeat timer..."
ssh $VPS "sudo systemctl start second-brain-heartbeat.timer"

Write-Host "Done."
