/**
 * launch-claude-edge.cjs — Claude 专属 Edge 启动器
 *
 * 启动独立的 Edge 实例供 Claude Code MCP 控制，确保：
 *   - 独立 profile (--user-data-dir=%USERPROFILE%/.claude/edge-profile)
 *   - IPv4 CDP (--remote-debugging-address=127.0.0.1, port 9224)
 *   - 后台最小化运行 (start /MIN + windowsHide)，不干扰用户正常使用
 *   - 启动后自动检查 cookie 数量，若稀疏则从用户 Edge (9222) 同步
 *
 * 用法：node launch-claude-edge.cjs
 * 依赖：sync-cookies.mjs（cookie 自动同步）
 */
const http = require("http");
const { execSync } = require("child_process");

const CDP_PORT = 9224;
const USER_DATA_DIR = `${process.env.USERPROFILE || process.env.HOME}/.claude/edge-profile`;

const EDGE_PATHS = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
];

function checkCdp() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${CDP_PORT}/json/version`, (res) => {
      res.resume();
      resolve(true);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(3000, () => { req.destroy(); resolve(false); });
  });
}

async function main() {
  if (await checkCdp()) {
    console.log("[INFO] Claude Edge 已在运行 (127.0.0.1:9224)");
    // Still check if cookie sync is needed
    try {
      console.log("[SYNC] Checking if cookie sync is needed...");
      execSync(`node "${__dirname}\\sync-cookies.mjs"`, {
        stdio: "inherit",
        timeout: 120000,
      });
    } catch (e) {
      console.error("[WARN] Cookie sync failed (non-fatal):", e.message);
    }
    return;
  }

  let edgePath = null;
  for (const p of EDGE_PATHS) {
    try { execSync(`test -f "${p}"`, { stdio: "ignore" }); edgePath = p; break; }
    catch (_) {}
  }
  if (!edgePath) throw new Error("找不到 Edge 安装路径");

  console.log("[INFO] 启动 Claude Edge (独立配置, 后台最小化)...");
  const args = [
    `--remote-debugging-port=${CDP_PORT}`,
    "--remote-debugging-address=127.0.0.1",
    "--remote-allow-origins=*",
    `--user-data-dir="${USER_DATA_DIR}"`,
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank",
  ].join(" ");

  execSync(`cmd /c start "" /MIN msedge ${args}`, { windowsHide: true, timeout: 10000 });

  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 1000));
    if (await checkCdp()) {
      console.log("[OK] Claude Edge 就绪 (127.0.0.1:9224, 独立配置, 后台运行)");

      // Auto-sync cookies if sparse
      try {
        console.log("[SYNC] Checking if cookie sync is needed...");
        execSync(`node "${__dirname}\\sync-cookies.mjs"`, {
          stdio: "inherit",
          timeout: 120000,
        });
      } catch (e) {
        console.error("[WARN] Cookie sync failed (non-fatal):", e.message);
      }

      return;
    }
  }
  console.error("[WARN] Claude Edge 可能未正常启动");
}

main().catch(err => { console.error("[FATAL]", err.message); process.exit(1); });
