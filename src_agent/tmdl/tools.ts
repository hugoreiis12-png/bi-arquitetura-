// src_agent/tmdl/tools.ts — Tool MCP para auditoria TMDL
// Port fiel de tmdl_tools.py

import * as path from "node:path";
import { z } from "zod";
import { runAudit } from "./audit.js";

// ============================================================
//  Schema de entrada (Zod)
// ============================================================

export const tmdlAuditSchema = {
  folder: z
    .string()
    .describe(
      "Caminho da pasta TMDL (definition) do Power BI. Ex.: ./Vendas.SemanticModel/definition"
    ),
  rules_path: z
    .string()
    .optional()
    .describe(
      "Caminho para rules.json (padrão: rules.json ao lado de tools.ts)"
    ),
  conventions_path: z
    .string()
    .optional()
    .describe("Caminho para tmdl.conventions.json do projeto (opcional)"),
  format: z
    .enum(["json", "md"])
    .default("json")
    .describe("Formato de saída — json ou md (padrão: json)"),
  fail_on_high: z
    .boolean()
    .default(false)
    .describe(
      "Se true, retorna exit code 1 quando há achados de severidade alta"
    ),
  max_items: z
    .number()
    .int()
    .min(1)
    .max(500)
    .default(25)
    .describe("Máximo de itens listados por achado no formato md (padrão: 25)"),
};

export type TmdlAuditInput = {
  folder: string;
  rules_path?: string;
  conventions_path?: string;
  format?: "json" | "md";
  fail_on_high?: boolean;
  max_items?: number;
};

// ============================================================
//  Handler
// ============================================================

export function handleTmdlAudit(input: TmdlAuditInput): string {
  const {
    folder,
    rules_path,
    conventions_path,
    format = "json",
    fail_on_high = false,
    max_items = 25,
  } = input;

  const { result, exitCode } = runAudit(
    path.resolve(folder),
    rules_path ? path.resolve(rules_path) : undefined,
    conventions_path ? path.resolve(conventions_path) : undefined,
    format,
    fail_on_high,
    max_items
  );

  if (exitCode !== 0 && format === "json") {
    try {
      const parsed = JSON.parse(result);
      return JSON.stringify(parsed);
    } catch {
      return result;
    }
  }

  return result;
}

// ============================================================
//  Tool definition (para registro no McpServer)
// ============================================================

export const tmdlAuditTool = {
  name: "tmdl_audit",
  description:
    "Audita uma pasta TMDL (definition) do Power BI com regras declarativas. " +
    "Executa regras de qualidade sobre tabelas, colunas, medidas, relacionamentos, " +
    "roles e perspectivas. Retorna inventário do modelo + achados por severidade.",
  inputSchema: tmdlAuditSchema,
  handler: handleTmdlAudit,
};
