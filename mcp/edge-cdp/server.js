/**
 * Edge CDP MCP Server — v1.2.0
 *
 * MCP server that exposes 22 browser-control tools via Edge CDP + Playwright.
 * Key capabilities:
 *   - CDP-based browser control (reuses user's Edge cookies/login state)
 *   - Doubao vision AI integration (screenshot → multimodal LLM analysis)
 *   - Visual indicator injection (purple bar to distinguish Claude's Edge)
 *   - Dedicated Edge profile (port 9224, isolated from user's Edge on 9222)
 *
 * Architecture:
 *   Claude Code → MCP stdio → server.js → Playwright connectOverCDP → Edge CDP
 *   Claude Code → MCP stdio → server.js → Doubao API (vision analysis)
 *
 * External dependencies:
 *   - Claude Edge: launch-claude-edge.cjs (port 9224, independent profile)
 *   - User Edge: msedge --remote-debugging-port=9222 (for cookie sync)
 *   - Cookie sync: sync-cookies.mjs (auto-sync on startup if sparse)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { chromium } from "playwright";

// --- Configuration ---
const CDP_URL = process.env.EDGE_CDP_URL || "http://127.0.0.1:9224";
const MAX_SCREENSHOT_WIDTH = 1920;
const DEFAULT_TIMEOUT = 15000;

// --- Doubao Vision API config ---
const DOUBAO_API_KEY = "ark-a73d32ae-9cae-42a7-97bc-d5700f069306-e5ac6";
const DOUBAO_MODEL = "ep-20260527110933-btjkj";
const DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3";

// --- Global state ---
let browser = null;        // Playwright Browser (connected via CDP)
let defaultContext = null; // Default browser context
let activePage = null;     // Currently focused page

// --- Helpers ---

const INDICATOR_SCRIPT = `(function(){
  if(document.getElementById("__claude_edge__"))return;
  var el=document.createElement("div");
  el.id="__claude_edge__";
  el.style.cssText="position:fixed!important;top:0!important;left:0!important;right:0!important;height:3px!important;background:linear-gradient(90deg,#6C5CE7,#A29BFE,#6C5CE7)!important;z-index:2147483647!important;pointer-events:none!important;";
  document.documentElement.appendChild(el);
})()`;

async function injectPageIndicator(page) {
  await page.evaluate(INDICATOR_SCRIPT).catch(() => {});
}

async function ensureConnected() {
  if (browser && browser.isConnected()) return;
  try {
    browser = await chromium.connectOverCDP(CDP_URL);
    defaultContext = browser.contexts()[0];
    const pages = defaultContext?.pages() || [];
    activePage = pages[0] || (await defaultContext?.newPage());
  } catch (e) {
    throw new Error(
      `Cannot connect to Edge at ${CDP_URL}. ` +
      `Make sure Edge is running with --remote-debugging-port. ` +
      `Run: node launch-claude-edge.cjs\nDetails: ${e.message}`
    );
  }
}

async function getActivePage() {
  if (!activePage) throw new Error("No active page. Navigate first or open a new page.");
  // Ensure the visual indicator is present (navigation may have removed it)
  await injectPageIndicator(activePage);
  return activePage;
}

async function callDoubaoVision(imageBase64, prompt, maxTokens = 4096) {
  const resp = await fetch(`${DOUBAO_BASE_URL}/chat/completions`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${DOUBAO_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: DOUBAO_MODEL,
      messages: [{
        role: "user",
        content: [
          { type: "image_url", image_url: { url: `data:image/png;base64,${imageBase64}` } },
          { type: "text", text: prompt }
        ]
      }],
      max_tokens: maxTokens,
      temperature: 0.2,
    }),
    signal: AbortSignal.timeout(120000),
  });
  if (!resp.ok) {
    const errText = await resp.text().catch(() => "");
    throw new Error(`Doubao API ${resp.status}: ${errText.substring(0, 300)}`);
  }
  const data = await resp.json();
  return data.choices[0].message.content;
}

// --- Tools definition ---

const TOOLS = [
  {
    name: "edge_navigate",
    description: "Navigate the active Edge tab to a URL. Waits for page load.",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "Full URL to navigate to (e.g. https://example.com)" },
        timeout: { type: "number", description: "Navigation timeout in ms (default 30000)" },
      },
      required: ["url"],
    },
  },
  {
    name: "edge_screenshot",
    description: "Take a screenshot of the active Edge tab (viewport or full page).",
    inputSchema: {
      type: "object",
      properties: {
        full_page: { type: "boolean", description: "Capture full scrollable page (default false)" },
        selector: { type: "string", description: "CSS selector of element to screenshot (optional)" },
      },
    },
  },
  {
    name: "edge_analyze_page",
    description:
      "Analyze the current page using Doubao vision AI. Takes a screenshot and sends it to Doubao for " +
      "comprehensive visual understanding — much more detailed than DOM text extraction. " +
      "Can describe layout, identify UI elements, read text in images, understand complex visual content, " +
      "and answer specific questions about what's on screen. Use this when you need to understand " +
      "what the page actually looks like, not just its text content.",
    inputSchema: {
      type: "object",
      properties: {
        prompt: {
          type: "string",
          description:
            "What to analyze. Default gives a comprehensive page overview. " +
            "Custom examples: 'list all buttons and their labels', " +
            "'extract the data from the table', 'what error message is shown?', " +
            "'describe the navigation menu structure'",
        },
        full_page: { type: "boolean", description: "Capture full scrollable page (default false, viewport only)" },
        selector: { type: "string", description: "CSS selector of element to screenshot and analyze (optional)" },
      },
    },
  },
  {
    name: "edge_click",
    description: "Click an element on the active page by CSS selector or text content.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector (e.g. button.submit, #login-btn)" },
        text: { type: "string", description: "Text content of element to click (alternative to selector)" },
        index: { type: "number", description: "If multiple elements match, click the Nth one (0-based, default 0)" },
        timeout: { type: "number", description: "Wait timeout for element (default 15000)" },
      },
      // Require at least one of selector or text
    },
  },
  {
    name: "edge_type",
    description: "Type text into an input field identified by CSS selector.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector for the input field" },
        text: { type: "string", description: "Text to type" },
        clear: { type: "boolean", description: "Clear existing text first (default true)" },
        press_enter: { type: "boolean", description: "Press Enter after typing (default false)" },
        timeout: { type: "number", description: "Wait timeout for element (default 15000)" },
      },
      required: ["selector", "text"],
    },
  },
  {
    name: "edge_get_content",
    description: "Get the page content: HTML source, text content, or specific element text.",
    inputSchema: {
      type: "object",
      properties: {
        mode: {
          type: "string",
          enum: ["html", "text", "article", "vision"],
          description: "html=full HTML, text=visible text only, article=extracted main content, vision=screenshot+Doubao AI analysis for comprehensive visual extraction (default text)",
        },
        selector: { type: "string", description: "CSS selector to get content from a specific element" },
        max_length: { type: "number", description: "Truncate output to this many characters" },
      },
    },
  },
  {
    name: "edge_get_url",
    description: "Get the current URL of the active Edge tab.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "edge_get_title",
    description: "Get the title of the active page.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "edge_evaluate",
    description: "Execute JavaScript in the active page and return the result (JSON-serializable values only).",
    inputSchema: {
      type: "object",
      properties: {
        script: { type: "string", description: "JavaScript code to evaluate. Use return to get values back." },
      },
      required: ["script"],
    },
  },
  {
    name: "edge_scroll",
    description: "Scroll the page by pixels or to bottom/top.",
    inputSchema: {
      type: "object",
      properties: {
        direction: {
          type: "string",
          enum: ["down", "up", "bottom", "top"],
          description: "Scroll direction or target",
        },
        amount: { type: "number", description: "Pixels to scroll (for up/down, default 500)" },
      },
      required: ["direction"],
    },
  },
  {
    name: "edge_press_key",
    description: "Press a keyboard key (Enter, Escape, Tab, ArrowDown, etc).",
    inputSchema: {
      type: "object",
      properties: {
        key: { type: "string", description: "Key name (e.g. Enter, Escape, Tab, ArrowDown, PageDown)" },
        selector: { type: "string", description: "Focus this element first (optional)" },
      },
      required: ["key"],
    },
  },
  {
    name: "edge_select",
    description: "Select an option from a <select> dropdown by value or label.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector for the <select> element" },
        value: { type: "string", description: "Option value to select" },
        label: { type: "string", description: "Option label to select (alternative to value)" },
      },
      required: ["selector"],
    },
  },
  {
    name: "edge_hover",
    description: "Hover the mouse over an element.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector of element to hover" },
        timeout: { type: "number", description: "Wait timeout (default 15000)" },
      },
      required: ["selector"],
    },
  },
  {
    name: "edge_wait",
    description: "Wait for an element to appear or for a given number of milliseconds.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "Wait for this CSS selector to be visible" },
        ms: { type: "number", description: "Wait for N milliseconds (alternative to selector)" },
        timeout: { type: "number", description: "Max wait timeout (default 30000)" },
      },
    },
  },
  {
    name: "edge_list_pages",
    description: "List all open tabs/pages in Edge with their URLs and titles.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "edge_switch_page",
    description: "Switch to a different open tab by index (0-based, see edge_list_pages).",
    inputSchema: {
      type: "object",
      properties: {
        index: { type: "number", description: "Tab index (0-based) from edge_list_pages" },
        url_pattern: { type: "string", description: "Switch to first tab whose URL contains this string (alternative to index)" },
      },
    },
  },
  {
    name: "edge_new_page",
    description: "Open a new tab and optionally navigate to a URL.",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "URL to navigate the new tab to (optional)" },
      },
    },
  },
  {
    name: "edge_close_page",
    description: "Close a tab by index (0-based). Will not close the last remaining tab.",
    inputSchema: {
      type: "object",
      properties: {
        index: { type: "number", description: "Tab index to close" },
      },
      required: ["index"],
    },
  },
  {
    name: "edge_fill_form",
    description: "Fill multiple form fields at once. Each field needs a selector and value.",
    inputSchema: {
      type: "object",
      properties: {
        fields: {
          type: "array",
          description: "Array of {selector, value} pairs to fill",
          items: {
            type: "object",
            properties: {
              selector: { type: "string" },
              value: { type: "string" },
              press_enter: { type: "boolean", description: "Press Enter after this field (optional)" },
            },
            required: ["selector", "value"],
          },
        },
      },
      required: ["fields"],
    },
  },
  {
    name: "edge_get_links",
    description: "Extract all links from the page with their text and href.",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "Limit to links within this CSS selector (optional)" },
        max_count: { type: "number", description: "Max number of links to return (default 50)" },
      },
    },
  },
  {
    name: "edge_get_attributes",
    description: "Get attributes of an element (href, src, class, data-*, etc).",
    inputSchema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector of the element" },
        attribute: { type: "string", description: "Specific attribute name. Omit to get all attributes." },
      },
      required: ["selector"],
    },
  },
];

// --- Tool handlers ---

async function handleNavigate(args) {
  await ensureConnected();
  const page = await getActivePage();
  await page.goto(args.url, { timeout: args.timeout || 30000, waitUntil: "domcontentloaded" });
  await injectPageIndicator(page);
  return {
    content: [{ type: "text", text: `Navigated to: ${page.url()}\nTitle: ${await page.title()}` }],
  };
}

async function handleScreenshot(args) {
  await ensureConnected();
  const page = await getActivePage();

  // Block font network requests to prevent font-loading timeout
  await page.route("**/*.{woff,woff2,ttf,otf,eot}", (route) => route.abort());

  let element = page;
  if (args.selector) {
    element = await page.$(args.selector);
    if (!element) throw new Error(`Element not found: ${args.selector}`);
  }

  const buffer = await element.screenshot({
    fullPage: args.full_page || false,
    type: "png",
    timeout: 15000,
  });

  await page.unroute("**/*.{woff,woff2,ttf,otf,eot}");

  return {
    content: [
      {
        type: "image",
        data: buffer.toString("base64"),
        mimeType: "image/png",
      },
    ],
  };
}

async function handleAnalyzePage(args) {
  await ensureConnected();
  const page = await getActivePage();

  // Block font network requests to prevent font-loading timeout
  await page.route("**/*.{woff,woff2,ttf,otf,eot}", (route) => route.abort());

  let element = page;
  if (args.selector) {
    element = await page.$(args.selector);
    if (!element) throw new Error(`Element not found: ${args.selector}`);
  }

  const buffer = await element.screenshot({
    fullPage: args.full_page || false,
    type: "png",
    timeout: 15000,
  });

  await page.unroute("**/*.{woff,woff2,ttf,otf,eot}");
  const imageB64 = buffer.toString("base64");

  const defaultPrompt =
    "Please analyze this webpage screenshot comprehensively. Describe:\n" +
    "1. The overall layout and structure\n" +
    "2. All visible text content (preserve original text as much as possible)\n" +
    "3. Navigation elements, buttons, links and their labels\n" +
    "4. Forms, input fields, dropdowns and their current values\n" +
    "5. Tables, lists, and data displays (use markdown table/list format)\n" +
    "6. Images, icons, charts, and visual elements\n" +
    "7. Any error messages, notifications, status indicators, or alerts\n" +
    "8. The main action a user would likely take on this page\n\n" +
    "Be detailed and specific. Preserve original text where possible. " +
    "This analysis will be used to automate browser interactions.";

  const prompt = args.prompt || defaultPrompt;
  const result = await callDoubaoVision(imageB64, prompt);

  return {
    content: [
      { type: "text", text: result },
      {
        type: "image",
        data: imageB64,
        mimeType: "image/png",
      },
    ],
  };
}

async function handleClick(args) {
  await ensureConnected();
  const page = await getActivePage();
  const timeout = args.timeout || DEFAULT_TIMEOUT;

  let element;
  if (args.selector) {
    await page.waitForSelector(args.selector, { timeout, state: "visible" });
    const elements = await page.$$(args.selector);
    const idx = args.index || 0;
    if (idx >= elements.length) throw new Error(`Selector "${args.selector}" matched only ${elements.length} elements, index ${idx} out of range`);
    element = elements[idx];
  } else if (args.text) {
    element = await page.getByText(args.text, { exact: false }).first();
    await element.waitFor({ state: "visible", timeout });
  } else {
    throw new Error("Must provide 'selector' or 'text'");
  }

  await element.click({ timeout });
  return {
    content: [{ type: "text", text: `Clicked: ${args.selector || args.text}` }],
  };
}

async function handleType(args) {
  await ensureConnected();
  const page = await getActivePage();
  const timeout = args.timeout || DEFAULT_TIMEOUT;

  await page.waitForSelector(args.selector, { timeout, state: "visible" });
  if (args.clear !== false) await page.fill(args.selector, "");
  await page.type(args.selector, args.text, { delay: 30 });
  if (args.press_enter) await page.press(args.selector, "Enter");

  return {
    content: [{ type: "text", text: `Typed into ${args.selector}` }],
  };
}

async function handleGetContent(args) {
  await ensureConnected();
  const page = await getActivePage();
  const mode = args.mode || "text";

  // Vision mode: screenshot + Doubao visual extraction
  if (mode === "vision") {
    let element = page;
    if (args.selector) {
      element = await page.$(args.selector);
      if (!element) throw new Error(`Element not found: ${args.selector}`);
    }
    await page.route("**/*.{woff,woff2,ttf,otf,eot}", (route) => route.abort());

    const buffer = await element.screenshot({ fullPage: false, type: "png", timeout: 15000 });

    await page.unroute("**/*.{woff,woff2,ttf,otf,eot}");
    const imageB64 = buffer.toString("base64");

    const prompt =
      "Extract ALL visible text content from this screenshot exactly as it appears. " +
      "Preserve original text, headings, button labels, form fields, table data (use markdown tables), " +
      "and list items. Do not summarize — output raw content in structured markdown.";
    const result = await callDoubaoVision(imageB64, prompt);

    const truncated = (args.max_length && result.length > args.max_length)
      ? result.substring(0, args.max_length) + "\n... [truncated]"
      : result;

    return {
      content: [
        { type: "text", text: truncated },
        { type: "image", data: imageB64, mimeType: "image/png" },
      ],
    };
  }

  let content;
  if (args.selector) {
    const el = await page.$(args.selector);
    if (!el) throw new Error(`Element not found: ${args.selector}`);
    content = mode === "html"
      ? await el.innerHTML()
      : await el.innerText();
  } else if (mode === "html") {
    content = await page.content();
  } else if (mode === "article") {
    // Extract main content using Readability-like approach
    content = await page.evaluate(() => {
      const article = document.querySelector("article, main, [role='main'], .content, .post, .article");
      return article ? article.innerText : document.body.innerText;
    });
  } else {
    content = await page.evaluate(() => document.body.innerText);
  }

  if (args.max_length && content.length > args.max_length) {
    content = content.substring(0, args.max_length) + "\n... [truncated]";
  }

  return {
    content: [{ type: "text", text: content }],
  };
}

async function handleGetUrl() {
  await ensureConnected();
  const page = await getActivePage();
  return {
    content: [{ type: "text", text: page.url() }],
  };
}

async function handleGetTitle() {
  await ensureConnected();
  const page = await getActivePage();
  return {
    content: [{ type: "text", text: await page.title() }],
  };
}

async function handleEvaluate(args) {
  await ensureConnected();
  const page = await getActivePage();
  const result = await page.evaluate(args.script);
  return {
    content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
  };
}

async function handleScroll(args) {
  await ensureConnected();
  const page = await getActivePage();
  const amount = args.amount || 500;

  switch (args.direction) {
    case "down":
      await page.evaluate((px) => window.scrollBy(0, px), amount);
      break;
    case "up":
      await page.evaluate((px) => window.scrollBy(0, -px), amount);
      break;
    case "bottom":
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      break;
    case "top":
      await page.evaluate(() => window.scrollTo(0, 0));
      break;
  }

  return {
    content: [{ type: "text", text: `Scrolled ${args.direction}` }],
  };
}

async function handlePressKey(args) {
  await ensureConnected();
  const page = await getActivePage();
  if (args.selector) await page.focus(args.selector);
  await page.keyboard.press(args.key);
  return {
    content: [{ type: "text", text: `Pressed: ${args.key}` }],
  };
}

async function handleSelect(args) {
  await ensureConnected();
  const page = await getActivePage();
  await page.waitForSelector(args.selector, { timeout: DEFAULT_TIMEOUT });

  if (args.value) {
    await page.selectOption(args.selector, args.value);
  } else if (args.label) {
    await page.selectOption(args.selector, { label: args.label });
  } else {
    throw new Error("Must provide 'value' or 'label'");
  }

  return {
    content: [{ type: "text", text: `Selected option in ${args.selector}` }],
  };
}

async function handleHover(args) {
  await ensureConnected();
  const page = await getActivePage();
  await page.waitForSelector(args.selector, { timeout: args.timeout || DEFAULT_TIMEOUT, state: "visible" });
  await page.hover(args.selector);
  return {
    content: [{ type: "text", text: `Hovered over ${args.selector}` }],
  };
}

async function handleWait(args) {
  await ensureConnected();
  const page = await getActivePage();

  if (args.selector) {
    await page.waitForSelector(args.selector, { timeout: args.timeout || 30000, state: "visible" });
    return { content: [{ type: "text", text: `Element visible: ${args.selector}` }] };
  } else if (args.ms) {
    await page.waitForTimeout(args.ms);
    return { content: [{ type: "text", text: `Waited ${args.ms}ms` }] };
  } else {
    throw new Error("Must provide 'selector' or 'ms'");
  }
}

async function handleListPages() {
  await ensureConnected();
  if (!defaultContext) throw new Error("No browser context");

  const pages = defaultContext.pages();
  const list = await Promise.all(
    pages.map(async (p, i) => {
      let url = "", title = "";
      try { url = p.url(); } catch (_) {}
      try { title = await p.title(); } catch (_) {}
      const active = p === activePage;
      return `${active ? "→" : " "} [${i}] ${title}\n     ${url}`;
    })
  );

  return {
    content: [{ type: "text", text: `${list.length} tabs:\n${list.join("\n")}` }],
  };
}

async function handleSwitchPage(args) {
  await ensureConnected();
  if (!defaultContext) throw new Error("No browser context");
  const pages = defaultContext.pages();

  let targetPage;
  if (args.url_pattern) {
    const pattern = args.url_pattern.toLowerCase();
    for (const p of pages) {
      if (p.url().toLowerCase().includes(pattern)) { targetPage = p; break; }
    }
    if (!targetPage) throw new Error(`No tab found with URL containing: ${args.url_pattern}`);
  } else if (args.index !== undefined) {
    if (args.index < 0 || args.index >= pages.length) {
      throw new Error(`Tab index ${args.index} out of range (0-${pages.length - 1})`);
    }
    targetPage = pages[args.index];
  } else {
    throw new Error("Must provide 'index' or 'url_pattern'");
  }

  activePage = targetPage;
  await activePage.bringToFront();
  return {
    content: [{ type: "text", text: `Switched to: ${await activePage.title()}\n${activePage.url()}` }],
  };
}

async function handleNewPage(args) {
  await ensureConnected();
  if (!defaultContext) throw new Error("No browser context");

  const page = await defaultContext.newPage();
  activePage = page;
  if (args.url) {
    await page.goto(args.url, { timeout: 30000, waitUntil: "domcontentloaded" });
    await injectPageIndicator(page);
  }

  return {
    content: [{ type: "text", text: `New tab opened: ${page.url()}` }],
  };
}

async function handleClosePage(args) {
  await ensureConnected();
  if (!defaultContext) throw new Error("No browser context");
  const pages = defaultContext.pages();
  if (pages.length <= 1) throw new Error("Cannot close the last remaining tab");

  const idx = args.index;
  if (idx < 0 || idx >= pages.length) throw new Error(`Index ${idx} out of range (0-${pages.length - 1})`);

  const page = pages[idx];
  await page.close();
  if (activePage === page) activePage = pages[0];

  return {
    content: [{ type: "text", text: `Closed tab ${idx}` }],
  };
}

async function handleFillForm(args) {
  await ensureConnected();
  const page = await getActivePage();

  for (const field of args.fields) {
    await page.waitForSelector(field.selector, { timeout: DEFAULT_TIMEOUT, state: "visible" });
    await page.fill(field.selector, "");
    await page.type(field.selector, field.value, { delay: 30 });
    if (field.press_enter) await page.press(field.selector, "Enter");
  }

  return {
    content: [{ type: "text", text: `Filled ${args.fields.length} fields` }],
  };
}

async function handleGetLinks(args) {
  await ensureConnected();
  const page = await getActivePage();
  const maxCount = args.max_count || 50;

  const links = await page.evaluate(({ baseSelector, max }) => {
    const scope = baseSelector
      ? document.querySelector(baseSelector)
      : document;
    if (!scope) return [];

    return Array.from(scope.querySelectorAll("a[href]"))
      .slice(0, max)
      .map((a, i) => ({
        index: i,
        text: a.textContent.trim().substring(0, 150),
        href: a.href,
      }));
  }, { baseSelector: args.selector, max: maxCount });

  const text = links.map((l) => `[${l.index}] ${l.text}\n    ${l.href}`).join("\n");
  return {
    content: [{ type: "text", text: text || "No links found" }],
  };
}

async function handleGetAttributes(args) {
  await ensureConnected();
  const page = await getActivePage();
  await page.waitForSelector(args.selector, { timeout: DEFAULT_TIMEOUT });

  const attrs = await page.evaluate((sel, attrName) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    if (attrName) return { [attrName]: el.getAttribute(attrName) };

    const result = {};
    for (const a of el.attributes) {
      result[a.name] = a.value;
    }
    return result;
  }, args.selector, args.attribute || null);

  if (!attrs) throw new Error(`Element not found: ${args.selector}`);

  return {
    content: [{ type: "text", text: JSON.stringify(attrs, null, 2) }],
  };
}

// --- Router ---

const HANDLERS = {
  edge_navigate: handleNavigate,
  edge_screenshot: handleScreenshot,
  edge_analyze_page: handleAnalyzePage,
  edge_click: handleClick,
  edge_type: handleType,
  edge_get_content: handleGetContent,
  edge_get_url: handleGetUrl,
  edge_get_title: handleGetTitle,
  edge_evaluate: handleEvaluate,
  edge_scroll: handleScroll,
  edge_press_key: handlePressKey,
  edge_select: handleSelect,
  edge_hover: handleHover,
  edge_wait: handleWait,
  edge_list_pages: handleListPages,
  edge_switch_page: handleSwitchPage,
  edge_new_page: handleNewPage,
  edge_close_page: handleClosePage,
  edge_fill_form: handleFillForm,
  edge_get_links: handleGetLinks,
  edge_get_attributes: handleGetAttributes,
};

// --- Server setup ---

const server = new Server(
  { name: "edge-cdp-mcp", version: "1.2.0" },
  { capabilities: { tools: {} } }
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
      isError: true,
    };
  }
});

// --- Main ---

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // Stderr so it doesn't corrupt the MCP stdio channel
  console.error(`Edge CDP MCP server started. Connecting to ${CDP_URL}...`);

  // Verify initial connection
  try {
    await ensureConnected();
    console.error(`Connected to Edge! ${defaultContext?.pages().length || 0} tabs open.`);
  } catch (e) {
    console.error(`Warning: ${e.message}`);
    console.error("Edge must be started with: start-edge-cdp.bat");
  }
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
