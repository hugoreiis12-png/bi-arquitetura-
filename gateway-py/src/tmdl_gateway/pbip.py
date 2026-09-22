"""Normalização TOM -> PBIP (serialização flat do TOM para layout definition/).

O `ExportToTmdlFolder` do sidecar (e o `pbi-tools extract` sem `--format PBIP`)
gera pasta flat: `database.tmdl`, `model.tmdl`, `relationships.tmdl`,
`<tabela>.tmdl` e culturas tudo na raiz. O repo (e o Desktop em modo PBIP)
espera `src/datasets/<Nome>.Dataset/definition/` com `tables/`, `cultures/`,
`roles/`, `version.json` e o ponteiro `.pbip` — ver `scaffolding/EXEMPLO-PBIP.md`.

Idempotente: se `definition/version.json` já existe e não há `.tmdl` soltos,
não faz nada.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


PBIP_DEFINITION_VERSION = {"version": "1.0"}

# Arquivos que vivem na raiz de definition/
MODEL_FILES = {"model.tmdl", "relationships.tmdl", "expressions.tmdl"}

# Tabelas geradas pelo Desktop (auto date/time): quarentena fora de definition/
AUTO_DATE_PREFIXES = ("LocalDateTable_", "DateTableTemplate_")

# pt-BR.tmdl, en-US.tmdl, ...
CULTURE_RE = re.compile(r"^[a-z]{2}-[A-Za-z]{2}$")


class PbipError(Exception):
    pass


def _move(src: Path, dst: Path, report: dict, kind: str) -> None:
    """Move arquivo e registra em `<kind>_arquivos` (contadores ficam separados)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        report.setdefault("sobrescritos", []).append(str(dst))
        if dst.is_file():
            dst.unlink()
    shutil.move(str(src), str(dst))
    report.setdefault(f"{kind}_arquivos", []).append(dst.name)


def normalize_tom_to_pbip(
    src_dir: str | Path,
    dataset_dir: str | Path,
    dataset_display_name: str = "Vendas",
) -> dict:
    """Reorganiza export flat TOM em layout PBIP. Retorna relatório.

    `src_dir`: pasta do export flat. `dataset_dir`: `<Nome>.Dataset/` destino
    (criado se ausente). `database.tmdl` vai para `_tom_source/` (proveniência,
    fora do compile). Auto-dates vão para `_auto_dates/` (fora do compile).
    """
    src = Path(src_dir)
    dest = Path(dataset_dir)
    if not src.is_dir():
        raise PbipError(f"pasta de origem inexistente: {src}")
    flat = [p for p in src.glob("*.tmdl") if p.is_file()]
    if not flat:
        if (src / "definition" / "version.json").is_file():
            return {"status": "ja_normalizado", "dataset_dir": str(src)}
        # src pode ser a própria definition/ (caso pull_apply direto nela)
        if (src / "version.json").is_file():
            return {"status": "ja_normalizado", "dataset_dir": str(src.parent)}
        raise PbipError(f"nenhum .tmdl em {src}")
    definition = dest / "definition"
    if (definition / "version.json").is_file() and not flat:
        return {"status": "ja_normalizado", "dataset_dir": str(dest)}
    if (definition / "version.json").is_file() and flat and src.resolve() != definition.resolve():
        pass  # segue: há material novo para incorporar

    report: dict = {
        "status": "normalizado",
        "dataset_dir": str(dest),
        "tabelas": 0,
        "quarentena_auto_dates": 0,
    }
    tables_d = definition / "tables"
    cultures_d = definition / "cultures"
    roles_d = definition / "roles"
    tom_source_d = dest / "_tom_source"
    auto_dates_d = dest / "_auto_dates"

    # Subpastas já organizadas (roles/, cultures/, tables/) — mescla.
    for sub in ("roles", "cultures", "tables"):
        s = src / sub
        if s.is_dir():
            for f in sorted(s.glob("*.tmdl")):
                _move(f, definition / sub / f.name, report, f"mesclados_{sub}")
            try:
                s.rmdir()
            except OSError:
                pass

    for f in sorted(flat):
        name = f.name
        if name == "database.tmdl":
            _move(f, tom_source_d / name, report, "proveniencia")
        elif name in MODEL_FILES:
            _move(f, definition / name, report, "modelo")
        elif CULTURE_RE.match(f.stem):
            _move(f, cultures_d / name, report, "culturas")
        elif name.startswith(AUTO_DATE_PREFIXES):
            _move(f, auto_dates_d / name, report, "quarentena_auto_dates_arquivos")
            report["quarentena_auto_dates"] += 1
        else:
            _move(f, tables_d / name, report, "tabelas")
            report["tabelas"] += 1

    (definition / "version.json").write_text(
        json.dumps(PBIP_DEFINITION_VERSION, indent=2) + "\n", encoding="utf-8"
    )
    # Ponteiro .pbip (best-effort documentado; Desktop valida ao abrir).
    pbip = dest.with_suffix(".pbip")
    if not pbip.is_file():
        pbip.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "artifacts": [{"type": "dataset", "path": dest.name}],
                    "settings": {"enableAutoRecovery": True},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        report["pbip_pointer"] = pbip.name
    report["nota"] = (
        f"Abra {pbip.name} no Desktop (modo PBIP) para validar; "
        "database.tmdl preservado em _tom_source/; auto-dates em _auto_dates/."
    )
    return report
