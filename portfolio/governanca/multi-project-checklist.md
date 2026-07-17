# 🛡️ Governança Multi-Projeto

> Como garantir que todos os projetos BI sigam o mesmo padrão.

## 1. Convenções que devem ser iguais em TODOS os projetos

| Item | Onde vive | Quem mantém |
|---|---|---|
| Padrão de nomenclatura | `bi-shared-library/padroes/` | Steward de Dados |
| Templates TMDL | `bi-shared-library/tmdl/` | Analytics Engineer |
| Scripts PowerShell | `bi-shared-library/scripts-ps1/` | Platform / DevOps |
| CI/CD workflows | `bi-shared-library/ci-cd/` | DevOps |
| PR template | `bi-template/.github/PULL_REQUEST_TEMPLATE.md` | Tech Lead |
| dax-smoke-tests pattern | `bi-template/tests/dax/README.md` | Analytics Engineer |
| Schema do catalog | `bi-portfolio-catalog/catalog/projects.schema.json` | DevOps |

## 2. Reusable Workflows (GitHub Actions)

Projetos **não** duplicam CI. Eles consomem:

```yaml
# .github/workflows/bi-ci-cd.yml do projeto
name: BI CI/CD
on:
  pull_request: { branches: [main] }
  push:        { branches: [main] }

jobs:
  validate:
    uses: org/bi-shared-library/.github/workflows/validate.yml@v2.1.0
    with:
      datasets-path: src/datasets
      tests-path: tests/dax
      fail-on-warnings: true
  # ... demais jobs
```

Resultado: 1 melhoria no CI propaga para **todos** os projetos automaticamente.

## 3. Auditoria mensal

Todo mês, rodar:

```bash
# Em cada projeto, comparar padrões esperados vs encontrados
for proj in bi-vendas bi-estoque bi-rh; do
  echo "=== $proj ==="
  cd $proj
  # 1. Estrutura de pastas está conforme template?
  # 2. Tem smoke tests?
  # 3. Tem data-dictionary atualizado?
  # 4. CI está consumindo shared-lib na latest?
  # 5. Tem RLS documentado?
done
```

Script sugerido: `tools/audit-portfolio.sh` no repo de catalog.

## 4. Decisões que devem ser uniformes

- **PBIP em vez de PBIX** → aplicável a todos
- **3 ambientes (Dev/Test/Prod)** → aplicável a todos
- **Service Principal por ambiente** → aplicável a todos
- **RLS versionado em TMDL** → aplicável a todos
- **Smoke tests antes de merge** → aplicável a todos
- **Conventional Commits** → aplicável a todos
- **Changelog atualizado** → aplicável a todos

## 5. Decisões que podem variar por projeto

- Linguagem (PT/EN) das medidas
- Granularidade de catálogo
- Política de refresh (scheduled vs on-demand)
- Workspace capacity (Premium vs Embedded vs Fabric)
- Tags / domínios de negócio
- Ferramenta de ticket (Jira, Azure Boards, GitHub Issues)

## 6. Onboarding de novo projeto BI

**Checklist do tech lead:**

- [ ] Projeto criado a partir do template `bi-template`
- [ ] Repo privado no org, com branch protection
- [ ] `deploy/{dev,test,prod}/config.json` preenchido
- [ ] 3 service principals criados (Dev/Test/Prod) com permissão no workspace
- [ ] Workspace Dev/Test/Prod criados no Power BI Service
- [ ] Segredos configurados no GitHub Secrets
- [ ] Pipeline executou pelo menos 1x com sucesso
- [ ] PR de catálogo aberto no `bi-portfolio-catalog` (adicionando o projeto)
- [ ] Steward e owner designados
- [ ] Data dictionary criado e primeira tabela populada
- [ ] Smoke tests básicos escritos
- [ ] Onboard do time (pair programming no primeiro PR)

Tempo estimado: **meio período a 1 dia**.
