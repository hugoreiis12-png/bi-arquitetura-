"""Audit logging for MCP actions.

Every tool invocation is logged with user, action, args hash, and outcome.
Logs are sent to Application Insights and optionally stored in immutable
storage for compliance (LGPD/SOX).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

import structlog

from .rbac import UserContext

logger = structlog.get_logger()


class AuditLogger:
    """Structured audit logger."""

    def __init__(self, retention_days: int = 2555):
        self.retention_days = retention_days

    def _hash_value(self, value: Any) -> str:
        """SHA-256 hash of a value (for logging without exposing content)."""
        s = json.dumps(value, sort_keys=True, default=str) if not isinstance(value, str) else value
        return f"sha256:{hashlib.sha256(s.encode()).hexdigest()[:16]}"

    def log(
        self,
        action: str,
        user: UserContext,
        details: dict[str, Any] | None = None,
        risk_level: Literal["safe", "moderate", "dangerous", "critical"] = "safe",
        outcome: Literal["success", "error", "denied"] = "success",
        duration_ms: float | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        """Emit a structured audit log entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "user": {
                "id": user.user_id,
                "email": user.email,
                "roles": user.roles,
            },
            "risk_level": risk_level,
            "outcome": outcome,
            "duration_ms": duration_ms,
            "cost_usd": cost_usd,
            "details_hash": self._hash_value(details) if details else None,
            "details_summary": self._summarize(details) if details else None,
        }

        # Map risk level to log severity
        severity_map = {
            "safe": "info",
            "moderate": "info",
            "dangerous": "warning",
            "critical": "critical",
        }
        severity = severity_map.get(risk_level, "info")

        log_method = getattr(logger, severity, logger.info)
        log_method("audit", **entry)

    def _summarize(self, details: dict[str, Any]) -> dict[str, Any]:
        """Create a non-sensitive summary of details for logging."""
        summary: dict[str, Any] = {}
        for key, value in details.items():
            if key in {"dax_query", "expression", "content"}:
                # Don't log full DAX/code; use hash
                summary[f"{key}_hash"] = self._hash_value(value)
            elif isinstance(value, str) and len(value) > 200:
                summary[key] = value[:200] + "..."
            else:
                summary[key] = value
        return summary
