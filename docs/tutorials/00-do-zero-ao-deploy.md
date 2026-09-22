# Tutorial Completo: Do Zero ao Deploy

> Guia passo a passo para desenvolvedores Power BI e data engineers que querem adotar engenharia de software em seus projetos de BI.

---

## Sumário

1. [Introdução](#1-introdução)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Configuração do Ambiente](#3-configuração-do-ambiente)
4. [Criando seu Primeiro Dataset](#4-criando-seu-primeiro-dataset)
5. [Trabalhando com Git](#5-trabalhando-com-git)
6. [Adicionando Medidas DAX](#6-adicionando-medidas-dax)
7. [Testes Automatizados](#7-testes-automatizados)
8. [CI/CD Pipeline](#8-cicd-pipeline)
9. [Deploy e Promoção](#9-deploy-e-promoção)
10. [Camada de IA (Opcional)](#10-camada-de-ia-opcional)
11. [Multi-Projeto](#11-multi-projeto)
12. [Próximos Passos](#12-próximos-passos)

---

## 1. Introdução

### O que é este projeto?

O **bi-ide-architecture** é um scaffolding (esqueleto) que transforma o desenvolvimento Power BI de um processo manual e individual em uma **prática de engenharia** com:

- Versionamento granular (cada tabela, coluna, medida é um arquivo)
- Testes automatizados antes de promover mudanças
- Deploy controlado entre ambientes (Dev → Test → Prod)
- Governança e auditoria completa

### Para quem é este tutorial?

- **Desenvolvedores Power BI** que querem profissionalizar seus projetos
- **Data Engineers** que trabalham com Power BI e querem CI/CD
- **Analistas de BI** que querem trabalhar em equipe sem conflitos
- **Líderes técnicos** que querem governança sobre projetos de BI

### O que você vai aprender?

Ao final deste tutorial, você saberá:
- Configurar o ambiente de desenvolvimento
- Criar e versionar datasets no formato PBIP
- Trabalhar com Git (branches, commits, PRs)
- Adicionar e testar medidas DAX
- Configurar pipelines de CI/CD
- Deploy entre ambientes
- Usar a camada de IA (opcional)

---

## 2. Pré-requisitos

### Software Necessário

| Software | Versão Mínima | Onde Baixar |
|----------|---------------|-------------|
| Windows | 10/11 ou Server | — |
| Power BI Desktop | ≥ 2.121 | [Microsoft Store](https://aka.ms/pbiSingleDownload) |
| VS Code | ≥ 1.85 | [code.visualstudio.com](https://code.visualstudio.com/) |
| Tabular Editor 3 | Community (grátis) | [tabulareditor.com](https://tabulareditor.com/) |
| DAX Studio | Latest | [daxstudio.org](https://daxstudio.org/) |
| Git | Latest | [git-scm.com](https://git-scm.com/) |
| pbi-tools | Latest | [pbi.tools](https://pbi.tools/) |

### Contas Necessárias

- **Azure AD** com acesso ao Power BI Service
- **GitHub** ou **Azure DevOps** para versionamento
- **Power BI Premium** (recomendado, para XMLA e Deployment Pipelines)

### Verificação Rápida

```bash
# Verifique se tudo está instalado
git --version
dotnet tool list -g  # Deve listar pbi-tools
code --version
```

---

## 3. Configuração do Ambiente

### 3.1 Instalar pbi-tools

```powershell
# Instale o pbi-tools globalmente
dotnet tool install --global Microsoft.PowerBI.Tools

# Verifique a instalação
pbi-tools --version
```

### 3.2 Habilitar PBIP no Power BI Desktop

1. Abra o Power BI Desktop
2. Vá em `File → Options → Preview features`
3. Ative **"Power BI Project (.pbip) save mode"**
4. Clique em **OK** e reinicie o Desktop

### 3.3 Clonar o Repositório

```bash
# Clone o scaffolding
git clone https://github.com/sua-org/bi-ide-architecture.git
cd bi-ide-architecture

# Abra no VS Code
code .
```

### 3.4 Configurar o VS Code

Ao abrir o VS Code, ele deve sugerir instalar as extensões recomendadas:
- **Power BI** (para TMDL)
- **DAX** (para syntax highlighting)
- **GitLens** (para visualização de Git)

Aceite todas as instalações.

### 3.5 Estrutura Inicial

Após clonar, você terá esta estrutura:

```
bi-ide-architecture/
├── src/
│   ├── datasets/        # Seus datasets ficarão aqui
│   ├── reports/         # Seus relatórios ficarão aqui
│   └── shared/          # Medidas compartilhadas
├── docs/
├── tests/
├── deploy/
├── scripts/
├── mcp/                 # MCP Server (para IA)
├── tools/               # ORM SDK (para IA)
└── README.md
```

---

## 4. Criando seu Primeiro Dataset

### 4.1 Criar o Dataset no Desktop

1. Abra o Power BI Desktop
2. Conecte-se a uma fonte de dados (ex: Excel, SQL Server)
3. Carregue os dados necessários
4. Modelifique: crie tabelas, colunas e relacionamentos

### 4.2 Salvar como PBIP

1. Vá em `File → Save As`
2. Escolha **"Power BI Project (.pbip)"**
3. Navegue até `src/datasets/`
4. Nomeie como `Vendas.pbip`
5. Clique em **Save**

O Desktop criará automaticamente:
```
src/datasets/
└── Vendas.pbip
└── Vendas.Dataset/
    ├── definition/
    │   ├── model.tmdl
    │   ├── tables/
    │   │   ├── Vendas.tmdl
    │   │   ├── Produto.tmdl
    │   │   └── Cliente.tmdl
    │   └── relationships.tmdl
    ├── diagramLayout.json
    └── .platform
```

### 4.3 Verificar no VS Code

Abra a pasta `Vendas.Dataset/` no VS Code. Você verá os arquivos `.tmdl` com a estrutura do modelo.

Exemplo de `Vendas.tmdl`:
```tmdl
table Vendas
    lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    column PedidoId
        dataType: int64
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    column Data do Pedido
        dataType: datetime
        formatString: Short Date
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    column Produto SK
        dataType: int64
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    measure Receita Total =
        SUM('Vendas'[Valor Unitário] * 'Vendas'[Quantidade])
        formatString: $#,##0.00
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 4.4 Commit Inicial

```bash
git add .
git commit -m "feat(vendas): cria dataset inicial com tabelas Vendas, Produto, Cliente"
git push origin main
```

---

## 5. Trabalhando com Git

### 5.1 Criando uma Feature

Sempre crie uma branch nova para cada funcionalidade:

```bash
# Atualize develop
git checkout develop
git pull origin develop

# Crie a branch de feature
git checkout -b feat/adiciona-medida-margem
```

### 5.2 Editando TMDL

Abra o arquivo da tabela no VS Code e faça suas alterações.

Exemplo: Adicionar uma medida de Margem:

```tmdl
table Vendas
    lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    column PedidoId
        dataType: int64
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    column Data do Pedido
        dataType: datetime
        formatString: Short Date
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    column Produto SK
        dataType: int64
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    column Valor Unitário
        dataType: decimal
        formatString: $#,##0.00
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    column Quantidade
        dataType: int64
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    measure Receita Total =
        SUM('Vendas'[Valor Unitário] * 'Vendas'[Quantidade])
        formatString: $#,##0.00
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    measure Custo Total =
        SUM('Vendas'[Custo Unitário] * 'Vendas'[Quantidade])
        formatString: $#,##0.00
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    measure Margem Líquida =
        DIVIDE(
            [Receita Total] - [Custo Total],
            [Receita Total],
            0
        )
        formatString: 0.00%
        lineageTag: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 5.3 Commit e Push

```bash
# Verifique o que mudou
git status
git diff

# Adicione as mudanças
git add src/datasets/Vendas.Dataset/definition/tables/Vendas.tmdl

# Commit com mensagem descritiva
git commit -m "feat(vendas): adiciona medida Margem Líquida"

# Push para o repositório remoto
git push origin feat/adiciona-medida-margem
```

### 5.4 Criando um Pull Request

1. Vá ao GitHub/Azure DevOps
2. Clique em "New Pull Request"
3. Base: `develop`, Head: `feat/adiciona-medida-margem`
4. Preencha o template do PR:
   - Descreva a mudança
   - Marque o tipo (feat)
   - Documente testes realizados
5. Aguarde CI passar
6. Aguarde code review (mínimo 1 aprovação)
7. Faça merge

---

## 6. Adicionando Medidas DAX

### 6.1 Convenções de Medidas

Siga estas convenções ao criar medidas:

| Regra | Exemplo | Errado |
|-------|---------|--------|
| Nome = substantivo do que mede | `Receita Total` | `CalcReceita` |
| Sem prefixo de tabela | `Margem` | `VendasMargem` |
| Formato em `formatString` | `formatString: $#,##0.00` | (sem formato) |
| Usar `VAR` para intermediários | `VAR _receita = ...` | (cálculo inline) |
| Usar `DIVIDE` para divisões | `DIVIDE(a, b, 0)` | `a / b` |

### 6.2 Exemplo de Medida Bem Escrita

```dax
Ticket Médio =
VAR _receita = [Receita Total]
VAR _pedidos = DISTINCTCOUNT('Vendas'[PedidoId])
RETURN
    DIVIDE(_receita, _pedidos, 0)
```

### 6.3 Validação de Medidas

Antes de commitar, valide sua medida:

```bash
# Via MCP Server (se configurado)
bi validate dax medida.dax --measure-name "Vendas.Ticket Médio"

# Ou manualmente no DAX Studio
# Execute a medida e verifique se retorna o resultado esperado
```

### 6.4 Documentação

Adicione a medida ao dicionário de dados:

```markdown
## Ticket Médio

**Tabela**: Vendas
**Tipo**: Medida
**Fórmula**: `DIVIDE(SUM(Vendas[Valor Unitário] * Vendas[Quantidade]), DISTINCTCOUNT(Vendas[PedidoId]), 0)`
**Formato**: $#,##0.00
**Descrição**: Valor médio por pedido
```

---

## 7. Testes Automatizados

### 7.1 DAX Smoke Tests

Crie testes em `tests/dax/`:

```dax
// tests/dax/02-medidas-vendas.dax
EVALUATE
ROW(
    "Receita Total", [Receita Total],
    "Custo Total", [Custo Total],
    "Margem Líquida", [Margem Líquida],
    "Ticket Médio", [Ticket Médio]
)
```

### 7.2 Rodando Testes Localmente

```bash
# Se tiver DAX Studio configurado
# Abra o arquivo .dax e execute

# Ou via Python (se MCP server configurado)
cd mcp/powerbi-mcp-server
pytest tests/ -v
```

### 7.3 Testes de Qualidade de Dados

Crie testes em `tests/data-quality/`:

```yaml
# tests/data-quality/vendas.yaml
checks for Vendas:
  - row_count > 0
  - column PedidoId is not null
  - column Data do Pedido is between '2020-01-01' and '2025-12-31'
  - column Valor Unitário > 0
  - column Quantidade > 0
```

---

## 8. CI/CD Pipeline

### 8.1 Estrutura do Pipeline

O pipeline completo está em `.github/workflows/bi-ci-cd.yml`:

```
┌─────────┐   ┌─────────┐   ┌───────────┐   ┌───────────┐
│ validate │──▶│  build  │──▶│deploy-dev │──▶│ manual-ok │
└─────────┘   └─────────┘   └───────────┘   └─────┬─────┘
                                                    │
                                              ┌─────▼─────┐
                                              │deploy-test│
                                              └─────┬─────┘
                                                    │
                                              ┌─────▼─────┐
                                              │deploy-prod│
                                              └───────────┘
```

### 8.2 Configurando os Secrets

No GitHub/Azure DevOps, adicione estes secrets:

| Secret | Valor |
|--------|-------|
| `AZURE_SP_DEV_CLIENT_ID` | Client ID do Service Principal |
| `AZURE_SP_DEV_CLIENT_SECRET` | Client Secret do SP |
| `AZURE_TENANT_ID` | Tenant ID do Azure AD |
| `AZURE_SUBSCRIPTION_ID` | ID da Subscription Azure |
| `PBI_WORKSPACE_ID_DEV` | ID do workspace Dev |
| `PBI_WORKSPACE_ID_TEST` | ID do workspace Test |
| `PBI_WORKSPACE_ID_PROD` | ID do workspace Prod |

### 8.3 Testando o Pipeline

1. Faça push para uma branch `feat/*`
2. O pipeline `validate` e `build` serão executados
3. Após merge em `main`, `deploy-dev` será executado
4. Verifique o resultado em Actions

---

## 9. Deploy e Promoção

### 9.1 Deploy Automático (Dev)

Após merge em `main`, o pipeline:
1. Compila os PBIPs com `pbi-tools compile`
2. Roda DAX smoke tests
3. Publica no workspace Dev via REST API
4. Notifica no Teams

### 9.2 Promoção Manual (Test/Prod)

```bash
# Promover para Test
./scripts/promote.ps1 -Environment test -Dataset "Vendas.Dataset"

# Promover para Prod (requer aprovação)
./scripts/promote.ps1 -Environment prod -Dataset "Vendas.Dataset"
```

### 9.3 Deployment Pipelines (Power BI Service)

Alternativamente, use o Deployment Pipeline do Power BI:

1. No Power BI Service, crie um Deployment Pipeline
2. Adicione os workspaces Dev, Test, Prod
3. Configure as regras de promoção
4. Use a interface web para promover

### 9.4 Verificando o Deploy

```bash
# Verifique se o dataset foi publicado
bi extract --workspace "bi-vendas-dev" --dataset "Vendas.Dataset" --preview
```

---

## 10. Camada de IA (Opcional)

### 10.1 MCP Server

O MCP server permite conectar IA (Cline, Continue, Claude Desktop) ao Power BI.

```bash
# Instale o MCP server
cd mcp/powerbi-mcp-server
pip install -e ".[dev]"

# Configure as variáveis de ambiente
export PBI_TENANT_ID=xxx
export PBI_SP_CLIENT_ID=xxx
export PBI_SP_CLIENT_SECRET=xxx

# Inicie o servidor
powerbi-mcp --http --port 8000
```

### 10.2 ORM SDK

O ORM SDK permite manipular modelos tabulares via Python:

```python
from powerbi_orm import Dataset

# Conectar ao modelo
dataset = Dataset.from_pbip("./src/datasets/Vendas.Dataset")

# Listar tabelas
for table in dataset.tables:
    print(f"Tabela: {table.name}")

# Criar medida
from powerbi_orm import Measure
medida = Measure(
    name="Nova Medida",
    expression="SUM(Vendas[Valor])"
)
dataset.tables["Vendas"].add_measure(medida)

# Commit
dataset.commit(message="feat: adiciona nova medida")
```

### 10.3 Validação DAX via IA

```bash
# Valide uma medida com o MCP server
bi validate dax medida.dax --measure-name "Vendas.Margem"
```

---

## 11. Multi-Projeto

### 11.1 Template Repo

Use este scaffolding como template para novos projetos:

```bash
# Crie um novo projeto a partir do template
gh repo create meu-org/bi-vendas --template sua-org/bi-ide-architecture

# Ou clone e renomeie
git clone https://github.com/sua-org/bi-ide-architecture.git bi-vendas
cd bi-vendas
git remote set-url origin https://github.com/meu-org/bi-vendas.git
```

### 11.2 Portfolio

Gerencie múltiplos projetos via `portfolio/catalog/projects.json`:

```json
{
  "projects": [
    {
      "id": "vendas",
      "name": "BI Vendas",
      "status": "active",
      "owner": "time-vendas",
      "workspace_dev": "bi-vendas-dev",
      "workspace_test": "bi-vendas-test",
      "workspace_prod": "bi-vendas-prod"
    }
  ]
}
```

### 11.3 Biblioteca Compartilhada

Use `src/shared/` para medidas e funções compartilhadas:

```
src/shared/
├── measures/
│   ├── common.dax        # Medidas comuns
│   └── calendar.dax      # Funções de calendário
├── tables/
│   └── dim_date.tmdl     # Tabela de dimensão data
└── scripts/
    └── refresh.py        # Scripts de refresh
```

---

## 12. Próximos Passos

### Recursos para Explorar

1. **Documentação detalhada**:
   - [`docs/architecture.md`](../architecture.md) — Arquitetura completa
   - [`docs/naming-conventions.md`](../naming-conventions.md) — Padrões de nomenclatura
   - [`docs/ci-cd.md`](../ci-cd.md) — Pipeline CI/CD

2. **Guias**:
   - [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — Como contribuir
   - [`TROUBLESHOOTING.md`](../../TROUBLESHOOTING.md) — Solução de problemas

3. **Avançado**:
   - [`docs/ai-architecture/`](../ai-architecture/) — Camada de IA
   - [`portfolio/README.md`](../../portfolio/README.md) — Multi-projeto

### Checklists

- [ ] Ambiente configurado
- [ ] Primeiro dataset criado e versionado
- [ ] Pipeline CI/CD funcionando
- [ ] Deploy Dev automatizado
- [ ] Deploy Test/Prod configurado
- [ ] Medidas testadas
- [ ] Documentação atualizada
- [ ] Time treinado

### Comunidade

- Abra issues para dúvidas
- Contribua com melhorias
- Compartilhe seus aprendizados

---

## Referências

- [Power BI Projects (PBIP) - Microsoft](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview)
- [Tabular Editor Documentation](https://docs.tabulareditor.com/)
- [DAX Studio Documentation](https://daxstudio.org/)
- [pbi-tools Documentation](https://pbi.tools/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

**Parabéns!** Você agora tem um projeto Power BI profissional com versionamento, testes e deploy controlado. 🚀
