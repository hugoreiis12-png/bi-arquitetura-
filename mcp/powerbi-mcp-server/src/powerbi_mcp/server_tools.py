"""ORM-backed MCP tools — 36 new tools wrapping the powerbi-orm SDK.

Grouped by domain: Dataset, Tables, Columns, Measures, Relationships,
Roles, Query, Validation, Guardrails, Approval.

Every tool follows the server.py pattern:
    @mcp.tool(tags={"risk:LEVEL"})
    async def pbi_xxx(...) -> dict[str, Any]:
        async def _execute():
            ...
        return await instrumented_tool("pbi_xxx", "LEVEL", _execute)
"""

from __future__ import annotations

from typing import Any

from .server import mcp, instrumented_tool, get_user, state
from .guardrails import (
    Permission,
    DLPError,
)

# ---------------------------------------------------------------------------
# 1. ORM Dataset  (5 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:safe"})
async def orm_connect_dataset(
    workspace_id: str,
    dataset_id: str,
    server: str | None = None,
) -> dict[str, Any]:
    """Connect to a Power BI dataset via the ORM.

    Args:
        workspace_id: Power BI workspace ID
        dataset_id: Dataset ID
        server: Optional XMLA server override

    Returns:
        Connection status and schema summary
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        xmla_server = server or state.settings.pbi_xmla_server
        ds.connect(
            server=xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )

        return {
            "status": "connected",
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "tables": ds.table_names,
        }

    return await instrumented_tool(
        "orm_connect_dataset", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_refresh_schema(workspace_id: str, dataset_id: str) -> dict[str, Any]:
    """Refresh the ORM schema cache for a connected dataset.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID

    Returns:
        Refreshed schema metadata
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        return {
            "status": "refreshed",
            "table_count": len(ds.table_names),
            "tables": ds.table_names,
        }

    return await instrumented_tool(
        "orm_refresh_schema", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_inspect_dataset(
    workspace_id: str,
    dataset_id: str,
) -> dict[str, Any]:
    """Inspect full dataset schema via the ORM (tables, columns, measures, relationships).

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID

    Returns:
        Full schema inspection
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        tables_info = []
        for t in ds.tables:
            tables_info.append({
                "name": t.name,
                "columns": [{"name": c.name, "type": c.data_type} for c in t.columns],
                "measures": [{"name": m.name} for m in t.measures],
            })

        return {
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "tables": tables_info,
            "table_count": len(ds.tables),
        }

    return await instrumented_tool(
        "orm_inspect_dataset", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_commit_dataset(
    workspace_id: str,
    dataset_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Commit pending ORM changes to the dataset.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        dry_run: If True, only validates without applying

    Returns:
        Commit result or dry-run validation
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )

        if dry_run:
            result = ds.dry_run()
            return {"dry_run": True, "changes": result}

        ds.commit()
        return {"status": "committed", "dry_run": False}

    return await instrumented_tool(
        "orm_commit_dataset", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_to_tmdl(workspace_id: str, dataset_id: str) -> dict[str, Any]:
    """Export dataset model to TMDL format via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID

    Returns:
        TMDL content for the model
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        tmdl = ds.to_tmdl()
        return {"tmdl": tmdl, "length": len(tmdl)}

    return await instrumented_tool(
        "orm_to_tmdl", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 2. ORM Tables  (3 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:moderate"})
async def orm_create_table(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    columns: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a new table via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Name of the new table
        columns: List of column definitions [{"name": "...", "type": "..."}]

    Returns:
        Table creation result
    """
    async def _execute():
        from powerbi_orm import Dataset, Table, Column

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )

        table = Table(name=table_name)
        for col_def in columns:
            table.add_column(Column(
                name=col_def["name"],
                data_type=col_def.get("type", "string"),
            ))

        ds.add_table(table)
        return {"status": "created", "table": table_name, "columns": len(columns)}

    return await instrumented_tool(
        "orm_create_table", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_alter_table(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    add_columns: list[dict[str, Any]] | None = None,
    remove_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Alter an existing table via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Table to alter
        add_columns: Columns to add [{"name": "...", "type": "..."}]
        remove_columns: Column names to remove

    Returns:
        Alter result
    """
    async def _execute():
        from powerbi_orm import Dataset, Column

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        added = []
        for col_def in (add_columns or []):
            table.add_column(Column(
                name=col_def["name"],
                data_type=col_def.get("type", "string"),
            ))
            added.append(col_def["name"])

        removed = []
        for col_name in (remove_columns or []):
            table.remove_column(col_name)
            removed.append(col_name)

        return {"table": table_name, "added": added, "removed": removed}

    return await instrumented_tool(
        "orm_alter_table", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_drop_table(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
) -> dict[str, Any]:
    """Drop a table via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Table to drop

    Returns:
        Drop result
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        ds.remove_table(table_name)
        return {"status": "dropped", "table": table_name}

    return await instrumented_tool(
        "orm_drop_table", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 3. ORM Columns  (3 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:moderate"})
async def orm_add_column(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    column_name: str,
    data_type: str = "string",
    format_string: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Add a column to an existing table via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Target table
        column_name: New column name
        data_type: Data type (string, int64, double, datetime, boolean)
        format_string: Optional format string
        description: Optional description

    Returns:
        Column creation result
    """
    async def _execute():
        from powerbi_orm import Dataset, Column

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        col = Column(
            name=column_name,
            data_type=data_type,
            format=format_string,
            description=description,
        )
        table.add_column(col)
        return {"status": "added", "table": table_name, "column": column_name}

    return await instrumented_tool(
        "orm_add_column", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_update_column(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    column_name: str,
    format_string: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Update column metadata via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Target table
        column_name: Column to update
        format_string: New format string
        description: New description

    Returns:
        Update result
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        col = table.get_column(column_name)
        if col is None:
            return {"error": f"Column '{column_name}' not found in '{table_name}'"}

        if format_string is not None:
            col.format = format_string
        if description is not None:
            col.description = description

        return {"status": "updated", "table": table_name, "column": column_name}

    return await instrumented_tool(
        "orm_update_column", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_remove_column(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    column_name: str,
) -> dict[str, Any]:
    """Remove a column via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Target table
        column_name: Column to remove

    Returns:
        Removal result
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        table.remove_column(column_name)
        return {"status": "removed", "table": table_name, "column": column_name}

    return await instrumented_tool(
        "orm_remove_column", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 4. ORM Measures  (5 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:moderate"})
async def orm_create_measure(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    measure_name: str,
    expression: str,
    format_string: str = "#,##0.00",
    description: str | None = None,
    folder: str | None = None,
) -> dict[str, Any]:
    """Create a new measure via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Target table
        measure_name: Measure name
        expression: DAX expression
        format_string: Number format
        description: Optional description
        folder: Optional display folder

    Returns:
        Measure creation result
    """
    async def _execute():
        user = await get_user()
        state.dlp.check_input(expression, user.roles, context="dax_measure")

        from powerbi_orm import Dataset, Measure

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        measure = Measure(
            name=measure_name,
            expression=expression,
            format=format_string,
            description=description,
        )
        table.add_measure(measure)
        return {"status": "created", "table": table_name, "measure": measure_name}

    return await instrumented_tool(
        "orm_create_measure", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_update_measure(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    measure_name: str,
    expression: str | None = None,
    format_string: str | None = None,
    description: str | None = None,
    folder: str | None = None,
) -> dict[str, Any]:
    """Update an existing measure via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Target table
        measure_name: Measure to update
        expression: New DAX expression
        format_string: New format string
        description: New description
        folder: New display folder

    Returns:
        Update result
    """
    async def _execute():
        user = await get_user()

        if expression is not None:
            state.dlp.check_input(expression, user.roles, context="dax_measure")

        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        measure = table.get_measure(measure_name)
        if measure is None:
            return {"error": f"Measure '{measure_name}' not found in '{table_name}'"}

        if expression is not None:
            measure.expression = expression
        if format_string is not None:
            measure.format = format_string
        if description is not None:
            measure.description = description

        return {"status": "updated", "table": table_name, "measure": measure_name}

    return await instrumented_tool(
        "orm_update_measure", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_remove_measure(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    measure_name: str,
) -> dict[str, Any]:
    """Remove a measure via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Target table
        measure_name: Measure to remove

    Returns:
        Removal result
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        table.remove_measure(measure_name)
        return {"status": "removed", "table": table_name, "measure": measure_name}

    return await instrumented_tool(
        "orm_remove_measure", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_inspect_measure(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    measure_name: str,
) -> dict[str, Any]:
    """Inspect a measure's metadata and dependencies.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Target table
        measure_name: Measure to inspect

    Returns:
        Measure details and dependencies
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        measure = table.get_measure(measure_name)
        if measure is None:
            return {"error": f"Measure '{measure_name}' not found in '{table_name}'"}

        return {
            "name": measure.name,
            "expression": measure.expression,
            "format": measure.format,
            "description": measure.description,
            "dependencies": measure.dependencies,
        }

    return await instrumented_tool(
        "orm_inspect_measure", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_list_measures(
    workspace_id: str,
    dataset_id: str,
    table_name: str | None = None,
) -> dict[str, Any]:
    """List all measures in a dataset or specific table.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Optional table filter

    Returns:
        List of measures
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        measures = []
        if table_name:
            table = ds.get_table(table_name)
            if table is None:
                return {"error": f"Table '{table_name}' not found"}
            for m in table.measures:
                measures.append({"table": table_name, "name": m.name, "format": m.format})
        else:
            for t in ds.tables:
                for m in t.measures:
                    measures.append({"table": t.name, "name": m.name, "format": m.format})

        return {"measures": measures, "count": len(measures)}

    return await instrumented_tool(
        "orm_list_measures", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 5. ORM Relationships  (3 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:moderate"})
async def orm_create_relationship(
    workspace_id: str,
    dataset_id: str,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    cardinality: str = "many_to_one",
    cross_filter: str = "one",
    is_active: bool = True,
) -> dict[str, Any]:
    """Create a relationship between two tables via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        from_table: Source table
        from_column: Source column
        to_table: Target table
        to_column: Target column
        cardinality: one_to_one, one_to_many, many_to_one, many_to_many
        cross_filter: one, many, both
        is_active: Whether the relationship is active

    Returns:
        Relationship creation result
    """
    async def _execute():
        from powerbi_orm import Dataset, Relationship

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        rel = Relationship(
            from_table=from_table,
            to_table=to_table,
            from_column=from_column,
            to_column=to_column,
            cardinality=cardinality,
            cross_filter=cross_filter,
            is_active=is_active,
        )
        ds.add_relationship(rel)
        return {
            "status": "created",
            "from": f"{from_table}[{from_column}]",
            "to": f"{to_table}[{to_column}]",
            "cardinality": cardinality,
        }

    return await instrumented_tool(
        "orm_create_relationship", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_remove_relationship(
    workspace_id: str,
    dataset_id: str,
    from_table: str,
    to_table: str,
) -> dict[str, Any]:
    """Remove a relationship between two tables via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        from_table: Source table
        to_table: Target table

    Returns:
        Removal result
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        ds.remove_relationship(from_table=from_table, to_table=to_table)
        return {
            "status": "removed",
            "from_table": from_table,
            "to_table": to_table,
        }

    return await instrumented_tool(
        "orm_remove_relationship", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_list_relationships(
    workspace_id: str,
    dataset_id: str,
) -> dict[str, Any]:
    """List all relationships in a dataset.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID

    Returns:
        List of relationships
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        rels = []
        for r in ds.relationships:
            rels.append({
                "from": f"{r.from_table}[{r.from_column}]",
                "to": f"{r.to_table}[{r.to_column}]",
                "cardinality": r.cardinality,
                "is_active": r.is_active,
            })

        return {"relationships": rels, "count": len(rels)}

    return await instrumented_tool(
        "orm_list_relationships", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 6. ORM Roles  (3 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:moderate"})
async def orm_create_role(
    workspace_id: str,
    dataset_id: str,
    role_name: str,
    table_filters: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Create a security role via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        role_name: Role name
        table_filters: Optional table filter definitions [{"table": "...", "filter": "..."}]

    Returns:
        Role creation result
    """
    async def _execute():
        from powerbi_orm import Dataset, Role

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )

        role = Role(name=role_name)
        for f in (table_filters or []):
            role.add_filter(f["table"], f["filter"])

        ds.add_role(role)
        return {"status": "created", "role": role_name, "filters": len(table_filters or [])}

    return await instrumented_tool(
        "orm_create_role", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:moderate"})
async def orm_update_role(
    workspace_id: str,
    dataset_id: str,
    role_name: str,
    add_filters: list[dict[str, str]] | None = None,
    remove_tables: list[str] | None = None,
) -> dict[str, Any]:
    """Update a security role's filters via the ORM.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        role_name: Role to update
        add_filters: Filters to add [{"table": "...", "filter": "..."}]
        remove_tables: Tables to remove filters from

    Returns:
        Update result
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        role = None
        for r in ds.roles:
            if r.name == role_name:
                role = r
                break

        if role is None:
            return {"error": f"Role '{role_name}' not found"}

        for f in (add_filters or []):
            role.add_filter(f["table"], f["filter"])

        for t in (remove_tables or []):
            role.remove_filter(t)

        return {"status": "updated", "role": role_name}

    return await instrumented_tool(
        "orm_update_role", "moderate", _execute,
        required_permission=Permission.WRITE_MODEL,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_list_roles(
    workspace_id: str,
    dataset_id: str,
) -> dict[str, Any]:
    """List all security roles in a dataset.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID

    Returns:
        List of roles with their filters
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        roles = []
        for r in ds.roles:
            roles.append({
                "name": r.name,
                "table_filters": dict(r.table_filters) if r.table_filters else {},
            })

        return {"roles": roles, "count": len(roles)}

    return await instrumented_tool(
        "orm_list_roles", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 7. ORM Query  (1 tool)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:safe"})
async def orm_execute_query(
    workspace_id: str,
    dataset_id: str,
    dax_query: str,
    max_rows: int = 10_000,
) -> dict[str, Any]:
    """Execute a DAX query via the ORM's aquery method.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        dax_query: DAX query to execute (SELECT/EVALUATE only)
        max_rows: Maximum rows to return

    Returns:
        Query results as rows
    """
    async def _execute():
        user = await get_user()

        from .validation import is_select_only_dax
        if not is_select_only_dax(dax_query):
            return {"error": "Only SELECT (EVALUATE) queries are allowed"}

        state.dlp.check_input(dax_query, user.roles, context="dax_query")

        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )

        result = await ds.aquery(dax_query)
        rows = result.data[:max_rows]
        return {
            "rows": rows,
            "row_count": len(rows),
            "columns": result.columns,
            "truncated": len(result.data) > max_rows,
        }

    return await instrumented_tool(
        "orm_execute_query", "safe", _execute,
        required_permission=Permission.READ_DATA,
        required_workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 8. Validation  (5 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:safe"})
async def orm_validate_dax_syntax(
    dax_code: str,
    measure_name: str | None = None,
) -> dict[str, Any]:
    """Validate DAX syntax using the ORM's built-in validator.

    Args:
        dax_code: DAX code to validate
        measure_name: Optional measure name for naming convention check

    Returns:
        Syntax validation result
    """
    async def _execute():
        from powerbi_orm import DAXExpression

        expr = DAXExpression(raw=dax_code)
        is_valid = expr.is_valid()
        tables = expr.extract_tables()
        measures = expr.extract_measures()

        return {
            "is_valid": is_valid,
            "tables": tables,
            "measures": measures,
            "measure_name": measure_name,
        }

    return await instrumented_tool(
        "orm_validate_dax_syntax", "safe", _execute,
        required_permission=Permission.VALIDATE_DAX,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_validate_dax_scope(
    dax_code: str,
    allowed_tables: list[str],
    allowed_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Validate DAX scope against allowed tables and columns.

    Args:
        dax_code: DAX code to validate
        allowed_tables: List of allowed table names
        allowed_columns: Optional list of allowed columns

    Returns:
        Scope validation result
    """
    async def _execute():
        from powerbi_orm import DAXExpression

        expr = DAXExpression(raw=dax_code)
        is_valid = expr.is_valid()
        scope_valid = expr.validate_scope(allowed_tables)

        violations = []
        if not is_valid:
            violations.append("syntax_invalid")
        if not scope_valid:
            violations.append("scope_violation")

        return {
            "is_valid": is_valid and scope_valid,
            "syntax_valid": is_valid,
            "scope_valid": scope_valid,
            "violations": violations,
            "allowed_tables": allowed_tables,
        }

    return await instrumented_tool(
        "orm_validate_dax_scope", "safe", _execute,
        required_permission=Permission.VALIDATE_DAX,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_detect_dax_patterns(
    dax_code: str,
) -> dict[str, Any]:
    """Detect anti-patterns and suggest optimizations.

    Args:
        dax_code: DAX code to analyze

    Returns:
        Anti-patterns detected and optimization suggestions
    """
    async def _execute():
        from .validation import detect_anti_patterns, estimate_query_cost

        issues, suggestions = detect_anti_patterns(dax_code)
        cost = estimate_query_cost(dax_code)

        return {
            "issues": issues,
            "suggestions": suggestions,
            "estimated_cost_ms": cost,
            "has_issues": len(issues) > 0,
        }

    return await instrumented_tool(
        "orm_detect_dax_patterns", "safe", _execute,
        required_permission=Permission.VALIDATE_DAX,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_format_dax(
    dax_code: str,
) -> dict[str, Any]:
    """Format DAX code using the ORM's MExpression formatter.

    Args:
        dax_code: DAX code to format

    Returns:
        Formatted DAX code
    """
    async def _execute():
        from powerbi_orm import MExpression

        expr = MExpression(raw=dax_code)
        formatted = expr.clean_whitespace()

        return {
            "original": dax_code,
            "formatted": formatted,
            "is_valid": expr.is_valid(),
        }

    return await instrumented_tool(
        "orm_format_dax", "safe", _execute,
        required_permission=Permission.READ_METADATA,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_extract_dax_references(
    dax_code: str,
) -> dict[str, Any]:
    """Extract table and measure references from DAX code.

    Args:
        dax_code: DAX code to analyze

    Returns:
        Referenced tables and measures
    """
    async def _execute():
        from powerbi_orm import DAXExpression

        expr = DAXExpression(raw=dax_code)
        tables = expr.extract_tables()
        measures = expr.extract_measures()

        return {
            "tables": tables,
            "measures": measures,
            "total_references": len(tables) + len(measures),
        }

    return await instrumented_tool(
        "orm_extract_dax_references", "safe", _execute,
        required_permission=Permission.READ_METADATA,
    )


# ---------------------------------------------------------------------------
# 9. Guardrails  (6 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:safe"})
async def orm_check_rls_access(
    workspace_id: str,
    dataset_id: str,
    table_name: str,
    user_email: str,
) -> dict[str, Any]:
    """Check RLS access for a specific user on a table.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID
        table_name: Table to check
        user_email: User email to check

    Returns:
        RLS access result
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        table = ds.get_table(table_name)
        if table is None:
            return {"error": f"Table '{table_name}' not found"}

        return {
            "table": table_name,
            "user_email": user_email,
            "roles": [r.name for r in ds.roles],
            "note": "Full RLS evaluation requires XMLA endpoint connection",
        }

    return await instrumented_tool(
        "orm_check_rls_access", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_audit_measure_dependencies(
    workspace_id: str,
    dataset_id: str,
) -> dict[str, Any]:
    """Audit all measure dependencies in a dataset.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID

    Returns:
        Dependency graph for all measures
    """
    async def _execute():
        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        dependencies = []
        for t in ds.tables:
            for m in t.measures:
                deps = m.dependencies or []
                dependencies.append({
                    "table": t.name,
                    "measure": m.name,
                    "depends_on": deps,
                    "is_leaf": len(deps) == 0,
                })

        return {"dependencies": dependencies, "count": len(dependencies)}

    return await instrumented_tool(
        "orm_audit_measure_dependencies", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_check_naming_conventions(
    workspace_id: str,
    dataset_id: str,
) -> dict[str, Any]:
    """Check naming conventions for all measures in a dataset.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID

    Returns:
        Naming convention violations
    """
    async def _execute():
        from powerbi_orm import Dataset
        from .validation import matches_naming_convention

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        violations = []
        for t in ds.tables:
            for m in t.measures:
                if not matches_naming_convention(m.name):
                    violations.append({
                        "table": t.name,
                        "measure": m.name,
                        "issue": "Naming convention violation",
                    })

        return {
            "violations": violations,
            "violation_count": len(violations),
            "total_measures": sum(len(t.measures) for t in ds.tables),
        }

    return await instrumented_tool(
        "orm_check_naming_conventions", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_audit_dlp(
    text: str,
    context: str = "general",
) -> dict[str, Any]:
    """Run DLP (Data Loss Prevention) check on text content.

    Args:
        text: Text to check for PII/sensitive data
        context: Context of the check (dax_query, dax_measure, general)

    Returns:
        DLP check result
    """
    async def _execute():
        user = await get_user()

        try:
            state.dlp.check_input(text, user.roles, context=context)
            return {
                "passed": True,
                "text_length": len(text),
                "context": context,
            }
        except DLPError as e:
            return {
                "passed": False,
                "pii_type": e.pii_type,
                "severity": e.severity,
                "context": e.context,
                "message": str(e),
            }

    return await instrumented_tool(
        "orm_audit_dlp", "safe", _execute,
        required_permission=Permission.READ_METADATA,
    )


@mcp.tool(tags={"risk:safe"})
async def orm_check_permissions(
    permission_type: str = "read_metadata",
) -> dict[str, Any]:
    """Check current user's permissions.

    Args:
        permission_type: Permission to check (read_metadata, read_data, write_model, validate_dax, deploy_dev, deploy_test, deploy_prod)

    Returns:
        Permission check result
    """
    async def _execute():
        user = await get_user()
        perm = Permission[permission_type.upper()]

        try:
            check_permission(user, perm)
            return {
                "allowed": True,
                "permission": permission_type,
                "user_roles": user.roles,
            }
        except Exception as e:
            return {
                "allowed": False,
                "permission": permission_type,
                "user_roles": user.roles,
                "error": str(e),
            }

    return await instrumented_tool("orm_check_permissions", "safe", _execute)


@mcp.tool(tags={"risk:safe"})
async def orm_audit_dataset(
    workspace_id: str,
    dataset_id: str,
) -> dict[str, Any]:
    """Comprehensive dataset audit: naming, dependencies, anti-patterns.

    Args:
        workspace_id: Workspace ID
        dataset_id: Dataset ID

    Returns:
        Full audit report
    """
    async def _execute():
        from powerbi_orm import Dataset
        from .validation import matches_naming_convention, detect_anti_patterns

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )
        ds.refresh_schema()

        naming_violations = []
        all_anti_patterns = []
        total_measures = 0

        for t in ds.tables:
            for m in t.measures:
                total_measures += 1
                if not matches_naming_convention(m.name):
                    naming_violations.append(f"{t.name}.{m.name}")
                issues, suggestions = detect_anti_patterns(m.expression)
                if issues:
                    all_anti_patterns.append({
                        "table": t.name,
                        "measure": m.name,
                        "issues": issues,
                        "suggestions": suggestions,
                    })

        return {
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "tables": len(ds.tables),
            "total_measures": total_measures,
            "naming_violations": naming_violations,
            "anti_patterns": all_anti_patterns,
            "score": max(0, 100 - len(naming_violations) * 5 - len(all_anti_patterns) * 10),
        }

    return await instrumented_tool(
        "orm_audit_dataset", "safe", _execute,
        required_permission=Permission.READ_METADATA,
        required_workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 10. Approval  (2 tools)
# ---------------------------------------------------------------------------


@mcp.tool(tags={"risk:critical"})
async def orm_request_approval(
    action: str,
    target: str,
    reason: str,
) -> dict[str, Any]:
    """Request an approval token for a critical ORM action.

    Args:
        action: Action requiring approval (commit_dataset, drop_table, etc.)
        target: Target of the action
        reason: Justification

    Returns:
        Approval token and instructions
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

    return await instrumented_tool("orm_request_approval", "critical", _execute)


@mcp.tool(tags={"risk:critical"})
async def orm_apply_approved_change(
    approval_token: str,
    workspace_id: str,
    dataset_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply an approved ORM change to the dataset.

    REQUIRES an approval token issued by a human.

    Args:
        approval_token: Token issued via CLI or Teams bot
        workspace_id: Target workspace
        dataset_id: Target dataset
        dry_run: If True, validates without applying

    Returns:
        Application result
    """
    async def _execute():
        user = await get_user()
        check_workspace_access(user, workspace_id)

        try:
            approval = await state.approval.validate(approval_token, user)
        except Exception as e:
            return {"error": f"Approval validation failed: {e}"}

        from powerbi_orm import Dataset

        ds = Dataset()
        ds.connect(
            server=state.settings.pbi_xmla_server,
            dataset=dataset_id,
            workspace=workspace_id,
            authentication="service_principal",
            client_id=state.settings.pbi_sp_client_id,
            client_secret=state.settings.pbi_sp_client_secret,
            tenant_id=state.settings.azure_tenant_id,
        )

        if dry_run:
            result = ds.dry_run()
            return {"dry_run": True, "changes": result, "approvers": approval.approvers}

        ds.commit()
        return {
            "status": "applied",
            "approvers": approval.approvers,
            "approval_action": approval.action,
        }

    return await instrumented_tool("orm_apply_approved_change", "critical", _execute)
