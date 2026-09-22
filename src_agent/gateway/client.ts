// src_agent/gateway/client.ts — Fachada fina: dax-staff delega mutação ao gateway-py.
// Regra: TS nunca escreve Git/disco de definition/ nem modelo; só valida input (zod)
// e repassa ao CLI `py -m tmdl_gateway.cli` (JSON no stdout). Leitura pura continua local.

import { spawnSync } from "node:child_process";
import * as path from "node:path";

export const GATEWAY_VERSION = "0.1.0";

function repoRoot(): string {
  // build/gateway/client.js -> <root>; src_agent/gateway/client.ts -> <root>
  return path.resolve(import.meta.dirname, "..", "..");
}

function gatewayCwd(): string {
  return path.join(repoRoot(), "gateway-py", "src");
}

export function callGateway(args: string[]): { ok: boolean; json: unknown; raw: string } {
  const py = process.env.PYTHON_BIN || "py";
  const res = spawnSync(py, ["-m", "tmdl_gateway.cli", "--repo", repoRoot(), ...args], {
    cwd: gatewayCwd(),
    encoding: "utf-8",
    timeout: 120000,
  });
  const raw = (res.stdout || "") + (res.stderr || "");
  try {
    const parsed: unknown = JSON.parse(res.stdout || "{}");
    if (parsed && typeof parsed === "object" && "error" in (parsed as Record<string, unknown>)) {
      return { ok: false, json: parsed, raw };
    }
    return { ok: res.status === 0, json: parsed, raw };
  } catch {
    return { ok: false, json: { error: "gateway retornou saída não-JSON", raw: raw.slice(0, 2000) }, raw };
  }
}

/** Espelha branching.py (TS não decide sozinho no commit; gateway é canônico). */
export function datasetForBranch(branch: string, base = "Vendas"): string {
  const b = (branch || "").trim();
  if (b === "main") return base;
  if (b === "develop") return `${base}_Dev`;
  if (b === "test" || b.startsWith("release/")) return `${base}_Test`;
  const slug = b.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 20).replace(/_+$/g, "");
  return slug ? `${base}_preview_${slug}` : `${base}_preview`;
}
