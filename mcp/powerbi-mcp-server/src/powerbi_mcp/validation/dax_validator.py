"""DAX validation harness (validador unificado).

Consolida num só lugar as duas validações de DAX que existiam separadas:
o validador estrutural/semântico do MCP server (Python) e o linter de
anti-patterns que vivia no servidor TS `dax-staff-mcp`.

Valida DAX em 7 dimensões:
1. Syntax        — balanceamento estrutural (ignora literais de texto)
2. Semantic      — executa contra o modelo (slot XMLA; honesto quando ausente)
3. Performance   — custo estimado (heurística)
4. Scope         — referencia só tabelas/colunas permitidas
5. RLS           — não vaza dados com RLS ativa
6. Naming        — convenção de nomenclatura
7. Anti-pattern  — boas práticas (advisory, não bloqueia o veredicto)

Sintaxe e semântica "de verdade" dependem de um motor real (parser DAX e
engine Tabular via XMLA). Enquanto o motor não está plugado, as checagens
correspondentes são heurísticas e o relatório diz isso — não finge aprovar.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger()


class ValidationCheck(str, Enum):
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    PERFORMANCE = "performance"
    SCOPE = "scope"
    RLS = "rls"
    NAMING = "naming"
    ANTI_PATTERN = "anti_pattern"


# Dimensões que NÃO derrubam o veredicto: são conselhos de boas práticas,
# não erros de correção. Um DAX pode ser válido e ainda ter anti-patterns.
ADVISORY_CHECKS: frozenset[ValidationCheck] = frozenset({ValidationCheck.ANTI_PATTERN})

_CHECK_LABELS: dict[ValidationCheck, str] = {
    ValidationCheck.SYNTAX: "Sintaxe",
    ValidationCheck.SEMANTIC: "Semântica",
    ValidationCheck.PERFORMANCE: "Performance",
    ValidationCheck.SCOPE: "Escopo",
    ValidationCheck.RLS: "RLS",
    ValidationCheck.NAMING: "Nomenclatura",
    ValidationCheck.ANTI_PATTERN: "Boas práticas",
}

# Assinaturas dos motores reais plugáveis (o "slot" para quando destravar).
# syntax_engine:   dax -> lista de erros estruturais (vazia = ok)
# semantic_engine: dax -> (ok, row_count | None, erro | None)
SyntaxEngine = Callable[[str], Awaitable[list[str]]]
SemanticEngine = Callable[[str], Awaitable[tuple[bool, int | None, str | None]]]


@dataclass
class ValidationResult:
    """Result of DAX validation."""

    is_valid: bool
    checks: dict[ValidationCheck, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    estimated_cost_ms: float | None = None
    row_count: int | None = None
    measure_name: str | None = None
    score: str | None = None
    semantic_verified: bool = False

    def to_markdown(self) -> str:
        """Format as a human-readable Markdown report."""
        lines = ["## 🧪 Validação DAX", ""]

        if self.measure_name:
            lines.append(f"**Medida:** `{self.measure_name}`")
        if self.score:
            lines.append(f"**Score:** {self.score}")
        if self.measure_name or self.score:
            lines.append("")

        status_emoji = {True: "✅", False: "❌"}
        lines.append("| Check | Status |")
        lines.append("|---|---|")
        for check, passed in self.checks.items():
            label = _CHECK_LABELS.get(check, check.value.title())
            lines.append(f"| {label} | {status_emoji[passed]} |")

        if self.estimated_cost_ms is not None:
            lines.append("")
            lines.append(f"**Performance estimada:** {self.estimated_cost_ms:.0f}ms")

        if self.row_count is not None:
            lines.append(f"**Linhas retornadas:** {self.row_count}")

        lines.append("")
        if self.is_valid:
            lines.append("**Veredicto: ✅ APROVADO**")
        else:
            lines.append("**Veredicto: ❌ REPROVADO**")
            lines.append("")
            lines.append("**Erros:**")
            for err in self.errors:
                lines.append(f"- {err}")

        if self.warnings:
            lines.append("")
            lines.append("**Avisos:**")
            for warn in self.warnings:
                lines.append(f"- {warn}")

        if self.suggestions:
            lines.append("")
            lines.append("**Sugestões:**")
            for sug in self.suggestions:
                lines.append(f"- {sug}")

        if not self.semantic_verified:
            lines.append("")
            lines.append(
                "> ℹ️ Sintaxe/semântica em modo **heurístico** — sem parser DAX / motor "
                "XMLA conectado. Correção real fica a cargo do motor quando plugado."
            )

        return "\n".join(lines)


# Naming convention: Vendas.Receita Total BRL, Vendas.Margem %, etc.
NAMING_PATTERN = re.compile(
    r"^[A-Z][a-zA-ZçÇãÃéÉ]+"  # Domain (PascalCase, accents ok)
    r"\."  # dot separator
    r"[A-Za-zÀ-ÿ0-9 \[\]%/_-]+$"  # Description with allowed chars
)

_STRING_LITERAL = re.compile(r'"[^"]*"')


def matches_naming_convention(measure_name: str) -> bool:
    """Check if measure name follows the naming convention."""
    return bool(NAMING_PATTERN.match(measure_name))


def strip_string_literals(dax_code: str) -> str:
    """Substitui literais de texto ("...") por "" para não confundir a análise
    estrutural — parênteses/colchetes/barras dentro de strings não contam."""
    return _STRING_LITERAL.sub('""', dax_code)


def _is_balanced(code: str, open_ch: str, close_ch: str) -> bool:
    depth = 0
    for ch in code:
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def check_syntax_structure(dax_code: str) -> list[str]:
    """Erros estruturais duros (lista vazia = ok). Ignora literais de texto.

    Não é um parser — não pega coluna inexistente nem aridade de função. Pega
    o que dá pra pegar sem gramática: aspas/parênteses/colchetes desbalanceados.
    """
    errors: list[str] = []
    if dax_code.count('"') % 2 != 0:
        errors.append("Aspas desbalanceadas — literal de texto não fechado")
    clean = strip_string_literals(dax_code)
    if not _is_balanced(clean, "(", ")"):
        errors.append("Parênteses desbalanceados")
    if not _is_balanced(clean, "[", "]"):
        errors.append("Colchetes desbalanceados — referência de medida/coluna incompleta")
    return errors


def detect_anti_patterns(dax_code: str) -> tuple[list[str], list[str]]:
    """Linter de boas práticas por heurística (portado do dax-staff TS).

    Retorna (issues, suggestions). NÃO parseia a expressão — é um linter, não um
    compilador. Serve para ranquear qualidade, não para atestar correção.
    """
    clean = strip_string_literals(dax_code)
    issues: list[str] = []
    suggestions: list[str] = []

    if re.search(r"\bEARLIER\s*\(", clean, re.I):
        issues.append("EARLIER detectado — padrão legado difícil de ler e manter")
        suggestions.append(
            "Capture o valor da linha atual em VAR antes do FILTER e compare com a variável"
        )

    if re.search(r"\bSUMX\s*\(", clean, re.I) and "*" not in clean and "/" not in clean:
        issues.append("SUMX sem expressão aritmética — verifique se SUM simples resolve")
        suggestions.append(
            "SUMX só se justifica com cálculo linha a linha; para coluna única use SUM"
        )

    if re.search(r"\bCALCULATE\s*\([^)]*\bFILTER\s*\(", clean, re.I | re.S):
        issues.append("FILTER como argumento de filtro em CALCULATE")
        suggestions.append(
            "Prefira predicado booleano: CALCULATE([Medida], Tabela[Coluna] = valor) — "
            "o engine otimiza melhor"
        )

    if re.search(r"[^/]/[^/*]", clean) and not re.search(r"\bDIVIDE\s*\(", clean, re.I):
        issues.append("Divisão com operador '/' — risco de erro de divisão por zero")
        suggestions.append("Use DIVIDE(numerador, denominador [, alternativa])")

    if (
        re.search(r"\bALL\s*\(", clean, re.I)
        and re.search(r"\bFILTER\s*\(", clean, re.I)
        and not re.search(r"\bALLSELECTED\b", clean, re.I)
    ):
        suggestions.append(
            "FILTER(ALL(...)) ignora seleções do usuário — confirme se ALLSELECTED não "
            "seria o contexto correto"
        )

    if not re.search(r"\bVAR\b", clean, re.I) and len(dax_code) > 200:
        suggestions.append(
            "Medida longa sem VAR — variáveis melhoram legibilidade e evitam reavaliação"
        )

    return issues, suggestions


def compute_score(has_structural_errors: bool, issue_count: int) -> str:
    """Score A–F: F para erro estrutural; senão A/B/C pela qtd de anti-patterns."""
    if has_structural_errors:
        return "F"
    if issue_count == 0:
        return "A"
    if issue_count <= 2:
        return "B"
    return "C"


def estimate_query_cost(dax_code: str) -> float:
    """Estimate DAX query cost in milliseconds (heuristic)."""
    cost = 50.0  # base

    heavy_funcs = {
        "FILTER(": 200,
        "CALCULATETABLE(": 150,
        "ADDCOLUMNS(": 100,
        "SUMMARIZE(": 100,
        "GROUPBY(": 100,
        "TOPN(": 80,
        "CROSSJOIN(": 150,
        "UNION(": 80,
    }
    for func, penalty in heavy_funcs.items():
        cost += dax_code.count(func) * penalty

    # Iterators
    iterator_count = sum(1 for it in ["SUMX(", "AVERAGEX(", "COUNTX(", "MAXX("] if it in dax_code)
    cost += iterator_count * 50

    # Table references
    table_refs = len(set(re.findall(r"'([^']+)'", dax_code)))
    cost += table_refs * 20

    return cost


def extract_references(dax_code: str) -> set[str]:
    """Extract table and column references from DAX code."""
    # Table references in single quotes: 'table_name'
    tables = set(re.findall(r"'([^']+)'", dax_code))
    # Column references: [column] or table[column]
    columns = set(re.findall(r"\[([^\]]+)\]", dax_code))
    return tables | columns


def is_select_only_dax(dax_code: str) -> bool:
    """Check if DAX is a SELECT-only query (no side effects)."""
    forbidden = ["CREATE", "ALTER", "DELETE", "DROP", "INSERT", "UPDATE", "TRUNCATE"]
    upper = dax_code.upper()
    return not any(f" {kw} " in upper or upper.startswith(kw) for kw in forbidden)


class DAXValidator:
    """Validador unificado de DAX gerado por IA.

    Motores reais são plugáveis: passe ``syntax_engine`` (parser DAX) e/ou
    ``semantic_engine`` (execução XMLA/Tabular). Sem eles, sintaxe cai para
    heurística estrutural e semântica NÃO é atestada (fica marcada como não
    verificada, sem falso-positivo verde).
    """

    def __init__(
        self,
        max_cost_ms: float = 5000.0,
        allowed_symbols: set[str] | None = None,
        *,
        syntax_engine: SyntaxEngine | None = None,
        semantic_engine: SemanticEngine | None = None,
    ):
        self.max_cost_ms = max_cost_ms
        self.allowed_symbols = allowed_symbols or set()
        self.syntax_engine = syntax_engine
        self.semantic_engine = semantic_engine

    async def validate(
        self,
        dax_code: str,
        *,
        syntax_check: bool = True,
        semantic_check: bool = True,
        measure_name: str | None = None,
        rls_test_callback=None,
    ) -> ValidationResult:
        """Run all validation checks and return a comprehensive result."""
        result = ValidationResult(is_valid=True, measure_name=measure_name)
        structural_errors = False

        # 1. Syntax — motor real se plugado; senão heurística estrutural.
        if syntax_check:
            if self.syntax_engine is not None:
                syntax_errors = await self.syntax_engine(dax_code)
            else:
                syntax_errors = check_syntax_structure(dax_code)
            result.checks[ValidationCheck.SYNTAX] = not syntax_errors
            if syntax_errors:
                structural_errors = True
                result.errors.extend(f"Sintaxe: {e}" for e in syntax_errors)

        # 2. Semantic — só com motor real; sem ele, não finge aprovar.
        syntax_ok = result.checks.get(ValidationCheck.SYNTAX, True)
        if semantic_check and syntax_ok:
            if self.semantic_engine is not None:
                ok, row_count, err = await self.semantic_engine(dax_code)
                result.checks[ValidationCheck.SEMANTIC] = ok
                result.row_count = row_count
                result.semantic_verified = True
                if not ok:
                    result.errors.append(f"Semântica: {err or 'query rejeitada pelo modelo'}")
            else:
                result.warnings.append(
                    "Semântica não verificada — sem motor XMLA conectado"
                )

        # 3. Performance estimate
        cost = estimate_query_cost(dax_code)
        result.estimated_cost_ms = cost
        result.checks[ValidationCheck.PERFORMANCE] = cost < self.max_cost_ms
        if not result.checks[ValidationCheck.PERFORMANCE]:
            result.errors.append(f"Performance: {cost:.0f}ms > {self.max_cost_ms:.0f}ms")

        # 4. Scope check
        if self.allowed_symbols:
            refs = extract_references(dax_code)
            forbidden = refs - self.allowed_symbols
            # Medidas vivem num namespace global e não são checadas contra os
            # símbolos de tabela/coluna. Elas seguem a convenção 'Domínio.Nome'
            # (contêm ponto); tabelas e colunas não. Referências que casam com a
            # convenção de medida são, portanto, ignoradas no scope check.
            forbidden = {r for r in forbidden if not matches_naming_convention(r)}
            result.checks[ValidationCheck.SCOPE] = len(forbidden) == 0
            if forbidden:
                result.errors.append(f"Escopo: refs não permitidas: {forbidden}")
        else:
            result.checks[ValidationCheck.SCOPE] = True

        # 5. RLS check (if callback provided)
        if rls_test_callback:
            try:
                rls_safe = await rls_test_callback(dax_code)
                result.checks[ValidationCheck.RLS] = rls_safe
                if not rls_safe:
                    result.errors.append("RLS: query pode vazar dados entre roles")
            except Exception as e:
                result.checks[ValidationCheck.RLS] = False
                result.errors.append(f"RLS check falhou: {e}")
        else:
            result.checks[ValidationCheck.RLS] = True

        # 6. Naming convention
        if measure_name:
            result.checks[ValidationCheck.NAMING] = matches_naming_convention(measure_name)
            if not result.checks[ValidationCheck.NAMING]:
                result.errors.append(
                    f"Naming: '{measure_name}' não segue convenção "
                    "(formato: 'Dominio.Nome Medida [formato]')"
                )

        # 7. Anti-patterns (advisory — enriquece, não bloqueia o veredicto)
        issues, suggestions = detect_anti_patterns(dax_code)
        result.warnings.extend(issues)
        result.suggestions.extend(suggestions)
        result.checks[ValidationCheck.ANTI_PATTERN] = len(issues) == 0

        # Score A–F (mesma escala do dax-staff)
        result.score = compute_score(structural_errors, len(issues))

        # Veredicto: só as dimensões bloqueantes contam (advisory de fora).
        blocking = {k: v for k, v in result.checks.items() if k not in ADVISORY_CHECKS}
        result.is_valid = all(blocking.values()) if blocking else False

        logger.info(
            "dax_validated",
            is_valid=result.is_valid,
            score=result.score,
            measure=measure_name,
            semantic_verified=result.semantic_verified,
            checks_passed=sum(1 for v in blocking.values() if v),
            checks_total=len(blocking),
            anti_patterns=len(issues),
        )

        return result