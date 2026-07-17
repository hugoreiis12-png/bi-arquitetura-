# 🔌 Primeira Conexão · "Baixa tudo do Power BI pra cá"

> O que acontece quando você pede pro AI conectar num Power BI já existente
> e trazer toda a estrutura pra IDE. Passo a passo, com estrutura de pastas,
> comandos, performance e limitações.

---

## 1. O comando (em conversa natural)

```
👤 Você: "conecta no Power BI Vendas e baixa tudo pra cá"
```

Ou, se preferir CLI direta:

```bash
powerbi-mcp extract \
  --workspace "bi-vendas-prod" \
  --dataset "Vendas.Dataset" \
  --output ./src/datasets \
  --include-reports \
  --generate-docs
```

## 2. O que o MCP server faz (passo a passo)

```
[1/9] Autentica com Service Principal
      - Lê credenciais do Key Vault
      - Adquire token OAuth2
      - Valida permissões no workspace

[2/9] Lista datasets do workspace via REST API
      - GET /v1.0/myorg/groups/{wsId}/datasets
      - Retorna: id, name, configuredBy, targetStorageMode, etc

[3/9] Conecta no XMLA endpoint do dataset
      - Provider: MSOLAP via pyadomd
      - Lê TMSCHEMA_* DMVs:
        * TMSCHEMA_TABLES
        * TMSCHEMA_COLUMNS
        * TMSCHEMA_MEASURES
        * TMSCHEMA_RELATIONSHIPS
        * TMSCHEMA_ROLES
        * TMSCHEMA_ROLE_MEMBERSHIPS
        * TMSCHEMA_DATA_SOURCES
        * TMSCHEMA_PARTITIONS
        * TMSCHEMA_REFRESHES (último refresh)

[4/9] Extrai TMDL via pbi-tools
      - pbi-tools extract <dataset> --out ./src/datasets/Vendas.Dataset --format PBIP
      - Resultado: estrutura padrão PBIP criada

[5/9] Enriquece com metadados extras
      - Gera overview.yaml (resumo machine-readable)
      - Gera README.md (overview humano)
      - Gera docs/data-dictionary.md
      - Gera docs/measure-catalog.md
      - Gera docs/lineage.md

[6/9] Aplica padrões do projeto
      - Renomeia tabelas pra convenção (f_*, d_*, _aux_*)
      - Formata TMDL via DAX Formatter
      - Valida contra naming-conventions.md
      - Reporta desvios

[7/9] Configura .gitignore local
      - Ignora .pbi/ (cache)
      - Mantém TMDL versionado

[8/9] Commit inicial
      - git init (se não existe)
      - git add .
      - git commit -m "feat: extract Vendas.Dataset from Power BI (v1.0.0)"
      - NÃO faz push (aguarda você revisar)

[9/9] Reporta resultado
      - Arquivos criados
      - Estatísticas (medidas, tabelas, etc)
      - Avisos (se convenção não foi seguida)
      - Próximos passos sugeridos
```

## 3. Estrutura criada na IDE

```
src/datasets/Vendas.Dataset/
│
├── .pbip                                ← abre no Power BI Desktop
├── README.md                            ← overview humano
├── overview.yaml                        ← machine-readable
│
├── definition/
│   ├── version.json
│   ├── model.tmdl
│   ├── relationships.tmdl
│   ├── expressions.tmdl
│   ├── tables/
│   │   ├── d_calendario.tmdl
│   │   ├── d_cliente.tmdl
│   │   ├── d_produto.tmdl
│   │   ├── d_vendedor.tmdl
│   │   ├── f_vendas__pedido.tmdl
│   │   ├── f_vendas__item.tmdl
│   │   ├── f_metas.tmdl
│   │   └── _util_business_days.tmdl
│   ├── roles/
│   │   ├── GerenteRegional.tmdl
│   │   ├── Vendedor.tmdl
│   │   └── Auditor.tmdl
│   └── cultures/
│       └── pt-BR.tmdl
│
├── dataSources/
│   ├── SQL-DW-Vendas.tmdl
│   └── Excel-Metas.tmdl
│
├── reports/                             ← se --include-reports
│   └── Dashboard-Vendas.Report/
│       └── ...
│
├── .pbi/                                ← cache (gitignored)
│
└── docs/                                ← gerado pelo AI
    ├── data-dictionary.md
    ├── measure-catalog.md
    └── lineage.md
```

### 3.1 `overview.yaml` (gerado)

```yaml
# overview.yaml
# Machine-readable summary of Vendas.Dataset
# Atualizado em: 2026-07-15T14:00:00Z

dataset:
  id: "uuid-do-dataset"
  name: "Vendas.Dataset"
  workspace: "[PROD] Vendas"
  workspace_id: "aaa-prod"
  target_storage_mode: "PremiumFiles"  # Import / DirectQuery / PremiumFiles
  configured_by: "user@empresa.com"
  created_at: "2024-01-15T10:30:00Z"
  last_refresh: "2026-07-15T06:00:00Z"
  refresh_schedule: "0 6 * * *"
  estimated_size_mb: 1234

schema:
  tables: 8
  columns: 87
  measures: 47
  calculated_columns: 12
  calculated_tables: 1
  relationships: 12
  hierarchies: 4
  perspectives: 1
  translations: 2
  roles: 3
  data_sources: 2

measures_by_folder:
  Vendas/Receita: 16
  Vendas/Margem: 12
  Vendas/Operacional: 8
  Vendas/Estoque: 6
  Vendas/Outros: 5

rl_roles:
  - name: GerenteRegional
    members: 5
    filter: "[regiao] in (USERNAME's regions)"
  - name: Vendedor
    members: 180
    filter: "[vendedor_email] = USERNAME()"
  - name: Auditor
    members: 3
    filter: null

data_sources:
  - type: Sql
    name: SQL-DW-Vendas
    server: "dw.empresa.com"
    database: "Vendas"
  - type: File
    name: Excel-Metas
    path: "sharepoint://.../metas.xlsx"

dependents:
  reports: 23
  dataflows: 4
  downstream_datasets: 2

version:
  extracted_at: "2026-07-15T14:00:00Z"
  extracted_by: "powerbi-mcp/1.0.0"
  source_workspace_version: "1.4.0"

warnings:
  - "8 medidas não seguem convenção de nomenclatura (ver measure-catalog.md)"
  - "RLS 'Vendedor' tem 180 members hardcoded (recomendado: usar grupo AD)"
```

### 3.2 `README.md` (gerado)

```markdown
# Vendas.Dataset

> Modelo semântico de Vendas B2B, extraído de [PROD] Vendas em 2026-07-15.

## Resumo

- **8 tabelas** (5 dimensões, 3 fatos)
- **47 medidas** (16 em Receita, 12 em Margem, 19 outras)
- **12 relacionamentos**
- **3 roles RLS**
- **2 data sources** (SQL DW + Excel)

## Estrutura

Ver [`overview.yaml`](./overview.yaml) para metadados completos.

## Edição

Abra o `.pbip` no Power BI Desktop para editar visualmente.
Ou edite os `.tmdl` diretamente no VSCode.

## Convenções aplicadas

- ✅ Tabelas: snake_case (f_*, d_*, _aux_*)
- ⚠️ 8 medidas fora do padrão (ver `docs/measure-catalog.md`)
- ✅ Roles documentadas

## Próximos passos

1. Revisar `docs/data-dictionary.md` (gerado automaticamente)
2. Aplicar convenção nas 8 medidas fora do padrão
3. Configurar SP do MCP se ainda não estiver
4. Configurar secrets do workspace no CI/CD
5. Fazer primeiro deploy em Dev (após merge)
```

## 4. Performance esperada

| Cenário | Tempo |
|---|---|
| Dataset pequeno (< 50 medidas, < 20 tabelas) | 5-10s |
| Dataset médio (50-200 medidas, 20-50 tabelas) | 15-30s |
| Dataset grande (200-1000 medidas, 50-100 tabelas) | 30-90s |
| Dataset muito grande (1000+ medidas, 100+ tabelas) | 1-3min |

**Fatores que influenciam:**
- Latência de rede até o XMLA endpoint
- Tamanho do catálogo de TMSCHEMA
- Performance do pbi-tools (depende de .NET)
- Velocidade de I/O local

## 5. O que NÃO é extraído (limitações)

| Item | Por quê | Alternativa |
|---|---|---|
| **Dados em si** | Extract puxa schema, não dados | Rodar refresh do dataset pra ter dados localmente |
| **Visuais de relatório** (cores, posições) | Só layout/estrutura via PBIP | Editar visual no Desktop |
| **BLOBs binários** (imagens embutidas, fontes) | TMDL não tem | Editar no Desktop |
| **Histórico de medidas** | Não é metadado versionado | Olhar no Power BI Service (Activity Log) |
| **Custom visuals não-padrão** | Alguns não têm TMDL equivalente | Verificar manualmente |
| **Permissões granulares** (Build permission por report) | Não está no TMDL | Configurar via Service |

## 6. "Tempo real" — o que funciona

| Cenário | Tempo real? | Como funciona |
|---|---|---|
| **Desktop com .pbip** aberto + VSCode | ✅ Sim, parcial | File watcher. VSCode vê saves do Desktop. Desktop vê saves do VSCode (próximo refresh). |
| **Desktop com .pbix** (antigo) aberto | ❌ Não | PBIX é binário, bloqueado. Migrar primeiro. |
| **Só Power BI Service** | ❌ Não (é pull) | MCP extrai sob demanda. Mudanças locais vão via git/CI. |
| **Service muda enquanto você edita** | ❌ Não | Última escrita vence. Use `git pull` antes de editar. |
| **AI monitorando mudanças no Service** | ⚠️ Opcional | Pode configurar webhook do Service → notifica AI. Mas não auto-puxa. |

**Regra de ouro:** com PBIP local, dá pra editar em VSCode e Desktop simultaneamente. Sem PBIP (só Service), é ciclo pull/edit/push.

## 7. Comandos úteis pós-extração

```bash
# Ver resumo do que foi extraído
cat src/datasets/Vendas.Dataset/overview.yaml

# Diff entre local e Service (mostra o que mudou lá)
powerbi-mcp diff --workspace "bi-vendas-prod" --dataset "Vendas.Dataset"

# Pull de mudanças do Service
powerbi-mcp pull --workspace "bi-vendas-prod" --dataset "Vendas.Dataset"

# Validar extração contra convenções
powerbi-mcp validate --dataset "Vendas.Dataset"

# Verificar se há warnings
powerbi-mcp audit --dataset "Vendas.Dataset"

# Publicar mudanças de volta (via CI/CD)
git add . && git commit -m "..." && git push

# Forçar re-extração (sobrescreve local)
powerbi-mcp extract --workspace "bi-vendas-prod" --dataset "Vendas.Dataset" --force
```

## 8. Troubleshooting

| Problema | Causa | Solução |
|---|---|---|
| "Permission denied" ao extrair | SP sem permissão no workspace | Adicionar SP como Contributor no workspace |
| "XMLA endpoint not found" | Workspace sem Premium/PPU | Upgrade pra Premium/PPU/Fabric, ou usar REST API apenas |
| "Dataset has no PBIP" | Desktop não salvou como PBIP | Abrir dataset no Desktop, Save As → PBIP |
| Extract demora demais | Dataset muito grande | Rodar em background, ou extrair só schema (sem TMDL) |
| TMDL files aparecem "estranhos" | Dataset tem custom visuals | Editar visualmente no Desktop após extrair |
| Medidas em branco no extract | Medidas com TOM exception | Rodar `pbi-tools scan` pra identificar |

## 9. Cenário completo (passo a passo realista)

```
Dia 1, segunda-feira, 09:00
============================
👤 João (dev novo, acabou de entrar no time) abre o VSCode.

09:05 — Instala extensões recomendadas
09:08 — Configura MCP no .vscode/mcp.json
09:10 — Cline autentica no Azure AD
09:12 — João pergunta: "conecta no Power BI Vendas e baixa tudo pra cá"

09:13 — AI: conectando... [extrai Vendas.Dataset em 18s]
09:14 — AI: "Extraí 28 arquivos TMDL + 3 docs. Branch inicial criado."

09:15 — João abre src/datasets/Vendas.Dataset/overview.yaml
09:20 — Lê o README.md gerado pelo AI
09:25 — Abre o .pbip no Power BI Desktop (confirma que abre normal)
09:30 — Volta pro VSCode, abre d_cliente.tmdl (lê a definição)
09:40 — Pergunta ao AI: "me dá um overview do modelo"
        [Cenário 3 do manual de uso]

10:00 — Faz primeiro commit: "docs: review extracted structure"
10:05 — Push pro repo
10:10 — CI valida TMDL, passa
10:15 — João está produtivo. Já entende o modelo e o padrão.
        (Em times sem AI, esse momento chegava em 1-2 semanas.)
```

---

## Resumo

**SIM, o AI conecta em Power BI já configurado e baixa tudo organizado em pastas na IDE.**

- ✅ Tabelas, relacionamentos, medidas, RLS, data sources
- ✅ Estrutura PBIP padrão + extras gerados (README, overview, data-dict)
- ✅ Performance: 5s a 3min dependendo do tamanho
- ⚠️ Tempo real só funciona com Desktop + .pbip
- ⚠️ Não extrai dados em si, só estrutura

**Próximo passo:** o "vai" pra eu implementar o MCP server + scripts de extract + tudo que torna isso realidade. 🚀
