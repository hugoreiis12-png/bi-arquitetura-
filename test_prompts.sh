#!/bin/bash

# test_prompts.sh — Testes de validação de argumentos de prompts
# Uso: ./test_prompts.sh [host:port] (default: localhost:8001)

set -e

GATEWAY_URL="${1:-http://localhost:8001/mcp}"
PASSED=0
FAILED=0

echo "=================================================="
echo "Testando Validação de Argumentos de Prompts"
echo "Gateway: $GATEWAY_URL"
echo "=================================================="
echo ""

# Função auxiliar para testar
test_prompt() {
    local test_num=$1
    local test_name=$2
    local pr_number=$3
    local expected_status=$4
    local should_contain=$5

    echo "[Teste $test_num] $test_name"
    echo "  PR Number: $pr_number"

    # Construir payload JSON
    payload=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "method": "prompts/get",
  "params": {
    "name": "review_measure",
    "arguments": {"pr_number": $pr_number}
  },
  "id": $test_num
}
EOF
)

    # Fazer request
    response=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY_URL" \
      -H "Content-Type: application/json" \
      -d "$payload")

    # Parse response (últimas 3 linhas: body + status)
    http_status=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -n -1)

    echo "  HTTP Status: $http_status (esperado: $expected_status)"

    # Verificar status
    if [ "$http_status" = "$expected_status" ]; then
        echo "  ✓ Status correto"
        PASSED=$((PASSED + 1))
    else
        echo "  ✗ Status INCORRETO"
        echo "  Response: $body"
        FAILED=$((FAILED + 1))
    fi

    # Verificar conteúdo se esperado
    if [ -n "$should_contain" ]; then
        if echo "$body" | grep -q "$should_contain"; then
            echo "  ✓ Contém: '$should_contain'"
            PASSED=$((PASSED + 1))
        else
            echo "  ✗ NÃO contém: '$should_contain'"
            echo "  Body: $body"
            FAILED=$((FAILED + 1))
        fi
    fi

    echo ""
}

# =============================================================================
# TESTES
# =============================================================================

echo "1. SHELL PLACEHOLDER \$1 (deve falhar com erro 400)"
test_prompt 1 "Shell Placeholder" '"$1"' "400" "placeholder shell"

echo "2. VALOR VÁLIDO (deve suceder com 200)"
test_prompt 2 "Valor Válido Int" "123" "200" ""

echo "3. STRING NUMÉRICA (deve suceder com 200, coerce automático)"
test_prompt 3 "String Numérica" '"456"' "200" ""

echo "4. TEMPLATE HANDLEBARS (deve falhar com erro 400)"
test_prompt 4 "Template Handlebars" '"{{pr_id}}"' "400" "template"

echo "5. PARÂMETRO FALTANDO (deve falhar com erro 400)"
# Teste especial: sem arguments
echo "[Teste 5] Parâmetro Faltando"
payload_missing=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "method": "prompts/get",
  "params": {
    "name": "review_measure",
    "arguments": {}
  },
  "id": 5
}
EOF
)

response=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY_URL" \
  -H "Content-Type: application/json" \
  -d "$payload_missing")

http_status=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

echo "  HTTP Status: $http_status (esperado: 400)"
if [ "$http_status" = "400" ]; then
    echo "  ✓ Status correto"
    PASSED=$((PASSED + 1))
else
    echo "  ✗ Status INCORRETO"
    FAILED=$((FAILED + 1))
fi

if echo "$body" | grep -q "obrigatório\|required"; then
    echo "  ✓ Contém: 'obrigatório' ou 'required'"
    PASSED=$((PASSED + 1))
else
    echo "  ✗ NÃO contém erro de parâmetro obrigatório"
    echo "  Body: $body"
    FAILED=$((FAILED + 1))
fi
echo ""

echo "6. TIPO FLOAT PARA INT (deve falhar com erro 400)"
test_prompt 6 "Float para Int" "3.14" "400" "float"

echo "7. PROMPT VÁLIDO COM OUTRO NOME (explain_measure)"
payload_explain=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "method": "prompts/get",
  "params": {
    "name": "explain_measure",
    "arguments": {"measure_name": "Sales Amount"}
  },
  "id": 7
}
EOF
)

response=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY_URL" \
  -H "Content-Type: application/json" \
  -d "$payload_explain")

http_status=$(echo "$response" | tail -1)
echo "[Teste 7] Prompt explain_measure (válido)"
echo "  HTTP Status: $http_status (esperado: 200)"
if [ "$http_status" = "200" ]; then
    echo "  ✓ Status correto"
    PASSED=$((PASSED + 1))
else
    echo "  ✗ Status INCORRETO"
    FAILED=$((FAILED + 1))
fi
echo ""

# =============================================================================
# RESUMO
# =============================================================================

echo "=================================================="
echo "RESUMO"
echo "=================================================="
echo "Testes Passaram: $PASSED"
echo "Testes Falharam: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✓ TUDO OK - Validação funcionando corretamente!"
    exit 0
else
    echo "✗ FALHAS ENCONTRADAS - Revisar logs acima"
    exit 1
fi
