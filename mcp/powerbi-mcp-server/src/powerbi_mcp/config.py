"""Configuration for the Power BI MCP server.

Loads configuration from environment variables. Sensitive values should be
stored in Azure Key Vault and accessed via the keyvault:// scheme.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    #  Server 
    server_name: str = "powerbi-mcp"
    server_version: str = "1.0.0"
    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    #  Azure AD / Power BI 
    azure_tenant_id: str = Field(..., description="Azure AD tenant ID")
    pbi_sp_client_id: str = Field(..., description="Service Principal client ID for Power BI")
    pbi_sp_client_secret: str = Field(..., description="Service Principal secret")
    pbi_authority: str = "https://login.microsoftonline.com"
    pbi_api_base: str = "https://api.powerbi.com"
    pbi_scope: str = "https://analysis.windows.net/powerbi/api/.default"

    #  Workspaces
    workspace_dev_id: str = ""
    workspace_test_id: str = ""
    workspace_prod_id: str = ""
    workspace_playground_id: str = ""

    # Rate Limiting (Redis)
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_enabled: bool = True

    #  Approval Workflow
    approval_token_ttl_minutes: int = 15
    require_two_approvers_for_prod: bool = True

    #  Cost Limits 
    cost_limit_daily_usd: float = 50.0
    cost_limit_per_user_daily_usd: float = 10.0
    auto_pause_on_cost_limit: bool = True

    # Audit & DLP 
    audit_log_retention_days: int = 2555  # 7 anos
    dlp_enabled: bool = True
    dlp_bypass_roles: list[str] = Field(default_factory=lambda: ["BI-AI-Admin"])

    #  Knowledge (RAG)
    ai_search_endpoint: str = ""
    ai_search_api_key: str = ""
    ai_search_index_name: str = "bi-knowledge"

    #  Observability
    app_insights_connection_string: str = ""
    otel_service_name: str = "powerbi-mcp"
    otel_sampling_rate: float = 1.0

    # Sandbox 
    sandbox_max_rows: int = 10_000
    sandbox_query_timeout_seconds: int = 30

    # Paths 
    bi_template_repo: str = "https://github.com/org/bi-template"
    repos_base_path: str = "/tmp/bi-repos"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
