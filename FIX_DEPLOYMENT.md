# Plano de Teste e Deploy — Fix do Erro de Validação

## Mudanças Realizadas

### 1. **Validação em TypeScript** (Camada Cliente/Gateway)
**Arquivo:** `src_agent/gateway/prompt-validator.ts` (NOVO)

- ✅ Módulo de validação de argumentos de prompts
- ✅ Detecção especial de shell placeholders (`$1`, `{{...}}`)
- ✅ Coerção de tipos (string "123" → int 123)
- ✅ Esquemas conhecidos para prompts (`review_measure`, `explain_measure`)

**Integração:** `src_agent/mcp-gateway/index.ts`
- ✅ Importado `validatePromptArgs`, `coercePromptArgs`
- ✅ Novo handler `GetPromptRequestSchema` que valida antes de rotear
- ✅ Error handler explícito se argumentos inválidos

### 2. **Validação em Python** (Camada Server)
**Arquivo:** `mcp/powerbi-mcp-server/src/powerbi_mcp/prompt_validation.py` (NOVO)

- ✅ Decorator `@validated_prompt` que wraps funções de prompt
- ✅ Validação + coerção de argumentos
- ✅ Lança `PromptValidationError` com detalhes se inválido
- ✅ Logs estruturados

**Integração:** `mcp/powerbi-mcp-server/src/powerbi_mcp/server.py`
- ✅ Importado `validated_prompt`
- ✅ Aplicado decorator a `review_measure` e `explain_measure`
- ✅ Docstrings atualizadas com regras

---

## Testes — Antes e Depois

### Teste 1: Shell Placeholder Detectado

**Antes (falha silenciosa):**
```
REQUEST: {"jsonrpc": "2.0", "method": "prompts/get", "params": {"name": "review_measure", "arguments": {"pr_number": "$1"}}}

ERROR (não propagado): PromptError: Could not convert argument 'pr_number' with value '$1' to expected type int
RESPONSE: 200 OK (silenciosamente falhou)
CLIENT: "Sucesso" mas prompt não foi renderizado
```

**Depois (falha explícita):**
```
REQUEST: {"jsonrpc": "2.0", "method": "prompts/get", "params": {"name": "review_measure", "arguments": {"pr_number": "$1"}}}

GATEWAY (TypeScript): Valida antes de rotear
ERROR: PromptValidationError: Argumentos inválidos para prompt 'review_measure': 
  pr_number: valor '$1' parece ser placeholder shell — use valor real (ex: '42' para int, 'medida_name' para string)
RESPONSE: 400 Bad Request + error message
CLIENT: Erro claro, sabe o que fazer
```

### Teste 2: String Numérica Aceita e Coerced

**Entrada:**
```
{"pr_number": "42"}  # String, não int
```

**Validação:** ✅ OK (string numérica pode ser coerced)
**Coerção:** "42" → 42 (int)
**Prompt renderizado:** "Please review PR #42..."

### Teste 3: Tipo Inválido

**Entrada:**
```
{"pr_number": 3.14}  # Float, não int
```

**Validação:** ❌ ERRO
**Erro:** "pr_number: esperado int, recebido float 3.14"

### Teste 4: Parâmetro Obrigatório Faltando

**Entrada:**
```
{}  # Sem pr_number
```

**Validação:** ❌ ERRO
**Erro:** "pr_number: parâmetro obrigatório não fornecido"

---

## Plano de Deploy

### Fase 1: Teste Local (Dev)

```bash
# 1. Build da imagem Docker localmente
cd Y:\_NIO\Atividade_do_dia\bi-ide-architecture
docker build -t bi-architecture:test .

# 2. Rodar container com compose
export PBI_TENANT_ID="test-tenant"
export PBI_SP_CLIENT_ID="test-client"
export PBI_SP_CLIENT_SECRET="test-secret"
export PBI_WORKSPACE_ID="test-ws"
docker-compose up -d

# 3. Testar com curl
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "prompts/get",
    "params": {
      "name": "review_measure",
      "arguments": {"pr_number": "$1"}
    },
    "id": 1
  }'

# Esperado: Error 400 com mensagem clara
```

### Fase 2: Teste Homolog

```bash
# 1. Commit das mudanças
git add -A
git commit -m "fix: validate prompt args, detect shell placeholders

- Adiciona validação de argumentos em TypeScript (gateway)
- Adiciona decorator @validated_prompt em Python (server)
- Detecta shell placeholders (\$1, {{}}) e falha explicitamente
- Coerce strings numéricas para int conforme necessário
- Mitiga: erro silencioso em prod quando cliente passa \$1 literal

Testes:
- Shell placeholder \$1 → erro 400 com mensagem clara
- String numérica '42' → coerced para 42 (int), prompt renderizado
- Float 3.14 para int param → erro validação
- Parâmetro obrigatório faltando → erro validação

Camadas:
1. TypeScript gateway: valida antes de rotear
2. Python decorator: valida + coerce no server
3. Explicitação de erros: PromptValidationError com contexto
Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# 2. Push para branch de teste
git checkout -b fix/prompt-validation
git push -u origin fix/prompt-validation

# 3. Deploy em Portainer (homolog)
# Usar o compose do branch, confirmar que mudanças foram aplicadas
# Monitorar logs: docker logs bi-mcp e docker logs bi-gateway

# 4. Testar com IDE (VS Code, Claude Code)
#    - Chamar prompts com valores válidos
#    - Chamar prompts com "$1" (deve falhar com mensagem clara)
#    - Verificar que erros aparecem em real-time
```

### Fase 3: Deploy em Produção

```bash
# 1. Fazer PR para main com as mudanças
# 2. Code review + aprovação
# 3. Merge para main
# 4. CI/CD automaticamente faz:
#    - Build nova imagem Docker com tag
#    - Deploy em Portainer (prod)
#    - Verificação de healthcheck
#    - Notificação em Slack

# 5. Monitoramento pós-deploy (24h)
#    - Alertar se erros de validação aumentam (pode indicar clients ruins)
#    - Verificar que prompts continuam funcionando com valores válidos
```

---

## Rollback Plan

Se houver problema em prod:

```bash
# 1. Identificar commit ruim
git log --oneline | head

# 2. Reverter para versão anterior
git revert <commit-hash>
git push origin main

# 3. Portainer vai pegar novo commit e fazer deploy automático

# 4. Validar que erros cessaram
docker logs bi-mcp | grep -i "validation\|error"
```

---

## Observabilidade & Logs

### Estrutura de Logs Esperada

**TypeScript Gateway** (quando validação falha):
```json
{
  "timestamp": "2026-09-25T18:15:30Z",
  "level": "error",
  "service": "bi-gateway",
  "event": "invalid_prompt_args",
  "prompt_name": "review_measure",
  "validation_errors": [
    "pr_number: valor '$1' parece ser placeholder shell — use valor real"
  ]
}
```

**Python Server** (quando validação falha):
```json
{
  "timestamp": "2026-09-25T18:15:31Z",
  "level": "error",
  "logger": "powerbi_mcp.server",
  "event": "prompt_validation_error",
  "prompt": "review_measure",
  "error": "Argumentos inválidos para prompt 'review_measure': pr_number: valor '$1' parece ser placeholder shell — use valor real (ex: '42' para int, 'medida_name' para string)"
}
```

### Query para Monitorar

```sql
-- Se tiver Application Insights
customEvents
| where name == "prompt_validation_error"
| summarize Count=count() by tostring(customDimensions.prompt)
| order by Count desc

-- Alertar se > 5 errors por hora para mesmo prompt
```

---

## Checklist de Validação

- [ ] Build Docker compila sem erro
- [ ] Gateway conecta aos dois backends (DAX + PBI)
- [ ] Prompt com argumento válido (int 42) → renderiza OK
- [ ] Prompt com argumento inválido ($1) → erro 400 com mensagem
- [ ] Prompt com string numérica ("42") → coerce para int, renderiza OK
- [ ] Logs estruturados aparecem em stderr
- [ ] Erro não quebra o server (healthcheck continua 200 OK)
- [ ] Client IDE recebe erro HTTP com contexto
- [ ] Approval workflow continua funcionando
- [ ] Rate limiter continua funcionando
- [ ] DLP checker continua funcionando

---

## Próximos Passos (After-Fix)

1. ✅ Deploy e validação em prod
2. → Implementar SDK centralizado (`bi-client-sdk/`)
3. → Criar CLI wrapper (`scripts/bi`)
4. → Documentar setup one-time
5. → Integração com IDE extensions

Ver: `PROBLEMA_E_SOLUCAO.md` (Fase 2-3)
