# 预检清单（只读，交给本机 Claude Code 执行）

目的：在 Zcode 正式部署前，先拿到任务书 §4、§6.1 模式 B 所需的事实。**本清单全部是只读命令，不创建、不修改、不删除任何东西。** 结果写入 `D:\My Media\reports\00-preflight.md`（目录不存在则只创建这一个空目录）。每项给出原始输出和一行结论：`GO / BLOCKED / NEEDS APPROVAL`。

## 1. 系统
```powershell
Get-ComputerInfo | Select-Object WindowsProductName, WindowsEditionId, WindowsVersion, OsBuildNumber, OsArchitecture, CsTotalPhysicalMemory
winver
```
结论要点：Edition（Home/Pro）、Build 是否 19045、x64。

## 2. 虚拟化 / WSL2 / Docker
```powershell
systeminfo | Select-String "Hyper-V"
wsl --status
wsl --version
wsl -l -v
docker version
docker compose version
docker info --format '{{.OperatingSystem}} | {{.DockerRootDir}} | {{.Driver}}'
```
附加：Docker Desktop 设置里 "Disk image location" 的实际路径，以及该路径下 `ext4.vhdx` 的大小：
```powershell
Get-ChildItem "$env:LOCALAPPDATA\Docker\wsl" -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue | Select-Object FullName, @{n='GB';e={[math]::Round($_.Length/1GB,1)}}
```
结论要点：Docker Desktop 版本是否官方支持当前 Win10 Build；WSL2 是否已启用；是否已有其他 WSL 发行版在用（影响能否 `wsl --shutdown`）。

## 3. Z: 盘（模式 B 的核心）
```powershell
Get-Volume -DriveLetter Z | Format-List DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining, DriveType, UniqueId, HealthStatus
Get-Partition -DriveLetter Z | Format-List DiskNumber, PartitionNumber, Type, Size, Offset
Get-Disk -Number (Get-Partition -DriveLetter Z).DiskNumber | Format-List Number, FriendlyName, BusType, PartitionStyle, Size, IsBoot, IsSystem
manage-bde -status Z:
Get-ChildItem Z:\ -Force | Select-Object Name, Mode, Length
Get-ChildItem Z:\ -Force -Directory | ForEach-Object { $b=(Get-ChildItem $_.FullName -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; [pscustomobject]@{Dir=$_.Name; GB=[math]::Round($b/1GB,2)} }
Test-Path Z:\LER-MEDIA
Test-Path Z:\.storage
```
结论要点：
- 文件系统必须是 NTFS；DriveType 必须是 Fixed（不能是网络盘/可移动盘）。
- 精确 `Size` 与 `SizeRemaining` 字节数。模式 B 需要 `SizeRemaining ≥ 452,000,000,000` 字节（450GB + 约 2GB 元数据余量）才能创建 VHDX；当前约 39 GB 可用会得到 **BLOCKED_SPACE**，这是预期结果，记录差额即可。
- `Z:\LER-MEDIA` 必须不存在或为空目录（它将成为挂载点）。
- 列出 Z: 根下所有现有目录及体积，原样记录，**不删不移**。

## 4. VHDX 能力
```powershell
Get-Command New-VHD -ErrorAction SilentlyContinue
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-Management-PowerShell -ErrorAction SilentlyContinue | Select-Object State
diskpart /? | Select-String -Quiet "DISKPART"
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
```
结论要点：有无 Hyper-V PowerShell 模块（没有也没关系，diskpart 可用即可）；当前会话是否管理员。

## 5. WSL2 对 Z: 的可见性
在任一已有 WSL 发行版内：
```bash
ls -ld /mnt/z && df -h /mnt/z && mount | grep ' /mnt/z '
```
结论要点：`/mnt/z` 是否已自动挂载为 drvfs。挂载点穿透测试留到 VHDX 创建后再做。

## 6. D: 与 C: 负担
```powershell
Get-Volume -DriveLetter C,D | Select-Object DriveLetter, FileSystem, @{n='SizeGB';e={[math]::Round($_.Size/1GB)}}, @{n='FreeGB';e={[math]::Round($_.SizeRemaining/1GB)}}
Test-Path "D:\My Media"
Get-ChildItem "D:\My Media" -Force -ErrorAction SilentlyContinue | Select-Object Name
```

## 7. Jellyfin 现状
```powershell
Get-Service | Where-Object Name -like '*jellyfin*'
Get-ItemProperty HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*, HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* -ErrorAction SilentlyContinue | Where-Object DisplayName -like '*Jellyfin*' | Select-Object DisplayName, DisplayVersion, InstallLocation
Get-ChildItem "$env:ProgramData\Jellyfin\Server" -Directory -ErrorAction SilentlyContinue | ForEach-Object { $b=(Get-ChildItem $_.FullName -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; [pscustomobject]@{Dir=$_.Name; GB=[math]::Round($b/1GB,2)} }
```

## 8. GPU
```powershell
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
```

## 9. 端口占用
```powershell
$ports = 8096,5055,7878,8989,9696,6767,8080,6060,4567,7892
Get-NetTCPConnection -State Listen | Where-Object { $ports -contains $_.LocalPort } | Select-Object LocalPort, OwningProcess, @{n='Process';e={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName}}
```

## 10. 现有容器 / 下载器 / 媒体工具
```powershell
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker volume ls
Get-Process | Where-Object { $_.ProcessName -match 'qbittorrent|sonarr|radarr|prowlarr|bazarr|jellyfin|plex|emby' } | Select-Object ProcessName, Id, Path
```

## 11. Fable / Bridge 只读探测
记录（不改任何配置）：Fable 进程运行在哪台机器/哪个容器；它当前连接 MCP 的方式（stdio / SSE / Streamable HTTP）；是否支持 bearer token；到本机 `localhost` 各端口的网络路径。只看配置文件和日志，**不要把其中的 token、密码写进报告**。

## 输出
`00-preflight.md` 末尾给一张汇总表：

| 项 | 结论 | 备注 |
|---|---|---|
| Win10 版本/Edition | GO/BLOCKED | |
| Docker Desktop 支持状态 | GO/BLOCKED/NEEDS APPROVAL | |
| Z: NTFS/Fixed | GO/BLOCKED | |
| Z: 可用空间 ≥ 452 GB | GO/BLOCKED_SPACE | 当前差额 |
| Z:\LER-MEDIA 可作挂载点 | GO/BLOCKED | |
| VHDX 工具可用 | GO | diskpart / New-VHD |
| /mnt/z 可见 | GO/BLOCKED | |
| D:\My Media 可用 | GO | |
| 端口冲突 | 列表 | |
| Fable MCP 能力 | 描述 | |
