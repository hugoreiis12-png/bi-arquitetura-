"""Column definitions for Power BI tables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .exceptions import ValidationError


class ColumnType(str, Enum):
    """Power BI column data types."""

    STRING = "string"
    INT64 = "int64"
    DOUBLE = "double"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATETIME = "dateTime"
    DATE = "dateTime"  # Power BI uses dateTime with date format
    TIME = "dateTime"
    BINARY = "binary"


@dataclass
class Column:
    """A column in a Power BI table."""

    name: str
    data_type: ColumnType
    description: str = ""
    is_hidden: bool = False
    format_string: str = ""
    is_key: bool = False
    source_column: str = ""

    def __post_init__(self):
        # Validate name (snake_case preferred)
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", self.name):
            raise ValidationError(
                f"Column name '{self.name}' must be alphanumeric + underscore"
            )

    def to_tmdl(self) -> str:
        """Generate TMDL representation."""
        lines = [
            f"    column {self.name}",
            f"        dataType: {self.data_type.value}",
        ]
        if self.format_string:
            lines.append(f"        formatString: {self.format_string}")
        if self.is_hidden:
            lines.append("        isHidden")
        if self.is_key:
            lines.append("        isKey")
        if self.source_column:
            lines.append(f"        sourceColumn: {self.source_column}")
        if self.description:
            lines.append(f"        description: {self.description}")
        lines.append("")
        lines.append("        annotation SummarizationSetBy = Automatic")
        return "\n".join(lines)
