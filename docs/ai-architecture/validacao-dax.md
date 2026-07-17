# ✅ Validação de DAX Gerado por AI

> AI vai escrever DAX errado. Esta é uma lei da natureza. Este documento
> especifica o harness de validação que roda antes de aceitar qualquer DAX
> vindo do AI.

## 1. Princípio

**Defesa em profundidade na validação.** 6 camadas. Cada uma pega uma classe diferente de erro. Erro passa por uma? A próxima pega.

```
Sintaxe → Semântica → Performance → Escopo → RLS → Naming
   ↓          ↓           ↓           ↓       ↓      ↓
 rejeita se  rejeita se  rejeita se  rejeita se  rejeita se  rejeita se
 erro de     resultado   custo       referencia  vaza dados  não segue
 parse       inesperado  estimado    tabela      com RLS     convenção
             ou nulo     > X ms      fora do
                                     permitido
```

## 2. Implementação

```python
# powerbi_mcp/guardrails/validation.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class ValidationError(str, Enum):
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    PERFORMANCE = "performance"
    SCOPE = "scope"
    RLS = "rls"
    NAMING = "naming"

@dataclass
class ValidationResult:
    is_valid: bool
    checks: dict[str, bool]
    errors: list[str]
    warnings: list[str]
    estimated_cost_ms: Optional[float] = None
    row_count: Optional[int] = None

def validate_ai_dax(
    dax_code: str,
    dataset: "Dataset",
    user: "UserContext",
    *,
    role_to_test: Optional[str] = None,
) -> ValidationResult:
    checks = {}
    errors = []
    warnings = []
    
    # 1. Sintaxe
    try:
        compile_check = pbi_tools.compile_check(dax_code, dataset.workspace_id)
        checks["syntax"] = compile_check.ok
        if not compile_check.ok:
            errors.append(f"Sintaxe: {compile_check.error}")
    except Exception as e:
        checks["syntax"] = False
        errors.append(f"Sintaxe (exceção): {e}")
    
    if not checks["syntax"]:
        return ValidationResult(False, checks, errors, warnings)
    
    # 2. Semântica (executa em sandbox)
    try:
        result = dataset.query_dax(dax_code, sandbox=True)
        checks["semantic"] = result.has_data or result.is_empty_expected
        if result.error:
            errors.append(f"Semântica: {result.error}")
            checks["semantic"] = False
        row_count = result.row_count
    except Exception as e:
        checks["semantic"] = False
        errors.append(f"Semântica (exceção): {e}")
    
    # 3. Performance
    cost = estimate_query_cost(dax_code, dataset)
    checks["performance"] = cost < MAX_COST_MS  # ex: 5000ms
    if not checks["performance"]:
        errors.append(f"Performance: {cost:.0f}ms > {MAX_COST_MS}ms")
    
    # 4. Escopo — não referencia tabelas/colunas que o user não tem acesso
    refs = extract_references(dax_code)
    allowed = user.allowed_symbols(dataset)
    forbidden = refs - allowed
    checks["scope"] = len(forbidden) == 0
    if forbidden:
        errors.append(f"Escopo: referências não permitidas: {forbidden}")
    
    # 5. RLS — testa com role do user
    if role_to_test:
        result_with_rls = dataset.query_dax(
            dax_code,
            effective_username=user.email,
            roles=[role_to_test],
            sandbox=True,
        )
        # Compara com resultado sem RLS
        if not result_with_rls.is_subset_of(result):
            checks["rls"] = False
            errors.append(f"RLS: query retorna dados diferentes com RLS — possível leak")
        else:
            checks["rls"] = True
    
    # 6. Naming
    if "create measure" in dax_code.intent:
        measure_name = extract_measure_name(dax_code)
        checks["naming"] = matches_naming_convention(measure_name)
        if not checks["naming"]:
            errors.append(f"Naming: '{measure_name}' não segue convenção")
    
    return ValidationResult(
        is_valid=all(checks.values()),
        checks=checks,
        errors=errors,
        warnings=warnings,
        estimated_cost_ms=cost,
        row_count=row_count,
    )
```

## 3. Estimativa de custo de query

```python
def estimate_query_cost(dax: str, dataset: "Dataset") -> float:
    """
    Estima tempo de execução em ms sem executar a query.
    Baseado em heurísticas de complexidade DAX.
    """
    cost = 50.0  # base
    
    # Funções pesadas
    heavy_funcs = {
        "FILTER(": 200,
        "CALCULATETABLE(": 150,
        "ADDCOLUMNS(": 100,
        "SUMMARIZE(": 100,
        "GROUPBY(": 100,
        "TOPN(": 80,
    }
    for func, penalty in heavy_funcs.items():
        cost += dax.count(func) * penalty
    
    # Iteradores
    iterator_count = sum(1 for it in ["SUMX(", "AVERAGEX(", "COUNTX(", "MAXX("] if it in dax)
    cost += iterator_count * 50
    
    # Joins implícitos (USERELATIONSHIP ou múltiplas tabelas)
    table_refs = len(extract_references(dax))
    cost += table_refs * 20
    
    # Tamanho das tabelas envolvidas
    for ref in extract_references(dax):
        if ref in dataset.table_sizes:
            size_factor = min(dataset.table_sizes[ref] / 1_000_000, 10)
            cost += size_factor * 100
    
    return cost
```

## 4. Sandbox de execução

**Importante:** validação roda em workspace sandbox (AI-Playground), nunca em Dev/Test/Prod.

```python
@dataclass
class SandboxConfig:
    workspace_id: str  # AI-Playground
    dataset_id: str    # cópia do dataset de Prod
    timeout_seconds: int = 30
    max_rows: int = 10_000
    memory_limit_mb: int = 1024
    cpu_quota: float = 0.5

def run_in_sandbox(dax: str, config: SandboxConfig) -> QueryResult:
    """
    Executa DAX em workspace isolado com quotas estritas.
    """
    # Garante que sandbox está configurado
    if not is_sandbox(config.workspace_id):
        raise SecurityError(f"{config.workspace_id} não é sandbox")
    
    # Executa via XMLA com roles e effective username
    return xmla.execute_with_context(
        workspace_id=config.workspace_id,
        dataset_id=config.dataset_id,
        dax=dax,
        effective_username="ai-sandbox",
        roles=["Reader"],
        timeout=config.timeout_seconds,
        max_rows=config.max_rows,
    )
```

## 5. Relatório de validação

**Output mostrado pro dev (e pro AI):**

```markdown
## 🧪 Validação: Vendas.Ticket Médio [R$]

| Check | Status | Detalhe |
|---|---|---|
| ✅ Sintaxe | OK | Compila sem erros |
| ✅ Semântica | OK | Retorna 1234567.89 (1 row) |
| ⚠️ Performance | WARN | Estimativa: 320ms (limite 5000ms) |
| ✅ Escopo | OK | Refs: [Vendas.Receita Total BRL, f_vendas__pedido[pedido_id]] — todas permitidas |
| ✅ RLS | OK | Com role Vendedor, retorna apenas dados do próprio usuário |
| ✅ Naming | OK | "Vendas.Ticket Médio [R$]" segue convenção |

**Veredicto: ✅ APROVADO**

Dica: a medida referencia DISTINCTCOUNT — considere pré-calcular se a tabela f_vendas__pedido crescer muito.
```

## 6. Auto-correção

**Se validação falha, AI pode tentar corrigir (até N vezes):**

```python
def validate_with_retry(dax, dataset, user, max_retries=3):
    for attempt in range(max_retries):
        result = validate_ai_dax(dax, dataset, user)
        if result.is_valid:
            return result, dax
        
        # Tenta corrigir
        fix_prompt = f"""
        Sua DAX falhou na validação:
        
        {dax}
        
        Erros:
        {chr(10).join('- ' + e for e in result.errors)}
        
        Corrija os erros e retorne apenas o DAX corrigido.
        """
        dax = ai_client.complete(fix_prompt)
    
    return result, dax  # última tentativa, mesmo se falhou
```

## 7. Logging e aprendizado

**Toda validação (sucesso ou falha) vai pro log:**

```json
{
  "timestamp": "...",
  "user": "...",
  "ai_session": "...",
  "dax_hash": "sha256:...",
  "validation": {
    "checks": {"syntax": true, "semantic": true, ...},
    "is_valid": true,
    "errors": [],
    "estimated_cost_ms": 320
  },
  "iteration": 1,
  "fix_applied": false,
  "outcome": "accepted"
}
```

**Com isso, dá pra treinar/melhorar o AI ao longo do tempo** (regressão, hot patterns, etc).
