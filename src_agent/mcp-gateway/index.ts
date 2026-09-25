#!/usr/bin/env node
// src_agent/mcp-gateway/index.ts — gateway MCP único (bi-architecture)
// Expõe dax-staff + powerbi-mcp num só endpoint POST /mcp (sem slash;
// /mcp/ aceito direto, sem redirect 307).
// Backends via env: DAX_BACKEND_URL, PBI_BACKEND_URL.
// Front via env: GATEWAY_HOST (default 0.0.0.0), GATEWAY_PORT (default 8000).

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
  GetPromptRequestSchema,
  type Tool,
  type Prompt,
} from "@modelcontextprotocol/sdk/types.js";
import { createServer } from "node:http";
import { validatePromptArgs, coercePromptArgs } from "../gateway/prompt-validator.js";

const DAX_URL = process.env.DAX_BACKEND_URL || "http://dax-staff:8001/mcp";
const PBI_URL = process.env.PBI_BACKEND_URL || "http://bi-mcp:8000/mcp";

interface Backend {
  prefix: string; // "" = mantém nome original
  url: string;
  client: Client;
  tools: Tool[];
}

async function connectBackend(prefix: string, url: string, name: string): Promise<Backend> {
  const client = new Client({ name: `bi-gateway-${name}`, version: "1.0.0" }, { capabilities: {} });
  await client.connect(new StreamableHTTPClientTransport(new URL(url)));
  const { tools } = await client.listTools();
  console.error(`[gateway] ${name}: ${tools.length} tools em ${url} (prefixo "${prefix}")`);
  return { prefix, url, client, tools };
}

async function reconnect(b: Backend, name: string): Promise<void> {
  try { await b.client.close(); } catch { /* ignore */ }
  const fresh = await connectBackend(b.prefix, b.url, name);
  b.client = fresh.client;
  b.tools = fresh.tools;
}

function exposedName(b: Backend, t: Tool): string {
  return b.prefix ? `${b.prefix}_${t.name}` : t.name;
}

const server = new Server(
  { name: "bi-architecture-gateway", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

let backends: Backend[] = [];
let starting: Promise<void> | null = null;
function ensureStarted(): Promise<void> {
  if (!starting) {
    starting = (async () => {
      backends = [
        await connectBackend("dax", DAX_URL, "dax-staff"),
        await connectBackend("", PBI_URL, "powerbi-mcp"),
      ];
    })();
  }
  return starting;
}

server.setRequestHandler(ListToolsRequestSchema, async () => {
  await ensureStarted();
  return {
    tools: backends.flatMap((b) =>
      b.tools.map((t) => ({
        ...t,
        name: exposedName(b, t),
        description: `[${b.prefix || "pbi"}] ${t.description ?? t.name}`,
      }))
    ),
  };
});

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  await ensureStarted();
  const name = req.params.name;
  const hit = backends
    .map((b) => ({ b, tool: b.tools.find((t) => exposedName(b, t) === name) }))
    .find((x) => x.tool);
  if (!hit || !hit.tool) throw new Error(`tool desconhecida no gateway: ${name}`);
  const toolName = hit.tool.name;
  const args = (req.params.arguments ?? {}) as Record<string, unknown>;
  try {
    return await hit.b.client.callTool({ name: toolName, arguments: args });
  } catch (err) {
    // 1 retry com reconnect (backend pode ter reiniciado)
    console.error(`[gateway] retry ${name} após falha:`, err);
    await reconnect(hit.b, hit.b.prefix || "powerbi-mcp");
    return await hit.b.client.callTool({ name: toolName, arguments: args });
  }
});

// Novo: handler para prompts com validação de argumentos (mitiga erro '$1')
server.setRequestHandler(GetPromptRequestSchema, async (req) => {
  await ensureStarted();
  const promptName = req.params.name;
  const promptArgs = (req.params.arguments ?? {}) as Record<string, unknown>;

  // Validar argumentos de prompt contra schema conhecido
  const validation = validatePromptArgs(promptName, promptArgs);
  if (!validation.valid) {
    console.error(`[gateway] invalid prompt args para ${promptName}:`, validation.errors);
    throw new Error(
      `Argumentos inválidos para prompt '${promptName}': ${validation.errors.join("; ")}`
    );
  }

  // Coercer argumentos (string numérica → int, etc.) — apenas para validação
  // local; o protocolo MCP transporta argumentos de prompt sempre como
  // string, então repassamos como string (o server Python faz a coerção
  // de tipo real via @validated_prompt).
  const coerced = coercePromptArgs(promptName, promptArgs);
  const wireArgs: Record<string, string> = {};
  for (const [key, value] of Object.entries(coerced)) {
    wireArgs[key] = String(value);
  }

  // Rotear para backend correto (assume que prompts estão no PBI backend)
  const backend = backends.find((b) => !b.prefix);
  if (!backend) throw new Error("PBI backend não encontrado");

  try {
    return await backend.client.getPrompt({ name: promptName, arguments: wireArgs });
  } catch (err) {
    console.error(`[gateway] prompt falhou ${promptName}:`, err);
    await reconnect(backend, "powerbi-mcp");
    return await backend.client.getPrompt({ name: promptName, arguments: wireArgs });
  }
});

// ---- front HTTP stateless (mesmo contrato do dax-staff --http) ----
const HOST = process.env.GATEWAY_HOST || "0.0.0.0";
const PORT = Number(process.env.GATEWAY_PORT || "8000");
const MAX_BODY = 4 * 1024 * 1024;

const httpServer = createServer((req, res) => {
  const pathname = new URL(req.url || "/", "http://localhost").pathname;
  if (pathname !== "/mcp" && pathname !== "/mcp/") {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Not found. MCP endpoint: POST /mcp" }));
    return;
  }
  if (req.method !== "POST") {
    res.writeHead(405, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      jsonrpc: "2.0",
      error: { code: -32000, message: "Method not allowed in stateless mode (use POST /mcp)" },
      id: null,
    }));
    return;
  }
  let raw = "";
  let tooLarge = false;
  req.on("data", (c: Buffer) => {
    raw += c.toString("utf-8");
    if (raw.length > MAX_BODY) { tooLarge = true; req.destroy(); }
  });
  req.on("end", async () => {
    if (tooLarge) {
      res.writeHead(413, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ jsonrpc: "2.0", error: { code: -32000, message: "Body > 4MB" }, id: null }));
      return;
    }
    let body: unknown;
    try { body = raw ? JSON.parse(raw) : undefined; }
    catch {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ jsonrpc: "2.0", error: { code: -32700, message: "Invalid JSON" }, id: null }));
      return;
    }
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
    res.on("close", () => { void transport.close(); });
    try { await server.connect(transport); }
    catch {
      await transport.close();
      if (!res.headersSent) {
        res.writeHead(503, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ jsonrpc: "2.0", error: { code: -32000, message: "Server busy, retry" }, id: null }));
      }
      return;
    }
    try { await transport.handleRequest(req, res, body); }
    catch (err) {
      console.error("[gateway] handleRequest:", err);
      if (!res.headersSent) {
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ jsonrpc: "2.0", error: { code: -32603, message: "Internal error" }, id: null }));
      }
    }
  });
});

await ensureStarted();
httpServer.listen(PORT, HOST, () => {
  console.error(`[gateway] bi-architecture em http://${HOST}:${PORT}/mcp`);
});
