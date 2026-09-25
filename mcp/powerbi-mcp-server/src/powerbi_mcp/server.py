"""Power BI MCP Server — main entrypoint.

"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastmcp import FastMCP
from mcp.server.fastmcp import Context

from .auth.azure_ad import AzureADAuth
from .config import Settings, get_settings
from .guardrails import (
    ApprovalService,
    AuditLogger,
    DLPChecker,
    Permission,
    RateLimiter,
    UserContext,
    check_permission,
    check_workspace_access,
    extract_user_context,
)
from .validation import DAXValidator, ValidationResult
from .prompt_validation import validated_prompt

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()


# ============ Global state (initialized in lifespan) ============
class AppState:
    settings: Settings
    auth: AzureADAuth
    rate_limiter: RateLimiter
    audit: AuditLogger
    dlp: DLPChecker
    approval: ApprovalService
    validator: DAXValidator


state = AppState()


# ============ Lifespan (startup/shutdown) ============
@asynccontextmanager
async def lifespan(server: FastMCP):
    settings = get_settings()
    settings.require_credentials()
    state.settings = settings
    state.auth = AzureADAuth(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.pbi_sp_client_id,
        client_secret=settings.pbi_sp_client_secret,
        scope=settings.pbi_scope,
    )
    state.rate_limiter = RateLimiter(settings.redis_url)
    state.audit = AuditLogger(retention_days=settings.audit_log_retention_days)
    state.dlp = DLPChecker(
        enabled=settings.dlp_enabled,
        bypass_roles=settings.dlp_bypass_roles,
    )
    state.approval = ApprovalService(
        redis_url=settings.redis_url,
        default_ttl_minutes=settings.approval_token_ttl_minutes,
    )
    state.validator = DAXValidator()

    logger.info(
        "mcp_server_started",
        env=settings.environment,
        version=settings.server_version,
    )
    try:
        yield
    finally:
        await state.rate_limiter.close()
        await state.approval.close()
        logger.info("mcp_server_stopped")


# ============ FastMCP server ============
mcp = FastMCP(
    "powerbi-mcp",
    instructions=(
        "MCP server for Power BI. Provides tools to explore semantic models, "
        "query DAX, validate measures, create PRs, and deploy with approval. "
        "All actions are governed by RBAC, rate limits, DLP, and audit logging."
    ),
    lifespan=lifespan,
)


# ============ Helper: get user context from MCP request ============
async def get_user(request_id: str = "default") -> UserContext:
    """Extract user context from request headers.

    In production, this reads the Authorization header (user JWT) and combines
    it with the SP token used to call Power BI.
    """
    # In a real FastMCP request, the context would have the request
    # This is a stub that should be replaced with actual header parsing
    sp_token = await state.auth.get_token()
    return UserContext(
        user_id=os.environ.get("MCP_USER_ID", "ai-agent"),
        email=os.environ.get("MCP_USER_EMAIL", "ai@empresa.com"),
        roles=os.environ.get("MCP_USER_ROLES", "BI-AI-Developer").split(","),
        sp_token=sp_token,
    )


async def instrumented_tool(
    name: str,
    risk_level: str,
    func,
    required_permission: Permission | None = None,
    required_workspace_id: str | None = None,
    *args,
    **kwargs,
):
    """Wrap a tool with guardrails: rate limit + audit + RBAC.

    When *required_permission* is provided the RBAC check is performed once
    here, so individual tools no longer need to call ``check_permission()``
    themselves.  The same applies to *required_workspace_id* which triggers
    ``check_workspace_access()``.
    """
    user = await get_user()
    start = time.time()

    # Check if user is paused
    if await state.rate_limiter.is_paused(user.user_id):
        state.audit.log(name, user, risk_level=risk_level, outcome="denied")
        return {"error": "User is temporarily paused. Contact admin."}

    # Rate limit
    try:
        await state.rate_limiter.check(user.user_id, name)
    except Exception as e:
        state.audit.log(name, user, risk_level=risk_level, outcome="denied")
        raise

    # RBAC: permission check (centralized)
    if required_permission is not None:
        check_permission(user, required_permission)

    # RBAC: workspace access check (centralized)
    if required_workspace_id is not None:
        check_workspace_access(user, required_workspace_id)

    # Execute
    try:
        result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        duration = (time.time() - start) * 1000
        state.audit.log(
            name,
            user,
            risk_level=risk_level,
            outcome="success",
            duration_ms=duration,
        )
        return result
    except Exception as e:
        duration = (time.time() - start) * 1000
        state.audit.log(
            name,
            user,
            risk_level=risk_level,
            outcome="error",
            duration_ms=duration,
        )
        raise


# ============ TOOLS · SAFE (read-only) ============


@mcp.tool(tags={"risk:safe"})
async def pbi_list_datasets(workspace_id: str) -> dict[str, Any]:
    """List datasets in a Power BI workspace. Read-only.

    Args:
        workspace_id: The Power BI workspace ID

    Returns:
        List of datasets with metadata
    """
    async def _execute():
        import httpx

        token = await state.auth.get_token()
        url = f"{state.settings.pbi_api_base}/v1.0/myorg/groups/{workspace_id}/datasets"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return {"datasets": data.get("value", []), "count": len(data.get("value", []))}

    return await instrumented_tool(
        "pbi_list_datasets", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def pbi_get_model_schema(
    workspace_id: str,
    dataset_id: str,
    include_measures: bool = True,
) -> dict[str, Any]:
    """Get semantic model schema (tables, columns, measures).

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        include_measures: Include measures in the response

    Returns:
        Model schema with tables, columns, and optionally measures
    """
    async def _execute():
        # In production, use XMLA endpoint or REST API
        # Placeholder: return structure hint
        return {
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "tables": [],
            "measures": [] if include_measures else None,
            "note": "Connect XMLA endpoint to populate. See docs/ai-architecture/mcp-server.md",
        }

    return await instrumented_tool(
        "pbi_get_model_schema", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def pbi_query_dax(
    workspace_id: str,
    dataset_id: str,
    dax_query: str,
    max_rows: int = 10_000,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Execute a DAX query (SELECT only). Read-only.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        dax_query: DAX query (must be SELECT/EVALUATE only)
        max_rows: Maximum rows to return
        timeout_seconds: Query timeout

    Returns:
        Query result with rows and metadata
    """
    from .validation import is_select_only_dax

    async def _execute():
        user = await get_user()

        # DLP check on query
        state.dlp.check_input(dax_query, user.roles, context="dax_query")

        # Reject non-SELECT queries
        if not is_select_only_dax(dax_query):
            return {
                "error": "Only SELECT (EVALUATE) queries are allowed",
                "hint": "Use pbi_propose_measure_update for writes",
            }

        # In production: execute via XMLA
        # Placeholder response
        return {
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "query_hash": hash(dax_query),
            "rows": [],
            "row_count": 0,
            "duration_ms": 0,
            "note": "Connect XMLA endpoint to execute. DLP applied.",
        }

    return await instrumented_tool(
        "pbi_query_dax", "safe", _execute,
        required_permission=Permission.READ_DATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def pbi_format_dax(dax_code: str) -> dict[str, Any]:
    """Format DAX code following the project conventions.

    Args:
        dax_code: DAX code to format

    Returns:
        Formatted DAX code
    """
    async def _execute():
        # Simple formatter (in production: use dax-formatter service or library)
        formatted = dax_code.strip()
        return {
            "original": dax_code,
            "formatted": formatted,
            "note": "Use dax-formatter library or sqlbi.com for production formatting",
        }

    return await instrumented_tool(
        "pbi_format_dax", "safe", _execute,
        required_permission=Permission.READ_METADATA,
    )


@mcp.tool(tags={"risk:safe"})
async def pbi_search_dictionary(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search the data dictionary and ADRs semantically.

    Args:
        query: Natural language query
        top_k: Number of results to return

    Returns:
        Top-K relevant entries
    """
    async def _execute():
        # In production: query Azure AI Search index
        if not state.settings.ai_search_endpoint:
            return {
                "results": [],
                "note": "Azure AI Search not configured. Set ai_search_endpoint in config.",
            }

        return {"results": [], "query": query, "top_k": top_k}

    return await instrumented_tool(
        "pbi_search_dictionary", "safe", _execute,
        required_permission=Permission.READ_METADATA,
    )


# ============ TOOLS · MODERATE ============


@mcp.tool(tags={"risk:moderate"})
async def pbi_validate_dax_syntax(
    dax_code: str,
    measure_name: str | None = None,
) -> dict[str, Any]:
    """Validate DAX syntax and run a 6-dimension validation.

    Args:
        dax_code: DAX code to validate
        measure_name: Optional name for naming convention check

    Returns:
        ValidationResult as dict (is_valid, checks, errors, warnings, cost)
    """
    async def _execute():
        result = await state.validator.validate(
            dax_code, syntax_check=True, semantic_check=False, measure_name=measure_name
        )

        return {
            "is_valid": result.is_valid,
            "score": result.score,
            "checks": {k.value: v for k, v in result.checks.items()},
            "errors": result.errors,
            "warnings": result.warnings,
            "suggestions": result.suggestions,
            "estimated_cost_ms": result.estimated_cost_ms,
            "semantic_verified": result.semantic_verified,
            "measure_name": result.measure_name,
            "markdown_report": result.to_markdown(),
        }

    return await instrumented_tool(
        "pbi_validate_dax_syntax", "moderate", _execute,
        required_permission=Permission.VALIDATE_DAX,
    )


@mcp.tool(tags={"risk:moderate"})
async def pbi_suggest_measure(
    description: str,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Suggest a DAX measure for a business rule.

    Args:
        description: Business rule description in natural language
        table_name: Target table for the measure

    Returns:
        Suggested DAX code with validation report
    """
    async def _execute():
        # In production: call LLM with RAG context + measure templates
        # Placeholder: returns a structured response showing the contract
        return {
            "description": description,
            "table_name": table_name,
            "suggested_measure": {
                "name": f"{table_name or 'Vendas'}.Suggested Measure",
                "expression": "/* AI-generated DAX would go here */\n0",
                "format_string": "#,##0.00",
                "folder": table_name or "Vendas",
            },
            "note": "Integrate with LLM provider (OpenAI / Anthropic) in production",
        }

    return await instrumented_tool(
        "pbi_suggest_measure", "moderate", _execute,
        required_permission=Permission.VALIDATE_DAX,
    )


# ============ TOOLS · DANGEROUS (writes metadata via PR) ============


@mcp.tool(tags={"risk:dangerous"})
async def pbi_propose_measure_update(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    measure_name: str,
    dax_expression: str,
    format_string: str = "#,##0.00",
    folder: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Propose a new measure by creating a branch + PR (does NOT apply directly).

    Args:
        workspace_id: Target workspace
        dataset_id: Target dataset
        table_name: Table to attach the measure to
        measure_name: Name of the new measure
        dax_expression: DAX code
        format_string: Number format
        folder: Display folder
        description: Description text

    Returns:
        PR proposal with URL and validation report
    """
    async def _execute():
        # 1. Validate the DAX first
        validation = await state.validator.validate(
            dax_expression, measure_name=measure_name
        )
        if not validation.is_valid:
            return {
                "error": "DAX validation failed",
                "validation": {
                    "errors": validation.errors,
                    "checks": {k.value: v for k, v in validation.checks.items()},
                },
            }

        # 2. Generate TMDL content
        tmdl_content = _generate_measure_tmdl(
            measure_name=measure_name,
            expression=dax_expression,
            format_string=format_string,
            folder=folder,
            description=description,
        )

        # 3. In production: create branch, commit, push, open PR
        # Placeholder returns the expected structure
        return {
            "status": "would_create_pr",
            "validation_passed": True,
            "tmdl_preview": tmdl_content,
            "pr": {
                "branch": f"ai/measure-{_slugify(measure_name)}-{_short_id()}",
                "title": f"feat({table_name}): {measure_name}",
                "body": _generate_pr_body(measure_name, validation),
                "labels": ["ai-generated", "needs-review"],
            },
            "note": "Integrate with GitHub API in production to actually create the PR",
        }

    return await instrumented_tool(
        "pbi_propose_measure_update", "dangerous", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


# ============ TOOLS · CRITICAL (require approval token) ============


@mcp.tool(tags={"risk:critical"})
async def pbi_apply_approved_change(
    approval_token: str,
    pr_number: int,
    target_environment: str,
) -> dict[str, Any]:
    """Apply an approved change to the target environment.

    REQUIRES an approval token issued by a human. For prod, requires 2 approvers.

    Args:
        approval_token: Token issued via CLI or Teams bot
        pr_number: PR number to deploy
        target_environment: dev | test | prod

    Returns:
        Deployment result
    """
    from .guardrails import ApprovalError

    async def _execute():
        user = await get_user()

        required_perm = {
            "dev": Permission.DEPLOY_DEV,
            "test": Permission.DEPLOY_TEST,
            "prod": Permission.DEPLOY_PROD,
        }.get(target_environment)

        if not required_perm:
            return {"error": f"Invalid environment: {target_environment}"}

        check_permission(user, required_perm)

        # Resolve o ambiente lógico (dev/test/prod) para o workspace_id real
        # antes de checar o allowlist — passar "prod" direto nunca casaria com
        # os padrões `bi-*`.
        workspace_id = {
            "dev": state.settings.workspace_dev_id,
            "test": state.settings.workspace_test_id,
            "prod": state.settings.workspace_prod_id,
        }.get(target_environment, "")
        if workspace_id:
            check_workspace_access(user, workspace_id)

        # Validate approval token
        try:
            approval = await state.approval.validate(approval_token, user)
        except ApprovalError as e:
            return {"error": f"Approval validation failed: {e}"}

        if not approval.action.endswith(f"_{target_environment}"):
            return {
                "error": f"Token action '{approval.action}' doesn't match target '{target_environment}'"
            }

        # In production: trigger deployment pipeline
        return {
            "status": "deploying",
            "pr_number": pr_number,
            "target": target_environment,
            "approvers": approval.approvers,
            "approval_action": approval.action,
            "note": "Trigger deployment pipeline in production",
        }

    return await instrumented_tool("pbi_apply_approved_change", "critical", _execute)


@mcp.tool(tags={"risk:critical"})
async def pbi_request_approval(
    action: str,
    target: str,
    reason: str,
) -> dict[str, Any]:
    """Request an approval token for a critical action.

    This is the first step in a critical action — it issues a token that
    must be approved by a human (via CLI or Teams) before the action
    can be executed.

    Args:
        action: Action to approve (deploy_test, deploy_prod, etc)
        target: Target of the action (PR number, resource name, etc)
        reason: Justification for the action

    Returns:
        Token info and instructions for approval
    """
    async def _execute():
        user = await get_user()

        required_approvers = 2 if "prod" in action and state.settings.require_two_approvers_for_prod else 1

        token = await state.approval.issue_token(
            user=user,
            action=action,
            target=target,
            required_approvers=required_approvers,
            metadata={"reason": reason, "requested_by": user.email},
        )

        return {
            "token": token.token,
            "action": action,
            "target": target,
            "required_approvers": required_approvers,
            "expires_at": token.expires_at,
            "approval_instructions": [
                f"Approve via CLI: powerbi-mcp-admin token approve --token {token.token}",
                f"Or via Teams: post /ai-approve {action} {target}",
            ],
        }

    return await instrumented_tool("pbi_request_approval", "critical", _execute)


# ============ RESOURCES ============


@mcp.resource("powerbi://workspaces")
async def list_workspaces() -> str:
    """List all configured Power BI workspaces."""
    s = state.settings
    return f"""Workspaces configured:
- Dev:       {s.workspace_dev_id}
- Test:      {s.workspace_test_id}
- Prod:      {s.workspace_prod_id}
- Playground: {s.workspace_playground_id}
"""


@mcp.resource("powerbi://overview/{workspace_id}/{dataset_id}")
async def get_overview(workspace_id: str, dataset_id: str) -> str:
    """Get a high-level overview of a dataset."""
    user = await get_user()
    check_permission(user, Permission.READ_METADATA)
    return f"""Dataset Overview:
- Workspace: {workspace_id}
- Dataset: {dataset_id}
- Use pbi_get_model_schema for full schema
"""


# ============ PROMPTS ============


@mcp.prompt()
@validated_prompt
async def review_measure(pr_number: int) -> str:
    """Prompt to review a PR with a measure change.

    Args:
        pr_number: Pull request number (int). MUST be numeric; shell placeholders like '$1' are invalid.
    """
    return f"""Please review PR #{pr_number} that proposes a new measure.

Steps:
1. Read the changed .tmdl files
2. Verify naming follows convention (Domain.Name [format])
3. Check DAX syntax and logic
4. Run smoke tests
5. Approve or request changes

Use pbi_get_model_schema to understand the existing model context.
"""


@mcp.prompt()
@validated_prompt
async def explain_measure(measure_name: str) -> str:
    """Prompt to explain what a measure does.

    Args:
        measure_name: Name of the measure (str). Must be non-empty.
    """
    return f"""Explain the measure '{measure_name}' in plain language:

1. Use pbi_get_model_schema to find the measure
2. Break down the DAX expression step by step
3. Explain what business question it answers
4. Show an example of when it would return a non-zero value
"""


# ============ Helpers ============


def _generate_measure_tmdl(
    measure_name: str,
    expression: str,
    format_string: str = "#,##0.00",
    folder: str | None = None,
    description: str | None = None,
) -> str:
    """Generate TMDL content for a measure."""
    folder_line = f"        displayFolder: {folder}\n" if folder else ""
    desc_line = f"        description: {description}\n" if description else ""
    return f"""measure '{measure_name}'
{desc_line}{folder_line}        formatString: {format_string}
        lineageTag: ai-{_short_id()}

        annotation SummarizationSetBy = Automatic

        expression = {expression}
"""


def _generate_pr_body(measure_name: str, validation: ValidationResult) -> str:
    """Generate PR body with validation report."""
    return f"""## 🤖 AI-Generated Measure

**Measure:** `{measure_name}`

{validation.to_markdown()}

### Reviewer Checklist
- [ ] Naming convention followed
- [ ] DAX logic correct
- [ ] Performance acceptable
- [ ] No RLS leaks
- [ ] Smoke tests added
"""


def _slugify(text: str) -> str:
    """Convert text to git-branch-safe slug."""
    import re

    s = text.lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    return s.strip("-")[:40]


def _short_id() -> str:
    """Generate a short ID for branches/tags."""
    import secrets

    return secrets.token_hex(3)


# ============ Main ============

from . import server_tools  # noqa: E402, F401
from . import tmdl_tools  # noqa: E402, F401


def main():
    """Run the MCP server."""
    import os
    import sys

    transport = "stdio"  # default for local dev
    if "--http" in sys.argv:
        transport = "http"
    elif "--sse" in sys.argv:
        transport = "sse"

    # Container/Portainer: MCP_HOST=0.0.0.0 para expor fora do container.
    # Default preserva comportamento local (127.0.0.1).
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))
    if transport in ("http", "sse"):
        mcp.run(transport=transport, host=host, port=port)
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
