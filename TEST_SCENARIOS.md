# Cenários de Teste — Validação de Prompt Args

## Teste 1: Shell Placeholder Detectado (❌ Esperado Falhar)

**Request:**
```bash
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
```

**Esperado:**
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "error": "Argumentos inválidos para prompt 'review_measure': pr_number: valor '$1' parece ser placeholder shell — use valor real (ex: '42' para int, 'medida_name' para string)"
    }
  },
  "id": 1
}
```

**HTTP Status:** 400 Bad Request  
**Antes (Erro):** HTTP 200 OK (prompt silenciosamente quebrado)

---

## Teste 2: Valor Válido (✅ Esperado Sucesso)

**Request:**
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "prompts/get",
    "params": {
      "name": "review_measure",
      "arguments": {"pr_number": 123}
    },
    "id": 2
  }'
```

**Esperado:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "description": "Prompt to review a PR with a measure change.",
    "arguments": [
      {
        "name": "pr_number",
        "description": "PR number to review",
        "required": true,
        "type": "number"
      }
    ]
  },
  "id": 2
}
```

**HTTP Status:** 200 OK  
**Antes (OK):** HTTP 200 OK ✓

---

## Teste 3: String Numérica (✅ Coerce Automático)

**Request:**
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "prompts/get",
    "params": {
      "name": "review_measure",
      "arguments": {"pr_number": "456"}
    },
    "id": 3
  }'
```

**Esperado:**
- Gateway valida: "456" é string numérica — OK para coerção
- Coerce: "456" → 456 (int)
- Servidor recebe: pr_number=456 (int)
- HTTP Status: 200 OK
- Prompt renderizado corretamente

**Antes (OK):** Dependeria se FastMCP coerciona automaticamente

---

## Teste 4: Template Handlebars (❌ Esperado Falhar)

**Request:**
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "prompts/get",
    "params": {
      "name": "review_measure",
      "arguments": {"pr_number": "{{pr_id}}"}
    },
    "id": 4
  }'
```

**Esperado:**
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "error": "Argumentos inválidos para prompt 'review_measure': pr_number: valor '{{pr_id}}' parece ser template {{...}} — use valor real"
    }
  },
  "id": 4
}
```

**HTTP Status:** 400 Bad Request

---

## Teste 5: Parâmetro Faltando (❌ Esperado Falhar)

**Request:**
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "prompts/get",
    "params": {
      "name": "review_measure",
      "arguments": {}
    },
    "id": 5
  }'
```

**Esperado:**
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "error": "Argumentos inválidos para prompt 'review_measure': pr_number: parâmetro obrigatório não fornecido"
    }
  },
  "id": 5
}
```

**HTTP Status:** 400 Bad Request

---

## Teste 6: Tipo Inválido (❌ Esperado Falhar)

**Request:**
```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "prompts/get",
    "params": {
      "name": "review_measure",
      "arguments": {"pr_number": 3.14}
    },
    "id": 6
  }'
```

**Esperado:**
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "error": "Argumentos inválidos para prompt 'review_measure': pr_number: esperado int, recebido float 3.14"
    }
  },
  "id": 6
}
```

**HTTP Status:** 400 Bad Request

---

## Teste 7: Logs Estruturados

**Esperado em `docker logs bi-gateway`:**
```json
{
  "timestamp": "2026-09-25T18:15:30Z",
  "level": "error",
  "service": "bi-gateway",
  "event": "invalid_prompt_args",
  "prompt_name": "review_measure",
  "validation_errors": ["pr_number: valor '$1' parece ser placeholder shell..."]
}
```

**Esperado em `docker logs bi-mcp`:**
```json
{
  "timestamp": "2026-09-25T18:15:31Z",
  "level": "error",
  "logger": "powerbi_mcp.server",
  "event": "prompt_validation_error",
  "prompt": "review_measure",
  "error": "Argumentos inválidos para prompt 'review_measure'..."
}
```

---

## Executar Testes Localmente

```bash
# 1. Build Docker
docker build -t bi-architecture:test .

# 2. Iniciar containers (homolog)
export PBI_TENANT_ID="test-tenant"
export PBI_SP_CLIENT_ID="test-client"
export PBI_SP_CLIENT_SECRET="test-secret"
export PBI_WORKSPACE_ID="test-ws"
docker-compose up -d

# 3. Aguardar healthcheck
sleep 10
docker ps | grep bi-

# 4. Executar testes
bash test_prompts.sh

# 5. Verificar logs
docker logs bi-gateway | tail -20
docker logs bi-mcp | tail -20

# 6. Limpar
docker-compose down -v
```

---

## Resultado Esperado

| Teste | Status | Antes | Depois |
|---|---|---|---|
| Shell `$1` | ❌ FAIL | 200 OK (erro silencioso) | 400 Bad Request (erro claro) |
| Valor válido | ✅ PASS | 200 OK | 200 OK |
| String numérica | ✅ PASS | 200 OK* | 200 OK |
| Template `{{x}}` | ❌ FAIL | Desconhecido | 400 Bad Request |
| Parâmetro faltando | ❌ FAIL | Desconhecido | 400 Bad Request |
| Tipo inválido | ❌ FAIL | Desconhecido | 400 Bad Request |

*Antes: Dependeria da coerção automática de FastMCP

---

## Monitoramento Pós-Deploy (24h)

```sql
-- Query para alertas
SELECT 
  COUNT(*) as validation_errors,
  event,
  DATEADD(HOUR, -1, GETUTCDATE()) as since_last_hour
FROM logs
WHERE logger LIKE 'powerbi_mcp%'
  AND event = 'prompt_validation_error'
  AND timestamp > DATEADD(HOUR, -1, GETUTCDATE())
GROUP BY event
HAVING COUNT(*) > 5  -- Alert se > 5 erros por hora
```

**O que monitora:**
- Spike em `PromptValidationError` → Indica client bug
- Diferentes prompts com erros → Identifica qual está quebrado
- Shell placeholder detectados → Conta tentativas de exploração

---

## Checklist Final

- [ ] TS build sem erro
- [ ] 32 testes Python passam
- [ ] Docker build sucesso
- [ ] Containers iniciam e healthcheck OK
- [ ] Teste 1 (shell placeholder): erro 400
- [ ] Teste 2 (válido): 200 OK
- [ ] Teste 3 (string numérica): 200 OK
- [ ] Teste 4 (template): erro 400
- [ ] Teste 5 (faltando param): erro 400
- [ ] Teste 6 (tipo inválido): erro 400
- [ ] Logs JSON estruturados aparecem
- [ ] Approval workflow continua funcionando
- [ ] Rate limiter continua funcionando
- [ ] DLP checker continua funcionando

✅ **Pronto para Prod**