#!/usr/bin/env python3
"""
Auditoria universal de pasta TMDL (PBIP /definition ou saída do TmdlSerializer).

Parsing por indentação — sem AMO/TOM, sem .NET, sem Power BI instalado. Roda em qualquer SO
e em CI. Nenhuma regra de negócio vive neste arquivo: elas são carregadas de rules.json, e o
que varia por projeto (tokens de idioma, prefixos, regras desativadas) vem de
tmdl.conventions.json. O mesmo binário audita qualquer modelo, de qualquer empresa.

Uso:
    python tmdl_audit.py <pasta-tmdl> [--regras rules.json] [--convencoes conv.json]
                         [--formato md|json] [--saida arquivo] [--falhar-em alta]

Exemplos:
    python tmdl_audit.py ./Vendas.SemanticModel/definition
    python tmdl_audit.py ./definition --formato json --saida audit.json
    python tmdl_audit.py ./definition --falhar-em alta       # uso em pipeline
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

TAB_WIDTH = 4

# Tipos de objeto reconhecidos como declaração (camelCase, case-insensitive na leitura).
OBJECT_KEYWORDS = {
    "database", "model", "table", "column", "measure", "partition", "hierarchy",
    "level", "relationship", "role", "tablepermission", "columnpermission",
    "perspective", "perspectivetable", "perspectivemeasure", "perspectivecolumn",
    "perspectivehierarchy", "culture", "cultureinfo", "expression", "function",
    "datasource", "querygroup", "annotation", "extendedproperty", "calculationgroup",
    "calculationitem", "kpi", "refreshpolicy", "detailrowsdefinition",
    "formatstringdefinition", "calculationgroupexpression", "variation",
    "changedproperty", "linguisticmetadata", "objecttranslation", "rolemembership",
    "datacoveragedefinition", "alternateof", "ref",
}

DECL_RE = re.compile(r"^(?P<kw>[A-Za-z]+)\s+(?P<rest>.*)$")
PROP_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*:\s*(?P<value>.*)$")
BOOL_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*$")

CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def tokens_do_nome(nome: str):
    """Tokens de um nome, quebrando por separadores e camelCase."""
    partes = re.split(r"[\s_\-\.]+", nome)
    saida = []
    for parte in partes:
        saida.extend(t for t in CAMEL_RE.split(parte) if t)
    return [t.lower() for t in saida]


class Node:
    __slots__ = ("kind", "name", "expr", "props", "children", "description", "file", "line")

    def __init__(self, kind, name, expr=None, description=None, file=None, line=0):
        self.kind = kind
        self.name = name
        self.expr = expr
        self.props = {}
        self.children = []
        self.description = description
        self.file = file
        self.line = line

    def prop(self, key, default=None):
        return self.props.get(key.lower(), default)

    def kids(self, kind):
        return [c for c in self.children if c.kind == kind]


def acumula(node, key, texto):
    """Acrescenta uma linha à expressão do nó (propriedade padrão ou propriedade nomeada)."""
    if key is None:
        node.expr = (node.expr or "") + texto + "\n"
    else:
        node.props[key] = (node.props.get(key) or "") + texto + "\n"


def indent_of(line: str) -> int:
    expanded = line.expandtabs(TAB_WIDTH)
    return len(expanded) - len(expanded.lstrip(" "))


def strip_quotes(name: str) -> str:
    name = name.strip()
    if len(name) >= 2 and name[0] == "'" and name.endswith("'"):
        return name[1:-1].replace("''", "'")
    return name


def parse_file(path: str, rel: str):
    """Devolve a lista de nós de nível raiz do documento."""
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()

    roots = []
    stack = []  # lista de (indent, Node)
    pending_desc = []
    in_fence = False
    fence_owner = None
    fence_key = None
    expr_owner = None
    expr_indent = None
    expr_key = None

    for lineno, raw in enumerate(lines, 1):
        if in_fence:
            if raw.strip() == "```":
                in_fence = False
                fence_owner = None
                fence_key = None
            elif fence_owner is not None:
                acumula(fence_owner, fence_key, raw.strip())
            continue

        if not raw.strip():
            if expr_owner is not None:
                acumula(expr_owner, expr_key, "")
            continue

        ind = indent_of(raw)
        body = raw.strip()

        # Corpo de expressão multilinha em andamento.
        if expr_owner is not None:
            if ind > expr_indent:
                acumula(expr_owner, expr_key, body)
                continue
            expr_owner = None
            expr_indent = None
            expr_key = None

        if body.startswith("///"):
            pending_desc.append(body[3:].strip())
            continue

        # Comando de script (createOrReplace etc.) — registrado como nó especial.
        if ind == 0 and body.lower() in ("createorreplace", "create", "delete", "alter"):
            node = Node("command", body, file=rel, line=lineno)
            roots.append(node)
            stack = [(0, node)]
            pending_desc = []
            continue

        node = None
        prop_hit = False

        m = DECL_RE.match(body)
        if m and m.group("kw").lower() in OBJECT_KEYWORDS:
            kw = m.group("kw").lower()
            rest = m.group("rest")
            is_ref = kw == "ref"
            if is_ref:
                # `ref table X` — o tipo real é o segundo token.
                m2 = DECL_RE.match(rest)
                if not m2:
                    continue
                kw = m2.group("kw").lower()
                rest = m2.group("rest")

            expr = None
            name = rest
            if "=" in rest:
                # Separa nome de propriedade padrão, respeitando aspas simples no nome.
                idx = find_top_level_eq(rest)
                if idx is not None:
                    name = rest[:idx].strip()
                    expr = rest[idx + 1:].strip()
            node = Node(kw, strip_quotes(name), expr=expr,
                        description=" ".join(pending_desc) or None,
                        file=rel, line=lineno)
            node.props["_isref"] = is_ref
            pending_desc = []
        elif body.lower() in ("ref",):
            continue
        else:
            # Propriedade do nó corrente.
            parent = stack[-1][1] if stack else None
            pm = PROP_RE.match(body)
            if pm and parent is not None:
                parent.props[pm.group("name").lower()] = pm.group("value").strip()
                prop_hit = True
                if pm.group("value").strip() == "" and pm.group("name").lower() in (
                    "source", "expression", "query", "content", "filterexpression",
                ):
                    expr_owner = parent
                    expr_indent = ind
                    expr_key = pm.group("name").lower()
                continue
            bm = BOOL_RE.match(body)
            if bm and parent is not None:
                parent.props[bm.group("name").lower()] = "true"
                prop_hit = True
                continue
            # Linha de propriedade com "=" (ex.: `source =`)
            if "=" in body and parent is not None:
                key, _, val = body.partition("=")
                key = key.strip().lower()
                val = val.strip()
                parent.props[key] = val
                if val in ("", "```"):
                    parent.props[key] = ""
                    if val == "```":
                        in_fence = True
                        fence_owner = parent
                        fence_key = key
                    else:
                        expr_owner = parent
                        expr_indent = ind
                        expr_key = key
                continue

        if node is None:
            continue

        while stack and stack[-1][0] >= ind:
            stack.pop()

        if stack:
            stack[-1][1].children.append(node)
        else:
            roots.append(node)

        stack.append((ind, node))

        # Expressão multilinha declarada na própria linha do objeto.
        if node.expr == "":
            expr_owner = node
            expr_indent = ind
            expr_key = None
        elif node.expr == "```":
            in_fence = True
            fence_owner = node
            fence_key = None
            node.expr = ""

    return roots


def find_top_level_eq(text: str):
    """Índice do primeiro '=' fora de aspas simples."""
    in_quote = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "'":
            if in_quote and i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            in_quote = not in_quote
        elif ch == "=" and not in_quote:
            return i
        i += 1
    return None


def collect(folder: str):
    docs = {}
    for root, _dirs, files in os.walk(folder):
        for fn in sorted(files):
            if not fn.lower().endswith(".tmdl"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, folder)
            try:
                docs[rel] = parse_file(full, rel)
            except Exception as exc:  # parsing best-effort
                docs[rel] = []
                print(f"[aviso] falha ao ler {rel}: {exc}", file=sys.stderr)
    return docs


def dedupe(nodes):
    """Mantém a definição mais completa de cada nome (descarta `ref` sem corpo)."""
    melhor = {}
    for n in nodes:
        atual = melhor.get(n.name)
        if atual is None or len(n.children) > len(atual.children) or (
            len(n.children) == len(atual.children) and len(n.props) > len(atual.props)
        ):
            melhor[n.name] = n
    return list(melhor.values())


def flatten(nodes, kind, out=None):
    if out is None:
        out = []
    for n in nodes:
        if n.kind == kind:
            out.append(n)
        flatten(n.children, kind, out)
    return out


def is_true(val):
    return str(val).strip().lower() in ("true", "1")



# ============================================================
#  Motor de regras — dirigido por rules.json + conventions.json.
#  Nenhuma regra de negócio mora neste arquivo.
# ============================================================

SEVERIDADES = {"baixa": 1, "media": 2, "alta": 3}

CONVENCOES_PADRAO = {
    "idioma": None,
    "tokens": {
        "chave": ["key", "keys", "sk", "id", "ids", "chave", "codigo", "código", "cod"],
        "data": ["data", "date", "dt", "dia", "mes", "mês", "ano"],
    },
    "nomenclatura": {},
    "modelo": {},
    "auditoria": {"regrasDesativadas": {}, "severidadeMinima": "baixa"},
}


def carregar_json(caminho, padrao=None):
    if not caminho or not os.path.isfile(caminho):
        return padrao
    with open(caminho, "r", encoding="utf-8") as fh:
        return json.load(fh)


def merge_convencoes(user):
    conv = json.loads(json.dumps(CONVENCOES_PADRAO))
    if not user:
        return conv
    for chave, valor in user.items():
        if chave.startswith("$"):
            continue
        if isinstance(valor, dict) and isinstance(conv.get(chave), dict):
            conv[chave].update({k: v for k, v in valor.items() if not k.startswith("$")})
        else:
            conv[chave] = valor
    return conv


class Alvo:
    """Um objeto do modelo pronto para ser avaliado por uma regra."""

    __slots__ = ("node", "kind", "pai", "rotulo", "contexto")

    def __init__(self, node, kind, pai=None, contexto=None):
        self.node = node
        self.kind = kind
        self.pai = pai
        self.contexto = contexto or {}
        if pai is not None:
            self.rotulo = f"{pai.name}[{node.name}]"
        else:
            self.rotulo = node.name


def resolver_tokens(valor, conv):
    """'@chave' vira a lista configurada; lista literal passa direto."""
    if isinstance(valor, str) and valor.startswith("@"):
        return [t.lower() for t in conv.get("tokens", {}).get(valor[1:], [])]
    if isinstance(valor, str):
        return [valor.lower()]
    return [str(v).lower() for v in valor]


def avaliar(cond, alvo, conv, indice):
    """Avalia um predicado declarativo. Devolve bool."""
    node = alvo.node

    if "e" in cond:
        return all(avaliar(c, alvo, conv, indice) for c in cond["e"])
    if "ou" in cond:
        return any(avaliar(c, alvo, conv, indice) for c in cond["ou"])
    if "nao" in cond:
        return not avaliar(cond["nao"], alvo, conv, indice)

    if "faltaPropriedade" in cond:
        return not any(node.prop(p) for p in cond["faltaPropriedade"])

    if "temPropriedade" in cond:
        return all(node.prop(p) is not None for p in cond["temPropriedade"])

    if "propriedadeIgual" in cond:
        return all(
            (node.prop(k) or "").strip().lower() == str(v).strip().lower()
            for k, v in cond["propriedadeIgual"].items()
        )

    if "propriedadeDiferente" in cond:
        # ausente conta como diferente
        return all(
            (node.prop(k) or "").strip().lower() != str(v).strip().lower()
            for k, v in cond["propriedadeDiferente"].items()
        )

    if "propriedadePresenteEDiferente" in cond:
        for k, v in cond["propriedadePresenteEDiferente"].items():
            atual = node.prop(k)
            if atual is None:
                return False
            if atual.strip().lower() == str(v).strip().lower():
                return False
        return True

    if "propriedadeEm" in cond:
        for k, valores in cond["propriedadeEm"].items():
            atual = (node.prop(k) or "").strip().lower()
            if atual not in [str(x).lower() for x in valores]:
                return False
        return True

    if "nomeContemToken" in cond:
        tokens = set(resolver_tokens(cond["nomeContemToken"], conv))
        return any(t in tokens for t in tokens_do_nome(node.name))

    if "nomeCasaRegex" in cond:
        return re.search(cond["nomeCasaRegex"], node.name) is not None

    if "nomeComecaCom" in cond:
        prefixos = resolver_tokens(cond["nomeComecaCom"], conv)
        low = node.name.lower()
        return any(low.startswith(p) for p in prefixos)

    if "semDescricao" in cond:
        return (not node.description) == bool(cond["semDescricao"])

    if "temExpressao" in cond:
        return bool(node.expr and node.expr.strip()) == bool(cond["temExpressao"])

    if "expressaoContem" in cond:
        alvo_txt = (node.expr or "").upper()
        return any(str(s).upper() in alvo_txt for s in cond["expressaoContem"])

    if "expressaoLinhasMaiorQue" in cond:
        return len((node.expr or "").splitlines()) > int(cond["expressaoLinhasMaiorQue"])

    if "semFilhos" in cond:
        tipos = str(cond["semFilhos"]).lower().split("|")
        return not any(node.kids(t) for t in tipos)

    if "temFilhos" in cond:
        tipos = str(cond["temFilhos"]).lower().split("|")
        return any(node.kids(t) for t in tipos)

    if "naoRelacionada" in cond:
        relacionada = node.name in indice["tabelas_relacionadas"] or bool(
            node.kids("calculationgroup")
        )
        return (not relacionada) == bool(cond["naoRelacionada"])

    if "nomeDuplicadoNoModelo" in cond:
        dup = indice["contagem_nomes"].get((alvo.kind, node.name), 0) > 1
        return dup == bool(cond["nomeDuplicadoNoModelo"])

    if "contagemFilhosMaiorQue" in cond:
        tipo, limite = cond["contagemFilhosMaiorQue"]
        return len(node.kids(str(tipo).lower())) > int(limite)

    raise ValueError(f"predicado desconhecido: {list(cond)}")


def coletar_alvos(docs):
    """Achata o modelo em alvos avaliáveis + índices auxiliares."""
    all_roots = [n for nodes in docs.values() for n in nodes]

    databases = flatten(all_roots, "database")
    models = flatten(all_roots, "model")
    tables = dedupe(flatten(all_roots, "table"))
    relationships = flatten(all_roots, "relationship")
    roles = dedupe(flatten(all_roots, "role"))
    perspectives = dedupe(flatten(all_roots, "perspective"))
    cultures = dedupe(flatten(all_roots, "culture") + flatten(all_roots, "cultureinfo"))
    expressions = flatten(all_roots, "expression")
    calc_groups = flatten(all_roots, "calculationgroup")

    alvos = []
    columns, measures, partitions, hierarchies = [], [], [], []

    for db in databases:
        alvos.append(Alvo(db, "database"))
    for m in models:
        alvos.append(Alvo(m, "model"))

    for t in tables:
        alvos.append(Alvo(t, "table"))
        for c in t.kids("column"):
            columns.append((t, c))
            alvos.append(Alvo(c, "column", pai=t))
        for m in t.kids("measure"):
            measures.append((t, m))
            alvos.append(Alvo(m, "measure", pai=t))
        for p in t.kids("partition"):
            partitions.append((t, p))
            alvos.append(Alvo(p, "partition", pai=t))
        for h in t.kids("hierarchy"):
            hierarchies.append((t, h))
            alvos.append(Alvo(h, "hierarchy", pai=t))

    for r in relationships:
        alvos.append(Alvo(r, "relationship"))
    for r in roles:
        alvos.append(Alvo(r, "role"))
    for p in perspectives:
        alvos.append(Alvo(p, "perspective"))
    for c in cultures:
        alvos.append(Alvo(c, "culture"))
    for e in expressions:
        alvos.append(Alvo(e, "expression"))

    tabelas_relacionadas = set()
    for r in relationships:
        for ref in (r.prop("fromcolumn", ""), r.prop("tocolumn", "")):
            if "." in ref:
                tabelas_relacionadas.add(strip_quotes(ref.split(".", 1)[0]))

    contagem_nomes = Counter((a.kind, a.node.name) for a in alvos)

    indice = {
        "tabelas_relacionadas": tabelas_relacionadas,
        "contagem_nomes": contagem_nomes,
    }

    inventario = {
        "database": databases[0].name if databases else None,
        "compatibilityLevel": databases[0].prop("compatibilitylevel") if databases else None,
        "culture": models[0].prop("culture") if models else None,
        "tabelas": len(tables),
        "tabelas_ocultas": sum(1 for t in tables if is_true(t.prop("ishidden"))),
        "colunas": len(columns),
        "colunas_ocultas": sum(1 for _t, c in columns if is_true(c.prop("ishidden"))),
        "colunas_calculadas": sum(1 for _t, c in columns if c.expr),
        "medidas": len(measures),
        "relacionamentos": len(relationships),
        "hierarquias": len(hierarchies),
        "particoes": len(partitions),
        "modos_de_particao": dict(
            Counter((p.prop("mode") or "?").strip().lower() for _t, p in partitions)
        ),
        "roles": len(roles),
        "perspectivas": len(perspectives),
        "culturas": len(cultures),
        "expressoes_compartilhadas": len(expressions),
        "grupos_de_calculo": len(calc_groups),
        "arquivos_tmdl": len(docs),
    }

    detalhe_tabelas = [
        {
            "tabela": t.name,
            "descricao": t.description,
            "oculta": is_true(t.prop("ishidden")),
            "colunas": len(t.kids("column")),
            "medidas": len(t.kids("measure")),
            "hierarquias": len(t.kids("hierarchy")),
            "particoes": [(p.name, p.prop("mode") or "?") for p in t.kids("partition")],
            "arquivo": t.file,
        }
        for t in sorted(tables, key=lambda x: x.name.lower())
    ]

    return alvos, indice, inventario, detalhe_tabelas


def executar_regras(alvos, indice, regras, conv):
    desativadas = conv.get("auditoria", {}).get("regrasDesativadas", {}) or {}
    minima = SEVERIDADES.get(conv.get("auditoria", {}).get("severidadeMinima", "baixa"), 1)

    achados = []
    for regra in regras:
        rid = regra.get("id")
        if rid in desativadas:
            continue
        sev = regra.get("severidade", "baixa")
        if SEVERIDADES.get(sev, 1) < minima:
            continue

        escopo = regra.get("escopo", "").lower()
        cond = regra.get("quando")
        if not cond:
            continue

        itens = []
        for alvo in alvos:
            if alvo.kind != escopo:
                continue
            try:
                if avaliar(cond, alvo, conv, indice):
                    itens.append(alvo.rotulo)
            except ValueError as exc:
                print(f"[aviso] regra '{rid}': {exc}", file=sys.stderr)
                break

        if itens:
            achados.append(
                {
                    "id": rid,
                    "titulo": regra.get("titulo", rid),
                    "severidade": sev,
                    "porque": regra.get("porque"),
                    "correcao": regra.get("correcao"),
                    "quantidade": len(itens),
                    "itens": itens,
                }
            )

    ordem_sev = {"alta": 0, "media": 1, "baixa": 2}
    achados.sort(key=lambda a: (ordem_sev.get(a["severidade"], 9), -a["quantidade"]))
    return achados


def render_md(inventario, tabelas, achados, conv, limite=25):
    out = ["# Auditoria do modelo semântico", ""]

    total = sum(a["quantidade"] for a in achados)
    altas = sum(a["quantidade"] for a in achados if a["severidade"] == "alta")
    out.append(f"{total} ocorrências em {len(achados)} regras — {altas} de severidade alta.")
    out.append("")

    out.append("## Inventário")
    out.append("")
    out.append("| Item | Valor |")
    out.append("| --- | --- |")
    for k, v in inventario.items():
        if isinstance(v, dict):
            v = ", ".join(f"{kk}: {vv}" for kk, vv in sorted(v.items())) or "—"
        out.append(f"| {k} | {v if v is not None else '—'} |")
    out.append("")

    out.append("## Tabelas")
    out.append("")
    out.append("| Tabela | Oculta | Colunas | Medidas | Hierarquias | Partições | Descrição |")
    out.append("| --- | --- | --- | --- | --- | --- | --- |")
    for t in tabelas:
        parts = ", ".join(f"{n} ({m})" for n, m in t["particoes"]) or "—"
        desc = (t["descricao"] or "—").replace("|", "\\|")
        if len(desc) > 60:
            desc = desc[:57] + "..."
        out.append(
            f"| {t['tabela']} | {'sim' if t['oculta'] else 'não'} | {t['colunas']} | "
            f"{t['medidas']} | {t['hierarquias']} | {parts} | {desc} |"
        )
    out.append("")

    out.append("## Achados")
    out.append("")
    if not achados:
        out.append("Nenhuma regra do conjunto ativo foi violada.")
    for a in achados:
        out.append(f"### [{a['severidade']}] {a['titulo']} ({a['quantidade']})")
        out.append("")
        if a.get("porque"):
            out.append(f"_{a['porque']}_")
            out.append("")
        for item in a["itens"][:limite]:
            out.append(f"- {item}")
        if a["quantidade"] > limite:
            out.append(f"- _(+{a['quantidade'] - limite} não listados)_")
        if a.get("correcao"):
            out.append("")
            out.append(f"**Correção:** {a['correcao']}")
        out.append("")

    desativadas = conv.get("auditoria", {}).get("regrasDesativadas", {}) or {}
    if desativadas:
        out.append("## Regras desativadas neste projeto")
        out.append("")
        for rid, motivo in desativadas.items():
            out.append(f"- `{rid}` — {motivo}")
        out.append("")

    return "\n".join(out)


def main():
    aqui = os.path.dirname(os.path.abspath(__file__))
    rules_padrao = os.path.join(aqui, "..", "assets", "rules.json")

    ap = argparse.ArgumentParser(
        description="Auditoria universal de pasta TMDL, dirigida por regras em JSON."
    )
    ap.add_argument("pasta", help="Caminho da pasta TMDL (ex.: .../definition)")
    ap.add_argument("--regras", default=rules_padrao,
                    help="rules.json (padrão: assets/rules.json da skill)")
    ap.add_argument("--convencoes", default=None,
                    help="tmdl.conventions.json do projeto (padrão: procura na pasta e acima)")
    ap.add_argument("--formato", choices=["md", "json"], default="md")
    ap.add_argument("--saida", help="Arquivo de saída (padrão: stdout)")
    ap.add_argument("--limite", type=int, default=25,
                    help="Máximo de itens listados por achado no formato md")
    ap.add_argument("--falhar-em", choices=["alta", "media", "baixa"], default=None,
                    help="Retorna código 1 se houver achado nesta severidade ou acima (uso em CI)")
    args = ap.parse_args()

    if not os.path.isdir(args.pasta):
        print(f"Pasta não encontrada: {args.pasta}", file=sys.stderr)
        return 2

    regras_doc = carregar_json(args.regras)
    if not regras_doc:
        print(f"Conjunto de regras não encontrado: {args.regras}", file=sys.stderr)
        return 2
    regras = regras_doc.get("rules", [])

    caminho_conv = args.convencoes
    if not caminho_conv:
        for candidato in (
            os.path.join(args.pasta, "tmdl.conventions.json"),
            os.path.join(args.pasta, "..", "tmdl.conventions.json"),
            os.path.join(args.pasta, "..", "..", "tmdl.conventions.json"),
        ):
            if os.path.isfile(candidato):
                caminho_conv = candidato
                break
    conv = merge_convencoes(carregar_json(caminho_conv))

    docs = collect(args.pasta)
    if not docs:
        print(f"Nenhum arquivo .tmdl encontrado em {args.pasta}", file=sys.stderr)
        return 2

    alvos, indice, inventario, tabelas = coletar_alvos(docs)
    achados = executar_regras(alvos, indice, regras, conv)

    if args.formato == "json":
        texto = json.dumps(
            {
                "inventario": inventario,
                "tabelas": tabelas,
                "achados": achados,
                "convencoes": caminho_conv,
                "regras": args.regras,
            },
            ensure_ascii=False,
            indent=2,
        )
    else:
        texto = render_md(inventario, tabelas, achados, conv, limite=args.limite)

    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as fh:
            fh.write(texto + "\n")
        print(f"Escrito em {args.saida}")
    else:
        print(texto)

    if args.falhar_em:
        piso = SEVERIDADES[args.falhar_em]
        if any(SEVERIDADES.get(a["severidade"], 1) >= piso for a in achados):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
