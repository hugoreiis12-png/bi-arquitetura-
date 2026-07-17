# 🧠 MCP Server Power BI · Especificação Técnica

> Detalhamento da implementação do MCP server que conecta IDE/AI ao Power BI.

## 1. Stack

- **Linguagem:** Python 3.11+ (type hints, async/await nativo)
- **SDK:** `mcp` (FastMCP) — `pip install fastmcp`
- **Web framework:** Starlette (FastMCP usa por baixo)
- **Auth:** `msal` (Microsoft Authentication Library) + OAuth2 client credentials
- **HTTP client:** `httpx` (async)
- **XMLA:** `pyadomd` para queries DAX via XMLA endpoint
- **TOM:** `pbi-tools` CLI invocado via subprocess
- **Cache:** `redis` (rate limit, schema cache)
- **Observability:** `opentelemetry-*` + Azure Monitor exporter
- **Testes:** `pytest` + `pytest-asyncio`

## 2. Estrutura do projeto

```
mcp/powerbi-mcp-server/
├── pyproject.toml
├── README.md
├── Dockerfile
├── docker-compose.yml         # dev local
├── .env.example
├── src/
│   └── powerbi_mcp/
│       ├── __init__.py
│       ├── server.py          # entrypoint FastMCP
│       ├── config.py          # settings (env vars)
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── azure_ad.py    # OAuth2 client credentials
│       │   └── token_cache.py # cache de token
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── safe/          # 🟢 read-only
│       │   │   ├── list_datasets.py
│       │   │   ├── get_schema.py
│       │   │   ├── query_dax.py
│       │   │   ├── format_dax.py
│       │   │   └── search_dictionary.py
│       │   ├── moderate/      # 🟡 write metadata
│       │   │   ├── validate_dax.py
│       │   │   └── suggest_measure.py
│       │   ├── dangerous/     # 🟠 write model
│       │   │   ├── propose_measure_update.py
│       │   │   └── propose_relationship.py
│       │   └── critical/      # 🔴 deploy / delete
│       │       ├── apply_change.py    # requer approval token
│       │       └── refresh_dataset.py # requer approval token
│       ├── resources/
│       │   ├── tmdl_files.py
│       │   ├── data_dict.py
│       │   └── lineage.py
│       ├── prompts/
│       │   ├── review_pr.py
│       │   ├── explain_measure.py
│       │   └── generate_kpi.py
│       ├── guardrails/
│       │   ├── rbac.py        # role-based access
│       │   ├── rate_limit.py  # por user + tool
│       │   ├── audit.py       # toda ação logada
│       │   ├── approval.py    # approval token workflow
│       │   └── dlp.py         # data loss prevention (PII)
│       ├── knowledge/
│       │   ├── rag_search.py  # busca no Azure AI Search
│       │   └── embeddings.py
│       └── utils/
│           ├── pbi_tools.py
│           ├── xmla.py
│           └── validation.py
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

## 3. Tools — contratos

### 3.1 `pbi_list_datasets` (🟢 safe)

```python
@mcp.tool(
    name="pbi_list_datasets",
    description="Lista datasets Power BI em um workspace. Read-only.",
    risk_level="safe",
)
async def list_datasets(
    workspace_id: str,
    user_context: UserContext = Depends(),
) -> List[DatasetInfo]:
    """Retorna metadados básicos dos datasets do workspace."""
    check_rbac(user_context, "pbi:read:metadata")
    audit_log("pbi_list_datasets", user_context, {"workspace_id": workspace_id})
    return await pbi_rest.list_datasets(workspace_id, user_context.sp_token)
```

### 3.2 `pbi_query_dax` (🟢 safe, mas com DLP)

```python
@mcp.tool(
    name="pbi_query_dax",
    description="Executa query DAX contra XMLA endpoint. Read-only.",
    risk_level="safe",
)
async def query_dax(
    workspace_id: str,
    dataset_id: str,
    dax_query: str,
    user_context: UserContext = Depends(),
) -> QueryResult:
    # 1. Validação de input
    if not is_select_only(dax_query):  # rejeita CREATE/ALTER/DELETE
        raise ToolError("Apenas queries SELECT (EVALUATE) são permitidas")
    
    # 2. DLP — bloqueia padrões que poderiam vazar PII
    dlp_check(dax_query, user_context)
    
    # 3. RBAC
    check_rbac(user_context, "pbi:read:data")
    
    # 4. Audit
    audit_log("pbi_query_dax", user_context, {
        "workspace_id": workspace_id,
        "dataset_id": dataset_id,
        "dax_hash": hash(dax_query),  # nunca loga a query inteira
        "row_count_limit": 10_000,
    })
    
    # 5. Execução com timeout + row limit
    return await xmla.execute(
        workspace_id, dataset_id, dax_query,
        timeout_seconds=30,
        max_rows=10_000,
    )
```

### 3.3 `pbi_propose_measure_update` (🟠 dangerous)

```python
@mcp.tool(
    name="pbi_propose_measure_update",
    description="Cria branch + PR com nova medida. NÃO aplica diretamente.",
    risk_level="dangerous",
)
async def propose_measure_update(
    workspace_id: str,
    dataset_id: str,
    measure_definition: MeasureDefinition,
    user_context: UserContext = Depends(),
) -> PRProposal:
    check_rbac(user_context, "pbi:write:model")
    audit_log("pbi_propose_measure_update", user_context, ...)
    
    # 1. Validação TMDL
    validation = await validate_tmdl(measure_definition)
    if not validation.ok:
        raise ToolError(f"Invalid TMDL: {validation.errors}")
    
    # 2. Cria branch no repo do dataset
    branch = f"ai/measure-{slugify(measure_definition.name)}-{short_uuid()}"
    await git.create_branch(dataset_repo, branch)
    
    # 3. Escreve TMDL
    tmdl_path = f"src/datasets/{dataset_id}/definition/tables/{measure_definition.table}.tmdl"
    await git.write_file(dataset_repo, branch, tmdl_path, measure_definition.to_tmdl())
    
    # 4. Gera smoke test
    test_path = f"tests/dax/ai-{short_uuid()}.dax"
    await git.write_file(dataset_repo, branch, test_path, generate_smoke_test(measure_definition))
    
    # 5. Abre PR
    pr = await git.create_pr(
        dataset_repo,
        branch=branch,
        title=f"feat(ai): {measure_definition.name}",
        body=generate_pr_body(measure_definition, validation),
        labels=["ai-generated", "needs-review"],
    )
    
    return PRProposal(pr_url=pr.url, pr_number=pr.number, branch=branch)
```

### 3.4 `pbi_apply_approved_change` (🔴 critical)

```python
@mcp.tool(
    name="pbi_apply_approved_change",
    description="Aplica mudança APROVADA em produção. Requer approval token.",
    risk_level="critical",
)
async def apply_approved_change(
    approval_token: str,
    pr_number: int,
    target_environment: Literal["dev", "test", "prod"],
    user_context: UserContext = Depends(),
) -> DeploymentResult:
    # 1. Valida approval token
    approval = await approval_service.validate(approval_token, user_context)
    if not approval.valid:
        raise ToolError("Approval token inválido ou expirado")
    
    # 2. Check RBAC + Environment
    check_rbac(user_context, f"pbi:deploy:{target_environment}")
    
    # 3. Aprovação adicional para prod
    if target_environment == "prod":
        require_two_approvers(approval, user_context)
    
    # 4. Audit detalhado
    audit_log_critical("pbi_apply_approved_change", user_context, {
        "pr_number": pr_number,
        "target": target_environment,
        "approvers": approval.approvers,
    })
    
    # 5. Deploy via pipeline (mesmo fluxo de dev humano)
    return await deployment_pipeline.run(pr_number, target_environment)
```

## 4. Approval Workflow

**Tokens de aprovação:**

```python
class ApprovalToken(BaseModel):
    token: str           # UUID v4
    user_id: str
    action: str          # "deploy_prod" / "delete_table" / etc
    target: str          # pr_number, dataset_id, etc
    approvers: List[str] # quem aprovou
    issued_at: datetime
    expires_at: datetime # 15 minutos
    used: bool = False

# Fluxo:
# 1. AI gera PR (propose_measure_update)
# 2. Dev revisa no GitHub, aprova
# 3. Dev gera approval token via:
#    - GitHub comment: /ai-approve
#    - CLI: powerbi-mcp token issue --pr 123 --action deploy_test
#    - Bot (Teams): "Approve deployment of PR #123 to test?"
# 4. Token é single-use, 15min TTL
# 5. AI usa token em apply_approved_change
```

## 5. RBAC · mapeamento de roles

| Role Azure AD | Tools MCP permitidas |
|---|---|
| `BI-Reader` | `pbi_list_datasets`, `pbi_get_schema`, `pbi_query_dax`, `pbi_format_dax` |
| `BI-Developer` | + `pbi_validate_dax`, `pbi_suggest_measure`, `pbi_propose_*` |
| `BI-Tech-Lead` | + `pbi_apply_approved_change` (dev/test) |
| `BI-Steward` | + `pbi_apply_approved_change` (all envs) |
| `BI-Admin` | + tudo (incluindo config) |

**Implementação:**

```python
ROLE_PERMISSIONS = {
    "BI-Reader": {"pbi:read:*"},
    "BI-Developer": {"pbi:read:*", "pbi:write:model", "pbi:validate:*"},
    "BI-Tech-Lead": {"pbi:read:*", "pbi:write:*", "pbi:deploy:dev", "pbi:deploy:test"},
    "BI-Steward": {"pbi:*"},
    "BI-Admin": {"*"},
}

def check_rbac(user: UserContext, required: str) -> None:
    user_perms = set()
    for role in user.roles:
        user_perms |= ROLE_PERMISSIONS.get(role, set())
    
    # Match com wildcard
    if required in user_perms or "*" in user_perms:
        return
    
    # Match por prefixo
    for perm in user_perms:
        if perm.endswith(":*") and required.startswith(perm[:-1]):
            return
    
    raise PermissionDeniedError(f"User lacks permission: {required}")
```

## 6. Rate Limiting

```python
RATE_LIMITS = {
    "default": {"per_minute": 60, "per_hour": 1000, "per_day": 10_000},
    "pbi_query_dax": {"per_minute": 30, "per_hour": 500, "per_day": 5_000},
    "pbi_apply_approved_change": {"per_minute": 5, "per_hour": 20, "per_day": 50},
    "ai_generation": {"per_minute": 10, "per_hour": 100, "cost_per_day_usd": 10.00},
}
```

Implementação com Redis sliding window.

## 7. Deploy

```yaml
# azure-container-app.yaml
apiVersion: app/v1
kind: ContainerApp
metadata:
  name: powerbi-mcp-server
spec:
  configuration:
    ingress:
      external: false  # interno apenas
    activeRevisionsMode: Single
  template:
    containers:
      - image: acrbi.azurecr.io/powerbi-mcp:v1.0.0
        env:
          - name: AZURE_TENANT_ID
            secretRef: tenant-id
          - name: PBI_MCP_SP_CLIENT_ID
            secretRef: sp-client-id
          - name: PBI_MCP_SP_CLIENT_SECRET
            secretRef: sp-client-secret
          - name: REDIS_URL
            secretRef: redis-url
          - name: AI_SEARCH_ENDPOINT
            secretRef: ai-search-endpoint
        resources:
          cpu: 1.0
          memory: 2.0Gi
    scale:
      minReplicas: 1
      maxReplicas: 3
      rules:
        - type: cpu
          metadata:
            type: Utilization
            value: 70
```

## 8. Segurança do MCP server

**Ameaças específicas de MCP:**

| Ameaça | Mitigação |
|---|---|
| **Prompt injection** via TMDL file malicioso | Input validation + sanitização de markdown antes de processar |
| **Tool abuse** (AI chamando tools em loop) | Rate limit + cost ceiling + adaptive alerting |
| **Secret leak** via output de query DAX | DLP scanner no output (regex de CPF, CNPJ, email, etc) |
| **Privilege escalation** via role confusion | RBAC explícito, sem herança implícita |
| **Lateral movement** (AI acessando outros workspaces) | Workspace allowlist por user context |
| **Replay attack** em approval token | Token single-use, 15min TTL, binding ao PR |
| **DoS** via queries pesadas | Timeout 30s, max 10k rows, cost estimate antes de executar |
| **Data exfiltration** via queries lentas | Anomaly detection (queries 10x maiores que baseline) |

## 9. Métricas de health

```promql
# Prometheus queries (ou App Insights equivalent)
mcp_tool_calls_total{tool, status, user_role}
mcp_tool_call_duration_seconds{tool, quantile="0.99"}
mcp_dax_query_rows_returned{tool}
mcp_approval_token_usage_total{action, env}
mcp_rbac_denied_total{tool, user_role, required_permission}
mcp_dlp_blocked_total{pattern}
mcp_active_users{role}
mcp_cost_usd_per_user_day
```
