# Arquitetura Detalhada

> Documento vivo. Última revisão: ver topo do README.

## 1. Princípios

1. **Código é a fonte da verdade.** Nada crítico vive no Power BI Service sem estar versionado.
2. **Tudo o que for texto é versionado.** TMDL, M, JSON, layouts de relatório, configurações de pipeline.
3. **Separação de responsabilidades.** Dataset (modelo) ≠ Report (visual). Shared ≠ Específico.
4. **Menor privilégio.** Service Principal com permissões mínimas. Rotação periódica.
5. **Promoção por aprovação.** Nada vai pra Prod sem sign-off explícito.
6. **Testes antes de publicação.** DAX smoke + data quality em todo PR.

## 2. Camadas

### 2.1 Camada de Autoria
- **Desenvolvedores BI** escrevem DAX, M, TMDL, layouts de relatório
- Trabalham localmente em branches, abrem PRs
- Cada dev tem seu próprio workspace Dev (ou compartilham via RLS)

### 2.2 Camada de Código
- Repositório Git no Azure DevOps ou GitHub
- Estrutura em pastas (ver README)
- PBIP em vez de PBIX — versionamento granular
- Conventional Commits + SemVer

### 2.3 Camada de Versionamento
- Branching: `main` (produção) ← `develop` (integração) ← `feat/*`, `fix/*`, `chore/*`
- Branch policy: build verde + 1 reviewer + linked work item
- Tags: `v1.2.3` — associadas a releases do Power BI Service

### 2.4 Camada de Orquestração (CI/CD)
- Pipeline disparado em PR (validate + test) e em push (deploy Dev)
- Promoção manual para Test/Prod via workflow_dispatch ou Deployment Pipeline
- Notificações no Teams

### 2.5 Camada de Runtime (Power BI Service)
- Workspaces espelhados: Dev / Test / Prod
- Deployment Pipeline nativo entre eles
- Refresh agendado + on-demand via REST
- Gateway para fontes on-premises

## 3. Diagrama de fluxo

```
[Dev BI local]
      │
      ├── git push ─────┐
      │                 ▼
      │            [PR + Review]
      │                 │
      │                 ▼
      │            [Build pipeline]
      │              ├── validate TMDL
      │              ├── compile PBIP
      │              └── dax smoke tests
      │                 │
      │                 ▼
      │            [Merge em main]
      │                 │
      │                 ▼
      │            [Deploy Dev workspace]   ◀─── automático
      │                 │
      │                 ▼
      │            [QA valida em Dev]
      │                 │
      │                 ▼
      │            [Aprova promoção]
      │                 │
      │                 ▼
      │            [Deploy Test workspace]  ◀─── manual / pipeline
      │                 │
      │                 ▼
      │            [Steward aprova]
      │                 │
      │                 ▼
      │            [Deploy Prod workspace]  ◀─── manual / pipeline
      │                 │
      │                 ▼
      └──────────► [Refresh + Monitor]
```

## 4. Decisões técnicas (ADRs)

### ADR-001: PBIP em vez de PBIX
- **Status:** Aceito
- **Contexto:** PBIX é binário e impede diffs legíveis
- **Decisão:** Toda nova autoria usa PBIP. Migração gradual do legado.
- **Consequências:** Requer Power BI Desktop recente. Conflitos TMDL exigem treinamento.

### ADR-002: Três ambientes
- **Status:** Aceito
- **Contexto:** Produção precisa de isolamento
- **Decisão:** Dev → Test → Prod, cada um com workspace e SP próprios
- **Consequências:** Custo de licenciamento maior. Necessidade de rotação de SP.

### ADR-003: pbi-tools como CLI oficial
- **Status:** Aceito
- **Contexto:** Necessidade de automação via linha de comando
- **Decisão:** Adotar `pbi-tools` (Microsoft) como CLI padrão
- **Consequências:** Dependência externa (mas oficial). Versionamento fixo no pipeline.

### ADR-004: DAX smoke tests obrigatórios
- **Status:** Aceito
- **Contexto:** DAX é difícil de revisar só lendo
- **Decisão:** Toda medida nova roda smoke test antes de merge
- **Consequências:** Cria catálogo de medidas em `tests/dax/`. Aumenta tempo de CI.
