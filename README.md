# 🧱 Arquitetura IDE · Power BI

> Repositório-modelo para conduzir projetos de BI no padrão de engenharia de software, usando **Power BI Project (PBIP)** como fonte da verdade, **Git** para versionamento e **CI/CD** para promoção entre ambientes.

---

## 🎯 Objetivo

Padronizar o desenvolvimento de soluções Power BI em uma estrutura que permita:

- 📁 **Versionamento granular** (DAX, M, TMDL, layouts de relatório) linha-a-linha
- 🔁 **Reprodutibilidade** de qualquer ambiente a partir do código
- 🧪 **Testes automatizados** antes de promover mudanças
- 🚀 **Deploy controlado** entre Dev → Test → Prod
- 👥 **Trabalho em equipe** sem sobrescrita destrutiva
- 🛡️ **Governança e auditoria** (quem mudou o quê, quando, por quê)

---

## 🧰 Stack

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

---

## 📂 Estrutura

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
├── .github/workflows/   # Pipelines do GitHub Actions (ou azure-pipelines.yml)
├── .vscode/             # Configurações versionadas da IDE
├── .gitignore
├── .gitattributes
└── README.md
```

---

## 🚀 Quickstart (do zero)

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
git clone https://dev.azure.com/sua-org/seu-projeto/_git/bi-ide-architecture
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

## 🧪 Testes

### DAX Smoke Tests
Localizados em `tests/dax/`. Executados pelo DAX Studio em modo "Execute" no pipeline. Exemplo:

```dax
// tests/dax/01-medidas-basicas.dax
EVALUATE
ROW(
    "Receita Total", [Receita Total],
    "Margem %", DIVIDE([Lucro], [Receita], 0),
    "Ticket Medio", DIVIDE([Receita], DISTINCTCOUNT('Vendas'[PedidoId]), 0)
)
```

### Data Quality
`tests/data-quality/` segue padrão Great Expectations ou SodaCL — executado antes do deploy para garantir integridade do ETL.

---

## 🔐 Segurança

- **Service Principal por ambiente**: um SP exclusivo para Dev, Test e Prod
- **Princípio do menor privilégio**: SPs só conseguem publicar nos workspaces permitidos
- **Segredos em Azure Key Vault** ou GitHub Secrets (nunca no repo)
- **Rotação trimestral** de credenciais
- **IP allowlist** quando possível (Power BI Premium)

---

## 📋 Documentação auxiliar

- [`docs/architecture.md`](docs/architecture.md) — desenho detalhado
- [`docs/naming-conventions.md`](docs/naming-conventions.md) — padrões de nomenclatura
- [`docs/data-dictionary.md`](docs/data-dictionary.md) — catálogo de tabelas e medidas
- [`docs/ci-cd.md`](docs/ci-cd.md) — detalhamento do pipeline

---

## 📈 Roadmap de adoção

| Fase | Entrega | Duração estimada |
|---|---|---|
| **0 · Setup** | Repo, IDE, PBIP habilitado, .gitignore | 1 dia |
| **1 · Fundação** | 1 projeto-piloto migrado pra PBIP, SP Dev, deploy REST | 1 semana |
| **2 · CI/CD** | Pipeline completo, smoke tests, branch policies | 2 semanas |
| **3 · Multi-ambiente** | Promoção Test/Prod, RLS versionado, alertas | 2 semanas |
| **4 · Escala (multi-projeto)** | Template repo + portfolio catalog | contínuo |

## 🧬 Multi-projeto (portfolio)

**Esta arquitetura é adaptativa a múltiplos projetos BI.** Você não precisa recriar tudo a cada novo BI — use este scaffolding como **Template Repo** e customize em cima.

Três padrões possíveis (ver `portfolio/README.md`):

- **Monorepo** — todos os BIs num único repo. Bom até ~5 projetos.
- **Template + Polyrepo** ⭐ — um repo por BI, todos clonados deste template. Bom para 5–15 projetos.
- **Federado** ⭐⭐ — Template + biblioteca central compartilhada. Bom para > 15 projetos.

O `portfolio/` deste scaffolding já vem com:
- Catálogo de projetos (`catalog/projects.json` com schema validável)
- Biblioteca compartilhada (TMDL, scripts, CI/CD reutilizável)
- Governança transversal (`governanca/multi-project-checklist.md`)

---

## 📄 Licença

Uso interno. Power BI, pbi-tools, Tabular Editor, DAX Studio e demais marcas pertencem a seus respectivos donos.

---

## 📦 Pacote de Implementação (código real)

Este repositório contém **código Python pronto pra rodar**, não apenas spec:

### `mcp/powerbi-mcp-server/`
MCP server completo com FastMCP:
- 12 tools (5 safe + 2 moderate + 1 dangerous + 2 critical)
- 7 camadas de guardrail (RBAC, rate limit, audit, DLP, approval, network, auth)
- CLI admin pra tokens de aprovação
- Validação DAX em 6 dimensões
- Dockerfile + deploy config
- 16 testes unitários

### `tools/orm/`
SDK Python `powerbi-orm`:
- Classes: Dataset, Table, Column, Measure, Relationship, Role
- Conexão XMLA + REST API
- Geração de TMDL a partir de objetos Python
- Commit + PR via git
- 15+ testes unitários

### `scripts/extract/extract_from_powerbi.py`
O "baixa tudo do Power BI pra cá":
- Conecta via Service Principal
- Lista datasets do workspace
- Extrai TMDL via pbi-tools
- Gera overview.yaml, README.md, data-dictionary.md
- Commit inicial opcional

### `scripts/bootstrap/bootstrap-mcp-infra.ps1`
Provisiona toda a infra Azure num comando:
- Resource Group, VNet, Subnet
- Container Apps Environment
- App Insights, Key Vault, Redis, AI Search
- Service Principal dedicado
- 5 Azure AD groups (RBAC)
- Idempotente

### `.vscode/mcp.json`
Configuração MCP pra Cline/Continue/Claude Desktop.
Inclui system prompt recomendado pra AI entender o contexto BI.

## 🚀 Quickstart completo

```bash
# 1. Bootstrap infra Azure
./scripts/bootstrap/bootstrap-mcp-infra.ps1 `
  -SubscriptionId "xxx" -ResourceGroupName "rg-bi-mcp-dev" `
  -Environment "dev"

# 2. Configurar credenciais
export PBI_TENANT_ID=xxx
export PBI_SP_CLIENT_ID=xxx
export PBI_SP_CLIENT_SECRET=xxx

# 3. Subir MCP server
cd mcp/powerbi-mcp-server
pip install -e ".[dev]"
powerbi-mcp --http --port 8000

# 4. Extrair dataset
bi extract --workspace "bi-vendas-prod" --dataset "Vendas.Dataset" --generate-docs --git-commit

# 5. Rodar testes
pytest mcp/powerbi-mcp-server/tests/
pytest tools/orm/tests/
```

## 🛠️ `bi` CLI — use no seu terminal

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

## 🔌 3 formas de me conectar ao seu projeto

| Forma | Comando | Quando usar |
|---|---|---|
| **1. `mavis` CLI** (sistema) | Você já tem acesso via essa interface |操控 me diretamente: peers, sessions, cron |
| **2. `bi` CLI** (projeto) | `bi ask "..."`, `bi deploy ...` | Terminal local, git hooks, CI |
| **3. MCP server** (rede) | Já construído em `mcp/` | Cline, Continue, Claude Desktop, qualquer cliente MCP |

### Onde me achar (sessões, agents, comandos)

```bash
# Você já tem acesso ao mavis tool na sua interface
# Mas via CLI também dá pra操控:

# Listar peers (sessões que você pode falar)
mavis session list --mode peers --session-id me

# Spawnar uma nova sessão sub-agent
mavis session create --agent_name explorer --parent_session_id me --session_type Branch

# Agendar tarefa recorrente
mavis cron create --agent_name me --cron_name "audit-quality" \
  --schedule "0 9 * * 1" \
  --prompt "roda os checks de qualidade de dados em todos os datasets"

# Ver agentes disponíveis
mavis agent list
```
