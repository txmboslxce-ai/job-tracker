# schedule_task.ps1
# Run this ONCE (as Administrator) to register the Job Tracker in Windows Task Scheduler.
# It will run every weekday at 8:00 AM.
#
# Usage (in an elevated PowerShell):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\schedule_task.ps1

$TaskName   = "JobTracker"
$RunAt      = "08:00"
$ProjectDir = "C:\Users\TimDunn\Claude\job-tracker"
$RunBat     = "$ProjectDir\run.bat"

# Remove existing task of the same name if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing '$TaskName' task."
}

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$RunBat`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $RunAt
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Scrapes job boards and emails new postings." `
    -RunLevel Limited

Write-Host ""
Write-Host "Task '$TaskName' registered successfully."
Write-Host "It will run every weekday at $RunAt."
Write-Host ""
Write-Host "To run immediately for testing:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "To view logs:"
Write-Host "  Get-Content '$ProjectDir\logs\job_tracker.log' -Tail 50"
