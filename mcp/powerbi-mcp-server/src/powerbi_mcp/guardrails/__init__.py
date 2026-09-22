"""Guardrails module — RBAC, rate limit, audit, DLP, approval."""

from .approval import ApprovalError, ApprovalService, ApprovalToken
from .audit import AuditLogger
from .dlp import DLPChecker, DLPError
from .rate_limit import CostLimitError, RateLimitError, RateLimiter
from .rbac import (
    Permission,
    PermissionDeniedError,
    ROLE_GROUPS,
    ROLE_PERMISSIONS,
    UserContext,
    WORKSPACE_ALLOWLIST,
    check_permission,
    check_workspace_access,
    extract_user_context,
    get_user_permissions,
    resolve_roles,
)

__all__ = [
    "ApprovalError",
    "ApprovalService",
    "ApprovalToken",
    "AuditLogger",
    "DLPChecker",
    "DLPError",
    "CostLimitError",
    "Permission",
    "PermissionDeniedError",
    "RateLimitError",
    "RateLimiter",
    "ROLE_GROUPS",
    "ROLE_PERMISSIONS",
    "UserContext",
    "WORKSPACE_ALLOWLIST",
    "check_permission",
    "check_workspace_access",
    "extract_user_context",
    "get_user_permissions",
    "resolve_roles",
]
