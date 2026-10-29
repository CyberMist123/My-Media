# Start the media stack: storage gate first (task book 6.2), then containers,
# then check native Jellyfin and qBittorrent. Containers never start on a failed gate.
$ErrorActionPreference = 'Stop'
$root = 'D:\My Media'
& powershell -NoProfile -ExecutionPolicy Bypass -File "$root\scripts\verify-storage.ps1"
if ($LASTEXITCODE -ne 0) { Write-Output 'Storage gate BLOCKED: containers not started.'; exit 1 }

docker compose -f "$root\compose.yaml" up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Containers must see the same volume (marker) at /data.
foreach ($svc in 'sonarr', 'radarr') {
    docker compose -f "$root\compose.yaml" exec -T $svc test -f /data/.ler-media.marker
    if ($LASTEXITCODE -ne 0) { Write-Output "FAIL $svc cannot see /data/.ler-media.marker; stopping."; docker compose -f "$root\compose.yaml" stop; exit 1 }
}

foreach ($u in 'http://localhost:8096/System/Info/Public', 'http://localhost:8090/api/v2/app/webapiVersion') {
    try { Invoke-WebRequest $u -UseBasicParsing -TimeoutSec 5 | Out-Null; Write-Output "UP $u" } catch { Write-Output "DOWN $u (native app not running?)" }
}
