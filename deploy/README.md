# Deploy Configuration

> Pasta espelha os workspaces do Power BI Service. Cada subpasta tem configs
> do ambiente correspondente (Dev, Test, Prod).

## Estrutura

```
deploy/
├── dev/    # Service Principal A, workspace Dev, refresh sob demanda
├── test/   # Service Principal B, workspace Test, refresh a cada hora
└── prod/   # Service Principal C, workspace Prod, refresh agendado pelo steward
```

## O que versionar aqui

✅ **SIM:**
- `config.json` com `workspaceId`, regiões permitidas, política de refresh
- `service-principal.json.template` (template, sem secrets)
- `runbook.md` (procedimento de operação)
- Tags e group IDs em metadata

❌ **NÃO:**
- Segredos de SP (vão no Azure Key Vault / GitHub Secrets)
- IDs específicos em produção sem aprovação
- Senhas, tokens, connection strings

## Exemplo `config.json`

```json
{
  "environment": "dev",
  "workspaceId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "workspaceName": "[DEV] Vendas",
  "servicePrincipalId": "${PBI_SP_DEV_CLIENT_ID}",
  "refreshPolicy": {
    "type": "on-demand",
    "schedule": null,
    "maxRetries": 3
  },
  "approvers": [
    "líder-tecnico@empresa.com"
  ],
  "alerts": {
    "teams": "https://outlook.office.com/webhook/...",
    "emailOnFailure": ["oncall-bi@empresa.com"]
  }
}
```
