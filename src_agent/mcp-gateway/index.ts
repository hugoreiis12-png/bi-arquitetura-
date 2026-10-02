// Backends via env: DAX_BACKEND_URL, PBI_BACKEND_URL.
// Front via env: GATEWAY_HOST (0.0.0.0), GATEWAY_PORT (8000).

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
  type Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { createServer } from "node:http";

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
  if (!hit) throw new Error(`tool desconhecida no gateway: ${name}`);
  const args = (req.params.arguments ?? {}) as Record<string, unknown>;
  try {
    return await hit.b.client.callTool({ name: hit.tool!.name, arguments: args });
  } catch (err) {
    // 1 retry com reconnect (backend pode ter reiniciado)
    console.error(`[gateway] retry ${name} após falha:`, err);
    await reconnect(hit.b, hit.b.prefix || "powerbi-mcp");
    return await hit.b.client.callTool({ name: hit.tool!.name, arguments: args });
  }
});

// ---- front HTTP (canonico POST /mcp + SSE legado compat) ----
const HOST = process.env.GATEWAY_HOST || "0.0.0.0";
const PORT = Number(process.env.GATEWAY_PORT || "8000");
const MAX_BODY = 4 * 1024 * 1024;

// Sessoes SSE legadas (compat Cline/Continue antigos): 1 cliente por vez.
const sseSessions = new Map<string, SSEServerTransport>();

const httpServer = createServer((req, res) => {
  const url = new URL(req.url || "/", "http://localhost");
  const pathname = url.pathname;

  // SSE legado: GET /sse abre stream persistente (fan-out p/ backends).
  if (pathname === "/sse" && req.method === "GET") {
    (async () => {
      await ensureStarted();
      const transport = new SSEServerTransport("/messages", res);
      sseSessions.set(transport.sessionId, transport);
      res.on("close", () => { sseSessions.delete(transport.sessionId); });
      try {
        await server.connect(transport);
      } catch {
        sseSessions.delete(transport.sessionId);
        if (!res.headersSent) {
          res.writeHead(503, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Server busy, retry" }));
        }
      }
    })();
    return;
  }

  // SSE legado: POST /messages?sessionId=...
  if (pathname === "/messages" && req.method === "POST") {
    const sessionId = url.searchParams.get("sessionId") || "";
    const transport = sseSessions.get(sessionId);
    if (!transport) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "SSE session not found. GET /sse first." }));
      return;
    }
    let raw = "";
    req.on("data", (c: Buffer) => { raw += c.toString("utf-8"); });
    req.on("end", async () => {
      let body: unknown;
      try { body = raw ? JSON.parse(raw) : undefined; }
      catch {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid JSON" }));
        return;
      }
      try { await transport.handlePostMessage(req, res, body); }
      catch (err) {
        console.error("[gateway] sse handlePostMessage:", err);
        if (!res.headersSent) {
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Internal error" }));
        }
      }
    });
    return;
  }

  if (pathname !== "/mcp" && pathname !== "/mcp/") {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Not found. Endpoints: POST /mcp (canonico), GET /sse + POST /messages (legado compat)" }));
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
  console.error(`[gateway] bi-architecture em http://${HOST}:${PORT}/mcp + GET /sse legado compat`);
});