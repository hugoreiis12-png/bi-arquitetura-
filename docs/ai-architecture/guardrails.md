# 🛡️ Guardrails · Segurança da Camada AI

> Defense in depth. 7 camadas obrigatórias. Falha de uma não compromete o todo.

## 1. As 7 camadas

```
┌─────────────────────────────────────────────────────────────┐
│ 1 · Network         VNet + Private Endpoint + IP allowlist  │
├─────────────────────────────────────────────────────────────┤
│ 2 · Authentication  OAuth2 SP + Key Vault + rotação         │
├─────────────────────────────────────────────────────────────┤
│ 3 · RBAC            Roles Azure AD + permission scoping     │
├─────────────────────────────────────────────────────────────┤
│ 4 · Classification  Risk level por tool (safe/crit)         │
├─────────────────────────────────────────────────────────────┤
│ 5 · Approval        Single-use tokens, 15min TTL            │
├─────────────────────────────────────────────────────────────┤
│ 6 · Audit           Log completo de toda ação               │
├─────────────────────────────────────────────────────────────┤
│ 7 · Rate Limit      Por user, por tool, por custo           │
└─────────────────────────────────────────────────────────────┘
```

## 2. Camada 1 · Network

**Topologia:**

```
Internet (devs)
    ↓ HTTPS only
Azure Front Door (WAF)
    ↓
Azure Container Apps Environment (VNet)
    ├─ MCP Server (private IP, sem internet outbound)
    └─ Redis (private endpoint)
    ↓ private endpoint
Power BI Service (Premium P1+ com private link)
```

**Regras:**

| Regra | Aplicação |
|---|---|
| MCP server sem IP público | Container App `ingress.external=false` |
| Saída apenas pra VNet | NSG outbound rules |
| WAF bloqueia SQL injection / path traversal | Front Door WAF policy |
| Private endpoint pro Power BI | Power BI Private Links (preview) |
| TLS 1.3 obrigatório | Front Door + Container App config |
| Certificados gerenciados | Azure Key Vault + managed certs |

## 3. Camada 2 · Authentication

**Service Principal dedicado ao MCP:**

```bash
# Cria SP só pro MCP
az ad sp create --display-name "bi-mcp-server" \
    --scopes /subscriptions/xxx/resourceGroups/rg-bi

# Atribui role mínima
az role assignment create \
    --assignee $SP_OBJECT_ID \
    --role "Power BI Service Contributor" \
    --scope "/subscriptions/xxx/resourceGroups/rg-bi/providers/Microsoft.PowerBIDedicated/capacities/cap-bi"
```

**Segredo:**
- Armazenado em **Azure Key Vault**
- Rotação a cada **90 dias** (automação via Event Grid)
- MCP server carrega na inicialização, cacheia em memória, recarrega se Key Vault sinaliza mudança

**Auth do dev final (que usa MCP via Cline/Claude):**

O MCP server recebe o **user context** (não roda como SP direto). Fluxo:

```
1. Dev autentica no Cline (Azure AD OAuth)
2. Cline envia JWT do user pro MCP server
3. MCP server valida JWT
4. MCP server extrai roles, groups, claims
5. MCP server usa seu próprio SP pra falar com Power BI
6. MCP server enriquece requests com user context
7. Audit log inclui quem (user) E com quais credenciais (SP)
```

**Implementação:**

```python
# MCP recebe: Authorization: Bearer <user-jwt>
# + X-MCP-Session-Id (pra correlação)

def extract_user_context(request) -> UserContext:
    jwt = decode_jwt(request.headers["Authorization"])
    
    # Valida assinatura, issuer, audience, expiration
    if not is_valid_jwt(jwt):
        raise AuthError("Invalid token")
    
    return UserContext(
        user_id=jwt["oid"],
        email=jwt["preferred_username"],
        roles=jwt.get("roles", []),
        groups=jwt.get("groups", []),
        sp_token=get_sp_token(),  # usa o SP do MCP
    )
```

## 4. Camada 3 · RBAC

**Roles Azure AD e permissões MCP:**

| Role Azure AD | Permissões MCP | Quem tem |
|---|---|---|
| `BI-AI-Reader` | `pbi:read:*` | Analista, negócio |
| `BI-AI-Developer` | `pbi:read:*`, `pbi:validate:*`, `pbi:write:model` | Dev BI |
| `BI-AI-Lead` | + `pbi:deploy:dev`, `pbi:deploy:test` | Tech lead |
| `BI-AI-Steward` | + `pbi:deploy:prod` | Steward de dados |
| `BI-AI-Admin` | `*` (incluindo config) | Platform team |

**Sincronização Azure AD → MCP:**

```python
# Cache de role mappings (Redis, TTL 5min)
ROLE_GROUPS = {
    "BI-AI-Reader":    "bi-ai-reader",
    "BI-AI-Developer": "bi-ai-developer",
    "BI-AI-Lead":      "bi-ai-lead",
    "BI-AI-Steward":   "bi-ai-steward",
    "BI-AI-Admin":     "bi-ai-admin",
}

def get_user_roles(user: UserContext) -> Set[str]:
    # Combina roles do JWT + groups do Azure AD
    roles = set(user.roles)
    for group_id in user.groups:
        for role_name, group_oid in ROLE_GROUPS.items():
            if group_id == group_oid:
                roles.add(role_name)
    return roles
```

**Workspace scoping (per user):**

```python
# Config em deploy/ai-playground/config.json
{
  "workspaceAllowlist": {
    "BI-AI-Reader":    ["bi-*-dev"],
    "BI-AI-Developer": ["bi-*-dev", "bi-*-ai-playground"],
    "BI-AI-Lead":      ["bi-*-dev", "bi-*-ai-playground", "bi-*-test"],
    "BI-AI-Steward":   ["bi-*-*"],
    "BI-AI-Admin":     ["*"]
  }
}

def check_workspace_access(user, workspace_id):
    user_patterns = get_workspace_patterns(user.roles)
    if not any(match(workspace_id, p) for p in user_patterns):
        raise PermissionDeniedError()
```

## 5. Camada 4 · Action Classification

**Cada tool tem risk_level declarado:**

```python
RISK_LEVELS = {
    "safe": {
        "description": "Read-only, sem side-effect",
        "approval_required": False,
        "audit_level": "INFO",
        "rate_limit": "default",
    },
    "moderate": {
        "description": "Write metadata não-critica, ou read de dados sensíveis",
        "approval_required": False,
        "audit_level": "INFO",
        "rate_limit": "stricter",
    },
    "dangerous": {
        "description": "Write de modelo (medidas, relações)",
        "approval_required": True,  # via PR review
        "audit_level": "WARN",
        "rate_limit": "low",
    },
    "critical": {
        "description": "Delete, deploy, change RLS, change data source",
        "approval_required": True,  # via approval token
        "audit_level": "CRITICAL",
        "rate_limit": "very_low",
    },
}
```

**Mapping por tool** (ver `mcp-server.md`).

## 6. Camada 5 · Approval Workflow

**Dois tipos de approval:**

### 6.1 PR Review (para dangerous)
- AI gera PR
- Dev humano revisa no GitHub
- Aprovação de 1+ reviewer antes de merge
- Merge dispara deploy em Dev (mesmo pipeline de dev humano)

### 6.2 Approval Token (para critical)
- AI propõe ação
- Dev/Steward gera approval token
- AI usa token (válido 15min, single-use)
- Ação é executada

**Geração de token (3 caminhos):**

```bash
# 1. CLI
powerbi-mcp token issue \
    --pr 1234 \
    --action deploy_test \
    --reason "Validação de hotfix em cliente X"

# 2. GitHub comment (bot)
# No PR, comentar: /ai-approve deploy_test

# 3. Teams adaptive card
# Bot posta card: "AI solicita deploy de PR #1234 em Test"
# Botões: Aprovar | Rejeitar | Revisar
```

**Token structure:**

```json
{
  "token": "apv_abc123...",
  "user_id": "uuid",
  "action": "deploy_test",
  "target": "PR#1234",
  "approvers": ["uuid1"],
  "issued_at": "2026-07-15T14:00:00Z",
  "expires_at": "2026-07-15T14:15:00Z",
  "single_use": true,
  "audit_hash": "sha256:..."
}
```

**Para prod: 2 approvers obrigatórios.**

## 7. Camada 6 · Audit Trail

**Log estrutura (App Insights custom logs):**

```json
{
  "timestamp": "2026-07-15T14:00:00.123Z",
  "session_id": "uuid",
  "user": {
    "id": "uuid",
    "email": "user@empresa.com",
    "roles": ["BI-AI-Developer"],
    "ip": "x.x.x.x",
    "user_agent": "Cline/1.0"
  },
  "mcp_request": {
    "tool": "pbi_query_dax",
    "risk_level": "safe",
    "args_hash": "sha256:...",
    "args_summary": "{workspace_id, dataset_id, query_hash}"
  },
  "mcp_response": {
    "status": "success",
    "duration_ms": 234,
    "rows_returned": 42,
    "output_hash": "sha256:..."
  },
  "approval": null,
  "cost": {
    "tokens_input": 1234,
    "tokens_output": 567,
    "estimated_usd": 0.012
  }
}
```

**Retenção:** 7 anos (compliance SOX/LGPD).

**Dashboards de auditoria:**
- Queries por user/period
- Tentativas negadas
- Aprovações solicitadas vs concedidas
- Custos por user
- Acessos a dados sensíveis (PII)

**Alertas:**
- Tentativa de acesso a workspace não permitido
- Approval token reutilizado
- Padrão de uso anômalo (10x baseline)
- Custo diário > threshold

## 8. Camada 7 · Rate Limiting

**Sliding window no Redis:**

```python
class RateLimiter:
    def __init__(self, redis_url):
        self.redis = redis.from_url(redis_url)
        self.limits = {
            "default": {"1m": 60, "1h": 1000, "1d": 10_000},
            "pbi_query_dax": {"1m": 30, "1h": 500, "1d": 5_000},
            "pbi_apply_approved_change": {"1m": 5, "1h": 20, "1d": 50},
        }
        self.cost_limits = {
            "default": {"1d_usd": 10.0},
            "ai_generation": {"1d_usd": 50.0},
        }
    
    def check(self, user_id: str, tool: str, estimated_cost: float = 0) -> None:
        limits = self.limits.get(tool, self.limits["default"])
        for window, max_count in limits.items():
            key = f"rate:{user_id}:{tool}:{window}"
            current = self.redis.incr(key)
            self.redis.expire(key, parse_window(window))
            if current > max_count:
                raise RateLimitError(f"Limit exceeded: {max_count}/{window}")
        
        # Cost limits
        cost_limits = self.cost_limits.get(tool, self.cost_limits["default"])
        for window, max_cost in cost_limits.items():
            key = f"cost:{user_id}:{tool}:{window}"
            current = self.redis.incrbyfloat(key, estimated_cost)
            if current > max_cost:
                # Auto-pause + alerta
                self.pause_user(user_id, duration=3600)
                notify_tech_lead(f"User {user_id} auto-paused: cost ${current}")
                raise CostLimitError()
```

## 9. DLP · Data Loss Prevention

**Bloqueia exfiltração de PII via queries DAX:**

```python
DLP_PATTERNS = [
    # CPF
    (r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "CPF"),
    # CNPJ
    (r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", "CNPJ"),
    # Email
    (r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "EMAIL"),
    # Telefone
    (r"\(\d{2}\)\s?9?\d{4}-?\d{4}", "PHONE"),
    # Cartão de crédito
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "CC"),
    # Endereço (heurística)
    (r"(?i)\b(rua|avenida|av\.?|travessa|alameda)\s+[\w\s,]+?\d+\b", "ADDRESS"),
]

def dlp_check_input(dax_query: str, user: UserContext) -> None:
    if user.has_role("BI-AI-Admin"):
        return  # admins bypass
    
    for pattern, pii_type in DLP_PATTERNS:
        if re.search(pattern, dax_query):
            audit_log("DLP_BLOCKED", user, {"type": pii_type, "tool": "input"})
            raise DLPError(f"Query contém possível {pii_type}")

def dlp_check_output(result: QueryResult, user: UserContext) -> QueryResult:
    if user.has_role("BI-AI-Admin"):
        return result
    
    for row in result.rows:
        for col, value in row.items():
            for pattern, pii_type in DLP_PATTERNS:
                if isinstance(value, str) and re.search(pattern, value):
                    # Redact ao invés de bloquear
                    row[col] = redact(value, pii_type)
                    audit_log("DLP_REDACTED", user, {"col": col, "type": pii_type})
    return result
```

## 10. Configurações externas vs internas

**Separação clara:**

```yaml
# config/external.yaml (público, versionado, baixa sensibilidade)
mcp:
  server_name: "bi-mcp-powerbi"
  version: "1.0.0"
  description: "Power BI MCP server for AI-augmented BI development"
  homepage: "https://github.com/org/bi-mcp"
  
  capabilities:
    - tools
    - resources
    - prompts
  
  default_settings:
    dax_query_max_rows: 10000
    dax_query_timeout_seconds: 30
    dax_format_style: "longLine"

# config/internal.yaml (privado, não versionado, em Key Vault)
mcp_internal:
  sp_credentials:
    client_id: "${PBI_MCP_SP_CLIENT_ID}"
    client_secret: "${PBI_MCP_SP_CLIENT_SECRET}"
    tenant_id: "${PBI_TENANT_ID}"
  
  rate_limits:
    enabled: true
    redis_url: "${REDIS_URL}"
  
  cost_limits:
    enabled: true
    daily_limit_usd: 50.0
  
  approval:
    token_ttl_minutes: 15
    require_two_approvers_for_prod: true
  
  audit:
    retention_days: 2555  # 7 anos
    storage_account: "${AUDIT_STORAGE}"
  
  dlp:
    enabled: true
    bypass_roles: ["BI-AI-Admin"]
  
  observability:
    app_insights_connection_string: "${APPINSIGHTS_CS}"
    sampling_rate: 1.0
```

## 11. Checklists de segurança

**Antes de subir pra prod:**

- [ ] Penetration testing feito
- [ ] Code review por security team
- [ ] Secrets em Key Vault (nunca em env direto)
- [ ] Network isolado (sem IP público)
- [ ] Audit log testado (quem fez o quê, quando)
- [ ] RBAC testado com cada role
- [ ] DLP testado com PII conhecido
- [ ] Rate limit testado
- [ ] Approval workflow testado end-to-end
- [ ] Rollback testado (rollback de PR via AI)
- [ ] Incident response playbook documentado
- [ ] Compliance review (LGPD/GDPR/SOX)

**Operacional (mensal):**

- [ ] Rotação de SP secret (se chegou 90 dias)
- [ ] Review de audit log por amostragem
- [ ] Review de access patterns (anomalias)
- [ ] Update de DLP patterns (novos tipos de PII)
- [ ] Review de cost ceilings
- [ ] Teste de DR (kill switch do MCP)
