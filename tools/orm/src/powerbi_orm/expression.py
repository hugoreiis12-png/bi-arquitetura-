"""DAX and Power Query (M) expression wrappers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .exceptions import ValidationError


@dataclass
class DAXExpression:
    """A DAX expression with validation helpers."""

    code: str
    description: str = ""

    def __post_init__(self):
        if not self.code or not self.code.strip():
            raise ValidationError("DAX expression cannot be empty")

        # Basic balance checks
        if self.code.count("(") != self.code.count(")"):
            raise ValidationError(f"Unbalanced parentheses in: {self.code[:50]}...")
        if self.code.count("[") != self.code.count("]"):
            raise ValidationError(f"Unbalanced brackets in: {self.code[:50]}...")

    @property
    def table_references(self) -> set[str]:
        """Extract table references in single quotes."""
        return set(re.findall(r"'([^']+)'", self.code))

    @property
    def column_references(self) -> set[str]:
        """Extract column references in square brackets."""
        return set(re.findall(r"\[([^\]]+)\]", self.code))

    @property
    def all_references(self) -> set[str]:
        return self.table_references | self.column_references

    def is_select_only(self) -> bool:
        """Check if this is a SELECT (EVALUATE) only expression."""
        forbidden = ["CREATE", "ALTER", "DELETE", "DROP", "INSERT", "UPDATE", "TRUNCATE"]
        upper = self.code.upper()
        return not any(f" {kw} " in upper for kw in forbidden)


@dataclass
class MExpression:
    """A Power Query (M) expression."""

    code: str
    name: str = ""

    def __post_init__(self):
        if not self.code or not self.code.strip():
            raise ValidationError("M expression cannot be empty")
