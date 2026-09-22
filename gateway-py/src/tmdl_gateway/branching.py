"""Branch -> dataset (divergência só no commit). Fonte única em Python.

Espelha `Settings.dataset_for_branch` (MCP) e o resolver TS da fachada.
Workspace permanece único e dinâmico (`PBI_WORKSPACE_ID`).
"""

from __future__ import annotations

import re


def resolve_dataset_for_branch(branch: str, base: str = "Vendas") -> str:
    """Mapeia branch para nome do dataset.

    main -> Vendas | develop -> Vendas_Dev | test/release/* -> Vendas_Test
    | demais -> Vendas_preview_<slug> (slug max 20 chars).
    """
    b = (branch or "").strip()
    if b == "main":
        return base
    if b == "develop":
        return f"{base}_Dev"
    if b == "test" or b.startswith("release/"):
        return f"{base}_Test"
    slug = re.sub(r"[^a-z0-9]+", "_", b.lower()).strip("_")[:20].strip("_")
    return f"{base}_preview_{slug}" if slug else f"{base}_preview"


def is_prod_target(branch: str) -> bool:
    """Prod = main (dataset base sem sufixo). Exige 2 aprovadores."""
    return (branch or "").strip() == "main"
