"use strict";

const path = require("path");

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
    path.resolve(__dirname, "..", "edge-cdp-mcp", "node_modules", "@modelcontextprotocol", "sdk", "dist", "cjs", relativePath),
  ]);
}

const { Client } = loadSdkModule(path.join("client", "index.js"));
const { StdioClientTransport } = loadSdkModule(path.join("client", "stdio.js"));

function parseToolArgs(rawArgs) {
  if (!rawArgs.length) {
    return {};
  }

  if (rawArgs.length === 1) {
    const raw = rawArgs[0];

    if (raw.startsWith("{")) {
      return JSON.parse(raw);
    }
  }

  const parsed = {};

  for (const entry of rawArgs) {
    const separator = entry.indexOf("=");

    if (separator === -1) {
      throw new Error(`Unsupported tool argument format: ${entry}. Use JSON or key=value.`);
    }

    const key = entry.slice(0, separator);
    const rawValue = entry.slice(separator + 1);

    if (!key) {
      throw new Error(`Invalid tool argument: ${entry}`);
    }

    if (rawValue === "true") {
      parsed[key] = true;
      continue;
    }

    if (rawValue === "false") {
      parsed[key] = false;
      continue;
    }

    if (rawValue !== "" && !Number.isNaN(Number(rawValue)) && /^-?\d+(\.\d+)?$/.test(rawValue)) {
      parsed[key] = Number(rawValue);
      continue;
    }

    parsed[key] = rawValue;
  }

  return parsed;
}

async function main() {
  const toolName = process.argv[2] || "obsidian_status";
  const toolArgs = parseToolArgs(process.argv.slice(3));

  const serverPath = path.resolve(__dirname, "server.cjs");
  const client = new Client({ name: "obsidian-mcp-smoke", version: "1.0.0" });
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [serverPath],
    cwd: __dirname,
    stderr: "pipe",
  });

  const stderrChunks = [];
  if (transport.stderr) {
    transport.stderr.on("data", (chunk) => {
      stderrChunks.push(chunk.toString());
    });
  }

  await client.connect(transport);
  const tools = await client.listTools();
  const result = await client.callTool({ name: toolName, arguments: toolArgs });

  console.log(
    JSON.stringify(
      {
        toolCount: tools.tools.length,
        toolNames: tools.tools.map((tool) => tool.name),
        toolName,
        toolArgs,
        result,
        stderr: stderrChunks.join(""),
      },
      null,
      2,
    ),
  );

  await client.close();
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
