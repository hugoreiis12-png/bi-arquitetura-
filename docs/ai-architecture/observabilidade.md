# 📊 Observabilidade · Camada AI

> Sem observabilidade, AI é caixa-preta. Você não vai confiar. Você não vai debugar.
> Aqui está o que medir, como medir, e como alertar.

## 1. Os 3 pilares

| Pilar | O que | Ferramenta |
|---|---|---|
| **Logs** | Eventos discretos (tool chamada, decisão) | Application Insights custom logs |
| **Metrics** | Valores numéricos ao longo do tempo (latência, qps) | App Insights metrics + Prometheus exporter |
| **Traces** | Caminho de uma request (correlation ID) | OpenTelemetry → App Insights |

## 2. Stack

- **OpenTelemetry SDK** no MCP server (instrumentação automática)
- **Azure Monitor Exporter** → Application Insights
- **Grafana** (opcional) para dashboards custom cross-workspace
- **Azure Alerts** para notificação (Teams, email, PagerDuty)

## 3. Métricas essenciais

### 3.1 Operacionais (SLO)

| Métrica | SLO | Alerta |
|---|---|---|
| Latência P50 do MCP | < 200ms | > 500ms (warn) |
| Latência P99 do MCP | < 2s | > 5s (critical) |
| Disponibilidade | > 99.5% | < 99% (critical) |
| Error rate | < 1% | > 2% (warn), > 5% (critical) |
| MCP tool calls/min | baseline + 2σ | > 5x baseline (warn) |
| Active users simultâneos | < 50 | > 80 (warn) |
| Memory usage | < 70% | > 85% (warn) |
| CPU usage | < 70% | > 85% (warn) |

### 3.2 Negócio (BI/AI)

| Métrica | Por quê medir |
|---|---|
| **AI acceptance rate** (% de medidas geradas aceitas em PR) | Health do AI |
| **AI failure rate por check** (sintaxe, semântica, perf, etc) | Onde AI está errando mais |
| **DAX smoke test pass rate** | Qualidade do código publicado |
| **Tempo médio de PR aberto → merge** | Velocidade de dev |
| **Medidas criadas/modificadas por dia** | Throughput |
| **Reports publicados por dia** | Throughput |
| **Refresh success rate por dataset** | Saúde do pipeline |
| **Refresh duration P50/P99** | Performance do pipeline |

### 3.3 Segurança (guardrails)

| Métrica | Por quê medir |
|---|---|
| **RBAC denials per user per day** | Tentativas suspeitas |
| **DLP blocks per day** | PII leakage attempts |
| **Approval tokens issued vs used** | Approval workflow health |
| **Approval tokens expired unused** | UX issue |
| **Rate limit hits per user** | Possível misuse |
| **Cost per user per day** | AI spend |
| **Sensitive workspace accesses** | Quem acessou o quê |
| **Anomalous query patterns** (volume, off-hours) | Possível misuse |

### 3.4 Custo

| Métrica | Granularidade |
|---|---|
| Tokens input/output | per user, per tool, per day |
| Custo OpenAI estimado | per user, per day, per month |
| Custo Power BI (CU consumidos) | per workspace, per day |
| Custo Azure (MCP, Redis, AI Search) | per service, per month |
| Custo total AI-augmented BI | per project, per month |

## 4. Implementação (Python)

```python
# powerbi_mcp/observability.py
from opentelemetry import trace, metrics
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.azure.monitor import AzureMonitorTraceExporter
from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter

# Setup global
tracer = trace.get_tracer("powerbi-mcp")
meter = metrics.get_meter("powerbi-mcp")

# Métricas custom
tool_call_counter = meter.create_counter(
    "mcp.tool.calls",
    description="Total de chamadas a tools do MCP",
)

tool_duration_histogram = meter.create_histogram(
    "mcp.tool.duration",
    unit="ms",
    description="Duração de execução de tool",
)

rbac_denied_counter = meter.create_counter(
    "mcp.rbac.denied",
    description="Tentativas negadas por RBAC",
)

approval_token_counter = meter.create_counter(
    "mcp.approval.tokens",
    description="Approval tokens emitidos/usados",
)

# Decorator
def instrumented_tool(risk_level: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tool_name = func.__name__
            start = time.time()
            
            # Increment counter
            tool_call_counter.add(1, {"tool": tool_name, "risk": risk_level})
            
            # Trace
            with tracer.start_as_current_span(f"mcp.{tool_name}") as span:
                span.set_attribute("tool.name", tool_name)
                span.set_attribute("tool.risk_level", risk_level)
                span.set_attribute("user.id", kwargs.get("user_context").user_id)
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("tool.status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("tool.status", "error")
                    span.record_exception(e)
                    raise
                finally:
                    duration = (time.time() - start) * 1000
                    tool_duration_histogram.record(duration, {"tool": tool_name})
                    span.set_attribute("tool.duration_ms", duration)
        
        return wrapper
    return decorator

# Uso
@mcp.tool(risk_level="safe")
@instrumented_tool("safe")
async def pbi_list_datasets(...):
    ...
```

## 5. Dashboards Grafana (opcional)

**Dashboard principal: "MCP Health"**

```
┌──────────────────────────────────────────────────────┐
│ MCP Tool Calls (last 24h)                            │
│ ▁▂▃▅▇█▇▅▃▂▁▁▁▂▃▅▇█▇▅▃▂▁                          │
├──────────────────────────────────────────────────────┤
│ Latência P50/P99         │  Error rate               │
│   234ms / 1.2s          │   0.3%                    │
├──────────────────────────────────────────────────────┤
│ Top 10 tools mais chamadas                            │
│ 1. pbi_list_datasets     4,521                       │
│ 2. pbi_query_dax         2,103                       │
│ 3. pbi_format_dax        1,876                       │
│ 4. pbi_get_schema          932                       │
│ 5. pbi_search_dictionary   654                       │
├──────────────────────────────────────────────────────┤
│ RBAC denials (last 7d)     │  DLP blocks (last 7d)  │
│ 12 (3 users)               │  3 (CPF pattern)        │
├──────────────────────────────────────────────────────┤
│ Custo AI (last 30d)        │  Acceptance rate        │
│ $1,234                     │  73%                    │
└──────────────────────────────────────────────────────┘
```

**Dashboard "AI Productivity":**

```
┌──────────────────────────────────────────────────────┐
│ Medidas criadas por origem (last 30d)                │
│ ████████░░ AI-geradas: 124 (62%)                      │
│ ████░░░░░░ Humano:    76  (38%)                      │
├──────────────────────────────────────────────────────┤
│ PRs com AI: 89   │  AI acceptance: 73%              │
│ PRs sem AI: 54   │  Avg time: 2.1h                   │
├──────────────────────────────────────────────────────┤
│ AI failures by check                                  │
│ syntax:    5 ( 4%)                                    │
│ semantic: 12 (10%)                                    │
│ perf:      3 ( 2%)                                    │
│ scope:     2 ( 2%)                                    │
│ naming:    8 ( 6%)                                    │
│ total fail: 30 (24%)                                  │
└──────────────────────────────────────────────────────┘
```

## 6. Alertas (Azure Monitor)

**Config via ARM template ou portal:**

```json
{
  "alerts": [
    {
      "name": "MCP High Error Rate",
      "severity": 2,
      "frequency": "PT5M",
      "windowSize": "PT15M",
      "criteria": {
        "type": "Metric",
        "metricName": "mcp.errors.rate",
        "operator": "GreaterThan",
        "threshold": 0.05
      },
      "actions": ["teams_webhook", "email_oncall"],
      "description": "Error rate do MCP acima de 5% em 15min"
    },
    {
      "name": "AI Cost Spike",
      "severity": 1,
      "frequency": "PT1H",
      "windowSize": "PT6H",
      "criteria": {
        "type": "Metric",
        "metricName": "mcp.cost.daily_usd",
        "operator": "GreaterThan",
        "threshold": 100
      },
      "actions": ["email_tech_lead"],
      "description": "Custo diário de AI passou de $100"
    },
    {
      "name": "RBAC Denial Spike",
      "severity": 1,
      "frequency": "PT15M",
      "criteria": {
        "type": "Aggregation",
        "metricName": "mcp.rbac.denied",
        "operator": "GreaterThan",
        "threshold": 10
      },
      "actions": ["email_security_team"],
      "description": "Mais de 10 negações RBAC em 15min — possível ataque"
    }
  ]
}
```

## 7. Distributed tracing

**Correlation ID propaga por TODA a chain:**

```
User Cline → MCP server → XMLA endpoint → Power BI Service
   id=abc       id=abc         id=abc          id=abc
```

**App Insights → Transaction Search:**
- Procura por `operation_id = abc`
- Vê toda a chain com duração de cada hop
- Identifica onde está o gargalo

## 8. Audit vs Observability

**Separação clara:**

| Aspecto | Audit | Observability |
|---|---|---|
| Propósito | Compliance, forense, LGPD | Operacional, debugging |
| Retenção | 7 anos | 30–90 dias |
| Granularidade | Cada ação individual | Agregações |
| Quem acessa | Stewards, auditores, legal | Devs, ops, SRE |
| Storage | Immutable (WORM) | Hot/Warm/Cold |
| Sampling | 100% (nunca dropa) | Sampling ok (1–10%) |

**Audit log** = juridicamente defensável. **Observability** = pra operar.

## 9. SLOs por stakeholder

| Stakeholder | SLO | Métrica |
|---|---|---|
| **Devs BI** | MCP responde rápido | Latência P50 < 200ms |
| **Tech Lead** | AI gera DAX que passa validação | Acceptance rate > 70% |
| **Steward** | Dados sensíveis nunca vazam | DLP blocks = catched, leaks = 0 |
| **CISO** | Tudo auditado, RBAC enforced | 100% logado, 0 incidentes |
| **CFO** | Custo controlado | Custo AI < $X/mês por projeto |
| **Usuário final** | Reports funcionam | Refresh success > 99% |

## 10. Runbook básico

**Alerta: "MCP Error Rate alto"**

```
1. Checar App Insights → Failures
2. Identificar tool com mais erros
3. Se for pbi_query_dax: checar XMLA endpoint health
4. Se for apply_approved_change: checar service principal
5. Se for systemic: restart container
6. Se persistir: rollback versão, notify on-call
```

**Alerta: "AI Cost Spike"**

```
1. Checar top users por custo (App Insights)
2. Identificar user com uso anômalo
3. Checar se é uso legítimo (job em lote) ou misuse
4. Se misuse: pause user via Redis (RATE:PAUSE)
5. Contatar user
6. Se systemic: reduzir daily limit global
```

**Alerta: "RBAC Denial Spike"**

```
1. Checar log de denials
2. Identificar pattern (mesmo user? mesmo tool? mesmo workspace?)
3. Se 1 user: investigar (treinamento? bug? ameaça?)
4. Se múltiplos users: investigar deploy novo (config errada?)
5. Se externo: ACIONAR SECURITY (possível ataque)
```
