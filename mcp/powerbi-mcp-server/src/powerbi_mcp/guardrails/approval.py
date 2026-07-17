"""Approval token workflow for critical actions.

Critical actions (deploy prod, delete, modify RLS) require a single-use
approval token. Tokens are issued by humans via CLI or Teams bot, are valid
for 15 minutes, and bind to a specific action+target.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
import structlog

from .rbac import UserContext

logger = structlog.get_logger()


@dataclass
class ApprovalToken:
    """A single-use approval token."""

    token: str
    user_id: str  # Who requested the action
    action: str  # e.g., "deploy_test", "deploy_prod"
    target: str  # e.g., "PR#127", "table:cliente"
    approvers: list[str] = field(default_factory=list)
    required_approvers: int = 1
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""
    used: bool = False
    metadata: dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc).isoformat() >= self.expires_at

    def is_valid(self) -> bool:
        return not self.used and not self.is_expired()

    def has_enough_approvers(self) -> bool:
        return len(self.approvers) >= self.required_approvers


class ApprovalError(Exception):
    """Raised when approval is missing or invalid."""

    pass


class ApprovalService:
    """Manages approval tokens via Redis."""

    def __init__(self, redis_url: str, default_ttl_minutes: int = 15):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.default_ttl_minutes = default_ttl_minutes

    async def close(self):
        await self.redis.close()

    async def issue_token(
        self,
        user: UserContext,
        action: str,
        target: str,
        required_approvers: int = 1,
        ttl_minutes: int | None = None,
        metadata: dict | None = None,
    ) -> ApprovalToken:
        """Issue a new approval token (pending approval)."""
        ttl = ttl_minutes or self.default_ttl_minutes
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=ttl)
        ).isoformat()

        token = ApprovalToken(
            token=f"apv_{secrets.token_urlsafe(24)}",
            user_id=user.user_id,
            action=action,
            target=target,
            required_approvers=required_approvers,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        await self._save(token)
        logger.info(
            "approval_token_issued",
            token_prefix=token.token[:10],
            action=action,
            target=target,
            required=required_approvers,
        )
        return token

    async def approve(self, token_str: str, approver: UserContext) -> ApprovalToken:
        """Add an approver to the token."""
        token = await self._load(token_str)
        if not token:
            raise ApprovalError("Token not found")
        if not token.is_valid():
            raise ApprovalError("Token expired or used")

        if approver.user_id == token.user_id:
            raise ApprovalError("Self-approval not allowed")

        if approver.user_id not in token.approvers:
            token.approvers.append(approver.user_id)

        await self._save(token)
        logger.info(
            "approval_added",
            token_prefix=token_str[:10],
            approver=approver.user_id,
            total=len(token.approvers),
            required=token.required_approvers,
        )
        return token

    async def validate(self, token_str: str, user: UserContext) -> ApprovalToken:
        """Validate a token and consume it (single-use)."""
        token = await self._load(token_str)
        if not token:
            raise ApprovalError("Token not found")
        if token.used:
            raise ApprovalError("Token already used")
        if token.is_expired():
            raise ApprovalError("Token expired")
        if not token.has_enough_approvers():
            raise ApprovalError(
                f"Insufficient approvers: {len(token.approvers)}/{token.required_approvers}"
            )
        if user.user_id != token.user_id:
            raise ApprovalError("Token issued to a different user")

        # Single-use: mark as used
        token.used = True
        await self._save(token)
        logger.info(
            "approval_token_consumed",
            token_prefix=token_str[:10],
            action=token.action,
            target=token.target,
        )
        return token

    async def _save(self, token: ApprovalToken) -> None:
        key = f"approval:{token.token}"
        ttl_seconds = self.default_ttl_minutes * 60
        await self.redis.setex(key, ttl_seconds, json.dumps(asdict(token)))

    async def _load(self, token_str: str) -> ApprovalToken | None:
        key = f"approval:{token_str}"
        data = await self.redis.get(key)
        if not data:
            return None
        d = json.loads(data)
        return ApprovalToken(**d)
