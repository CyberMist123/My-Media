# Storage gate (task book 6.2): exit 0 only when Z:\LER-MEDIA and M:\ are the
# same mounted LER-MEDIA volume named in the marker, within the hard cap and
# writable. start.ps1 must not start any media-writing service otherwise.
# Read-only except for one probe file; no elevation needed.
param(
    [string]$MountDir = 'Z:\LER-MEDIA',
    [string]$Letter = 'M',
    [string]$Vhdx = 'Z:\.storage\LER-MEDIA.vhdx',
    [long]$CapBytes = 450000000000
)
$fail = @()
function Check($ok, $msg) { if ($ok) { Write-Output "PASS $msg" } else { Write-Output "FAIL $msg"; $script:fail += $msg } }

$marker = Join-Path $MountDir '.ler-media.marker'
$want = $null
if (Test-Path -LiteralPath $marker) {
    $want = ((Get-Content -LiteralPath $marker) -match '^volume=') -replace '^volume=', ''
}
Check ($want) "marker present with volume id ($marker)"

Check (Test-Path -LiteralPath $Vhdx) "VHDX exists ($Vhdx)"
$img = Get-DiskImage -ImagePath $Vhdx -ErrorAction SilentlyContinue
Check ($img -and $img.Attached) "VHDX attached"

$vol = Get-Volume -FileSystemLabel 'LER-MEDIA' -ErrorAction SilentlyContinue
Check ($vol) "LER-MEDIA volume online"
if ($vol) {
    Check ($vol.UniqueId -eq $want) "volume id matches marker ($($vol.UniqueId))"
    $paths = @(($vol | Get-Partition).AccessPaths)
    Check ($paths -contains "$MountDir\") "mounted at $MountDir"
    Check ($paths -contains "${Letter}:\") "drive letter ${Letter}:"
    Check ($vol.Size -le $CapBytes) "size $($vol.Size) <= cap $CapBytes"
    Write-Output ("INFO free={0} size={1}" -f $vol.SizeRemaining, $vol.Size)
}

$probe = "${Letter}:\.staging\.verify-probe"
try { Set-Content -LiteralPath $probe -Value (Get-Date -Format s) -ErrorAction Stop; Remove-Item -LiteralPath $probe; Check $true "writable via ${Letter}:" }
catch { Check $false "writable via ${Letter}: ($($_.Exception.Message))" }

if ($fail.Count) { Write-Output "STORAGE_GATE=BLOCKED"; exit 1 }
Write-Output "STORAGE_GATE=OK"; exit 0
