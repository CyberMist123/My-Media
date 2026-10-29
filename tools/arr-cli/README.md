# arr-cli

Fable 接入影视栈的命令行入口，替代 arr-mcp（Fable 的 MCP 只支持 stdio、每回合 8 秒握手，HTTP MCP 不划算）。只用 Python 标准库。

```text
python "D:\My Media\tools\arr-cli\arr.py" status            # 各服务健康/版本
python "D:\My Media\tools\arr-cli\arr.py" search "绝命毒师"   # 经 Seerr 搜，返回 tmdbId
python "D:\My Media\tools\arr-cli\arr.py" request tv 1396 --seasons 1 --dry-run
python "D:\My Media\tools\arr-cli\arr.py" request movie 27205
python "D:\My Media\tools\arr-cli\arr.py" requests | queue | torrents | space
```

输出统一 JSON：`{"ok": true, "data": ...}` 或 `{"ok": false, "error": ...}`（退出码 2）。

## 权限边界
- **没有任何删除/移除命令**——删除只走 CleanArr 预览或 Jellyfin 手动（任务书 §12/§13）。
- 写操作只有一种：`request`（Seerr 新建请求）。请求带 `X-Api-User` 以专用非管理员 Seerr 用户身份提交。
- qBittorrent 只读。
- `--dry-run` 只打印将提交的内容。

## 配置（环境变量，或 `D:\My Media\.env`，不进仓库）
| 变量 | 默认 |
|---|---|
| `SEERR_URL` / `SEERR_API_KEY` / `SEERR_FABLE_USER_ID` | `http://localhost:5055` |
| `SONARR_URL` / `SONARR_API_KEY` | `http://localhost:8989` |
| `RADARR_URL` / `RADARR_API_KEY` | `http://localhost:7878` |
| `PROWLARR_URL` / `PROWLARR_API_KEY` | `http://localhost:9696` |
| `QB_URL` / `QB_USER` / `QB_PASS` | `http://localhost:8090`；不设 `QB_USER` 时依赖 qB「本机免认证」 |
| `MEDIA_ROOT` | `M:\` |

Seerr API Key 是管理员级；Fable 与 `.env` 同机，无法做到对 Fable 完全不可见，所以 `.env` 的 ACL 与"不在聊天里回显"是唯一屏障。
