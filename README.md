# Claude Code Workflow — 一键安装包

> Claude Code + DeepSeek 全套工作流，一条命令部署到 Windows。

## 这是什么？

一套经过数月打磨的 Claude Code 工作流配置，包含：

- **AI 后端**：DeepSeek V4 Pro（128K 上下文）+ Claude Code 2.1.153
- **4 个 MCP 服务器**：Edge 浏览器控制 / Obsidian 笔记 /  Microsoft 365 / AutoCAD（可选）
- **14 个自定义工具**：多模态视觉识别 / PDF 批量处理 / RAG 知识库 / Word 文档生成 / 会话管理
- **6 个 Skills**：批量信息处理 / 日常自动化 / 文件整理 / Obsidian 控制
- **8 个 CLI 增强**：starship 提示符 / fzf 搜索 / zoxide 跳转 / ripgrep / eza / bat / delta / pandoc
- **15 条行为规则**：中文回复 / 自主闭环 / 遇墙问梯 / 官方文档优先 等

## 前置条件

| 需要 | 说明 |
|------|------|
| Windows 10/11 | 64 位 |
| Git for Windows | 提供 Git Bash 环境 |
| 网络连接 | 下载依赖 + API 调用 |

**其他一切（Node.js / Python / Claude Code / CLI 工具）由安装器自动处理。**

## 快速安装

### 方式一：一行命令（推荐）

在 **Git Bash** 中运行：

```bash
powershell -ExecutionPolicy Bypass -Command "iex (irm https://raw.githubusercontent.com/sherlock-miller/claude-code-workflow/main/bootstrap.ps1)"
```

### 方式二：手动克隆

```bash
git clone https://github.com/sherlock-miller/claude-code-workflow.git
cd claude-code-workflow
powershell -ExecutionPolicy Bypass -File install.ps1
```

### 安装选项

```bash
# 完整安装（所有组件）
powershell -File install.ps1 -Full

# 最小安装（只有核心配置）
powershell -File install.ps1 -Quick

# 非交互式安装（预先提供参数）
powershell -File install.ps1 -Yes -DeepSeekKey "sk-your-key" -WorkspaceDir "C:\Users\you\projects"
```

## 安装后

```bash
# 重启 Git Bash，然后：
cc                              # 启动 Claude Code
ccc                             # 恢复上次会话
claude-workflow verify          # 运行诊断检查
claude-workflow status          # 快速状态
claude-workflow update          # 更新到最新版
```

## API 密钥获取

安装过程中会提示输入两个 API Key：

| API | 用途 | 获取地址 |
|-----|------|----------|
| DeepSeek | Claude Code 的 AI 引擎（必填） | https://platform.deepseek.com/api_keys |
| 豆包 ARK | 图片/PDF 视觉识别（可选） | https://console.volcengine.com/ark |

Key 加密存储在 `~/.claude/.env` 中，不会被分享或上传。

## 组件说明

| 组件 | 说明 | 依赖 |
|------|------|------|
| **core** | settings.json / CLAUDE.md / hooks | 必装 |
| **edge-cdp** | Edge 浏览器 MCP（22 个工具，独立 profile） | Node.js |
| **obsidian-mcp** | Obsidian 笔记控制 MCP（8 个工具） | Node.js + Obsidian |
| **autocad-mcp** | AutoCAD 图层/样式管理 MCP（21 个工具） | Python + AutoCAD |
| **ms365-mcp** | Microsoft 365 集成（邮件/日历/OneDrive） | Node.js |
| **cli-tools** | starship/fzf/zoxide/rg/eza/bat/delta | 无 |
| **python-tools** | 视觉识别 / 文档处理 / RAG / Word 生成 | Python |
| **skills** | 批量处理 / 文件整理 / 日常自动化 | 无 |

## 文件结构

```
~/.claude/                        # 安装后的目录
├── settings.json                 # 全局配置（权限/hooks/API）
├── mcp.json                      # MCP 服务器注册
├── CLAUDE.md                     # 行为规则和能力定义
├── .env                          # API Key（仅本地，gitignored）
├── .workflow-version             # 版本追踪
├── installed_paths.json          # 机器路径注册表
├── hooks/
│   ├── notify.ps1                # 任务完成通知（Toast+蜂鸣）
│   └── validate-path.ps1         # 工作区边界保护
├── tools/                        # Python + Node.js 工具脚本
├── edge-mcp/                     # Edge CDP MCP 服务器
├── obsidian-mcp/                 # Obsidian MCP 服务器（可选）
├── autocad-mcp/                  # AutoCAD MCP 服务器（可选）
├── skills/                       # 本地技能定义
├── scripts/                      # 维护脚本（verify/update）
└── projects/                     # Memory 系统（自动积累）
```

## 卸载

```bash
# 删除安装目录即可
rm -rf ~/.claude/

# 清理 bashrc 中的集成块（手动编辑或运行）
powershell -Command "(Get-Content ~/.bashrc) -replace '(?s)# >>> claude-workflow.*# <<< claude-workflow\r?\n?', '' | Set-Content ~/.bashrc"
```

## License

MIT
