"""
MCP tool for TMDL audit — wraps tmdl.py into a callable MCP tool.

Provides `pbi_tmdl_audit` which runs declarative TMDL rules against a
model definition folder and returns structured findings.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from fastmcp import FastMCP

# Re-export the server instance from server.py
from .server import mcp, instrumented_tool, get_user

# Import the TMDL audit engine
from .tmdl import (
    collect,
    coletar_alvos,
    executar_regras,
    render_md,
    merge_convencoes,
    carregar_json,
    SEVERIDADES,
)


@mcp.tool(tags={"risk:safe", "tmdl", "audit"})
async def pbi_tmdl_audit(
    folder: str,
    rules_path: Optional[str] = None,
    conventions_path: Optional[str] = None,
    format: str = "json",
    fail_on_high: bool = False,
    max_items: int = 25,
) -> str:
    """Audita uma pasta TMDL (definition) do Power BI com regras declarativas.

    Executa regras de qualidade sobre tabelas, colunas, medidas, relacionamentos,
    roles e perspectivas. Retorna inventário do modelo + achados por severidade.

    Args:
        folder: Caminho da pasta TMDL (ex.: ./Vendas.SemanticModel/definition)
        rules_path: Caminho para rules.json (padrão: assets/rules.json do package)
        conventions_path: Caminho para tmdl.conventions.json do projeto (opcional)
        format: Formato de saída — "json" ou "md" (padrão: json)
        fail_on_high: Se True, retorna código 1 quando há achados de severidade alta
        max_items: Máximo de itens listados por achado no formato md (padrão: 25)

    Returns:
        Auditoria completa com inventário e achados estruturados.
    """

    async def _execute():
        # Resolve rules path
        if not rules_path:
            rules_padrao = os.path.join(
                os.path.dirname(__file__), "assets", "rules.json"
            )
            effective_rules = rules_padrao
        else:
            effective_rules = rules_path

        if not os.path.isfile(effective_rules):
            return json.dumps(
                {"error": f"Regras não encontradas: {effective_rules}"},
                ensure_ascii=False,
            )

        if not os.path.isdir(folder):
            return json.dumps(
                {"error": f"Pasta não encontrada: {folder}"},
                ensure_ascii=False,
            )

        # Load rules
        regras_doc = carregar_json(effective_rules)
        if not regras_doc:
            return json.dumps(
                {"error": f"Erro ao carregar regras: {effective_rules}"},
                ensure_ascii=False,
            )
        regras = regras_doc.get("rules", [])

        # Load conventions
        conv = merge_convencoes(carregar_json(conventions_path))

        # Collect TMDL documents
        docs = collect(folder)
        if not docs:
            return json.dumps(
                {"error": f"Nenhum arquivo .tmdl encontrado em {folder}"},
                ensure_ascii=False,
            )

        # Run audit
        alvos, indice, inventario, tabelas = coletar_alvos(docs)
        achados = executar_regras(alvos, indice, regras, conv)

        if format == "md":
            return render_md(inventario, tabelas, achados, conv, limite=max_items)

        # JSON output
        result = {
            "inventario": inventario,
            "tabelas": tabelas,
            "achados": achados,
            "convencoes": conventions_path,
            "regras": effective_rules,
            "resumo": {
                "total_ocorrencias": sum(a["quantidade"] for a in achados),
                "regras_violadas": len(achados),
                "alta": sum(
                    a["quantidade"] for a in achados if a["severidade"] == "alta"
                ),
                "media": sum(
                    a["quantidade"] for a in achados if a["severidade"] == "media"
                ),
                "baixa": sum(
                    a["quantidade"] for a in achados if a["severidade"] == "baixa"
                ),
            },
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    return await instrumented_tool("pbi_tmdl_audit", "read", _execute)
