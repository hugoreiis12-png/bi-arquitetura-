"""Cliente do binario powerbi-modeling-mcp lado-a-lado (pinado).

O gateway nunca implementa TOM direto: mutacao objeto-a-objeto e descoberta
localhost passam pelo binario oficial via MCP stdio persistente (JSON-RPC:
initialize -> tools/list -> tools/call). Sem binario ou sem Desktop, o
gateway opera em fallback offline (pasta TMDL) e reporta explicitamente.

Historico: a versao anterior usava `subprocess.run` one-shot com envelope
custom `{"request": {"Operation": ...}}`. O servidor real fala MCP JSON-RPC e
fica vivo no stdin, entao o one-shot nunca retornava (timeout/stdout vazio)
e caia em `offline`. Alem disso o wrapper npx polui o stdout (bug upstream
microsoft/powerbi-modeling-mcp#87), o que quebra parse de one-shot.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    """Como localizar o binario lado-a-lado."""

    mode: str = "npx"  # npx | exe
    version: str = SIDECAR_DEFAULT_VERSION
    exe_path: str = r"C:\MCPServers\PowerBIModelingMCP\extension\server\powerbi-modeling-mcp.exe"
    readonly: bool = False
    accepteula: bool = False
    authmode: str = "interactive"  # interactive | serviceprincipal
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "SidecarConfig":
        eula_raw = (
            os.environ.get("MODELING_MCP_ACCEPT_EULA")
            or os.environ.get("PBI_MODELING_MCP_ACCEPT_EULA")
            or ""
        ).lower()
        return cls(
            mode=os.environ.get("MODELING_MCP_MODE", "npx"),
            version=os.environ.get("MODELING_MCP_VERSION", SIDECAR_DEFAULT_VERSION),
            exe_path=os.environ.get(
                "MODELING_MCP_EXE",
                r"C:\MCPServers\PowerBIModelingMCP\extension\server\powerbi-modeling-mcp.exe",
            ),
            readonly=os.environ.get("MODELING_MCP_READONLY", "").lower() in ("1", "true"),
            accepteula=eula_raw in ("1", "true", "yes"),
            authmode=os.environ.get("MODELING_MCP_AUTHMODE", "interactive"),
            timeout_seconds=int(os.environ.get("MODELING_MCP_TIMEOUT", "60")),
        )


def sidecar_available(cfg: SidecarConfig | None = None) -> dict:
    """Healthcheck sem efeitos colaterais (nao conecta em modelo)."""
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


# ---------------------------------------------------------------------------
# Sessao MCP stdio persistente (SDK oficial `mcp`)
# ---------------------------------------------------------------------------

def _stdio_params(cfg: SidecarConfig):
    from mcp.client.stdio import StdioServerParameters

    if cfg.mode == "exe":
        args = ["--start"]
        if cfg.readonly:
            args.append("--readonly")
        if cfg.accepteula:
            args.append("--accepteula")
        if cfg.authmode:
            args.append(f"--authmode={cfg.authmode}")
        env = dict(os.environ)
        if cfg.accepteula:
            env.setdefault("PBI_MODELING_MCP_ACCEPT_EULA", "true")
        return StdioServerParameters(command=cfg.exe_path, args=args, env=env)
    env = dict(os.environ)
    if cfg.accepteula:
        env.setdefault("PBI_MODELING_MCP_ACCEPT_EULA", "true")
    args = ["-y", f"{SIDECAR_NPM_PACKAGE}@{cfg.version}", "--start"]
    if cfg.readonly:
        args.append("--readonly")
    if cfg.accepteula:
        args.append("--accepteula")
    if cfg.authmode:
        args.append(f"--authmode={cfg.authmode}")
    return StdioServerParameters(command="npx", args=args, env=env)


def _result_to_json(res: Any) -> dict:
    """Normaliza CallToolResult do SDK para dict."""
    if res is None:
        return {}
    structured = getattr(res, "structuredContent", None)
    if isinstance(structured, dict) and structured:
        return structured
    content = getattr(res, "content", None)
    texts: list[str] = []
    if isinstance(content, list):
        for block in content:
            t = getattr(block, "text", None)
            if isinstance(t, str) and t.strip():
                texts.append(t)
    elif isinstance(res, dict):
        return res
    for t in texts:
        s = t.strip()
        # Servidor pode devolver JSON puro ou texto com JSON embutido.
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except (json.JSONDecodeError, ValueError):
            continue
    if texts:
        return {"text": "\n".join(texts)}
    if getattr(res, "isError", False):
        return {"error": "tool retornou isError sem conteudo"}
    return {}


def _is_eula_error(payload: Any) -> bool:
    s = json.dumps(payload, ensure_ascii=False, default=str).lower()
    return "eula" in s and ("accept" in s or "blocked" in s or "eula" in s)


async def _call_tool(session: Any, name: str, args: dict) -> dict:
    res = await session.call_tool(name, args or {})
    out = _result_to_json(res)
    if getattr(res, "isError", False) and "error" not in out:
        out = {"error": out.get("text", "tool retornou erro"), **out}
    return out


async def _try_accept_eula(session: Any, tools: Any) -> bool:
    names = {getattr(t, "name", "") for t in (getattr(tools, "tools", []) or [])}
    if "accept_eula" not in names:
        return False
    try:
        await session.call_tool("accept_eula", {})
        return True
    except Exception:
        return False


async def _session_call(
    cfg: SidecarConfig, fn: Any, timeout: int | None = None
) -> Any:
    """Abre sessao stdio, faz handshake e executa fn(session, tools)."""
    from mcp.client.stdio import stdio_client
    from mcp import ClientSession

    info = sidecar_available(cfg)
    if not info["available"]:
        raise SidecarError(f"sidecar indisponivel ({info})")
    if cfg.mode == "exe" and not Path(cfg.exe_path).is_file():
        raise SidecarError(f"binario nao encontrado: {cfg.exe_path}")

    params = _stdio_params(cfg)
    timeout_s = timeout or cfg.timeout_seconds

    async def _run() -> Any:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                # EULA: servidor bloqueia tudo ate aceitar. Tenta aceitar
                # uma vez se o operator optou (flag/env) e segue.
                if cfg.accepteula:
                    try:
                        await _try_accept_eula(session, tools)
                    except Exception:
                        pass
                return await fn(session, tools)

    return await asyncio.wait_for(_run(), timeout=timeout_s)


def _call_sync(cfg: SidecarConfig, fn: Any, timeout: int | None = None) -> Any:
    try:
        return asyncio.run(_session_call(cfg, fn, timeout))
    except FileNotFoundError as exc:
        raise SidecarError(f"binario nao encontrado: {exc}") from exc
    except (OSError, TimeoutError, asyncio.TimeoutError) as exc:
        raise SidecarError(f"falha ao falar com sidecar: {exc}") from exc


def _tool_names(tools: Any) -> dict[str, str]:
    """Mapeia nome normalizado -> nome real."""
    out: dict[str, str] = {}
    for t in getattr(tools, "tools", []) or []:
        name = getattr(t, "name", "")
        if name:
            out[name.lower()] = name
    return out


async def _call_with_variants(
    session: Any, tool_name: str, variants: list[dict]
) -> dict:
    last: dict = {"error": "sem variantes para tentar"}
    for args in variants:
        try:
            out = await _call_tool(session, tool_name, args)
        except Exception as exc:  # noqa: BLE001 -- tenta proxima variante
            last = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        if isinstance(out, dict) and out.get("error") and len(variants) > 1:
            last = out
            continue
        return out
    return last


# ---------------------------------------------------------------------------
# Descoberta de instancias locais (randomica: qualquer .pbip aberto)
# ---------------------------------------------------------------------------

_LIST_OP_VARIANTS = [
    {"Operation": "ListLocalInstances"},
    {"operation": "ListLocalInstances"},
    {"Operation": "list_local_instances"},
    {"operation": "list_local_instances"},
    {"Operation": "ListInstances"},
    {"operation": "ListInstances"},
    {},
]


def _normalize_instances(payload: Any) -> list[dict]:
    """Extrai lista de instancias de qualquer envelope (list ou dict)."""
    items: Any = payload
    if isinstance(payload, dict):
        for key in ("instances", "value", "data", "localInstances", "result"):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break
        else:
            # Envelope {connection, database} unico -> lista de 1.
            if any(k in payload for k in ("connection", "connectionString", "server", "port", "database")):
                items = [payload]
            else:
                return []
    if isinstance(items, dict):
        items = items.get("value", []) or []
    if not isinstance(items, list):
        return []
    norm: list[dict] = []
    for it in items:
        if isinstance(it, str):
            norm.append({"connection": it, "database": "", "name": it})
            continue
        if not isinstance(it, dict):
            continue
        conn = (
            it.get("connection")
            or it.get("connectionString")
            or it.get("connectionName")
            or it.get("server")
            or it.get("address")
            or ""
        )
        port = it.get("port")
        if not conn and port:
            conn = f"localhost:{port}"
        database = (
            it.get("database")
            or it.get("databaseName")
            or it.get("fileName")
            or it.get("name")
            or ""
        )
        name = it.get("name") or it.get("fileName") or database or str(conn)
        norm.append({**it, "connection": str(conn), "database": str(database), "name": str(name)})
    # Filtra entradas totalmente vazias (ruido do envelope).
    return [n for n in norm if n.get("connection") or n.get("database")]


async def _list_instances_async(session: Any, tools: Any) -> dict:
    names = _tool_names(tools)
    # 1) Tool direta dedicada (se existir no futuro).
    for key, real in names.items():
        if ("local" in key and "instance" in key) or key in ("list_local_instances", "listlocalinstances"):
            out = await _call_with_variants(session, real, [{}])
            if not out.get("error"):
                return {"tool": real, "payload": out}
    # 2) Operacao generica de conexao (forma documentada do servidor .NET).
    for key, real in names.items():
        if "connection" in key and "operation" in key:
            out = await _call_with_variants(session, real, _LIST_OP_VARIANTS)
            if not out.get("error"):
                return {"tool": real, "payload": out}
            return {"tool": real, "payload": out}
    # 3) Fallback: qualquer tool com "connection" no nome.
    for key, real in names.items():
        if "connection" in key:
            out = await _call_with_variants(session, real, _LIST_OP_VARIANTS)
            return {"tool": real, "payload": out}
    tool_list = sorted(names.values())
    return {"tool": "", "payload": {"error": f"tool de conexao nao encontrada (tools: {tool_list[:20]})"}}


def list_local_instances(cfg: SidecarConfig | None = None) -> dict:
    """Descoberta de Desktop local (read-only). Fallback offline se ausente.

    Retorna TODAS as instancias (qualquer .pbip aberto, sem filtro fixo):
    {"source": "sidecar", "tool": ..., "instances": [{connection, database, name}]}
    ou {"source": "offline", "instances": [], "error_kind": ..., "note": ...}.
    """
    cfg = cfg or SidecarConfig.from_env()

    async def _fn(session: Any, tools: Any) -> dict:
        res = await _list_instances_async(session, tools)
        payload = res.get("payload", {})
        if isinstance(payload, dict) and _is_eula_error(payload) and not cfg.accepteula:
            payload = {
                **payload,
                "hint": "Servidor bloqueado pelo EULA: rode com --accepteula (apos ler o EULA) ou defina PBI_MODELING_MCP_ACCEPT_EULA=true",
            }
        return {"tool": res.get("tool", ""), "payload": payload}

    try:
        res = _call_sync(cfg, _fn, timeout=30)
    except SidecarError as exc:
        msg = str(exc)
        kind = "sidecar_ausente" if ("indisponivel" in msg or "nao encontrado" in msg) else "protocolo_quebrado"
        return {"source": "offline", "instances": [], "error_kind": kind, "note": msg}
    except Exception as exc:  # noqa: BLE001 -- nunca quebra o gateway
        return {"source": "offline", "instances": [], "error_kind": "protocolo_quebrado", "note": f"{type(exc).__name__}: {exc}"}
    payload = res.get("payload", {})
    if isinstance(payload, dict) and payload.get("error"):
        err = str(payload.get("error"))
        kind = "desktop_fechado" if ("desktop" in err.lower() or "instance" in err.lower()) else "protocolo_quebrado"
        return {"source": "offline", "instances": [], "error_kind": kind, "note": err, "tool": res.get("tool", "")}
    instances = _normalize_instances(payload)
    return {"source": "sidecar", "tool": res.get("tool", ""), "instances": instances}


# ---------------------------------------------------------------------------
# Export TMDL (somente leitura do modelo)
# ---------------------------------------------------------------------------

def export_tmdl_via_sidecar(
    connection: str, database: str, out_dir: str, cfg: SidecarConfig | None = None
) -> dict:
    """Exporta modelo para pasta TMDL via sidecar (somente leitura do modelo)."""
    cfg = cfg or SidecarConfig.from_env()

    variants = [
        {"ConnectionName": connection, "TmdlFolderPath": str(Path(out_dir))},
        {"connectionName": connection, "tmdlFolderPath": str(Path(out_dir))},
        {"Connection": connection, "Database": database, "TmdlFolderPath": str(Path(out_dir))},
        {"connection": connection, "database": database, "tmdlFolderPath": str(Path(out_dir))},
    ]

    async def _fn(session: Any, tools: Any) -> dict:
        names = _tool_names(tools)
        for key, real in names.items():
            if "database" in key and "operation" in key:
                for extra in ({"Operation": "ExportToTmdlFolder"}, {"operation": "ExportToTmdlFolder"}):
                    for v in variants:
                        out = await _call_with_variants(session, real, [{**extra, **v}])
                        if not out.get("error"):
                            return {"tool": real, "payload": out}
                return {"tool": real, "payload": {"error": "ExportToTmdlFolder falhou em todas as variantes"}}
        for key, real in names.items():
            if "database" in key:
                out = await _call_with_variants(session, real, variants)
                return {"tool": real, "payload": out}
        return {"tool": "", "payload": {"error": "tool de database nao encontrada"}}

    try:
        res = _call_sync(cfg, _fn, timeout=200)
    except SidecarError as exc:
        return {"source": "offline", "out_dir": out_dir, "note": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"source": "offline", "out_dir": out_dir, "note": f"{type(exc).__name__}: {exc}"}
    payload = res.get("payload", {})
    if isinstance(payload, dict) and payload.get("error"):
        return {"source": "offline", "out_dir": out_dir, "note": str(payload.get("error"))}
    return {"source": "sidecar", "tool": res.get("tool", ""), "result": payload, "out_dir": out_dir}


# ---------------------------------------------------------------------------
# Bulk em transacao obrigatoria (mesma sessao: Begin -> chunks -> Commit)
# ---------------------------------------------------------------------------

def _tx_variants(op: str) -> list[dict]:
    return [{"Operation": op}, {"operation": op}, {}]


async def _tx_call(session: Any, tools: Any, op: str) -> dict:
    names = _tool_names(tools)
    for key, real in names.items():
        if "transaction" in key and "operation" in key:
            return await _call_with_variants(session, real, _tx_variants(op))
    for key, real in names.items():
        if "transaction" in key:
            return await _call_with_variants(session, real, _tx_variants(op))
    return {"error": "tool de transacao nao encontrada"}


async def _dispatch_op(session: Any, tools: Any, op: dict) -> dict:
    """Roteia uma operacao generica para a tool MCP correspondente."""
    names = _tool_names(tools)
    if not isinstance(op, dict):
        return {"error": f"operacao invalida: {op!r}"}
    # Forma MCP explicita: {"tool": ..., "arguments": {...}}.
    if "tool" in op and isinstance(op["tool"], str) and op["tool"].lower() in names:
        return await _call_tool(session, names[op["tool"].lower()], op.get("arguments", {}) or {})
    # Forma legada {"Operation": X, ...}: tenta categorias conhecidas.
    operation = op.get("Operation") or op.get("operation") or ""
    args = {k: v for k, v in op.items() if k not in ("Operation", "operation", "tool", "arguments")}
    op_low = str(operation).lower()
    if op_low in ("validate", "execute", "clearcache"):
        for key, real in names.items():
            if "dax" in key and "query" in key:
                out = await _call_with_variants(session, real, [{**a, **args} for a in _tx_variants(operation)])
                if not out.get("error"):
                    return out
    # Fallback: tenta cada categoria de modelagem com a operacao como args.
    for key, real in names.items():
        if any(w in key for w in ("database", "model", "table", "measure", "column", "relationship", "dax")):
            out = await _call_with_variants(
                session, real, [{**a, **args} for a in _tx_variants(operation)] if operation else [args]
            )
            if not out.get("error"):
                return out
    return {"error": f"operacao sem rota MCP: {operation or op}"}


def execute_in_transaction(
    connection: str,
    operations: list[dict],
    chunk_size: int = 50,
    cfg: SidecarConfig | None = None,
) -> dict:
    """Executa lote em transacao obrigatoria (Begin -> chunks -> Commit/Rollback).

    Nao executa nada se o sidecar estiver ausente: retorna plano dry-run.
    """
    cfg = cfg or SidecarConfig.from_env()
    if len(operations) > 200:
        raise SidecarError(f"bulk excede 200 operacoes ({len(operations)})")
    if not operations:
        return {"status": "noop", "chunks": 0, "operations": 0}
    chunks = [
        operations[i : i + chunk_size] for i in range(0, len(operations), chunk_size)
    ]
    info = sidecar_available(cfg)
    if not info["available"]:
        return {
            "status": "dry_run",
            "reason": f"sidecar indisponivel ({info.get('mode')})",
            "chunks": len(chunks),
            "operations": len(operations),
        }

    async def _fn(session: Any, tools: Any) -> dict:
        begun = await _tx_call(session, tools, "Begin")
        if begun.get("error"):
            # Servidor sem transacao explicita: executa direto (bulk simples).
            applied = 0
            for chunk in chunks:
                for op in chunk:
                    out = await _dispatch_op(session, tools, op)
                    if out.get("error"):
                        raise SidecarError(f"bulk abortado ({applied} aplicadas): {out.get('error')}")
                    applied += 1
            return {"status": "committed", "chunks": len(chunks), "applied": applied, "transaction": "sem_begin_explicito"}
        applied: list[dict] = []
        try:
            for chunk in chunks:
                for op in chunk:
                    out = await _dispatch_op(session, tools, op)
                    if out.get("error"):
                        raise SidecarError(str(out.get("error"))[:500])
                    applied.append(op)
            committed = await _tx_call(session, tools, "Commit")
            if committed.get("error"):
                raise SidecarError(str(committed.get("error"))[:500])
            return {"status": "committed", "chunks": len(chunks), "applied": len(applied)}
        except Exception:
            try:
                await _tx_call(session, tools, "Rollback")
            except Exception:
                pass
            raise

    try:
        return _call_sync(cfg, _fn, timeout=200)
    except SidecarError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SidecarError(f"bulk abortado com rollback: {exc}") from exc
