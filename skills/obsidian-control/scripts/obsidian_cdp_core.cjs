"use strict";

const path = require("path");
const fs = require("fs");

const DEFAULT_VAULT_PATH = process.env.OBSIDIAN_VAULT_PATH || "";
const DEFAULT_CDP_URL = process.env.OBSIDIAN_CDP_URL || "http://127.0.0.1:9225";
const DEFAULT_TIMEOUT_MS = 15000;

const DEFAULTS = {
  vaultPath: DEFAULT_VAULT_PATH,
  cdpUrl: DEFAULT_CDP_URL,
  timeoutMs: DEFAULT_TIMEOUT_MS,
};

function requirePlaywright() {
  const candidates = [
    path.resolve(__dirname, "..", "..", "..", "obsidian-mcp", "node_modules", "playwright-core"),
    path.resolve(__dirname, "..", "..", "..", ".claude", "edge-mcp", "node_modules", "playwright-core"),
    path.resolve(__dirname, "..", "..", "..", "node_modules", "playwright-core"),
    "playwright-core",
  ];

  for (const candidate of candidates) {
    try {
      if (typeof candidate === "string" && !path.isAbsolute(candidate)) {
        return require(candidate);
      }
      return require(candidate);
    } catch (e) {
      // continue
    }
  }
  throw new Error("playwright-core not found. Install: npm install playwright-core");
}

async function connectToObsidian(cdpUrl, timeoutMs) {
  const pw = requirePlaywright();
  const browser = await pw.chromium.connectOverCDP(cdpUrl, { timeout: timeoutMs });
  const contexts = browser.contexts();
  if (!contexts.length) throw new Error("No browser contexts found in Obsidian CDP session");
  const pages = contexts[0].pages();
  if (!pages.length) throw new Error("No pages found in Obsidian CDP session");
  const page = pages[0];
  return { browser, page };
}

async function safeEvaluate(page, expression, timeoutMs) {
  return page.evaluate(expression, { timeout: timeoutMs });
}

function buildVaultsScript() {
  return `
    (() => {
      try {
        const vaults = window.app?.vault?.getAllLoadedVaults
          ? window.app.vault.getAllLoadedVaults()
          : [];
        return vaults.map(v => ({
          path: v.adapter?.basePath || v.adapter?.getBasePath?.() || "",
          name: v.getName?.() || "",
        }));
      } catch (e) {
        return { error: e.message };
      }
    })()
  `;
}

function buildStatusScript(vaultPath) {
  return `
    (() => {
      try {
        const a = window.app;
        if (!a) return { error: "window.app not available" };
        const vault = a.vault;
        if (!vault) return { error: "app.vault not available" };
        const activeFile = a.workspace?.getActiveFile?.();
        const title = document.title || "";
        const vaultName = vault.getName?.() || "";
        const basePath = vault.adapter?.basePath || vault.adapter?.getBasePath?.() || "";
        return {
          available: true,
          activeFile: activeFile ? activeFile.path : null,
          activeFileName: activeFile ? activeFile.name : null,
          title: title,
          vaultName: vaultName,
          vaultPath: basePath,
          pageUrl: window.location.href,
          fileCount: vault.getMarkdownFiles?.()?.length || 0,
        };
      } catch (e) {
        return { error: e.message };
      }
    })()
  `;
}

function buildListScript() {
  return `
    (() => {
      try {
        const files = window.app?.vault?.getMarkdownFiles?.() || [];
        return files.map(f => ({ path: f.path, name: f.name }));
      } catch (e) {
        return { error: e.message };
      }
    })()
  `;
}

function buildOpenScript(notePath, fallbackContent) {
  const contentArg = fallbackContent !== undefined ? JSON.stringify(fallbackContent) : "null";
  return `
    (async () => {
      try {
        const app = window.app;
        if (!app) return { error: "window.app not available" };

        let file = app.vault.getAbstractFileByPath(${JSON.stringify(notePath)});
        if (!file) {
          const content = ${contentArg};
          if (content) {
            file = await app.vault.create(${JSON.stringify(notePath)}, content);
          }
          if (!file) return { error: "File not found in vault: ${notePath.replace(/\\/g, "\\\\")}" };
        }

        const leaf = app.workspace.getLeaf(true);
        await leaf.openFile(file);
        app.workspace.setActiveLeaf(leaf, true, true);
        app.workspace.revealLeaf(leaf);

        const activeFile = app.workspace.getActiveFile();
        return {
          ok: activeFile?.path === ${JSON.stringify(notePath)},
          activeFile: activeFile?.path || null,
          title: document.title || "",
        };
      } catch (e) {
        return { error: e.message };
      }
    })()
  `;
}

function buildCurrentScript() {
  return `
    (() => {
      try {
        const app = window.app;
        const activeFile = app?.workspace?.getActiveFile?.();
        return {
          activeFile: activeFile?.path || null,
          activeFileName: activeFile?.name || null,
          title: document.title || "",
        };
      } catch (e) {
        return { error: e.message };
      }
    })()
  `;
}

async function navigateToVault(page, vaultPath, timeoutMs) {
  const url = page.url();
  if (url.includes("starter.html")) {
    await page.evaluate(
      (vp) => {
        return window.electron?.ipcRenderer?.sendSync?.("vault-open", vp, false);
      },
      vaultPath,
      { timeout: timeoutMs }
    );
    await page.waitForURL((u) => u.toString().includes("index.html"), { timeout: timeoutMs });
    await page.waitForTimeout(2000);
  }
}

async function runAction(options) {
  const { action, vaultPath, cdpUrl, timeoutMs, output, target } = options;

  const { browser, page } = await connectToObsidian(cdpUrl, timeoutMs);
  try {
    await navigateToVault(page, vaultPath, timeoutMs);

    switch (action) {
      case "status": {
        const status = await safeEvaluate(page, buildStatusScript(vaultPath), timeoutMs);
        return { ...status, vaultPath, cdpUrl };
      }

      case "list": {
        const files = await safeEvaluate(page, buildListScript(), timeoutMs);
        return { files: Array.isArray(files) ? files : [], vaultPath };
      }

      case "current": {
        const current = await safeEvaluate(page, buildCurrentScript(), timeoutMs);
        return { ...current, vaultPath };
      }

      case "open": {
        if (!target) throw new Error("note_path is required for open action");
        let fallbackContent;
        const fullPath = path.join(vaultPath, target);
        if (fs.existsSync(fullPath)) {
          fallbackContent = fs.readFileSync(fullPath, "utf-8");
        }
        const result = await safeEvaluate(page, buildOpenScript(target, fallbackContent), timeoutMs);
        return { ...result, vaultPath, target };
      }

      case "screenshot": {
        const dest = output || path.join(vaultPath, "screenshot.png");
        await page.screenshot({ path: dest, fullPage: false });
        return { screenshot: dest, vaultPath };
      }

      case "verify-note": {
        if (!target) throw new Error("note_path is required for verify-note action");
        let fallbackContent;
        const fullPath = path.join(vaultPath, target);
        if (fs.existsSync(fullPath)) {
          fallbackContent = fs.readFileSync(fullPath, "utf-8");
        }
        const openResult = await safeEvaluate(page, buildOpenScript(target, fallbackContent), timeoutMs);
        if (!openResult.ok) {
          return { ok: false, target, error: openResult.error || "Active file mismatch", activeFile: openResult.activeFile };
        }
        const current = await safeEvaluate(page, buildCurrentScript(), timeoutMs);
        return { ok: current.activeFile === target, target, activeFile: current.activeFile };
      }

      case "verify-all": {
        const files = await safeEvaluate(page, buildListScript(), timeoutMs);
        if (!Array.isArray(files)) return { error: "Failed to list files", total: 0, passed: 0, failed: 0 };

        let passed = 0;
        let failed = 0;
        const failures = [];

        for (const file of files) {
          let fallbackContent;
          const fullPath = path.join(vaultPath, file.path);
          if (fs.existsSync(fullPath)) {
            fallbackContent = fs.readFileSync(fullPath, "utf-8");
          }
          const openResult = await safeEvaluate(page, buildOpenScript(file.path, fallbackContent), timeoutMs);
          const current = await safeEvaluate(page, buildCurrentScript(), timeoutMs);
          if (current.activeFile === file.path) {
            passed++;
          } else {
            failed++;
            failures.push({ path: file.path, activeFile: current.activeFile });
          }
        }

        return { total: files.length, passed, failed, failures };
      }

      default:
        throw new Error(`Unknown action: ${action}`);
    }
  } finally {
    await browser.close().catch(() => {});
  }
}

module.exports = { DEFAULTS, runAction, connectToObsidian };
