# Claude Code Workflow

> 这是一套 Claude Code 工作流配置的**参考实现和快速部署工具**——把我在 Windows 上日常使用的配置、工具和脚本打包成一个可复用的安装器。**它不是"一键变大神"的魔法，而是一个帮你省去手动配置时间的起点。**

## 这个项目做了什么

本质上就一件事：**把你需要手动编辑的配置文件（settings.json / mcp.json / .bashrc / CLAUDE.md 等），通过模板渲染自动生成并部署到正确的位置。** 同时附带了一些我日常使用的 Python/Node.js 工具脚本和 MCP 服务器。

它的价值在于：**如果你本来就打算配置这些东西，它能帮你从半天的手动配置缩短到几分钟。** 如果你不知道这些东西是什么、为什么要配置它们，那这个项目目前对你来说参考价值大于实用价值。

## 功能与评估

以下是对每个组件的诚实评估，按实用程度排序。

### 高价值部分

| 功能 | 实际是什么 | 为什么有用 |
|------|-----------|-----------|
| **Claude Code 环境配置** | 自动安装 Claude Code + 配置 DeepSeek API 作为后端 | DeepSeek API 价格远低于 Anthropic 官方，日常使用一个月几块钱。省去手动折腾环境变量和模型映射 |
| **8 个 CLI 工具** | starship / fzf / zoxide / ripgrep / eza / bat / delta / pandoc | 都是开源社区广泛使用的终端效率工具，独立于 AI 编程也能大幅提升命令行体验。starship 美化提示符，fzf 模糊搜索历史，zoxide 智能跳转目录 |
| **15 条行为规则** | CLAUDE.md 中的行为约束 | 让 Claude Code 始终用中文回复、主动闭环任务、优先查官方文档等。这些规则本身不依赖任何工具，可以直接复制使用 |
| **会话管理工具** | session_manager.py + session_questions.py | 在终端里快速搜索、恢复历史会话。解决 Claude Code 对话多了之后找不回来的问题 |

### 有门槛但可能有用

| 功能 | 实际是什么 | 限制和前提 |
|------|-----------|-----------|
| **Edge 浏览器 MCP** | 通过 CDP 协议控制一个独立 Edge 实例，实现网页自动化 | 需要额外启动专用 Edge 实例。对做网页调试/自动化的开发者有用 |
| **ms365 MCP** | 通过 Microsoft Graph API 操作邮件/日历/OneDrive | 首次需要 OAuth 浏览器登录。需要 Microsoft 365 账号 |
| **Python 工具集** | 多模态视觉识别（豆包 API）/ PDF 批量转 Markdown / Chroma RAG 知识库 / Word 文档生成 | 每个工具依赖不同的 Python 包和 API Key。视觉识别需要单独的豆包/ARK API Key |
| **本地 Skills** | 批量信息处理 / 文件整理 / 日常自动化 / Obsidian 控制 | 通用性一般，更多是我个人场景的参考实现 |

### 安装门槛较高（不建议普通用户装）

| 功能 | 为什么门槛高 |
|------|------------|
| **Obsidian MCP** | 需要 Obsidian 以特定参数启动、有独立的 vault 目录结构 |
| **AutoCAD MCP** | 需要 AutoCAD 2024-2026 + pywin32，纯 Windows + 商用软件依赖 |

### ⚠️ 关于 MCP 工具数量的提醒

MCP 服务器并非越多越好。注册过多工具可能导致 Claude Code 在工具选择时出现遗漏，甚至你都不知道 AI "看不到"某些工具了。**建议只启用自己真正需要的，而不是全装。**

## 关于 AI 后端

这个项目**不提供任何 AI 模型**。它默认配置使用 **DeepSeek 的公开 API**（模型 ID: `deepseek-v4-pro`），通过 DeepSeek 官方的 Anthropic 兼容端点调用。你需要自己去 [DeepSeek 平台](https://platform.deepseek.com/api_keys) 注册并获取 API Key。

如果你更倾向于用 Anthropic 官方 API，修改 `settings.json` 中的 `ANTHROPIC_BASE_URL` 即可。

## 前置条件

| 需要 | 说明 |
|------|------|
| Windows 10/11 | 当前只支持 Windows |
| Git for Windows | 提供 Git Bash 终端环境 |
| 网络 | 下载依赖需要 |

Node.js 和 Python 安装器会自动检测，缺失时提示你安装。

## 安装

**建议先 clone 再看代码，确认没问题再运行：**

```bash
git clone https://github.com/sherlock-miller/claude-code-workflow.git
cd claude-code-workflow
# 阅读 install.ps1 后再决定是否运行
powershell -ExecutionPolicy Bypass -File install.ps1
```

如果选择最小安装（跳过所有可选组件）：

```bash
powershell -ExecutionPolicy Bypass -File install.ps1 -Quick
```

也有不安全的快捷方式（`iex`），但**不推荐**——你应该先看代码。

## 安装后

```bash
# 重启 Git Bash，然后：
cc                              # 启动 Claude Code
claude-workflow verify          # 诊断检查
```

## API Key 说明

安装过程中需要输入 DeepSeek API Key（必填），可选输入豆包 ARK API Key（用于视觉识别工具）。

Key 存储在 `~/.claude/.env` 中，文件权限限制为仅当前用户可读，但内容是明文。如需要更强的安全措施，建议使用 Windows 凭据管理器。

## 文件结构

```
~/.claude/                        # 安装后的目录
├── settings.json                 # 全局配置
├── mcp.json                      # MCP 服务器注册
├── CLAUDE.md                     # 行为规则和能力说明
├── .env                          # API Key
├── hooks/                        # 通知和路径保护
├── tools/                        # Python + Node.js 工具
├── edge-mcp/                     # Edge CDP 服务器
├── skills/                       # 本地技能
└── scripts/                      # 维护脚本
```

## 卸载

```bash
rm -rf ~/.claude/
# 在 ~/.bashrc 中删除 "# >>> claude-workflow" 到 "# <<< claude-workflow" 之间的内容
```

## 贡献与交流

这个项目的目标是**降低 Claude Code 工作流配置的门槛**，让更多人能快速上手，并在此基础上共同改进配置方案。

如果你有更好的工具、更优雅的配置方式，或者发现了 bug，欢迎提 Issue 或 PR。如果你基于这套配置做了自己的定制版本，也欢迎分享经验。

## License

MIT
