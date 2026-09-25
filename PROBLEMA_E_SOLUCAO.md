# Análise de Erro em Prod + Solução Arquitetural

## I. ANÁLISE DO ERRO (Root Cause)

### Stack Trace
```
fastmcp/prompts/prompt.py:340 in render
  → _convert_string_arguments()
    Pydantic ValidationError: Input should be a valid integer, unable to parse string '$1' as int
```

### Achado Crítico
**Prompt:** `review_measure(pr_number: int)` — **Linha 662 de `server.py`**

```python
@mcp.prompt()
async def review_measure(pr_number: int) -> str:
    """Prompt to review a PR with a measure change."""
    return f"""Please review PR #{pr_number} that proposes a new measure...
```

**O Problema:** Cliente está chamando com **literal `'$1'`** em vez de número real:
- FastMCP recebe: `{"pr_number": "$1"}`
- Tenta converter string → int
- Falha: `"$1"` não é inteiro
- Erro é **capturado** mas não propagado → **silent failure em prod**

### Por Que É Perigoso

| Aspecto | Impacto |
|---|---|
| **Cliente recebe HTTP 200/202** | Acredita que prompt foi renderizado |
| **Prompt não funciona** | IA recebe vazio ou erro genérico |
| **Log mostra erro mas continua** | Difícil diagnosticar em prod |
| **Escala** | Afeta TODOS os clientes que usam `review_measure` com dados dinâmicos |

---

## II. CORREÇÃO IMEDIATA (3 camadas)

### 1. **Validação de Entrada (Cliente)**
Garantir que argumentos de prompts são sempre válidos antes de enviar:

```typescript
// src_agent/gateway/prompt-client.ts (NOVO)
export function validatePromptArgs(
  promptName: string,
  args: Record<string, unknown>,
  schema: Record<string, "int" | "string" | "float">
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  for (const [key, expectedType] of Object.entries(schema)) {
    const value = args[key];
    
    if (expectedType === "int") {
      if (typeof value === "string") {
        if (!/^\d+$/.test(value)) {
          errors.push(`${key}: string "${value}" é inválida para int (use número)`);
        }
      } else if (typeof value !== "number") {
        errors.push(`${key}: tipo ${typeof value} não é int`);
      }
    }
  }
  
  return { valid: errors.length === 0, errors };
}

// Uso
const result = validatePromptArgs("review_measure", 
  { pr_number: "$1" }, 
  { pr_number: "int" }
);
// result.valid === false
// result.errors = ['pr_number: string "$1" é inválida para int (use número)']
```

### 2. **Coerção Automática (FastMCP/Server)**
Adicionar middleware em `server.py` que converte strings numéricas para int:

```python
# mcp/powerbi-mcp-server/src/powerbi_mcp/server.py (NOVO — antes dos prompts)

from typing import Any
from pydantic import ValidationError

async def coerce_prompt_args(
    prompt_name: str,
    args: dict[str, Any],
    type_hints: dict[str, type]
) -> dict[str, Any]:
    """Coerce prompt arguments para tipos esperados.
    
    Regra: string "123" → int 123 (OK)
            string "$1"  → mantém e deixa validação falhar (EXPLÍCITO)
    """
    coerced = dict(args)
    
    for key, value_type in type_hints.items():
        if key not in coerced:
            continue
        
        value = coerced[key]
        
        # String numérica → int
        if value_type is int and isinstance(value, str):
            if value.isdigit():
                try:
                    coerced[key] = int(value)
                except ValueError:
                    pass  # deixa falhar na validação explicitamente
    
    return coerced

# Wrapper de prompts (NOVO — adiciona coerção antes de chamar)
_original_prompt = mcp.prompt

def coercing_prompt(fn):
    """Decorator que adiciona coerção de tipos a prompts."""
    import inspect
    
    sig = inspect.signature(fn)
    type_hints = {
        param_name: param.annotation
        for param_name, param in sig.parameters.items()
        if param.annotation != inspect.Parameter.empty
    }
    
    async def wrapper(**kwargs):
        coerced = await coerce_prompt_args(fn.__name__, kwargs, type_hints)
        return await fn(**coerced)
    
    return _original_prompt()(wrapper)

# Aplicar aos prompts
@coercing_prompt
async def review_measure(pr_number: int) -> str:
    return f"Please review PR #{pr_number}..."
```

### 3. **Erro Explícito (FastMCP)**
Configurar FastMCP para falhar **rapidamente** em validação inválida:

```python
# mcp/powerbi-mcp-server/pyproject.toml
[project]
dependencies = [
    "fastmcp>=1.0.0,<2.0.0",  # Pin versão — não deixar flutuar
]

# mcp/powerbi-mcp-server/src/powerbi_mcp/server.py (NOVO — no lifespan)
from fastmcp import FastMCP

mcp = FastMCP(
    "powerbi-mcp",
    version="1.0.0",
    # Novo: falhar cedo em validation, não silenciosamente
    capabilities={"tools": {}, "prompts": {}},
)

# Registrar error handler global
@mcp.before_request()
async def validate_request(request: dict) -> dict:
    """Hook que valida requisição antes de processar."""
    if request.get("method") == "prompts/get":
        # Extrair args do payload
        args = request.get("params", {}).get("arguments", {})
        if not args:
            return request
        
        # Validação estrita: reject "$1" literal
        for key, value in args.items():
            if isinstance(value, str) and value.startswith("$"):
                logger.error(
                    "invalid_prompt_arg",
                    prompt=request.get("params", {}).get("name"),
                    arg=key,
                    value=value,
                    hint="Shell placeholder detectado — use valor real"
                )
                raise ValueError(f"Argumento '{key}' com valor '{value}' é inválido (template shell?)")
    
    return request
```

---

## III. ARQUITETURA: CONFIG CENTRALIZADO + MCP UNIFICADO

### Objetivo
- ✅ **Uma config única** — user configura MCP uma vez
- ✅ **PowerBI + DAX unificados** — client não precisa saber que há dois backends
- ✅ **Sem instalação local** — Python CLI de 1 linha, ou apenas config JSON + chamadas HTTP

### Arquitetura Proposta

```
┌──────────────────────────────────────────────────────────────┐
│              BI-IDE-ARCHITECTURE CONFIG (NOVO)               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ~/.bi/config.yaml (ou env vars)                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ mcp:                                                 │   │
│  │   gateway_url: http://192.168.0.160:8001/mcp        │   │
│  │   # Ou local dev:                                    │   │
│  │   # host: localhost                                  │   │
│  │   # port: 8000                                       │   │
│  │                                                      │   │
│  │ auth:                                                │   │
│  │   azure_tenant_id: ${PBI_TENANT_ID}                │   │
│  │   client_id: ${PBI_SP_CLIENT_ID}                    │   │
│  │   client_secret: ${PBI_SP_CLIENT_SECRET}            │   │
│  │                                                      │   │
│  │ workspace:                                           │   │
│  │   id: ${PBI_WORKSPACE_ID}                           │   │
│  │   name: bi-dynamics                                 │   │
│  │                                                      │   │
│  │ project:                                             │   │
│  │   name: bi-vendas                                   │   │
│  │   repo_path: ~/projects/bi-vendas                   │   │
│  │   branch_strategy: feature-branch                   │   │
│  │                                                      │   │
│  │ features:                                            │   │
│  │   auto_audit_on_save: true                          │   │
│  │   require_approval_for_prod: true                   │   │
│  │   two_approvers_prod: true                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ↓ Lido por:                                                │
│  - IDE plugins (VS Code, JetBrains, Claude)                 │
│  - Python SDK (bi-client library)                           │
│  - CLI (bi command)                                         │
│  - Portainer env (container startup)                        │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│           BI-CLIENT SDK (NOVO — Python Package)              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  from bi_client import BiClient, BiConfig                   │
│                                                              │
│  # Load config from ~/.bi/config.yaml or env               │
│  config = BiConfig.from_env()                              │
│  client = BiClient(config)                                 │
│                                                              │
│  # Unified API — não precisa conhecer DAX + PBI backends  │
│  client.audit_tmdl()                      # DAX server     │
│  client.validate_dax("VAR x = 1+1")       # DAX server     │
│  client.push_dataset()                    # PBI server     │
│  client.run_dax_query("EVALUATE ...")     # PBI server     │
│  client.request_approval("deploy_prod")   # PBI server     │
│                                                              │
│  # Internamente: router inteligente que escolhe backend     │
│  # + tratamento de erros + retry + logging                 │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│           GATEWAY (EXISTENTE — sem mudanças)                 │
├──────────────────────────────────────────────────────────────┤
│  Streamable HTTP :8001/mcp                                  │
│  Roteia: dax_* → dax-staff :8001                           │
│          pbi_* → bi-mcp :8000                              │
└──────────────────────────────────────────────────────────────┘
```

### Implementação: BI-Client SDK

**Arquivo novo:** `bi-client-sdk/pyproject.toml` + `bi_client/`

```python
# bi-client-sdk/bi_client/__init__.py
from .config import BiConfig
from .client import BiClient

__all__ = ["BiConfig", "BiClient"]

# bi-client-sdk/bi_client/config.py
from typing import Optional, Literal
from pathlib import Path
import os
import yaml
from pydantic import BaseSettings, Field

class BiConfig(BaseSettings):
    """Configuração centralizada de MCP."""
    
    gateway_url: str = Field(
        default="http://localhost:8000/mcp",
        description="URL do gateway MCP (prod: http://host:8001/mcp)"
    )
    
    # Azure AD
    azure_tenant_id: str = Field(default="", env="PBI_TENANT_ID")
    client_id: str = Field(default="", env="PBI_SP_CLIENT_ID")
    client_secret: str = Field(default="", env="PBI_SP_CLIENT_SECRET")
    
    # Workspace
    workspace_id: str = Field(default="", env="PBI_WORKSPACE_ID")
    workspace_name: str = Field(default="")
    
    # Projeto local
    project_name: str = Field(default="")
    repo_path: str = Field(default=".")
    
    # Feature flags
    auto_audit_on_save: bool = False
    require_approval_for_prod: bool = True
    
    @classmethod
    def from_file(cls, path: str | Path = "~/.bi/config.yaml") -> "BiConfig":
        """Carregar config de arquivo YAML."""
        p = Path(path).expanduser()
        if p.exists():
            with open(p) as f:
                data = yaml.safe_load(f) or {}
            return cls(**data.get("bi", {}))
        return cls()
    
    @classmethod
    def from_env(cls) -> "BiConfig":
        """Carregar de env vars (Portainer, CLI, etc)."""
        return cls()
    
    def to_file(self, path: str | Path = "~/.bi/config.yaml") -> None:
        """Salvar config em YAML."""
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            yaml.dump({"bi": self.dict(exclude_defaults=True)}, f)


# bi-client-sdk/bi_client/client.py
import httpx
from typing import Any, Dict, Literal
from .config import BiConfig
from .router import ToolRouter
from .errors import BiClientError

class BiClient:
    """Cliente unificado para MCP (DAX + PowerBI)."""
    
    def __init__(self, config: BiConfig | None = None):
        self.config = config or BiConfig.from_env()
        self.http = httpx.AsyncClient()
        self.router = ToolRouter(self.config)
    
    async def call_tool(
        self,
        tool_name: str,
        **kwargs
    ) -> dict[str, Any]:
        """Chamar uma ferramenta MCP (roteada automaticamente)."""
        
        # Validar argumentos antes de enviar
        if tool_name == "dax_review_measure":
            if not isinstance(kwargs.get("pr_number"), int):
                raise BiClientError(
                    f"pr_number deve ser int, recebido {type(kwargs['pr_number'])}"
                )
        
        # Rotear para backend correto
        backend = self.router.route_tool(tool_name)
        
        # POST /mcp com payload MCP
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": kwargs,
            },
            "id": 1,
        }
        
        try:
            resp = await self.http.post(self.config.gateway_url, json=payload)
            resp.raise_for_status()
            return resp.json().get("result", {})
        except httpx.HTTPError as e:
            raise BiClientError(f"MCP call failed: {e}")
    
    # High-level APIs (sugar over call_tool)
    
    async def audit_tmdl(self, repo_path: str = ".") -> dict:
        """Auditar modelo TMDL contra regras."""
        return await self.call_tool("dax_audit_tmdl", repo_path=repo_path)
    
    async def validate_dax(self, measure_code: str, name: str = "") -> dict:
        """Validar sintaxe DAX."""
        return await self.call_tool("dax_validate_dax", 
                                   measure_code=measure_code,
                                   measure_name=name)
    
    async def push_pbip(self, path: str, message: str = "") -> dict:
        """Push PBIP para Power BI."""
        return await self.call_tool("pbi_push_pbip",
                                   path=path,
                                   commit_message=message)
    
    async def request_approval(
        self,
        action: Literal["deploy_dev", "deploy_test", "deploy_prod"],
        target: str,
        reason: str = ""
    ) -> dict:
        """Solicitar token de aprovação."""
        return await self.call_tool("pbi_request_approval",
                                   action=action,
                                   target=target,
                                   reason=reason)
    
    async def close(self):
        """Cleanup."""
        await self.http.aclose()


# bi-client-sdk/bi_client/router.py
from .config import BiConfig

class ToolRouter:
    """Roteia chamadas de ferramenta para backend correto (DAX ou PBI)."""
    
    # Mapeamento de tool → backend
    DAX_TOOLS = {
        "dax_validate_dax",
        "dax_audit_tmdl",
        "dax_resolve_dax_metrics",
    }
    
    PBI_TOOLS = {
        "pbi_push_pbip",
        "pbi_pull_pbip",
        "pbi_run_dax_query",
        "pbi_request_approval",
        "pbi_apply_approved_change",
    }
    
    def __init__(self, config: BiConfig):
        self.config = config
    
    def route_tool(self, tool_name: str) -> str:
        """Retorna o backend ('dax' ou 'pbi') para a ferramenta."""
        if tool_name in self.DAX_TOOLS:
            return "dax"
        elif tool_name in self.PBI_TOOLS:
            return "pbi"
        else:
            return "unknown"


# bi-client-sdk/bi_client/errors.py
class BiClientError(Exception):
    """Erro genérico do cliente BI."""
    pass

class ValidationError(BiClientError):
    """Erro de validação de argumentos."""
    pass
```

### CLI Wrapper

```bash
# scripts/bi (wrapper executável)
#!/usr/bin/env python3
"""CLI do BI-IDE Architecture — sem instalação local necessária."""

import sys
from pathlib import Path
from bi_client import BiClient, BiConfig

async def main():
    config = BiConfig.from_env()
    client = BiClient(config)
    
    if len(sys.argv) < 2:
        print("bi <command> [args]")
        print("  audit       — Auditar TMDL contra regras")
        print("  validate    — Validar DAX")
        print("  push        — Push PBIP para Power BI")
        print("  config      — Mostrar/editar config")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "audit":
        result = await client.audit_tmdl()
        print(json.dumps(result, indent=2))
    
    elif cmd == "validate":
        if len(sys.argv) < 3:
            print("bi validate <dax-code>")
            sys.exit(1)
        result = await client.validate_dax(sys.argv[2])
        print(json.dumps(result, indent=2))
    
    elif cmd == "config":
        if len(sys.argv) > 2 and sys.argv[2] == "init":
            config.to_file()
            print(f"Config criada em ~/.bi/config.yaml")
        else:
            print(config.json(indent=2))
    
    else:
        print(f"Comando desconhecido: {cmd}")
        sys.exit(1)
    
    await client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Uso

**Setup (one-time):**
```bash
# Instalar cliente
pip install bi-client-sdk

# Configurar (Portainer env, ou local ~/.bi/config.yaml)
export PBI_TENANT_ID="..."
export PBI_SP_CLIENT_ID="..."
export PBI_SP_CLIENT_SECRET="..."
export PBI_WORKSPACE_ID="..."
export BI_GATEWAY_URL="http://192.168.0.160:8001/mcp"

# Ou criar config file
bi config init
```

**Uso (IDE + CLI):**
```python
# Python code (IDE, script, Jupyter)
from bi_client import BiClient, BiConfig

config = BiConfig.from_env()
client = BiClient(config)

# Validar DAX
result = await client.validate_dax("VAR x = [Sales] + [Costs] RETURN x")
print(result)

# Auditar TMDL
audit = await client.audit_tmdl()
print(f"Achados: {audit['resumo']['total_ocorrencias']}")
```

```bash
# CLI
bi audit                              # Auditar modelo
bi validate "VAR x = 1 RETURN x"     # Validar DAX
bi push src/datasets/Vendas.Dataset   # Push para Power BI
bi config                             # Mostrar config
```

---

## IV. PLANO DE IMPLEMENTAÇÃO

### Fase 1: Fix Imediato (hoje)
- [ ] Adicionar validação de prompt args (Camada 1)
- [ ] Adicionar coerção automática em server.py (Camada 2)
- [ ] Adicionar error handler global (Camada 3)
- [ ] Commit + deploy para homolog

### Fase 2: SDK Centralizado (próxima semana)
- [ ] Criar `bi-client-sdk/` com `BiConfig` + `BiClient`
- [ ] Adicionar `ToolRouter` inteligente
- [ ] Criar CLI wrapper `scripts/bi`
- [ ] Documentar setup one-time

### Fase 3: Integração (após validação)
- [ ] Testar com VS Code + Claude Code extensions
- [ ] Publicar bi-client-sdk no PyPI (ou internal registry)
- [ ] Atualizar docs de onboarding

---

## V. RISCOS MITIGADOS

| Risco | Antes | Depois |
|---|---|---|
| **Client passa `'$1'` ao prompt** | Silencioso; prompt falha | Validado antes; erro claro |
| **FastMCP não converte type** | Falha genérica | Coerção automática string→int |
| **User não sabe como usar MCP** | Dois servers, dois endpoints | Um SDK, uma config, uma API |
| **Setup complexo** | Instalar deps Python, config env | `pip install bi-client-sdk` + `export PBI_*` |
| **IDE precisa conhecer routing** | Lógica espalhada | ToolRouter centralizado |

---

## VI. Próximos Passos

1. **Hoje:** Apply Camadas 1-3 de fix. Test em homolog.
2. **Amanhã:** Code review + deploy para prod
3. **Próxima semana:** Desenvolver bi-client-sdk (Fase 2)
4. **Validação:** Testar com IDE real (VS Code, Claude Code)
