"""Query API for executing DAX queries via XMLA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueryResult:
    """Result of a DAX query execution."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    duration_ms: float = 0.0
    error: str | None = None

    @property
    def has_data(self) -> bool:
        return self.row_count > 0

    @property
    def is_empty(self) -> bool:
        return self.row_count == 0

    def scalar(self) -> Any:
        """Return the single value of a single-row, single-column result."""
        if self.row_count != 1 or len(self.columns) != 1:
            raise ValueError(
                f"scalar() requires 1x1 result, got {self.row_count}x{len(self.columns)}"
            )
        return self.rows[0][self.columns[0]]

    def first_row(self) -> dict[str, Any]:
        """Return the first row, or raise if empty."""
        if not self.rows:
            raise ValueError("No rows in result")
        return self.rows[0]
