# Switch Jellyfin from tray mode to a Windows service (Owner 2026-10-29), so it
# survives logoff and restarts itself after a crash. Run once, elevated.
# Service: JellyfinServer, LocalSystem, delayed auto-start (gives the
# LER-MEDIA-Mount boot task time to attach the media volume first),
# restart on exit. Same program and data directories as before.
$ErrorActionPreference = 'Stop'
$srv = 'D:\My Media\Server'
$data = 'D:\My Media\jellyfin-data'
$nssm = "$srv\nssm.exe"
$name = 'JellyfinServer'

# 1. Stop tray mode and drop its autostart entry.
Stop-Process -Name 'Jellyfin.Windows.Tray', 'jellyfin' -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
foreach ($k in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
               'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
               'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run') {
    if (Get-ItemProperty -Path $k -Name JellyfinTray -ErrorAction SilentlyContinue) {
        Remove-ItemProperty -Path $k -Name JellyfinTray
        Write-Output "removed tray autostart from $k"
    }
}

# 2. Install (or refresh) the service.
if (-not (Get-Service $name -ErrorAction SilentlyContinue)) {
    & $nssm install $name "$srv\jellyfin.exe" | Out-Null
}
# Write AppParameters straight to the registry: PowerShell strips the inner quotes
# when passing them to nssm, which turned the datadir into "D:\My".
Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\$name\Parameters" -Name AppParameters `
    -Value ('--datadir "{0}" --service' -f $data)
& $nssm set $name AppDirectory $srv | Out-Null
& $nssm set $name DisplayName 'Jellyfin Server' | Out-Null
& $nssm set $name Start SERVICE_DELAYED_AUTO_START | Out-Null
& $nssm set $name ObjectName LocalSystem | Out-Null
& $nssm set $name AppExit Default Restart | Out-Null
& $nssm set $name AppRestartDelay 10000 | Out-Null
& $nssm set $name AppStdout "$data\log\service-stdout.log" | Out-Null
& $nssm set $name AppStderr "$data\log\service-stderr.log" | Out-Null
Set-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Jellyfin\Server' -Name ServiceAccountType -Value 'LocalSystem'

# 3. (Re)start and wait for the API.
Stop-Service $name -ErrorAction SilentlyContinue
# Clean up the stray data dir an earlier quoting bug created at D:\My, but only
# if it holds nothing except Jellyfin's own fresh skeleton.
$stray = 'D:\My'
if (Test-Path -LiteralPath "$stray\.jellyfin-data") {
    $names = (Get-ChildItem -LiteralPath $stray -Force).Name
    if (-not ($names | Where-Object { $_ -notin 'cache', 'config', 'data', 'log', 'metadata', 'plugins', 'root', '.jellyfin-data' })) {
        Remove-Item -LiteralPath $stray -Recurse -Force
        Write-Output "removed stray $stray"
    }
}
Start-Service $name
foreach ($i in 1..30) {
    Start-Sleep -Seconds 4
    try { $info = Invoke-RestMethod 'http://localhost:8096/System/Info/Public'; break } catch {}
}
Get-Service $name | Select-Object Name, Status, StartType
if ($info) { Write-Output "Jellyfin $($info.Version) up (wizard done: $($info.StartupWizardCompleted))" } else { Write-Output 'Jellyfin did not answer on 8096 within 2 minutes' }
