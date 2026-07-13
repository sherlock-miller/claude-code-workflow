# Obsidian Electron CDP — 技术深度参考

## 为什么是 CDP

Obsidian 基于 Electron 34（对应 Chromium 132）。Electron 应用可以用 `--remote-debugging-port` 启动，暴露 Chrome DevTools Protocol 端点。通过 CDP 可以:

1. 直接注入 JavaScript 到 Obsidian 渲染进程
2. 调用 Obsidian 内部未文档化的 `window.app` API
3. 读取和操作 vault 状态
4. 截图验证界面

### URI 方案为什么被放弃

`obsidian://open?vault=...&file=...` 方案的问题是:
- 经常弹出 "Vault not found" 弹窗，缺乏可靠的状态反馈
- 只能单向触发操作，无法读取当前状态（活动文件、标签页等）
- 无法确认笔记是否真的在界面中激活

CDP 方案解决了所有这些读状态问题。

## 启动 Obsidian 调试模式

```powershell
# 基本启动
& "C:\Program Files\Obsidian\Obsidian.exe" --remote-debugging-port=9223

# 强制重启（先杀旧进程）
taskkill /f /im Obsidian.exe 2>$null
Start-Sleep 2
& "C:\Program Files\Obsidian\Obsidian.exe" --remote-debugging-port=9223
```

启动后验证 CDP 可用:
```bash
curl http://127.0.0.1:9223/json/version
# 返回 Browser, V8-Version, webSocketDebuggerUrl
```

## CDP 端点

| 端点 | 用途 |
|------|------|
| `/json/version` | 浏览器版本信息 (Browser, Protocol-Version, User-Agent, webSocketDebuggerUrl) |
| `/json` | 可调试页面列表 (type, url, title, webSocketDebuggerUrl) |
| `/json/new?url=...` | 创建新页面 |
| `/devtools/browser/<id>` | Browser 级别的 WebSocket |
| `/devtools/page/<id>` | Page 级别的 WebSocket |

## Playwright 连接方式

```javascript
const pw = require('playwright-core');

// 连接到 Electron CDP
const browser = await pw.chromium.connectOverCDP('http://127.0.0.1:9223');

// Electron 只有一个 BrowserContext
const contexts = browser.contexts();
const pages = contexts[0].pages();

// Obsidian 主窗口通常是唯一的 page
const page = pages[0];
```

### Electron 页面生命周期

```
┌──────────────────────┐
│   app://obsidian.md/ │
│   starter.html       │  ← 启动页: 未打开任何 vault
│                      │
│   ── vault-open ──► │
│                      │
│   app://obsidian.md/ │
│   index.html         │  ← 主界面: vault 已加载, window.app 可用
└──────────────────────┘
```

## 页面切换: starter → index

```javascript
// starter.html 上调用 IPC 打开 vault
const result = await page.evaluate((vaultPath) => {
  return window.electron.ipcRenderer.sendSync("vault-open", vaultPath, false);
}, "E:\\path\\to\\vault");

// 等待切换到 index.html
await page.waitForURL(url => url.toString().includes("index.html"), {
  timeout: 15000
});

// Obsidian 加载 vault 需要时间
await page.waitForTimeout(2000);
```

## Obsidian 内部 API 速查

> 以下 API 均未在 Obsidian 官方文档中公开，通过 `page.evaluate()` 注入调用。

### Vault 操作

```javascript
// 列出所有 Markdown 文件
app.vault.getMarkdownFiles()                    // → TFile[]
// 结果示例: [{ path: "Home.md", name: "Home.md", extension: "md", ... }, ...]

// 按路径获取文件对象（路径相对于 vault 根）
app.vault.getAbstractFileByPath("dir/note.md")  // → TFile | null

// 创建新文件（同时写入磁盘 + 注册到 vault 索引）
await app.vault.create("new.md", "content")     // → TFile

// 读取文件内容
await app.vault.read(file)                      // → string

// 修改文件内容
await app.vault.modify(file, "new content")

// 删除文件
await app.vault.delete(file)

// 获取 vault 名称
app.vault.getName()                             // → "obsidian-vault"

// 获取 vault 根路径
app.vault.adapter.basePath                      // → "E:\\path\\to\\vault"

// 检查文件是否存在于磁盘
await app.vault.adapter.exists("path/file.md")  // → boolean
```

### Workspace 操作

```javascript
// 获取或创建叶子视图 (tab)
const leaf = app.workspace.getLeaf(true)        // true = 新建 tab

// 在叶子视图中打开文件
await leaf.openFile(file)

// 将叶子设为活动
app.workspace.setActiveLeaf(leaf, true, true)   // (leaf, pushHistory, focus)

// 将叶子带到最前面
app.workspace.revealLeaf(leaf)

// 获取当前活动文件
app.workspace.getActiveFile()                   // → TFile | null

// 通过链接文本打开（支持 alias 和 block reference）
app.workspace.openLinkText("note.md", "", false)
```

### 其他有用 API

```javascript
// 所有已加载的 vault
app.vault.getAllLoadedVaults()                  // → Vault[]

// 获取所有叶子视图
app.workspace.getLeavesOfType("markdown")

// 获取最近打开的文件列表
app.workspace.getRecentFiles()

// 文档标题
document.title                                  // → "note - vault - Obsidian x.y.z"

// 当前页面 URL
window.location.href                            // → "app://obsidian.md/index.html"
```

## 核心注入脚本实现

### buildStatusScript — 状态查询

```javascript
() => {
  const a = window.app;
  if (!a) return { error: "window.app not available" };
  const vault = a.vault;
  return {
    available: true,
    activeFile: a.workspace?.getActiveFile?.()?.path || null,
    title: document.title || "",
    vaultName: vault.getName?.() || "",
    vaultPath: vault.adapter?.basePath || "",
    pageUrl: window.location.href,
    fileCount: vault.getMarkdownFiles?.()?.length || 0,
  };
}
```

### buildOpenScript — 打开笔记（含 fallback）

```javascript
async () => {
  const app = window.app;
  // 1. 尝试从 vault 索引获取
  let file = app.vault.getAbstractFileByPath(notePath);
  // 2. 新文件 fallback: 通过 vault.create 注册
  if (!file && fallbackContent) {
    file = await app.vault.create(notePath, fallbackContent);
  }
  // 3. 打开并激活
  const leaf = app.workspace.getLeaf(true);
  await leaf.openFile(file);
  app.workspace.setActiveLeaf(leaf, true, true);
  app.workspace.revealLeaf(leaf);
  return {
    ok: app.workspace.getActiveFile()?.path === notePath,
    activeFile: app.workspace.getActiveFile()?.path
  };
}
```

**Fallback 机制的必要性**: 当文件从外部（Claude Code Write 工具、git checkout 等）写入 vault 磁盘时，Obsidian 的文件监视器可能尚未索引该文件，此时 `getAbstractFileByPath` 返回 null。fallback 通过 Node.js `fs.readFileSync` 先读磁盘内容，再传给 `vault.create()` 在 Obsidian 内部注册。

### buildVerifyAllScript — 整仓验证流程

```
1. 获取 vault.getMarkdownFiles() → 文件列表
2. for each file:
   a. 检查磁盘上文件是否存在 (fs.existsSync)
   b. 存在 → 读内容 → buildOpenScript(file.path, content)
   c. 不存在 → buildOpenScript(file.path)
   d. buildCurrentScript() 验证 activeFile === file.path
   e. 统计 passed/failed
3. 返回 { total, passed, failed, failures[] }
```

## 常见问题与调试

### 问题 1: CDP 可用但 `window.app` 不可用

**症状**: CDP `/json/version` 返回正常，但 `page.evaluate()` 报 "window.app not available"

**原因**: 连接到的页面不是 `index.html`，可能是:
- `starter.html` — 未打开 vault
- 插件 webview — 如浏览器插件打开的第三方网页

**调试**: `curl http://127.0.0.1:9223/json` 查看页面列表

**解决**:
- 如果是 starter.html → 调用 `vault-open` IPC 切换
- 如果是 webview → 重启 Obsidian（旧实例可能只暴露了 webview）

### 问题 2: 新版 Obsidian API 变更

**症状**: 某个 API 调用返回 undefined 或报错

**应对**: 逐一验证关键 API:
```javascript
// 每次 Obsidian 升级后验证这些
typeof window.app                          // "object"
typeof window.app.vault.getMarkdownFiles   // "function"
typeof window.app.vault.getAbstractFileByPath  // "function"
typeof window.app.workspace.getActiveFile  // "function"
typeof window.app.workspace.getLeaf        // "function"
```

### 问题 3: Electron `connectOverCDP` 超时

**症状**: `connectOverCDP` 抛出 timeout 错误

**解决**:
1. 检查端口是否正确 (`curl http://127.0.0.1:9223/json/version`)
2. 增加 `timeout` 参数: `connectOverCDP(url, { timeout: 30000 })`
3. 检查防火墙是否阻止 localhost 连接

## 依赖说明

| 包 | 版本 | 用途 | 安装 |
|----|------|------|------|
| `playwright-core` | ^1.54.0 | CDP 连接、页面操作、截图 | `npm i playwright-core` |
| `@modelcontextprotocol/sdk` | ^1.15.0 | MCP 协议 (Server, StdioServerTransport, Tool schemas) | `npm i @modelcontextprotocol/sdk` |

`playwright-core` 不含浏览器二进制（用系统已安装的 Electron/Obsidian），比完整 `playwright` 小 ~300MB。
