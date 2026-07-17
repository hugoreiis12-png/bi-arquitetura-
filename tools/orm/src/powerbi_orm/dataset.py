"""Dataset class — the root of the powerbi-orm hierarchy.

A Dataset represents a Power BI semantic model (a Tabular database) and is
the entry point for reading schema, querying DAX, and managing tables.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from .connection import AuthConfig, Connection
from .exceptions import ConnectionError, ModelNotFoundError, ValidationError
from .expression import DAXExpression
from .measure import Measure
from .query import QueryResult
from .relationship import Relationship
from .role import Role
from .table import Table

logger = structlog.get_logger()


@dataclass
class Dataset:
    """A Power BI semantic model.

    Example:
        ds = Dataset.connect(
            workspace="bi-vendas-dev",
            tenant_id=os.environ["PBI_TENANT_ID"],
            client_id=os.environ["PBI_SP_CLIENT_ID"],
            client_secret=os.environ["PBI_SP_CLIENT_SECRET"],
        )

        # Read
        for table in ds.tables:
            print(f"{table.name}: {len(table.columns)} cols")

        # Query
        result = ds.query("EVALUATE ROW(\"x\", [Vendas.Receita Total BRL])")
        print(result.scalar())

        # Write
        ds.tables["f_vendas__pedido"].add_measure(
            Measure(
                name="Vendas.Ticket Médio [R$]",
                expression=DAXExpression("DIVIDE([Receita], DISTINCTCOUNT(...))"),
            )
        )
        ds.commit(branch="feat/...", message="...")
    """

    workspace_id: str
    dataset_id: str
    name: str = ""
    auth: AuthConfig = field(default_factory=lambda: AuthConfig("", "", ""))
    connection: Connection | None = None
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)
    _pending_changes: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _schema_cache_ttl: int = 300  # 5 min
    _schema_loaded_at: float = field(default=0.0, init=False, repr=False)

    @classmethod
    def connect(
        cls,
        workspace: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        dataset_id: str | None = None,
    ) -> "Dataset":
        """Connect to a Power BI dataset.

        Args:
            workspace: Workspace ID (or name to be resolved)
            tenant_id: Azure AD tenant ID
            client_id: Service Principal client ID
            client_secret: Service Principal secret
            dataset_id: Optional specific dataset ID. If not provided, the
                       first dataset in the workspace is used.
        """
        auth = AuthConfig(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        connection = Connection(workspace_id=workspace, auth=auth)

        ds = cls(
            workspace_id=workspace,
            dataset_id=dataset_id or "",
            auth=auth,
            connection=connection,
        )

        # If no specific dataset, list and pick first
        if not ds.dataset_id:
            try:
                datasets = asyncio.run(connection.list_datasets())
                if not datasets:
                    raise ModelNotFoundError(f"No datasets found in workspace {workspace}")
                ds.dataset_id = datasets[0]["id"]
                ds.name = datasets[0]["name"]
            except Exception as e:
                logger.warning("dataset_list_failed", error=str(e))
                # Will be filled in when refresh_schema is called
        return ds

    @property
    def measure_names(self) -> set[str]:
        """All measure names in the dataset."""
        names = set()
        for table in self.tables:
            for m in table.measures:
                names.add(m.name)
        return names

    @property
    def all_symbols(self) -> set[str]:
        """All tables, columns, and measures — for scope checking."""
        symbols = set()
        for table in self.tables:
            symbols.add(table.name)
            for col in table.columns:
                symbols.add(col.name)
            for m in table.measures:
                symbols.add(m.name)
        return symbols

    def refresh_schema(self) -> None:
        """Reload the schema from the source (XMLA or local)."""
        # In production: query XMLA for TMSCHEMA_* DMVs
        # For now, this is a placeholder for the read path
        self._schema_loaded_at = time.time()
        logger.info("schema_refreshed", dataset=self.name)

    def query(self, dax: str | DAXExpression) -> QueryResult:
        """Execute a DAX query and return results.

        Args:
            dax: DAX query string or DAXExpression object

        Returns:
            QueryResult with rows, columns, row_count, duration_ms
        """
        if isinstance(dax, DAXExpression):
            dax = dax.code

        start = time.time()
        result = QueryResult()
        result.error = "Not connected to live XMLA. Configure connection for production use."

        # In production:
        # 1. Cache check (Redis, 60s TTL)
        # 2. pyadomd execute
        # 3. Parse result set
        result.duration_ms = (time.time() - start) * 1000
        return result

    async def aquery(self, dax: str | DAXExpression) -> QueryResult:
        """Async version of query()."""
        if isinstance(dax, DAXExpression):
            dax = dax.code

        start = time.time()
        result = QueryResult()
        result.error = "Not connected to live XMLA. Configure connection for production use."
        result.duration_ms = (time.time() - start) * 1000
        return result

    def dax(self, dax: str) -> QueryResult:
        """Shorthand for query()."""
        return self.query(dax)

    def add_relationship(self, rel: Relationship) -> "Dataset":
        """Add a relationship. Returns self for chaining."""
        self.relationships.append(rel)
        self._pending_changes.append({"op": "add_relationship", "data": rel})
        return self

    def add_role(self, role: Role) -> "Dataset":
        """Add an RLS role. Returns self for chaining."""
        self.roles.append(role)
        self._pending_changes.append({"op": "add_role", "data": role})
        return self

    def validate(self) -> list[str]:
        """Validate the dataset (schema, naming, RLS).

        Returns:
            List of validation warnings/errors. Empty list = OK.
        """
        issues = []

        # Check for duplicate measure names
        seen_measures = set()
        for table in self.tables:
            for m in table.measures:
                if m.name in seen_measures:
                    issues.append(f"Duplicate measure name: {m.name}")
                seen_measures.add(m.name)

        # Check relationships reference existing tables/columns
        table_names = {t.name for t in self.tables}
        for rel in self.relationships:
            if rel.from_table not in table_names:
                issues.append(f"Relationship references missing table: {rel.from_table}")
            if rel.to_table not in table_names:
                issues.append(f"Relationship references missing table: {rel.to_table}")

        return issues

    def dry_run(self) -> dict[str, Any]:
        """Simulate the pending changes without applying them.

        Returns:
            Summary of what would change.
        """
        return {
            "pending_changes": len(self._pending_changes),
            "tables": len(self.tables),
            "relationships": len(self.relationships),
            "roles": len(self.roles),
            "issues": self.validate(),
        }

    def to_tmdl(self) -> str:
        """Serialize the dataset to TMDL format."""
        output = []
        for table in self.tables:
            output.append(table.to_tmdl())
        for rel in self.relationships:
            output.append(rel.to_tmdl())
        for role in self.roles:
            output.append(role.to_tmdl())
        return "\n".join(output)

    def commit(
        self,
        branch: str,
        message: str,
        pr_title: str | None = None,
        pr_body: str | None = None,
        create_pr: bool = True,
        repo_path: str | None = None,
    ) -> dict[str, Any]:
        """Commit changes and optionally create a PR.

        Args:
            branch: Branch name to create
            message: Commit message
            pr_title: PR title (defaults to first line of message)
            pr_body: PR body
            create_pr: Whether to create a PR after commit
            repo_path: Path to git repo (defaults to current directory)

        Returns:
            Dict with branch name, commit SHA, and optionally PR URL
        """
        import subprocess

        repo = Path(repo_path) if repo_path else Path.cwd()
        result = {"branch": branch, "files_changed": []}

        # 1. Write TMDL files
        for table in self.tables:
            tmdl_path = repo / f"src/datasets/{self.name}.Dataset/definition/tables/{table.name}.tmdl"
            tmdl_path.parent.mkdir(parents=True, exist_ok=True)
            tmdl_path.write_text(table.to_tmdl())
            result["files_changed"].append(str(tmdl_path))

        # 2. Git operations
        try:
            # Create branch
            subprocess.run(
                ["git", "checkout", "-b", branch],
                cwd=repo, check=True, capture_output=True,
            )
            # Stage
            subprocess.run(
                ["git", "add", "-A"],
                cwd=repo, check=True, capture_output=True,
            )
            # Commit
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo, check=True, capture_output=True, text=True,
            )
            # Parse commit SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo, check=True, capture_output=True, text=True,
            )
            result["commit_sha"] = sha_result.stdout.strip()

            if create_pr:
                # Push and create PR via gh CLI
                subprocess.run(
                    ["git", "push", "-u", "origin", branch],
                    cwd=repo, check=True, capture_output=True,
                )
                title = pr_title or message.split("\n")[0]
                body = pr_body or f"Auto-generated by powerbi-orm\n\n{message}"
                pr_result = subprocess.run(
                    [
                        "gh", "pr", "create",
                        "--title", title,
                        "--body", body,
                        "--label", "ai-generated,needs-review",
                    ],
                    cwd=repo, check=True, capture_output=True, text=True,
                )
                result["pr_url"] = pr_result.stdout.strip()

        except subprocess.CalledProcessError as e:
            result["error"] = f"Git operation failed: {e.stderr}"
            logger.error("commit_failed", error=str(e))

        return result
