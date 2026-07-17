"""Measure definitions for Power BI tables."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from typing import Any

from .exceptions import ValidationError
from .expression import DAXExpression


@dataclass
class Measure:
    """A DAX measure attached to a Power BI table."""

    name: str
    expression: DAXExpression
    format_string: str = "#,##0.00"
    folder: str = ""
    description: str = ""
    is_hidden: bool = False
    lineage_tag: str = field(default_factory=lambda: f"measure-{secrets.token_hex(4)}")
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate naming convention: Domain.Name [format]
        # E.g.: "Vendas.Receita Total BRL", "Vendas.Margem %"
        pattern = re.compile(r"^[A-Z][a-zA-ZçÇãÃéÉ]+\.[A-Za-zÀ-ÿ0-9 \[\]%/_-]+$")
        if not pattern.match(self.name):
            raise ValidationError(
                f"Measure name '{self.name}' doesn't follow convention "
                "(expected: 'Domain.Name [format]')"
            )

    def to_tmdl(self) -> str:
        """Generate TMDL representation."""
        lines = [
            f"    measure '{self.name}'",
        ]
        if self.description:
            lines.append(f"        description: {self._escape(self.description)}")
        if self.folder:
            lines.append(f"        displayFolder: {self.folder}")
        if self.format_string:
            lines.append(f"        formatString: {self.format_string}")
        if self.is_hidden:
            lines.append("        isHidden")
        lines.append(f"        lineageTag: {self.lineage_tag}")
        lines.append("")
        lines.append("        annotation SummarizationSetBy = Automatic")
        lines.append("")
        lines.append(f"        expression = {self.expression.code}")
        return "\n".join(lines)

    @staticmethod
    def _escape(text: str) -> str:
        """Escape a string for TMDL."""
        return text.replace('"', '\\"').replace("\n", " ")
