# Bootstrap scripts

## `bootstrap-mcp-infra.ps1`

Provisiona toda a infraestrutura necessária pro MCP server rodar no Azure.

### O que cria

- ✅ Resource Group
- ✅ VNet + Subnet dedicada
- ✅ Application Insights
- ✅ Key Vault
- ✅ Azure Cache for Redis
- ✅ Azure AI Search (RAG)
- ✅ Container Apps Environment
- ✅ Service Principal dedicado
- ✅ 5 Azure AD groups (RBAC)
- 📋 Power BI workspaces (manual)

### Pré-requisitos

- Azure CLI instalado e autenticado (`az login`)
- Permissões: Owner ou Contributor na subscription
- PowerShell 7+ (ou PowerShell Core)

### Uso

```powershell
.\bootstrap-mcp-infra.ps1 `
  -SubscriptionId "abc-123-xyz" `
  -ResourceGroupName "rg-bi-mcp-dev" `
  -Location "eastus" `
  -Environment "dev" `
  -PowerBIWorkspaceDev "[DEV] Vendas" `
  -PowerBIWorkspaceTest "[TEST] Vendas" `
  -PowerBIWorkspaceProd "Vendas" `
  -PowerBIWorkspacePlayground "[AI-PLAYGROUND] Vendas"
```

### Output

Gera arquivo `.bootstrap-config-dev.json` com:
- IDs de todos os recursos
- Connection strings
- IDs de SP
- URLs de endpoints

Use esses valores pra configurar o `.env` do MCP server e os secrets do CI/CD.

### Idempotência

O script é idempotente — pode rodar múltiplas vezes. Recursos existentes são pulados.

### Custos estimados

| Recurso | SKU | Custo mensal |
|---|---|---|
| App Insights | — | ~$5 |
| Key Vault | Standard | ~$1 |
| Redis Basic C0 | Basic | ~$15 |
| AI Search | Standard S1 | ~$250 |
| Container Apps | Consumption | ~$30 (1-3 réplicas) |
| **Total** | | **~$300/mês** |

(Exclui Power BI Premium que já existe.)
