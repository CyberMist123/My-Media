# My Media — Windows 10 本地影音库部署

执行 Agent 请直接阅读 [`Zcode_部署任务书.md`](./Zcode_部署任务书.md)，它是唯一有效规范。

- 媒体卷：`Z:\.storage\LER-MEDIA.vhdx`（模式 B，当前为 35 GB 测试阶段），Windows 侧挂在 `Z:\LER-MEDIA`，Docker 侧用盘符 `M:\`（同一卷，见任务书 §6.1）
- 开机挂载：[`scripts/mount-ler-media.ps1`](./scripts/mount-ler-media.ps1)，由计划任务 `LER-MEDIA-Mount` 调用
- Fable 接入：[`tools/arr-cli`](./tools/arr-cli/README.md)（CLI，不走 MCP）
- 程序目录：`D:\My Media`（本仓库检出处）；`.env` 不提交
- 预检结果：[`reports/00-preflight.md`](./reports/00-preflight.md)，调查记录见 issue #2
