# CI/CD — Detalhamento

> Como funciona o pipeline, gates de qualidade e processo de promoção.

## 1. Pipeline em estágios

### 1.1 `validate` (todo PR)
- **Trigger:** PR aberto/atualizado
- **Runner:** `windows-latest`
- **Passos:**
  1. Checkout
  2. Setup .NET
  3. Install pbi-tools
  4. Compila todos os PBIPs em `src/datasets/`
  5. Falha se schema TMDL inválido
- **Artefato:** `pbip-build` (pasta `build/`)

### 1.2 `dax-tests` (todo PR)
- **Trigger:** Após `validate`
- **Passos:**
  1. Lista arquivos em `tests/dax/*.dax`
  2. Para cada um, valida sintaxe e mostra resultado
  3. Falha se algum teste falhar

### 1.3 `deploy-dev` (push em main)
- **Trigger:** Merge na main
- **Requer:** `validate` + `dax-tests` verdes
- **Environment:** `dev` (com 0 aprovadores necessários — auto-deploy)
- **Passos:**
  1. Login com Service Principal Dev (Azure)
  2. Publica PBIP no workspace Dev
  3. Dispara refresh
  4. Notifica Teams

### 1.4 `promote` (manual)
- **Trigger:** `workflow_dispatch` com input `target_env`
- **Requer:** Aprovação manual via GitHub Environment
- **Passos:**
  1. Aguarda aprovação
  2. Publica no workspace alvo (Test ou Prod)
  3. Notifica Teams

## 2. Gates de qualidade

| Gate | Bloqueia merge? | Ferramenta |
|---|---|---|
| Compilação TMDL | ✅ | `pbi-tools compile` |
| Smoke tests DAX | ✅ | DAX Studio + scripts |
| Linter de naming | ✅ | Power BI Project Tools |
| Code review (1 reviewer) | ✅ | GitHub PR / Azure DevOps |
| Build verde | ✅ | GitHub Actions |
| Atualização do data-dictionary | ⚠️ Recomendado | PR template |

## 3. Segredos necessários

Configure no GitHub (`Settings → Secrets and variables → Actions`):

| Secret | Descrição |
|---|---|
| `AZURE_TENANT_ID` | Tenant do Azure AD |
| `AZURE_SUBSCRIPTION_ID` | Subscription com o Power BI |
| `AZURE_SP_DEV_CLIENT_ID` | Service Principal Dev |
| `AZURE_SP_DEV_CLIENT_SECRET` | Segredo do SP Dev |
| `AZURE_SP_TEST_CLIENT_ID` | Service Principal Test |
| `AZURE_SP_TEST_CLIENT_SECRET` | Segredo do SP Test |
| `AZURE_SP_PROD_CLIENT_ID` | Service Principal Prod |
| `AZURE_SP_PROD_CLIENT_SECRET` | Segredo do SP Prod |
| `WORKSPACE_ID_DEV` | ID do workspace Dev |
| `WORKSPACE_ID_TEST` | ID do workspace Test |
| `WORKSPACE_ID_PROD` | ID do workspace Prod |
| `TEAMS_WEBHOOK` | URL do webhook do Teams |

## 4. Promoção manual

### 4.1 Via GitHub Actions
1. Acesse a aba `Actions`
2. Selecione `BI CI/CD`
3. `Run workflow`
4. Escolha `target_env` = `test` ou `prod`
5. Confirme

### 4.2 Via Power BI Deployment Pipeline
1. Acesse https://app.powerbi.com → pipelines
2. Selecione o pipeline do projeto
3. `Deploy` na coluna Dev → Test
4. Validação manual em Test
5. `Deploy` Test → Prod (com aprovação do steward)

### 4.3 Via CLI local (emergência)
```powershell
.\scripts\publish.ps1 `
  -DatasetPath "src/datasets/Vendas.Dataset" `
  -WorkspaceId "xxxx-yyyy-zzzz" `
  -Environment prod
```

## 5. Rollback

### 5.1 Rollback de dataset
```powershell
# Volta o workspace Prod para a versão anterior
.\scripts\publish.ps1 `
  -DatasetPath "src/datasets/Vendas.Dataset" `
  -WorkspaceId $prodWsId `
  -Environment prod `
  -Conflict replace
```

### 5.2 Rollback de report
- Reverte o PR no Git
- Re-deploy automático no próximo push em main

### 5.3 Rollback de dados
- Não é coberto por este pipeline. Acionar refresh do snapshot anterior via REST.

## 6. Monitoramento pós-deploy

| Sinal | Como monitorar | Ação |
|---|---|---|
| Refresh falhou | Power BI Activity Log + alert | Acionar runbook |
| Tempo de refresh alto | Power BI Premium Metrics | Investigar measures |
| Erro 5xx no REST | Application Insights | Reverter deployment |
| RLS não funciona | Teste manual com usuário | Re-publicar com fix de role |
