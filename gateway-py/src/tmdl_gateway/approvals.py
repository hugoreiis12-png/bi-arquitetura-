"""Approval tokens single-use para `tmdl_commit` (arquivo JSON, TTL 15min).

Espelha a semântica do `ApprovalService` do MCP Python (sem exigir Redis):
token `apv_*`, binding `action:target`, prod (`main`) exige 2 aprovadores.
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from pathlib import Path


TOKEN_TTL_SECONDS = 15 * 60


class ApprovalError(Exception):
    pass


def _store_dir(repo: Path) -> Path:
    d = Path(repo) / ".gateway" / "approvals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> float:
    return time.time()


def required_approvers(action: str, target: str) -> int:
    t = f"{action}:{target}"
    if action == "tmdl_commit" and (":main" in t or t.endswith(":Vendas")):
        return 2
    if "prod" in t:
        return 2
    return 1


def request_token(
    repo: str | Path,
    action: str,
    target: str,
    reason: str = "",
    requested_by: str = "dev",
) -> dict:
    repo_p = Path(repo)
    token = f"apv_{secrets.token_urlsafe(24)}"
    record = {
        "token": token,
        "action": action,
        "target": target,
        "reason": reason,
        "requested_by": requested_by,
        "approvers": [],
        "required_approvers": required_approvers(action, target),
        "issued_at": _now(),
        "expires_at": _now() + TOKEN_TTL_SECONDS,
        "used": False,
        "id": uuid.uuid4().hex[:12],
    }
    (_store_dir(repo_p) / f"{record['id']}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def _all(repo_p: Path) -> list[dict]:
    out = []
    d = _store_dir(repo_p)
    for p in d.glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except OSError:
            continue
    return out


def approve_token(repo: str | Path, token: str, approver: str) -> dict:
    repo_p = Path(repo)
    for rec in _all(repo_p):
        if rec.get("token") == token:
            if rec.get("used"):
                raise ApprovalError("token já utilizado (single-use)")
            if _now() > float(rec.get("expires_at", 0)):
                raise ApprovalError("token expirado")
            if approver not in rec["approvers"]:
                rec["approvers"].append(approver)
            p = _store_dir(repo_p) / f"{rec['id']}.json"
            p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            return rec
    raise ApprovalError("token não encontrado")


def check_token(repo: str | Path, token: str, action: str, target: str) -> dict:
    """Valida sem consumir (para checar antes de operações que podem falhar)."""
    repo_p = Path(repo)
    for rec in _all(repo_p):
        if rec.get("token") == token:
            if rec.get("used"):
                raise ApprovalError("token já utilizado (single-use)")
            if _now() > float(rec.get("expires_at", 0)):
                raise ApprovalError("token expirado")
            if rec.get("action") != action or rec.get("target") != target:
                raise ApprovalError(
                    f"token binding divergente: {rec.get('action')}:{rec.get('target')} != {action}:{target}"
                )
            if len(rec.get("approvers", [])) < int(rec.get("required_approvers", 1)):
                raise ApprovalError(
                    f"aprovadores insuficientes: {len(rec['approvers'])}/{rec['required_approvers']}"
                )
            return rec
    raise ApprovalError("token não encontrado")


def consume_token(repo: str | Path, token: str) -> dict:
    """Marca single-use após sucesso. Falha se já consumido."""
    repo_p = Path(repo)
    for rec in _all(repo_p):
        if rec.get("token") == token:
            if rec.get("used"):
                raise ApprovalError("token já utilizado (single-use)")
            rec["used"] = True
            rec["used_at"] = _now()
            p = _store_dir(repo_p) / f"{rec['id']}.json"
            p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            return rec
    raise ApprovalError("token não encontrado")


def validate_for_commit(
    repo: str | Path, token: str, action: str, target: str
) -> dict:
    """Valida e consome o token (single-use). Falha sem escrever nada."""
    repo_p = Path(repo)
    for rec in _all(repo_p):
        if rec.get("token") == token:
            if rec.get("used"):
                raise ApprovalError("token já utilizado (single-use)")
            if _now() > float(rec.get("expires_at", 0)):
                raise ApprovalError("token expirado")
            if rec.get("action") != action or rec.get("target") != target:
                raise ApprovalError(
                    f"token binding divergente: {rec.get('action')}:{rec.get('target')} != {action}:{target}"
                )
            if len(rec.get("approvers", [])) < int(rec.get("required_approvers", 1)):
                raise ApprovalError(
                    f"aprovadores insuficientes: {len(rec['approvers'])}/{rec['required_approvers']}"
                )
            rec["used"] = True
            rec["used_at"] = _now()
            p = _store_dir(repo_p) / f"{rec['id']}.json"
            p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            return rec
    raise ApprovalError("token não encontrado")
