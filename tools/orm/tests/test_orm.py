"""Tests for powerbi-orm."""

import pytest

from powerbi_orm import (
    Cardinality,
    Column,
    ColumnType,
    CrossFilter,
    DAXExpression,
    Dataset,
    Measure,
    Relationship,
    Role,
    Table,
)
from powerbi_orm.exceptions import ValidationError


class TestDAXExpression:
    def test_valid_expression(self):
        expr = DAXExpression("SUM('Vendas'[Valor])")
        assert "Vendas" in expr.table_references
        assert "Valor" in expr.column_references

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            DAXExpression("")

    def test_unbalanced_parens_raises(self):
        with pytest.raises(ValidationError):
            DAXExpression("SUM('Vendas'[Valor]")

    def test_unbalanced_brackets_raises(self):
        with pytest.raises(ValidationError):
            DAXExpression("SUM('Vendas'[Valor)")


class TestMeasure:
    def test_valid_measure(self):
        m = Measure(
            name="Vendas.Receita Total BRL",
            expression=DAXExpression("SUM('f_vendas__pedido'[valor_brl])"),
        )
        assert m.name == "Vendas.Receita Total BRL"

    def test_invalid_naming_raises(self):
        with pytest.raises(ValidationError):
            Measure(
                name="receita total",  # lowercase, no domain
                expression=DAXExpression("SUM([x])"),
            )

    def test_tmdl_generation(self):
        m = Measure(
            name="Vendas.Receita BRL",
            expression=DAXExpression("SUM('Vendas'[Valor])"),
            folder="Vendas/Receita",
            format_string="R$ #,##0.00",
        )
        tmdl = m.to_tmdl()
        assert "measure 'Vendas.Receita BRL'" in tmdl
        assert "displayFolder: Vendas/Receita" in tmdl
        assert "formatString: R$ #,##0.00" in tmdl
        assert "SUM('Vendas'[Valor])" in tmdl


class TestColumn:
    def test_valid_column(self):
        c = Column(name="cliente_id", data_type=ColumnType.INT64, is_key=True)
        assert c.name == "cliente_id"
        assert c.is_key

    def test_invalid_name_raises(self):
        with pytest.raises(ValidationError):
            Column(name="cliente-id", data_type=ColumnType.STRING)  # hyphen

    def test_tmdl_generation(self):
        c = Column(
            name="valor_brl",
            data_type=ColumnType.DECIMAL,
            format_string="#,##0.00",
        )
        tmdl = c.to_tmdl()
        assert "column valor_brl" in tmdl
        assert "dataType: decimal" in tmdl


class TestTable:
    def test_fact_table_detection(self):
        t = Table(name="f_vendas__pedido")
        assert t.is_fact
        assert not t.is_dimension

    def test_dimension_table_detection(self):
        t = Table(name="d_cliente")
        assert t.is_dimension
        assert not t.is_fact

    def test_helper_table_detection(self):
        t = Table(name="_util_business_days")
        assert t.is_helper

    def test_add_measure_chaining(self):
        t = Table(name="f_vendas")
        result = t.add_measure(
            Measure(
                name="Vendas.Test",
                expression=DAXExpression("1"),
            )
        )
        assert result is t  # chaining
        assert len(t.measures) == 1

    def test_remove_measure(self):
        t = Table(name="f_vendas")
        t.add_measure(
            Measure(name="Vendas.A", expression=DAXExpression("1"))
        )
        t.add_measure(
            Measure(name="Vendas.B", expression=DAXExpression("2"))
        )
        t.remove_measure("Vendas.A")
        assert len(t.measures) == 1
        assert t.measures[0].name == "Vendas.B"


class TestRelationship:
    def test_default_name(self):
        r = Relationship(
            from_table="f_vendas",
            from_column="cliente_id",
            to_table="d_cliente",
            to_column="cliente_id",
        )
        assert "f_vendas" in r.name
        assert "d_cliente" in r.name

    def test_tmdl_generation(self):
        r = Relationship(
            from_table="f_vendas",
            from_column="cliente_id",
            to_table="d_cliente",
            to_column="cliente_id",
            cardinality=Cardinality.MANY_TO_ONE,
            cross_filter=CrossFilter.SINGLE,
        )
        tmdl = r.to_tmdl()
        assert "fromColumn: f_vendas[cliente_id]" in tmdl
        assert "toColumn: d_cliente[cliente_id]" in tmdl


class TestRole:
    def test_add_filter_chaining(self):
        role = Role(name="Vendedor")
        result = role.add_filter(
            "d_cliente",
            "[vendedor_email] = USERPRINCIPALNAME()",
        )
        assert result is role
        assert len(role.table_filters) == 1

    def test_tmdl_generation(self):
        role = Role(name="Vendedor")
        role.add_filter("d_cliente", "[vendedor_email] = USERPRINCIPALNAME()")
        tmdl = role.to_tmdl()
        assert "role 'Vendedor'" in tmdl
        assert "tablePermission d_cliente" in tmdl
        assert "USERPRINCIPALNAME()" in tmdl


class TestDataset:
    def test_measure_names(self):
        ds = Dataset(workspace_id="ws", dataset_id="ds")
        t = Table(name="f_vendas")
        t.add_measure(Measure(name="Vendas.A", expression=DAXExpression("1")))
        t.add_measure(Measure(name="Vendas.B", expression=DAXExpression("2")))
        ds.tables.append(t)

        assert "Vendas.A" in ds.measure_names
        assert "Vendas.B" in ds.measure_names

    def test_validate_duplicate_measures(self):
        ds = Dataset(workspace_id="ws", dataset_id="ds")
        t = Table(name="f_vendas")
        t.add_measure(Measure(name="Vendas.Dup", expression=DAXExpression("1")))
        # Add same name to another table
        t2 = Table(name="f_outro")
        t2.add_measure(Measure(name="Vendas.Dup", expression=DAXExpression("1")))
        ds.tables.extend([t, t2])

        issues = ds.validate()
        assert any("Duplicate" in i for i in issues)

    def test_validate_missing_relationship_table(self):
        ds = Dataset(workspace_id="ws", dataset_id="ds")
        ds.add_relationship(
            Relationship(
                from_table="nonexistent_table",
                from_column="id",
                to_table="d_cliente",
                to_column="id",
            )
        )
        issues = ds.validate()
        assert any("missing table" in i for i in issues)

    def test_all_symbols(self):
        ds = Dataset(workspace_id="ws", dataset_id="ds")
        t = Table(name="d_cliente")
        t.add_column(Column(name="cliente_id", data_type=ColumnType.INT64))
        t.add_measure(Measure(name="Vendas.Test", expression=DAXExpression("1")))
        ds.tables.append(t)

        symbols = ds.all_symbols
        assert "d_cliente" in symbols
        assert "cliente_id" in symbols
        assert "Vendas.Test" in symbols

    def test_dry_run(self):
        ds = Dataset(workspace_id="ws", dataset_id="ds")
        t = Table(name="f_vendas")
        t.add_measure(Measure(name="Vendas.X", expression=DAXExpression("1")))
        ds.tables.append(t)
        ds.add_relationship(
            Relationship(
                from_table="f_vendas",
                from_column="x",
                to_table="d_cliente",
                to_column="x",
            )
        )

        result = ds.dry_run()
        assert result["tables"] == 1
        assert result["relationships"] == 1
        assert result["pending_changes"] == 1
