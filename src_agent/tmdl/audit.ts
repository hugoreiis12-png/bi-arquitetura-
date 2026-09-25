// src_agent/tmdl/audit.ts — Engenharia de auditoria TMDL dirigida por regras JSON
// Port fiel de tmdl.py (linhas 309-679)

import * as fs from "node:fs";
import * as path from "node:path";
import { Counter } from "./utils.js";
import {
  type TmdlNode,
  type Rule,
  type RuleCondition,
  type Finding,
  type Inventory,
  type TableDetail,
  type AuditIndex,
  type Target,
  type Conventions,
  type AuditResult,
  type TmdlDocs,
  nodeProp,
  nodeKids,
} from "./types.js";
import {
  collect,
  dedupe,
  flatten,
  isTrue,
  stripQuotes,
  tokensDoNome,
} from "./parser.js";

// ============================================================
//  Constantes
// ============================================================

const SEVERIDADES: Record<string, number> = { baixa: 1, media: 2, alta: 3 };

const CONVENCOES_PADRAO: Conventions = {
  idioma: null,
  tokens: {
    chave: ["key", "keys", "sk", "id", "ids", "chave", "codigo", "código", "cod"],
    data: ["data", "date", "dt", "dia", "mes", "mês", "ano"],
  },
  nomenclatura: {},
  modelo: {},
  auditoria: { regrasDesativadas: {}, severidadeMinima: "baixa" },
};

// ============================================================
//  Convenções
// ============================================================

export function carregarJson(caminho: string): Record<string, unknown> | null {
  if (!caminho || !fs.existsSync(caminho)) return null;
  try {
    const content = fs.readFileSync(caminho, "utf-8");
    return JSON.parse(content);
  } catch {
    return null;
  }
}

export function mergeConvencoes(user: Record<string, unknown> | null): Conventions {
  const conv: Conventions = JSON.parse(JSON.stringify(CONVENCOES_PADRAO));
  if (!user) return conv;

  for (const [chave, valor] of Object.entries(user)) {
    if (chave.startsWith("$")) continue;
    const target = conv as Record<string, unknown>;
    const existing = target[chave];
    if (typeof valor === "object" && valor !== null && typeof existing === "object" && existing !== null) {
      for (const [k, v] of Object.entries(valor as Record<string, unknown>)) {
        if (!k.startsWith("$")) {
          (existing as Record<string, unknown>)[k] = v;
        }
      }
    } else {
      target[chave] = valor;
    }
  }
  return conv;
}

// ============================================================
//  Tokens e avaliação de predicados
// ============================================================

function resolverTokens(valor: string | string[], conv: Conventions): string[] {
  if (typeof valor === "string" && valor.startsWith("@")) {
    return (conv.tokens[valor.slice(1)] ?? []).map((t) => t.toLowerCase());
  }
  if (typeof valor === "string") return [valor.toLowerCase()];
  return valor.map((v) => String(v).toLowerCase());
}

/** Avalia um predicado declarativo — devolve boolean */
export function avaliar(cond: RuleCondition, alvo: Target, conv: Conventions, indice: AuditIndex): boolean {
  const node = alvo.node;

  // Operadores compostos
  if ("e" in cond) {
    return (cond as { e: RuleCondition[] }).e.every((c) => avaliar(c, alvo, conv, indice));
  }
  if ("ou" in cond) {
    return (cond as { ou: RuleCondition[] }).ou.some((c) => avaliar(c, alvo, conv, indice));
  }
  if ("nao" in cond) {
    return !avaliar((cond as { nao: RuleCondition }).nao, alvo, conv, indice);
  }

  // Predicados de propriedade
  if ("faltaPropriedade" in cond) {
    const props = (cond as { faltaPropriedade: string | string[] }).faltaPropriedade;
    const propsArr = Array.isArray(props) ? props : [props];
    return !propsArr.some((p) => nodeProp(node, p));
  }

  if ("temPropriedade" in cond) {
    const props = (cond as { temPropriedade: string | string[] }).temPropriedade;
    const propsArr = Array.isArray(props) ? props : [props];
    return propsArr.every((p) => nodeProp(node, p) !== undefined);
  }

  if ("propriedadeIgual" in cond) {
    const pairs = (cond as { propriedadeIgual: Record<string, string> }).propriedadeIgual;
    return Object.entries(pairs).every(
      ([k, v]) => (nodeProp(node, k) ?? "").trim().toLowerCase() === String(v).trim().toLowerCase()
    );
  }

  if ("propriedadeDiferente" in cond) {
    const pairs = (cond as { propriedadeDiferente: Record<string, string> }).propriedadeDiferente;
    return Object.entries(pairs).every(
      ([k, v]) => (nodeProp(node, k) ?? "").trim().toLowerCase() !== String(v).trim().toLowerCase()
    );
  }

  if ("propriedadePresenteEDiferente" in cond) {
    const pairs = (cond as { propriedadePresenteEDiferente: Record<string, string> }).propriedadePresenteEDiferente;
    for (const [k, v] of Object.entries(pairs)) {
      const atual = nodeProp(node, k);
      if (atual === undefined) return false;
      if (atual.trim().toLowerCase() === String(v).trim().toLowerCase()) return false;
    }
    return true;
  }

  if ("propriedadeEm" in cond) {
    const pairs = (cond as { propriedadeEm: Record<string, string[]> }).propriedadeEm;
    for (const [k, valores] of Object.entries(pairs)) {
      const atual = (nodeProp(node, k) ?? "").trim().toLowerCase();
      if (!valores.map((x) => String(x).toLowerCase()).includes(atual)) return false;
    }
    return true;
  }

  // Predicados de nome
  if ("nomeContemToken" in cond) {
    const tokens = new Set(resolverTokens((cond as { nomeContemToken: string | string[] }).nomeContemToken, conv));
    return tokensDoNome(node.name).some((t) => tokens.has(t));
  }

  if ("nomeCasaRegex" in cond) {
    // rules.json vem do Python: prefixo (?i) = case-insensitive (invalido no JS).
    let pattern = (cond as { nomeCasaRegex: string }).nomeCasaRegex;
    let flags = "";
    if (pattern.startsWith("(?i)")) {
      pattern = pattern.slice(4);
      flags = "i";
    }
    const regex = new RegExp(pattern, flags);
    return regex.test(node.name);
  }

  if ("nomeComecaCom" in cond) {
    const prefixos = resolverTokens((cond as { nomeComecaCom: string | string[] }).nomeComecaCom, conv);
    const low = node.name.toLowerCase();
    return prefixos.some((p) => low.startsWith(p));
  }

  // Predicados de descrição/expressão
  if ("semDescricao" in cond) {
    return (!node.description) === Boolean((cond as { semDescricao: boolean }).semDescricao);
  }

  if ("temExpressao" in cond) {
    return Boolean(node.expr && node.expr.trim()) === Boolean((cond as { temExpressao: boolean }).temExpressao);
  }

  if ("expressaoContem" in cond) {
    const alvoTxt = (node.expr ?? "").toUpperCase();
    const terms = (cond as { expressaoContem: string | string[] }).expressaoContem;
    const termsArr = Array.isArray(terms) ? terms : [terms];
    return termsArr.some((s) => alvoTxt.includes(String(s).toUpperCase()));
  }

  if ("expressaoLinhasMaiorQue" in cond) {
    return (node.expr ?? "").split("\n").length > (cond as { expressaoLinhasMaiorQue: number }).expressaoLinhasMaiorQue;
  }

  // Predicados de filhos
  if ("semFilhos" in cond) {
    const tipos = String((cond as { semFilhos: string }).semFilhos).toLowerCase().split("|");
    return !tipos.some((t) => nodeKids(node, t).length > 0);
  }

  if ("temFilhos" in cond) {
    const tipos = String((cond as { temFilhos: string }).temFilhos).toLowerCase().split("|");
    return tipos.some((t) => nodeKids(node, t).length > 0);
  }

  // Predicados de modelo
  if ("naoRelacionada" in cond) {
    const relacionada = indice.tabelas_relacionadas.has(node.name) || nodeKids(node, "calculationgroup").length > 0;
    return (!relacionada) === Boolean((cond as { naoRelacionada: boolean }).naoRelacionada);
  }

  if ("nomeDuplicadoNoModelo" in cond) {
    const dup = (indice.contagem_nomes.get(`${alvo.kind}:${node.name}`) ?? 0) > 1;
    return dup === Boolean((cond as { nomeDuplicadoNoModelo: boolean }).nomeDuplicadoNoModelo);
  }

  if ("contagemFilhosMaiorQue" in cond) {
    const [tipo, limite] = (cond as { contagemFilhosMaiorQue: [string, number] }).contagemFilhosMaiorQue;
    return nodeKids(node, String(tipo).toLowerCase()).length > Number(limite);
  }

   if ("medidaComLookups" in cond) {
    const esperado = Boolean((cond as { medidaComLookups: boolean }).medidaComLookups);
    const txt = (node.expr ?? "").toUpperCase();
    const tem = /\bLOOKUPVALUE\s*\(/.test(txt) || /\bVALUES\s*\(/.test(txt);
    return tem === esperado;
   }

  throw new Error(`predicado desconhecido: ${Object.keys(cond)}`);
}

// ============================================================
//  Coleta de alvos e inventário
// ============================================================

export function coletarAlvos(docs: TmdlDocs): [Target[], AuditIndex, Inventory, TableDetail[]] {
  const allRoots = Object.values(docs).flat();

  const databases = flatten(allRoots, "database");
  const models = flatten(allRoots, "model");
  const tables = dedupe(flatten(allRoots, "table"));
  const relationships = flatten(allRoots, "relationship");
  const roles = dedupe(flatten(allRoots, "role"));
  const perspectives = dedupe(flatten(allRoots, "perspective"));
  const cultures = dedupe([...flatten(allRoots, "culture"), ...flatten(allRoots, "cultureinfo")]);
  const expressions = flatten(allRoots, "expression");
  const calcGroups = flatten(allRoots, "calculationgroup");

  const alvos: Target[] = [];
  const columns: Array<[TmdlNode, TmdlNode]> = [];
  const measures: Array<[TmdlNode, TmdlNode]> = [];
  const partitions: Array<[TmdlNode, TmdlNode]> = [];
  const hierarchies: Array<[TmdlNode, TmdlNode]> = [];

  for (const db of databases) alvos.push({ node: db, kind: "database", rotulo: db.name });
  for (const m of models) alvos.push({ node: m, kind: "model", rotulo: m.name });

  for (const t of tables) {
    alvos.push({ node: t, kind: "table", rotulo: t.name });
    for (const c of nodeKids(t, "column")) {
      columns.push([t, c]);
      alvos.push({ node: c, kind: "column", pai: t, rotulo: `${t.name}[${c.name}]` });
    }
    for (const m of nodeKids(t, "measure")) {
      measures.push([t, m]);
      alvos.push({ node: m, kind: "measure", pai: t, rotulo: `${t.name}[${m.name}]` });
    }
    for (const p of nodeKids(t, "partition")) {
      partitions.push([t, p]);
      alvos.push({ node: p, kind: "partition", pai: t, rotulo: `${t.name}[${p.name}]` });
    }
    for (const h of nodeKids(t, "hierarchy")) {
      hierarchies.push([t, h]);
      alvos.push({ node: h, kind: "hierarchy", pai: t, rotulo: `${t.name}[${h.name}]` });
    }
  }

  for (const r of relationships) alvos.push({ node: r, kind: "relationship", rotulo: r.name });
  for (const r of roles) alvos.push({ node: r, kind: "role", rotulo: r.name });
  for (const p of perspectives) alvos.push({ node: p, kind: "perspective", rotulo: p.name });
  for (const c of cultures) alvos.push({ node: c, kind: "culture", rotulo: c.name });
  for (const e of expressions) alvos.push({ node: e, kind: "expression", rotulo: e.name });

  // Índices auxiliares
  const tabelasRelacionadas = new Set<string>();
  for (const r of relationships) {
    for (const ref of [nodeProp(r, "fromcolumn", ""), nodeProp(r, "tocolumn", "")]) {
      if (ref && ref.includes(".")) {
        tabelasRelacionadas.add(stripQuotes(ref.split(".", 1)[0]));
      }
    }
  }

  const contagemNomes = new Counter<string>();
  for (const a of alvos) {
    contagemNomes.inc(`${a.kind}:${a.node.name}`);
  }

  const indice: AuditIndex = {
    tabelas_relacionadas: tabelasRelacionadas,
    contagem_nomes: contagemNomes.map,
  };

  // Inventário
  const compatLevel = databases.length > 0 ? nodeProp(databases[0], "compatibilitylevel") ?? null : null;
  const dbCulture = models.length > 0 ? nodeProp(models[0], "culture") ?? null : null;

  const partitionModes = new Counter<string>();
  for (const [_t, p] of partitions) {
    partitionModes.inc((nodeProp(p, "mode") ?? "?").trim().toLowerCase());
  }

  const inventario: Inventory = {
    database: databases.length > 0 ? databases[0].name : null,
    compatibilityLevel: compatLevel,
    culture: dbCulture,
    tabelas: tables.length,
    tabelas_ocultas: tables.filter((t) => isTrue(nodeProp(t, "ishidden"))).length,
    colunas: columns.length,
    colunas_ocultas: columns.filter(([_t, c]) => isTrue(nodeProp(c, "ishidden"))).length,
    colunas_calculadas: columns.filter(([_t, c]) => c.expr).length,
    medidas: measures.length,
    relacionamentos: relationships.length,
    hierarquias: hierarchies.length,
    particoes: partitions.length,
    modos_de_particao: partitionModes.toObject(),
    roles: roles.length,
    perspectivas: perspectives.length,
    culturas: cultures.length,
    expressoes_compartilhadas: expressions.length,
    grupos_de_calculo: calcGroups.length,
    arquivos_tmdl: Object.keys(docs).length,
  };

  // Detalhe das tabelas
  const detalheTabelas: TableDetail[] = tables
    .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
    .map((t) => ({
      tabela: t.name,
      descricao: t.description,
      oculta: isTrue(nodeProp(t, "ishidden")),
      colunas: nodeKids(t, "column").length,
      medidas: nodeKids(t, "measure").length,
      hierarquias: nodeKids(t, "hierarchy").length,
      particoes: nodeKids(t, "partition").map((p) => [p.name, nodeProp(p, "mode") ?? "?"] as [string, string]),
      arquivo: t.file,
    }));

  return [alvos, indice, inventario, detalheTabelas];
}

// ============================================================
//  Execução de regras
// ============================================================

export function executarRegras(alvos: Target[], indice: AuditIndex, regras: Rule[], conv: Conventions): Finding[] {
  const desativadas = conv.auditoria?.regrasDesativadas ?? {};
  const minima = SEVERIDADES[conv.auditoria?.severidadeMinima ?? "baixa"] ?? 1;

  const achados: Finding[] = [];

  for (const regra of regras) {
    if (regra.id in desativadas) continue;
    const sev = regra.severidade ?? "baixa";
    if ((SEVERIDADES[sev] ?? 1) < minima) continue;

    const escopo = (regra.escopo ?? "").toLowerCase();
    const cond = regra.quando;
    if (!cond) continue;

    const itens: string[] = [];
    for (const alvo of alvos) {
      if (alvo.kind !== escopo) continue;
      try {
        if (avaliar(cond, alvo, conv, indice)) {
          itens.push(alvo.rotulo);
        }
      } catch (exc) {
        console.error(`[aviso] regra '${regra.id}': ${exc}`);
        break;
      }
    }

    if (itens.length > 0) {
      achados.push({
        id: regra.id,
        titulo: regra.titulo ?? regra.id,
        severidade: sev,
        porque: regra.porque,
        correcao: regra.correcao,
        quantidade: itens.length,
        itens,
      });
    }
  }

  const ordemSev: Record<string, number> = { alta: 0, media: 1, baixa: 2 };
  achados.sort((a, b) => (ordemSev[a.severidade] ?? 9) - (ordemSev[b.severidade] ?? 9) || b.quantidade - a.quantidade);

  return achados;
}

// ============================================================
//  Renderização Markdown
// ============================================================

export function renderMd(
  inventario: Inventory,
  tabelas: TableDetail[],
  achados: Finding[],
  conv: Conventions,
  limite: number = 25
): string {
  const out: string[] = ["# Auditoria do modelo semântico", ""];

  const total = achados.reduce((s, a) => s + a.quantidade, 0);
  const altas = achados.filter((a) => a.severidade === "alta").reduce((s, a) => s + a.quantidade, 0);
  out.push(`${total} ocorrências em ${achados.length} regras — ${altas} de severidade alta.`);
  out.push("");

  // Inventário
  out.push("## Inventário");
  out.push("");
  out.push("| Item | Valor |");
  out.push("| --- | --- |");
  for (const [k, v] of Object.entries(inventario)) {
    let display: string;
    if (typeof v === "object" && v !== null) {
      display = Object.entries(v as Record<string, number>)
        .map(([kk, vv]) => `${kk}: ${vv}`)
        .join(", ") || "—";
    } else {
      display = v !== null && v !== undefined ? String(v) : "—";
    }
    out.push(`| ${k} | ${display} |`);
  }
  out.push("");

  // Tabelas
  out.push("## Tabelas");
  out.push("");
  out.push("| Tabela | Oculta | Colunas | Medidas | Hierarquias | Partições | Descrição |");
  out.push("| --- | --- | --- | --- | --- | --- | --- |");
  for (const t of tabelas) {
    const parts = t.particoes.map(([n, m]) => `${n} (${m})`).join(", ") || "—";
    let desc = (t.descricao ?? "—").replace(/\|/g, "\\|");
    if (desc.length > 60) desc = desc.slice(0, 57) + "...";
    out.push(
      `| ${t.tabela} | ${t.oculta ? "sim" : "não"} | ${t.colunas} | ${t.medidas} | ${t.hierarquias} | ${parts} | ${desc} |`
    );
  }
  out.push("");

  // Achados
  out.push("## Achados");
  out.push("");
  if (achados.length === 0) {
    out.push("Nenhuma regra do conjunto ativo foi violada.");
  }
  for (const a of achados) {
    out.push(`### [${a.severidade}] ${a.titulo} (${a.quantidade})`);
    out.push("");
    if (a.porque) {
      out.push(`_${a.porque}_`);
      out.push("");
    }
    for (const item of a.itens.slice(0, limite)) {
      out.push(`- ${item}`);
    }
    if (a.quantidade > limite) {
      out.push(`- _(+${a.quantidade - limite} não listados)_`);
    }
    if (a.correcao) {
      out.push("");
      out.push(`**Correção:** ${a.correcao}`);
    }
    out.push("");
  }

  const desativadas = conv.auditoria?.regrasDesativadas ?? {};
  const desativadasEntries = Object.entries(desativadas);
  if (desativadasEntries.length > 0) {
    out.push("## Regras desativadas neste projeto");
    out.push("");
    for (const [rid, motivo] of desativadasEntries) {
      out.push(`- \`${rid}\` — ${motivo}`);
    }
    out.push("");
  }

  return out.join("\n");
}

//  Função principal de auditoria

export function runAudit(
  folder: string,
  rulesPath?: string,
  conventionsPath?: string,
  format: "json" | "md" = "json",
  failOnHigh: boolean = false,
  maxItems: number = 25
): { result: string; exitCode: number } {
  // Resolver path das regras
  const effectiveRules = rulesPath ?? path.join(import.meta.dirname ?? ".", "rules.json");

  if (!fs.existsSync(effectiveRules)) {
    return { result: JSON.stringify({ error: `Regras não encontradas: ${effectiveRules}` }), exitCode: 2 };
  }

  if (!fs.existsSync(folder)) {
    return { result: JSON.stringify({ error: `Pasta não encontrada: ${folder}` }), exitCode: 2 };
  }

  // Carregar regras
  const regrasDoc = carregarJson(effectiveRules) as { rules?: Rule[] } | null;
  if (!regrasDoc) {
    return { result: JSON.stringify({ error: `Erro ao carregar regras: ${effectiveRules}` }), exitCode: 2 };
  }
  const regras = regrasDoc.rules ?? [];

  // Carregar convenções
  let convPath = conventionsPath;
  if (!convPath) {
    for (const candidato of [
      path.join(folder, "tmdl.conventions.json"),
      path.join(folder, "..", "tmdl.conventions.json"),
      path.join(folder, "..", "..", "tmdl.conventions.json"),
    ]) {
      if (fs.existsSync(candidato)) {
        convPath = candidato;
        break;
      }
    }
  }
  const conv = mergeConvencoes(carregarJson(convPath ?? "") as Record<string, unknown> | null);

  // Coletar TMDL
  const docs = collect(folder);
  if (Object.keys(docs).length === 0) {
    return { result: JSON.stringify({ error: `Nenhum arquivo .tmdl encontrado em ${folder}` }), exitCode: 2 };
  }

  // Executar auditoria
  const [alvos, indice, inventario, tabelas] = coletarAlvos(docs);
  const achados = executarRegras(alvos, indice, regras, conv);

  if (format === "md") {
    return { result: renderMd(inventario, tabelas, achados, conv, maxItems), exitCode: 0 };
  }

  // JSON output
  const result: AuditResult = {
    inventario,
    tabelas,
    achados,
    convencoes: convPath ?? null,
    regras: effectiveRules,
    resumo: {
      total_ocorrencias: achados.reduce((s, a) => s + a.quantidade, 0),
      regras_violadas: achados.length,
      alta: achados.filter((a) => a.severidade === "alta").reduce((s, a) => s + a.quantidade, 0),
      media: achados.filter((a) => a.severidade === "media").reduce((s, a) => s + a.quantidade, 0),
      baixa: achados.filter((a) => a.severidade === "baixa").reduce((s, a) => s + a.quantidade, 0),
    },
  };

  let exitCode = 0;
  if (failOnHigh) {
    const piso = SEVERIDADES["alta"];
    if (achados.some((a) => (SEVERIDADES[a.severidade] ?? 1) >= piso)) {
      exitCode = 1;
    }
  }

  return { result: JSON.stringify(result, null, 2), exitCode };
}
