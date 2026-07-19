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

# my-trader Monitor — daily at 07:30 (after US markets close, before Shaun's day starts)
$mtPython = Join-Path $ProjectPath "investments\.venv\Scripts\python.exe"
$mtAction = New-ScheduledTaskAction -Execute $mtPython `
    -Argument "-m mytrader.main monitor" `
    -WorkingDirectory (Join-Path $ProjectPath "investments\my-trader")
$mtTrigger = New-ScheduledTaskTrigger -Daily -At "07:30"
Register-ScheduledTask -TaskName "SecondBrain-MyTraderMonitor" -Action $mtAction `
    -Trigger $mtTrigger -RunLevel Limited -Force
Write-Output "Registered: SecondBrain-MyTraderMonitor"

Write-Output "`nAll tasks registered. View in Task Scheduler (taskschd.msc)"
Write-Output "After VPS is live, disable Heartbeat, Reflection, WhatsAppBot (keep VaultSync):"
Write-Output "  Disable-ScheduledTask -TaskName 'SecondBrain-Heartbeat'"
Write-Output "  Disable-ScheduledTask -TaskName 'SecondBrain-Reflection'"
Write-Output "  Disable-ScheduledTask -TaskName 'SecondBrain-WhatsAppBot'"
