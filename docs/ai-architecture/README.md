# 🧠 Camada AI-Augmented · MCP + ORM + Guardrails

> Adiciona uma camada de IA sobre a arquitetura BI, com MCP server como ponte,
> ORM semântico para manipulação do modelo, e guardrails de segurança rigorosos.

## 0. Análise de viabilidade (TL;DR)

| Requisito | Viável? | Complexidade | Condição crítica |
|---|---|---|---|
| MCP server como ponte IDE ↔ Power BI | ✅ Sim | Média | MCP server precisa rodar no Azure (não local) para baixa latência |
| "Direct Query em tempo real" via MCP | ✅ Sim | Alta | Requer XMLA endpoint habilitado (Premium/Fabric/PPU) |
| ORM para modelo semântico | ✅ Sim | Alta | Sem ORM tradicional; construímos SDK Python sobre TOM/TMDL/XMLA |
| Guardrails internos e externos | ✅ Sim | Média | Defense in depth: 7 camadas obrigatórias |
| Roles de acesso (RBAC) | ✅ Sim | Baixa | Azure AD groups + custom claims no token MCP |

**Veredicto: todas as 4 demandas são implementáveis, mas o ORM é o mais ambicioso** (não existe ORM pronto pra Power BI — vamos construir um wrapper sobre TOM/TMDL/XMLA).

---

## 1. Visão geral · camadas adicionadas

```
┌─────────────────────────────────────────────────────────────────────┐
│                          👨‍💻 Desenvolvedor BI                       │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ conversa natural
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│           VSCode + Cliente MCP (Cline / Continue / Claude)          │
│           - lê PBIP files localmente                                 │
│           - mostra preview de DAX formatado                          │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ MCP protocol (stdio / SSE / HTTP)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│           🧠 MCP Server Power BI (Azure Container App)               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Tools:      │  │ Resources:   │  │ Prompts:     │  │ Guards:  │ │
│  │ - query-dax │  │ - TMDL files │  │ - review-pr  │  │ - RBAC   │ │
│  │ - add-mesa  │  │ - data dict  │  │ - explain    │  │ - audit  │ │
│  │ - list-tbl  │  │ - lineage    │  │ - generate   │  │ - rate   │ │
│  └─────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │
└──────┬─────────────────────────────────────┬──────────────┬──────────┘
       │                                     │              │
       ▼                                     ▼              ▼
┌──────────────┐  ┌──────────────────────┐  ┌────────────────────────┐
│ XMLA Endpoint│  │ Power BI REST API    │  │ Knowledge Layer (RAG)  │
│ (Direct Qry) │  │ (deploy, refresh)   │  │ - data dictionary     │
│ Premium/PPU  │  │                      │  │ - ADRs                 │
│ ou Fabric    │  │                      │  │ - past PRs             │
└──────┬───────┘  └──────┬───────────────┘  │ - data lineage         │
       │                 │                  │ - business glossary    │
       │                 │                  └────────────────────────┘
       ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Power BI Service (Workspaces)                      │
│  [Dev] [Test] [AI-Playground] [Prod]                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Componentes em detalhe

### 2.1 MCP Server (ponte)

**Stack recomendada:**
- Linguagem: **Python 3.11+** (FastMCP SDK)
- Hospedagem: **Azure Container Apps** (auto-scaling, HTTPS, VNet integration)
- Auth: **OAuth2 client credentials** com Service Principal
- State: **Redis** (rate limit, cache de schema)
- Observability: **OpenTelemetry → Application Insights**

**Tools que o MCP deve expor (10 essenciais):**

| Tool | Risco | Descrição |
|---|---|---|
| `pbi_list_datasets` | 🟢 safe | Lista datasets do workspace |
| `pbi_get_model_schema` | 🟢 safe | Retorna TMDL resumido do modelo |
| `pbi_query_dax` | 🟢 safe | Executa DAX query (SELECT only, sem side-effects) |
| `pbi_get_measure_definition` | 🟢 safe | Lê definição de uma medida |
| `pbi_format_dax` | 🟢 safe | Formata código DAX |
| `pbi_search_data_dictionary` | 🟢 safe | Busca semântica no data dictionary |
| `pbi_diff_environments` | 🟢 safe | Compara Dev vs Prod |
| `pbi_suggest_measure` | 🟡 moderate | Sugere DAX para uma regra de negócio |
| `pbi_validate_dax_syntax` | 🟡 moderate | Valida sintaxe antes de aplicar |
| `pbi_propose_measure_update` | 🟠 dangerous | Cria branch + PR com mudança |
| `pbi_apply_approved_change` | 🔴 critical | Aplica mudança no Service (requer approval token) |

> Detalhe completo em [`mcp-server.md`](mcp-server.md)

### 2.2 ORM Semântico (Python SDK)

**Por que "ORM":** o modelo semântico do Power BI (Tabular Model) tem schema, relações, medidas — parecido com um banco. Vamos dar a devs Python uma API fluente para manipulá-lo.

**Bibliotecas base:**
- `pyadomd` — query DAX via XMLA
- `msal` — autenticação Azure AD
- `pbi-tools` CLI invocado via subprocess
- `pydantic` — validação de schema

**API exemplo:**

```python
from powerbi_orm import Dataset, Table, Column, Measure, Relationship

# Conecta
ds = Dataset.connect(
    workspace="bi-vendas-dev",
    sp_id=os.environ["PBI_SP_CLIENT_ID"],
    sp_secret=os.environ["PBI_SP_CLIENT_SECRET"],
    tenant=os.environ["PBI_TENANT_ID"],
)

# Lê (query DAX)
receita = ds.query("EVALUATE ROW(\"x\", [Vendas.Receita Total BRL])")
print(receita.rows[0]["x"])  # 1234567.89

# Descreve schema (introspection)
for table in ds.tables:
    print(f"{table.name}: {len(table.columns)} cols, {len(table.measures)} measures")

# Adiciona medida (write)
ds.tables["f_vendas__pedido"].add_measure(
    name="Vendas.Ticket Médio [R$]",
    expression="DIVIDE([Vendas.Receita Total BRL], DISTINCTCOUNT(f_vendas__pedido[pedido_id]))",
    format_string='R$ #,##0.00',
    folder="Vendas",
)

# Valida antes de persistir
ds.validate()  # checa nomes, RLS, dependências
ds.commit(branch="feat/ticket-medio-novo", message="feat: ticket médio por pedido")
```

> Detalhe completo em [`orm-semantico.md`](orm-semantico.md)

### 2.3 Direct Query "tempo real" via MCP

**O que é:** o MCP server mantém conexão persistente com o XMLA endpoint e expõe `pbi_query_dax` como ferramenta. Latência típica: 200-800ms para queries leves, 2-5s para agregações pesadas.

**Limitação importante:** "tempo real" aqui significa **latência de query**, não replicação contínua. Para dashboards truly real-time (sub-segundo), o caminho é diferente (streaming datasets, push API, Fabric eventstreams).

**Quando usar:**
- ✅ Dev fazendo drill-down em dados durante desenvolvimento
- ✅ AI gerando hipótese e validando contra dados ao vivo
- ✅ Validação de measure no dataset real antes de promover
- ❌ Dashboard de produção (esse continua via cache do Power BI)

> Detalhe em [`mcp-server.md`](mcp-server.md) (seção "Direct Query mode")

---

## 3. Guardrails · 7 camadas de segurança

**Defense in depth.** Mesmo que uma camada falhe, as outras protegem.

| # | Camada | Tipo | O que faz |
|---|---|---|---|
| 1 | **Network** | Infra | MCP server atrás de VNet + Private Endpoint. Sem IP público. |
| 2 | **Authentication** | Auth | OAuth2 SP com secret rotacionado a cada 90 dias via Key Vault |
| 3 | **Authorization (RBAC)** | Auth | Roles Azure AD determinam quais tools MCP o user pode chamar |
| 4 | **Action classification** | App | Cada tool tem risk-level: safe / moderate / dangerous / critical |
| 5 | **Approval workflow** | App | Actions dangerous+ exigem approval token (válido 15min, 1 uso) |
| 6 | **Audit trail** | App | Cada chamada logada: user, tool, args, output, timestamp, cost |
| 7 | **Rate limiting** | App | Por user: 60 req/min; por tool: limites específicos |

**Classificação de tools por risco (regra de ouro):**

```
🟢 SAFE     → read-only, sem side-effect, dados não-sensíveis
🟡 MODERATE → read de dados sensíveis OU write de metadata não-critica
🟠 DANGEROUS → write de medidas/relacionamentos, requer PR review
🔴 CRITICAL  → delete, change RLS, deploy to Prod, change data source
```

> Detalhe completo em [`guardrails.md`](guardrails.md) e [`rbac.md`](rbac.md)

---

## 4. Knowledge Layer (RAG) — adição crítica

**O AI precisa de contexto para não inventar dados.** Sem isso, ele vai gerar medidas erradas ou alucinar schema.

**Fontes de conhecimento:**

| Fonte | O que tem | Como indexar |
|---|---|---|
| `docs/data-dictionary.md` | Definição de tabelas, colunas, medidas | Markdown chunking + embeddings |
| `docs/naming-conventions.md` | Padrões de nomenclatura | Markdown |
| ADRs (Architecture Decision Records) | Decisões de design | Markdown |
| `git log` | Histórico de mudanças (quem mudou o quê, por quê) | Texto |
| Past PRs (aprovados) | Padrões de revisão, feedback recorrente | Texto |
| Business glossary | Termos de negócio (siglas, KPIs) | Glossário |
| Lineage metadata | De onde vem cada coluna | OpenLineage / Purview |
| Power BI lineage | Quais reports dependem de quais datasets | REST API |

**Stack RAG:**
- Vector DB: **Azure AI Search** (índice híbrido: keyword + semântico)
- Embedding: **text-embedding-3-large** (OpenAI) ou **cohere-embed-v3**
- Chunking: 512 tokens, overlap 64
- Atualização: a cada merge em main (CI atualiza o índice)

**Exemplo de uso pelo AI:**

```
Dev: "cria uma medida de taxa de churn"
AI:   [busca RAG: 'taxa churn' → 2 medidas existentes, 1 ADR, 0 regras]
AI:   "Já existe [Clientes.Churn % Mensal]. A definição atual é:
       VAR _ativos_inicio = ...
       Você quer criar uma variação (ex: trimestral) ou atualizar a atual?"
```

---

## 5. Validação de DAX gerado por AI

**AI vai escrever DAX errado. Sempre.** É lei da física. Você precisa de um harness de validação.

**Validações obrigatórias antes de aceitar DAX do AI:**

```python
def validate_ai_dax(dax_code: str, dataset: Dataset) -> ValidationResult:
    # 1. Sintaxe — usa pbi-tools compile pra checar
    syntax_ok = pbi_tools.compile_check(dax_code)

    # 2. Semântica — roda em dataset de sandbox com dados sintéticos
    result = dataset.query(dax_code)
    semantic_ok = result.error is None and result.has_data

    # 3. Performance — estima custo de execução
    perf_ok = estimate_query_cost(dax_code) < MAX_COST

    # 4. Segurança — não referencia tabelas/colunas fora do permitido
    scope_ok = all(ref in ALLOWED_TABLES for ref in dax_code.references)

    # 5. RLS — não vaza dados quando rodado com RLS ativo
    rls_safe = test_with_rls(dax_code, sample_roles)

    # 6. Naming — segue convenção
    naming_ok = matches_naming_convention(dax_code)

    return ValidationResult(syntax_ok, semantic_ok, perf_ok, scope_ok, rls_safe, naming_ok)
```

> Detalhe em [`validacao-dax.md`](validacao-dax.md)

---

## 6. Sandbox dedicado · AI-Playground

**Workspace separado só pra AI.** Nunca deixe o AI tocar direto no Dev/Test/Prod.

```
Power BI Service
├── [Dev] Vendas         ← dev humano
├── [Test] Vendas        ← QA humano
├── [AI-Playground] Vendas  ← IA (isolado)
└── [Prod] Vendas        ← só via promotion
```

**O que o AI pode fazer no Playground:**
- ✅ Ler schema, executar DAX, criar medidas experimentais
- ✅ Testar transformações Power Query
- ✅ Gerar mock data para validar lógica

**O que o AI NÃO pode fazer no Playground:**
- ❌ Acessar dados de produção (datasets Prod são read-only via XMLA)
- ❌ Modificar datasets de outros workspaces
- ❌ Disparar refresh em Prod
- ❌ Publicar em qualquer workspace sem approval

**Caminho de promoção AI → Dev:**
1. AI termina trabalho no Playground
2. AI gera PR no repo do projeto (com TMDL + testes)
3. PR passa pelos gates normais (validate, smoke tests, reviewer)
4. Merge em main → deploy em Dev (mesmo fluxo de dev humano)
5. AI **nunca** promove direto pra Test/Prod

---

## 7. Observabilidade · ver o AI trabalhando

**Sem observabilidade, AI é caixa-preta. Você não vai confiar.**

**Métricas obrigatórias:**

| Métrica | Por quê |
|---|---|
| MCP tool calls/min | Detectar runaway loops |
| Latência por tool | SLA do MCP server |
| DAX queries rejeitadas | Taxa de erro do AI |
| DAX measure acceptance rate | % de medidas geradas aceitas em PR |
| Approval rate por tool | Quanto o AI precisa de aprovação |
| Tokens consumidos / user | Custo de AI |
| Actions negadas pelo RBAC | Tentativas de acesso indevido |
| Audit log completeness | Garantia de que tudo está logado |

**Stack:**
- **OpenTelemetry SDK** no MCP server
- **Application Insights** (Azure) como backend
- **Grafana** (opcional) para dashboards customizados
- **Alertas**: Adaptive para anomalias (ex: 10x aumento de calls)

> Detalhe em [`observabilidade.md`](observabilidade.md)

---

## 8. Custos · AI + Power BI não é de graça

**O que custa:**

| Item | Estimativa mensal | Variável? |
|---|---|---|
| Azure Container Apps (MCP) | $30–100 | Baseado em uso |
| Azure AI Search (RAG) | $70–250 | Baseado em storage + queries |
| Embeddings (re-indexação) | $5–20 | Mensal |
| OpenAI API (AI calls) | $50–500+ | **Muito variável** |
| Power BI Premium CU (XMLA) | $5.000+ (P1) | Fixo |
| Application Insights | $10–50 | Volume de logs |

**Guardrails de custo:**

```yaml
# Limites por user
ai_limits:
  tokens_per_day: 200_000
  cost_per_day_usd: 10.00
  queries_per_minute: 30

# Alertas
alerts:
  - name: "AI burn rate"
    condition: "tokens_per_hour > 50_000"
    severity: warning
    action: notify_tech_lead

  - name: "AI cost spike"
    condition: "daily_cost > 50"
    severity: critical
    action: auto_pause_ai_user
```

> Detalhe em [`custos.md`](custos.md)

---

## 9. Disaster Recovery · quando o AI dá ruim

**Cenários reais que vão acontecer:**

| Cenário | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| AI cria 1.000 medidas inúteis | Alta | Médio | Sandbox isolado + PR review |
| AI deleta tabela crítica | Média | Crítico | Tools de delete bloqueadas por padrão |
| AI expõe dado sensível via DAX | Média | Crítico (LGPD) | RLS test + DLP scanner + audit |
| AI entra em loop e custa $500 em 1h | Alta | Médio | Rate limit + cost ceiling |
| AI publica direto em Prod | Baixa | Crítico | Deploy Prod requer human approval, sempre |
| MCP server cai | Média | Baixo | Auto-restart + fallback pra modo manual |
| AI vaza segredos via prompt injection | Média | Crítico | Input validation + secret scrubbing |
| AI é usado por ex-funcionário | Baixa | Alto | RBAC dinâmico + token revocation imediato |

> Detalhe em [`disaster-recovery.md`](disaster-recovery.md)

---

## 10. Roadmap de implementação

**Fases para colocar isso em produção sem explodir nada:**

### Fase 0 · Preparação (1 semana)
- [ ] Provisionar Azure Container Apps + VNet
- [ ] Criar service principal MCP-only (escopo restrito)
- [ ] Configurar Redis pra rate limit
- [ ] Setup Application Insights
- [ ] Habilitar XMLA endpoint nos workspaces Premium/PPU

### Fase 1 · MCP Read-only (2 semanas)
- [ ] Implementar tools safe (🟢): list, get, query, format
- [ ] Configurar RBAC com roles Azure AD
- [ ] Deploy em container
- [ ] Smoke tests
- [ ] Onboarding de 2-3 devs

### Fase 2 · Knowledge Layer (2 semanas)
- [ ] Indexar data-dictionary, ADRs, past PRs
- [ ] Setup Azure AI Search
- [ ] Auto-update do índice no CI (após merge em main)
- [ ] Testar retrieval quality

### Fase 3 · MCP Write (moderate) (2 semanas)
- [ ] Tools de validação (validate-dax, format-dax)
- [ ] Tool de sugestão (suggest-measure)
- [ ] Approval workflow simples
- [ ] Workspace AI-Playground

### Fase 4 · ORM SDK (3 semanas)
- [ ] `powerbi-orm` Python package
- [ ] Read operations (query, schema, lineage)
- [ ] Write operations (measures, columns, RLS)
- [ ] Validação integrada
- [ ] Testes unitários + e2e

### Fase 5 · MCP Write (dangerous + critical) (2 semanas)
- [ ] Approval workflow completo
- [ ] Audit trail + compliance
- [ ] Cost ceilings + auto-pause
- [ ] Pen-testing interno

### Fase 6 · Rollout (contínuo)
- [ ] Onboarding gradual de times
- [ ] Métricas de aceitação
- [ ] Feedback loop
- [ ] Documentação de uso

**Total: ~10-12 semanas pra um AI-augmented BI maduro.**

---

## 11. Métricas de sucesso

**Como saber se está funcionando:**

| KPI | Meta |
|---|---|
| Tempo de dev de medida complexa | ↓ 50% |
| Acceptance rate de AI-generated DAX | > 70% |
| PRs que falham em review (Dax) | ↓ 60% |
| Tempo de onboarding de novo dev | ↓ 40% |
| Incidentes de segurança | 0 |
| Custo de AI por dev/mês | < $100 |
| NPS do dev com AI | > 50 |

---

## Próximo passo

**Aprovação da arquitetura.** Se você topar com essa direção, próximo turno eu entrego:

1. **MCP Server completo** (`mcp/powerbi-mcp-server/`) — Python + FastMCP, deployável
2. **ORM SDK** (`tools/orm/`) — `powerbi-orm` package
3. **Guardrails implementation** — middlewares FastMCP + RBAC
4. **Sandbox bootstrap script** — cria workspace AI-Playground
5. **Test harness** — validação automática de DAX
6. **Atualização da visual page** com a camada AI
7. **Atualização do zip final**
