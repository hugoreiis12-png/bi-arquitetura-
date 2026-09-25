"""Configuration for the Power BI MCP server.

Loads configuration from environment variables. Sensitive values should be
stored in Azure Key Vault and accessed via the keyvault:// scheme.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
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
    # Credenciais têm default vazio para que import e testes não falhem sem
    # ambiente configurado. A validação real (não-vazio) ocorre no lifespan do
    # server via require_credentials(), não no import.
    azure_tenant_id: str = Field(
        default="",
        description="Azure AD tenant ID",
        validation_alias=AliasChoices("PBI_TENANT_ID", "AZURE_TENANT_ID"),
    )
    pbi_sp_client_id: str = Field(default="", description="Service Principal client ID for Power BI")
    pbi_sp_client_secret: str = Field(default="", description="Service Principal secret")
    pbi_authority: str = "https://login.microsoftonline.com"
    pbi_api_base: str = "https://api.powerbi.com"
    pbi_scope: str = "https://analysis.windows.net/powerbi/api/.default"
    pbi_xmla_server: str = Field(
        default="",
        description="Override do endpoint XMLA (default: derivado do workspace)",
        validation_alias=AliasChoices("PBI_XMLA_SERVER", "XMLA_SERVER"),
    )

    #  Workspace unico dinamico (por projeto conectado) + dataset base.
    #  O desvio dev/test/prod acontece so no commit, via sufixo por branch.
    #  IDs legados por ambiente continuam como fallback de leitura.
    workspace_id: str = Field(
        default="", validation_alias=AliasChoices("PBI_WORKSPACE_ID", "WORKSPACE_ID")
    )
    workspace_name: str = Field(
        default="", validation_alias=AliasChoices("PBI_WORKSPACE_NAME", "WORKSPACE_NAME")
    )
    dataset_name: str = Field(
        default="Vendas", validation_alias=AliasChoices("PBI_DATASET_NAME", "DATASET_NAME")
    )
    workspace_dev_id: str = Field(
        default="", validation_alias=AliasChoices("PBI_WORKSPACE_DEV_ID", "WORKSPACE_DEV_ID")
    )
    workspace_test_id: str = Field(
        default="", validation_alias=AliasChoices("PBI_WORKSPACE_TEST_ID", "WORKSPACE_TEST_ID")
    )
    workspace_prod_id: str = Field(
        default="", validation_alias=AliasChoices("PBI_WORKSPACE_PROD_ID", "WORKSPACE_PROD_ID")
    )
    workspace_playground_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "PBI_WORKSPACE_PLAYGROUND_ID", "WORKSPACE_PLAYGROUND_ID"
        ),
    )

    def resolve_workspace_id(self) -> str:
        """Workspace unico: PBI_WORKSPACE_ID primeiro, senão legado por environment."""
        if self.workspace_id:
            return self.workspace_id
        fallback = {
            "dev": self.workspace_dev_id,
            "test": self.workspace_test_id,
            "prod": self.workspace_prod_id,
        }.get(self.environment, "")
        return fallback or self.workspace_playground_id

    def resolve_xmla_server(self, workspace_id: str = "") -> str:
        """XMLA override, ou derivado do workspace único."""
        if self.pbi_xmla_server:
            return self.pbi_xmla_server
        ws = workspace_id or self.resolve_workspace_id()
        return f"powerbi://api.powerbi.com/v1.0/myorg/{ws}"

    @staticmethod
    def dataset_for_branch(branch: str, base: str = "Vendas") -> str:
        """Mapeia branch -> nome do dataset (divergencia so no commit).

        main -> Vendas | develop -> Vendas_Dev | test/release/* -> Vendas_Test
        | demais (feat/fix/ai/*) -> Vendas_preview_<slug> (slug max 20 chars).
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

    def require_credentials(self) -> None:
        """Garante que as credenciais do Service Principal estão presentes.

        Chamado no startup do server (lifespan), não no import — assim testes e
        ferramentas offline podem instanciar Settings sem ambiente configurado.
        """
        missing = [
            name
            for name, value in (
                ("PBI_TENANT_ID", self.azure_tenant_id),
                ("PBI_SP_CLIENT_ID", self.pbi_sp_client_id),
                ("PBI_SP_CLIENT_SECRET", self.pbi_sp_client_secret),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Credenciais do Power BI ausentes: "
                + ", ".join(missing)
                + ". Configure-as no .env ou nas variáveis de ambiente."
            )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
