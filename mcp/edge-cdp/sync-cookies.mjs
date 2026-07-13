/**
 * sync-cookies.mjs — Cookie 自动同步脚本
 *
 * 从用户 Edge (9222) 导出 cookie，导入到 Claude Edge (9224)。
 * 仅当 Claude Edge cookie 数 < MIN_COOKIES 阈值时才执行同步。
 *
 * 由 launch-claude-edge.cjs 在启动时自动调用，也可独立运行：
 *   node sync-cookies.mjs
 *
 * 实现方式：Playwright connectOverCDP → CDP Network.getAllCookies / Network.setCookie
 * 此举可正确处理 httpOnly / Secure / SameSite 等所有 cookie 属性。
 */

import { chromium } from "playwright";

const USER_CDP = "http://127.0.0.1:9222";
const CLAUDE_CDP = "http://127.0.0.1:9224";
const MIN_COOKIES = 500;

async function getCookies(cdpUrl, label) {
  const browser = await chromium.connectOverCDP(cdpUrl);
  const cdp = await browser.contexts()[0].newCDPSession(
    browser.contexts()[0].pages()[0] || await browser.contexts()[0].newPage()
  );
  const result = await cdp.send("Network.getAllCookies");
  await browser.close();
  console.log(`  ${label}: ${result.cookies.length} cookies`);
  return result.cookies;
}

async function main() {
  console.log("[SYNC] Checking cookie status...");

  // 1. Check Claude Edge cookie count
  let claudeCookies;
  try {
    claudeCookies = await getCookies(CLAUDE_CDP, "Claude Edge");
  } catch (e) {
    console.error(`[SYNC] Cannot connect to Claude Edge (9224): ${e.message}`);
    process.exit(1);
  }

  if (claudeCookies.length >= MIN_COOKIES) {
    console.log(`[SYNC] OK — Claude Edge has ${claudeCookies.length} cookies, no sync needed`);
    return;
  }

  console.log(`[SYNC] Only ${claudeCookies.length} cookies (threshold: ${MIN_COOKIES}), syncing...`);

  // 2. Check if user Edge is available
  let userCookies;
  try {
    userCookies = await getCookies(USER_CDP, "User Edge");
  } catch (e) {
    console.error(`[SYNC] Cannot connect to User Edge (9222): ${e.message}`);
    console.error("[SYNC] Start your Edge with: msedge --remote-debugging-port=9222");
    process.exit(1);
  }

  if (userCookies.length === 0) {
    console.log("[SYNC] User Edge has 0 cookies, nothing to sync");
    return;
  }

  // 3. Import cookies into Claude Edge
  const claudeBrowser = await chromium.connectOverCDP(CLAUDE_CDP);
  const cdp = await claudeBrowser.contexts()[0].newCDPSession(
    claudeBrowser.contexts()[0].pages()[0] || await claudeBrowser.contexts()[0].newPage()
  );

  let success = 0;
  let failed = 0;

  for (const c of userCookies) {
    try {
      const params = {
        name: c.name,
        value: c.value,
        domain: c.domain,
        path: c.path || "/",
        secure: c.secure || false,
        httpOnly: c.httpOnly || false,
        sameSite: c.sameSite || "Lax",
      };
      if (c.expires > 0) params.expires = c.expires;
      await cdp.send("Network.setCookie", params);
      success++;
    } catch {
      failed++;
    }
    if ((success + failed) % 500 === 0) {
      console.log(`  ... ${success + failed}/${userCookies.length}`);
    }
  }

  await claudeBrowser.close();

  console.log(`[SYNC] Done — imported: ${success}, failed: ${failed}, total: ${userCookies.length}`);
  if (failed > 0) {
    console.log(`[SYNC] WARNING: ${failed} cookies failed to import`);
  } else {
    console.log("[SYNC] All cookies synced successfully");
  }
}

main().catch(err => {
  console.error("[SYNC] Fatal:", err.message);
  process.exit(1);
});
