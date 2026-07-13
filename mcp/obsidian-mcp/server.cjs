"use strict";

const path = require("path");
const { spawn } = require("child_process");

function requireFromCandidates(candidates) {
  const errors = [];

  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch (error) {
      errors.push(`${candidate}: ${error.message}`);
    }
  }

  throw new Error(errors.join("\n"));
}

function loadSdkModule(relativePath) {
  return requireFromCandidates([
    path.resolve(__dirname, "node_modules", "@modelcontextprotocol", "sdk", "dist", "cjs", relativePath),
    path.resolve(__dirname, "..", ".claude", "edge-mcp", "node_modules", "@modelcontextprotocol", "sdk", "dist", "cjs", relativePath),
    path.resolve(__dirname, "..", "edge-cdp-mcp", "node_modules", "@modelcontextprotocol", "sdk", "dist", "cjs", relativePath),
  ]);
}

const { Server } = loadSdkModule(path.join("server", "index.js"));
const { StdioServerTransport } = loadSdkModule(path.join("server", "stdio.js"));
const { CallToolRequestSchema, ListToolsRequestSchema } = loadSdkModule("types.js");
const {
  DEFAULTS,
  runAction,
} = require(path.resolve(__dirname, "..", "skills", "obsidian-control", "scripts", "obsidian_cdp_core.cjs"));

const DEFAULT_DEBUG_PORT = Number(process.env.OBSIDIAN_DEBUG_PORT || 9223);
const AUTO_LAUNCH = process.env.OBSIDIAN_AUTO_LAUNCH === "1";
const DEFAULT_TIMEOUT_MS = DEFAULTS.timeoutMs;
const LAUNCH_SCRIPT = path.resolve(__dirname, "..", "skills", "obsidian-control", "scripts", "obsidian_control.ps1");

const TOOLS = [
  {
    name: "obsidian_status",
    description: "Check whether Obsidian is reachable through Electron CDP and report the live vault status.",
    inputSchema: {
      type: "object",
      properties: {
        vault_path: { type: "string", description: "Vault root path. Defaults to workspace vault." },
        cdp_url: { type: "string", description: "CDP URL. Defaults to http://127.0.0.1:9223." },
        timeout_ms: { type: "number", description: "Connection timeout in milliseconds." },
      },
    },
  },
  {
    name: "obsidian_launch",
    description: "Launch Obsidian with a remote debugging port so the agent can directly control the live app.",
    inputSchema: {
      type: "object",
      properties: {
        vault_path: { type: "string", description: "Vault root path to open." },
        debug_port: { type: "number", description: "Remote debugging port. Defaults to 9223." },
        timeout_seconds: { type: "number", description: "How long to wait for CDP to come up." },
        force_restart: { type: "boolean", description: "Restart existing Obsidian processes before launch." },
      },
    },
  },
  {
    name: "obsidian_list_files",
    description: "List Markdown files visible inside the live Obsidian vault.",
    inputSchema: {
      type: "object",
      properties: {
        vault_path: { type: "string" },
        cdp_url: { type: "string" },
        timeout_ms: { type: "number" },
        auto_launch: { type: "boolean", description: "Launch Obsidian if CDP is unavailable." },
        force_restart_on_launch: { type: "boolean", description: "Restart Obsidian if auto-launch is needed." },
      },
    },
  },
  {
    name: "obsidian_current_note",
    description: "Report the currently active note in the live Obsidian window.",
    inputSchema: {
      type: "object",
      properties: {
        vault_path: { type: "string" },
        cdp_url: { type: "string" },
        timeout_ms: { type: "number" },
        auto_launch: { type: "boolean" },
        force_restart_on_launch: { type: "boolean" },
      },
    },
  },
  {
    name: "obsidian_open_note",
    description: "Open a specific Markdown note inside the live Obsidian window.",
    inputSchema: {
      type: "object",
      properties: {
        note_path: { type: "string", description: "Vault-relative note path such as Home.md or docs/index.md." },
        vault_path: { type: "string" },
        cdp_url: { type: "string" },
        timeout_ms: { type: "number" },
        auto_launch: { type: "boolean" },
        force_restart_on_launch: { type: "boolean" },
      },
      required: ["note_path"],
    },
  },
  {
    name: "obsidian_screenshot",
    description: "Capture a screenshot of the live Obsidian window.",
    inputSchema: {
      type: "object",
      properties: {
        output_path: { type: "string", description: "Destination PNG path." },
        vault_path: { type: "string" },
        cdp_url: { type: "string" },
        timeout_ms: { type: "number" },
        auto_launch: { type: "boolean" },
        force_restart_on_launch: { type: "boolean" },
      },
    },
  },
  {
    name: "obsidian_verify_note",
    description: "Open one note and verify that it became the active file in the live app.",
    inputSchema: {
      type: "object",
      properties: {
        note_path: { type: "string", description: "Vault-relative note path." },
        vault_path: { type: "string" },
        cdp_url: { type: "string" },
        timeout_ms: { type: "number" },
        auto_launch: { type: "boolean" },
        force_restart_on_launch: { type: "boolean" },
      },
      required: ["note_path"],
    },
  },
  {
    name: "obsidian_verify_all",
    description: "Open every Markdown file in the vault and verify that each one can become the active file.",
    inputSchema: {
      type: "object",
      properties: {
        vault_path: { type: "string" },
        cdp_url: { type: "string" },
        timeout_ms: { type: "number" },
        auto_launch: { type: "boolean" },
        force_restart_on_launch: { type: "boolean" },
      },
    },
  },
];

function jsonText(value) {
  return JSON.stringify(value, null, 2);
}

function formatToolResult(value, summary) {
  return {
    content: [
      {
        type: "text",
        text: summary || jsonText(value),
      },
    ],
    structuredContent: value,
  };
}

function normalizeOptions(args = {}) {
  return {
    vaultPath: args.vault_path || DEFAULTS.vaultPath,
    cdpUrl: args.cdp_url || DEFAULTS.cdpUrl,
    timeoutMs: Number(args.timeout_ms || DEFAULT_TIMEOUT_MS),
    output: args.output_path || "",
    target: args.note_path || "",
  };
}

function parseDebugPort(cdpUrl) {
  try {
    return Number(new URL(cdpUrl).port || DEFAULT_DEBUG_PORT);
  } catch (error) {
    void error;
    return DEFAULT_DEBUG_PORT;
  }
}

async function launchObsidian(args = {}) {
  const options = normalizeOptions(args);
  const debugPort = Number(args.debug_port || parseDebugPort(options.cdpUrl) || DEFAULT_DEBUG_PORT);
  const timeoutSeconds = Number(args.timeout_seconds || Math.ceil(options.timeoutMs / 1000) || 30);
  const forceRestart = Boolean(args.force_restart);

  if (!Number.isFinite(debugPort) || debugPort <= 0) {
    throw new Error(`Invalid debug port: ${debugPort}`);
  }

  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
    throw new Error(`Invalid timeout_seconds: ${timeoutSeconds}`);
  }

  return new Promise((resolve, reject) => {
    const childArgs = [
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      LAUNCH_SCRIPT,
      "-Action",
      "launch",
      "-VaultPath",
      options.vaultPath,
      "-DebugPort",
      String(debugPort),
      "-TimeoutSeconds",
      String(timeoutSeconds),
    ];

    if (forceRestart) {
      childArgs.push("-ForceRestart");
    }

    const child = spawn("powershell", childArgs, {
      cwd: path.resolve(__dirname, ".."),
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", reject);
    child.on("exit", (code) => {
      if (code !== 0) {
        reject(new Error((stderr || stdout || `obsidian launch exited with ${code}`).trim()));
        return;
      }

      const payload = stdout.trim();
      if (!payload) {
        resolve({
          action: "launch",
          vaultPath: options.vaultPath,
          cdpUrl: options.cdpUrl,
          cdpAvailable: true,
          forceRestart,
        });
        return;
      }

      try {
        resolve(JSON.parse(payload));
      } catch (error) {
        reject(new Error(`Failed to parse launch output: ${payload}\n${error.message}`));
      }
    });
  });
}

async function runWithOptionalLaunch(args, action) {
  const options = normalizeOptions(args);

  try {
    return await runAction({ ...options, action });
  } catch (error) {
    const shouldLaunch = Boolean(args.auto_launch || AUTO_LAUNCH);

    if (!shouldLaunch) {
      throw error;
    }

    await launchObsidian({
      vault_path: options.vaultPath,
      cdp_url: options.cdpUrl,
      timeout_seconds: Math.ceil(options.timeoutMs / 1000),
      force_restart: Boolean(args.force_restart_on_launch),
    });

    return runAction({ ...options, action });
  }
}

async function handleStatus(args = {}) {
  const options = normalizeOptions(args);

  try {
    const result = await runAction({ ...options, action: "status" });
    return formatToolResult(result, `Connected to Obsidian. Active file: ${result.activeFile || "none"}`);
  } catch (error) {
    const unavailable = {
      available: false,
      vaultPath: options.vaultPath,
      cdpUrl: options.cdpUrl,
      message: error.message,
      hint: "Call obsidian_launch, optionally with force_restart=true, before trying note operations.",
    };

    return formatToolResult(unavailable, unavailable.message);
  }
}

async function handleLaunch(args = {}) {
  const result = await launchObsidian(args);
  return formatToolResult(result, `Launch completed for ${result.vaultPath || normalizeOptions(args).vaultPath}`);
}

async function handleListFiles(args = {}) {
  const result = await runWithOptionalLaunch(args, "list");
  return formatToolResult(result, `Found ${result.files.length} Markdown files in the live vault.`);
}

async function handleCurrentNote(args = {}) {
  const result = await runWithOptionalLaunch(args, "current");
  return formatToolResult(result, `Current active file: ${result.activeFile || "none"}`);
}

async function handleOpenNote(args = {}) {
  const result = await runWithOptionalLaunch(args, "open");
  return formatToolResult(result, `Opened ${result.activeFile || args.note_path}.`);
}

async function handleScreenshot(args = {}) {
  const result = await runWithOptionalLaunch(args, "screenshot");
  return formatToolResult(result, `Saved screenshot to ${result.screenshot}`);
}

async function handleVerifyNote(args = {}) {
  const result = await runWithOptionalLaunch(args, "verify-note");
  return formatToolResult(result, result.ok ? `Verified ${result.target}` : `Verification failed for ${result.target}`);
}

async function handleVerifyAll(args = {}) {
  const result = await runWithOptionalLaunch(args, "verify-all");
  return formatToolResult(result, `Verified ${result.passed}/${result.total} notes successfully.`);
}

const HANDLERS = {
  obsidian_status: handleStatus,
  obsidian_launch: handleLaunch,
  obsidian_list_files: handleListFiles,
  obsidian_current_note: handleCurrentNote,
  obsidian_open_note: handleOpenNote,
  obsidian_screenshot: handleScreenshot,
  obsidian_verify_note: handleVerifyNote,
  obsidian_verify_all: handleVerifyAll,
};

const server = new Server(
  { name: "obsidian-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const handler = HANDLERS[name];

  if (!handler) {
    return {
      content: [{ type: "text", text: `Unknown tool: ${name}` }],
      isError: true,
    };
  }

  try {
    return await handler(args || {});
  } catch (error) {
    return {
      content: [{ type: "text", text: `Error: ${error.message}` }],
      structuredContent: {
        error: error.message,
        tool: name,
      },
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`Obsidian MCP server started. Vault default: ${DEFAULTS.vaultPath}`);
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
