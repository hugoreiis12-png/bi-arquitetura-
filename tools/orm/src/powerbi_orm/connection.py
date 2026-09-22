"""Connection management for Power BI (REST API + XMLA endpoint)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from .exceptions import ConnectionError

logger = structlog.get_logger()


@dataclass
class AuthConfig:
    """Authentication configuration for Power BI."""

    tenant_id: str
    client_id: str
    client_secret: str
    scope: str = "https://analysis.windows.net/powerbi/api/.default"
    authority: str = "https://login.microsoftonline.com"


def resolve_dataset_for_branch(branch: str, base: str = "Vendas") -> str:
    """Branch -> dataset (divergencia so no commit). Espelha Settings.dataset_for_branch.

    main -> Vendas | develop -> Vendas_Dev | test/release/* -> Vendas_Test
    | demais -> Vendas_preview_<slug>.
    """
    import re

    b = (branch or "").strip()
    if b == "main":
        return base
    if b == "develop":
        return f"{base}_Dev"
    if b == "test" or b.startswith("release/"):
        return f"{base}_Test"
    slug = re.sub(r"[^a-z0-9]+", "_", b.lower()).strip("_")[:20].strip("_")
    return f"{base}_preview_{slug}" if slug else f"{base}_preview"


@dataclass
class Connection:
    """A connection to Power BI Service (REST + XMLA).

    workspace_id e unico e dinamico (projeto conectado). O dataset diverge
    so no commit, via sufixo por branch (ver resolve_dataset_for_branch).
    """

    workspace_id: str
    auth: AuthConfig
    api_base: str = "https://api.powerbi.com"
    timeout: int = 30
    dataset_name: str = "Vendas"
    _token: str = field(default="", init=False, repr=False)
    _token_expires_at: float = field(default=0.0, init=False, repr=False)

    def _ensure_token(self) -> str:
        """Ensure a valid OAuth2 token is available."""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        import msal

        app = msal.ConfidentialClientApplication(
            client_id=self.auth.client_id,
            client_credential=self.auth.client_secret,
            authority=f"{self.auth.authority}/{self.auth.tenant_id}",
        )

        result = app.acquire_token_for_client(scopes=[self.auth.scope])
        if "access_token" not in result:
            error = result.get("error", "unknown")
            description = result.get("error_description", "")
            raise ConnectionError(f"Failed to acquire token: {error} - {description}")

        self._token = result["access_token"]
        self._token_expires_at = time.time() + int(result.get("expires_in", 3600))
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Content-Type": "application/json",
        }

    async def rest_get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        """Make an authenticated GET request to Power BI REST API."""
        url = f"{self.api_base}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            return resp.json()

    async def rest_post(self, path: str, body: dict | None = None) -> dict[str, Any]:
        """Make an authenticated POST request."""
        url = f"{self.api_base}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=body or {})
            resp.raise_for_status()
            return resp.json() if resp.content else {}

    async def list_datasets(self) -> list[dict[str, Any]]:
        """List all datasets in the workspace."""
        result = await self.rest_get(f"/v1.0/myorg/groups/{self.workspace_id}/datasets")
        return result.get("value", [])

    async def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        """Get a specific dataset."""
        return await self.rest_get(
            f"/v1.0/myorg/groups/{self.workspace_id}/datasets/{dataset_id}"
        )

    @property
    def xmla_endpoint(self) -> str:
        """Return the XMLA endpoint URL for this workspace."""
        return (
            f"powerbi://api.powerbi.com/v1.0/myorg/"
            f"{self.workspace_id}"
        )

    def xmla_connection_string(self) -> str:
        """Build the ADOMD connection string for XMLA queries."""
        return (
            f"Provider=MSOLAP;"
            f"Data Source={self.xmla_endpoint};"
            f"Initial Catalog={self.dataset_name};"
            f"User ID={self.auth.client_id};"
            f"Password={self.auth.client_secret};"
            f"Persist Security Info=True;"
        )
