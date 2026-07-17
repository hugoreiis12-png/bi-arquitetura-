"""powerbi-orm usage examples.

Run with: python -m examples
"""

import os

from powerbi_orm import (
    Column,
    ColumnType,
    DAXExpression,
    Dataset,
    Measure,
    Relationship,
    Cardinality,
)


def example_basic_read():
    """Connect and read schema."""
    ds = Dataset.connect(
        workspace=os.environ["PBI_WORKSPACE_ID"],
        tenant_id=os.environ["PBI_TENANT_ID"],
        client_id=os.environ["PBI_SP_CLIENT_ID"],
        client_secret=os.environ["PBI_SP_CLIENT_SECRET"],
    )
    ds.refresh_schema()

    print(f"Dataset: {ds.name} ({ds.dataset_id})")
    print(f"Tables: {len(ds.tables)}")

    for table in ds.tables:
        print(f"  {table.name}: {len(table.columns)} cols, {len(table.measures)} measures")


def example_query():
    """Execute a DAX query."""
    ds = Dataset.connect(
        workspace=os.environ["PBI_WORKSPACE_ID"],
        tenant_id=os.environ["PBI_TENANT_ID"],
        client_id=os.environ["PBI_SP_CLIENT_ID"],
        client_secret=os.environ["PBI_SP_CLIENT_SECRET"],
    )

    result = ds.query("EVALUATE ROW(\"Receita\", [Vendas.Receita Total BRL])")
    if result.error:
        print(f"Error: {result.error}")
    elif result.has_data:
        print(f"Receita Total: R$ {result.scalar():,.2f}")


def example_add_measure():
    """Add a new measure to a table."""
    ds = Dataset.connect(
        workspace=os.environ["PBI_WORKSPACE_ID"],
        tenant_id=os.environ["PBI_TENANT_ID"],
        client_id=os.environ["PBI_SP_CLIENT_ID"],
        client_secret=os.environ["PBI_SP_CLIENT_SECRET"],
    )
    ds.refresh_schema()

    # Add a new measure
    ds.tables["f_vendas__pedido"].add_measure(
        Measure(
            name="Vendas.Ticket Médio [R$]",
            expression=DAXExpression(
                "DIVIDE([Vendas.Receita Total BRL], DISTINCTCOUNT(f_vendas__pedido[pedido_id]), 0)"
            ),
            format_string="R$ #,##0.00",
            folder="Vendas",
            description="Valor médio por pedido, considerando devoluções",
        )
    )

    # Validate before commit
    issues = ds.validate()
    if issues:
        print("Validation issues:")
        for i in issues:
            print(f"  - {i}")
        return

    # Dry run
    print("Dry run:", ds.dry_run())

    # Commit (creates branch + PR)
    result = ds.commit(
        branch="feat/vendas-ticket-medio",
        message="feat(vendas): adiciona medida Ticket Médio [R$]",
        create_pr=True,
    )
    print(f"PR: {result.get('pr_url', 'N/A')}")


if __name__ == "__main__":
    example_basic_read()
