# Arquitetura IDE · Power BI

> Repositório-modelo para conduzir projetos de BI no padrão de engenharia de software, usando **Power BI Project (PBIP)** como fonte da verdade, **Git** para versionamento e **CI/CD** para promoção entre ambientes.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Objetivo](#objetivo)
- [Stack](#stack)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Quickstart (do zero)](#quickstart-do-zero)
- [Fluxo de Trabalho](#fluxo-de-trabalho)
- [Arquitetura de Camadas](#arquitetura-de-camadas)
- [Camada de IA (MCP + ORM)](#camada-de-ia-mcp--orm)
- [Testes](#testes)
- [CI/CD](#cicd)
- [Segurança](#segurança)
- [Multi-Projeto (Portfolio)](#multi-projeto-portfolio)
- [CLI `bi`](#cli-bi)
- [Conectando IA ao Projeto](#conectando-ia-ao-projeto)
- [Documentação](#documentação)
- [Roadmap de Adoção](#roadmap-de-adoção)
- [Contribuindo](#contribuindo)
- [Licença](#licença)

---

## Visão Geral

Este scaffolding transforma o desenvolvimento Power BI de um processo manual e individual em uma **prática de engenharia** com versionamento granular, testes automatizados e deploy controlado.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ARQUITETURA IDE · POWER BI                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  AUTHORING   │  │    CODE     │  │  VERSIONING │  │    CI/CD  │ │
│  │             │  │             │  │             │  │           │ │
│  │  Desktop    │  │  Git        │  │  Branches   │  │  Actions  │ │
│  │  Tab. Editor│  │  TMDL       │  │  Tags       │  │  Deploy   │ │
│  │  DAX Studio │  │  PBIP       │  │  SemVer     │  │  Gates    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘ │
│         │                │                │               │        │
│         └────────────────┴────────────────┴───────────────┘        │
│                              │                                     │
│                    ┌─────────▼─────────┐                           │
│                    │   RUNTIME (PBI)   │                           │
│                    │   Service / FABRIC│                           │
│                    └───────────────────┘                           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    CAMADA DE IA                             │   │
│  │  MCP Server · ORM SDK · DAX Validator · RBAC · Guardrails  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Objetivo

Padronizar o desenvolvimento de soluções Power BI em uma estrutura que permita:

- **Versionamento granular** (DAX, M, TMDL, layouts de relatório) linha-a-linha
- **Reprodutibilidade** de qualquer ambiente a partir do código
- **Testes automatizados** antes de promover mudanças
- **Deploy controlado** entre Dev → Test → Prod
- **Trabalho em equipe** sem sobrescrita destrutiva
- **Governança e auditoria** (quem mudou o quê, quando, por quê)

---

## Stack

| Camada | Ferramenta | Papel |
|---|---|---|
| Edição de modelo | **Tabular Editor 3** + **TMDL** | Edição em massa, C# scripts |
| Edição de código | **VS Code** | IntelliSense, lint, format |
| Editor visual | **Power BI Desktop** (PBIP mode) | Layout do relatório, preview |
| Profiling | **DAX Studio** | Performance, métricas, query plans |
| CLI | **pbi-tools** (Microsoft) | Compile / extract / deploy via linha de comando |
| Merge/Compare | **ALM Toolkit** | Resolução fina de conflitos entre datasets |
| Versionamento | **Git** + **Azure DevOps / GitHub** | Repositório, PRs, branch policies |
| CI/CD | **Azure Pipelines** ou **GitHub Actions** | Build, test, deploy |
| Runtime | **Power BI Service** + **Deployment Pipelines** | Promoção Dev/Test/Prod |
| IA (MCP) | **FastMCP** + **Python** | Bridge IDE↔Power BI |
| IA (ORM) | **powerbi-orm** | SDK Python para TOM/TMDL/XMLA |

---

## Estrutura do Repositório

```
.
├── src/
│   ├── datasets/        # Modelos semânticos (.Dataset em PBIP)
│   ├── reports/         # Relatórios (.Report em PBIP)
│   ├── dataflows/       # Dataflow Gen2 definitions
│   ├── shared/          # Medidas, calendário, funções compartilhadas
│   └── pipelines/       # Data pipelines (Fabric / ADF)
├── docs/                # Arquitetura, convenções, dicionário de dados
├── tests/
│   ├── dax/             # DAX smoke tests
│   └── data-quality/    # Testes de qualidade de dados
├── deploy/
│   ├── dev/             # Configs/segredos do workspace Dev
│   ├── test/            # Configs/segredos do workspace Test
│   └── prod/            # Configs/segredos do workspace Prod
├── scripts/             # PowerShell e Bash para automação local
├── mcp/                 # MCP Server (bridge IDE↔Power BI)
├── tools/               # SDKs e ferramentas (ORM, validators)
├── .github/workflows/   # Pipelines do GitHub Actions
├── .vscode/             # Configurações versionadas da IDE
├── .gitignore
├── .gitattributes
├── CONTRIBUTING.md      # Guia de contribuição
├── TROUBLESHOOTING.md   # Solução de problemas
├── CHANGELOG.md         # Histórico de versões
└── README.md            # Este arquivo
```

---

## Quickstart (do zero)

### 1. Pré-requisitos

- Windows 10/11 ou Windows Server
- **Power BI Desktop** ≥ 2.121 (com PBIP save mode ativado)
- **VS Code** ≥ 1.85
- **Tabular Editor 3** (licença Community para uso não-comercial)
- **DAX Studio** (latest)
- **Git** + acesso a Azure DevOps ou GitHub
- **pbi-tools** instalado:
  ```powershell
  dotnet tool install --global Microsoft.PowerBI.Tools
  ```

### 2. Habilitar PBIP no Power BI Desktop

`File → Options → Preview features → Power BI Project (.pbip) save mode` ✅

### 3. Clonar o repositório

```bash
git clone https://github.com/sua-org/bi-ide-architecture.git
cd bi-ide-architecture
code .
```

### 4. Configurar o VS Code

Ao abrir, as extensions recomendadas aparecem automaticamente. Aceite todas.

### 5. Criar um dataset no formato PBIP

No Power BI Desktop:
1. Crie / abra o `.pbix` que vai virar PBIP
2. `File → Save As → escolha "Power BI Project (.pbip)"`
3. Salve dentro de `src/datasets/`

Resultado: o Desktop cria a pasta `.Dataset` ao lado do `.pbip`.

### 6. Trabalhar com Git

```bash
git checkout -b feat/calendario-fiscal
# edite os .tmdl
git add .
git commit -m "feat: adiciona tabela calendario fiscal com offset"
git push origin feat/calendario-fiscal
# abra PR
```

### 7. Deploy automatizado

Ao dar merge em `main`, o pipeline:
1. Compila os PBIPs com `pbi-tools compile`
2. Roda DAX smoke tests
3. Publica no workspace Dev
4. Notifica no Teams

Promoção para Test/Prod é manual via Deployment Pipeline ou `scripts/promote.ps1`.

---

## Fluxo de Trabalho

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  AUTHOR   │────▶│   CODE   │────▶│  REVIEW  │────▶│  DEPLOY  │
│          │     │          │     │          │     │          │
│ Desktop  │     │  Git     │     │  PR +    │     │  CI/CD   │
│ Tab.Ed   │     │  TMDL    │     │  Review  │     │  Pipeline│
│ DAX.St   │     │  PBIP    │     │  Tests   │     │  Gates   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                        │
                                        ▼
                                 ┌──────────┐
                                 │  MERGE   │
                                 │          │
                                 │ develop  │
                                 │    ↓     │
                                 │  main    │
                                 └──────────┘
```

### Branching Model

```
main ← develop ← feat/*, fix/*, chore/*, docs/*
```

- `main` → Produção (protegido, deploy automático)
- `develop` → Desenvolvimento (merge de features)
- `feat/*` → Funcionalidades novas
- `fix/*` → Correções de bugs
- `chore/*` → Tarefas de manutenção
- `docs/*` → Documentação

### Conventional Commits

```
feat(vendas): adiciona medida Margem Líquida
fix(dax): corrige divisão por zero em Ticket Médio
docs(api): documenta novos endpoints do MCP
chore(deps): atualiza powerbi-orm para v0.4.1
```

---

## Arquitetura de Camadas

| Camada | Responsabilidade | Ferramentas |
|--------|------------------|-------------|
| **Authoring** | Criação e edição de modelos | Desktop, Tabular Editor, DAX Studio |
| **Code** | Armazenamento fonte da verdade | Git, TMDL, PBIP |
| **Versioning** | Controle de versões e tags | Git, SemVer, Conventional Commits |
| **Orchestration** | CI/CD e promoção | GitHub Actions, Deployment Pipelines |
| **Runtime** | Execução e serving | Power BI Service, Fabric |

### Convenções de Nomenclatura

| Elemento | Padrão | Exemplo |
|----------|--------|---------|
| Tabela fato | substantivo de negócio | `Vendas`, `Estoque` |
| Tabela dimensão | substantivo singular | `Produto`, `Cliente` |
| Tabela técnica | prefixo `_`, oculta | `_Medidas`, `_Parâmetros` |
| Coluna | linguagem de negócio | `Data do Pedido`, `Valor Total` |
| Medida | substantivo do que mede | `Faturamento`, `Ticket Médio` |
| Chave surrogate | sufixo consistente | `Produto SK` (oculta) |

---

## Camada de IA (MCP + ORM)

### MCP Server (`mcp/powerbi-mcp-server/`)

Bridge entre IDE (Cline, Continue, Claude Desktop) e Power BI Service.

**Tools disponíveis**:

| Tool | Risco | Descrição |
|------|-------|-----------|
| `list_workspaces` | 🟢 Safe | Lista workspaces acessíveis |
| `list_reports` | 🟢 Safe | Lista relatórios de um workspace |
| `list_datasets` | 🟢 Safe | Lista datasets de um workspace |
| `get_dataset_schema` | 🟢 Safe | Retorna schema do modelo |
| `validate_dax` | 🟢 Safe | Valida sintaxe e padrões DAX |
| `execute_dax_query` | 🟡 Moderate | Executa query DAX |
| `create_or_update_measure` | 🟡 Moderate | Cria/atualiza medida |
| `deploy_dataset` | 🔴 Dangerous | Publica dataset no workspace |
| `delete_dataset` | 🔴 Critical | Remove dataset do workspace |
| `manage_roles` | 🔴 Critical | Gerencia roles RLS |

**Guardrails** (7 camadas):
1. **RBAC** — Controle de acesso por role
2. **Rate Limit** — Limitação de requisições
3. **Audit** — Log de todas as operações
4. **DLP** — Prevenção de perda de dados
5. **Approval** — Aprovação para operações críticas
6. **Naming Lint** — Validação de convenções
7. **Anti-patterns** — Detecção de práticas inadequadas

### ORM SDK (`tools/orm/`)

SDK Python para manipulação de modelos tabulares.

```python
from powerbi_orm import Dataset, Table, Column, Measure

# Conectar ao modelo
dataset = Dataset.from_pbip("./src/datasets/Vendas.Dataset")

# Manipular objetos
tabela = dataset.tables["Vendas"]
coluna = Column(name="Receita", dataType="decimal")
medida = Measure(name="Receita Total", expression="SUM(Vendas[Receita])")

# Commit via ORM
dataset.commit(message="feat: adiciona medida Receita Total")
```

**Classes disponíveis**: Dataset, Table, Column, Measure, Relationship, Role

---

## Testes

### DAX Smoke Tests

Localizados em `tests/dax/`. Executados pelo DAX Studio em modo "Execute" no pipeline.

```dax
// tests/dax/01-medidas-basicas.dax
EVALUATE
ROW(
    "Receita Total", [Receita Total],
    "Margem %", DIVIDE([Lucro], [Receita], 0),
    "Ticket Medio", DIVIDE([Receita], DISTINCTCOUNT('Vendas'[PedidoId]), 0)
)
```

### Validação DAX (MCP Server)

O validador DAX analisa em 7 dimensões:
1. **Sintaxe** — Parênteses, vírgulas, nomes
2. **Semântica** — Tipos de dados, colunas existentes
3. **Performance** — anti-patterns (FILTER sobre tabela inteira, etc.)
4. **Escopo** — Medidas referenciadas existem?
5. **RLS** — Compatibilidade com roles
6. **Nomenclatura** — Convenções do projeto
7. **Anti-patterns** — LOOKUPVALUE vs RELATED, etc.

### Data Quality

`tests/data-quality/` segue padrão Great Expectations ou SodaCL — executado antes do deploy para garantir integridade do ETL.

---

## CI/CD

Pipeline completa documentada em `docs/ci-cd.md`.

### Pipeline Resumida

```
PR/merge → validate → build → deploy-dev → manual-approval → deploy-test → manual-approval → deploy-prod
```

### Jobs

| Job | Trigger | O que faz |
|-----|---------|-----------|
| `validate` | push PR | Valida TMDL, lint, estrutura |
| `build` | PR merge | Compila PBIPs, smoke tests |
| `deploy-dev` | merge main | Publica no workspace Dev |
| `deploy-test` | manual | Publica no workspace Test |
| `deploy-prod` | manual | Publica no workspace Prod |

### Secrets Necessários

| Secret | Descrição |
|--------|-----------|
| `AZURE_SP_DEV_CLIENT_ID` | Client ID do SP Dev |
| `AZURE_SP_DEV_CLIENT_SECRET` | Client Secret do SP Dev |
| `AZURE_TENANT_ID` | Tenant ID Azure |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID Azure |
| `PBI_WORKSPACE_ID_DEV` | Workspace Dev |
| `PBI_WORKSPACE_ID_TEST` | Workspace Test |
| `PBI_WORKSPACE_ID_PROD` | Workspace Prod |

---

## Segurança

- **Service Principal por ambiente**: um SP exclusivo para Dev, Test e Prod
- **Princípio do menor privilégio**: SPs só conseguem publicar nos workspaces permitidos
- **Segredos em Azure Key Vault** ou GitHub Secrets (nunca no repo)
- **Rotação trimestral** de credenciais
- **IP allowlist** quando possível (Power BI Premium)
- **RLS versionado** no Git e publicado via CI/CD

---

## Multi-Projeto (Portfolio)

**Esta arquitetura é adaptativa a múltiplos projetos BI.** Você não precisa recriar tudo a cada novo BI — use este scaffolding como **Template Repo** e customize em cima.

Três padrões possíveis (ver `portfolio/README.md`):

| Padrão | Descrição | Escala |
|--------|-----------|--------|
| **Monorepo** | Todos os BIs num único repo | Até ~5 projetos |
| **Template + Polyrepo** ⭐ | Um repo por BI, clonados deste template | 5–15 projetos |
| **Federado** ⭐⭐ | Template + biblioteca central compartilhada | > 15 projetos |

O `portfolio/` deste scaffolding já vem com:
- Catálogo de projetos (`catalog/projects.json` com schema validável)
- Biblioteca compartilhada (TMDL, scripts, CI/CD reutilizável)
- Governança transversal (`governanca/multi-project-checklist.md`)

---

## CLI `bi`

Wrapper unificado que combina MCP server, ORM SDK e scripts de operação.

```bash
# Adicione ao PATH ou use direto
export PATH="$PWD/scripts:$PATH"

# Diagnóstico
bi doctor
bi status

# Operações
bi extract --workspace X --dataset Y --generate-docs
bi validate dax measure.dax --measure-name "Vendas.X"
bi ask "qual a estrutura de d_cliente?"
bi deploy --pr 127 --env test
bi review --pr 127

# Tokens de aprovação
bi token issue --action deploy_prod --target "PR#127" --reason "Hotfix"
bi token approve --token apv_xxx --approver-id maria@empresa.com

# MCP server
bi server start
bi server logs
bi server stop
```

---

## Conectando IA ao Projeto

| Forma | Comando | Quando usar |
|---|---|---|
| **`bi` CLI** (projeto) | `bi ask "..."`, `bi deploy ...` | Terminal local, git hooks, CI |
| **MCP server** (rede) | Já construído em `mcp/` | Cline, Continue, Claude Desktop, qualquer cliente MCP |

### Configuração MCP no VS Code

```json
// .vscode/mcp.json
{
  "servers": {
    "powerbi-mcp": {
      "command": "powerbi-mcp",
      "args": ["--http", "--port", "8000"],
      "env": {
        "PBI_TENANT_ID": "${env:PBI_TENANT_ID}",
        "PBI_SP_CLIENT_ID": "${env:PBI_SP_CLIENT_ID}",
        "PBI_SP_CLIENT_SECRET": "${env:PBI_SP_CLIENT_SECRET}"
      }
    }
  }
}
```

---

## Documentação

### Documentos Principais

| Documento | Descrição |
|-----------|-----------|
| [`docs/architecture.md`](docs/architecture.md) | Arquitetura detalhada, 5 camadas, ADRs |
| [`docs/naming-conventions.md`](docs/naming-conventions.md) | Padrões de nomenclatura |
| [`docs/data-dictionary.md`](docs/data-dictionary.md) | Catálogo de tabelas e medidas |
| [`docs/ci-cd.md`](docs/ci-cd.md) | Pipeline CI/CD completa |
| [`docs/ai-architecture/`](docs/ai-architecture/) | Arquitetura da camada de IA |
| [`docs/convenções_qualidade.md`](docs/convenções_qualidade.md) | Convenções de qualidade |

### Guias

| Documento | Descrição |
|-----------|-----------|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Guia de contribuição |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | Solução de problemas |
| [`CHANGELOG.md`](CHANGELOG.md) | Histórico de versões |

### Tutoriais

| Documento | Descrição |
|-----------|-----------|
| [`docs/tutorials/00-do-zero-ao-deploy.md`](docs/tutorials/00-do-zero-ao-deploy.md) | Tutorial completo: do zero ao deploy |

---

## Roadmap de Adoção

| Fase | Entrega | Duração estimada |
|---|---|---|
| **0 · Setup** | Repo, IDE, PBIP habilitado, .gitignore | 1 dia |
| **1 · Fundação** | 1 projeto-piloto migrado pra PBIP, SP Dev, deploy REST | 1 semana |
| **2 · CI/CD** | Pipeline completo, smoke tests, branch policies | 2 semanas |
| **3 · Multi-ambiente** | Promoção Test/Prod, RLS versionado, alertas | 2 semanas |
| **4 · Escala (multi-projeto)** | Template repo + portfolio catalog | contínuo |
| **5 · IA** | MCP server, ORM, validação DAX, assistente AI | contínuo |

---

## Contribuindo

Consulte [`CONTRIBUTING.md`](CONTRIBUTING.md) para o guia completo de contribuição.

Resumo rápido:
1. Fork/Clone o repositório
2. Crie uma branch de feature (`feat/*`, `fix/*`, `chore/*`)
3. Implemente suas mudanças
4. Adicione testes se aplicável
5. Atualize a documentação
6. Abra um Pull Request
7. Aguarde code review e aprovação

---

## Licença

Uso interno. Power BI, pbi-tools, Tabular Editor, DAX Studio e demais marcas pertencem a seus respectivos donos.
