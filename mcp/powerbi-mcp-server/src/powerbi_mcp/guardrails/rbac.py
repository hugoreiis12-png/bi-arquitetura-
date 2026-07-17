"""Role-Based Access Control (RBAC) for MCP tools.

Maps Azure AD groups to permissions, validates user access, and provides
workspace allowlisting per role.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class Permission(str, Enum):
    """MCP permissions, hierarchical via prefix matching."""

    # Read
    READ_METADATA = "pbi:read:metadata"
    READ_DATA = "pbi:read:data"
    READ_ALL = "pbi:read:*"

    # Write metadata
    VALIDATE_DAX = "pbi:validate:dax"
    WRITE_MODEL = "pbi:write:model"
    WRITE_ALL = "pbi:write:*"

    # Deploy
    DEPLOY_DEV = "pbi:deploy:dev"
    DEPLOY_TEST = "pbi:deploy:test"
    DEPLOY_PROD = "pbi:deploy:prod"
    DEPLOY_ALL = "pbi:deploy:*"

    # Critical operations
    REFRESH = "pbi:refresh"
    MODIFY_RLS = "pbi:modify:rls"
    DELETE = "pbi:delete"

    # Admin
    ADMIN = "*"


# Azure AD Group OID → Role mapping
ROLE_GROUPS: dict[str, str] = {
    "BI-AI-Reader": "00000000-0000-0000-0000-000000000001",
    "BI-AI-Developer": "00000000-0000-0000-0000-000000000002",
    "BI-AI-Lead": "00000000-0000-0000-0000-000000000003",
    "BI-AI-Steward": "00000000-0000-0000-0000-000000000004",
    "BI-AI-Admin": "00000000-0000-0000-0000-000000000005",
}


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "BI-AI-Reader": {
        Permission.READ_METADATA,
        Permission.READ_DATA,
    },
    "BI-AI-Developer": {
        Permission.READ_METADATA,
        Permission.READ_DATA,
        Permission.VALIDATE_DAX,
        Permission.WRITE_MODEL,
    },
    "BI-AI-Lead": {
        Permission.READ_METADATA,
        Permission.READ_DATA,
        Permission.VALIDATE_DAX,
        Permission.WRITE_MODEL,
        Permission.DEPLOY_DEV,
        Permission.DEPLOY_TEST,
    },
    "BI-AI-Steward": {
        Permission.READ_METADATA,
        Permission.READ_DATA,
        Permission.VALIDATE_DAX,
        Permission.WRITE_MODEL,
        Permission.DEPLOY_DEV,
        Permission.DEPLOY_TEST,
        Permission.DEPLOY_PROD,
        Permission.REFRESH,
        Permission.MODIFY_RLS,
    },
    "BI-AI-Admin": {Permission.ADMIN},
}


# Workspace allowlist patterns per role
WORKSPACE_ALLOWLIST: dict[str, list[str]] = {
    "BI-AI-Reader": ["bi-*-dev"],
    "BI-AI-Developer": ["bi-*-dev", "bi-*-ai-playground"],
    "BI-AI-Lead": ["bi-*-dev", "bi-*-ai-playground", "bi-*-test"],
    "BI-AI-Steward": ["bi-*"],
    "BI-AI-Admin": [".*"],
}


class PermissionDeniedError(Exception):
    """Raised when user lacks required permission."""

    def __init__(self, required: str, user_roles: list[str]):
        self.required = required
        self.user_roles = user_roles
        super().__init__(
            f"Permission denied: '{required}' required. User roles: {user_roles}"
        )


@dataclass
class UserContext:
    """Authenticated user context."""

    user_id: str
    email: str
    roles: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    sp_token: str = ""  # SP token used to call Power BI on behalf of user

    @property
    def display_name(self) -> str:
        return self.email.split("@")[0] if self.email else self.user_id


def resolve_roles(roles: list[str], groups: list[str]) -> set[str]:
    """Resolve user roles from JWT roles + Azure AD groups."""
    resolved = set(roles)

    for group_id in groups:
        for role_name, group_oid in ROLE_GROUPS.items():
            if group_id == group_oid or group_id == role_name:
                resolved.add(role_name)

    return resolved


def get_user_permissions(roles: list[str], groups: list[str]) -> set[Permission]:
    """Get all permissions granted to the user."""
    user_roles = resolve_roles(roles, groups)
    permissions: set[Permission] = set()

    for role in user_roles:
        if role in ROLE_PERMISSIONS:
            permissions |= ROLE_PERMISSIONS[role]

    return permissions


def check_permission(
    user: UserContext,
    required: str | Permission,
    audit_hook: Any | None = None,
) -> None:
    """Check if user has the required permission. Raises if not.

    Args:
        user: Authenticated user context
        required: Required permission (e.g., 'pbi:read:metadata' or Permission.READ_METADATA)
        audit_hook: Optional callback for logging denied attempts
    """
    required_str = required.value if isinstance(required, Permission) else required
    user_perms = get_user_permissions(user.roles, user.groups)

    # Wildcard admin
    if Permission.ADMIN in user_perms or "*" in user_perms:
        return

    # Exact match
    if required_str in {p.value for p in user_perms}:
        return

    # Prefix wildcard match (e.g., 'pbi:read:*' matches 'pbi:read:metadata')
    for perm in user_perms:
        perm_str = perm.value if isinstance(perm, Permission) else perm
        if perm_str.endswith(":*"):
            prefix = perm_str[:-1]
            if required_str.startswith(prefix):
                return

    # Permission denied
    logger.warning(
        "rbac_denied",
        user_id=user.user_id,
        required=required_str,
        user_roles=user.roles,
    )
    if audit_hook:
        audit_hook("rbac_denied", user, {"required": required_str})

    raise PermissionDeniedError(required_str, user.roles)


def check_workspace_access(user: UserContext, workspace_id: str) -> None:
    """Check if user can access the given workspace."""
    user_roles = resolve_roles(user.roles, user.groups)

    # Get all allowlist patterns for user's roles
    patterns: list[str] = []
    for role in user_roles:
        if role in WORKSPACE_ALLOWLIST:
            patterns.extend(WORKSPACE_ALLOWLIST[role])

    # Check if any pattern matches
    for pattern in patterns:
        if pattern == ".*" or re.match(pattern.replace("*", ".*"), workspace_id):
            return

    logger.warning(
        "workspace_access_denied",
        user_id=user.user_id,
        workspace_id=workspace_id,
    )
    raise PermissionDeniedError(f"workspace:{workspace_id}", user.roles)


def extract_user_context(claims: dict[str, Any], sp_token: str = "") -> UserContext:
    """Build UserContext from validated JWT claims."""
    return UserContext(
        user_id=claims.get("oid", claims.get("sub", "")),
        email=claims.get("preferred_username", claims.get("email", "")),
        roles=claims.get("roles", []),
        groups=claims.get("groups", []),
        sp_token=sp_token,
    )
