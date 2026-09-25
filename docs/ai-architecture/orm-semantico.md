#  ORM Semântico · Power BI Tabular Model

> SDK Python para manipular o modelo semântico do Power BI como se fosse ORM.
> Wrapper sobre TOM (Tabular Object Model) + TMDL + XMLA + pbi-tools.

## 1. Por que "ORM" e não "ORM"

Power BI usa **Tabular Model** (Analysis Services por baixo). Não é relacional. **Não existe ORM tradicional** (SQLAlchemy, Entity Framework) que funcione. O que construímos é um **SDK fluente** que dá sensação de ORM:

- Classes mapeadas a entidades do modelo (Table, Column, Measure, Relationship)
- Decorators para declaração declarativa
- Validação de schema
- Migration-like versionamento

## 2. Stack

- **Linguagem:** Python 3.11+
- **XMLA:** `pyadomd` (ADO.NET provider pra Python)
- **Auth:** `msal`
- **TOM:** via `pbi-tools` CLI
- **TMDL parsing:** custom (YAML superset)
- **Validação:** `pydantic` v2
- **Testes:** `pytest` + `pytest-mock`

## 3. Estrutura

```
tools/orm/
├── pyproject.toml
├── README.md
├── src/
│   └── powerbi_orm/
│       ├── __init__.py
│       ├── dataset.py            # Dataset class (root)
│       ├── table.py              # Table class
│       ├── column.py             # Column types
│       ├── measure.py            # Measure class
│       ├── relationship.py       # Relationship class
│       ├── role.py               # RLS Role class
│       ├── expression.py         # DAX/M expression wrapper
│       ├── connection.py         # XMLA + REST connection
│       ├── query.py              # DAX query execution
│       ├── validation.py         # schema validation
│       ├── exceptions.py
│       └── types.py
├── tests/
│   ├── unit/
│   └── integration/
└── examples/
    ├── 01_basic_read.py
    ├── 02_add_measure.py
    ├── 03_create_relationship.py
    └── 04_migration.py
```

## 4. API

### 4.1 Conexão

```python
from powerbi_orm import Dataset

ds = Dataset.connect(
    workspace="bi-vendas-dev",
    auth={
        "tenant_id": os.environ["PBI_TENANT_ID"],
        "client_id": os.environ["PBI_MCP_SP_CLIENT_ID"],
        "client_secret": os.environ["PBI_MCP_SP_CLIENT_SECRET"],
    },
    timeout=30,
)
```

### 4.2 Read · Query DAX

```python
# Query simples
result = ds.query("""
    EVALUATE
    SUMMARIZECOLUMNS(
        'd_cliente'[segmento],
        "Receita", [Vendas.Receita Total BRL]
    )
    ORDER BY [Receita] DESC
""")
for row in result.rows:
    print(f"{row['segmento']}: R$ {row['Receita']:,.2f}")

# Query com parâmetros
result = ds.query_dax_file(
    "tests/queries/receita_por_segmento.dax",
    params={"year": 2026, "min_value": 100_000}
)

# Row shortcut
receita = ds.dax("EVALUATE ROW(\"x\", [Vendas.Receita Total BRL])").scalar()
print(f"Receita total: R$ {receita:,.2f}")
```

### 4.3 Read · Schema introspection

```python
# Lista tabelas
for table in ds.tables:
    print(f"{table.name} ({len(table.columns)} cols, {len(table.measures)} measures)")

# Detalhe de uma tabela
vendas = ds.tables["f_vendas__pedido"]
print(vendas.columns["valor_brl"].data_type)       # Decimal
print(vendas.columns["cliente_id"].relationships)   # ['d_cliente']

# Medidas com filtro
measures = ds.measures.filter(folder="Vendas")
for m in measures:
    print(f"{m.name}: {m.expression[:60]}...")
```

### 4.4 Write · Adicionar medida

```python
from powerbi_orm import Measure, FormatString

ds.tables["f_vendas__pedido"].add_measure(
    Measure(
        name="Vendas.Ticket Médio [R$]",
        expression="""
            VAR _receita = [Vendas.Receita Total BRL]
            VAR _pedidos = DISTINCTCOUNT(f_vendas__pedido[pedido_id])
            RETURN
                DIVIDE(_receita, _pedidos, 0)
        """,
        format_string=FormatString.CURRENCY_BRL,
        folder="Vendas",
        description="Valor médio por pedido, considerando devoluções",
        is_hidden=False,
    )
)

# Valida antes de commit
ds.validate()        # roda schema + naming + DAX syntax check
ds.dry_run()         # simula a operação

# Commit (cria branch + PR)
ds.commit(
    branch="feat/vendas-ticket-medio",
    message="feat(vendas): adiciona medida Ticket Médio",
    pr_title="feat(vendas): adiciona medida Ticket Médio [R$]",
    pr_body="Gerado por powerbi-orm via AI",
    create_pr=True,
)
```

### 4.5 Write · Atualizar relacionamento

```python
from powerbi_orm import Relationship, Cardinality, CrossFilter

ds.add_relationship(
    Relationship(
        from_table="f_vendas__pedido",
        from_column="cliente_id",
        to_table="d_cliente",
        to_column="cliente_id",
        cardinality=Cardinality.MANY_TO_ONE,
        cross_filter=CrossFilter.SINGLE,
        is_active=True,
    )
)
```

### 4.6 Write · RLS Role

```python
from powerbi_orm import Role, RoleFilter

ds.add_role(
    Role(
        name="Gerente Regional",
        members=[],  # populado via API depois
        table_filters=[
            RoleFilter(
                table="d_cliente",
                expression="[regiao] = USERPRINCIPALNAME()",
            )
        ],
    )
)
```

### 4.7 Migration · versionamento declarativo

```python
# migrations/001_add_ticket_medio.py
from powerbi_orm import Migration, AddMeasure

class AddTicketMedio(Migration):
    version = "1.4.0"
    description = "Adiciona medida Ticket Médio"
    
    def up(self, ds: Dataset):
        ds.tables["f_vendas__pedido"].add_measure(
            Measure(
                name="Vendas.Ticket Médio [R$]",
                expression="DIVIDE([Vendas.Receita Total BRL], DISTINCTCOUNT(f_vendas__pedido[pedido_id]))",
                format_string=FormatString.CURRENCY_BRL,
                folder="Vendas",
            )
        )
    
    def down(self, ds: Dataset):
        ds.tables["f_vendas__pedido"].remove_measure("Vendas.Ticket Médio [R$]")

# Roda migração
ds.migrate("001_add_ticket_medio")
ds.migrate("001_add_ticket_medio", direction="down")
```

## 5. Internals · como funciona por baixo

```
powerbi_orm (Python)
    ↓ usa
┌──────────────────┬─────────────────┬──────────────┐
│ pyadomd (XMLA)   │ pbi-tools CLI   │ REST API     │
│ - query DAX      │ - compile       │ - deploy     │
│ - read schema    │ - extract       │ - refresh    │
│                  │ - publish       │ - metadata   │
└──────────────────┴─────────────────┴──────────────┘
    ↓                       ↓                ↓
XMLA endpoint         Local PBIP        Power BI
(Direct Query)        (TMDL files)      Service
```

**Operação de write (ex: add_measure):**

```
1. add_measure() chamado
2. SDK valida com pydantic (schema, naming, formato)
3. SDK baixa TMDL atual via XMLA ou git pull
4. SDK modifica TMDL em memória (preservando formatação)
5. SDK roda pbi-tools compile local (valida sintaxe)
6. SDK roda validate_dax (semantic check)
7. SDK cria branch no git
8. SDK commit + push
9. SDK abre PR via GitHub API
10. Retorna PRProposal (nunca modifica o Service direto)
```

**Operação de read (ex: query):**

```
1. query() chamado
2. SDK checa cache Redis (TTL 60s)
3. Se miss, executa via pyadomd → XMLA endpoint
4. Parse do ADOMD result set
5. Retorna DataFrame-like object (result.rows, result.scalar(), etc)
6. Atualiza cache
```

## 6. Validação automática

```python
# Rodado em add_measure e em dry_run
def validate_measure(m: Measure, ds: Dataset) -> ValidationResult:
    checks = [
        # 1. Sintaxe
        ("syntax", pbi_tools.compile_check(m.to_tmdl())),
        # 2. Nome segue convenção
        ("naming", matches_naming_convention(m.name, ds)),
        # 3. Referências existem
        ("references", all(ref in ds.symbols for ref in m.expression.references)),
        # 4. Não é duplicado
        ("duplicate", m.name not in ds.measure_names),
        # 5. Pastas existem
        ("folder", m.folder in ds.allowed_folders or m.folder is None),
        # 6. Performance — não usa FILTER pesado
        ("performance", estimate_cost(m.expression) < MAX_COST),
    ]
    return ValidationResult(checks)
```

## 7. Limitações conhecidas

- **Não suporta TODAS as features do TOM.** Tabelas calculadas, perspectives, e algumas advanced features ficam pra depois.
- **Write não é transacional.** Se o commit no git falha após o compile, fica inconsistente. Mitigação: state machine com retry.
- **Schema cache pode ficar stale.** Em datasets grandes com muitos devs, usar `ds.refresh_schema()` antes de modificar.
- **Direct Query vs Import:** o ORM funciona com ambos, mas performance de query é diferente.

## 8. Roadmap

- [ ] v0.1 — read-only (query, schema, lineage)
- [ ] v0.2 — write measures, columns
- [ ] v0.3 — relationships, RLS
- [ ] v0.4 — migrations framework
- [ ] v0.5 — perspectives, translations
- [ ] v0.6 — Fabric / OneLake support
- [ ] v1.0 — produção-ready com cobertura de testes > 80%
