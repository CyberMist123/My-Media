# One-off hard-cap test (task book 6.3): build a throwaway 300 MiB VHDX,
# fill it until NTFS refuses, check that a further write fails, free space and
# check writes recover, then detach and delete the test VHDX. Run elevated.
# Touches only Z:\.storage\captest.vhdx and Z:\.storage\captest-mnt.
$ErrorActionPreference = 'Stop'
$vhdx = 'Z:\.storage\captest.vhdx'
$mnt = 'Z:\.storage\captest-mnt'
$log = 'D:\My Media\reports\captest.log'
function Say($m) { $l = "$(Get-Date -Format s) $m"; Write-Output $l; Add-Content -LiteralPath $log -Value $l -Encoding utf8 }
function Invoke-Diskpart($lines) {
    $f = Join-Path $env:TEMP 'captest-dp.txt'
    ($lines -join "`r`n") | Set-Content -LiteralPath $f -Encoding ascii
    diskpart /s $f | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "diskpart failed ($LASTEXITCODE): $($lines -join '; ')" }
}

if (Test-Path -LiteralPath $vhdx) { throw "$vhdx already exists; remove it first" }
New-Item -ItemType Directory -Force $mnt | Out-Null
$result = 'FAILED_CAP_TEST'
try {
    Invoke-Diskpart @("create vdisk file=`"$vhdx`" maximum=300 type=expandable", 'attach vdisk', 'convert gpt',
               'create partition primary', 'format fs=ntfs label="CAPTEST" quick', "assign mount=`"$mnt`"")
    $part = Get-Volume -FileSystemLabel CAPTEST | Get-Partition
    $part | Set-Partition -NoDefaultDriveLetter $true
    foreach ($p in @($part.AccessPaths)) { if ($p -match '^[A-Z]:\\$') { $part | Remove-PartitionAccessPath -AccessPath $p } }
    $vol = Get-Volume -FileSystemLabel CAPTEST
    Say "captest volume size=$($vol.Size) free=$($vol.SizeRemaining)"

    # 1. Fill with 16 MiB files until the file system refuses.
    $i = 0; $refused = $false
    while ($i -lt 100) {
        $out = fsutil file createnew "$mnt\fill$i.bin" 16777216 2>&1
        if ($LASTEXITCODE -ne 0) { $refused = $true; Say "fill$i refused: $out"; break }
        $i++
    }
    $vol = Get-Volume -FileSystemLabel CAPTEST
    Say "after fill: files=$i free=$($vol.SizeRemaining) refused=$refused"

    # 2. A further write must fail.
    $write2 = $true
    try { [IO.File]::WriteAllBytes("$mnt\over.bin", (New-Object byte[] 33554432)) } catch { $write2 = $false; Say "over-cap write refused: $($_.Exception.InnerException.Message)$($_.Exception.Message)" }

    # 3. Free space and writes recover.
    Remove-Item "$mnt\fill0.bin", "$mnt\fill1.bin" -ErrorAction SilentlyContinue
    $recovered = $true
    try { [IO.File]::WriteAllBytes("$mnt\after.bin", (New-Object byte[] 8388608)) } catch { $recovered = $false }
    Say "recovered after freeing 32 MiB: $recovered"

    if ($refused -and -not $write2 -and $recovered -and $vol.Size -le 314572800) { $result = 'CAP_ENFORCED' }
} finally {
    try { Invoke-Diskpart @("select vdisk file=`"$vhdx`"", 'detach vdisk') } catch { Say "detach: $($_.Exception.Message)" }
    Remove-Item -LiteralPath $vhdx -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $mnt -Force -Recurse -ErrorAction SilentlyContinue
    Say "cleanup: vhdx gone=$(-not (Test-Path -LiteralPath $vhdx))"
    Say "RESULT $result"
}
