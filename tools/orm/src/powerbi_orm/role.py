"""RLS (Row-Level Security) role definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RoleFilter:
    """A filter expression applied to a table within a role."""

    table: str
    expression: str  # DAX expression, e.g., "[region] = USERPRINCIPALNAME()"
    description: str = ""


@dataclass
class Role:
    """An RLS role with table-level filters."""

    name: str
    table_filters: list[RoleFilter] = field(default_factory=list)
    members: list[str] = field(default_factory=list)  # Email addresses or group IDs
    description: str = ""

    def add_filter(self, table: str, expression: str, description: str = "") -> "Role":
        """Add a table filter to this role. Returns self for chaining."""
        self.table_filters.append(RoleFilter(table, expression, description))
        return self

    def to_tmdl(self) -> str:
        """Generate TMDL representation."""
        lines = [f"    role '{self.name}'"]
        if self.description:
            lines.append(f"        description: {self.description}")
        lines.append("        modelPermission: read")
        for flt in self.table_filters:
            lines.append("")
            lines.append(f"        tablePermission {flt.table}")
            lines.append(f"            filterExpression: {flt.expression}")
        return "\n".join(lines)
