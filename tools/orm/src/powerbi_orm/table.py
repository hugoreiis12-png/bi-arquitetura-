"""Table definitions for Power BI semantic models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .column import Column
from .exceptions import ValidationError
from .measure import Measure


@dataclass
class Table:
    """A table in a Power BI semantic model."""

    name: str
    columns: list[Column] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)
    description: str = ""
    is_hidden: bool = False
    source_expression: str = ""  # M expression (Power Query)

    def __post_init__(self):
        # Validate naming convention based on prefix
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", self.name):
            raise ValidationError(f"Table name '{self.name}' invalid")

        # Validate convention: f_, d_, _aux_
        prefixes = ("f_", "d_", "_aux_", "_util_")
        if not any(self.name.startswith(p) for p in prefixes):
            if not self.name.startswith("LocalDateTable") and not self.name.startswith("DateTableTemplate"):
                # Allow these standard table names
                if not self.name.startswith("CalculatedTable"):
                    pass  # Just warn, don't raise

    @property
    def is_fact(self) -> bool:
        return self.name.startswith("f_")

    @property
    def is_dimension(self) -> bool:
        return self.name.startswith("d_")

    @property
    def is_helper(self) -> bool:
        return self.name.startswith(("_aux_", "_util_"))

    def add_column(self, column: Column) -> "Table":
        """Add a column. Returns self for chaining."""
        self.columns.append(column)
        return self

    def add_measure(self, measure: Measure) -> "Table":
        """Add a measure. Returns self for chaining."""
        self.measures.append(measure)
        return self

    def remove_measure(self, name: str) -> "Table":
        """Remove a measure by name. Returns self for chaining."""
        self.measures = [m for m in self.measures if m.name != name]
        return self

    def get_measure(self, name: str) -> Measure | None:
        """Get a measure by name."""
        for m in self.measures:
            if m.name == name:
                return m
        return None

    def get_column(self, name: str) -> Column | None:
        """Get a column by name."""
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def to_tmdl(self) -> str:
        """Generate TMDL representation of this table."""
        lines = [f"table {self.name}"]

        if self.description:
            lines.append(f"    description: {self.description}")
        if self.is_hidden:
            lines.append("    isHidden")
        lines.append("    lineageTag: " + f"table-{self.name}")
        lines.append("")

        for col in self.columns:
            lines.append(col.to_tmdl())
            lines.append("")

        for measure in self.measures:
            lines.append(measure.to_tmdl())
            lines.append("")

        return "\n".join(lines)
