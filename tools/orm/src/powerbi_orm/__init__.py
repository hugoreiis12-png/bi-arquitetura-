"""powerbi-orm — Python ORM-style SDK for Power BI semantic models.

Provides fluent classes to read, query, and modify Tabular models via
XMLA endpoint (DirectQuery), TMDL files (local), and Power BI REST API.
"""

from .column import Column, ColumnType
from .connection import Connection
from .dataset import Dataset
from .exceptions import (
    ConnectionError,
    ModelNotFoundError,
    ORMError,
    PermissionError,
    ValidationError,
)
from .expression import DAXExpression, MExpression
from .measure import Measure
from .query import QueryResult
from .relationship import Cardinality, CrossFilter, Relationship
from .role import Role, RoleFilter
from .table import Table

__version__ = "0.4.0"

__all__ = [
    "Cardinality",
    "Column",
    "ColumnType",
    "Connection",
    "CrossFilter",
    "DAXExpression",
    "Dataset",
    "MExpression",
    "Measure",
    "ModelNotFoundError",
    "ORMError",
    "ConnectionError",
    "PermissionError",
    "QueryResult",
    "Relationship",
    "Role",
    "RoleFilter",
    "Table",
    "ValidationError",
]
