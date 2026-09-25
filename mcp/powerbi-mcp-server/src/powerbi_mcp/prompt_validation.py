"""Validação de argumentos de prompts MCP.

Mitiga: cliente passando '$1' ou strings inválidas → erro claro no server
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, TypeVar, cast
from functools import wraps

F = TypeVar("F", bound=Callable[..., Any])

# Esquemas de prompts conhecidos (manutenção: adicionar novos conforme aparecerem)
PROMPT_SCHEMAS: dict[str, dict[str, str]] = {
    "review_measure": {
        "pr_number": "int",
    },
    "explain_measure": {
        "measure_name": "str",
    },
}

class PromptValidationError(ValueError):
    """Erro de validação de argumentos de prompt."""

    pass


def validate_prompt_arg(
    param_name: str,
    value: Any,
    expected_type: str,
) -> tuple[bool, str | None]:
    """Valida um argumento individual de prompt.

    Detecção especial de shell placeholders ('$1', etc.)

    Args:
        param_name: Nome do parâmetro
        value: Valor passado
        expected_type: Tipo esperado ('int', 'str', 'float', 'bool')

    Returns:
        (valid, error_message)
    """
    # Detectar shell placeholders — sempre inválido
    if isinstance(value, str):
        if re.match(r"^\$\d+$", value):
            return (
                False,
                f"{param_name}: valor '{value}' parece ser placeholder shell "
                f"— use valor real (ex: '42' para int, 'medida_name' para str)",
            )
        if re.match(r"^\{\{.*\}\}$", value):
            return (
                False,
                f"{param_name}: valor '{value}' parece ser template {{{{...}}}} "
                f"— use valor real",
            )

    # Validação de tipo
    if expected_type == "int":
        if isinstance(value, int):
            return True, None
        if isinstance(value, str):
            if re.match(r"^-?\d+$", value):
                return True, None  # Aceitar string numérica para coerção
            return False, (
                f"{param_name}: esperado int, recebido string "
                f"não-numérica '{value}'"
            )
        return False, f"{param_name}: esperado int, recebido {type(value).__name__}"

    elif expected_type == "float":
        if isinstance(value, (int, float)):
            return True, None
        if isinstance(value, str):
            if re.match(r"^-?\d+\.?\d*$", value):
                return True, None  # Aceitar string numérica
            return False, (
                f"{param_name}: esperado float, recebido string "
                f"não-numérica '{value}'"
            )
        return False, f"{param_name}: esperado float, recebido {type(value).__name__}"

    elif expected_type == "str":
        if isinstance(value, str):
            return True, None
        return False, f"{param_name}: esperado str, recebido {type(value).__name__}"

    elif expected_type == "bool":
        if isinstance(value, bool):
            return True, None
        if isinstance(value, str) and value in ("true", "false", "1", "0"):
            return True, None  # Aceitar para coerção
        return False, f"{param_name}: esperado bool, recebido {type(value).__name__}"

    return True, None


def coerce_prompt_arg(value: Any, expected_type: str) -> Any:
    """Coerce um argumento para o tipo esperado.

    Regra: string "123" → int 123 (OK); "true" → bool True (OK)
    Mantém valores já corretos.
    """
    if expected_type == "int" and isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass  # Deixa validação posterior falhar
    elif expected_type == "float" and isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    elif expected_type == "bool" and isinstance(value, str):
        return value in ("true", "1")

    return value


def validate_prompt_args(
    prompt_name: str,
    kwargs: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Valida argumentos de um prompt contra seu schema conhecido.

    Args:
        prompt_name: Nome do prompt
        kwargs: Dicionário de argumentos

    Returns:
        (valid, error_messages)
    """
    errors: list[str] = []
    schema = PROMPT_SCHEMAS.get(prompt_name, {})

    if not schema:
        # Sem schema: aceitar (prompt novo ou desconhecido)
        return True, []

    for param_name, expected_type in schema.items():
        if param_name not in kwargs:
            errors.append(f"{param_name}: parâmetro obrigatório não fornecido")
            continue

        value = kwargs[param_name]
        valid, error = validate_prompt_arg(param_name, value, expected_type)
        if not valid:
            errors.append(error)

    return len(errors) == 0, errors


def validated_prompt(fn: F) -> F:
    """Decorator que valida argumentos de um prompt FastMCP.

    Uso:
        @mcp.prompt()
        @validated_prompt
        async def review_measure(pr_number: int) -> str:
            return f"Please review PR #{pr_number}..."

    Se argumentos forem inválidos, lança PromptValidationError com detalhes.
    """

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Extrair schema do nome da função
        prompt_name = fn.__name__
        schema = PROMPT_SCHEMAS.get(prompt_name, {})

        if not schema:
            # Sem schema registrado: passar direto
            return await fn(*args, **kwargs)

        # Validar argumentos
        valid, errors = validate_prompt_args(prompt_name, kwargs)
        if not valid:
            error_msg = f"Argumentos inválidos para prompt '{prompt_name}': {'; '.join(errors)}"
            raise PromptValidationError(error_msg)

        # Coercer argumentos (string → int, etc.)
        coerced_kwargs = {}
        for param_name, expected_type in schema.items():
            if param_name in kwargs:
                coerced_kwargs[param_name] = coerce_prompt_arg(
                    kwargs[param_name], expected_type
                )
            else:
                coerced_kwargs[param_name] = kwargs.get(param_name)

        # Chamar função com argumentos coerced
        return await fn(*args, **coerced_kwargs)

    return cast(F, wrapper)