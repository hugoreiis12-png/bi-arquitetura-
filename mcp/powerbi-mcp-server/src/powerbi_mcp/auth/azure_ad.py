"""Azure AD authentication helpers."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class TokenInfo:
    """OAuth2 token with expiry tracking."""

    access_token: str
    expires_at: float
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # 60s buffer

    @property
    def expires_in_seconds(self) -> int:
        return max(0, int(self.expires_at - time.time()))


class AzureADAuth:
    """Service Principal OAuth2 client credentials flow."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        authority: str = "https://login.microsoftonline.com",
        scope: str = "https://analysis.windows.net/powerbi/api/.default",
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.authority = authority
        self.scope = scope
        self._token: TokenInfo | None = None
        self._lock = asyncio.Lock()

    async def get_token(self, force_refresh: bool = False) -> str:
        """Return a valid access token, refreshing if necessary."""
        async with self._lock:
            if self._token and not self._token.is_expired and not force_refresh:
                return self._token.access_token

            token = await self._acquire_token()
            self._token = token
            logger.info("token_acquired", expires_in=token.expires_in_seconds)
            return token.access_token

    async def _acquire_token(self) -> TokenInfo:
        url = f"{self.authority}/{self.tenant_id}/oauth2/v2.0/token"
        body = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=body)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        return TokenInfo(
            access_token=data["access_token"],
            expires_at=time.time() + int(data.get("expires_in", 3600)),
        )

    async def validate_user_jwt(self, jwt_token: str) -> dict[str, Any]:
        """Validate a user's bearer JWT and return claims.

        For dev: decode without signature verification (replace with JWKS in prod).
        Production should validate against Azure AD JWKS endpoint.
        """
        import base64
        import json

        try:
            parts = jwt_token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")

            # Decode payload (base64url)
            payload = parts[1]
            padding = 4 - len(payload) % 4
            payload += "=" * padding
            decoded = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded)

            # Basic validation
            now = time.time()
            if claims.get("exp", 0) < now:
                raise ValueError("Token expired")
            if claims.get("nbf", 0) > now:
                raise ValueError("Token not yet valid")

            return claims
        except Exception as e:
            logger.error("jwt_validation_failed", error=str(e))
            raise ValueError(f"Invalid JWT: {e}") from e
