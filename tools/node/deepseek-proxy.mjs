// DeepSeek Anthropic Gateway — Message Format Proxy (Chain Mode)
//
// Architecture:
//   Claude Code → :8787 (this proxy, system role fix)
//              → :16889 (dsv4-cc-proxy, thinking block fixes)
//              → api.deepseek.com/anthropic
//
// Usage:  node ~/.claude/tools/deepseek-proxy.mjs
// Config: ANTHROPIC_BASE_URL=http://127.0.0.1:8787

import http from "node:http";

const TARGET_HOST = "127.0.0.1";
const TARGET_PORT = 16889; // dsv4-cc-proxy (thinking fixes)
const PORT = parseInt(process.env.DEEPSEEK_PROXY_PORT || "8787");

function transformBody(bodyText) {
  try {
    const body = JSON.parse(bodyText);
    if (!body.messages) return bodyText;

    const systemMessages = [];
    const otherMessages = [];

    for (const msg of body.messages) {
      if (msg.role === "system") {
        systemMessages.push(msg);
      } else {
        otherMessages.push(msg);
      }
    }

    if (systemMessages.length === 0) return bodyText;

    const systemContent = systemMessages.flatMap((m) => {
      if (typeof m.content === "string") return [{ type: "text", text: m.content }];
      if (Array.isArray(m.content)) return m.content;
      return [{ type: "text", text: JSON.stringify(m.content) }];
    });

    body.system = systemContent;
    body.messages = otherMessages;

    return JSON.stringify(body);
  } catch {
    return bodyText;
  }
}

const server = http.createServer((clientReq, clientRes) => {
  const { method, url, headers } = clientReq;

  // Strip /anthropic prefix — dsv4-cc-proxy adds it back
  let upstreamPath = url;
  if (upstreamPath.startsWith("/anthropic")) {
    upstreamPath = upstreamPath.slice("/anthropic".length) || "/";
  }

  const options = {
    hostname: TARGET_HOST,
    port: TARGET_PORT,
    path: upstreamPath,
    method,
    headers: { ...headers, host: `${TARGET_HOST}:${TARGET_PORT}` },
  };

  const chunks = [];
  clientReq.on("data", (chunk) => chunks.push(chunk));
  clientReq.on("end", () => {
    let body = Buffer.concat(chunks).toString("utf-8");

    // Fix 1: system in messages[] → top-level system param
    if (url.includes("/messages") && body) {
      body = transformBody(body);
      options.headers["content-length"] = Buffer.byteLength(body);
    }

    const proxyReq = http.request(options, (proxyRes) => {
      if (proxyRes.headers["content-type"]?.includes("text/event-stream")) {
        clientRes.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(clientRes);
      } else {
        const resChunks = [];
        proxyRes.on("data", (c) => resChunks.push(c));
        proxyRes.on("end", () => {
          clientRes.writeHead(proxyRes.statusCode, proxyRes.headers);
          clientRes.end(Buffer.concat(resChunks));
        });
      }
    });

    proxyReq.on("error", (err) => {
      if (!clientRes.headersSent) {
        clientRes.writeHead(502);
      }
      clientRes.end(JSON.stringify({ error: { message: err.message } }));
    });

    proxyReq.write(body);
    proxyReq.end();
  });
});

server.listen(PORT, "127.0.0.1", () => {
  process.stderr.write(
    `[deepseek-proxy] http://127.0.0.1:${PORT} → http://127.0.0.1:${TARGET_PORT} (dsv4-cc-proxy) → DeepSeek\n`
  );
});
