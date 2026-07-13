# Obsidian Control — 技能定义

## 概述

直接控制 Obsidian 桌面应用的完整能力。通过 Electron Chrome DevTools Protocol (CDP) 连接 Obsidian 运行时，调用 `window.app` 内部 API，实现对 vault 的读写控制、文件验证和截图。

**核心思路**: Obsidian 是 Electron 应用 → `--remote-debugging-port=9223` 启动 → `playwright-core` 通过 CDP 连接 → `page.evaluate()` 注入脚本调用 Obsidian 内部 API。

## 触发条件

当用户提到以下任一场景时激活:
- 在 Obsidian 中打开/编辑/创建笔记
- 列出/搜索 vault 中的文件
- 截图 Obsidian 界面
- 验证笔记是否在 Obsidian 中正确显示
- 批量操作 vault 中的 Markdown 文件
- 关键词: "obsidian" + "打开/控制/操作/笔记/截图/验证"

## 架构

```
Claude Code (MCP Client)
    │ stdio
    ▼
obsidian-mcp/server.cjs (MCP Server — 8 tools)
    │ require()
    ▼
skills/obsidian-control/scripts/obsidian_cdp_core.cjs (CDP 控制核心)
    │ playwright-core .connectOverCDP()
    ▼
Obsidian Electron (--remote-debugging-port=9223)
    │ page.evaluate()
    ▼
window.app.vault / window.app.workspace (Obsidian 内部 API)
```

### 文件职责

| 文件 | 职责 |
|------|------|
| `obsidian-mcp/server.cjs` | MCP 协议层: 8 个工具的 schema 定义、参数校验、结果格式化、launch 调度 |
| `obsidian-mcp/smoke-test.cjs` | MCP 客户端测试: 启动 server 子进程，通过 stdio 调用单个工具 |
| `skills/obsidian-control/scripts/obsidian_cdp_core.cjs` | CDP 控制核心: 连接 Electron、页面判断、注入脚本、返回结构化结果 |
| `skills/obsidian-control/scripts/obsidian_control.ps1` | PowerShell 启动器: 定位 Obsidian.exe、终止/启动进程、等待 CDP 就绪 |

## 8 个 MCP 工具

| 工具 | 参数 | 功能 |
|------|------|------|
| `obsidian_status` | vault_path?, cdp_url?, timeout_ms? | 检查 CDP 连接状态、当前活动文件、vault 路径、文件总数 |
| `obsidian_launch` | vault_path?, debug_port?, timeout_seconds?, force_restart? | 以调试端口启动/重启 Obsidian |
| `obsidian_list_files` | vault_path?, cdp_url?, timeout_ms?, auto_launch? | 列出 vault 中所有 .md 文件的 path 和 name |
| `obsidian_current_note` | vault_path?, cdp_url?, timeout_ms? | 返回当前活动文件的 path、name、窗口标题 |
| `obsidian_open_note` | **note_path** (必填), vault_path?, cdp_url?, timeout_ms? | 在 Obsidian 中打开指定笔记并激活该标签页 |
| `obsidian_screenshot` | output_path?, vault_path?, cdp_url?, timeout_ms? | 截取 Obsidian 窗口截图（PNG） |
| `obsidian_verify_note` | **note_path** (必填), vault_path?, cdp_url?, timeout_ms? | 打开笔记并验证其是否成为活动文件（ok: true/false） |
| `obsidian_verify_all` | vault_path?, cdp_url?, timeout_ms? | 遍历 vault 所有 .md 文件，逐个验证可打开性 |

参数带 `?` 为选填，有默认值。`auto_launch` 设为 true 时，CDP 连接失败会自动调用 `obsidian_launch`。

## 默认配置

| 配置项 | 值 | 来源 |
|--------|-----|------|
| Vault 路径 | `E:\claude code\codex的obsidian经验\obsidian-vault` | `obsidian_cdp_core.cjs` DEFAULTS |
| CDP 地址 | `http://127.0.0.1:9223` | `obsidian_cdp_core.cjs` DEFAULTS |
| 超时 | 15000ms | `obsidian_cdp_core.cjs` DEFAULTS |
| Debug 端口 | 9223 | `server.cjs` OBSIDIAN_DEBUG_PORT 环境变量 |
| Obsidian 路径 | 自动检测 7 个常见位置 + 全盘搜索 | `obsidian_control.ps1` Find-ObsidianExe |

## 前置条件

1. **Obsidian 已安装** — `C:\Program Files\Obsidian\Obsidian.exe` 或其他位置
2. **Node.js ≥ 18** — 运行 MCP server 和 CDP 脚本
3. **PowerShell** — 启动 Obsidian（Windows 自带）
4. **npm 依赖** — `obsidian-mcp/` 下已安装 `@modelcontextprotocol/sdk` 和 `playwright-core`
5. **Obsidian 以调试模式运行** — 必须带 `--remote-debugging-port=9223` 启动

## 故障排除

| 症状 | 原因 | 解决 |
|------|------|------|
| CDP 连接失败 | Obsidian 未启动或未开调试端口 | 执行 `obsidian_launch` 或手动启动 Obsidian 带 `--remote-debugging-port=9223` |
| `window.app not available` | 连接到了 webview 而非主编辑器窗口 | 重启 Obsidian（旧实例可能只暴露了插件 webview） |
| `File not found in vault` | 文件由外部创建，Obsidian 索引未刷新 | 已内置 fallback: 检测到新文件时自动通过 `vault.create()` 注册 |
| `playwright-core not found` | npm 依赖未安装 | `cd obsidian-mcp && npm install` |
| Obsidian 端口被占 | 上次进程未完全退出 | `force_restart: true` 或手动 kill Obsidian 进程 |

## 已知限制

1. **内部 API 依赖** — `window.app.vault` / `window.app.workspace` 是 Obsidian 内部 API，版本升级后可能变化
2. **仅限本地** — CDP 连接只在 `127.0.0.1` 上，不支持远程控制
3. **主窗口独占** — 必须连接到 `app://obsidian.md/index.html` 页面，不能是 starter 页或插件 webview
4. **外部文件索引延迟** — 从外部写入的文件需要等 Obsidian 文件监视器刷新后才能通过 `getAbstractFileByPath` 找到（已有 fallback 处理）

## 参考文档

- `references/obsidian-electron-cdp.md` — CDP 协议细节、Obsidian 内部 API 完整列表、JavaScript 注入脚本详解
- `references/portable-agent-integration.md` — 迁移到新工作区/新机器/新智能体的完整步骤
