"""Tests for DAX validation."""

import pytest

from powerbi_mcp.validation import (
    DAXValidator,
    ValidationCheck,
    estimate_query_cost,
    extract_references,
    is_select_only_dax,
    matches_naming_convention,
)


class TestNamingConvention:
    def test_valid_names(self):
        assert matches_naming_convention("Vendas.Receita Total BRL")
        assert matches_naming_convention("Vendas.Margem %")
        assert matches_naming_convention("Estoque.Giro Dias")
        assert matches_naming_convention("RH.Headcount Ativo")

    def test_invalid_names(self):
        assert not matches_naming_convention("vendas.receita")
        assert not matches_naming_convention("Receita Total BRL")
        assert not matches_naming_convention("vendas.Receita Total")
        assert not matches_naming_convention("Vendas.")


class TestSelectOnly:
    def test_select_queries_pass(self):
        assert is_select_only_dax("EVALUATE ROW(\"x\", 1)")
        assert is_select_only_dax("EVALUATE FILTER('Vendas', [Valor] > 100)")
        assert is_select_only_dax("DEFINE MEASURE 'A'[X] = 1\nEVALUATE ROW(\"x\", [X])")

    def test_destructive_queries_fail(self):
        assert not is_select_only_dax("DROP TABLE 'Vendas'")
        assert not is_select_only_dax("DELETE FROM 'Vendas' WHERE 1=1")
        assert not is_select_only_dax("ALTER TABLE 'Vendas' ADD COLUMN [X]")
        assert not is_select_only_dax("CREATE TABLE [X] ([Y] INT)")


class TestCostEstimation:
    def test_simple_query_low_cost(self):
        cost = estimate_query_cost("EVALUATE ROW(\"x\", SUM('Vendas'[Valor]))")
        assert cost < 100

    def test_filter_increases_cost(self):
        base = estimate_query_cost("EVALUATE ROW(\"x\", 1)")
        with_filter = estimate_query_cost("EVALUATE FILTER('Vendas', [Valor] > 0)")
        assert with_filter > base

    def test_iterators_increase_cost(self):
        without = estimate_query_cost("EVALUATE SUM('Vendas'[Valor])")
        with_iter = estimate_query_cost("EVALUATE SUMX('Vendas', [Valor])")
        assert with_iter > without


class TestReferenceExtraction:
    def test_extracts_tables(self):
        refs = extract_references("EVALUATE 'Vendas'")
        assert "Vendas" in refs

    def test_extracts_columns(self):
        refs = extract_references("EVALUATE ROW(\"x\", [Valor])")
        assert "Valor" in refs

    def test_extracts_mixed(self):
        dax = "EVALUATE FILTER('Vendas', 'Vendas'[Valor] > 0)"
        refs = extract_references(dax)
        assert "Vendas" in refs
        assert "Valor" in refs


class TestDAXValidator:
    @pytest.mark.asyncio
    async def test_valid_simple_dax(self):
        validator = DAXValidator()
        result = await validator.validate(
            "EVALUATE ROW(\"x\", SUM('Vendas'[Valor]))",
            measure_name="Vendas.Test",
        )
        assert result.is_valid
        assert result.checks[ValidationCheck.SYNTAX]
        assert result.checks[ValidationCheck.NAMING]
        assert result.checks[ValidationCheck.PERFORMANCE]

    @pytest.mark.asyncio
    async def test_unbalanced_parens(self):
        validator = DAXValidator()
        result = await validator.validate(
            "EVALUATE ROW(\"x\", SUM('Vendas'[Valor]",
            measure_name="Vendas.Test",
        )
        assert not result.checks[ValidationCheck.SYNTAX]
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_invalid_naming(self):
        validator = DAXValidator()
        result = await validator.validate(
            "EVALUATE ROW(\"x\", 1)",
            measure_name="receita total",
        )
        assert not result.checks[ValidationCheck.NAMING]

    @pytest.mark.asyncio
    async def test_scope_violation(self):
        validator = DAXValidator(allowed_symbols={"Vendas", "Valor"})
        result = await validator.validate(
            "EVALUATE ROW(\"x\", 'Forbidden'[Secret])",
            measure_name="Vendas.Test",
        )
        assert not result.checks[ValidationCheck.SCOPE]

    @pytest.mark.asyncio
    async def test_expensive_query(self):
        validator = DAXValidator(max_cost_ms=100.0)
        dax = "EVALUATE FILTER(FILTER(FILTER('Vendas', [X] > 0), [Y] > 0), [Z] > 0)"
        result = await validator.validate(dax, measure_name="Vendas.Test")
        assert not result.checks[ValidationCheck.PERFORMANCE]

    @pytest.mark.asyncio
    async def test_markdown_report(self):
        validator = DAXValidator()
        result = await validator.validate(
            "EVALUATE ROW(\"x\", 1)",
            measure_name="Vendas.Test",
        )
        md = result.to_markdown()
        assert "Validação DAX" in md
        assert "Vendas.Test" in md
        assert "Sintaxe" in md or "Syntax" in md
