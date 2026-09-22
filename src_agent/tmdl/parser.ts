// src_agent/tmdl/parser.ts — Parser TMDL por indentação
// Port fiel de tmdl.py (linhas 29-246 + 266-302)
// Parsing por indentação — sem AMO/TOM, sem .NET, sem Power BI instalado.

import * as fs from "node:fs";
import * as path from "node:path";
import { createNode, type TmdlNode, type TmdlDocs } from "./types.js";

const TAB_WIDTH = 4;

// Tipos de objeto reconhecidos como declaração (camelCase, case-insensitive na leitura).
const OBJECT_KEYWORDS = new Set([
  "database", "model", "table", "column", "measure", "partition", "hierarchy",
  "level", "relationship", "role", "tablepermission", "columnpermission",
  "perspective", "perspectivetable", "perspectivemeasure", "perspectivecolumn",
  "perspectivehierarchy", "culture", "cultureinfo", "expression", "function",
  "datasource", "querygroup", "annotation", "extendedproperty", "calculationgroup",
  "calculationitem", "kpi", "refreshpolicy", "detailrowsdefinition",
  "formatstringdefinition", "calculationgroupexpression", "variation",
  "changedproperty", "linguisticmetadata", "objecttranslation", "rolemembership",
  "datacoveragedefinition", "alternateof", "ref",
]);

const DECL_RE = /^(?<kw>[A-Za-z]+)\s+(?<rest>.*)$/;
const PROP_RE = /^(?<name>[A-Za-z][A-Za-z0-9_]*)\s*:\s*(?<value>.*)$/;
const BOOL_RE = /^(?<name>[A-Za-z][A-Za-z0-9_]*)\s*$/;
const CAMEL_RE = /(?<=[a-z0-9])(?=[A-Z])/;

/** Tokens de um nome, quebrando por separadores e camelCase */
export function tokensDoNome(nome: string): string[] {
  const partes = nome.split(/[\s_\-\.]+/);
  const saida: string[] = [];
  for (const parte of partes) {
    for (const t of parte.split(CAMEL_RE)) {
      if (t) saida.push(t.toLowerCase());
    }
  }
  return saida;
}

/** Acrescenta uma linha à expressão do nó */
function acumula(node: TmdlNode, key: string | null, texto: string): void {
  if (key === null) {
    node.expr = (node.expr ?? "") + texto + "\n";
  } else {
    node.props[key] = (node.props[key] ?? "") + texto + "\n";
  }
}

/** Calcula a indentação de uma linha (expandido para 4 espaços) */
function indentOf(line: string): number {
  const expanded = line.replace(/\t/g, " ".repeat(TAB_WIDTH));
  const stripped = expanded.replace(/^ +/, "");
  return expanded.length - stripped.length;
}

/** Remove aspas simples de um nome */
export function stripQuotes(name: string): string {
  name = name.trim();
  if (name.length >= 2 && name[0] === "'" && name.endsWith("'")) {
    return name.slice(1, -1).replace("''", "'");
  }
  return name;
}

/** Índice do primeiro '=' fora de aspas simples */
function findTopLevelEq(text: string): number | null {
  let inQuote = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === "'") {
      if (inQuote && i + 1 < text.length && text[i + 1] === "'") {
        i++;
        continue;
      }
      inQuote = !inQuote;
    } else if (ch === "=" && !inQuote) {
      return i;
    }
  }
  return null;
}

/** Parse de um arquivo TMDL — devolve a lista de nós de nível raiz */
export function parseFile(filePath: string, rel: string): TmdlNode[] {
  let content = fs.readFileSync(filePath, "utf-8");
  // Remove BOM (byte order mark) se presente
  if (content.charCodeAt(0) === 0xFEFF) {
    content = content.slice(1);
  }
  const lines = content.split(/\r?\n/);

  const roots: TmdlNode[] = [];
  const stack: Array<[number, TmdlNode]> = [];
  let pendingDesc: string[] = [];
  let inFence = false;
  let fenceOwner: TmdlNode | null = null;
  let fenceKey: string | null = null;
  let exprOwner: TmdlNode | null = null;
  let exprIndent = -1;
  let exprKey: string | null = null;

  for (let lineno = 1; lineno <= lines.length; lineno++) {
    const raw = lines[lineno - 1];

    // --- Fence em andamento ---
    if (inFence) {
      if (raw.trim() === "```") {
        inFence = false;
        fenceOwner = null;
        fenceKey = null;
      } else if (fenceOwner !== null) {
        acumula(fenceOwner, fenceKey, raw.trim());
      }
      continue;
    }

    // --- Linha vazia ---
    if (!raw.trim()) {
      if (exprOwner !== null) {
        acumula(exprOwner, exprKey, "");
      }
      continue;
    }

    const ind = indentOf(raw);
    const body = raw.trim();

    // --- Corpo de expressão multilinha em andamento ---
    if (exprOwner !== null) {
      if (ind > exprIndent) {
        acumula(exprOwner, exprKey, body);
        continue;
      }
      exprOwner = null;
      exprIndent = -1;
      exprKey = null;
    }

    // --- Comentário de descrição (///) ---
    if (body.startsWith("///")) {
      pendingDesc.push(body.slice(3).trim());
      continue;
    }

    // --- Comando de script (createOrReplace etc.) ---
    if (ind === 0 && ["createorreplace", "create", "delete", "alter"].includes(body.toLowerCase())) {
      const node = createNode("command", body, { file: rel, line: lineno });
      roots.push(node);
      stack.length = 0;
      stack.push([0, node]);
      pendingDesc = [];
      continue;
    }

    let node: TmdlNode | null = null;

    const m = DECL_RE.exec(body);
    if (m && m.groups && OBJECT_KEYWORDS.has(m.groups.kw.toLowerCase())) {
      let kw = m.groups.kw.toLowerCase();
      let rest = m.groups.rest;
      const isRef = kw === "ref";

      if (isRef) {
        const m2 = DECL_RE.exec(rest);
        if (!m2 || !m2.groups) continue;
        kw = m2.groups.kw.toLowerCase();
        rest = m2.groups.rest;
      }

      let expr: string | null = null;
      let name = rest;

      if (rest.includes("=")) {
        const idx = findTopLevelEq(rest);
        if (idx !== null) {
          name = rest.slice(0, idx).trim();
          expr = rest.slice(idx + 1).trim();
        }
      }

      node = createNode(kw, stripQuotes(name), {
        expr,
        description: pendingDesc.length > 0 ? pendingDesc.join(" ") : null,
        file: rel,
        line: lineno,
      });
      node._isref = isRef;
      pendingDesc = [];
    } else if (body.toLowerCase() === "ref") {
      continue;
    } else {
      // --- Propriedade do nó corrente ---
      const parent = stack.length > 0 ? stack[stack.length - 1][1] : null;

      if (parent !== null) {
        const pm = PROP_RE.exec(body);
        if (pm && pm.groups) {
          parent.props[pm.groups.name.toLowerCase()] = pm.groups.value.trim();
          if (pm.groups.value.trim() === "" &&
              ["source", "expression", "query", "content", "filterexpression"].includes(pm.groups.name.toLowerCase())) {
            exprOwner = parent;
            exprIndent = ind;
            exprKey = pm.groups.name.toLowerCase();
          }
          continue;
        }

        const bm = BOOL_RE.exec(body);
        if (bm && bm.groups) {
          parent.props[bm.groups.name.toLowerCase()] = "true";
          continue;
        }

        // Linha de propriedade com "="
        if (body.includes("=") && parent !== null) {
          const eqIdx = body.indexOf("=");
          const key = body.slice(0, eqIdx).trim().toLowerCase();
          const val = body.slice(eqIdx + 1).trim();
          parent.props[key] = val;
          if (val === "" || val === "```") {
            parent.props[key] = "";
            if (val === "```") {
              inFence = true;
              fenceOwner = parent;
              fenceKey = key;
            } else {
              exprOwner = parent;
              exprIndent = ind;
              exprKey = key;
            }
          }
          continue;
        }
      }
    }

    if (node === null) continue;

    // Desempilha nós com indentação >= atual
    while (stack.length > 0 && stack[stack.length - 1][0] >= ind) {
      stack.pop();
    }

    if (stack.length > 0) {
      stack[stack.length - 1][1].children.push(node);
    } else {
      roots.push(node);
    }

    stack.push([ind, node]);

    // Expressão multilinha declarada na própria linha do objeto
    if (node.expr === "") {
      exprOwner = node;
      exprIndent = ind;
      exprKey = null;
    } else if (node.expr === "```") {
      inFence = true;
      fenceOwner = node;
      fenceKey = null;
      node.expr = "";
    }
  }

  return roots;
}

/** Coleta recursiva de todos os arquivos .tmdl de uma pasta */
export function collect(folder: string): TmdlDocs {
  const docs: TmdlDocs = {};

  function walk(dir: string) {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".tmdl")) {
        const rel = path.relative(folder, fullPath);
        try {
          docs[rel] = parseFile(fullPath, rel);
        } catch (exc) {
          docs[rel] = [];
          console.error(`[aviso] falha ao ler ${rel}: ${exc}`);
        }
      }
    }
  }

  walk(folder);
  return docs;
}

/** Remove refs duplicados — mantém a definição mais completa */
export function dedupe(nodes: TmdlNode[]): TmdlNode[] {
  const melhor = new Map<string, TmdlNode>();
  for (const n of nodes) {
    const atual = melhor.get(n.name);
    if (!atual || n.children.length > atual.children.length ||
        (n.children.length === atual.children.length && Object.keys(n.props).length > Object.keys(atual.props).length)) {
      melhor.set(n.name, n);
    }
  }
  return Array.from(melhor.values());
}

/** Achata a árvore coletando todos os nós de um determinado kind */
export function flatten(nodes: TmdlNode[], kind: string, out?: TmdlNode[]): TmdlNode[] {
  if (!out) out = [];
  for (const n of nodes) {
    if (n.kind === kind) out.push(n);
    flatten(n.children, kind, out);
  }
  return out;
}

/** Verifica se um valor é "true" */
export function isTrue(val: unknown): boolean {
  const s = String(val ?? "").trim().toLowerCase();
  return s === "true" || s === "1";
}
