# Obsidian Control — 可移植集成指南

## 迁移清单

将 Obsidian 控制能力从当前工作区迁移到新环境，需要复制以下文件:

### 必须复制的文件

```
新工作区/
├── obsidian-mcp/                          ← MCP 服务器目录
│   ├── server.cjs                         ← MCP 协议层 (8 tools)
│   ├── smoke-test.cjs                     ← 测试客户端
│   └── package.json                       ← npm 依赖声明
├── skills/obsidian-control/               ← Skill 目录
│   ├── SKILL.md                           ← 技能定义 (触发条件、主流程、故障排除)
│   ├── scripts/
│   │   ├── obsidian_cdp_core.cjs          ← CDP 控制核心 (连接、注入、action 路由)
│   │   └── obsidian_control.ps1           ← PowerShell 启动器 (定位exe、启动、等待CDP)
│   └── references/
│       ├── obsidian-electron-cdp.md       ← CDP 技术深度参考
│       └── portable-agent-integration.md  ← 本文档
```

### 可选复制的文件

```
├── obsidian_control.ps1                   ← 工作区级包装脚本 (转发到 skill 脚本)
└── codex的obsidian经验/obsidian-vault/    ← 参考 vault (含 obsidian-control/ 说明文档)
```

## 适配步骤

### 步骤 1: 复制文件

```powershell
# 从源工作区复制核心文件
Copy-Item -Recurse "源工作区/obsidian-mcp" "目标工作区/"
Copy-Item -Recurse "源工作区/skills/obsidian-control" "目标工作区/skills/"
```

### 步骤 2: 更新默认路径

以下 5 个文件包含硬编码路径，需要批量替换:

| 文件 | 需修改的内容 | 说明 |
|------|-------------|------|
| `obsidian-mcp/server.cjs` | vault 路径描述 | TOOLS 定义中的 description |
| `skills/.../obsidian_cdp_core.cjs` | `DEFAULT_VAULT_PATH` | 第 7 行，默认 vault 路径 |
| `skills/.../obsidian_control.ps1` | `$DefaultVault` | 第 11 行，默认 vault 路径 |
| `skills/.../SKILL.md` | 默认配置表格 | 文档中的 vault 路径描述 |
| `skills/.../references/*.md` | 路径示例 | 所有文档中的路径示例 |

**查找替换模式** (以当前工作区为例):
```
查找: C:\\Users\\<用户名>\\Documents\\obsidian-vault
替换: <你的 vault 路径>
```

### 步骤 3: 安装 npm 依赖

```bash
cd 目标工作区/obsidian-mcp
npm install
```

验证安装:
```bash
ls node_modules/@modelcontextprotocol/sdk/dist/cjs/server/index.js
ls node_modules/playwright-core/index.js
# 两者都应有输出
```

### 步骤 4: 检查系统依赖

| 依赖 | 检查命令 | 最低版本 |
|------|---------|---------|
| Node.js | `node --version` | 18.0.0 |
| Obsidian | 桌面应用已安装 | 1.0.0 |
| PowerShell | `powershell --version` | 5.1 (Windows 自带) |

查找 Obsidian 路径（如不在常见位置）:
```powershell
Get-Command obsidian -ErrorAction SilentlyContinue
# 或
Get-ChildItem -Path $env:LOCALAPPDATA -Filter Obsidian.exe -Recurse -Depth 4
```

### 步骤 5: 配置 Claude Code MCP

在项目 `.claude/mcp.json` 中添加:

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "node",
      "args": ["<工作区绝对路径>/obsidian-mcp/server.cjs"],
      "env": {
        "OBSIDIAN_DEBUG_PORT": "9223"
      },
      "disabled": false
    }
  }
}
```

### 步骤 6: 更新 CLAUDE.md (可选但建议)

在工作区 `CLAUDE.md` 中添加:

```markdown
## Obsidian 控制

- 默认 vault: <vault 路径>
- 以后 Markdown 输出默认进入该 vault
- 直接控制 Obsidian 时使用 MCP 工具: obsidian_status, obsidian_open_note 等
- 主控制路径: Electron CDP (非 obsidian:// URI)
```

### 步骤 7: 验证

按顺序执行:

```bash
# 1. 启动 Obsidian (如未运行)
node -e "require('./skills/obsidian-control/scripts/obsidian_cdp_core.cjs')" \
  && echo "Core module OK"

# 2. MCP smoke test
cd obsidian-mcp && node smoke-test.cjs obsidian_status

# 3. 如果 Obsidian 未启动，先 launch
node smoke-test.cjs obsidian_launch force_restart=true

# 4. 验证文件列表
node smoke-test.cjs obsidian_list_files

# 5. 打开一个笔记
node smoke-test.cjs obsidian_open_note note_path="Home.md"

# 6. 整仓验证
node smoke-test.cjs obsidian_verify_all
```

## 跨平台注意事项

### Windows → macOS

1. **PowerShell → bash**: macOS 不自带 PowerShell。Obsidian 启动脚本需改为 bash:
   ```bash
   #!/bin/bash
   open -a Obsidian --args --remote-debugging-port=9223
   ```
2. **路径分隔符**: `\\` → `/`
3. **Obsidian 路径**: macOS 通常在 `/Applications/Obsidian.app/Contents/MacOS/Obsidian`

### Windows → Linux

1. **启动方式**: 直接用二进制:
   ```bash
   /usr/bin/obsidian --remote-debugging-port=9223
   ```
2. **路径分隔符**: `\\` → `/`
3. **Vault 路径**: 一般是 `~/Documents/Obsidian Vault/`

## 依赖兼容性矩阵

MCP SDK 加载使用了多路径候选机制 (`requireFromCandidates`):

```javascript
// server.cjs 中的加载顺序
1. obsidian-mcp/node_modules/@modelcontextprotocol/sdk/dist/cjs/...
2. ../.claude/edge-mcp/node_modules/@modelcontextprotocol/sdk/dist/cjs/...
3. ../edge-cdp-mcp/node_modules/@modelcontextprotocol/sdk/dist/cjs/...
```

`obsidian_cdp_core.cjs` 中的 playwright-core 加载:

```javascript
1. obsidian-mcp/node_modules/playwright-core
2. ../.claude/edge-mcp/node_modules/playwright-core
3. ../node_modules/playwright-core
4. require("playwright-core")  // 全局安装的
```

这种设计允许多个项目共享同一份依赖，减少重复安装。

## 自动化迁移脚本

以下是一个参考用的 PowerShell 自动化迁移脚本:

```powershell
param(
  [string]$SourceWorkspace,
  [string]$TargetWorkspace,
  [string]$TargetVault
)

$dirs = @("obsidian-mcp", "skills/obsidian-control")
foreach ($d in $dirs) {
  Copy-Item -Recurse (Join-Path $SourceWorkspace $d) (Join-Path $TargetWorkspace $d) -Force
}

$replacements = @{
  "C:\\Users\\<用户名>\\Documents\\obsidian-vault" = $TargetVault
}

$files = @(
  "obsidian-mcp/server.cjs",
  "skills/obsidian-control/scripts/obsidian_cdp_core.cjs",
  "skills/obsidian-control/scripts/obsidian_control.ps1",
  "skills/obsidian-control/SKILL.md"
)

foreach ($f in $files) {
  $path = Join-Path $TargetWorkspace $f
  $content = Get-Content $path -Raw
  foreach ($k in $replacements.Keys) {
    $content = $content.Replace($k, $replacements[$k])
  }
  Set-Content $path $content
}

Set-Location (Join-Path $TargetWorkspace "obsidian-mcp")
npm install

Write-Output "迁移完成。请执行验证步骤。"
```

## 版本兼容记录

| Obsidian 版本 | Electron 版本 | CDP 可用性 | 内部 API 兼容 |
|--------------|--------------|-----------|-------------|
| 1.12.7 | 34.2.0 | ✅ | ✅ 全部正常 |
| 1.8.10 | 34.2.0 | ✅ | ✅ 全部正常 |
| 1.7.x | ~32.x | 未测试 | 预计兼容 |
| < 1.0 | < 28.x | 未测试 | `--remote-debugging-port` 可能不支持 |
