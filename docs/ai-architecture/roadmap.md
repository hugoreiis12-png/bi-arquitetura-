# 🗺️ Roadmap de Implementação AI-Augmented BI

> Plano executável em fases. Cada fase termina com algo usável.
> Estimativas conservadoras para 1-2 devs full-time.

## Visão geral

```
Fase 0 ─→ Fase 1 ─→ Fase 2 ─→ Fase 3 ─→ Fase 4 ─→ Fase 5 ─→ Fase 6
Setup     MCP R/O   Knowledge  MCP W     ORM      MCP W    Rollout
                  Layer       Moderate           Critical
                                                    
1 sem     2 sem     2 sem      2 sem     3 sem    2 sem    contínuo
                                                                  
T O T A L:  ~ 1 0 - 1 2   s e m a n a s
```

## Fase 0 · Preparação (1 semana)

**Objetivo:** infra pronta pra receber o MCP server.

### Infra
- [ ] Provisionar Azure Container Apps Environment
- [ ] Criar VNet + subnet dedicada
- [ ] Provisionar Redis (cache + rate limit)
- [ ] Provisionar App Insights
- [ ] Setup Key Vault pra secrets
- [ ] Habilitar XMLA endpoint nos workspaces Premium/PPU existentes
- [ ] Habilitar Private Endpoint pro Power BI (se PPU)

### Identidade
- [ ] Criar Service Principal dedicado `bi-mcp-server`
- [ ] Atribuir role mínima (Power BI Service Contributor no scope certo)
- [ ] Configurar secret rotation policy (90 dias)
- [ ] Criar Azure AD groups: `BI-AI-Reader`, `BI-AI-Developer`, `BI-AI-Lead`, `BI-AI-Steward`, `BI-AI-Admin`
- [ ] Adicionar primeiros usuários nos groups

### Workspaces
- [ ] Criar workspace `bi-ai-playground` em cada projeto (Vendas, Estoque, RH)
- [ ] Copiar datasets de Prod pra Playgrounds
- [ ] Configurar Playgrounds com capacidade separada (ou separada do Premium compartilhado)

### Baseline
- [ ] Baseline de uso humano (latência, queries, custos) pra comparar depois
- [ ] Comunicar time sobre a iniciativa
- [ ] Definir champions (1 dev super-user por área)

**Entregável:** Infra provisionada, SP configurado, 1 workspace AI-Playground.

---

## Fase 1 · MCP Read-only (2 semanas)

**Objetivo:** devs podem conversar com AI sobre os dados via MCP, mas AI não modifica nada.

### MCP Server
- [ ] Criar repo `bi-mcp-server`
- [ ] Setup FastMCP + Dockerfile
- [ ] Implementar auth (JWT validation, SP token acquisition)
- [ ] Implementar ferramentas safe:
  - `pbi_list_datasets`
  - `pbi_get_model_schema`
  - `pbi_query_dax` (com row limit + timeout)
  - `pbi_format_dax`
  - `pbi_get_measure_definition`
  - `pbi_diff_environments`
- [ ] Implementar audit log
- [ ] Implementar rate limit
- [ ] Implementar DLP (input + output)
- [ ] CI/CD pro MCP server

### IDE
- [ ] Setup Cline/Continue com MCP server configurado
- [ ] Workspace template com `.vscode/mcp.json` apontando pro MCP
- [ ] Documentação de uso

### Validação
- [ ] Testes unitários (mock Power BI)
- [ ] Testes de integração (Power BI real)
- [ ] Penetration testing básico
- [ ] Piloto com 2-3 devs selecionados

**Entregável:** MCP server deployado, devs conseguem fazer perguntas sobre dados via VSCode.

**Métricas-alvo:**
- Latência P50 < 500ms
- Error rate < 1%
- AI identifica schema corretamente em > 90% dos casos

---

## Fase 2 · Knowledge Layer / RAG (2 semanas)

**Objetivo:** AI tem contexto rico (data dict, ADRs, past PRs), não só schema.

### Coleta
- [ ] Indexar `docs/data-dictionary.md` de cada projeto
- [ ] Indexar `docs/naming-conventions.md`
- [ ] Indexar ADRs
- [ ] Indexar últimos 200 PRs (apenas descrição + comentários)
- [ ] Indexar issues fechadas
- [ ] Business glossary

### Pipeline
- [ ] Setup Azure AI Search
- [ ] Setup embedding generation
- [ ] Setup indexer (roda após merge em main)
- [ ] Chunking strategy (512 tokens, overlap 64)
- [ ] Hybrid search (keyword + vector)

### MCP Integration
- [ ] Tool `pbi_search_dictionary` (busca RAG)
- [ ] Resource `data-dictionary` (carrega contexto sob demanda)
- [ ] Prompt template `generate_measure_with_context`

### Validação
- [ ] Retrieval eval: "quão bem o AI acha a info certa?"
- [ ] Human eval: 20 perguntas, AI responde certo em > 80%
- [ ] Latência de retrieval < 300ms

**Entregável:** AI tem contexto rico, respostas mais precisas.

---

## Fase 3 · MCP Write · Moderate (2 semanas)

**Objetivo:** AI pode gerar DAX, mas sempre via PR (nunca direto no Service).

### Tools
- [ ] `pbi_validate_dax_syntax`
- [ ] `pbi_suggest_measure`
- [ ] `pbi_propose_measure_update` (cria branch + PR)
- [ ] `pbi_propose_relationship`
- [ ] `pbi_propose_column`

### Validação
- [ ] Harness completo de validação (sintaxe + semântica + perf + escopo + RLS + naming)
- [ ] Sandbox de execução
- [ ] Auto-correction loop (max 3 retries)
- [ ] Relatório de validação legível

### Workflow
- [ ] PR template automático com métricas de validação
- [ ] Labels automáticas (`ai-generated`, `needs-review`)
- [ ] Reviewer auto-assignment (1 reviewer do projeto)
- [ ] Integração com Cline/Continue pra mostrar progresso

### Piloto
- [ ] 1 projeto-piloto (Vendas)
- [ ] 2 devs testando por 1 semana
- [ ] Feedback loop

**Entregável:** AI gera medidas/relacionamentos via PR, com validação completa.

**Métricas-alvo:**
- AI acceptance rate > 50% (versão 1, vai melhorar)
- 0 incidentes de segurança
- Tempo de criação de medida ↓ 60%

---

## Fase 4 · ORM SDK (3 semanas)

**Objetivo:** Python SDK pra manipular o modelo semantic de forma fluente.

### Core
- [ ] `powerbi-orm` package (pyproject.toml, setup)
- [ ] `Dataset` class com connection (XMLA + REST)
- [ ] `Table`, `Column`, `Measure`, `Relationship`, `Role` classes
- [ ] Query API (DAX execution com cache)
- [ ] Schema introspection

### Write operations
- [ ] Add/remove measure
- [ ] Add/remove column
- [ ] Add/remove relationship
- [ ] Add/modify RLS role
- [ ] Migration framework (up/down com versionamento)

### Validação
- [ ] Integração com pbi-tools compile
- [ ] DAX syntax check
- [ ] Naming convention check
- [ ] Performance estimation
- [ ] Dry-run mode

### Testes
- [ ] Unit tests (> 80% coverage)
- [ ] Integration tests contra sandbox
- [ ] E2E tests (migration full cycle)
- [ ] Documentation com examples

### Publicação
- [ ] Publish to internal PyPI (Azure Artifacts)
- [ ] README + docs
- [ ] Type hints completos (mypy strict)

**Entregável:** `powerbi-orm` package pronto pra uso.

---

## Fase 5 · MCP Write · Dangerous + Critical (2 semanas)

**Objetivo:** AI pode aplicar mudanças aprovadas, com workflow rigoroso.

### Tools
- [ ] `pbi_apply_approved_change` (critical, requer token)
- [ ] `pbi_refresh_dataset` (critical, requer token)
- [ ] `pbi_delete_measure` (critical, requer token)
- [ ] `pbi_modify_rls` (critical, requer 2 approvers)

### Approval workflow
- [ ] Approval token service
- [ ] CLI: `powerbi-mcp token issue`
- [ ] GitHub bot: `/ai-approve <action>`
- [ ] Teams adaptive card
- [ ] Single-use, 15min TTL
- [ ] 2-approver rule for prod

### Audit + Compliance
- [ ] Audit log completo (immutable, 7 anos)
- [ ] Compliance review (LGPD, SOX se aplicável)
- [ ] Penetration testing completo
- [ ] Incident response playbook

### Observability
- [ ] Full OpenTelemetry instrumentation
- [ ] Grafana dashboards
- [ ] Azure Alerts configurados
- [ ] Cost monitoring

**Entregável:** AI pode fazer deploy em Prod, com gates rigorosos.

---

## Fase 6 · Rollout e Otimização (contínuo)

**Objetivo:** expandir uso, melhorar adoption, otimizar.

### Onboarding
- [ ] Docs de uso (best practices, anti-patterns)
- [ ] Vídeo tutorial
- [ ] Workshop interno
- [ ] Slack/Teams channel de suporte
- [ ] Champion program (1 super-user por projeto)

### Expansão
- [ ] Rollout pra outros projetos (Estoque, RH)
- [ ] Customização por projeto (catalog, naming)
- [ ] Integração com outras ferramentas (Jira, ServiceNow)
- [ ] NL2DAX (linguagem natural → DAX)
- [ ] NL2PQ (linguagem natural → Power Query)

### Otimização
- [ ] Fine-tuning baseado em logs (acceptance/rejection patterns)
- [ ] Auto-suggestion de melhorias (medidas que sempre falham, etc)
- [ ] Performance optimization (caching, prefetching)
- [ ] Cost optimization (modelo mais barato pra tarefas simples)

### Métricas de sucesso
- [ ] AI acceptance rate > 70%
- [ ] Tempo de dev ↓ 50%
- [ ] Custo AI < $100/dev/mês
- [ ] NPS devs > 50
- [ ] 0 incidentes de segurança

---

## Marcos (milestones)

| Marco | Data alvo | O que desbloqueia |
|---|---|---|
| **M1** | Fim Fase 1 | Devs podem explorar dados via AI |
| **M2** | Fim Fase 2 | AI conhece contexto do negócio |
| **M3** | Fim Fase 3 | AI gera código (com review humano) |
| **M4** | Fim Fase 4 | ORM SDK pronto pra devs Python |
| **M5** | Fim Fase 5 | AI pode deployar (com approval) |
| **M6** | Fim Fase 6 | AI-augmented BI em produção, escala |

---

## Riscos do roadmap

| Risco | Mitigação |
|---|---|
| **Sprawl de features** (quero tudo ao mesmo tempo) | Stick to phases. Cada fase é gateada por validação. |
| **Resistência cultural** ("AI vai tirar meu emprego") | Comunicação clara, AI como ferramenta, não substituto. Champions. |
| **Custo de AI explodir** | Cost ceilings + alertas + sampling de requests. |
| **Incidente de segurança** | Penetration testing, audit log imutável, incident response. |
| **XMLA endpoint instável** | Circuit breaker, fallback pra modo manual, cache agressivo. |
| **Power BI mudar APIs** | Versionamento explícito, testes de contract. |
| **Lock-in com vendor de AI** | Abstrair AI provider (OpenAI hoje, Anthropic amanhã, local LLM depois). |

---

## Investimento estimado

| Recurso | Custo mensal estimado |
|---|---|
| Azure Container Apps | $50 |
| Azure AI Search (Standard S1) | $250 |
| Azure Redis (Basic) | $30 |
| App Insights | $50 |
| Key Vault | $5 |
| OpenAI API (500k tokens/dia) | $300 |
| Power BI Premium P1 (já existente) | $5.000 |
| **Total incremental** | **~$700/mês** |
| Custo por dev/mês | $35 |

ROI esperado: 1 dev full-time economizado (R$ 15k/mês) → payback em < 1 mês.

---

## Próximo passo

**Decisão:** você aprova esse roadmap?

Se sim, próximo turno eu entrego:
1. **MCP server completo** (código, deploy config, testes)
2. **ORM SDK** (código, testes, docs)
3. **Configurações de guardrails** (RBAC, DLP, approval, audit)
4. **Bootstrap script** (cria infra completa automaticamente)
5. **Atualização visual** + zip final

Se tiver ajustes no roadmap (ex: mudar prioridade, cortar fase, etc), me diz que eu adapto.
