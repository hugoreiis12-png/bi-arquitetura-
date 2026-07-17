# 🎮 Manual de Uso · AI-Augmented BI no dia a dia

> Como devs, leads, analistas e stewards interagem com a arquitetura na prática.
> Baseado em cenários reais. Cada cenário tem conversa, fluxo, código e resultado esperado.

---

## Sumário rápido

1. **O setup inicial** — abrir VSCode, configurar MCP, primeira conversa
2. **Cenário 1** — criar uma medida nova (caminho feliz)
3. **Cenário 2** — debugar uma medida lenta
4. **Cenário 3** — explorar o modelo semântico
5. **Cenário 4** — onboarding de dev novo no time
6. **Cenário 5** — validação de qualidade de dados
7. **Cenário 6** — geração automática de documentação
8. **Cenário 7** — análise de impacto cross-report
9. **Cenário 8** — deploy em produção (high stakes)
10. **Cenário 9** — quando o AI alucina
11. **Cheat sheet** — comandos rápidos
12. **Troubleshooting** — quando dá ruim

---

## 0. Setup inicial (5 min, uma vez só)

### Instalar extensões
- VSCode
- Cline (ou Continue) — cliente MCP
- Power BI Project Tools
- Tabular Editor IDE
- DAX Formatter
- GitLens

### Configurar o MCP server

Cria/edita `.vscode/mcp.json` na raiz do projeto:

```json
{
  "mcpServers": {
    "powerbi": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "PBI_TENANT_ID", "-e", "PBI_MCP_SP_CLIENT_ID", "-e", "PBI_MCP_SP_CLIENT_SECRET", "acrbi.azurecr.io/powerbi-mcp:1.0.0"],
      "env": {
        "PBI_TENANT_ID": "${input:tenant_id}",
        "PBI_MCP_SP_CLIENT_ID": "${input:sp_client_id}",
        "PBI_MCP_SP_CLIENT_SECRET": "${input:sp_client_secret}"
      }
    }
  }
}
```

> Em produção real, o MCP server roda em Azure (HTTP/SSE), não local Docker. Mas pra dev local, Docker funciona.

### Autenticar
Primeira vez que abrir, Cline pede o login Azure AD. Aprova. Token dura ~1h e é renovado automaticamente.

### Testar
Abre o chat do Cline e digita:

```
Você: "olá, em qual workspace estamos?"
```

Resposta esperada:

```
🤖 AI: Estamos no workspace **[DEV] Vendas** (id: xxx-dev).

Tenho acesso aos seguintes datasets:
- Vendas.Dataset (1.2 GB, última atualização 14:30)
- Vendas.Historico (readonly, arquivado)

Posso ajudar com o quê?
```

**Pronto. Você está pronto pra usar.**

---

## Cenário 1 · Criar uma medida nova (caminho feliz)

**Contexto:** O time comercial pediu uma métrica nova: "taxa de recompra em 90 dias". Dev abre o VSCode e pede pro AI.

### Conversa (em linguagem natural)

```
👤 Você: "preciso criar uma medida chamada Taxa Recompra 90d.
         ela mede o % de clientes que voltaram a comprar em até 90 dias
         após a primeira compra. considera apenas clientes com pelo menos
         2 compras no ano."

🤖 AI: "Vou pesquisar no data dictionary e no schema primeiro..."

         [busca RAG: 'taxa recompra'] → 0 medidas existentes
         [busca RAG: 'cliente primeira compra'] → 1 definição em d_cliente
         [lê schema: f_vendas__pedido[dt_pedido, cliente_id]]
         [lê RLS: vendas, gerente regional]

         "Entendi. Antes de gerar, deixa eu confirmar a regra de negócio:

         a) Janela de 90 dias: a partir da PRIMEIRA compra do cliente
            no dataset inteiro, ou no ano corrente?
         b) Compras canceladas/devolvidas: contam?
         c) Limite: clientes com 1 compra no ano não contam, certo?"

👤 Você: "a) a partir da primeira compra no dataset
          b) sim, contam (considera líquida)
          c) sim, 1 compra não conta, precisa ter 2+ no ano"

🤖 AI: "Perfeito. Vou gerar a medida e validar."

         [gera DAX candidato]
         [roda validação: sintaxe ✓ semântica ✓ perf ✓ escopo ✓ RLS ✓ naming ✓]

         "Validei. Resultado:

         ✅ Sintaxe: OK
         ✅ Semântica: 12.4% (3.421 de 27.604 clientes com 2+ compras)
         ✅ Performance: ~340ms (estimativa)
         ✅ Escopo: refs todas permitidas
         ✅ RLS: com role Vendedor, retorna apenas próprios clientes
         ✅ Naming: 'Vendas.Taxa Recompra 90d %' segue convenção

         Criei o PR #127: github.com/org/bi-vendas/pull/127
         Branch: ai/measure-taxa-recompra-90d
         Reviewers auto-assigned: @tech-lead, @analytics-engineer

         Verifica e aprova quando puder."

👤 Você: [abre o PR, lê a DAX gerada, aprova o PR no GitHub]
         "PR merged"

🤖 AI: "Detectei o merge. Deploy em Dev disparado.

         ⏳ Build... ✓
         ⏳ Compile... ✓
         ⏳ Smoke tests... ✓
         ⏳ Publish to [DEV] Vendas... ✓
         ⏳ Refresh... ✓

         ✅ Deploy concluído em 47s.
         Pode testar: app.powerbi.com/groups/xxx-dev
         Medida: Vendas.Taxa Recompra 90d %
         Valor atual: 12.4%"
```

### Tempo total: ~8 min (vs ~2h escrevendo do zero)

### O que aconteceu por baixo

```
1. Dev falou em português natural
2. AI fez 3 perguntas pra entender (não chutou)
3. AI gerou DAX + validou em 6 dimensões
4. AI criou branch, commit, PR automaticamente
5. Dev aprovou via GitHub (interface que ele já conhece)
6. Pipeline normal do projeto (não do AI) fez o deploy
7. AI notifica o resultado
```

### Como fica o DAX gerado

```dax
/// Taxa de clientes que voltaram a comprar em até 90 dias após
/// a primeira compra, considerando clientes com 2+ compras no ano.
Vendas.Taxa Recompra 90d % = 
VAR _clientesCom2Compras =
    CALCULATETABLE(
        VALUES( f_vendas__pedido[cliente_id] ),
        FILTER(
            VALUES( f_vendas__pedido[cliente_id] ),
            CALCULATE(
                DISTINCTCOUNT( f_vendas__pedido[pedido_id] ),
                ALLEXCEPT( f_vendas__pedido, f_vendas__pedido[cliente_id] )
            ) >= 2
        )
    )
VAR _clientesComRecompra =
    FILTER(
        _clientesCom2Compras,
        VAR _primeiraCompra =
            CALCULATE(
                MIN( f_vendas__pedido[dt_pedido] ),
                ALLEXCEPT( f_vendas__pedido, f_vendas__pedido[cliente_id] )
            )
        VAR _comprouEm90D =
            CALCULATE(
                COUNTROWS( f_vendas__pedido ),
                f_vendas__pedido[dt_pedido] > _primeiraCompra,
                f_vendas__pedido[dt_pedido] <= _primeiraCompra + 90,
                ALLEXCEPT( f_vendas__pedido, f_vendas__pedido[cliente_id] )
            )
        RETURN
            _comprouEm90D >= 1
    )
VAR _total = COUNTROWS( _clientesCom2Compras )
VAR _recompra = COUNTROWS( _clientesComRecompra )
RETURN
    DIVIDE( _recompra, _total, 0 )
```

E o smoke test:

```dax
// tests/dax/ai-127-taxa-recompra-90d.dax
EVALUATE
ROW(
    "Taxa Recompra 90d %", [Vendas.Taxa Recompra 90d %],
    "Range válido?", IF(
        [Vendas.Taxa Recompra 90d %] >= 0 && [Vendas.Taxa Recompra 90d %] <= 1,
        "OK",
        "OUT_OF_RANGE"
    ),
    "Não nulo?", NOT ISBLANK( [Vendas.Taxa Recompra 90d %] )
)
```

---

## Cenário 2 · Debugar uma medida lenta

**Contexto:** Time reportou que o dashboard de Vendas está com refresh de 15min (era 3min). Dev suspeita de uma medida nova.

### Conversa

```
👤 Você: "o refresh de Vendas tá em 15min, era 3min. alguma medida nova?"

🤖 AI: "Vou rodar análise de performance no dataset..."

         [conecta XMLA]
         [roda DMV: SELECT * FROM $SYSTEM.TMSCHEMA_MEASURES]
         [analisa últimas 20 measures por tempo de execução]
         [compara com baseline histórico]

         "Encontrei 3 medidas candidatas:

         1. 🔴 Vendas.Receita Acumulada YTD — 4.2s (era 0.8s)
            Modificada em PR #115, há 3 dias.

         2. 🟡 Vendas.Clientes Únicos Acumulado — 2.1s (era 0.6s)
            Modificada em PR #118, há 2 dias.

         3. 🟢 Vendas.Ticket Médio [R$] — 0.4s (normal)

         Suspeita principal: Vendas.Receita Acumulada YTD.

         Posso explicar o que mudou e sugerir fix?"

👤 Você: "sim"

🤖 AI: "Análise da medida Vendas.Receita Acumulada YTD:

         ANTES (PR #98, 1 mês atrás):
         [Vendas.Receita Acumulada] = TOTALYTD([Vendas.Receita Total BRL])

         DEPOIS (PR #115, 3 dias atrás):
         Vendas.Receita Acumulada YTD =
         VAR _dtMax = MAX( d_calendario[date] )
         VAR _result =
             CALCULATE(
                 [Vendas.Receita Total BRL],
                 DATESYTD( d_calendario[date], "04-30" ),
                 FILTER( ALL( d_calendario[date] ), d_calendario[date] <= _dtMax )
             )
         RETURN _result

         O problema: o FILTER(ALL(...)) com comparação de MAX força
         o engine a materializar a tabela inteira de d_calendario
         (~3650 linhas) para cada partição.

         Versão otimizada sugerida:
         Vendas.Receita Acumulada YTD =
         VAR _dtMax = MAX( d_calendario[date] )
         RETURN
             CALCULATE(
                 [Vendas.Receita Total BRL],
                 d_calendario[date] <= _dtMax,
                 DATESYTD( d_calendario[date], "04-30" )
             )

         Estima redução de 70% no tempo (de 4.2s para ~1.2s).

         Crio PR com a otimização?"

👤 Você: "cria"

🤖 AI: "PR #129 criado: feat(perf): otimiza Receita Acumulada YTD
         Branch: ai/perf-receita-acumulada-ytd
         Smoke test adicionado: latency_check.

         [aguarda aprovação no PR]"

👤 Você: [aprova o PR no GitHub]

🤖 AI: "Merge detectado. Deploy em Dev.

         ⏳ Build... ✓
         ⏳ Smoke tests... ✓
         ⏳ Publish... ✓
         ⏳ Refresh disparado (full refresh, estimado 3min)...

         ✅ Refresh concluído em 3min 12s.
         (vs 15min antes)

         Recomendo monitorar o próximo refresh agendado pra confirmar
         a tendência."
```

---

## Cenário 3 · Explorar o modelo semântico

**Contexto:** Dev novo no time, quer entender a estrutura do modelo de Vendas.

### Conversa

```
👤 Você: "me dá um overview do modelo de Vendas"

🤖 AI: "Claro. Modelo Vendas em [DEV] Vendas (atualizado em 14:30 hoje).

         📊 Resumo:
         - 8 tabelas (3 fatos, 4 dimensões, 1 calendário)
         - 47 medidas (16 em 'Vendas/Receita', 12 em 'Vendas/Margem', ...)
         - 12 relacionamentos (todos many-to-one)
         - 3 roles RLS (Gerente Regional, Vendedor, Auditor)

         📁 Tabelas (em ordem de importância):

         FATOS:
         1. f_vendas__pedido (12M linhas)
         2. f_vendas__item (45M linhas)
         3. f_metas (8k linhas)

         DIMENSÕES:
         1. d_calendario (3.650 dias, 2018-2030)
         2. d_cliente (27k clientes)
         3. d_produto (5k SKUs)
         4. d_vendedor (180 vendedores)

         🔗 Relacionamentos principais:
         f_vendas__pedido → d_cliente, d_calendario, d_produto, d_vendedor

         🔐 RLS ativo:
         - Vendedor: vê apenas vendas do próprio email
         - Gerente Regional: vê vendas da própria região
         - Auditor: vê tudo

         📂 Medidas mais usadas (por # de reports):
         1. Vendas.Receita Total BRL (23 reports)
         2. Vendas.Margem % (18 reports)
         3. Vendas.Ticket Médio [R$] (15 reports)
         4. Vendas.Pedidos (12 reports)

         O que quer explorar primeiro?"

👤 Você: "me mostra a hierarquia de Cliente"

🤖 AI: "Hierarquia: Cliente → Segmento → Região

         d_cliente
         ├── cliente_id (PK)
         ├── nm_cliente
         ├── segmento (PME | Enterprise | Governo)
         ├── regiao (Sul | Sudeste | Norte | Nordeste | Centro-Oeste)
         ├── vendedor_email (FK → d_vendedor)
         ├── dt_cadastro
         └── is_ativo

         d_vendedor
         ├── vendedor_id (PK)
         ├── nm_vendedor
         ├── email (= USERPRINCIPALNAME() no RLS)
         └── regiao

         Relacionamentos:
         f_vendas__pedido[cliente_id] → d_cliente[cliente_id] (1:N)
         d_cliente[vendedor_email] → d_vendedor[email] (1:N)

         RLS:
         - Vendedor filtra por d_cliente[vendedor_email] = USERNAME()
         - Gerente Regional filtra por d_cliente[regiao] in (USERNAME()'s region)

         Quer ver exemplo de drill-down? Posso rodar uma query pra você."
```

---

## Cenário 4 · Onboarding de novo dev

**Contexto:** Dev novo entrou no time. Senta na frente do VSCode.

### Fluxo (primeiras 2h)

```
09:00 — Dev clona o repo, abre VSCode
09:05 — Extension prompt aparece, instala recomendadas
09:10 — Cline pergunta: "Bem-vindo ao bi-vendas! Sou seu assistente AI.
        Posso te ajudar a entender o projeto, criar medidas, debugar.
        Por onde quer começar?"

         Opções sugeridas:
         a) "Me dá um tour pelo projeto"
         b) "Me mostra o modelo de Vendas"
         c) "Quais são as medidas mais importantes?"
         d) "Me ensina o padrão de nomenclatura"

09:15 — Dev clica (a). AI roda tour guiado.

09:30 — Dev pergunta: "como eu crio uma medida nova?"

         AI: "Posso fazer isso pra você. Você descreve a regra de
         negócio em português, eu valido, gero DAX, valido de novo
         em sandbox, e abro um PR. Você revisa e aprova.

         Quer tentar? Me conta a medida que você precisa criar."

09:45 — Dev cria primeira medida com supervisão do AI.

10:30 — Dev roda primeiro deploy (merge de PR já aberto).

10:45 — Dev pergunta: "tem algum débito técnico conhecido?"

         AI: "Sim, tenho 3 items no backlog (do último audit):
         1. Medida Vendas.Lucro Líquido BRL usa FILTER (pode otimizar)
         2. d_calendario tem 2 colunas não usadas (dt_fiscal_ano_fim, ano_fiscal_label)
         3. RLS de Auditor está vazio (sem members)

         Quer que eu crie PRs pra algum desses?"
```

### O que o AI faz pelo dev novo
- **Contextualiza** o projeto (não é só "leia o README")
- **Ensinca** padrões via exemplos
- **Gera código** com supervisão
- **Aponta débitos técnicos** automaticamente
- **Faz onboarding** de forma conversacional (não documentação densa)

---

## Cenário 5 · Validação de qualidade de dados

**Contexto:** Antes de fechar o mês, dev quer checar a qualidade dos dados de Vendas.

### Conversa

```
👤 Você: "roda uns checks de qualidade de dados em Vendas"

🤖 AI: "Rodando 7 checks padrão..."

         [roda queries em paralelo via XMLA]

         ✅ 1. Unicidade: pedido_id — 100% único
         ✅ 2. Não-nulos: cliente_id — 0% null
         ⚠️ 3. Não-nulos: dt_faturamento — 0.3% null (78 pedidos)
         ✅ 4. Range: valor_brl — todos entre 0 e 1M
         ✅ 5. Referência: cliente_id existe em d_cliente — 100%
         ✅ 6. Referência: produto_id existe em d_produto — 100%
         ❌ 7. Regra: pedidos com dt_faturamento < dt_pedido
            42 pedidos (0.001%) com faturamento ANTERIOR ao pedido

         Resumo: 5 ✅, 1 ⚠️, 1 ❌

         Quer que eu detalhe o problema dos 42 pedidos?"

👤 Você: "sim, e me diz o que fazer"

🤖 AI: "Os 42 pedidos com dt_faturamento < dt_pedido:

         Padrão identificado: 38 deles são de um único vendedor
         (vendedor_id = 145) e todos com dt_pedido em 2026-06-15
         (um dia específico). Provável erro em lote (data do sistema
         estava errada nesse dia).

         Sugestão: abrir issue #132 para investigar, OU
         se for erro conhecido, documentar a regra e excluir
         esses 42 do dataset de qualidade.

         Quer que eu abra a issue?"

👤 Você: "abre"

🤖 AI: "Issue #132 criada: 'data quality: 42 pedidos com dt_faturamento < dt_pedido'
         Assignee: @tech-lead
         Labels: data-quality, ai-detected

         Detalhes no corpo da issue + queries reproduzíveis."
```

---

## Cenário 6 · Geração automática de documentação

**Contexto:** Time quer melhorar o data dictionary. Dev pede pro AI.

### Conversa

```
👤 Você: "documente todas as medidas de Vendas que ainda não estão
         no data dictionary"

🤖 AI: "Encontrei 12 medidas sem documentação. Documentando..."

         [lê TMDL de cada medida]
         [analisa expressão DAX]
         [busca em RAG: referências cruzadas]
         [gera documentação em markdown]

         Documentação adicionada em docs/data-dictionary.md (PR #133).
         Exemplos de entries gerados:

         ---

         ### Vendas.Lucro Líquido BRL
         **Tipo:** Medida
         **Pasta:** Vendas/Lucro
         **Descrição:** Lucro após todos os descontos e devoluções,
         considerando apenas receita faturada.
         **Fórmula:** `Receita Total BRL - CMV - Despesas Variáveis`
         **Dependências:** f_vendas__pedido, d_produto[custo_unitario]
         **RLS:** Funciona com qualquer role
         **Última atualização:** PR #98 (2026-06-12)
         **Reports que usam:** Dashboard Financeiro, Relatório Mensal

         ---

         ✅ PR #133 aberto com 12 medidas documentadas.
         Reviewer: @steward-dados"
```

---

## Cenário 7 · Análise de impacto cross-report

**Contexto:** Dev quer mudar uma medida muito usada, mas precisa saber quem depende dela.

### Conversa

```
👤 Você: "se eu mudar Vendas.Receita Total BRL, o que quebra?"

🤖 AI: "Análise de impacto (via lineage + dependency graph)..."

         [consulta Power BI REST API: GetReports]
         [consulta XMLA: $SYSTEM.TMSCHEMA_DEPENDENCIES]
         [cruzamento com catálogo de reports]

         "A medida Vendas.Receita Total BRL é usada em:

         📊 23 reports:
         - Dashboard Vendas Geral (workspace Vendas)
         - Relatório Comercial Mensal (workspace Vendas)
         - Forecast 2026 (workspace Vendas)
         - ...

         📁 8 datasets derivados (dataflows que copiam):
         - Vendas.Mensal (dataflow)
         - Vendas.Snapshots
         - ...

         🔗 12 medidas dependem dela:
         - Vendas.Margem %
         - Vendas.Receita Acumulada
         - Vendas.Ticket Médio
         - Vendas.Lucro
         - ...

         ⚠️ Risco: ALTO. Qualquer mudança no cálculo propaga.

         Recomendações:
         1. Criar medida NOVA (Vendas.Receita Total BRL v2) ao invés
            de modificar a existente
         2. Migrar reports gradualmente
         3. Depreciar a antiga após 30 dias

         Quer que eu crie a v2 automaticamente?"
```

---

## Cenário 8 · Deploy em produção (high stakes)

**Contexto:** Steward precisa promover um hotfix validado pra Prod.

### Conversa

```
👤 Você: "PR #127 está validado em Test. Promover pra Prod."

🤖 AI: "Entendido. Deploy em Prod é ação CRÍTICA.

         Requisitos:
         1. Você tem role BI-AI-Steward? [check]
         2. PR #127 passou todos os smoke tests? [check ✓]
         3. PR #127 foi revisado por 1+ reviewer? [check ✓]
         4. Approval token solicitado? [pendente]

         Gerando token request..."

         [AI posta card no Teams pro canal #bi-deploys]

         ┌─────────────────────────────────────────────┐
         │ 🚀 AI Deployment Request                    │
         │                                             │
         │ PR: #127 (feat: Taxa Recompra 90d)          │
         │ Solicitante: @joao@empresa.com              │
         │ Ambiente: [PROD] Vendas                     │
         │ Mudanças: 1 medida nova, 1 smoke test       │
         │ Smoke tests: ✅ 100%                        │
         │ Reviewers: @ana-lead, @carlos-steward      │
         │ Aprovações: 0/2 (requer 2 pra prod)         │
         │                                             │
         │ [✅ Aprovar]  [❌ Rejeitar]  [🔍 Revisar] │
         └─────────────────────────────────────────────┘

👤 Você: [aprova no card]

🤖 AI: "1/2 aprovações. Aguardando segunda."

         [segundo steward @maria-steward aprova]

🤖 AI: "2/2 aprovações. Prosseguindo com deploy.

         [gera approval token (15min TTL, single-use)]
         [executa deploy pipeline]

         ⏳ Build Prod... ✓
         ⏳ Smoke tests em Prod... ✓
         ⏳ Publish to [PROD] Vendas... ✓
         ⏳ Refresh parcial (apenas tabela afetada)... ✓
         ⏳ Validação RLS com user real... ✓

         ✅ Deploy concluído em 2min 14s.

         Métricas pós-deploy:
         - Medida acessível em 5s após publish
         - Refresh incremental: 8s (vs full: 3min)
         - RLS testado: 3 roles, 0 vazamentos
         - Queries básicas: <500ms

         Monitorando nas próximas 24h."
```

---

## Cenário 9 · Quando o AI alucina

**Contexto:** AI tenta gerar medida, falha na validação, tenta corrigir 3x e não consegue.

### Conversa

```
👤 Você: "cria medida: Churn Risk Score baseado em recência,
         frequência e valor dos clientes"

🤖 AI: "Vou gerar."

         [tentativa 1: DAX com RFM]
         [validação: sintaxe ✓, semântica ✓, perf ❌ (8.2s)]

         "Tentativa 1 falhou por performance. Otimizando..."

         [tentativa 2: DAX otimizado com VAR]
         [validação: sintaxe ✓, semântica ✓, perf ✓ (1.1s),
          escopo ❌ — referencia tabela que não existe: d_cliente_rfm]

         "Tentativa 2 falhou: referenciei tabela d_cliente_rfm
         que não existe no dataset. Criando a tabela antes..."

         [tentativa 3: com d_cliente_rfm criada]
         [validação: sintaxe ✓, semântica ✓, perf ✓, escopo ✓,
          RLS ❌ — query retorna dados diferentes com RLS ativo]

         "Tentativa 3 falhou no check de RLS: a medida vaza dados
         entre regiões quando role Gerente Regional está ativo.

         Análise: o FILTER que uso pra calcular frequência
         não respeita o filtro de RLS.

         3 tentativas esgotadas. Recomendo abordagem diferente:
         ao invés de gerar RFM em DAX, criar tabela pré-calculada
         em Power Query (no ETL) e usar DAX simples pra ler.

         Quer que eu:
         a) Te entregue a análise do problema pra você implementar?
         b) Tente outra abordagem (4ª tentativa)?
         c) Sugira um expert humano pra ajudar?"

👤 Você: "a"

🤖 AI: "Documentando análise em issue #135:

         Título: '[AI] Churn Risk Score - análise de bloqueio'

         Conteúdo:
         - 3 abordagens tentadas
         - Por que cada uma falhou
         - Recomendação: pré-calcular em ETL
         - Estimativa de esforço: 4h ETL + 1h DAX
         - Tags: ai-blocked, rfm, needs-human-expert

         Assignee: @analytics-engineer (recomendado)
         Labels: ai-blocked, needs-human, medium-priority

         Issue criada."
```

**Importante:** o AI sabe quando parar e pedir ajuda humana. Isso é parte do design (não bug).

---

## Cheat sheet · comandos rápidos

### Exploração

```
"lista os datasets deste workspace"
"qual a estrutura da tabela d_cliente?"
"medidas mais usadas em Vendas"
"que reports usam Receita Total BRL?"
"qual a diferença entre Dev e Prod?"
```

### Criação

```
"cria medida [nome] que [descrição em português]"
"cria relacionamento entre f_vendas e d_produto via produto_id"
"cria role RLS pra [descrição da permissão]"
"documenta a medida [nome]"
"abre issue pra débito técnico: [descrição]"
```

### Debug

```
"por que o refresh tá lento?"
"essa medida tem problema de performance?"
"verifica qualidade dos dados de [tabela]"
"essa query tá retornando o valor certo?"
"testa RLS com role Vendedor"
```

### Deploy

```
"promove PR #[X] pra Test"
"gera approval token pra Prod (PR #[X])"
"faz rollback do último deploy em Dev"
"compara Dev vs Prod"
```

### Meta

```
"o que mudou na última semana?"
"qual a acceptance rate do AI nos últimos 30 dias?"
"quais PRs estão esperando review?"
"tickets atribuídos a mim"
```

---

## Troubleshooting

| Problema | Causa provável | Solução |
|---|---|---|
| AI não responde | MCP server caiu | Verificar status: `curl https://mcp.empresa.com/health` |
| AI responde "permissão negada" | User sem role Azure AD | Pedir ao admin pra adicionar no group correto |
| Validação sempre falha | Sandbox com dados ruins | Verificar se AI-Playground tem dados sincronizados |
| Deploy demora muito | Pipeline sobrecarregado | Checar status do Azure DevOps/GitHub Actions |
| AI gera DAX "estranho" | Pouco contexto | Pedir: "antes de gerar, me explica a regra de negócio" |
| Approval token expirou | Demorou mais que 15min | Gerar novo token via CLI ou bot |
| AI ignora instrução | Prompt mal estruturado | Reformular: ser explícito sobre o que quer |
| RBAC bloqueia acesso legítimo | Config errado | Pedir ao admin pra revisar `workspace_allowlist` |
| Custos de AI subindo | Loop ou misuse | Checar audit log, identificar user, auto-pause se abuso |

---

## O que você NÃO vai fazer (vs antes)

| Tarefa | Antes (sem AI) | Depois (com AI) |
|---|---|---|
| Escrever DAX do zero | 30min–2h | 5min (conversa) |
| Debugar medida lenta | 1–4h | 10min (AI sugere) |
| Onboarding de novo dev | 2 semanas | 2–3 dias |
| Gerar documentação | 1 dia | 30min (AI gera) |
| Cross-impact analysis | Manual, 2h | 2min (AI mapeia) |
| Deploy com aprovação | Email + manual | 2 clicks no Teams |
| Audit mensal de qualidade | 1 dia | 1h (AI roda checks) |
| Comparar Dev vs Prod | Manual via portal | 1 pergunta ao AI |

**Estimativa de ganho:** 30–50% de tempo economizado por dev, por dia.

---

## Comandos de admin (ops)

```
# Pausar AI para um user (emergência)
powerbi-mcp admin pause-user --user joao@empresa.com --duration 1h

# Ver audit log em tempo real
powerbi-mcp admin audit --tail --filter user=joao

# Forçar refresh de schema
powerbi-mcp admin refresh-schema --workspace bi-vendas-dev

# Rotacionar secret do SP
powerbi-mcp admin rotate-sp --name bi-mcp-server

# Bloquear workspace (emergência)
powerbi-mcp admin block-workspace --workspace bi-vendas-prod --reason "investigando vazamento"
```

---

## Próximo passo

Esse manual é o que sua equipe vai consultar no dia a dia. Agora a pergunta real:

**Quer que eu comece a implementar?**

Se sim, próximo turno entrego (em ordem):
1. **MCP server** (código Python completo, deploy config, testes)
2. **Bootstrap script** (cria toda a infra automaticamente)
3. **`powerbi-orm` SDK** (código + testes)
4. **Guardrails** (RBAC, DLP, audit, approval)
5. **Configurações Cline/Continue** prontas
6. **Atualização visual + zip final**

Manda o "vai" que eu vou. 🚀
