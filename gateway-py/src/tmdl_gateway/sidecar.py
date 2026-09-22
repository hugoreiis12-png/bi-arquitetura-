"""Cliente do binário powerbi-modeling-mcp lado-a-lado (pinado).

O gateway nunca implementa TOM direto: mutação objeto-a-objeto e descoberta
localhost passam pelo binário oficial via stdio (JSON-RPC). Sem binário ou sem
Desktop, o gateway opera em fallback offline (pasta TMDL) e reporta explicitly.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


SIDECAR_NPM_PACKAGE = "@microsoft/powerbi-modeling-mcp"
# Preview upstream: pin exato verificado no registry em 2026-09-22.
SIDECAR_DEFAULT_VERSION = "0.5.0-beta.13"
SIDECAR_VSIX_TEMPLATE = (
    "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/"
    "analysis-services/vsextensions/powerbi-modeling-mcp/"
    "[version]/vspackage?targetPlatform=win32-x64"
)


class SidecarError(Exception):
    pass


@dataclass
class SidecarConfig:
    """Como localizar o binário lado-a-lado."""

    mode: str = "npx"  # npx | exe
    version: str = SIDECAR_DEFAULT_VERSION
    exe_path: str = r"C:\MCPServers\PowerBIModelingMCP\extension\server\powerbi-modeling-mcp.exe"
    readonly: bool = False

    @classmethod
    def from_env(cls) -> "SidecarConfig":
        return cls(
            mode=os.environ.get("MODELING_MCP_MODE", "npx"),
            version=os.environ.get("MODELING_MCP_VERSION", SIDECAR_DEFAULT_VERSION),
            exe_path=os.environ.get(
                "MODELING_MCP_EXE",
                r"C:\MCPServers\PowerBIModelingMCP\extension\server\powerbi-modeling-mcp.exe",
            ),
            readonly=os.environ.get("MODELING_MCP_READONLY", "").lower() in ("1", "true"),
        )


def sidecar_available(cfg: SidecarConfig | None = None) -> dict:
    """Healthcheck sem efeitos colaterais (não conecta em modelo)."""
    cfg = cfg or SidecarConfig.from_env()
    if cfg.mode == "exe":
        ok = Path(cfg.exe_path).is_file()
        return {"available": ok, "mode": "exe", "path": cfg.exe_path}
    npx = shutil.which("npx")
    return {
        "available": npx is not None,
        "mode": "npx",
        "package": f"{SIDECAR_NPM_PACKAGE}@{cfg.version}",
        "npx": npx or "",
    }


def _run_json_rpc(payload: dict, cfg: SidecarConfig, timeout: int = 60) -> dict:
    """Envia 1 request JSON-RPC ao binário via stdio. Levanta SidecarError se ausente."""
    info = sidecar_available(cfg)
    if not info["available"]:
        raise SidecarError(f"sidecar indisponível ({info})")
    if cfg.mode == "exe":
        cmd = [cfg.exe_path, "--start"]
    else:
        cmd = ["npx", "-y", f"{SIDECAR_NPM_PACKAGE}@{cfg.version}", "--start"]
    if cfg.readonly:
        cmd.append("--readonly")
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
            # npx no Windows é um shim .cmd: CreateProcess direto falha com
            # FileNotFoundError; shell=True resolve via cmd.exe.
            shell=(os.name == "nt" and cfg.mode == "npx"),
        )
    except FileNotFoundError as exc:
        raise SidecarError(f"binário não encontrado: {exc}") from exc
    except OSError as exc:
        raise SidecarError(f"falha ao iniciar sidecar: {exc}") from exc
    if proc.returncode != 0:
        raise SidecarError(f"sidecar exit {proc.returncode}: {proc.stderr[:500]}")
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"raw": proc.stdout[:2000]}


def list_local_instances(cfg: SidecarConfig | None = None) -> dict:
    """Descoberta de Desktop local (read-only). Fallback offline se ausente."""
    cfg = cfg or SidecarConfig.from_env()
    try:
        res = _run_json_rpc(
            {"request": {"Operation": "ListLocalInstances"}}, cfg, timeout=30
        )
        return {"source": "sidecar", "instances": res.get("data", res)}
    except SidecarError as exc:
        return {"source": "offline", "instances": [], "note": str(exc)}


def export_tmdl_via_sidecar(
    connection: str, database: str, out_dir: str, cfg: SidecarConfig | None = None
) -> dict:
    """Exporta modelo para pasta TMDL via sidecar (somente leitura do modelo)."""
    cfg = cfg or SidecarConfig.from_env()
    payload = {
        "request": {
            "Operation": "ExportToTmdlFolder",
            "ConnectionName": connection,
            "TmdlFolderPath": str(Path(out_dir)),
        }
    }
    try:
        res = _run_json_rpc(payload, cfg, timeout=200)
        return {"source": "sidecar", "result": res, "out_dir": out_dir}
    except SidecarError as exc:
        return {"source": "offline", "out_dir": out_dir, "note": str(exc)}


def execute_in_transaction(
    connection: str,
    operations: list[dict],
    chunk_size: int = 50,
    cfg: SidecarConfig | None = None,
) -> dict:
    """Executa lote em transação obrigatória (Begin → chunks → Commit/Rollback).

    Não executa nada se o sidecar estiver ausente: retorna plano dry-run.
    """
    cfg = cfg or SidecarConfig.from_env()
    if len(operations) > 200:
        raise SidecarError(f"bulk excede 200 operações ({len(operations)})")
    if not operations:
        return {"status": "noop", "chunks": 0, "operations": 0}
    chunks = [
        operations[i : i + chunk_size] for i in range(0, len(operations), chunk_size)
    ]
    info = sidecar_available(cfg)
    if not info["available"]:
        return {
            "status": "dry_run",
            "reason": f"sidecar indisponível ({info.get('mode')})",
            "chunks": len(chunks),
            "operations": len(operations),
        }
    applied: list[dict] = []
    try:
        _run_json_rpc({"request": {"Operation": "Begin"}}, cfg)
    except SidecarError as exc:
        # Binário sumiu entre o healthcheck e o apply: nada foi aplicado,
        # rollback é vácuo — devolve plano dry-run em vez de falhar.
        if "não encontrado" in str(exc) and not applied:
            return {
                "status": "dry_run",
                "reason": str(exc)[:300],
                "chunks": len(chunks),
                "operations": len(operations),
            }
        raise
    try:
        for chunk in chunks:
            for op in chunk:
                _run_json_rpc({"request": op}, cfg)
                applied.append(op)
        _run_json_rpc({"request": {"Operation": "Commit"}}, cfg)
        return {"status": "committed", "chunks": len(chunks), "applied": len(applied)}
    except Exception as exc:  # noqa: BLE001 — rollback obrigatório antes de propagar
        try:
            _run_json_rpc({"request": {"Operation": "Rollback"}}, cfg)
        except Exception:
            pass
        raise SidecarError(f"bulk abortado com rollback ({len(applied)} aplicadas): {exc}")
