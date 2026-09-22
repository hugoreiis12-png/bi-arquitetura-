"""tmdl-gateway — versionamento Power BI só-TMDL (módulo separado)."""

from .branching import resolve_dataset_for_branch
from .gateway import (
    Gateway,
    GatewayError,
    SIDECAR_PIN,
)

__all__ = [
    "Gateway",
    "GatewayError",
    "resolve_dataset_for_branch",
    "SIDECAR_PIN",
]
