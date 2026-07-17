"""Custom exceptions for powerbi-orm."""


class ORMError(Exception):
    """Base exception for all ORM errors."""


class ConnectionError(ORMError):
    """Failed to connect to Power BI."""


class ModelNotFoundError(ORMError):
    """The specified model/workspace/dataset was not found."""


class ValidationError(ORMError):
    """A model object failed validation."""


class PermissionError(ORMError):
    """User lacks permission for the operation."""
