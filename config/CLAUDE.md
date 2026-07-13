# Claude Code 全局能力配置

> 最后更新: 2026-07-06 | 所有能力在任意工作目录中可用

### DeepSeek API + Claude Code 配置（2026-05-31 基于双方官方文档验证）
- **使用教程**: `{{WORKSPACE_DIR}}\Claude Code + DeepSeek API 使用指南.md`
- **关键发现**: DeepSeek V4 Pro 思考深度实际只有两档（low/medium/high→high, xhigh/max→max）
- **模型映射**: Opus/Sonnet→Pro, Haiku/Subagent→Flash（详见 [[model_mapping_internal]]）
- **文档获取**: Claude Code用llms.txt+.md, DeepSeek用本地HTML
- **调研方法论**: [[research_methodology]] — 先原始文档→双向验证→确认后修改→记录来源

## 能力总览

### 多模态视觉理解
- `~/.claude/tools/multimodal_vision.py` — 文件识别 (图片/PDF/PPTX → 文本)
- `~/.claude/tools/clipboard_vision.py` — 剪贴板截图识别 (Win+Shift+S → 识别)
- 模型: Doubao-Seed-2.0-lite (默认) + Doubao-Seed-2.0-pro (ep-20260602111026-9wcsc, 高精度任务用)
- 切换: `ARK_MODEL="ep-20260602111026-9wcsc" python multimodal_vision.py ...`

### 批量文档处理 + RAG 知识库
- `~/.claude/tools/doc_preprocessor.py` — PDF/PPTX 批量 → Markdown (断点续传+并发)
- `~/.claude/tools/knowledge_base.py` — Markdown → Chunks → 嵌入 → Chroma 向量库 → 检索
- 模式: 离线预处理 + 在线 RAG 检索
- 用途: 课程大作业等需要理解大量课件资料的场景

### 浏览器自动化 (Edge CDP MCP)
- `~/.claude/edge-mcp/server.js` — 22个浏览器控制工具 (v1.2.0)
- **双 Edge 实例**: Claude Edge (9224, 独立 profile, 后台最小化) vs 用户 Edge (9222)
- **视觉标识**: Claude Edge 页面顶部紫色渐变条，一眼可区分
- **Cookie 自动同步**: 启动时检测+按需从用户 Edge 同步 (`launch-claude-edge.cjs` + `sync-cookies.mjs`)
- `edge_analyze_page` — 截图+豆包视觉AI分析页面（比DOM文本提取详细得多）
- `edge_get_content mode="vision"` — 视觉提取页面内容

### Microsoft 365 集成 (ms365 MCP)
- `@softeria/ms-365-mcp-server` — 通过 Microsoft Graph API 操作个人 M365 账户
- **全局级 MCP** (`--scope user`)，所有目录可用
- 已认证账户: `{{MS365_ACCOUNT}}` (Microsoft 365 Premium)
- 能力: 邮件/日历/OneDrive/待办事项/联系人/OneNote/用户设置
- 注: Teams/SharePoint/Planner/Office 文档编辑需要 work/school 账户

### Obsidian 桌面应用控制 (Obsidian MCP)
- `~/.claude/obsidian-mcp/server.cjs` — 8个 MCP 工具，通过 Electron CDP 直连 Obsidian
- `~/.claude/skills/obsidian-control/scripts/obsidian_cdp_core.cjs` — CDP 控制核心
- `~/.claude/skills/obsidian-control/scripts/obsidian_control.ps1` — PowerShell 启动器
- 8 工具: `obsidian_status` / `obsidian_launch` / `obsidian_list_files` / `obsidian_current_note` / `obsidian_open_note` / `obsidian_screenshot` / `obsidian_verify_note` / `obsidian_verify_all`
- 主 vault: `{{OBSIDIAN_VAULT}}`, CDP 端口: 9225
- 前置: Obsidian 需以 `--remote-debugging-port=9225` 启动 (9223 被 Edge 占用)

### Obsidian AI 插件 (Copilot)
- **Copilot for Obsidian** v3.3.3 — 侧边栏 AI 聊天，直接走 DeepSeek HTTP API，不走 shell spawn
- 安装在主 vault 的 `.obsidian/plugins/copilot/`
- **为什么是 Copilot 而非 Agentic Copilot/Claudian**: [[windows_spawn_chinese_bug]] — Windows 上 spawn CLI + shell:cmd.exe 会破坏中文，Copilot 用 HTTP API 从根本上避免了这个问题
- 与 Obsidian MCP 的互补: 插件 = 你在 Obsidian 里用 AI；MCP = AI 在终端里操控 Obsidian
- 详细选型过程: [[obsidian_ai_plugin]]

### DeepSeek Anthropic Gateway — 消息格式代理
- **当前状态 (2026-05-29)**: 全局 `claude` 已锁定 **2.1.153**（直连 DeepSeek，无需代理，稳定可用）
- **兼容性问题**: Claude Code 2.1.154+ 有三个兼容 Bug，需要链式代理解决：
  1. System role 在 messages[] 数组内 (HTTP 400)
  2. tool_use 消息缺少 thinking 块
  3. SSE 流中 thinking 事件导致内部错误
- **链式代理方案** (用于测试 2.1.156+):
  - `~/.claude/tools/deepseek-proxy.mjs` — Node.js 代理 (:8787)，修复 system role 问题
  - `dsv4-cc-proxy` (pip, v1.8.0) — Python 代理 (:16889)，修复 thinking 块问题
  - 启动链: `ccproxy` (Git Bash 函数) 或 `~/.claude/tools/deepseek-proxy-start.ps1`
- **Git Bash 启动**:
  - 稳定版: `cc` 或 `claude` → 2.1.153 + 直连 DeepSeek
  - 测试版: `cctry` → 启动代理链 + 运行 2.1.156
  - 手动代理链: `ccproxy` → 只启动代理 (不启动 Claude)
- **环境变量** (用户级): `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic` (直接), `ANTHROPIC_MODEL=deepseek-v4-pro[1m]`
- **自动更新已禁用**: `DISABLE_AUTOUPDATER=1` 三重部署（用户环境变量 + `settings.json` + `~/.bashrc`），防止 Claude Code 启动时自动升级
- **降级后文件锁定**: 如遇到 `EBUSY claude.exe` 错误，说明有僵死 claude 进程占用文件，需 `Get-Process -Name claude \| Stop-Process -Force` 后重试
- **升级监控**: 2.1.156 是最新版本，后续版本需先 `cctry` 测试是否修复兼容性后再解锁升级

### 文档生成与演示 (PPT + Word)
- **Marp CLI v4.4.0** — Markdown → PPTX/PDF，24K Stars，已通过豆包视觉验证
  - 用法: `marp slides.md --pptx -o output.pptx`
  - 限制: PPTX 为位图渲染（非可编辑文本），适合展示不适合二创
- **Word 文档生成器** — `~/.claude/tools/word_builder.py` + `~/.claude/tools/word_omml.py`
  - python-docx 生成结构 + OMML 公式注入 + 专业表格样式
  - **关键规则**（基于激光大作业踩坑）:
    - 禁 Win32COM 做内容编辑（仅用于 .doc→.docx / .docx→.pdf 转换）
    - 样式统一英文名（Heading 1/2/3），中文通过 w:rFonts/eastAsia 回退
    - 全链路 UTF-8，Python stdout 必须包 io.TextIOWrapper(buffer, encoding='utf-8')
    - 公式用 LaTeX 标记，Word 中 MathType 一键转原生公式
- **docxtpl v0.20.2** — Jinja2 模板驱动批量生成
- **pandoc v3.2.1** — 30+ 格式互转 (`~/.local/bin/pandoc.exe`)
- **docx-js** (npm `docx`) — Anthropic/Codex 官方路线，OOXML 质量优于 python-docx
  - 参考: Anthropic 官方 docx skill（已研究），`doc_coauthoring` skill

### 蒸馏 Skills（全局安装）
- **huashu-nuwa** — 女娲：蒸馏公众人物思维模型，6路并行搜索+三重验证
  - 触发词: 「造skill」「蒸馏XX」「XX的思维方式」
  - 预蒸馏: Jobs/Musk/Munger/Feynman/张一鸣 等 17 位
- **dot-skill** — 同事：蒸馏同事/关系/名人，Work Skill + Persona 双层架构
  - 来源: titanwings/colleague-skill (18.8K Stars)
- 安装方式: `npx skills add <repo> --all -g -y`
- 备选: 仓颉(认知植入)、永生(4D蒸馏+反蒸馏)、万魂幡(万能输入)

### Obsidian 社区插件（8个已安装）
- **Dataview** — 笔记数据库查询 | **Templater** — 高级模板引擎
- **Calendar** — 日历+每日笔记 | **Kanban** — 看板视图
- **Tasks** — 跨文件任务管理 | **QuickAdd** — 快速捕获
- **Copilot** — AI聊天 (DeepSeek API) | ***(Obsidian MCP)*** — 外部控制
- 安装路径: `{{OBSIDIAN_VAULT}}\.obsidian\plugins\`

### Skills
- `obsidian-control` — Obsidian 桌面应用直接控制：打开/列出/验证笔记、截图、批量校验
- `file-organizer` — 文件分类/重命名/去重/归档
- `batch-processor` — 网页抓取/PDF提取/报告生成
- `daily-automation` — 备份/提醒/周报

### AutoCAD 控制 (MCP Server)
- `~/.claude/tools/autocad_mcp_server.py` — MCP Server (stdio JSON-RPC)，通过 COM 接口控制 AutoCAD
- 配置在 `~/.claude/mcp.json` → `autocad` 条目
- **支持版本**: AutoCAD 2024-2026 (实测 2025 可用)
- **连接方式**: 优先连接已运行实例
- **能力**: 图层 CRUD+批量+GB/T 预设、文字/标注样式管理、线型加载、系统变量读写
- **能力**: 图层管理（CRUD+批量+预设）、样式管理（文字/标注）、线型加载、系统变量读写
- **预设方案**: `preset layers --gb` (18个GB/T标准图层)、`preset dimstyle --arch` (建筑标注样式)

### 会话历史管理
- **`claudecode-history-viewer`** — Web UI 会话浏览器 (`npx -y claudecode-history-viewer --language zh`)
  - 端口 3747，中文界面，暗色主题，全文搜索，支持会话恢复
- **`session_questions.py`** — 终端快速提问索引 (`python ~/.claude/tools/session_questions.py`)
  - `--latest 5` 最近 N 个会话 | `--search 关键词` 搜索 | `--export` 导出 Markdown
- **会话历史管理**: `python {{INSTALL_DIR}}\tools\session_manager.py list|archive|rename|search` — 终端会话列表/归档/重命名/搜索
- **Claude Code 技巧**: /btw(旁路提问) /goal(自主多轮) /context(上下文用量) /effort(推理深度) /plan(计划模式) — 详见 [[claude_code_hidden_features]]

### 配置
- **权限模式**: `defaultMode: "acceptEdits"` — 文件编辑自动批准，减少授权弹窗
- **推理深度**: `effortLevel: "max"` — DeepSeek V4 Pro 实际只有 high/max 两档，max 为最强模式

### Hooks
- **Stop / PermissionRequest**: `~/.claude/hooks/notify.ps1` — Windows Toast 原生通知 + BEL 蜂鸣 + 系统声音
- **PreToolUse**: `~/.claude/hooks/validate-path.ps1` — 工作区边界保护：区内自动放行，区外弹出权限询问
  - 白名单: `~/.claude/`, VS Code 配置, Obsidian vault
  - 危险命令和敏感文件由 `permissions.deny` 拦截，不在此脚本中处理

### 关键路径
| 用途 | 路径 |
|------|------|
| 全局 settings | `~/.claude/settings.json` |
| 全局 mcp | `~/.claude/mcp.json` |
| Edge CDP MCP | `~/.claude/edge-mcp/` |
| Obsidian MCP | `~/.claude/obsidian-mcp/` |
| ms365 MCP | `npx -y @softeria/ms-365-mcp-server` (项目级 MCP) |
| Hooks | `~/.claude/hooks/` |
| Skills | `~/.agents/skills/` (全局 npx skills install) + `~/.claude/skills/` |
| Tools | `~/.claude/tools/` (word_builder, word_omml, multimodal_vision, etc) |
| Word/Ppt Test | `{{WORKSPACE_DIR}}/test/` |
| Knowledge Bases | `~/.claude/knowledge_bases/` |
| Memory | `~/.claude/projects/` |
| Shell 配置 | `~/.bashrc`, `~/.config/starship.toml`, `~/.gitconfig` |
| CLI 工具链 | `~/.local/bin/` (starship, fzf, zoxide, rg, eza, bat, delta) |
| 终端文档 | `~/.claude/projects/E--claude-code/memory/terminal_toolchain.md` |

## Memory 系统

跨会话持久记忆，存储在 `~/.claude/projects/<项目>/memory/` 中。记录用户偏好、项目上下文、能力配置、反馈等。在任意目录工作时自动加载 `MEMORY.md` 索引。

## 行为规则（全局生效）

- **始终用中文回复**: 无论用户用什么语言提问，始终用中文回复。禁止输出英文对话内容。
- **遇墙问梯**: 遇到被墙的网站（HuggingFace, GitHub raw 等）导致连接超时/403，直接请用户打开梯子，不自行寻找国内镜像或其他 workaround。
- **字数统计算实测**: 统计英文词数必须用 Python 脚本等工具逐词计数，禁止凭视觉扫读估算。原因：扫读会漏掉功能词(a/the/of)、多词短语被当成单概念、Markdown 分行让文本显得比实际短——曾把 850 词估成 560。
- **最终回复分隔线**: 每条面向用户的最终回复（非工具输出、非工作过程）开头必须加一行分隔线 `━━━━━━━━━━━━━━━━━━━━━━━━━━━━` 作为视觉标记，让用户一眼区分工作过程输出和最终回答。分隔线要单独一行，前后各空一行。
- **配置必须基于官方文档验证**: 涉及 API 参数、模型名、effort 级别等技术配置时，不能依赖训练数据中的记忆，必须读取官方文档原文验证。回忆的信息经常与官方文档不一致，直接使用可能导致配置错误或程序崩溃。
- **解决方案优先找现成的**: 优先去 GitHub 等平台找已有项目/工具/脚本→借鉴类似项目的代码实现→不到万不得已不自己新创。自己造轮子容易出错还浪费时间。
- **信息获取优先官方+最新**: 优先读官方文档、大平台、今年/本月的最新信息，不依赖模型记忆中可能过时的数据。
- **遇到阻碍主动解决**: 工具报错、域名被拦、编码异常时主动排查根因并修复，不默默绕过。绕过的问题最后都会成为隐患。
- **自主工作闭环**: 用户期望自主调研→部署→测试→验证的完整闭环。装完工具后必须实际使用并测试效果（PPT/Word→豆包视觉验证，代码→运行对比），不等用户要求。
- **消息连发处理**: 收到多条指令时立即创建 TaskCreate 任务列表追踪，独立任务用 run_in_background 并行，每完成一个更新状态。

### Python: `{{PYTHON_PATH}}`
