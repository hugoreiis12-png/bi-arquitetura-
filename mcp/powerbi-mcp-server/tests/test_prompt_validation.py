"""Testes para prompt_validation.py — validação de argumentos de prompts."""

import pytest
from powerbi_mcp.prompt_validation import (
    validate_prompt_arg,
    validate_prompt_args,
    coerce_prompt_arg,
    PromptValidationError,
    validated_prompt,
)


class TestValidatePromptArg:
    """Testes para validação de argumentos individuais."""

    def test_int_valid_number(self):
        """Int válido: número inteiro."""
        valid, error = validate_prompt_arg("pr_number", 42, "int")
        assert valid is True
        assert error is None

    def test_int_string_numeric(self):
        """Int com string numérica: deve aceitar para coerção."""
        valid, error = validate_prompt_arg("pr_number", "42", "int")
        assert valid is True
        assert error is None

    def test_int_shell_placeholder_dollar(self):
        """Int com shell placeholder $1: deve rejeitar."""
        valid, error = validate_prompt_arg("pr_number", "$1", "int")
        assert valid is False
        assert "placeholder shell" in error
        assert "$1" in error

    def test_int_shell_placeholder_template(self):
        """Int com template {{...}}: deve rejeitar."""
        valid, error = validate_prompt_arg("pr_number", "{{param}}", "int")
        assert valid is False
        assert "template" in error

    def test_int_float(self):
        """Int com float 3.14: deve rejeitar."""
        valid, error = validate_prompt_arg("pr_number", 3.14, "int")
        assert valid is False
        assert "float" in error

    def test_int_string_non_numeric(self):
        """Int com string não-numérica: deve rejeitar."""
        valid, error = validate_prompt_arg("pr_number", "abc", "int")
        assert valid is False
        assert "não-numérica" in error

    def test_string_valid(self):
        """String válida."""
        valid, error = validate_prompt_arg("measure_name", "Sales Amount", "str")
        assert valid is True
        assert error is None

    def test_string_number(self):
        """String com número: válido."""
        valid, error = validate_prompt_arg("measure_name", "123", "str")
        assert valid is True

    def test_float_valid(self):
        """Float válido."""
        valid, error = validate_prompt_arg("ratio", 3.14, "float")
        assert valid is True

    def test_float_int(self):
        """Float com int: aceita (int é válido para float)."""
        valid, error = validate_prompt_arg("ratio", 42, "float")
        assert valid is True

    def test_float_string_numeric(self):
        """Float com string numérica."""
        valid, error = validate_prompt_arg("ratio", "3.14", "float")
        assert valid is True

    def test_bool_valid(self):
        """Bool válido."""
        valid, error = validate_prompt_arg("flag", True, "bool")
        assert valid is True

    def test_bool_string_true(self):
        """Bool com string 'true'."""
        valid, error = validate_prompt_arg("flag", "true", "bool")
        assert valid is True

    def test_bool_string_1(self):
        """Bool com string '1'."""
        valid, error = validate_prompt_arg("flag", "1", "bool")
        assert valid is True

    def test_bool_invalid_string(self):
        """Bool com string inválida."""
        valid, error = validate_prompt_arg("flag", "maybe", "bool")
        assert valid is False


class TestValidatePromptArgs:
    """Testes para validação de múltiplos argumentos."""

    def test_all_valid(self):
        """Todos os argumentos válidos."""
        valid, errors = validate_prompt_args("review_measure", {"pr_number": 42})
        assert valid is True
        assert errors == []

    def test_missing_required(self):
        """Falta parâmetro obrigatório."""
        valid, errors = validate_prompt_args("review_measure", {})
        assert valid is False
        assert any("required" in e or "obrigatório" in e for e in errors)

    def test_shell_placeholder_detected(self):
        """Shell placeholder $1 detectado."""
        valid, errors = validate_prompt_args("review_measure", {"pr_number": "$1"})
        assert valid is False
        assert any("placeholder shell" in e for e in errors)

    def test_string_numeric_coercible(self):
        """String numérica aceitável para coerção."""
        valid, errors = validate_prompt_args("review_measure", {"pr_number": "42"})
        assert valid is True
        assert errors == []

    def test_multiple_errors(self):
        """Múltiplos erros em um prompt."""
        # Se houvesse múltiplos parâmetros inválidos
        valid, errors = validate_prompt_args("review_measure", {})
        assert valid is False


class TestCoercePromptArg:
    """Testes para coerção de tipos."""

    def test_coerce_string_to_int(self):
        """Coerce string numérica para int."""
        result = coerce_prompt_arg("42", "int")
        assert result == 42
        assert isinstance(result, int)

    def test_coerce_string_to_float(self):
        """Coerce string para float."""
        result = coerce_prompt_arg("3.14", "float")
        assert result == 3.14
        assert isinstance(result, float)

    def test_coerce_string_to_bool_true(self):
        """Coerce string 'true' para bool."""
        result = coerce_prompt_arg("true", "bool")
        assert result is True

    def test_coerce_string_to_bool_1(self):
        """Coerce string '1' para bool."""
        result = coerce_prompt_arg("1", "bool")
        assert result is True

    def test_coerce_string_to_bool_false(self):
        """Coerce string 'false' para bool."""
        result = coerce_prompt_arg("false", "bool")
        assert result is False

    def test_no_coerce_already_correct_type(self):
        """Não coerce se tipo já está correto."""
        result = coerce_prompt_arg(42, "int")
        assert result == 42

    def test_coerce_string_preserves_invalid(self):
        """Não coerce strings inválidas."""
        result = coerce_prompt_arg("$1", "int")
        assert result == "$1"  # Preserva para que validação falhe


class TestValidatedPromptDecorator:
    """Testes para o decorator @validated_prompt."""

    @pytest.mark.asyncio
    async def test_valid_args_passes(self):
        """Decorator com args válidos passa."""

        @validated_prompt
        async def dummy_prompt(pr_number: int) -> str:
            return f"PR #{pr_number}"

        # Simular chamada com argumento válido
        # (nota: decorator não está wired ao registro de schemas, apenas testa estrutura)
        result = await dummy_prompt(pr_number=42)
        assert "PR #42" in result

    @pytest.mark.asyncio
    async def test_decorator_without_schema(self):
        """Decorator sem schema registrado: passa args direto (sem coerção)."""

        @validated_prompt
        async def unmapped_prompt(value: str) -> str:
            # Sem schema, decorator passa direto
            return f"Value: {value}"

        result = await unmapped_prompt(value="test")
        assert "Value: test" in result


class TestIntegration:
    """Testes de integração end-to-end."""

    def test_realistic_flow_valid_pr(self):
        """Fluxo realista: cliente envia PR número válido."""
        # Validar
        valid, errors = validate_prompt_args("review_measure", {"pr_number": 123})
        assert valid is True

        # Coerce
        args = {"pr_number": "123"}
        coerced_args = {}
        for key, value in args.items():
            coerced_args[key] = coerce_prompt_arg(value, "int")

        assert coerced_args["pr_number"] == 123

    def test_realistic_flow_shell_placeholder(self):
        """Fluxo realista: cliente envia shell placeholder — deve falhar."""
        valid, errors = validate_prompt_args("review_measure", {"pr_number": "$1"})
        assert valid is False
        assert len(errors) > 0

        # Erro deve ser actionable
        error_msg = errors[0]
        assert "shell" in error_msg.lower() or "placeholder" in error_msg.lower()

    def test_realistic_flow_string_numeric(self):
        """Fluxo realista: cliente envia '42' (string) — aceita e coerce."""
        valid, errors = validate_prompt_args("review_measure", {"pr_number": "42"})
        assert valid is True

        coerced = coerce_prompt_arg("42", "int")
        assert coerced == 42 and isinstance(coerced, int)
