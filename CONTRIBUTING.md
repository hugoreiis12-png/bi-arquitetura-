# Contribuindo com o bi-ide-architecture

Obrigado por contribuir! Este guia explica como participar do projeto de forma padronizada.

## Índice

1. [Código de Conduta](#código-de-conduta)
2. [Visão Geral do Fluxo](#visão-geral-do-fluxo)
3. [Ambiente de Desenvolvimento](#ambiente-de-desenvolvimento)
4. [Branching Model](#branching-model)
5. [Commits (Conventional Commits)](#commits)
6. [Pull Requests](#pull-requests)
7. [Code Review](#code-review)
8. [Convenções de Código](#convenções-de-código)
9. [Testes](#testes)
10. [Documentação](#documentação)
11. [Issues e Bugs](#issues-e-bugs)

---

## Código de Conduta

- Respeite todos os participantes
- Fique aberto a feedback construtivo
- Foque no que é melhor para o projeto

---

## Visão Geral do Fluxo

```
1. Fork/Clone o repositório
2. Crie uma branch de feature
3. Implemente suas mudanças
4. Adicione testes se aplicável
5. Atualize a documentação
6. Abra um Pull Request
7. Aguarde code review e aprovação
8. Merge em develop → main (via CI/CD)
```

---

## Ambiente de Desenvolvimento

### Pré-requisitos

- Windows 10/11 ou Windows Server
- Power BI Desktop ≥ 2.121 (com PBIP ativado)
- VS Code ≥ 1.85
- Tabular Editor 3 (Community license)
- DAX Studio (latest)
- Git + acesso ao repositório
- pbi-tools:
  ```powershell
  dotnet tool install --global Microsoft.PowerBI.Tools
  ```
- Python 3.10+ (para MCP server e ORM)
- Node.js 18+ (para scripts auxiliares)

### Setup Local

```bash
# 1. Clone o repositório
git clone https://github.com/sua-org/bi-ide-architecture.git
cd bi-ide-architecture

# 2. Instale dependências Python
cd mcp/powerbi-mcp-server
pip install -e ".[dev]"
cd ../..

# 3. Instale dependências do ORM
cd tools/orm
pip install -e ".[dev]"
cd ../..

# 4. Abra no VS Code
code .

# 5. Instale extensões recomendadas
# (o VS Code deve sugerir automaticamente)
```

### Configuração de Credenciais

```bash
# Copie o template
cp mcp/powerbi-mcp-server/.env.example mcp/powerbi-mcp-server/.env

# Edite com suas credenciais
# NUNCA versione o arquivo .env
```

---

## Branching Model

```
main
├── develop
│   ├── feat/nome-da-feature
│   ├── fix/nome-do-fix
│   ├── chore/nome-da-tarefa
│   └── docs/nome-da-documentacao
```

### Regras

| Branch | Origem | Merge em | Deploy |
|--------|--------|-----------|--------|
| `main` | — | — | Produção |
| `develop` | `main` | `main` | Desenvolvimento |
| `feat/*` | `develop` | `develop` | — |
| `fix/*` | `develop` | `develop` | — |
| `chore/*` | `develop` | `develop` | — |
| `docs/*` | `develop` | `develop` | — |

### Criação de Branch

```bash
# Sempre partindo de develop atualizado
git checkout develop
git pull origin develop

# Feature
git checkout -b feat/adiciona-medida-receita

# Fix
git checkout -b fix/correcao-calculo-margem

# Chore
git checkout -b chore/atualiza-dependencias

# Docs
git checkout -b docs/atualiza-readme
```

---

## Commits

Utilizamos [Conventional Commits](https://www.conventionalcommits.org/).

### Formato

```
<tipo>(<escopo>): <descrição>

[corpo opcional]

[footer opcional]
```

### Tipos

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `feat` | Nova funcionalidade | `feat(vendas): adiciona medida Margem Líquida` |
| `fix` | Correção de bug | `fix(dax): corrige divisão por zero em Ticket Médio` |
| `docs` | Documentação | `docs(readme): adiciona seção de troubleshooting` |
| `style` | Formatação (sem mudança de lógica) | `style(tmdl): organiza ordem das colunas` |
| `refactor` | Refatoração sem mudança de comportamento | `refactor(orm): extrai classe BaseRepository` |
| `test` | Adição/correção de testes | `test(dax): adiciona smoke test para Receita` |
| `chore` | Tarefas de manutenção | `chore(deps): atualiza powerbi-orm para v0.4.1` |
| `ci` | Mudanças na CI/CD | `ci(actions): adiciona job de validação TMDL` |

### Escopos Comuns

| Escopo | Área |
|--------|------|
| `vendas` | Modelo de vendas |
| `estoque` | Modelo de estoque |
| `rh` | Modelo de RH |
| `dax` | Medidas e cálculos DAX |
| `tmdl` | Definições de modelo |
| `orm` | SDK Python ORM |
| `mcp` | MCP Server |
| `scripts` | Scripts de automação |
| `ci` | Pipeline CI/CD |
| `docs` | Documentação |

### Exemplos

```bash
git commit -m "feat(vendas): adiciona medida Receita Líquida"
git commit -m "fix(dax): corrige filtro de data em YTD"
git commit -m "docs(api): documenta novos endpoints do MCP"
git commit -m "chore(ci): atualiza versão do pbi-tools"
```

---

## Pull Requests

### Template

O repositório possui um PR template (`.github/PULL_REQUEST_TEMPLATE.md`). Preencha todos os campos.

### Fluxo

1. **Push sua branch**:
   ```bash
   git push origin feat/sua-feature
   ```

2. **Abra o PR** no GitHub/Azure DevOps:
   - Base: `develop`
   - Head: `feat/sua-feature`

3. **Preencha o template**:
   - Descreva o que muda
   - Link à issue (se houver)
   - Marque o tipo de mudança
   - Documente testes realizados
   - Inclua evidências (screenshots, se aplicável)

4. **Aguarde CI**:
   - Validação TMDL ✓
   - DAX smoke tests ✓
   - Build ✓

5. **Aguarde review** (mínimo 1 aprovação)

6. **Merge** após aprovação

### Regras do PR

- Título segue Conventional Commits
- Branch está atualizada com `develop`
- Todos os checks estão verdes
- Não há conflitos
- Documentação atualizada (se aplicável)
- CHANGELOG atualizado (se houver mudança relevante)

---

## Code Review

### Para Revisores

1. **Verifique a estrutura**:
   - Segue convenções de nomenclatura?
   - Organização do TMDL está correta?

2. **Verifique a lógica**:
   - DAX está correto e performático?
   - Relacionamentos estão adequados?

3. **Verifique a documentação**:
   - Descrições preenchidas?
   - README/docs atualizados?

4. **Verifique a segurança**:
   - RLS adequado?
   - Credenciais não expostas?

### Para Autores

- Responda a todos os comentários
- Faça as alterações solicitadas
- Marque como "Resolved" após implementar
- Peça nova revisão se necessário

---

## Convenções de Código

### TMDL

- **Tabelas de fato**: substantivo de negócio (`Vendas`, `Estoque`)
- **Tabelas de dimensão**: substantivo singular (`Produto`, `Cliente`)
- **Tabelas técnicas**: prefixo `_` e oculta (`_Medidas`, `_Parâmetros`)
- **Colunas**: linguagem de negócio, capitalização natural
- **Chaves**: sufixo consistente, sempre oculta (`Produto SK`)
- **Medidas**: substantivo do que mede (`Faturamento`, `Ticket Médio`)

### DAX

- Use `VAR` para variáveis intermediárias
- Prefira `CALCULATE` com filtros diretos a `FILTER` sobre tabela inteira
- Nunca use `LOOKUPVALUE` quando `RELATED` é possível
- Defina `formatString` em todas as medidas visíveis
- Use `DIVIDE` para divisões (evita divisão por zero)

### Python (MCP Server / ORM)

- Siga PEP 8
- Use type hints
- Documente funções públicas com docstrings
- Escreva testes para funcionalidades novas
- Use `black` para formatação

### PowerShell

- Use `CmdletBinding()` em scripts
- Trate erros com `try/catch`
- Use parâmetros com validação
- Documente com `<# .SYNOPSIS #>`

---

## Testes

### Tipos de Teste

| Tipo | Local | Como rodar |
|------|-------|------------|
| DAX smoke tests | `tests/dax/` | DAX Studio ou CI |
| Unitários (Python) | `mcp/powerbi-mcp-server/tests/` | `pytest` |
| Unitários (ORM) | `tools/orm/tests/` | `pytest` |
| Integração | `tests/integration/` | `pytest -m integration` |

### Rodando Testes Localmente

```bash
# MCP Server
cd mcp/powerbi-mcp-server
pytest tests/ -v

# ORM
cd tools/orm
pytest tests/ -v

# Todos
pytest mcp/powerbi-mcp-server/tests/ tools/orm/tests/ -v
```

### Adicionando Testes

1. Crie arquivo `test_<nome>.py` no diretório de testes
2. Use prefixo `test_` para funções
3. Use fixtures para setup comum
4. Execute antes de abrir PR

---

## Documentação

### Quando Atualizar

- Nova medida → `docs/data-dictionary.md`
- Nova tabela → `docs/data-dictionary.md`
- Mudança de nomenclatura → `docs/naming-conventions.md`
- Mudança de arquitetura → `docs/architecture.md`
- Nova feature → `README.md` (seção relevante)
- Bug corrigido → `CHANGELOG.md`

### Padrões

- Use Markdown
- Inclua exemplos práticos
- Mantenha a língua portuguesa (padrão do projeto)
- Referencie outros documentos quando relevante

---

## Issues e Bugs

### Reportando Bugs

1. Verifique se já existe issue similar
2. Crie nova issue com template
3. Inclua:
   - Passos para reproduzir
   - Comportamento esperado vs atual
   - Screenshots (se aplicável)
   - Ambiente (SO, versões)

### Sugestões de Melhoria

1. Descreva a funcionalidade desejada
2. Explique o caso de uso
3. Indique se está disposto a implementar

### Issues Marcadas com `good first issue`

Perfeitas para iniciantes no projeto!

---

## Perguntas?

- Abra uma issue com tag `question`
- Consulte a documentação em `docs/`
- Entre em contato com os mantenedores

Obrigado por contribuir! 🚀
