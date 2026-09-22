# Guia de Uso: MCP Server + opencode

## Visão Geral

O projeto bi-ide-architecture oferece **dois modos de operação** para desenvolvimento BI com IA:

| Modo | Caminho | Uso Principal |
|------|---------|---------------|
| **opencode** | Tools embutidas | Desenvolvimento local (TMDL, DAX, medidas) |
| **MCP Client** | Cline/Continue/Claude Desktop | Operações no Power BI Service (cloud) |

---

## 1. opencode (Já Funcional)

Tools disponíveis nesta sessão sem configuração adicional:

### powerbi-modeling-mcp
- Criar/editar tabelas, colunas, medidas
- Gerenciar relacionamentos
- Exportar TMDL/TMSL
- Operações em Semantic Model local

### dax-staff
- `validate_dax` — Validação 6 dimensões
- `search_dax_pattern` — Patterns DAX prontos
- `generate_theme_json` — Temas Power BI
- `generate_svg` — Micro-visuais (sparklines, bullets)
- `generate_html_component` — Cards KPI HTML
- `generate_deneb_spec` — Specs Vega-Lite

### excel
- Manipulação completa de planilhas
- Tabelas, gráficos, pivot tables
- Formatação, validação, fórmulas

---

## 2. MCP Client (Cline/Continue/Claude Desktop)

### Pré-requisitos
1. Docker Desktop instalado e rodando
2. Azure CLI (`az`) instalado
3. Credenciais Azure AD (Service Principal)
4. Imagem Docker publicada no ACR

### Configuração

O arquivo `.vscode/mcp.json` já está configurado:

```json
{
  "mcpServers": {
    "powerbi": {
      "command": "docker",
      "args": ["run", "-i", "--rm", ...],
      "env": {
        "PBI_TENANT_ID": "...",
        "PBI_SP_CLIENT_ID": "...",
        ...
      }
    }
  }
}
```

### Credenciais Necessárias

Copiar `.env.example` → `.env`:

| Variável | Descrição |
|----------|-----------|
| `PBI_TENANT_ID` | Azure AD Tenant ID |
| `PBI_SP_CLIENT_ID` | Service Principal Client ID |
| `PBI_SP_CLIENT_SECRET` | Service Principal Secret |
| `PBI_WORKSPACE_DEV_ID` | Workspace Dev |
| `PBI_WORKSPACE_TEST_ID` | Workspace Test |
| `PBI_WORKSPACE_PROD_ID` | Workspace Prod |
| `PBI_WORKSPACE_PLAYGROUND_ID` | Workspace Playground |
| `REDIS_URL` | Redis (rate limit + approval cache) |
| `AI_SEARCH_ENDPOINT` | Azure AI Search (RAG) |
| `APP_INSIGHTS_CONNECTION_STRING` | Telemetria |

### Tools do MCP Server (12 tools)

#### Seguras (sem side-effects)
| Tool | Descrição |
|------|-----------|
| `pbi_list_datasets` | Listar datasets no workspace |
| `pbi_get_model_schema` | Schema de tabelas, colunas, medidas |
| `pbi_query_dax` | Executar DAX (SELECT only) |
| `pbi_format_dax` | Formatar código DAX |
| `pbi_search_dictionary` | Busca semântica no data dictionary |

#### Moderadas (validadas)
| Tool | Descrição |
|------|-----------|
| `pbi_validate_dax_syntax` | Validação 6 dimensões |
| `pbi_suggest_measure` | Sugerir DAX para regra de negócio |

#### Perigosas (PR review)
| Tool | Descrição |
|------|-----------|
| `pbi_propose_measure_update` | Criar branch + PR com nova medida |

#### Críticas (aprovação obrigatória)
| Tool | Descrição |
|------|-----------|
| `pbi_apply_approved_change` | Deploy (prod: 2 aprovadores) |
| `pbi_request_approval` | Gerar token de aprovação |

### Guardrails (7 camadas)
1. Network — VNet + private endpoint
2. Authentication — OAuth2 SP + JWT
3. RBAC — 5 roles, 11 permissões
4. Action classification — 4 níveis de risco
5. Approval workflow — Tokens single-use, TTL 15min
6. Audit trail — Todas as ações logadas
7. Rate limiting — Por usuário, tool, custo
8. DLP — Bloqueio de PII

---

## 3. Fluxo de Trabalho Recomendado

```
┌─────────────────────────────────────────────────────────────┐
│                     DESENVOLVIMENTO                         │
├─────────────────────────────────────────────────────────────┤
│  opencode                                                   │
│  ├─ Criar modelo TMDL local                                 │
│  ├─ Escrever medidas DAX                                    │
│  ├─ Validar com dax-staff                                   │
│  ├─ Gerar temas e micro-visuais                             │
│  └─ Commit → Git                                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     PUBLICAÇÃO                              │
├─────────────────────────────────────────────────────────────┤
│  MCP Client (Cline/Continue)                                │
│  ├─ Listar datasets existentes                              │
│  ├─ Comparar schemas                                        │
│  ├─ Propor mudanças via PR                                  │
│  ├─ Aprovar e deploy                                        │
│  └─ Monitorar via telemetria                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Status Atual

| Componente | Status |
|------------|--------|
| opencode tools | ✅ Funcional |
| MCP Server code | ✅ Implementado |
| Dockerfile | ✅ Pronto |
| .vscode/mcp.json | ✅ Configurado |
| .env | ❌ Não criado |
| Docker Desktop | ❌ Daemon não rodando |
| Azure CLI | ❌ Não instalado |
| ACR image | ❌ Não publicada |

---

## 5. Próximos Passos

### Para habilitar MCP Client:
1. Criar `.env` com credenciais reais
2. Iniciar Docker Desktop
3. Build: `docker build -t powerbi-mcp:1.0.0 .`
4. Teste local: `docker run -i --rm --env-file .env powerbi-mcp:1.0.0`
5. Instalar Azure CLI
6. Push para ACR: `az acr build --registry acrbi --image powerbi-mcp:1.0.0 .`

### Para opencode:
Nada necessário — já funciona.
