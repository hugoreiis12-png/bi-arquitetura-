# Cline / Continue configuration

## Prerequisites

1. Install [Cline](https://marketplace.visualstudio.com/items?itemName=saoudrizwan.claude-dev) or [Continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue) extension
2. Authenticate with your AI provider (Anthropic, OpenAI, etc.)
3. Have `.vscode/mcp.json` configured (see file in this directory)

## Authentication flow

When you first use the MCP server, VSCode prompts for:
- Power BI credentials (Service Principal)
- Workspace IDs
- Redis, AI Search, App Insights connection strings

These are stored in `.vscode/mcp.json` and only requested once per workspace.

## System prompt for BI development

If you want to optimize AI behavior for BI, add this to your client settings:

```text
You are an expert Power BI developer assistant with access to MCP tools.

Project context:
- This is a Power BI Project (PBIP) using TMDL files for version control
- Code is reviewed via GitHub PRs before deployment
- DAX measures must follow naming convention: Domain.Name [format]
- Tables: f_<fact>, d_<dimension>, _aux_<helper>
- DAX smoke tests are required for every measure

Tool usage:
- Use pbi_list_datasets to see available datasets
- Use pbi_get_model_schema before suggesting changes
- Use pbi_validate_dax_syntax before proposing new measures
- Use pbi_propose_measure_update for write operations (creates PR)
- NEVER deploy directly - always via PR review
- For data modifications, prefer pbi_query_dax (read) over writes

Safety:
- All critical actions require approval tokens
- DLP blocks PII patterns - don't try to extract CPF/CNPJ/emails
- Stay within user's RBAC permissions
- When uncertain, ask the user to clarify
```

## Common Cline/Continue commands

```text
# Schema exploration
"conecta no Power BI Vendas e me dá um overview"
"lista as medidas de Vendas"
"qual a estrutura de d_cliente?"

# Measure creation
"cria uma medida Vendas.Ticket Médio [R$] que divide Receita por Pedidos"
"documenta a medida Vendas.Lucro Líquido BRL"

# Debug
"por que o refresh do Vendas tá lento?"
"verifica qualidade dos dados de f_vendas__pedido"
"essa query retorna o valor certo? EVALUATE ROW('x', [Vendas.Receita Total BRL])"

# Deploy
"promove PR #127 pra Test"
"faz rollback do último deploy em Dev"
"compara o modelo em Dev vs Prod"
```

## Troubleshooting

| Problem | Solution |
|---|---|
| MCP server not detected | Restart VSCode, check `.vscode/mcp.json` syntax |
| "Permission denied" | Check Azure AD group membership with admin |
| "Workspace not found" | Verify workspace ID in `.vscode/mcp.json` |
| Docker not found | Install Docker Desktop, or use HTTP mode |
| Tool fails silently | Check MCP server logs in VSCode Output panel |

## Alternative: HTTP mode (no Docker)

If you can't use Docker, run the MCP server directly:

```bash
cd mcp/powerbi-mcp-server
pip install -e .
powerbi-mcp --http --port 8000
```

Then in `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "powerbi": {
      "url": "http://localhost:8000/sse",
      "transport": "sse"
    }
  }
}
```
