#!/usr/bin/env node
// src/index.ts — dax-staff-mcp v2
// Cobertura das 5 camadas do stack de front-end Power BI:
// C1 Temas JSON | C2 SVG via DAX | C3 HTML+CSS | C4 Deneb/Vega-Lite | C5 SDK pbiviz
// + Auditoria TMDL dirigida por regras JSON

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { tmdlAuditTool, handleTmdlAudit } from "./tmdl/tools.js";
import { callGateway } from "./gateway/client.js";

const server = new McpServer({
  name: "dax-staff-mcp",
  version: "2.0.0",
});

// ---------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------

/** Remove strings entre aspas para nao contar parenteses dentro de literais */
function stripStrings(code: string): string {
  return code.replace(/"[^"]*"/g, '""');
}

function balanced(code: string, open: string, close: string): boolean {
  let depth = 0;
  for (const ch of code) {
    if (ch === open) depth++;
    else if (ch === close) depth--;
    if (depth < 0) return false;
  }
  return depth === 0;
}

/** Cores em data URI precisam de %23 no lugar de # */
function svgColor(color: string): string {
  return color.replace("#", "%23");
}

// ---------------------------------------------------------------
// TOOL: validate_dax (v2 — validator reforcado)
// ---------------------------------------------------------------
server.tool(
  "validate_dax",
  "Valida uma medida DAX: balanceamento estrutural + anti-patterns de performance e legibilidade",
  {
    measure_code: z.string().describe("Codigo DAX da medida"),
    measure_name: z.string().optional().describe("Nome da medida")
  },
  async ({ measure_code, measure_name }) => {
    const errors: string[] = [];
    const issues: string[] = [];
    const suggestions: string[] = [];

    // --- Checagens estruturais (erros duros) ---
    const quoteCount = (measure_code.match(/"/g) || []).length;
    if (quoteCount % 2 !== 0) {
      errors.push("Aspas desbalanceadas — literal de texto nao fechado");
    }
    const clean = stripStrings(measure_code);
    if (!balanced(clean, "(", ")")) {
      errors.push("Parenteses desbalanceados");
    }
    if (!balanced(clean, "[", "]")) {
      errors.push("Colchetes desbalanceados — referencia de medida/coluna incompleta");
    }

    // --- Anti-patterns (issues) ---
    if (/\bEARLIER\s*\(/i.test(clean)) {
      issues.push("EARLIER detectado — padrao legado dificil de ler e manter");
      suggestions.push("Capture o valor da linha atual em VAR antes do FILTER e compare com a variavel");
    }

    if (/\bSUMX\s*\(/i.test(clean) && !clean.includes("*") && !clean.includes("/")) {
      issues.push("SUMX sem expressao aritmetica — verifique se SUM simples resolve");
      suggestions.push("SUMX so se justifica com calculo linha a linha; para coluna unica use SUM");
    }

    if (/\bCALCULATE\s*\([^)]*\bFILTER\s*\(/is.test(clean)) {
      issues.push("FILTER como argumento de filtro em CALCULATE");
      suggestions.push("Prefira predicado booleano: CALCULATE([Medida], Tabela[Coluna] = valor) — o engine otimiza melhor");
    }

    const divisions = clean.match(/[^\/]\/[^\/*]/g);
    if (divisions && !/\bDIVIDE\s*\(/i.test(clean)) {
      issues.push("Divisao com operador '/' — risco de erro de divisao por zero");
      suggestions.push("Use DIVIDE(numerador, denominador [, alternativa])");
    }

    if (/\bALL\s*\(/i.test(clean) && /\bFILTER\s*\(/i.test(clean) && !/\bALLSELECTED\b/i.test(clean)) {
      suggestions.push("FILTER(ALL(...)) ignora selecoes do usuario — confirme se ALLSELECTED nao seria o contexto correto");
    }

    if (!/\bVAR\b/i.test(clean) && measure_code.length > 200) {
      suggestions.push("Medida longa sem VAR — variaveis melhoram legibilidade e evitam reavaliacao");
    }

    // --- Score ---
    const score =
      errors.length > 0 ? "F" :
      issues.length === 0 ? "A" :
      issues.length <= 2 ? "B" : "C";

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          measure: measure_name || "unnamed",
          errors,
          issues,
          suggestions,
          score,
          note: errors.length > 0
            ? "Erros estruturais impedem compilacao — corrija antes dos anti-patterns"
            : "Validacao heuristica; validacao contra o modelo real fica a cargo do powerbi-modeling-mcp"
        }, null, 2)
      }]
    };
  }
);

// ---------------------------------------------------------------
// TOOL: generate_theme_json (CAMADA 1 — Temas JSON / Design Tokens)
// ---------------------------------------------------------------
server.tool(
  "generate_theme_json",
  "Gera arquivo de tema JSON do Power BI (design tokens: cores, fontes, estilos de visual)",
  {
    theme_name: z.string().describe("Nome do tema"),
    data_colors: z.array(z.string()).min(3).describe("Paleta principal (hex), ex: ['#0066CC','#00A3E0','#7AB800']"),
    font_family: z.string().default("Segoe UI").describe("Fonte padrao"),
    background: z.string().default("#FFFFFF").describe("Cor de fundo dos visuais"),
    good_color: z.string().default("#16A34A").describe("Cor semantica: positivo"),
    bad_color: z.string().default("#DC2626").describe("Cor semantica: negativo"),
    neutral_color: z.string().default("#6B7280").describe("Cor semantica: neutro")
  },
  async ({ theme_name, data_colors, font_family, background, good_color, bad_color, neutral_color }) => {
    const theme = {
      name: theme_name,
      dataColors: data_colors,
      good: good_color,
      bad: bad_color,
      neutral: neutral_color,
      background: background,
      foreground: "#1F2937",
      tableAccent: data_colors[0],
      textClasses: {
        title: { fontFace: font_family, fontSize: 14, color: "#1F2937" },
        label: { fontFace: font_family, fontSize: 10, color: "#374151" },
        callout: { fontFace: font_family, fontSize: 28, color: "#111827" }
      },
      visualStyles: {
        "*": {
          "*": {
            background: [{ color: { solid: { color: background } }, transparency: 0 }],
            border: [{ show: false }],
            title: [{ fontFamily: font_family, fontSize: 12, alignment: "left" }],
            outspacePane: [{ backgroundColor: { solid: { color: background } } }]
          }
        }
      }
    };
    return {
      content: [{
        type: "text",
        text: [
          "Salve como " + theme_name.replace(/\s+/g, "-").toLowerCase() + ".json e importe em Exibicao > Temas > Procurar temas:",
          "```json",
          JSON.stringify(theme, null, 2),
          "```"
        ].join("\n")
      }]
    };
  }
);

// ---------------------------------------------------------------
// TOOL: generate_svg (CAMADA 2 — SVG via DAX, familia de micro-visuais)
// ---------------------------------------------------------------
server.tool(
  "generate_svg",
  "Gera medida DAX que produz micro-visual SVG (sparkline, bullet chart ou barra in-cell) como Image URL",
  {
    visual_type: z.enum(["sparkline", "bullet", "bar"]).describe("Tipo de micro-visual"),
    measure: z.string().describe("Medida base, ex: [Total Sales]"),
    category_column: z.string().optional().describe("Coluna de eixo para sparkline, ex: DimDate[MonthKey] (obrigatoria para sparkline)"),
    target_measure: z.string().optional().describe("Medida de meta para bullet, ex: [Sales Target]"),
    width: z.number().default(120),
    height: z.number().default(24),
    color: z.string().default("#0066CC")
  },
  async ({ visual_type, measure, category_column, target_measure, width, height, color }) => {
    const c = svgColor(color);
    const gray = "%23E5E7EB";
    const dark = "%23374151";
    let dax = "";

    if (visual_type === "sparkline") {
      if (!category_column) {
        return { content: [{ type: "text", text: "Erro: sparkline exige category_column (ex: DimDate[MonthKey])." }] };
      }
      dax = `SVG Sparkline =
VAR Pts =
    ADDCOLUMNS(
        VALUES(${category_column}),
        "@Val", CALCULATE(${measure})
    )
VAR N = COUNTROWS(Pts)
VAR MinV = MINX(Pts, [@Val])
VAR MaxV = MAXX(Pts, [@Val])
VAR Rng = IF(MaxV - MinV = 0, 1, MaxV - MinV)
VAR Points =
    CONCATENATEX(
        Pts,
        VAR i = RANKX(Pts, ${category_column}, , ASC)
        VAR x = (i - 1) * (${width} / (N - 1))
        VAR y = ${height} - (([@Val] - MinV) / Rng * ${height})
        RETURN FORMAT(x, "0.0") & "," & FORMAT(y, "0.0"),
        " ",
        ${category_column}, ASC
    )
RETURN
IF(N > 1,
"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='${width}' height='${height}' viewBox='0 0 ${width} ${height}'><polyline points='" & Points & "' fill='none' stroke='${c}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/></svg>"
)`;
    }

    if (visual_type === "bullet") {
      const target = target_measure || "[Target]";
      dax = `SVG Bullet =
VAR Actual = ${measure}
VAR Target = ${target}
VAR MaxScale = MAX(Actual, Target) * 1.1
VAR WActual = DIVIDE(Actual, MaxScale, 0) * ${width}
VAR XTarget = DIVIDE(Target, MaxScale, 0) * ${width}
RETURN
"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='${width}' height='${height}' viewBox='0 0 ${width} ${height}'>" &
"<rect x='0' y='" & ${height} * 0.25 & "' width='${width}' height='" & ${height} * 0.5 & "' fill='${gray}' rx='2'/>" &
"<rect x='0' y='" & ${height} * 0.25 & "' width='" & FORMAT(WActual, "0.0") & "' height='" & ${height} * 0.5 & "' fill='${c}' rx='2'/>" &
"<line x1='" & FORMAT(XTarget, "0.0") & "' y1='2' x2='" & FORMAT(XTarget, "0.0") & "' y2='" & ${height} - 2 & "' stroke='${dark}' stroke-width='2'/>" &
"</svg>"`;
    }

    if (visual_type === "bar") {
      dax = `SVG Bar InCell =
VAR Actual = ${measure}
VAR MaxAll = CALCULATE(MAXX(ALLSELECTED(), ${measure}))
VAR W = DIVIDE(Actual, MaxAll, 0) * ${width}
RETURN
"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='${width}' height='${height}' viewBox='0 0 ${width} ${height}'>" &
"<rect x='0' y='2' width='" & FORMAT(W, "0.0") & "' height='" & ${height} - 4 & "' fill='${c}' rx='2'/>" &
"</svg>"`;
    }

    return {
      content: [{
        type: "text",
        text: [
          "```dax",
          dax,
          "```",
          "",
          "Setup no Power BI: selecione a medida > Ferramentas de medida > Categoria de dados = URL de Imagem. Use em Table, Matrix ou New Card.",
          "Nota: cores usam %23 no lugar de # — obrigatorio em data URI."
        ].join("\n")
      }]
    };
  }
);

// ---------------------------------------------------------------
// TOOL: generate_html_component (CAMADA 3 — HTML + CSS)
// ---------------------------------------------------------------
server.tool(
  "generate_html_component",
  "Gera medida DAX que produz componente HTML/CSS (card de KPI) para visuais HTML Content / HTML VizCreator",
  {
    component: z.enum(["kpi_card", "kpi_card_animated"]).describe("Tipo de componente"),
    title: z.string().describe("Titulo do card, ex: 'Vendas Totais'"),
    value_measure: z.string().describe("Medida do valor principal, ex: [Total Sales]"),
    delta_measure: z.string().optional().describe("Medida de variacao percentual, ex: [Sales YoY %]"),
    value_format: z.string().default("$#,##0").describe("Formato do valor (sintaxe FORMAT)"),
    accent_color: z.string().default("#0066CC")
  },
  async ({ component, title, value_measure, delta_measure, value_format, accent_color }) => {
    const deltaBlock = delta_measure
      ? `VAR Delta = ${delta_measure}
VAR DeltaColor = IF(Delta >= 0, "#16A34A", "#DC2626")
VAR DeltaIcon = IF(Delta >= 0, UNICHAR(9650), UNICHAR(9660))
VAR DeltaHtml = "<div style='font-size:13px; font-weight:600; color:" & DeltaColor & ";'>" & DeltaIcon & " " & FORMAT(ABS(Delta), "0.0%") & "</div>"`
      : `VAR DeltaHtml = ""`;

    const animCss = component === "kpi_card_animated"
      ? `"<style>@keyframes fadeUp {from {opacity:0; transform:translateY(8px);} to {opacity:1; transform:translateY(0);}} .kpi {animation: fadeUp 0.5s ease-out;} .kpi:hover {transform:scale(1.02); transition:transform 0.15s;}</style>" & `
      : ``;

    const dax = `HTML ${title.replace(/[^A-Za-z0-9]/g, "")} Card =
${deltaBlock}
RETURN
${animCss}"<div class='kpi' style='font-family:Segoe UI, sans-serif; background:#FFFFFF; border-radius:12px; padding:20px; border-left:4px solid ${accent_color}; box-shadow:0 1px 3px rgba(0,0,0,0.08);'>" &
"<div style='font-size:12px; color:#6B7280; text-transform:uppercase; letter-spacing:0.05em;'>${title}</div>" &
"<div style='font-size:32px; font-weight:700; color:#111827; margin:4px 0;'>" & FORMAT(${value_measure}, "${value_format}") & "</div>" &
DeltaHtml &
"</div>"`;

    return {
      content: [{
        type: "text",
        text: [
          "```dax",
          dax,
          "```",
          "",
          "Requisito: visual HTML Content (Daniel Marsh-Patrick) ou HTML VizCreator — HTML nao renderiza em visuais nativos.",
          "Arraste a medida para o campo Values do visual HTML."
        ].join("\n")
      }]
    };
  }
);

// ---------------------------------------------------------------
// TOOL: generate_deneb_spec (CAMADA 4 — Vega-Lite declarativo)
// ---------------------------------------------------------------
server.tool(
  "generate_deneb_spec",
  "Gera specification Vega-Lite pronta para o visual Deneb (bar, line, heatmap, area)",
  {
    chart_type: z.enum(["bar", "line", "area", "heatmap"]).describe("Tipo de grafico"),
    x_field: z.string().describe("Campo do eixo X (nome exato no dataset do Deneb)"),
    y_field: z.string().describe("Campo do eixo Y / valor"),
    color_field: z.string().optional().describe("Campo de cor/serie (opcional; no heatmap e o valor da celula)"),
    x_type: z.enum(["nominal", "ordinal", "temporal", "quantitative"]).default("nominal"),
    accent_color: z.string().default("#0066CC")
  },
  async ({ chart_type, x_field, y_field, color_field, x_type, accent_color }) => {
    const base: Record<string, unknown> = {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json",
      usermeta: { deneb: { build: "1.9.0", metaVersion: 1, provider: "vegaLite" } },
      data: { name: "dataset" },
      config: {
        font: "Segoe UI",
        axis: { labelColor: "#374151", titleColor: "#374151", gridColor: "#F3F4F6" },
        view: { stroke: "transparent" }
      }
    };

    let spec: Record<string, unknown> = base;

    if (chart_type === "bar") {
      spec = {
        ...base,
        mark: { type: "bar", cornerRadiusEnd: 4, tooltip: true },
        encoding: {
          x: { field: x_field, type: x_type, axis: { labelAngle: 0 } },
          y: { field: y_field, type: "quantitative" },
          ...(color_field
            ? { color: { field: color_field, type: "nominal" } }
            : { color: { value: accent_color } })
        }
      };
    }

    if (chart_type === "line" || chart_type === "area") {
      spec = {
        ...base,
        mark: { type: chart_type, point: chart_type === "line", tooltip: true, ...(chart_type === "area" ? { opacity: 0.7 } : {}) },
        encoding: {
          x: { field: x_field, type: x_type === "nominal" ? "temporal" : x_type },
          y: { field: y_field, type: "quantitative" },
          ...(color_field
            ? { color: { field: color_field, type: "nominal" } }
            : { color: { value: accent_color } })
        }
      };
    }

    if (chart_type === "heatmap") {
      spec = {
        ...base,
        mark: { type: "rect", tooltip: true },
        encoding: {
          x: { field: x_field, type: x_type },
          y: { field: y_field, type: "nominal" },
          color: {
            field: color_field || y_field,
            type: "quantitative",
            scale: { scheme: "blues" }
          }
        }
      };
    }

    return {
      content: [{
        type: "text",
        text: [
          "Cole no editor do Deneb (aba Specification). Os campos devem estar no bucket Values do visual com estes nomes exatos:",
          "```json",
          JSON.stringify(spec, null, 2),
          "```",
          "",
          "Cross-filtering: habilite em Settings > Interactivity dentro do Deneb."
        ].join("\n")
      }]
    };
  }
);

// ---------------------------------------------------------------
// TOOL: search_dax_pattern (biblioteca — patterns revisados)
// ---------------------------------------------------------------
server.tool(
  "search_dax_pattern",
  "Busca patterns DAX na biblioteca interna",
  {
    pattern_name: z.string().describe("Nome do pattern (ex: cohort, abc, running-total, semantic-color, status-icon)"),
    context: z.string().optional().describe("Contexto adicional para personalizacao")
  },
  async ({ pattern_name, context: _context }) => {
    const patterns: Record<string, { description: string; code: string }> = {
      "cohort": {
        description: "Analise de retencao de clientes por cohort",
        code: `Cohort Retention =
VAR FirstPurchase = CALCULATE(MIN(Sales[Date]), ALL(DimDate))
RETURN CALCULATE(DISTINCTCOUNT(Sales[CustomerID]), FILTER(ALL(DimDate), DimDate[Date] >= FirstPurchase))`
      },
      "abc": {
        description: "Classificacao ABC — versao com VAR, sem EARLIER",
        code: `ABC Class =
VAR CurrentSales = [Total Sales]
VAR TotalSales = CALCULATE([Total Sales], ALL(Products))
VAR RunningTotal =
    SUMX(
        FILTER(ALL(Products), [Total Sales] >= CurrentSales),
        [Total Sales]
    )
VAR Pct = DIVIDE(RunningTotal, TotalSales)
RETURN SWITCH(TRUE(), Pct <= 0.8, "A", Pct <= 0.95, "B", "C")`
      },
      "running-total": {
        description: "Total acumulado (running total)",
        code: `Running Total =
CALCULATE([Total Sales], FILTER(ALL(DimDate[Date]), DimDate[Date] <= MAX(DimDate[Date])))`
      },
      "semantic-color": {
        description: "Sistema de cores semantico para conditional formatting (field value)",
        code: `Color Semantic =
SWITCH(TRUE(),
    [KPI Status] = "Critical", "#DC2626",
    [KPI Status] = "Warning", "#F59E0B",
    [KPI Status] = "Good", "#16A34A",
    "#6B7280"
)`
      },
      "status-icon": {
        description: "Icones Unicode para status em tabelas/cards",
        code: `Icon Status =
SWITCH(TRUE(),
    [KPI Status] = "Critical", UNICHAR(9660),
    [KPI Status] = "Warning", UNICHAR(9650),
    [KPI Status] = "Good", UNICHAR(9654),
    UNICHAR(9679)
)`
      }
    };

    const pattern = patterns[pattern_name.toLowerCase()];
    if (!pattern) {
      return {
        content: [{
          type: "text",
          text: `Pattern "${pattern_name}" nao encontrado. Disponiveis: ${Object.keys(patterns).join(", ")}`
        }]
      };
    }

    return {
      content: [{
        type: "text",
        text: `# ${pattern_name.toUpperCase()} Pattern\n\n**Descricao:** ${pattern.description}\n\n\`\`\`dax\n${pattern.code}\n\`\`\``
      }]
    };
  }
);

// ---------------------------------------------------------------
// RESOURCE: Referencia DAX
// ---------------------------------------------------------------
server.resource(
  "dax-reference",
  "dax://reference",
  async (uri) => ({
    contents: [{
      uri: uri.href,
      text: `# DAX Reference

## Funcoes de Agregacao
- SUM, AVERAGE, MIN, MAX, COUNT, COUNTROWS, DISTINCTCOUNT

## Funcoes de Filtro
- CALCULATE, FILTER, ALL, ALLSELECTED, VALUES, DISTINCT

## Time Intelligence
- TOTALYTD, TOTALMTD, TOTALQTD, SAMEPERIODLASTYEAR, DATEADD, DATESINPERIOD

## Iteradores
- SUMX, AVERAGEX, MINX, MAXX, COUNTX

## Funcoes de Tabela
- SUMMARIZE, ADDCOLUMNS, TREATAS, CROSSFILTER, SUMMARIZECOLUMNS`
    }]
  })
);

// ---------------------------------------------------------------
// RESOURCE: Guia do stack de front-end (5 camadas) + setup pbiviz (C5)
// ---------------------------------------------------------------
server.resource(
  "frontend-stack",
  "dax://frontend-stack",
  async (uri) => ({
    contents: [{
      uri: uri.href,
      text: `# Stack de Front-end Power BI — 5 Camadas

C1 Temas JSON        -> tool: generate_theme_json
C2 SVG via DAX       -> tool: generate_svg (sparkline | bullet | bar)
C3 HTML + CSS        -> tool: generate_html_component (requer visual HTML Content)
C4 Deneb/Vega-Lite   -> tool: generate_deneb_spec (bar | line | area | heatmap)
C5 Custom SDK pbiviz -> scaffold manual (abaixo)

## C5 — Setup pbiviz
1. Pre-requisitos: Node.js 18+, conta Power BI Pro/PPU
2. npm install -g powerbi-visuals-tools@latest
3. pbiviz new MeuVisual && cd MeuVisual && npm install
4. pbiviz start (dev server; habilite Developer Mode no Power BI Service)
5. Estrutura: pbiviz.json (metadados) | capabilities.json (data roles) | src/visual.ts (classe IVisual com constructor/update/destroy)
6. Certificacao: codigo sem fetch/eval/innerHTML com dados de usuario; pbiviz package para empacotar .pbiviz

## Performance por camada
- SVG DAX: limite pratico ~32k chars por medida
- HTML: minimize DOM e animacoes pesadas
- Deneb: specs simples, evite transforms redundantes
- SDK: virtualize renderizacao e faca debounce de updates`
    }]
  })
);

// ---------------------------------------------------------------
// TOOL: tmdl_audit (Auditoria TMDL dirigida por regras JSON)
// ---------------------------------------------------------------
server.tool(
  "tmdl_audit",
  tmdlAuditTool.description,
  tmdlAuditTool.inputSchema,
  async (input) => {
    const result = handleTmdlAudit(input);
    return {
      content: [{
        type: "text",
        text: result
      }]
    };
  }
);

// ---------------------------------------------------------------
// GATEWAY TMDL-only (fachada fina -> gateway-py separado)
// Pull 2 fases (propose exige aceite p/ apply), commit exige approval token,
// DAX RUN local via localhost (sem token). TS nunca escreve Git/definition/.
// ---------------------------------------------------------------
function gwText(input: unknown): { content: Array<{ type: "text"; text: string }> } {
  const r = callGateway(input as string[]);
  return { content: [{ type: "text" as const, text: JSON.stringify(r.json, null, 2) }] };
}

server.tool(
  "tmdl_pull_propose",
  "Fase 1 somente-leitura: inventaria o dataset conectado e devolve proposta (aplique só com tmdl_pull_apply + accept:true)",
  { workspace: z.string().describe("Workspace (Name; ID único resolve no gateway)"), dataset: z.string().describe("Dataset base, ex: Vendas_Dev") },
  async ({ workspace, dataset }) => gwText(["pull-propose", "--workspace", workspace, "--dataset", dataset])
);

server.tool(
  "tmdl_pull_apply",
  "Fase 2 (único ponto que escreve no repo): exige proposal_id + accept:true; com dataset_dir materializa o export, com pbip_layout normaliza TOM->PBIP",
  {
    proposal: z.string().describe("proposal_id do tmdl_pull_propose"),
    accept: z.boolean().describe("Deve ser true explícito"),
    dataset_dir: z.string().optional().describe("Destino, ex: src/datasets/Vendas.Dataset"),
    pbip_layout: z.boolean().default(false).describe("Normaliza TOM->PBIP no destino")
  },
  async ({ proposal, accept, dataset_dir, pbip_layout }) => gwText([
    "pull-apply", "--proposal", proposal,
    ...(accept ? ["--accept"] : []),
    ...(dataset_dir ? ["--dataset-dir", dataset_dir] : []),
    ...(pbip_layout ? ["--pbip-layout"] : [])
  ])
);

server.tool(
  "tmdl_approval_request",
  "Emite approval token single-use p/ tmdl_commit (main/Vendas exige 2 aprovadores)",
  {
    target: z.string().describe("branch:dataset, ex: feat/x:Vendas_preview_feat_x"),
    reason: z.string().optional().describe("Justificativa"),
    requested_by: z.string().optional().describe("Solicitante")
  },
  async ({ target, reason, requested_by }) => gwText(["approval-request", "--target", target, ...(reason ? ["--reason", reason] : []), ...(requested_by ? ["--requested-by", requested_by] : [])])
);

server.tool(
  "tmdl_approve",
  "Registra um aprovador no token (prod exige 2 antes do commit)",
  { token: z.string().describe("Token apv_*"), approver: z.string().describe("Email do aprovador") },
  async ({ token, approver }) => gwText(["approve", "--token", token, "--approver", approver])
);

server.tool(
  "tmdl_commit",
  "Commit só-TMDL gateado: exige approval token válido + mensagem Conventional Commits; divergência por branch",
  {
    branch: z.string().describe("Branch a criar"),
    message: z.string().describe("Mensagem Conventional Commits"),
    approval: z.string().describe("Token apv_* válido p/ branch:dataset"),
    target_dataset: z.string().optional().describe("Override (default: derivado do branch)"),
    create_pr: z.boolean().default(false).describe("Abrir PR via gh")
  },
  async ({ branch, message, approval, target_dataset, create_pr }) => gwText(["commit", "--branch", branch, "--message", message, "--approval", approval, ...(target_dataset ? ["--target-dataset", target_dataset] : []), ...(create_pr ? ["--create-pr"] : [])])
);

server.tool(
  "bulk_propose",
  "Bulk sempre em transação: fase 1 dry-run (cap 200 ops, chunks de 50)",
  {
    workspace: z.string().describe("Workspace"),
    dataset: z.string().describe("Dataset alvo"),
    operations: z.string().describe("JSON array de operações do sidecar")
  },
  async ({ workspace, dataset, operations }) => gwText(["bulk-propose", "--workspace", workspace, "--dataset", dataset, "--operations", operations])
);

server.tool(
  "bulk_apply",
  "Bulk fase 2: exige proposal + accept:true; executa Begin→chunks→Commit/Rollback no sidecar",
  {
    proposal: z.string().describe("proposal_id do bulk_propose"),
    accept: z.boolean().describe("Deve ser true explícito"),
    connection: z.string().describe("Conexão do sidecar (ex: localhost:<porta> ou dataset)")
  },
  async ({ proposal, accept, connection }) => gwText(accept ? ["bulk-apply", "--proposal", proposal, "--accept", "--connection", connection] : ["bulk-apply", "--proposal", proposal, "--connection", connection])
);

server.tool(
  "dax_run_local",
  "DAX RUN local: auto-detecta localhost:<porta>, valida+audit+compila, escreve no Desktop em memória em transação e persiste definition/ (sem approval token; Service continua via tmdl_commit)",
  { dataset_path: z.string().describe("Pasta do dataset, ex: src/datasets/Vendas.Dataset") },
  async ({ dataset_path }) => gwText(["dax-run", "--dataset-path", dataset_path])
);

// ---------------------------------------------------------------
// Iniciar servidor
// ---------------------------------------------------------------
const transport = new StdioServerTransport();
await server.connect(transport);
console.error("DAX Staff MCP Server v2 running on stdio");