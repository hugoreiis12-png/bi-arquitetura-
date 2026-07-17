# powerbi-orm

Python ORM-style SDK for Power BI semantic models (Tabular/TMDL).

## What it does

- **Read** semantic model schema (tables, columns, measures, relationships, RLS)
- **Query** DAX against the dataset (DirectQuery via XMLA)
- **Write** measures, columns, relationships, RLS roles
- **Validate** schema (naming, duplicates, references)
- **Commit** changes via git (creates branch + PR)
- **Generate TMDL** from Python objects

## What it's NOT

- Not a real ORM (no SQL database underneath)
- Not a substitute for Power BI Desktop
- Not for editing report visuals (use Desktop for that)

## Install

```bash
pip install powerbi-orm
```

## Quickstart

```python
import os
from powerbi_orm import Dataset, DAXExpression, Measure

# Connect
ds = Dataset.connect(
    workspace=os.environ["PBI_WORKSPACE_ID"],
    tenant_id=os.environ["PBI_TENANT_ID"],
    client_id=os.environ["PBI_SP_CLIENT_ID"],
    client_secret=os.environ["PBI_SP_CLIENT_SECRET"],
)
ds.refresh_schema()

# Read
print(f"Tables: {len(ds.tables)}")
for table in ds.tables:
    print(f"  {table.name}: {len(table.columns)} cols, {len(table.measures)} measures")

# Query
result = ds.query("EVALUATE ROW(\"x\", [Vendas.Receita Total BRL])")
if result.has_data:
    print(f"Receita: R$ {result.scalar():,.2f}")

# Add a measure
ds.tables["f_vendas__pedido"].add_measure(
    Measure(
        name="Vendas.Ticket Médio [R$]",
        expression=DAXExpression(
            "DIVIDE([Vendas.Receita Total BRL], DISTINCTCOUNT(f_vendas__pedido[pedido_id]), 0)"
        ),
        format_string="R$ #,##0.00",
        folder="Vendas",
    )
)

# Validate
issues = ds.validate()
if not issues:
    # Commit (creates branch + PR)
    result = ds.commit(
        branch="feat/vendas-ticket-medio",
        message="feat(vendas): adiciona medida Ticket Médio",
        create_pr=True,
    )
    print(f"PR: {result.get('pr_url')}")
```

## Architecture

powerbi-orm wraps multiple technologies:

| Layer | Tech | Purpose |
|---|---|---|
| Connection | `httpx` + `msal` | REST API for metadata |
| Query | `pyadomd` | XMLA endpoint for DAX |
| Schema | TOM via XMLA | Read Tabular schema |
| Write | Git CLI | Commit + push + create PR |
| Validation | Pure Python | Naming, syntax, scope |

## API Reference

### `Dataset`

Root class. Holds the entire model.

- `Dataset.connect(workspace, tenant_id, client_id, client_secret)` — factory
- `ds.refresh_schema()` — load schema from XMLA
- `ds.query(dax)` — execute DAX, return `QueryResult`
- `ds.dax(dax)` — shorthand for `query`
- `ds.tables` — list of `Table`
- `ds.relationships` — list of `Relationship`
- `ds.roles` — list of `Role`
- `ds.add_relationship(rel)`
- `ds.add_role(role)`
- `ds.validate()` — return list of issues
- `ds.dry_run()` — show what would change
- `ds.commit(branch, message, create_pr=True)` — git commit + PR
- `ds.to_tmdl()` — serialize to TMDL

### `Table`

- `table.add_column(col)`
- `table.add_measure(measure)`
- `table.remove_measure(name)`
- `table.get_measure(name)` / `get_column(name)`
- `table.to_tmdl()`

### `Measure`

```python
Measure(
    name="Vendas.Receita BRL",
    expression=DAXExpression("SUM('f_vendas__pedido'[valor_brl])"),
    format_string="R$ #,##0.00",
    folder="Vendas",
    description="...",
)
```

### `Column`

```python
Column(
    name="cliente_id",
    data_type=ColumnType.INT64,
    is_key=True,
    format_string="0",
)
```

### `Relationship`

```python
Relationship(
    from_table="f_vendas",
    from_column="cliente_id",
    to_table="d_cliente",
    to_column="cliente_id",
    cardinality=Cardinality.MANY_TO_ONE,
    cross_filter=CrossFilter.SINGLE,
)
```

### `Role`

```python
role = Role(name="Vendedor")
role.add_filter("d_cliente", "[vendedor_email] = USERPRINCIPALNAME()")
role.members = ["user1@empresa.com", "user2@empresa.com"]
```

## License

MIT
