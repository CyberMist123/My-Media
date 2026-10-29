# Attach Z:\.storage\LER-MEDIA.vhdx and make sure the volume is reachable at
# both Z:\LER-MEDIA (Windows-native apps) and M:\ (Docker/WSL: they do not
# traverse NTFS mount points). Idempotent. Must run elevated, before Docker
# Desktop starts (the boot task registered by register-boot-mount.ps1 does this).
param(
    [string]$Vhdx = 'Z:\.storage\LER-MEDIA.vhdx',
    [string]$MountDir = 'Z:\LER-MEDIA',
    [string]$Letter = 'M',
    [string]$Label = 'LER-MEDIA',
    [string]$Log = 'D:\My Media\reports\mount-ler-media.log'
)
$ErrorActionPreference = 'Stop'
function Say($m) { $l = "$(Get-Date -Format s) $m"; Write-Output $l; Add-Content -LiteralPath $Log -Value $l -Encoding utf8 }

try {
    if (-not (Test-Path -LiteralPath $Vhdx)) { throw "VHDX not found: $Vhdx" }

    $img = Get-DiskImage -ImagePath $Vhdx
    if (-not $img.Attached) {
        $script = Join-Path $env:TEMP 'ler-attach.txt'
        "select vdisk file=`"$Vhdx`"`r`nattach vdisk" | Set-Content -LiteralPath $script -Encoding ascii
        diskpart /s $script | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "diskpart attach failed ($LASTEXITCODE)" }
        Start-Sleep -Seconds 3
        Say "attached $Vhdx"
    }

    $vol = Get-Volume -FileSystemLabel $Label -ErrorAction SilentlyContinue
    if (-not $vol) { throw "volume labelled $Label not found after attach" }
    $part = $vol | Get-Partition
    # Stop Windows from handing the volume a random extra letter on every attach;
    # the only access paths must be M: and the Z:\LER-MEDIA mount point.
    if (-not $part.NoDefaultDriveLetter) { $part | Set-Partition -NoDefaultDriveLetter $true; Say "set NoDefaultDriveLetter" }
    $paths = @($part.AccessPaths)
    foreach ($p in $paths) {
        if ($p -match '^[A-Z]:\\$' -and $p -ne "${Letter}:\") { $part | Remove-PartitionAccessPath -AccessPath $p; Say "removed stray letter $p" }
    }

    if (-not ($paths -contains "${Letter}:\")) {
        if (Get-Volume -DriveLetter $Letter -ErrorAction SilentlyContinue) { throw "${Letter}: is taken by another volume" }
        $part | Add-PartitionAccessPath -AccessPath "${Letter}:"
        Say "assigned ${Letter}:"
    }
    if (-not ($paths -contains "$MountDir\")) {
        if (-not (Test-Path -LiteralPath $MountDir)) { New-Item -ItemType Directory -Path $MountDir | Out-Null }
        if (Get-ChildItem -LiteralPath $MountDir -Force) { throw "$MountDir is not empty; refusing to mount over it" }
        $part | Add-PartitionAccessPath -AccessPath $MountDir
        Say "mounted at $MountDir"
    }

    $vol = Get-Volume -FileSystemLabel $Label
    Say ("OK {0} size={1} free={2}" -f $vol.UniqueId, $vol.Size, $vol.SizeRemaining)
    exit 0
} catch {
    Say "FAIL $($_.Exception.Message)"
    exit 1
}
