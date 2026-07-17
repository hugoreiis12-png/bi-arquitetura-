#!/usr/bin/env python3
"""Extract a Power BI dataset to a local PBIP project structure.

This is the "baixa tudo do Power BI pra cá" command. It connects to a
Power BI workspace, extracts the dataset as PBIP files, generates extra
metadata (README, overview.yaml, data-dictionary), and creates a git commit.

Usage:
    python extract_from_powerbi.py \\
        --workspace "bi-vendas-prod" \\
        --dataset "Vendas.Dataset" \\
        --output ./src/datasets \\
        --include-reports \\
        --generate-docs \\
        --git-commit
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()


# ============ Power BI REST helpers ============


class PowerBIClient:
    """Minimal Power BI REST API client."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        import msal

        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_base = "https://api.powerbi.com"

        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )
        result = app.acquire_token_for_client(
            scopes=["https://analysis.windows.net/powerbi/api/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"Auth failed: {result.get('error_description')}")
        self._token = result["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(f"{self.api_base}{path}", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def list_datasets(self, workspace_id: str) -> list[dict]:
        result = await self.get(f"/v1.0/myorg/groups/{workspace_id}/datasets")
        return result.get("value", [])

    async def get_dataset(self, workspace_id: str, dataset_id: str) -> dict:
        return await self.get(f"/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}")

    async def get_dataset_users(self, workspace_id: str, dataset_id: str) -> list:
        result = await self.get(
            f"/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/users"
        )
        return result.get("value", [])

    async def get_refreshes(self, workspace_id: str, dataset_id: str) -> list:
        result = await self.get(
            f"/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
        )
        return result.get("value", [])


# ============ XMLA / TMDL extraction ============


def extract_with_pbi_tools(dataset_name: str, output_path: Path) -> bool:
    """Run pbi-tools extract to get TMDL files."""
    try:
        subprocess.run(
            [
                "pbi-tools",
                "extract",
                dataset_name,
                "--out",
                str(output_path),
                "--format",
                "PBIP",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except FileNotFoundError:
        logger.warning("pbi_tools_not_found", hint="Install with: dotnet tool install --global Microsoft.PowerBI.Tools")
        return False
    except subprocess.CalledProcessError as e:
        logger.error("pbi_tools_failed", stderr=e.stderr)
        return False


def extract_via_xmla(workspace_id: str, dataset_id: str, output_path: Path) -> dict[str, Any]:
    """Extract schema via XMLA endpoint using TMSCHEMA DMVs.

    Note: requires pyadomd (Windows only) and XMLA endpoint access.
    Returns metadata that can be used to generate TMDL.
    """
    # Placeholder: In production, this would use pyadomd to query:
    # - TMSCHEMA_TABLES
    # - TMSCHEMA_COLUMNS
    # - TMSCHEMA_MEASURES
    # - TMSCHEMA_RELATIONSHIPS
    # - TMSCHEMA_ROLES
    # - TMSCHEMA_DATA_SOURCES

    # For now, return a structure hint
    return {
        "tables": [],
        "relationships": [],
        "roles": [],
        "data_sources": [],
        "note": "XMLA extraction not implemented in stub. Use pbi-tools or configure pyadomd.",
    }


# ============ Documentation generators ============


def generate_readme(
    dataset_name: str,
    workspace_name: str,
    overview: dict[str, Any],
    output_path: Path,
) -> None:
    """Generate a human-readable README.md for the dataset."""
    schema = overview.get("schema", {})

    content = f"""# {dataset_name}

> Modelo semântico extraído de **{workspace_name}** em {overview.get("extracted_at", "N/A")}.

## Resumo

- **{schema.get("tables", 0)} tabelas** ({schema.get("fact_tables", 0)} fatos, {schema.get("dim_tables", 0)} dimensões)
- **{schema.get("measures", 0)} medidas**
- **{schema.get("relationships", 0)} relacionamentos**
- **{schema.get("roles", 0)} roles RLS**
- **{schema.get("data_sources", 0)} data sources**

## Estrutura

Ver [`overview.yaml`](./overview.yaml) para metadados completos em formato machine-readable.

```
{definition_str(output_path)}
```

## Edição

Abra o `.pbip` no Power BI Desktop para editar visualmente.
Ou edite os `.tmdl` diretamente no VSCode.

## Convenções aplicadas

- ✅ Tabelas: snake_case com prefixos (f_*, d_*, _aux_*)
- {schema.get("naming_warnings", 0)} medidas fora do padrão
- {schema.get("rls_warnings", 0)} roles com avisos
"""
    readme_path = output_path / "README.md"
    readme_path.write_text(content, encoding="utf-8")
    logger.info("readme_generated", path=str(readme_path))


def _definition_str(output_path: Path) -> str:
    """Generate a tree-like view of the definition folder."""
    lines = ["definition/"]
    tables_dir = output_path / "definition" / "tables"
    if tables_dir.exists():
        for f in sorted(tables_dir.glob("*.tmdl")):
            lines.append(f"  ├── {f.name}")
    roles_dir = output_path / "definition" / "roles"
    if roles_dir.exists():
        lines.append("  roles/")
        for f in sorted(roles_dir.glob("*.tmdl")):
            lines.append(f"    ├── {f.name}")
    return "\n".join(lines)


def generate_overview(
    dataset_name: str,
    workspace_id: str,
    dataset_id: str,
    schema: dict[str, Any],
    last_refresh: str | None,
    refresh_schedule: str | None,
    output_path: Path,
) -> None:
    """Generate overview.yaml with machine-readable metadata."""
    overview = {
        "dataset": {
            "id": dataset_id,
            "name": dataset_name,
            "workspace_id": workspace_id,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "last_refresh": last_refresh,
            "refresh_schedule": refresh_schedule,
        },
        "schema": schema,
        "warnings": [],
    }
    overview_path = output_path / "overview.yaml"
    overview_path.write_text(
        yaml.safe_dump(overview, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("overview_generated", path=str(overview_path))


def generate_data_dictionary(
    tables: list[dict], output_path: Path
) -> None:
    """Generate docs/data-dictionary.md with table/measure catalog."""
    lines = [f"# Dicionário de Dados — {output_path.name}", ""]
    lines.append(f"> Gerado automaticamente em {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    for table in tables:
        lines.append(f"## {table.get('name', 'Unknown')}")
        lines.append("")

        cols = table.get("columns", [])
        if cols:
            lines.append("### Colunas")
            lines.append("")
            lines.append("| Coluna | Tipo | Descrição |")
            lines.append("|---|---|---|")
            for c in cols:
                lines.append(f"| `{c.get('name')}` | {c.get('dataType')} | {c.get('description', '')} |")
            lines.append("")

        measures = table.get("measures", [])
        if measures:
            lines.append("### Medidas")
            lines.append("")
            lines.append("| Medida | Pasta | Descrição |")
            lines.append("|---|---|---|")
            for m in measures:
                lines.append(f"| `{m.get('name')}` | {m.get('folder', '')} | {m.get('description', '')} |")
            lines.append("")

    doc_path = output_path / "docs" / "data-dictionary.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("data_dictionary_generated", path=str(doc_path))


# ============ Main extraction flow ============


async def main():
    parser = argparse.ArgumentParser(
        description="Extract a Power BI dataset to local PBIP structure"
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Power BI workspace ID (or name)",
    )
    parser.add_argument(
        "--dataset",
        help="Dataset name or ID (defaults to first dataset in workspace)",
    )
    parser.add_argument(
        "--output",
        default="./src/datasets",
        help="Output base directory",
    )
    parser.add_argument(
        "--include-reports",
        action="store_true",
        help="Also extract related reports",
    )
    parser.add_argument(
        "--generate-docs",
        action="store_true",
        help="Generate README, overview.yaml, data-dictionary",
    )
    parser.add_argument(
        "--git-commit",
        action="store_true",
        help="Create initial git commit",
    )
    parser.add_argument(
        "--commit-message",
        default=None,
        help="Custom commit message (default: 'feat: extract ...')",
    )
    parser.add_argument(
        "--tenant-id",
        default=os.environ.get("PBI_TENANT_ID"),
        help="Azure AD tenant ID (or env PBI_TENANT_ID)",
    )
    parser.add_argument(
        "--client-id",
        default=os.environ.get("PBI_SP_CLIENT_ID"),
        help="Service Principal client ID (or env PBI_SP_CLIENT_ID)",
    )
    parser.add_argument(
        "--client-secret",
        default=os.environ.get("PBI_SP_CLIENT_SECRET"),
        help="Service Principal secret (or env PBI_SP_CLIENT_SECRET)",
    )

    args = parser.parse_args()

    if not all([args.tenant_id, args.client_id, args.client_secret]):
        print("❌ Missing credentials. Set PBI_TENANT_ID, PBI_SP_CLIENT_ID, PBI_SP_CLIENT_SECRET")
        sys.exit(1)

    print(f"🔌 Conectando no workspace {args.workspace}...")
    client = PowerBIClient(args.tenant_id, args.client_id, args.client_secret)

    # List datasets
    datasets = await client.list_datasets(args.workspace)
    if not datasets:
        print(f"❌ Nenhum dataset encontrado em {args.workspace}")
        sys.exit(1)

    # Pick dataset
    if args.dataset:
        target = next(
            (d for d in datasets if d["id"] == args.dataset or d["name"] == args.dataset),
            None,
        )
        if not target:
            print(f"❌ Dataset '{args.dataset}' não encontrado. Disponíveis:")
            for d in datasets:
                print(f"   - {d['name']} ({d['id']})")
            sys.exit(1)
    else:
        target = datasets[0]
        print(f"   → Usando primeiro dataset: {target['name']}")

    print(f"📊 Dataset: {target['name']} ({target['id']})")
    print(f"   ConfiguredBy: {target.get('configuredBy', 'N/A')}")
    print(f"   TargetStorageMode: {target.get('targetStorageMode', 'N/A')}")

    # Get refresh history
    refreshes = await client.get_refreshes(args.workspace, target["id"])
    last_refresh = refreshes[0]["startTime"] if refreshes else None
    if last_refresh:
        print(f"   LastRefresh: {last_refresh}")

    # Build output path
    safe_name = target["name"].replace(" ", "_").replace("/", "_")
    output_path = Path(args.output) / f"{safe_name}.Dataset"
    output_path.mkdir(parents=True, exist_ok=True)

    # Extract TMDL via pbi-tools
    print(f"📥 Extraindo TMDL para {output_path}...")
    if extract_with_pbi_tools(target["name"], output_path):
        print("   ✓ TMDL extraído com sucesso")
    else:
        print("   ⚠ pbi-tools não disponível, gerando estrutura mínima...")
        # Generate minimal structure
        (output_path / "definition").mkdir(exist_ok=True)
        (output_path / "definition" / "tables").mkdir(exist_ok=True)
        (output_path / "definition" / "roles").mkdir(exist_ok=True)

    # Get schema (placeholder)
    schema_meta = extract_via_xmla(args.workspace, target["id"], output_path)
    schema_summary = {
        "tables": len(schema_meta.get("tables", [])),
        "measures": 0,
        "relationships": len(schema_meta.get("relationships", [])),
        "roles": len(schema_meta.get("roles", [])),
        "data_sources": len(schema_meta.get("data_sources", [])),
    }

    # Generate docs
    if args.generate_docs:
        print("📝 Gerando documentação...")
        generate_overview(
            dataset_name=target["name"],
            workspace_id=args.workspace,
            dataset_id=target["id"],
            schema=schema_summary,
            last_refresh=last_refresh,
            refresh_schedule=None,
            output_path=output_path,
        )
        generate_readme(
            dataset_name=target["name"],
            workspace_name=args.workspace,
            overview={
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "schema": schema_summary,
            },
            output_path=output_path,
        )
        generate_data_dictionary(
            tables=schema_meta.get("tables", []),
            output_path=output_path,
        )

    # Git commit
    if args.git_commit:
        print("🔧 Criando commit inicial...")
        try:
            subprocess.run(
                ["git", "init", "-q"],
                cwd=output_path.parent.parent.parent,  # repo root
                check=False,
            )
            subprocess.run(
                ["git", "add", "-A"],
                cwd=output_path.parent.parent.parent,
                check=True,
            )
            msg = args.commit_message or f"feat: extract {target['name']} from Power BI"
            subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=output_path.parent.parent.parent,
                check=True,
                capture_output=True,
            )
            print(f"   ✓ Commit criado: {msg}")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠ Git commit falhou: {e}")

    print(f"\n✅ Extração concluída em {output_path}")
    print(f"   Arquivos: {sum(1 for _ in output_path.rglob('*') if _.is_file())}")
    print(f"   Próximos passos:")
    print(f"   1. Revisar overview.yaml")
    print(f"   2. Editar .tmdl files no VSCode")
    print(f"   3. Validar: pbi-tools compile {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
