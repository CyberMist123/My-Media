# Register the boot task that runs mount-ler-media.ps1 as SYSTEM at startup,
# i.e. before anyone logs in and Docker Desktop starts. Run once, elevated.
$ErrorActionPreference = 'Stop'
$script = 'D:\My Media\scripts\mount-ler-media.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName 'LER-MEDIA-Mount' -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'LER-MEDIA-Mount'
Start-Sleep -Seconds 8
Get-ScheduledTaskInfo -TaskName 'LER-MEDIA-Mount' | Select-Object LastRunTime, LastTaskResult
Get-Content -LiteralPath 'D:\My Media\reports\mount-ler-media.log' -Tail 3
