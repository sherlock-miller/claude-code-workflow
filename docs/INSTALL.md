# Claude Code Workflow — 安装指南

> 目标：让从未用过 Claude Code 的人，也能在 **5 分钟内** 拥有一个功能完整的 AI 编程工作环境。

## 准备工作

### 1. 确认你的系统

- Windows 10 或 Windows 11（64 位）
- 能上网

### 2. 安装 Git for Windows（如果还没装）

Git for Windows 会同时安装 **Git Bash**（我们后续操作都在这个终端里进行）。

1. 打开 https://git-scm.com/download/win
2. 下载 64-bit 版本，双击安装
3. 安装过程中一路点「Next」使用默认设置即可
4. 安装完成后，在桌面右键 → 选择 **「Git Bash Here」**，如果弹出一个命令行窗口，说明安装成功

> 如果已经有 Git Bash，跳过这一步。

### 3. 检查 Node.js 和 Python

在 Git Bash 中运行以下命令，检查是否已安装：

```bash
node --version    # 应该显示 v18 或更高
python --version  # 显示 3.x 即可
```

- **如果 node 没装**：去 https://nodejs.org/ 下载 LTS 版本安装
- **如果 python 没装**：去 https://www.python.org/downloads/ 下载安装（勾选 "Add Python to PATH"）
- 两个都装了但版本太旧也没关系，安装器会提示你

> 如果你不想用 Python 相关的工具（视觉识别、文档处理），不装 Python 也可以。安装器会跳过那部分。

---

## 安装

### 一键安装（推荐）

打开 **Git Bash**，粘贴下面这条命令，回车：

```bash
powershell -ExecutionPolicy Bypass -Command "iex (irm https://raw.githubusercontent.com/sherlock-miller/claude-code-workflow/main/bootstrap.ps1)"
```

安装器会自动：
1. 检测你的电脑环境
2. 如果没有 Claude Code，帮你装上
3. 让你选择要装哪些组件
4. 引导你输入 API Key
5. 把所有配置文件渲染好
6. 安装所有依赖
7. 配置 Shell 集成

### 安装过程中的选择

安装器会问你几个问题，大部分直接回车用默认值就行：

| 问题 | 建议 | 说明 |
|------|------|------|
| Workspace directory | 直接回车 | 默认为 `C:\Users\你的用户名\projects` |
| Edge CDP MCP | Y | 浏览器自动化，很实用 |
| Obsidian MCP | N | 没用 Obsidian 就跳过 |
| AutoCAD MCP | N | 没用 AutoCAD 就跳过 |
| Microsoft 365 MCP | Y | 邮件/日历/OneDrive 集成 |
| CLI Tools | Y | 增强终端体验（starship 等） |
| Python Tools | Y | 视觉识别/文档处理工具 |
| Skills | Y | 批量处理/文件整理 |
| NPM Skills | N | 高级功能，可后续安装 |

### 关于 API Key

安装器会提示你输入两个 Key：

**DeepSeek API Key（必填）**

这是 Claude Code 运行所需的 AI 后端。

1. 打开 https://platform.deepseek.com/api_keys
2. 注册/登录 DeepSeek 账号
3. 点击「创建 API Key」，复制生成的 Key
4. 粘贴到安装器中

> DeepSeek API 价格非常便宜，日常使用一个月花费通常在 10 元以内。

**豆包/ARK API Key（可选）**

用于图片识别、PDF 转文字等视觉功能。不需要可以跳过。

1. 打开 https://console.volcengine.com/ark
2. 注册火山引擎账号
3. 创建 API Key 并复制
4. 粘贴到安装器中（或直接回车跳过）

---

## 安装后

### 第一次启动

1. **重启 Git Bash**（关掉再打开）
2. 输入 `cc`，回车

你会看到一个完全配置好的 Claude Code 环境。试试这些命令：

```
/help        → 查看帮助
/context     → 查看上下文使用量
```

### 验证安装

在 Git Bash 中运行：

```bash
claude-workflow verify
```

你会看到一份详细的诊断报告，每一项都标有 PASS/WARN/FAIL。

### 如果遇到问题

**Q: 提示 "claude: command not found"**

A: 先运行 `source ~/.bashrc` 重载配置，如果还不行，重启 Git Bash。

**Q: API Key 不对**

A: 编辑 `C:\Users\你的用户名\.claude\.env`，修改 `ANTHROPIC_API_KEY=你的Key`。然后重启 Git Bash。

**Q: Edge CDP 工具用不了**

A: Edge Chrome DevTools Protocol 需要特定配置。运行：
```bash
node ~/.claude/edge-mcp/launch-claude-edge.cjs
```
这会启动一个专用的 Edge 实例。

**Q: 想卸载**

A: 删除 `C:\Users\你的用户名\.claude\` 目录，然后编辑 `~/.bashrc` 删除 `# >>> claude-workflow` 到 `# <<< claude-workflow` 之间的内容。

---

## 目录结构和文件说明

安装完成后，你的电脑上会多出这些文件：

```
C:\Users\你的用户名\
├── .bashrc                       ← Shell 配置（安装器追加了工作流配置）
├── .gitconfig                    ← Git 配置（安装器补充了必要设置）
├── .config\
│   └── starship.toml             ← 终端提示符美化
├── .local\
│   └── bin\                      ← CLI 增强工具
│       ├── starship.exe
│       ├── fzf.exe
│       ├── zoxide.exe
│       ├── rg.exe
│       ├── eza.exe
│       ├── bat.exe
│       └── delta.exe
└── .claude\                      ← 工作流核心目录
    ├── settings.json             ← 全局配置
    ├── mcp.json                  ← MCP 服务器注册
    ├── CLAUDE.md                 ← 行为规则和工具说明
    ├── .env                      ← API Key（加密存储，仅本地）
    ├── installed_paths.json      ← 路径注册表
    ├── hooks\                    ← 钩子脚本
    │   ├── notify.ps1            ← 任务完成通知
    │   └── validate-path.ps1     ← 工作区保护
    ├── tools\                    ← Python/Node.js 工具
    ├── edge-mcp\                 ← 浏览器自动化
    ├── skills\                   ← 技能包
    └── scripts\                  ← 维护脚本
```

---

## 进阶：自定义你的工作流

### 修改行为规则

编辑 `~/.claude/CLAUDE.md`，按你的需要调整规则。比如：
- 把语言改成英文：删掉 "始终用中文回复" 这一行
- 添加你自己的规则

### 添加新工具

把你写的 Python 脚本放到 `~/.claude/tools/` 下，Claude Code 会自动识别。

### 添加新 MCP 服务器

编辑 `~/.claude/mcp.json`，参考已有的配置添加新条目，然后重启 Claude Code。

### 更新工作流

```bash
claude-workflow update    # 更新所有组件
claude-workflow update --component edge-cdp  # 只更新浏览器自动化
```

---

## 获取帮助

- **GitHub Issues**: https://github.com/sherlock-miller/claude-code-workflow/issues
- **运行诊断**: `claude-workflow verify`
- **查看完整配置**: `cat ~/.claude/CLAUDE.md`
