# Power BI MCP Server

MCP server for AI-augmented Power BI development. Exposes 12 tools, 5 roles,
7 guardrails layers, and full DAX validation harness.

## Quick start

### Local development

```bash
# Install
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your values

# Run (stdio mode, for local Cline/Continue)
powerbi-mcp

# Run (HTTP mode, for Azure deployment)
powerbi-mcp --http
```

### Docker

```bash
docker build -t powerbi-mcp:1.0.0 .
docker run -i --rm \
  -e AZURE_TENANT_ID=xxx \
  -e PBI_SP_CLIENT_ID=xxx \
  -e PBI_SP_CLIENT_SECRET=xxx \
  powerbi-mcp:1.0.0
```

## Tools exposed

### Safe (no approval, no side-effects)

| Tool | Description |
|---|---|
| `pbi_list_datasets` | List datasets in a workspace |
| `pbi_get_model_schema` | Get tables, columns, measures |
| `pbi_query_dax` | Execute DAX query (SELECT only) |
| `pbi_format_dax` | Format DAX code |
| `pbi_search_dictionary` | Search data dictionary semantically |

### Moderate (no approval, but validated)

| Tool | Description |
|---|---|
| `pbi_validate_dax_syntax` | 6-dimension DAX validation |
| `pbi_suggest_measure` | Suggest DAX for a business rule |

### Dangerous (PR review required)

| Tool | Description |
|---|---|
| `pbi_propose_measure_update` | Create branch + PR with new measure |

### Critical (approval token required)

| Tool | Description |
|---|---|
| `pbi_apply_approved_change` | Deploy approved change (prod requires 2 approvers) |
| `pbi_request_approval` | Issue approval token for a critical action |

## Guardrails

7 layers of defense:

1. **Network** — VNet + private endpoint (when deployed to Azure)
2. **Authentication** — OAuth2 SP + JWT validation
3. **RBAC** — 5 roles, 11 permissions, workspace allowlisting
4. **Action classification** — 4 risk levels (safe/moderate/dangerous/critical)
5. **Approval workflow** — Single-use tokens, 15min TTL
6. **Audit trail** — Every action logged with structured fields
7. **Rate limiting** — Per user, per tool, per cost

Plus **DLP** (Data Loss Prevention) — blocks PII in queries and outputs.

## Configuration

All config is via environment variables. See `.env.example` for full list.

Required:
- `AZURE_TENANT_ID`
- `PBI_SP_CLIENT_ID`
- `PBI_SP_CLIENT_SECRET`

Optional:
- `REDIS_URL` (for rate limit + approval cache)
- `AI_SEARCH_ENDPOINT` + `AI_SEARCH_API_KEY` (for RAG)
- `APP_INSIGHTS_CONNECTION_STRING` (for telemetry)

## Admin CLI

```bash
# Issue approval token
powerbi-mcp-admin token issue \
  --action deploy_test \
  --target PR#127 \
  --user-id joao@empresa.com \
  --reason "Hotfix em cliente X"

# Approve token
powerbi-mcp-admin token approve \
  --token apv_xxx \
  --approver-id maria@empresa.com

# Pause a user
powerbi-mcp-admin user pause \
  --user-id joao@empresa.com \
  --duration 1h
```

## Deploy to Azure

```bash
# Build and push
az acr build --registry acrbi \
  --image powerbi-mcp:v1.0.0 \
  --file Dockerfile .

# Deploy to Container Apps
az containerapp create \
  --name powerbi-mcp \
  --resource-group rg-bi \
  --environment env-bi \
  --image acrbi.azurecr.io/powerbi-mcp:v1.0.0 \
  --ingress external \
  --target-port 8000 \
  --env-vars \
    AZURE_TENANT_ID=secretref:tenant-id \
    PBI_SP_CLIENT_ID=secretref:sp-client-id \
    PBI_SP_CLIENT_SECRET=secretref:sp-client-secret \
    REDIS_URL=secretref:redis-url
```

## Architecture

See `docs/ai-architecture/mcp-server.md` for the full specification.

## License

Internal use only.
