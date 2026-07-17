"""Data Loss Prevention (DLP) — PII detection in queries and outputs.

Detects patterns that could leak PII: CPF, CNPJ, email, phone, credit cards.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass
class PIIPattern:
    """A PII pattern to detect."""

    name: str
    pattern: re.Pattern[str]
    severity: str  # "low" | "medium" | "high"


PII_PATTERNS: list[PIIPattern] = [
    PIIPattern(
        name="CPF",
        pattern=re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
        severity="high",
    ),
    PIIPattern(
        name="CNPJ",
        pattern=re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
        severity="high",
    ),
    PIIPattern(
        name="EMAIL",
        pattern=re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b"),
        severity="medium",
    ),
    PIIPattern(
        name="PHONE_BR",
        pattern=re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}"),
        severity="medium",
    ),
    PIIPattern(
        name="CREDIT_CARD",
        pattern=re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        severity="high",
    ),
    PIIPattern(
        name="ADDRESS",
        pattern=re.compile(
            r"(?i)\b(rua|avenida|av\.?|travessa|alameda)\s+[\w\s,]+?\d+\b"
        ),
        severity="low",
    ),
]


class DLPError(Exception):
    """Raised when PII is detected."""

    def __init__(self, pii_type: str, severity: str, context: str):
        self.pii_type = pii_type
        self.severity = severity
        self.context = context
        super().__init__(f"DLP blocked: {pii_type} detected in {context}")


class DLPChecker:
    """DLP engine for input/output scanning."""

    def __init__(self, enabled: bool = True, bypass_roles: list[str] | None = None):
        self.enabled = enabled
        self.bypass_roles = set(bypass_roles or [])
        self.patterns = PII_PATTERNS

    def should_bypass(self, user_roles: list[str]) -> bool:
        """Check if user can bypass DLP based on roles."""
        return bool(set(user_roles) & self.bypass_roles)

    def check_input(self, text: str, user_roles: list[str], context: str = "input") -> None:
        """Check input for PII. Raises DLPError if found."""
        if not self.enabled or self.should_bypass(user_roles):
            return

        for pii in self.patterns:
            if pii.pattern.search(text):
                logger.warning(
                    "dlp_input_blocked",
                    pii_type=pii.name,
                    severity=pii.severity,
                    context=context,
                )
                raise DLPError(pii.name, pii.severity, context)

    def redact_output(
        self, data: dict | list | str, user_roles: list[str]
    ) -> dict | list | str:
        """Redact PII from output data."""
        if not self.enabled or self.should_bypass(user_roles):
            return data

        def _redact_value(value: Any) -> Any:
            if isinstance(value, str):
                for pii in self.patterns:
                    value = pii.pattern.sub(f"[REDACTED:{pii.name}]", value)
                return value
            if isinstance(value, dict):
                return {k: _redact_value(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_redact_value(v) for v in value]
            return value

        return _redact_value(data)
