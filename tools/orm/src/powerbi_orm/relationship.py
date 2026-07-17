"""Relationship definitions between Power BI tables."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Cardinality(str, Enum):
    """Relationship cardinality."""

    ONE_TO_ONE = "oneToOne"
    ONE_TO_MANY = "oneToMany"  # From side: 1
    MANY_TO_ONE = "manyToOne"  # From side: many
    MANY_TO_MANY = "manyToMany"


class CrossFilter(str, Enum):
    """Cross filter direction."""

    SINGLE = "singleDirection"
    BOTH = "bothDirections"
    NONE = "none"
    AUTOMATIC = "automatic"


@dataclass
class Relationship:
    """A relationship between two Power BI tables."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: Cardinality = Cardinality.MANY_TO_ONE
    cross_filter: CrossFilter = CrossFilter.SINGLE
    is_active: bool = True
    name: str = ""
    security_filter: bool = True

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.from_table}[{self.from_column}] -> {self.to_table}[{self.to_column}]"

    def to_tmdl(self) -> str:
        """Generate TMDL representation."""
        cardinality_str = self._cardinality_to_tmdl()
        cf_str = ""
        if self.cross_filter != CrossFilter.SINGLE:
            cf_str = f"        crossFilteringBehavior: {self.cross_filter.value}\n"

        active_str = "" if self.is_active else "        isActive: false\n"
        sec_str = "" if self.security_filter else "        securityFilteringBehavior: none\n"

        return f"""    relationship {self.name}
        fromColumn: {self.from_table}[{self.from_column}]
        toColumn: {self.to_table}[{self.to_column}]
{cardinality_str}{cf_str}{active_str}{sec_str}
        annotate SummarizationSetBy = Automatic
"""

    def _cardinality_to_tmdl(self) -> str:
        """Convert cardinality to TMDL format."""
        if self.cardinality == Cardinality.ONE_TO_ONE:
            return "        fromCardinality: one\n        toCardinality: one\n"
        elif self.cardinality == Cardinality.ONE_TO_MANY:
            return "        fromCardinality: one\n        toCardinality: many\n"
        elif self.cardinality == Cardinality.MANY_TO_ONE:
            return "        fromCardinality: many\n        toCardinality: one\n"
        else:
            return "        fromCardinality: many\n        toCardinality: many\n"
